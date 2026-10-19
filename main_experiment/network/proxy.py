"""HTTPS CONNECT gateway: exact provider hosts, public DNS, matching TLS SNI.

No credentials, study files or Docker socket are mounted here. TLS is not
terminated; logs contain connection decisions only, never request bodies/keys.
"""
import ipaddress
import json
import os
import select
import socket
import socketserver
import time


def authority(value, allowed):
    if value.count(':') != 1:
        raise ValueError('authority')
    host, port = value.lower().split(':')
    if port != '443' or host not in allowed:
        raise ValueError('host-or-port')
    return host


def server_name(hello):
    """Extract the sole DNS SNI from a complete ClientHello handshake message."""
    if len(hello) < 4 or hello[0] != 1 or int.from_bytes(hello[1:4], 'big') != len(hello)-4:
        raise ValueError('client-hello')
    pos = 4
    def take(n):
        nonlocal pos
        if pos+n > len(hello):
            raise ValueError('truncated-hello')
        value = hello[pos:pos+n]; pos += n
        return value
    def number(n):
        return int.from_bytes(take(n), 'big')
    take(34)  # protocol version and random
    take(number(1))
    take(number(2))
    take(number(1))
    extension_end = pos + 2 + number(2)
    if extension_end != len(hello):
        raise ValueError('extensions-length')
    names = []
    seen = set()
    while pos < extension_end:
        kind, size = number(2), number(2)
        payload = take(size)
        if kind in seen:
            raise ValueError('duplicate-extension')
        seen.add(kind)
        if kind == 0:
            if len(payload) < 2 or int.from_bytes(payload[:2], 'big') != len(payload)-2:
                raise ValueError('sni-length')
            offset = 2
            while offset < len(payload):
                if offset+3 > len(payload):
                    raise ValueError('sni-entry')
                typ = payload[offset]
                n = int.from_bytes(payload[offset+1:offset+3], 'big'); offset += 3
                name = payload[offset:offset+n]; offset += n
                if typ != 0 or len(name) != n or not n:
                    raise ValueError('sni-entry')
                names.append(name.decode('ascii').lower())
    if len(names) != 1:
        raise ValueError('sni-required')
    return names[0]


def exact(sock, n):
    data = b''
    while len(data) < n:
        block = sock.recv(n-len(data))
        if not block:
            raise ValueError('connection-ended')
        data += block
    return data


def client_hello(sock):
    raw, handshake = b'', b''
    while len(raw) < 131072:
        header = exact(sock, 5)
        size = int.from_bytes(header[3:5], 'big')
        if header[0] != 22 or header[1] != 3 or not 0 < size <= 18432:
            raise ValueError('tls-handshake-required')
        payload = exact(sock, size)
        raw += header + payload; handshake += payload
        if len(handshake) >= 4:
            length = 4 + int.from_bytes(handshake[1:4], 'big')
            if length > 65536:
                raise ValueError('hello-too-large')
            if len(handshake) >= length:
                return raw, server_name(handshake[:length])
    raise ValueError('hello-too-large')


def public_addresses(host):
    addresses = sorted({r[4][0] for r in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('non-public-upstream')
    return addresses


def audit(decision, reason, host=None):
    print(json.dumps({'time_unix': time.time(), 'decision': decision,
                      'reason': reason, 'host': host}), flush=True)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        host = None
        try:
            self.request.settimeout(10)
            header = b''
            while not header.endswith(b'\r\n\r\n'):
                if len(header) >= 8192:
                    raise ValueError('headers-too-large')
                header += exact(self.request, 1)
            line = header.split(b'\r\n', 1)[0].decode('ascii').split(' ')
            if len(line) != 3 or line[0] != 'CONNECT' or line[2] not in ('HTTP/1.0','HTTP/1.1'):
                raise ValueError('connect-only')
            host = authority(line[1], self.server.allowed)
            self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            raw, sni = client_hello(self.request)
            if sni != host:
                raise ValueError('sni-mismatch')
            # Resolve once, reject private/link-local answers, and connect to the
            # checked IP itself; no second DNS lookup or domain-rebinding window.
            addresses = public_addresses(host)
            upstream = None
            for address in addresses:
                try:
                    upstream = socket.create_connection((address,443), timeout=10)
                    break
                except OSError:
                    continue
            if upstream is None:
                raise ValueError('upstream-unreachable')
            with upstream:
                upstream.sendall(raw)
                audit('allow', 'provider-tls', host)
                self.request.settimeout(30); upstream.settimeout(30)
                while True:
                    ready, _, _ = select.select([self.request, upstream], [], [], 120)
                    if not ready:
                        break
                    for source in ready:
                        block = source.recv(65536)
                        if not block:
                            return
                        (upstream if source is self.request else self.request).sendall(block)
        except (ValueError, OSError, UnicodeError) as exc:
            audit('deny', str(exc) if isinstance(exc, ValueError) else type(exc).__name__, host)
            try:
                self.request.sendall(b'HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            except OSError:
                pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    allowed = json.loads(os.environ['ALLOWED_HOSTS'])
    if not allowed or any(not isinstance(h,str) for h in allowed):
        raise ValueError('Explicit provider host allowlist required')
    with Server(('0.0.0.0',8080), Handler) as server:
        server.allowed = allowed
        server.serve_forever()
