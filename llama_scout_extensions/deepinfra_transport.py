"""Offline request capture with dummy credentials and no external network."""
import http.server
import json
import os
import subprocess
import threading

records=[]
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_POST(self):
        d=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        records.append({'path':self.path, 'model':d.get('model'),
            'temperature':d.get('temperature'), 'reasoning_effort':d.get('reasoning_effort'),
            'max_tokens':d.get('max_tokens'), 'max_completion_tokens':d.get('max_completion_tokens'),
            'stream':d.get('stream'), 'tool_count':len(d.get('tools',[])),
            'field_names':sorted(d)})
        usage={'prompt_tokens':20,'completion_tokens':5,'total_tokens':25}
        base={'id':'chatcmpl-nonclinical','created':1,'model':d['model']}
        if d.get('stream'):
            data=[{**base,'object':'chat.completion.chunk','choices':[{'index':0,'delta':{'role':'assistant','content':'READY'},'finish_reason':None}]},
                  {**base,'object':'chat.completion.chunk','choices':[{'index':0,'delta':{},'finish_reason':'stop'}],'usage':usage}]
            body=(''.join('data: '+json.dumps(x)+'\n\n' for x in data)+'data: [DONE]\n\n').encode()
            content_type='text/event-stream'
        else:
            body=json.dumps({**base,'object':'chat.completion','choices':[{'index':0,'message':{'role':'assistant','content':'READY'},'finish_reason':'stop'}],'usage':usage}).encode()
            content_type='application/json'
        self.send_response(200)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)

server=http.server.HTTPServer(('127.0.0.1',18999),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
settings=json.loads(os.environ['PROBE_CONFIG'])
settings['provider']['deepinfra']['options']['baseURL']='http://127.0.0.1:18999/v1'
env=dict(os.environ,DEEPINFRA_API_KEY='nonclinical-dummy',OPENCODE_CONFIG_CONTENT=json.dumps(settings),
         OPENCODE_DISABLE_MODELS_FETCH='true',OPENCODE_DISABLE_AUTOUPDATE='true',OPENCODE_DISABLE_DEFAULT_PLUGINS='true')
try:
    p=subprocess.run(['opencode','run','--format','json','--model',os.environ['PROBE_MODEL'],
                      'Reply READY. Do not call tools.'],env=env,capture_output=True,text=True,timeout=90)
    print(json.dumps({'exit_code':p.returncode,'requests':records,'stderr':p.stderr[-1200:]}))
finally:
    server.shutdown()
