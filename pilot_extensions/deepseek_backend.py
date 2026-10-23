"""DeepSeek-only adapter with the unchanged provider-only network firewall."""
import json
import copy
import os
from pathlib import Path
import uuid

from main_experiment.backend import DockerSession, capture, telemetry, message_ids
from main_experiment.completion import assess
from main_experiment.core import fingerprint
from main_experiment.egress import Egress
from main_experiment.support import command, save

MODEL = {'id':'deepseek','model':'deepseek/deepseek-flash','key_env':'DEEPSEEK_API_KEY'}
COMPLETION = {'provider':'deepseek','normal_reasons':['stop'],
    'structural_checks':'Unchanged main assess function with its stop-only profile; actual provider/model IDs additionally checked.'}
PROVIDER = {'provider':{'deepseek':{'npm':'@ai-sdk/openai-compatible','name':'DeepSeek official',
    'options':{'baseURL':'https://api.deepseek.com/v1'},
    'models':{'deepseek-flash':{'name':'DeepSeek V4.1 Flash (1017 as of 2026-10-22)',
      'reasoning':True,'interleaved':{'field':'reasoning_content'},'tool_call':True,'limit':{'context':1000000,'output':384000},
      'cost':{'input':0.30,'output':1.20,'cache_read':0.006}}}}}}


def completion(history, before, sid, execution):
    # Reuse ALL structural checks with the stop-only policy, without changing
    # history or the sealed main provider policy. Unknown finishes still fail.
    result=assess(history,before,sid,'openai',execution)
    result['structural_policy_sha256']=result.pop('policy_sha256')
    result.update(provider='deepseek',policy_sha256=fingerprint(COMPLETION))
    assistants=[m['info'] for m in history.get('messages',[]) if m.get('info',{}).get('role')=='assistant']
    if not assistants or any(m.get('providerID')!='deepseek' or m.get('modelID')!='deepseek-flash' for m in assistants):
        result.update(normal=False,reason='unexpected_deepseek_model_identity')
    return result


class DeepSeekEgress(Egress):
    def __init__(self, session, capture_fn):
        self.session,self.capture=session,capture_fn
        self.name=session.name+'-gateway'
        self.allowed=['api.deepseek.com']


class DeepSeekSession(DockerSession):
    def __init__(self,c,model,directory,image):
        if model!=MODEL:raise ValueError('Only the declared official DeepSeek model is supported')
        self.c,self.model,self.directory,self.image=c,model,Path(directory),image
        self.name='cb-'+uuid.uuid4().hex
        self.workspace=self.directory/'live'
        self.egress=DeepSeekEgress(self,capture)

    def start(self):
        super().start()
        # Explicit model metadata avoids a changing remote catalog. The key is
        # supplied only as an environment variable at phase execution.
        config=copy.deepcopy(PROVIDER)
        config['provider']['deepseek']['options']={**PROVIDER['provider']['deepseek']['options'],
                                                 'apiKey':'{env:DEEPSEEK_API_KEY}'}
        capture(['docker','exec',self.name,'python','-c',
            'from pathlib import Path;import sys;p=Path("/state/config/opencode/opencode.json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(sys.argv[1])',json.dumps(config)])
        save(self.directory/'provider-config.json',PROVIDER)

    def phase(self,text,path,session=None):
        key=self.model['key_env']
        if not os.environ.get(key):raise ValueError('Missing DEEPSEEK_API_KEY')
        argv=['docker','exec','-e',key,self.name,'opencode','run','--format','json','--model',self.model['model']]
        if session:argv+=['--session',session]
        argv.append(text)
        before=[]
        if session:before=message_ids(self.export_history(session,path/'history-before.json'))
        result=command(argv,self.directory,path/'agent.jsonl',self.c['phase_seconds'])
        result.update(telemetry(path/'agent.jsonl'),terminal=False)
        save(path/'agent.json',result)
        if result['exit_code']!=0 or result['timed_out'] or result['provider_errors']:
            raise RuntimeError('Agent process/provider failure; inspect private log')
        ids=result['session_ids']
        if len(ids)!=1 or (session and ids!=[session]):raise RuntimeError('Session identity mismatch')
        sid=ids[0];history=self.export_history(sid,path/'history.json')
        message_ids(history)
        decision=completion(history,before,sid,result)
        result.update(completion=decision,terminal=decision['normal'])
        save(path/'completion.json',decision);save(path/'agent.json',result)
        if not decision['normal']:raise RuntimeError('DeepSeek completion not established: '+decision['reason'])
        return sid,history
