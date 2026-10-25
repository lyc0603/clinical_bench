"""Three independent Llama 4 Scout conditions; never launches the main study."""
import argparse
import copy
import json
import os
from pathlib import Path
import random
import shutil
import time

from main_experiment.core import config,fingerprint,private_path,prompts
from main_experiment.runner import seal,workflow
from main_experiment.evaluate import Evaluator
from main_experiment.support import digest,load_env,manifest,save
from pre_experiment.paired_pilot import qualification_valid
from llama_scout_extensions.deepinfra_backend import MODELS,DeepInfraSession,settings
from llama_scout_extensions.deepinfra_readiness import tools as adapter_tools

HERE=Path(__file__).resolve().parent
MODEL=MODELS[0]
CONDITIONS=['initial_only','self_review','p21_feedback']

def tools():
    return {p.name:digest(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.md')}

def current(base_path,qualification,readiness,transport,ripgrep):
    base=config(base_path);s=seal(base)
    q=json.loads(qualification.read_text());qualification_valid(q,s)
    for entry in q['checks']:
        path=qualification.parent/entry['model']/entry['condition']/entry['phase']/'summary.json'
        if digest(path)!=entry['summary_sha256']:
            raise ValueError('P21 qualification evidence changed')
    cache=manifest(Path(base['p21']['cache']))
    if 'lib/engines/app.data' in cache:
        raise ValueError('Use qualified clean-state P21 cache')
    r=json.loads((readiness/'qualification.json').read_text())
    t=json.loads((transport/'qualification.json').read_text())
    if not r.get('qualified') or not t.get('qualified') or r['tools']!=adapter_tools() or t['tools']!=adapter_tools():
        raise ValueError('Current passing model qualification required')
    evidence=manifest(readiness);evidence.pop('qualification.json',None)
    if evidence!=r['evidence'] or r['main_code']!=s['code'] or r['runtime']['image']!=s['runtime']['image']:
        raise ValueError('Model readiness evidence/runtime changed')
    if r['transport_receipt_sha256']!=digest(transport/'qualification.json'):
        raise ValueError('Transport receipt mismatch')
    if r.get('tool_support',{}).get('ripgrep_sha256')!=digest(ripgrep):
        raise ValueError('Qualified ripgrep support required')
    order=CONDITIONS[:];random.Random(20261025).shuffle(order)
    payload={'scope':'excluded_llama_4_scout_three_independent_conditions_v1',
        'base_seal':s,'p21_qualification_sha256':digest(qualification),
        'readiness_sha256':digest(readiness/'qualification.json'),
        'transport_sha256':digest(transport/'qualification.json'),
        'cache_source':cache,'adapter_tools':adapter_tools(),'runner_tools':tools(),
        'tool_support':{'ripgrep_sha256':digest(ripgrep),'source':str(ripgrep.resolve())},
        'model':MODEL,'settings':settings(MODEL),'order':order,'order_seed':20261025,
        'policy':'One fresh independent generation per condition; serial; one repair for self-review and P21 feedback; no agent time cap; no automatic retry; preserve failures. Main-study behavior for partial/unusable P21 feedback is retained. No auxiliary-correctness eligibility gate.',
        'authorization':'User explicitly requested Llama 4 Scout three conditions through the configured DeepInfra API and publication of aggregate results to GitHub.'}
    return base,payload

def initial_only(c,directory,image):
    directory.mkdir(parents=True,exist_ok=False)
    state={'model':MODEL['id'],'condition':'initial_only','repetition':0,'status':'started','started_unix':time.time()}
    save(directory/'state.json',state)
    agent=DeepInfraSession(c,MODEL,directory,image)
    try:
        agent.start();phase=directory/'initial';phase.mkdir()
        text=prompts()['generate'];(phase/'prompt.txt').write_text(text)
        sid,_=agent.phase(text,phase)
        agent.pause()
        before=manifest(agent.workspace)
        shutil.copytree(agent.workspace,phase/'workspace')
        if manifest(phase/'workspace')!=before:
            raise RuntimeError('Checkpoint copy mismatch')
        save(phase/'workspace-manifest.json',before)
        Evaluator(c,image)(phase/'workspace',phase)
        if manifest(phase/'workspace')!=before:
            raise RuntimeError('Evaluator altered checkpoint')
        save(phase/'checkpoint-manifest.json',manifest(phase))
        save(directory/'initial-only.json',{'model':MODEL['id'],'condition':'initial_only','status':'completed',
            'shared_initial':False,'checkpoint':'initial','started_unix':state['started_unix'],'finished_unix':time.time(),
            'agent_sha256':digest(phase/'agent.json'),'evaluation_sha256':digest(phase/'evaluation.json'),
            'workspace_manifest_sha256':fingerprint(before),'repair_metrics':'not_applicable'})
        state.update(status='completed',session_id=sid)
    except BaseException as exc:
        state.update(status='failed',reason=str(exc));raise
    finally:
        try:
            agent.stop()
        finally:
            state['finished_unix']=time.time();save(directory/'state.json',state)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('freeze','run'))
    for name in ('base-config','qualification','readiness','transport','lock','out','env-file','ripgrep'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true')
    a=p.parse_args();load_env(a.env_file)
    base,payload=current(a.base_config,a.qualification,a.readiness,a.transport,a.ripgrep)
    lock_path=private_path(a.lock);lock={'payload':payload,'sha256':fingerprint(payload)}
    if a.action=='freeze':
        if lock_path.exists():
            raise ValueError('Preserve existing freeze')
        save(lock_path,lock)
        print('Frozen excluded Llama 4 Scout pilot; order: '+', '.join(payload['order']));return
    if not a.execute:
        p.error('run requires --execute')
    if json.loads(lock_path.read_text())!=lock:
        raise ValueError('Freeze drift')
    if not os.environ.get('DEEPINFRA_API_KEY'):
        raise ValueError('Missing DEEPINFRA_API_KEY')
    out=private_path(a.out)
    if out.exists():
        raise ValueError('Attempt root exists; never overwrite')
    if shutil.disk_usage(out.parent).free < 10*1024**3:
        raise ValueError('Less than 10 GiB free')
    out.mkdir();save(out/'pilot-plan.json',lock)
    guard=out/'.running';guard.write_text(str(os.getpid()))
    c=copy.deepcopy(base);c['models']=[MODEL]
    c.update(tool_ripgrep=str(a.ripgrep.resolve()),tool_ripgrep_sha256=digest(a.ripgrep))
    image=payload['base_seal']['runtime']['image'];done=[]
    try:
        for condition in payload['order']:
            if (out/'operator-adjudication.json').exists():
                raise RuntimeError('Operator adjudication stops scheduling')
            _,now=current(a.base_config,a.qualification,a.readiness,a.transport,a.ripgrep)
            if now!=payload:
                raise ValueError('Frozen settings/evidence changed')
            if shutil.disk_usage(out).free < 10*1024**3:
                raise ValueError('Less than 10 GiB free before next workflow')
            save(out/'progress.json',{'running':condition,'completed':done,'main_study_started':False})
            directory=out/condition
            if condition=='initial_only':
                initial_only(c,directory,image)
            else:
                item={'workflow':'llama-4-scout-'+condition,'model':MODEL['id'],'condition':condition,'repetition':0}
                workflow(c,item,directory,image,backend=DeepInfraSession)
            done.append(condition)
            save(out/'progress.json',{'running':None,'completed':done,'main_study_started':False})
        _,now=current(a.base_config,a.qualification,a.readiness,a.transport,a.ripgrep)
        if now!=payload:
            raise ValueError('Post-run frozen evidence changed')
    except BaseException as exc:
        save(out/'interruption.json',{'type':type(exc).__name__,'reason':str(exc),'automatic_retry':False,'completed':done});raise
    else:
        guard.unlink();save(out/'completed.json',{'main_study_started':False,'independent_workflows':3,'completed':done})

if __name__=='__main__':
    main()
