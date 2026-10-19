"""No-key pre-agent bypass probes. Run inside the real restricted container."""
import json
import socket
import ssl
import sys


def blocked_connect(address, port, typ=socket.SOCK_STREAM):
    with socket.socket(socket.AF_INET, typ) as sock:
        sock.settimeout(2)
        try:
            if typ == socket.SOCK_DGRAM:
                sock.sendto(b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                            b'\x07example\x03com\x00\x00\x01\x00\x01', (address,port))
                sock.recvfrom(512)
            else:
                sock.connect((address,port))
        except OSError:
            return True
    return False


def check(proxy, allowed, docker_dns='127.0.0.11'):
    results = {}
    # Numeric IPs deliberately bypass DNS, proxy env vars and client libraries.
    results['direct_https_blocked'] = blocked_connect('1.1.1.1',443)
    results['direct_http_blocked'] = blocked_connect('1.1.1.1',80)
    results['external_dns_blocked'] = blocked_connect('1.1.1.1',53)
    results['udp_dns_blocked'] = blocked_connect('1.1.1.1',53,socket.SOCK_DGRAM)
    results['docker_dns_udp_blocked'] = blocked_connect(docker_dns,53,socket.SOCK_DGRAM)
    results['docker_dns_tcp_blocked'] = blocked_connect(docker_dns,53)
    with socket.create_connection((proxy,8080), timeout=5) as sock:
        sock.sendall(b'CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n')
        results['external_proxy_host_blocked'] = sock.recv(4096).startswith(b'HTTP/1.1 403')
    # An API-host CONNECT with a DIFFERENT TLS SNI must fail, too.
    with socket.create_connection((proxy,8080), timeout=5) as sock:
        request = f'CONNECT {allowed}:443 HTTP/1.1\r\nHost: {allowed}:443\r\n\r\n'.encode()
        sock.sendall(request)
        header=b''
        while not header.endswith(b'\r\n\r\n'):
            chunk=sock.recv(1)
            if not chunk:
                raise RuntimeError('Gateway did not accept provider CONNECT')
            header+=chunk
        if not header.startswith(b'HTTP/1.1 200'):
            raise RuntimeError('Gateway did not accept provider CONNECT')
        try:
            with ssl.create_default_context().wrap_socket(sock,server_hostname='example.com'):
                results['domain_fronting_blocked'] = False
        except (ssl.SSLError,OSError):
            results['domain_fronting_blocked'] = True
    if not all(results.values()):
        raise RuntimeError('Outbound network bypass probe failed: '+json.dumps(results))
    return results


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1],sys.argv[2])))
