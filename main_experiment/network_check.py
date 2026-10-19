"""No-key Docker boundary check; TLS handshakes only, no model requests."""
import argparse
import json
from pathlib import Path

from .backend import DockerSession, capture


def check(image, out):
    out=Path(out)
    if out.exists():
        raise ValueError('Network check destination must not exist')
    out.mkdir(parents=True)
    inputs=out/'empty-inputs';inputs.mkdir()
    checks=[]
    for provider in ('openai','anthropic','google'):
        directory=out/provider;directory.mkdir()
        c={'inputs':str(inputs.resolve()),'cpus':4,'memory':'8g'}
        model={'model':provider+'/network-check','key_env':'UNUSED_NO_CREDENTIAL'}
        agent=DockerSession(c,model,directory,image)
        try:
            agent.start()
            # No keys, prompts, source data, HTTP requests or paid invocations.
            probe=(Path(__file__).parent/'network/probe.py').read_text()
            positive=probe.split("if __name__ == '__main__':")[0]+'''
with socket.create_connection((sys.argv[1],8080), timeout=10) as sock:
    sock.sendall(f'CONNECT {sys.argv[2]}:443 HTTP/1.1\\r\\nHost: {sys.argv[2]}:443\\r\\n\\r\\n'.encode())
    header=b''
    while not header.endswith(b'\\r\\n\\r\\n'):
        block=sock.recv(1)
        if not block:
            raise RuntimeError('Gateway closed allowed CONNECT')
        header+=block
    if not header.startswith(b'HTTP/1.1 200'):
        raise RuntimeError('Allowed CONNECT rejected')
    with ssl.create_default_context().wrap_socket(sock,server_hostname=sys.argv[2]):
        print('provider_tls_ok')
'''
            result=capture(['docker','exec',agent.name,'python','-c',positive,
                            agent.egress.ip,agent.egress.allowed[0]])
            if result!='provider_tls_ok':
                raise RuntimeError('Provider TLS check missing')
            checks.append({'provider':provider,'network_probes':'passed','provider_tls':'passed'})
        finally:
            agent.stop()
            # This synthetic check retains host logs but disposes its resources.
            import subprocess
            subprocess.run(['docker','rm','-f',agent.name,agent.egress.name],check=False,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['docker','volume','rm',agent.name+'-state'],check=False,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (out/'results.json').write_text(json.dumps(checks,indent=2)+'\n')
    return checks


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(check(a.image,a.out),indent=2))
