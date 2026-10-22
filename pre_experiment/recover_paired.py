"""Adjudicated continuation after host-validator failure; never retry an agent."""
import argparse
import copy
import json
import os
from pathlib import Path

from main_experiment.core import code_manifest, config, fingerprint, private_path
from main_experiment.backend import message_ids
from main_experiment.runner import seal
from main_experiment.support import digest, load_env, manifest, save
from pre_experiment.paired_pilot import paired_workflow, qualification_valid, tool_manifest
from pre_experiment.qualify_p21 import passing


def completed_evidence(directory, model, old_payload):
    state=json.loads((directory/'state.json').read_text())
    if state['status'] not in ('completed','failed'):
        raise ValueError('Uncertain prior invocation; do not continue')
    if state['status']=='failed' and state.get('reason')!='P21 report unavailable or invalid; endpoint retained, scheduling stopped for adjudication':
        raise ValueError('Prior failure is not an adjudicated evaluator-only failure')
    hashes={};initial=None
    for phase in ('initial','final'):
        p=directory/phase
        agent=json.loads((p/'agent.json').read_text())
        if not agent['completion']['normal']:
            raise ValueError('Agent did not complete; no retry authorized by this continuation')
        history=json.loads((p/'history.json').read_text())
        if history!=json.loads((p/'history.raw.json').read_text()):
            raise ValueError('History differs from raw export')
        if not all(m['info']['providerID']+'/'+m['info']['modelID']==model['model'] for m in history['messages'] if m['info']['role']=='assistant'):
            raise ValueError('Prior requested model identity mismatch')
        ids=message_ids(history)
        if initial is not None:
            if ids[:len(initial)]!=initial or len(ids)<=len(initial):raise ValueError('Session continuity mismatch')
        else:initial=ids
        expected=old_payload['seal']['prompts']['generate' if phase=='initial' else 'self_review']
        if (p/'prompt.txt').read_text()!=expected:raise ValueError('Prior prompt mismatch')
        if manifest(p/'workspace')!=json.loads((p/'workspace-manifest.json').read_text()):
            raise ValueError('Prior workspace changed')
        for name in ('agent.json','history.json','history.raw.json','workspace-manifest.json','evaluation.json','prompt.txt'):
            hashes[phase+'/'+name]=digest(p/name)
    receipt=json.loads((directory/'initial-only.json').read_text())
    if receipt['evaluation_sha256']!=hashes['initial/evaluation.json']:
        raise ValueError('Initial endpoint receipt mismatch')
    hashes['initial-only.json']=digest(directory/'initial-only.json')
    hashes['state.json']=digest(directory/'state.json')
    return {'original_status':state['status'],'source_sha256':hashes,
            'final_checkpoint_note':'A final checkpoint manifest may be absent because the evaluator gate raised; pre-evaluation workspace manifests and normal exported histories are verified instead.'}


def reassessment_evidence(mapping, c, sources):
    result={}
    for alias,directory in sources.items():
        result[alias]={}
        for phase in ('initial','final'):
            p=Path(mapping[alias][phase])
            summary=json.loads((p/'summary.json').read_text())
            if (not passing(summary) or summary.get('config_sha256')!=fingerprint(c)
                    or summary.get('evaluator_code')!=code_manifest()
                    or summary.get('source_dataset_manifest')!=manifest(Path(directory)/phase/'workspace/output/adam/datasets')):
                raise ValueError('Prior completed endpoint lacks passing current reassessment')
            result[alias][phase]={'directory':str(p.resolve()),'summary_sha256':digest(p/'summary.json'),
               'parsed_sha256':digest(p/'1/unqualified-report-parse.json')}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('freeze','run'))
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--lock',type=Path,required=True)
    p.add_argument('--qualification',type=Path)
    p.add_argument('--source-root',type=Path)
    p.add_argument('--source-lock',type=Path)
    p.add_argument('--reassessment-map',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--env-file',type=Path)
    p.add_argument('--execute',action='store_true')
    a=p.parse_args();c=config(a.config);current=seal(c);lock_path=private_path(a.lock)
    if a.action=='freeze':
        if not all((a.qualification,a.source_root,a.source_lock,a.reassessment_map)):
            p.error('freeze requires qualification, source-root, source-lock and reassessment-map')
        if lock_path.exists():raise ValueError('Do not overwrite a recovery lock')
        old=json.loads(a.source_lock.read_text());prior=old['payload']
        if old['sha256']!=fingerprint(prior) or prior['scope']!='excluded_paired_pilot_v1':raise ValueError('Invalid original paired lock')
        if prior['seal']['code']!=code_manifest():raise ValueError('Generation/evaluator code changed; independent review required')
        if prior['tools']['paired_pilot.py']!=digest(Path(__file__).with_name('paired_pilot.py')):raise ValueError('Original runner changed')
        comparison=copy.deepcopy(c)
        for key in ('cache','meddra_directory'):comparison['p21'][key]=prior['seal']['config']['p21'][key]
        if comparison!=prior['seal']['config']:raise ValueError('Only declared cache location/state initialization may change')
        before=manifest(Path(prior['seal']['config']['p21']['cache']));before.pop('lib/engines/app.data',None)
        after=manifest(Path(c['p21']['cache']))
        if before!=after or 'lib/engines/app.data' in after:raise ValueError('Clean runtime must differ only by omitted mutable app.data')
        qualification=json.loads(a.qualification.read_text());qualification_valid(qualification,current)
        sources={};proof={};remaining=[]
        for model in c['models']:
            d=a.source_root/model['id']
            if d.exists():
                proof[model['id']]=completed_evidence(d,model,prior);sources[model['id']]=str(d.resolve())
            else:remaining.append(dict(workflow='paired-'+model['id'],model=model['id'],condition='self_review',repetition=0))
        if not sources or not remaining:raise ValueError('Continuation requires completed source phases and unstarted providers')
        mapping=json.loads(a.reassessment_map.read_text())
        reassessments=reassessment_evidence(mapping,c,sources)
        payload={'scope':'excluded_paired_recovery_v1','seal':current,'tools':tool_manifest(),
            'cache_source_manifest':after,'documentation_sha256':digest(Path(__file__).with_name('RECOVERY.md')),'source_lock':str(a.source_lock.resolve()),'source_lock_sha256':digest(a.source_lock),
            'prior_payload':prior,'sources':sources,'source_proof':proof,'workflows':remaining,
            'reassessments':reassessments,'qualification':qualification,'qualification_sha256':digest(a.qualification),
            'policy':'No new invocation for completed model phases; original validation failure retained; uniformly reassess conformance; run only previously unstarted providers.'}
        save(lock_path,{'payload':payload,'sha256':fingerprint(payload)})
        print('Recovery frozen; completed agents will not be rerun.')
        return
    if not a.execute or not a.out or not a.env_file:p.error('run requires execute, out and env-file')
    lock=json.loads(lock_path.read_text());payload=lock['payload']
    def verify():
        if payload['scope']!='excluded_paired_recovery_v1' or lock['sha256']!=fingerprint(payload):raise ValueError('Invalid recovery lock')
        if payload['seal']!=seal(c) or payload['tools']!=tool_manifest():raise ValueError('Recovery freeze mismatch')
        if payload['documentation_sha256']!=digest(Path(__file__).with_name('RECOVERY.md')):raise ValueError('Recovery protocol changed')
        if manifest(Path(c['p21']['cache']))!=payload['cache_source_manifest']:raise ValueError('Clean runtime source changed')
        for model in c['models']:
            alias=model['id']
            if alias in payload['sources'] and completed_evidence(Path(payload['sources'][alias]),model,payload['prior_payload'])!=payload['source_proof'][alias]:raise ValueError('Prior evidence changed')
        mapping={alias:{phase:r['directory'] for phase,r in phases.items()} for alias,phases in payload['reassessments'].items()}
        if reassessment_evidence(mapping,c,payload['sources'])!=payload['reassessments']:raise ValueError('Reassessment evidence changed')
        qualification_valid(payload['qualification'],payload['seal'])
    verify();out=private_path(a.out)
    if out.exists():raise ValueError('Recovery output exists; never silently retry')
    load_env(a.env_file)
    if any(not os.environ.get(m['key_env']) for m in c['models']):raise ValueError('Missing provider credential')
    out.mkdir(parents=True);save(out/'pilot-plan.json',lock)
    directories={**payload['sources'],**{i['model']:str(out/i['model']) for i in payload['workflows']}}
    save(out/'result-sources.json',{'model_directories':directories,'reassessments':payload['reassessments'],
         'original_source_status':payload['source_proof'],'recovery_lock_sha256':lock['sha256']})
    guard=out/'.running';guard.write_text(str(os.getpid()))
    try:
        for item in payload['workflows']:
            verify();paired_workflow(c,item,out/item['model'],payload['seal']['runtime']['image']);verify()
    except BaseException as exc:
        save(out/'interruption.json',{'reason':str(exc),'type':type(exc).__name__,'policy':'Stop and adjudicate; retain all evidence and guard.'});raise
    else:
        guard.unlink();save(out/'completed.json',{'status':'completed_remaining_providers','reused_completed_models':list(payload['sources']),'original_failures_retained':True,'main_study':False})


if __name__=='__main__':main()
