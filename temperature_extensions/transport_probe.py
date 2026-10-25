import http.server,json,threading,subprocess,os
records=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  d=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  records.append({'path':self.path,'generationConfig':d.get('generationConfig')})
  body={'candidates':[{'content':{'role':'model','parts':[{'text':'READY'}]},'finishReason':'STOP'}],'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':1,'totalTokenCount':11},'modelVersion':'gemini-3.1-pro-preview'}
  stream='alt=sse'in self.path
  payload=(('data: '+json.dumps(body)+'\n\n')if stream else json.dumps(body)).encode()
  self.send_response(200);self.send_header('Content-Type','text/event-stream'if stream else'application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
server=http.server.HTTPServer(('127.0.0.1',18999),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
config={'enabled_providers':['google'],'provider':{'google':{'options':{'baseURL':'http://127.0.0.1:18999/v1beta'}}},'permission':{'*':'allow','webfetch':'deny','websearch':'deny','task':'deny'},**json.loads(os.environ['SAMPLER_CONFIG'])}
env=dict(os.environ,GOOGLE_GENERATIVE_AI_API_KEY='nonclinical-dummy',OPENCODE_CONFIG_CONTENT=json.dumps(config),OPENCODE_DISABLE_MODELS_FETCH='true',OPENCODE_DISABLE_AUTOUPDATE='true',OPENCODE_DISABLE_DEFAULT_PLUGINS='true')
p=subprocess.run(['opencode','run','--model','google/gemini-3.1-pro-preview','--format','json','Reply READY. Do not call tools.'],env=env,capture_output=True,text=True,timeout=90)
print(json.dumps({'exit_code':p.returncode,'requests':records,'stdout':p.stdout[-1200:],'stderr':p.stderr[-1200:]}))
server.shutdown()
