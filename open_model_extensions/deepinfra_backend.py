"""DeepInfra adapter using the pinned native SDK and original sandbox rules."""
import json
import os
from pathlib import Path
import uuid

from main_experiment.backend import DockerSession,capture,telemetry,message_ids
from main_experiment.completion import assess
from main_experiment.core import fingerprint
from main_experiment.egress import Egress
from main_experiment.support import command,save

MODELS=[{'id':f'gpt_oss_{size}b','model':f'deepinfra/openai/gpt-oss-{size}b',
         'key_env':'DEEPINFRA_API_KEY'} for size in (20,120)]
COMPLETION={'provider':'deepinfra','normal_reasons':['stop'],
            'structural_checks':'Original exported-current-turn checks, plus exact provider and model identity.'}

def settings(model):
    if model not in MODELS:
        raise ValueError('Only the declared DeepInfra models are supported')
    upstream=model['model'].split('/',1)[1]
    # The native @ai-sdk/deepinfra SDK appends /openai/chat/completions.
    return {'agent':{'build':{'temperature':1.0},'title':{'disable':True}},
        'provider':{'deepinfra':{'options':{'baseURL':'https://api.deepinfra.com/v1',
            'apiKey':'{env:DEEPINFRA_API_KEY}'},'models':{upstream:{
            'reasoning':True,'tool_call':True,'temperature':True,
            'limit':{'context':131072,'output':16384},
            'options':{'reasoningEffort':'medium'},
            'cost':{'input':0.03 if model==MODELS[0] else 0.037,
                    'output':0.14 if model==MODELS[0] else 0.17}}}}}}

class DeepInfraEgress(Egress):
    def __init__(self,session,capture_fn):
        self.session,self.capture=session,capture_fn
        self.name=session.name+'-gateway'
        self.allowed=['api.deepinfra.com']

class DeepInfraSession(DockerSession):
    def __init__(self,c,model,directory,image):
        if model not in MODELS:
            raise ValueError('Unexpected DeepInfra model')
        self.c,self.model,self.directory,self.image=c,model,Path(directory),image
        self.name='cb-'+uuid.uuid4().hex
        self.workspace=self.directory/'live'
        self.egress=DeepInfraEgress(self,capture)

    def start(self):
        super().start()
        config=settings(self.model)
        capture(['docker','exec',self.name,'python','-c',
          'from pathlib import Path;import sys;p=Path("/state/config/opencode/opencode.json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(sys.argv[1])',json.dumps(config)])
        save(self.directory/'provider-config.json',config)

    def phase(self,text,path,session=None):
        key=self.model['key_env']
        if not os.environ.get(key):
            raise ValueError('Missing DEEPINFRA_API_KEY')
        argv=['docker','exec','-e',key,self.name,'opencode','run','--format','json','--model',self.model['model']]
        if session:
            argv+=['--session',session]
        argv.append(text)
        before=message_ids(self.export_history(session,path/'history-before.json')) if session else []
        result=command(argv,self.directory,path/'agent.jsonl',self.c['phase_seconds'])
        result.update(telemetry(path/'agent.jsonl'),terminal=False)
        save(path/'agent.json',result)
        if result['exit_code']!=0 or result['timed_out'] or result['provider_errors']:
            raise RuntimeError('DeepInfra process/provider failure; inspect retained private log')
        ids=result['session_ids']
        if len(ids)!=1 or (session and ids!=[session]):
            raise RuntimeError('Session identity mismatch')
        sid=ids[0];history=self.export_history(sid,path/'history.json')
        message_ids(history)
        decision=assess(history,before,sid,'openai',result)
        decision['structural_policy_sha256']=decision.pop('policy_sha256')
        decision.update(provider='deepinfra',policy_sha256=fingerprint(COMPLETION))
        upstream=self.model['model'].split('/',1)[1]
        assistants=[m['info'] for m in history.get('messages',[]) if m.get('info',{}).get('role')=='assistant']
        if not assistants or any(m.get('providerID')!='deepinfra' or m.get('modelID')!=upstream for m in assistants):
            decision.update(normal=False,reason='unexpected_provider_or_model_identity')
        actual=json.loads(capture(['docker','exec',self.name,'cat','/state/config/opencode/opencode.json']))
        # The file contains only an environment-variable placeholder, no key.
        save(path/'provider-config-after.json',actual)
        schema=actual.pop('$schema',None)
        if schema not in (None,'https://opencode.ai/config.json') or actual!=settings(self.model):
            decision.update(normal=False,reason='sampling_configuration_changed')
        result.update(completion=decision,terminal=decision['normal'])
        save(path/'completion.json',decision);save(path/'agent.json',result)
        if not decision['normal']:
            raise RuntimeError('DeepInfra completion not established: '+decision['reason'])
        return sid,history
