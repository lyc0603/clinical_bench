"""Serial five-endpoint orchestration; resume only models with zero clinical starts."""
import argparse
import json
from pathlib import Path
import shutil
import time
import traceback
from ai431_full.run import prepare,run
from main_experiment.support import save,digest,load_env,manifest
from .report_ai431_full import report

ORDER=['claude','gemini','deepseek','gpt_oss_20b']
PLANNED=['claude','gemini','deepseek','gateway_sol','gpt_oss_20b']

def read(path):return json.loads(Path(path).read_text())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--readiness',type=Path);p.add_argument('--qualification',type=Path);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--resume-unstarted',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:p.error('--execute required')
    load_env(a.env_file);batch=a.batch
    if a.resume_unstarted:
        state=read(batch/'state.json');history=batch/'orchestration-history';history.mkdir(exist_ok=True);save(history/(str(time.time_ns())+'-state.json'),state)
        candidates=[model for model in ORDER if state['models'].get(model,{}).get('status')=='prelaunch_failure']
        if not candidates:raise ValueError('No unstarted endpoints available; never silently rerun a clinical attempt')
        for model in candidates:
            root=Path(state['models'][model]['root'])
            if (root/'run-location.json').exists() or (root/'run-evidence.tar.gz').exists():raise ValueError('Cannot resume a model that already started clinically')
        state['resumed_unstarted_only']=True
    else:
        if not all((a.source,a.readiness,a.qualification)):p.error('Source, readiness and qualification required for a new batch')
        batch.mkdir(parents=True,exist_ok=False);shutil.copytree(a.readiness,batch/'readiness');shutil.copy2(a.qualification,batch/'qualification.json')
        readiness=read(batch/'readiness/readiness.json');state={'status':'preparing','started_unix':time.time(),'models':{}}
        plan={'scope':'One new independent full-benchmark AI-431-inspired attempt per qualified endpoint','planned':PLANNED,'execution_order':ORDER,'main_study_started':False,'metrics':19,'launcher_sha256':digest(Path(__file__))};save(batch/'plan.json',plan)
        for model in PLANNED:
            receipt=next(r for r in readiness['checks'] if r['profile']['id']==model)
            if not receipt['qualified']:state[model]={'status':'not_started','reason':'readiness_failure','http_status':receipt.get('http_status')}
        candidates=[]
        for model in ORDER:
            receipt=next(r for r in readiness['checks'] if r['profile']['id']==model)
            if not receipt['qualified']:continue
            root=batch.parent/(batch.name+'-'+model);prepare(root,a.source,batch/'readiness'/model/'receipt.json',batch/'qualification.json')
            state['models'][model]={'root':str(root),'status':'frozen','freeze_sha256':read(root/'freeze.json')['sha256']};candidates.append(model)
        save(batch/'state.json',state)
    state['status']='running';state['launcher_sha256']=digest(Path(__file__));save(batch/'state.json',state)
    for model in candidates:
        root=Path(state['models'][model]['root']);state['models'][model]['status']='running';save(batch/'state.json',state);print('START MODEL',model,flush=True)
        try:run(root)
        except BaseException as exc:
            state['models'][model]['error_type']=type(exc).__name__;save(root/'orchestration-errors'/(str(time.time_ns())+'.private.json'),{'error_type':type(exc).__name__,'traceback':traceback.format_exc()})
        if not (root/'run-location.json').exists():
            state['models'][model]['status']='prelaunch_failure';save(batch/'state.json',state);print('PRELAUNCH BLOCKED',model,flush=True);continue
        execution=Path(read(root/'run-location.json')['execution']);observed=read(execution/'state.json');state['models'][model]['status']=observed['status'];state['models'][model]['passed_tasks']=sum(t['status']=='passed' for t in observed['tasks'])
        report(root,batch/'aggregates'/model)
        receipt=read(root/'archive-receipt.json')
        if not receipt['verified_lossless'] or digest(root/'run-evidence.tar.gz')!=receipt['sha256'] or manifest(execution)!=read(root/'evidence-manifest.private.json'):raise ValueError('Refuse cleanup without exact verified archive')
        save(root/'duplicate-cleanup-receipt.json',{'archive_sha256':receipt['sha256'],'complete_file_manifest_matched':True,'duplicate_removed':str(execution),'original_evidence_preserved':True,'timestamp_unix':time.time()});shutil.rmtree(execution)
        save(batch/'state.json',state);print('END MODEL',model,state['models'][model]['status'],flush=True)
    state['status']='blocked_prelaunch' if any(m['status']=='prelaunch_failure' for m in state['models'].values()) else 'completed';state['finished_unix']=time.time();save(batch/'state.json',state)
    print('BATCH',state['status'],flush=True)

if __name__=='__main__':main()
