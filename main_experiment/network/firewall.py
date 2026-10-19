"""Apply rules inside the AGENT network namespace; never the host namespace.

Invoked only by a short-lived controller helper with NET_ADMIN. The agent
itself has no capabilities. No helper shares the agent's files or PID namespace.
"""
import ipaddress
import json
import subprocess
import sys


def rules(proxy):
    ip = ipaddress.IPv4Address(proxy)
    return [
        ['iptables','-P','OUTPUT','DROP'],
        ['ip6tables','-P','OUTPUT','DROP'],
        ['iptables','-F','OUTPUT'],
        ['ip6tables','-F','OUTPUT'],
        # TCP loopback supports the local OpenCode server, not DNS forwarding.
        ['iptables','-A','OUTPUT','-o','lo','-d','127.0.0.1/32','-p','tcp','-j','ACCEPT'],
        ['ip6tables','-A','OUTPUT','-o','lo','-d','::1/128','-p','tcp','-j','ACCEPT'],
        ['iptables','-A','OUTPUT','-d',str(ip),'-p','tcp','--dport','8080','-j','ACCEPT'],
    ]


if __name__ == '__main__':
    for argv in rules(sys.argv[1]):
        subprocess.run(argv, check=True)
    evidence = {tool: subprocess.check_output([tool,'-S','OUTPUT'],text=True)
                for tool in ('iptables','ip6tables')}
    print(json.dumps(evidence))
