"""No-key unit tests for the exact-host/TLS gate and agent namespace rules."""
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import patch

from main_experiment.egress import HERE, Egress, hosts, policy
from main_experiment.network.firewall import rules
from main_experiment.network.proxy import authority, client_hello, public_addresses, server_name


def hello(host):
    context=ssl.create_default_context()
    incoming,outgoing=ssl.MemoryBIO(),ssl.MemoryBIO()
    client=context.wrap_bio(incoming,outgoing,server_side=False,server_hostname=host)
    try:
        client.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return outgoing.read()


class FakeSocket:
    def __init__(self,data): self.data=data
    def recv(self,n):
        result=self.data[:min(n,3)];self.data=self.data[len(result):];return result


class EgressTests(unittest.TestCase):
    def test_exact_host_port_only(self):
        allowed=['api.openai.com']
        self.assertEqual('api.openai.com',authority('API.OPENAI.COM:443',allowed))
        for value in ['api.openai.com.evil.test:443','api.openai.com:80','api.openai.com.:443',
                      '127.0.0.1:443','[::1]:443','user@api.openai.com:443','example.com:443']:
            with self.assertRaises(ValueError):authority(value,allowed)

    def test_real_clienthello_and_fragmented_socket(self):
        raw=hello('api.openai.com')
        returned,name=client_hello(FakeSocket(raw))
        self.assertEqual('api.openai.com',name)
        self.assertEqual(raw,returned)
        handshake=raw[5:]
        # Fragment the handshake over two TLS records as well as socket reads.
        split=30
        fragmented=b''.join(b'\x16\x03\x01'+len(part).to_bytes(2,'big')+part
                            for part in (handshake[:split],handshake[split:]))
        self.assertEqual('api.openai.com',client_hello(FakeSocket(fragmented))[1])

    def test_non_tls_and_truncated_rejected(self):
        for raw in [b'GET / HTTP/1.1\r\n',b'\x16\x03\x01\x00\x20abc',b'']:
            with self.assertRaises(ValueError):client_hello(FakeSocket(raw))

    def test_missing_sni_rejected(self):
        raw=hello(None)
        with self.assertRaises(ValueError):client_hello(FakeSocket(raw))

    def test_dns_requires_only_public_addresses(self):
        for addresses in [['127.0.0.1'],['169.254.169.254'],['10.0.0.1'],['::1'],['1.1.1.1','172.17.0.1']]:
            records=[(None,None,None,None,(x,443)) for x in addresses]
            with patch('socket.getaddrinfo',return_value=records):
                with self.assertRaises(ValueError):public_addresses('api.openai.com')
        with patch('socket.getaddrinfo',return_value=[(None,None,None,None,('1.1.1.1',443))]):
            self.assertEqual(['1.1.1.1'],public_addresses('api.openai.com'))

    def test_firewall_drop_both_families_no_dns_or_general_loopback(self):
        rows=rules('172.17.0.2')
        self.assertIn(['iptables','-P','OUTPUT','DROP'],rows)
        self.assertIn(['ip6tables','-P','OUTPUT','DROP'],rows)
        accepts=[r for r in rows if 'ACCEPT' in r]
        self.assertEqual(3,len(accepts))
        self.assertTrue(all('-p' in r and r[r.index('-p')+1]=='tcp' for r in accepts))
        self.assertEqual(1,sum('8080' in r for r in accepts))
        self.assertIn('127.0.0.1/32',accepts[0])
        self.assertIn('::1/128',accepts[1])
        with self.assertRaises(ipaddress.AddressValueError):rules('example.com')

    def test_selected_provider_only_and_proxy_env(self):
        for provider in ('openai','anthropic','google'):
            self.assertEqual(1,len(hosts({'model':provider+'/model'})))
        class Session:
            name='test';model={'model':'openai/model'}
        gate=Egress(Session(),lambda *args:None);gate.ip='172.17.0.2'
        env=gate.environment()
        self.assertEqual('http://172.17.0.2:8080',env['HTTPS_PROXY'])
        self.assertEqual('true',env['OPENCODE_DISABLE_MODELS_FETCH'])
        self.assertNotIn('*',env['NO_PROXY'])

    def test_gateway_has_no_study_or_keys_and_helper_not_host_network(self):
        calls=[]
        class Session:
            name='test';model={'model':'openai/model'};image='image'
        with tempfile.TemporaryDirectory() as t:
            s=Session();s.directory=Path(t)
            def capture(argv):
                calls.append(argv)
                if 'inspect' in argv:return '172.17.0.2'
                if '/gateway/firewall.py' in argv:return '{}'
                if 'exec' in argv:return '{"probe":true}'
                return 'container'
            gate=Egress(s,capture);gate.start();gate.restrict()
            gateway=calls[0]
            self.assertIn('--read-only',gateway)
            self.assertNotIn('/inputs',str(gateway))
            self.assertNotIn('API_KEY',str(gateway))
            helper=next(c for c in calls if '--cap-add' in c)
            self.assertIn('container:test',helper)
            self.assertNotIn('host',helper)
            self.assertNotIn('--privileged',helper)
            self.assertTrue((s.directory/'egress-probes.json').exists())
