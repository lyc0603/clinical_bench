"""Excluded DeepSeek pilot: one paired session and one P21-feedback session."""
import argparse
import copy
import json
import os
from pathlib import Path
import time

from main_experiment.core import config, fingerprint, private_path
from main_experiment.runner import seal, workflow
from main_experiment.support import digest, load_env, manifest, save
from pre_experiment.paired_pilot import paired_workflow, qualification_valid
from .deepseek_backend import MODEL, PROVIDER, COMPLETION, DeepSeekSession

HERE=Path(__file__).resolve().parent


def tools():
    return {p.name:digest(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.md')}


def current(base_path,qualification_path):
    base=config(base_path);s=seal(base)
    q=json.loads(qualification_path.read_text());qualification_valid(q,s)
    for entry in q['checks']:
        f=qualification_path.parent/entry['model']/entry['condition']/entry['phase']/'summary.json'
        if digest(f)!=entry['summary_sha256']:raise ValueError('Qualification evidence changed')
    cache=manifest(Path(base['p21']['cache']))
    if 'lib/engines/app.data' in cache:raise ValueError('Use the qualified clean-state cache source')
    return base,{'base_seal':s,'qualification_sha256':digest(qualification_path),
      'cache_source':cache,'extension_tools':tools(),'model':MODEL,
      'provider_configuration':PROVIDER,'completion_policy':COMPLETION,
      'scope':'excluded_deepseek_pilot_v1','order':['paired','p21_feedback'],
      'policy':'Serial; no agent time cap; no automatic retries; initial-only shares self-review generation; no main-study launch.'}


def smoke(base,out):
    out.mkdir(parents=True,exist_ok=False)
    empty=out/'empty-inputs';empty.mkdir()
    c=copy.deepcopy(base);c['inputs']=str(empty.resolve());c['models']=[MODEL]
    d=out/'transport';d.mkdir();a=DeepSeekSession(c,MODEL,d,seal(base)['runtime']['image'])
    result={'qualified':False,'model':MODEL,'tools':tools(),'provider_configuration':PROVIDER}
    try:
        a.start();sid=None;phases={}
        texts=['Use the bash tool once to run python -c "print(12345)". Do not inspect files. Then reply READY.',
               'Reply READY2. Do not call any tools or inspect files.']
        for phase,text in zip(('initial','final'),texts):
            p=d/phase;p.mkdir();sid,h=a.phase(text,p,sid)
            phases[phase]=json.loads((p/'agent.json').read_text())
        if not (phases['initial']['tool_calls'] or 0):raise ValueError('Readiness did not demonstrate tool use')
        result.update(qualified=True,completion={k:v['completion'] for k,v in phases.items()},
                      phase_agent_sha256={p:digest(d/p/'agent.json') for p in phases},
                      evidence_manifest=manifest(d))
    finally:
        a.stop();save(out/'qualification.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('smoke','freeze','run'))
    p.add_argument('--base-config',type=Path,required=True)
    p.add_argument('--p21-qualification',type=Path,required=True)
    p.add_argument('--smoke',type=Path)
    p.add_argument('--lock',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--env-file',type=Path)
    p.add_argument('--execute',action='store_true')
    a=p.parse_args();base,payload=current(a.base_config,a.p21_qualification)
    if a.action=='smoke':
        if not a.execute or not a.env_file or not a.out:p.error('smoke needs --execute, --env-file, --out')
        load_env(a.env_file)
        if not os.environ.get(MODEL['key_env']):raise ValueError('Missing DEEPSEEK_API_KEY')
        smoke(base,private_path(a.out));print('DeepSeek nonclinical readiness passed.');return
    if not a.lock:p.error('--lock required')
    lock_path=private_path(a.lock)
    if a.action=='freeze':
        if not a.smoke:p.error('--smoke readiness directory required')
        sm=private_path(a.smoke);receipt=json.loads((sm/'qualification.json').read_text())
        if not receipt['qualified'] or receipt['tools']!=tools() or receipt['provider_configuration']!=PROVIDER:
            raise ValueError('Passing current DeepSeek readiness required')
        actual=manifest(sm/'transport')
        # Gateway log is collected only after the readiness evidence is captured.
        actual.pop('egress-gateway.jsonl',None)
        if actual!=receipt['evidence_manifest']:raise ValueError('Readiness evidence changed')
        if lock_path.exists():raise ValueError('Preserve previous lock')
        payload['readiness']={'directory':str(sm),'receipt_sha256':digest(sm/'qualification.json')}
        save(lock_path,{'payload':payload,'sha256':fingerprint(payload)})
        print('DeepSeek excluded pilot frozen; no clinical agent calls.');return
    if not a.execute or not a.env_file or not a.out:p.error('run needs --execute, --env-file, --out')
    lock=json.loads(lock_path.read_text());frozen=lock['payload']
    def verify():
        _,now=current(a.base_config,a.p21_qualification)
        reference={k:v for k,v in frozen.items() if k!='readiness'}
        if now!=reference or fingerprint(frozen)!=lock['sha256']:raise ValueError('DeepSeek freeze drift')
        if digest(Path(frozen['readiness']['directory'])/'qualification.json')!=frozen['readiness']['receipt_sha256']:
            raise ValueError('Readiness receipt changed')
    verify();load_env(a.env_file)
    if not os.environ.get(MODEL['key_env']):raise ValueError('Missing DEEPSEEK_API_KEY')
    out=private_path(a.out);out.mkdir(parents=True,exist_ok=False)
    save(out/'pilot-plan.json',lock);guard=out/'.running';guard.write_text(str(os.getpid()))
    c=copy.deepcopy(base);c['models']=[MODEL];image=frozen['base_seal']['runtime']['image']
    try:
        for condition in frozen['order']:
            verify()
            item={'workflow':'deepseek-'+condition,'model':'deepseek',
                  'condition':'self_review' if condition=='paired' else 'p21_feedback','repetition':0}
            target=out/condition/'deepseek';target.parent.mkdir(parents=True,exist_ok=True)
            if condition=='paired':paired_workflow(c,item,target,image,backend=DeepSeekSession)
            else:workflow(c,item,target,image,backend=DeepSeekSession)
            verify()
    except BaseException as exc:
        save(out/'interruption.json',{'type':type(exc).__name__,'reason':str(exc),'automatic_retry':False})
        raise
    else:
        guard.unlink();save(out/'completed.json',{'main_study':False,'new_sessions':2,'endpoints':3})


if __name__=='__main__':main()
