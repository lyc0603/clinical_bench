"""Controller-only setup of provider gateway and immutable agent egress rules."""
import json
from pathlib import Path
import subprocess

from experiment.experiment import save

HERE = Path(__file__).resolve().parent / 'network'


def policy():
    return json.loads((HERE / 'policy.json').read_text())


def hosts(model):
    return policy()['providers'][model['model'].split('/',1)[0]]


class Egress:
    def __init__(self, session, capture):
        self.session, self.capture = session, capture
        self.name = session.name + '-gateway'
        self.allowed = hosts(session.model)

    def start(self):
        s = self.session
        self.capture(['docker','run','-d','--name',self.name,'--network','bridge',
            '--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=16m',
            '--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--cpus','1','--memory','128m','--pids-limit','64',
            '-e','PYTHONDONTWRITEBYTECODE=1','-e','ALLOWED_HOSTS='+json.dumps(self.allowed),
            '-v',str(HERE / 'proxy.py')+':/gateway/proxy.py:ro',
            s.image,'python','/gateway/proxy.py'])
        self.ip = self.capture(['docker','inspect','--format',
                               '{{.NetworkSettings.Networks.bridge.IPAddress}}',self.name])
        import ipaddress
        ipaddress.IPv4Address(self.ip)

    def environment(self):
        url = 'http://'+self.ip+':8080'
        return {'HTTP_PROXY':url,'HTTPS_PROXY':url,'http_proxy':url,'https_proxy':url,
                'ALL_PROXY':url,'all_proxy':url,
                'NO_PROXY':'localhost,127.0.0.1,::1','no_proxy':'localhost,127.0.0.1,::1',
                'OPENCODE_DISABLE_AUTOUPDATE':'true','OPENCODE_DISABLE_MODELS_FETCH':'true',
                'OPENCODE_DISABLE_DEFAULT_PLUGINS':'true','OPENCODE_DISABLE_LSP_DOWNLOAD':'true',
                'OPENCODE_ENABLE_EXA':'false','OPENCODE_ENABLE_PARALLEL':'false'}

    def restrict(self):
        s = self.session
        # Docker creates a distinct network namespace for the agent. This
        # helper shares ONLY that namespace, never host networking or mounts.
        raw = self.capture(['docker','run','--rm','--network','container:'+s.name,
            '--cap-drop','ALL','--cap-add','NET_ADMIN','--security-opt','no-new-privileges',
            '-v',str(HERE / 'firewall.py')+':/gateway/firewall.py:ro',
            s.image,'python','/gateway/firewall.py',self.ip])
        save(s.directory / 'egress-rules.json',json.loads(raw))
        # Probe code is controller supplied and gone before the model starts.
        # It uses no provider credential and sends no study content.
        raw = self.capture(['docker','exec',s.name,'python','-c',
                            (HERE / 'probe.py').read_text(),self.ip,self.allowed[0]])
        save(s.directory / 'egress-probes.json',json.loads(raw))
        save(s.directory / 'egress-policy.json',{
            'policy':policy(),'allowed_hosts':self.allowed,'gateway':self.name,
            'gateway_ip':self.ip,'direct_egress':'DROP IPv4 and IPv6 except gateway TCP8080 and TCP localhost'})

    def stop(self):
        s = self.session
        # Connection decisions only. Never record CONNECT headers, TLS bodies,
        # credentials or prompts at the gateway.
        log = s.directory / 'egress-gateway.jsonl'
        with log.open('w') as f:
            subprocess.run(['docker','logs',self.name],stdout=f,stderr=subprocess.STDOUT,timeout=30)
        subprocess.run(['docker','stop','--time','1',self.name],stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=30)
