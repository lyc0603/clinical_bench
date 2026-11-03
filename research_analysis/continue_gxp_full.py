"""Post-hoc storage-only continuation; no model requests or clinical code edits."""
import argparse
import json
from pathlib import Path
import shutil
import time
import pandas as pd
import pyreadstat
from main_experiment.support import save, digest, manifest, load_env
from main_experiment.core import fingerprint, code_manifest
from main_experiment.backend import capture
from main_experiment.rebuild import RebuildRuntime
from main_experiment.evaluate import Evaluator
from gxp_full.plan import EXPORT_WRAPPER, definitions
from gxp_full.run import own_code, replay_entry
from gxp_full.checks import export_checks, equal_values
from gxp_full.storage import normalize_character_storage


def read(path):
    return json.loads(path.read_text())


def qualify(out, source_spec, exporter, image):
    """All 531 columns, synthetic rows, all character columns missing."""
    q=out/'qualification';(q/'inputs').mkdir(parents=True)
    shutil.copy2(source_spec,q/'inputs/specifications.json')
    spec=read(source_spec);w=q/'workspace';(w/'output/adam/programs').mkdir(parents=True);(w/'artifacts').mkdir()
    frames={};paths={}
    for ds in [r[0] for r in spec['sheets']['Datasets'][1:] if r[0]]:
        defs={v['Variable']:v for v in definitions(spec,ds)}
        f=pd.DataFrame({c:([float('nan')]*2 if v['Type']=='Character' else [1.25,float('nan')]) for c,v in defs.items()})
        frames[ds]=f;path='artifacts/'+ds+'.json';f.to_json(w/path,orient='table',index=False,double_precision=15);paths[ds]=path
    save(w/'artifacts/datasets.json',paths)
    shutil.copy2(exporter,w/'output/adam/programs/export.py');(w/'output/adam/programs/run_export.py').write_text(EXPORT_WRAPPER)
    before=manifest(w);execution=RebuildRuntime({'inputs':str(q/'inputs')},image).rebuild(w,['python','-B','output/adam/programs/run_export.py'],q/'execution.log',180)
    if execution['exit_code'] or execution['timed_out']:raise ValueError('Synthetic export failed')
    if any(manifest(w).get(k)!=v for k,v in before.items()):raise ValueError('Synthetic protected-file drift')
    coverage,errors=export_checks(w,spec,frames)
    receipt={'passed':not errors,'clinical_records_used':False,'model_calls':0,'synthetic_datasets':13,'synthetic_variables':531,'all_character_columns_missing':True,'coverage':coverage,'errors':errors,'execution':execution,'exporter_sha256':digest(exporter),'wrapper_sha256':digest(w/'output/adam/programs/run_export.py')}
    save(q/'receipt.json',receipt)
    if errors:raise ValueError('Synthetic export QC failed: '+str(errors))
    print('Synthetic 13-dataset/531-variable missing-character qualification: PASS',flush=True)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--original-execution',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:p.error('--execute required')
    load_env(a.env_file);root=a.root.resolve();original=a.original_execution.resolve();out=a.out.resolve();out.mkdir(exist_ok=False)
    lock=read(root/'freeze.json');frozen=lock['payload'];old=read(original/'state.json')
    if fingerprint(frozen)!=lock['sha256'] or old['status']!='failed' or old.get('export',{}).get('status')!='failed':raise ValueError('Expected intact original failed run')
    if manifest(root/'inputs')!=frozen['inputs'] or code_manifest()!=frozen['reused_main_code']:raise ValueError('Inputs or original evaluator drift')
    if any(digest(root/'original-code-snapshot'/name)!=h for name,h in frozen['code'].items()):raise ValueError('Original implementation snapshot drift')
    if len(old['nodes'])!=73 or any(n['status']!='passed' for n in old['nodes']):raise ValueError('Not all original process nodes accepted')
    # Every accepted generated process program and record is bound to original
    # controller receipts before any result can be reused.
    evidence=[]
    for n in old['nodes']:
        item=next(i for i in n['attempts'] if i['attempt']==n['accepted_attempt']);d=original/'datasets'/n['dataset']/'nodes'/n['node']/f"attempt-{item['attempt']}"
        program=d/'workspace/output/adam/programs/nodes'/(n['dataset']+'__'+n['node']+'.py')
        if digest(program)!=item['program_sha256'] or digest(d/'checks.private.json')!=item['checks_sha256'] or manifest(d/'workspace')!=read(d/'workspace-manifest.json'):raise ValueError('Accepted process drift')
        evidence.append({'dataset':n['dataset'],'node':n['node'],'program_sha256':digest(program)})
    seed=original/'export/attempt-2/workspace';item=old['export']['attempts'][-1];exporter=seed/'output/adam/programs/export.py'
    if digest(exporter)!=item['program_sha256'] or digest(seed.parent/'checks.private.json')!=item['checks_sha256']:raise ValueError('Original export drift')
    spec=read(root/'inputs/specifications.json');paths=read(seed/'artifacts/datasets.json');frames={};normalizations=[]
    for ds,path in paths.items():
        f=pd.read_json(seed/path,orient='table');defs={v['Variable']:v for v in definitions(spec,ds)};fixed=normalize_character_storage(f,defs)
        plan=next(d for d in frozen['plan'] if d['dataset']==ds);last_node=plan['nodes'][-1]['name']
        accepted=next(n for n in old['nodes'] if n['dataset']==ds and n['node']==last_node)
        final=original/'datasets'/ds/'nodes'/last_node/f"attempt-{accepted['accepted_attempt']}"/'workspace/artifacts'/f"{len(plan['nodes'])-1}-result.json"
        prior=pd.read_json(final,orient='table')[list(defs)]
        # Original export seed already has one additional 15-digit JSON round
        # trip. Reuse the original frozen equality tolerance, never relax it.
        equal_values(f,prior,defs)
        if digest(seed/path)!=digest(original/'export-seed'/path):raise ValueError('Original serialized export seed drift')
        equal_values(f,fixed,defs)
        for c in f:
            if defs[c]['Type']=='Numeric':pd.testing.assert_series_equal(f[c],fixed[c],check_exact=True)
            else:
                mask=f[c].notna();pd.testing.assert_series_equal(f.loc[mask,c],fixed.loc[mask,c],check_dtype=False,check_exact=True)
                if str(f[c].dtype)!=str(fixed[c].dtype):normalizations.append({'dataset':ds,'variable':c,'before':str(f[c].dtype),'after':str(fixed[c].dtype),'nonmissing':int(mask.sum())})
        frames[ds]=f
    if len(frames)!=13:raise ValueError('Missing original frames')
    base=read(root/'base-config.private.json');image=capture(['docker','image','inspect','--format','{{.Id}}',base['image']])
    if image!=frozen['image']:raise ValueError('Image drift')
    qualification=qualify(out,root/'inputs/specifications.json',exporter,image)
    shutil.copytree(root/'inputs',out/'inputs')
    if manifest(out/'inputs')!=frozen['inputs']:raise ValueError('Local input snapshot drift')
    package=out/'final-workspace';shutil.copytree(seed,package)
    # Remove only rejected generated outputs, retaining programs and frames.
    for name in ('datasets','metadata'):
        path=package/'output/adam'/name
        if path.exists():shutil.rmtree(path)
    for name in ('manifest.json','notes.md'):
        path=package/'output/adam'/name
        if path.exists():path.unlink()
    (package/'output/adam/programs/run_export.py').write_text(EXPORT_WRAPPER)
    (package/'output/adam/programs/rebuild.py').write_text(replay_entry(frozen['plan'],set(frames)))
    for r in evidence:
        if digest(package/'output/adam/programs/nodes'/(r['dataset']+'__'+r['node']+'.py'))!=r['program_sha256']:raise ValueError('Reused process code differs')
    changed={'policy':'Post-hoc storage-only continuation, not a new independent replicate; original failed run retained. No model calls, no generated clinical/export program edits. Missing character values normalized to SAS blank in export wrapper only. Same terminal evaluator. P21 never fed back for repairs.',
        'original_freeze_sha256':lock['sha256'],'original_state_sha256':digest(original/'state.json'),'original_export_checks_sha256':item['checks_sha256'],'original_exporter_sha256':digest(exporter),'accepted_processes':evidence,'normalizations':normalizations,'input_manifest':frozen['inputs'],'code':own_code(),'evaluator_code':code_manifest(),'script_sha256':digest(Path(__file__)),'qualification':qualification,'initial_package_manifest':manifest(package),'main_study_started':False,'new_model_calls':0}
    save(out/'continuation-lock.json',{'payload':changed,'sha256':fingerprint(changed)})
    state={'status':'running','started_unix':time.time(),'original_run_status':'failed','posthoc_storage_continuation':True,'model_calls':0};save(out/'state.json',state)
    def unchanged():
        if own_code()!=changed['code'] or code_manifest()!=changed['evaluator_code'] or digest(Path(__file__))!=changed['script_sha256'] or manifest(out/'inputs')!=changed['input_manifest']:raise ValueError('Continuation lock drift')
    try:
        unchanged();runtime=RebuildRuntime({**base,'inputs':str(out/'inputs')},image);before=manifest(package)
        execution=runtime.rebuild(package,['python','-B','output/adam/programs/run_export.py'],out/'export.log',base['rebuild_timeout_seconds'])
        if execution['exit_code'] or execution['timed_out']:raise ValueError('Clinical export execution failed')
        if any(manifest(package).get(k)!=v for k,v in before.items()):raise ValueError('Export modified protected input/programs')
        coverage,errors=export_checks(package,spec,frames);save(out/'export-checks.json',{'passed':not errors,'coverage':coverage,'errors':errors,'execution':execution})
        if errors:raise ValueError('Export QC failed: '+str(errors))
        print('Reused clinical export: 13/13 XPT, 531/531 variables, preserved values PASS',flush=True)
        before=manifest(package);save(out/'final-workspace-manifest.json',before);unchanged();evaluation=out/'final-evaluation';evaluation.mkdir()
        print('Independent unchanged evaluator: P21, auxiliary checks, offline rebuild',flush=True)
        e=Evaluator({**base,'inputs':str(out/'inputs')},image)(package,evaluation)
        if manifest(package)!=before:raise ValueError('Evaluator modified final package')
        unchanged();save(out/'evaluation.private.json',e);state['status']='completed'
    except BaseException as exc:
        state.update(status='failed',error_type=type(exc).__name__,reason=str(exc));raise
    finally:
        state['finished_unix']=time.time();save(out/'state.json',state)
        archive=root/out.name
        if archive.exists():raise ValueError('Never overwrite prior continuation')
        shutil.copytree(out,archive)
    print(json.dumps({'status':state['status'],'seconds':state['finished_unix']-state['started_unix'],'new_model_calls':0,'conformance':{k:(e.get('conformance') or {}).get(k) for k in ('report_usable','validation_coverage_complete','dataset_rule_pairs','finding_instances','failure_code')},'semantic_reproduced':e.get('semantic_reproduced'),'byte_reproduced':e.get('byte_reproduced'),'rebuild':e.get('rebuild'),'rebuild_error':e.get('rebuild_error')},indent=2),flush=True)


if __name__=='__main__':main()
