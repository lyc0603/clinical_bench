"""Multi-provider copy of the same full DAG loop; shared repaired architecture is hash-bound."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import pandas as pd
import pyreadstat
from .client import request as provider_request,PROFILES,MAX_TOKENS
from .archive import archive_evidence
from gxp_full.run import own_code as architecture_code
from gxp_adsl import run as shared
from gxp_adsl.checks import eligible
from main_experiment.backend import capture
from main_experiment.core import code_manifest,fingerprint,private_path
from main_experiment.support import save,manifest,digest,load_env
from main_experiment.rebuild import RebuildRuntime
from main_experiment.evaluate import Evaluator
from gxp_full.plan import make_plan,definitions,SYSTEM,EXPORT_SYSTEM,NODE_WRAPPER,EXPORT_WRAPPER
from gxp_full.checks import node_checks,export_checks

WORKERS=2


def own_code():
    return {p.name:digest(p) for p in sorted(Path(__file__).parent.iterdir()) if p.suffix in ('.py','.md')}


def read_source_schema(path):
    encoding=None
    try:
        frame,meta=pyreadstat.read_xport(str(path),disable_datetime_conversion=True)
    except UnicodeDecodeError:
        encoding='cp1252'
        frame,meta=pyreadstat.read_xport(str(path),disable_datetime_conversion=True,encoding=encoding)
    return {'rows':len(frame),'columns':meta.readstat_variable_types,'read_encoding':encoding}


def prepare(root,project,qualification):
    if root.exists():raise ValueError('Preserve prior run; new root required')
    root.mkdir(parents=True);source=project/'experiments/main-study-current/prepared-inputs'
    (root/'inputs/Input').mkdir(parents=True)
    for name in ('specifications.json','SAP.pdf'):shutil.copy2(source/name,root/'inputs'/name)
    schemas={}
    for path in sorted((source/'Input').glob('*.xpt')):
        shutil.copy2(path,root/'inputs/Input'/path.name)
        schemas[path.stem.upper()]=read_source_schema(path)
    if len(schemas)!=22:raise ValueError('Expected all 22 source domains')
    save(root/'source-schemas.json',schemas)
    base=json.loads((project/'experiments/config.gemini-temperature-qualified.local.json').read_text());save(root/'base-config.private.json',base)
    shutil.copy2(qualification,root/'qualification.json')
    plan=make_plan(json.loads((root/'inputs/specifications.json').read_text()));save(root/'dag.json',plan)
    save(root/'source-provenance.json',{'selected_input_files':manifest(root/'inputs'),'scope':'Entire frozen source package, no reference ADaM or prior generated outputs'})
    return plan


def payload(root):
    profile=json.loads((root/'provider-profile.json').read_text())
    base=json.loads((root/'base-config.private.json').read_text());image=capture(['docker','image','inspect','--format','{{.Id}}',base['image']])
    spec=json.loads((root/'inputs/specifications.json').read_text());plan=make_plan(spec);q=json.loads((root/'qualification.json').read_text())
    if not q.get('passed') or q.get('clinical_inputs_used') is not False or q.get('image')!=image or q.get('node_wrapper_sha256')!=hashlib.sha256(NODE_WRAPPER.encode()).hexdigest() or q.get('export_wrapper_sha256')!=hashlib.sha256(EXPORT_WRAPPER.encode()).hexdigest() or q.get('export_system_sha256')!=hashlib.sha256(EXPORT_SYSTEM.encode()).hexdigest():raise ValueError('Matching nonclinical qualification required')
    if json.loads((root/'dag.json').read_text())!=plan:raise ValueError('DAG file differs from current plan')
    return {'architecture':'Independent GxP-Agent-inspired full-benchmark extension; not original author 13-dataset implementation',
        'model':profile['model'],'provider':profile['provider'],'provider_profile':profile,'max_tokens':MAX_TOKENS,'sampling':'provider defaults; no temperature/reasoning override',
        'plan':plan,'expected_datasets':[x['dataset'] for x in plan],'expected_variables':531,'expected_subjects':len(eligible(root/'inputs')),
        'workers':WORKERS,'max_attempts_per_node':2,'max_attempts_export':2,'provider_automatic_retry':False,
        'node_system':SYSTEM,'export_system':EXPORT_SYSTEM,'node_wrapper':NODE_WRAPPER,'export_wrapper':EXPORT_WRAPPER,
        'code':own_code(),'shared_gxp_helpers':shared.tools(),'shared_architecture':architecture_code(),'reused_main_code':code_manifest(),
        'image':image,'python_version':capture(['docker','run','--rm','--network','none',image,'python','--version']),
        'inputs':manifest(root/'inputs'),'source_schemas_sha256':digest(root/'source-schemas.json'),'source_provenance_sha256':digest(root/'source-provenance.json'),
        'qualification_sha256':digest(root/'qualification.json'),'config_sha256':digest(root/'base-config.private.json'),
        'p21_cache':manifest(Path(base['p21']['cache'])),'p21_support_inputs':{d:digest(Path(base['inputs'])/'Input'/(d.lower()+'.xpt')) for d in base['p21']['support_domains']},
        'storage':'Unique non-cloud /private/tmp execution retained; gzip archive independently stream-hash-verified; no evidence deletion by runner',
        'gate_policy':'Exact ownership; fixed complete row universe at ingest; immutable controller row identity/order after ingest; assigned type/length, subject eligibility, selected consistency checks; nonempty dataset required. No comprehensive derivation oracle.',
        'failure_policy':'Exhausted dataset node blocks descendants; unrelated branches continue. Provider/controller errors stop new requests, preserve in-flight work. Export accepted dataset subset if any, evaluate against full expected set; partial P21 counts descriptive only.',
        'clinical_rule_changes':False,'manual_clinical_code_repair':False,'P21_feedback':False,'main_study_started':False}


def replay_entry(plan,accepted):
    # Generic orchestration only, no source selection or variable derivations.
    selected=[d for d in plan if d['dataset'] in accepted]
    return '''from pathlib import Path
import json,subprocess
import pandas as pd
plan='''+repr(selected)+'''
Path('artifacts').mkdir(exist_ok=True)
latest={}
for dataset in plan:
    name=dataset['dataset'];up={k:latest[k] for k in dataset['dependencies']}
    upath='artifacts/'+name+'-upstream.json';Path(upath).write_text(json.dumps(up))
    previous='-'
    for i,node in enumerate(dataset['nodes']):
        result='artifacts/'+name+'-'+str(i)+'.json'
        program='output/adam/programs/nodes/'+name+'__'+node['name']+'.py'
        subprocess.run(['python','-B','output/adam/programs/run_node.py',program,previous,result,upath],check=True)
        previous=result
    frame=pd.read_json(previous,orient='table');frame=frame[[c for c in frame if not c.startswith('__')]]
    path='artifacts/'+name+'-final.json';frame.to_json(path,orient='table',index=False,double_precision=15);latest[name]=path
Path('artifacts/datasets.json').write_text(json.dumps(latest))
subprocess.run(['python','-B','output/adam/programs/run_export.py'],check=True)
'''


def run(root):
    lock=json.loads((root/'freeze.json').read_text());frozen=payload(root)
    if lock!={'payload':frozen,'sha256':fingerprint(frozen)}:raise ValueError('Freeze drift')
    if shutil.disk_usage(root).free<10*1024**3:raise ValueError('Need 10 GiB free')
    if (root/'run-evidence.tar.gz').exists():raise ValueError('Preserve prior archive')
    out=Path('/private/tmp')/(root.name+'-execution');out.mkdir(exist_ok=False);save(root/'run-location.json',{'execution':str(out),'archive':str(root/'run-evidence.tar.gz')});save(out/'plan.json',lock)
    base=json.loads((root/'base-config.private.json').read_text());runtime=RebuildRuntime({**base,'inputs':str(root/'inputs')},frozen['image'])
    spec=json.loads((root/'inputs/specifications.json').read_text());schemas=json.loads((root/'source-schemas.json').read_text());expected=eligible(root/'inputs');plan=frozen['plan']
    def request(prompt,directory,system):
        return provider_request(frozen['provider_profile'],prompt,directory,system,frozen['provider_profile']['response_model'])
    state={'status':'running','started_unix':time.time(),'datasets':{},'nodes':[],'main_study_started':False};mutex=threading.Lock();stop=threading.Event();results={}
    def flush():
        with mutex:save(out/'state.json',state)
    def unchanged():
        return own_code()==frozen['code'] and shared.tools()==frozen['shared_gxp_helpers'] and architecture_code()==frozen['shared_architecture'] and manifest(root/'inputs')==frozen['inputs']
    def dataset_run(ds):
        name=ds['dataset'];defs={v['Variable']:v for v in definitions(spec,name)};required={'STUDYID','USUBJID'};previous=None;previous_path='-'
        state['datasets'][name]={'status':'running','dependencies':ds['dependencies']};flush()
        seed=out/'datasets'/name/'seed';(seed/'output/adam/programs/nodes').mkdir(parents=True);(seed/'artifacts/upstream').mkdir(parents=True)
        (seed/'output/adam/programs/run_node.py').write_text(NODE_WRAPPER);up={}
        for dependency in ds['dependencies']:
            frame=results[dependency]['frame'];path='artifacts/upstream/'+dependency+'.json';frame[[v['Variable'] for v in definitions(spec,dependency)]].to_json(seed/path,orient='table',index=False,double_precision=15);up[dependency]=path
        save(seed/'artifacts/upstream.json',up);accepted=seed
        for index,node in enumerate(ds['nodes']):
            if stop.is_set():state['datasets'][name]['status']='blocked_provider_failure';flush();return None
            required.update(node['owns']);record={'dataset':name,'node':node['name'],'status':'running','attempts':[]};state['nodes'].append(record);flush()
            prompt=json.dumps({'dataset':ds['metadata'],'process_node':node,'cumulative_required_variables':sorted(required),
                'all_dataset_specifications':definitions(spec,name),'node_variable_specifications':[defs[x] for x in node['owns']],
                'rules':spec['sheets']['Rules'],'implementation_details':spec['sheets']['Implementation details'],
                'windows':spec['sheets']['Windows'],'parameter_map':spec['sheets']['Parameter map'],'value_level':spec['sheets']['Value level'],'codelists':spec['sheets']['Codelists'],'site_map':spec['sheets']['Site map'] if name=='ADSL' else None,
                'source_schemas':schemas,'source_files':{d:'/inputs/Input/'+d.lower()+'.xpt' for d in schemas},
                'declared_upstream_schemas':{k:{c:str(t) for c,t in results[k]['frame'].dtypes.items() if not c.startswith('__')} for k in ds['dependencies']},
                'previous_schema':{k:str(v) for k,v in previous.dtypes.items()} if previous is not None else None,'previous_rows':len(previous) if previous is not None else None,
                'no_reference_outputs':True,'controller_row_contract':'Complete row universe at ingest; __ROWID assigned by controller. Later nodes may not add/drop/reorder or change protected values.'},ensure_ascii=False)
            feedback='';succeeded=False
            for attempt in (1,2):
                if not unchanged():stop.set();raise ValueError('Frozen code/input drift')
                if stop.is_set():state['datasets'][name]['status']='blocked_provider_failure';flush();return None
                d=out/'datasets'/name/'nodes'/node['name']/f'attempt-{attempt}'
                try:text=request(prompt+feedback,d,SYSTEM)
                except Exception as exc:
                    record.update(status='provider_failure',error_type=type(exc).__name__);state['datasets'][name]['status']='provider_failure';stop.set();flush();raise
                w=d/'workspace';shutil.copytree(accepted,w);program='output/adam/programs/nodes/'+name+'__'+node['name']+'.py';artifact='artifacts/'+str(index)+'-result.json';(w/program).write_text(text);errors=[];execution=None;frame=None
                try:
                    code=shared.extract_code(text);ast.parse(code);(w/program).write_text(code);before=manifest(w)
                    execution=runtime.rebuild(w,['python','-B','output/adam/programs/run_node.py',program,previous_path,artifact,'artifacts/upstream.json'],d/'execution.log',base['rebuild_timeout_seconds'])
                    if execution['exit_code'] or execution['timed_out']:raise ValueError('Execution failed: '+(d/'execution.log').read_text(errors='replace')[-4000:])
                    after=manifest(w)
                    if any(after.get(k)!=v for k,v in before.items()):raise ValueError('Protected programs/artifacts changed')
                    if set(after)-set(before)!={artifact}:raise ValueError('Node wrote undeclared files')
                    frame=pd.read_json(w/artifact,orient='table');errors=node_checks(frame,previous,required,defs,expected,node['owns'],name)
                except Exception as exc:errors.append(str(exc))
                save(d/'checks.private.json',{'passed':not errors,'errors':errors,'execution':execution,'required_variables':sorted(required)})
                record['attempts'].append({'attempt':attempt,'passed':not errors,'program_sha256':digest(w/program),'usage_sha256':digest(d/'usage.json'),'checks_sha256':digest(d/'checks.private.json')});flush()
                if not errors:
                    save(d/'workspace-manifest.json',manifest(w));accepted=w;previous=frame;previous_path=artifact;succeeded=True;record.update(status='passed',accepted_attempt=attempt);flush();print(name+'.'+node['name']+': passed attempt '+str(attempt),flush=True);break
                feedback='\nPrevious reply:\n'+text+'\nConcrete errors:\n'+json.dumps(errors)+'\nReturn one corrected complete Python module for the same process node, preserving all protected values.'
            if not succeeded:
                record['status']='failed';state['datasets'][name]['status']='failed';state['datasets'][name]['failed_node']=node['name'];flush();print(name+': FAILED '+node['name'],flush=True);return None
        state['datasets'][name]['status']='passed';flush();return {'workspace':accepted,'frame':previous}
    flush()
    try:
        remaining={ds['dataset']:ds for ds in plan}
        while remaining and not stop.is_set():
            blocked=[name for name,ds in remaining.items() if any(state['datasets'].get(dep,{}).get('status') in ('failed','blocked','provider_failure','blocked_provider_failure') for dep in ds['dependencies'])]
            for name in blocked:
                state['datasets'][name]={'status':'blocked','dependencies':remaining[name]['dependencies']};del remaining[name]
            ready=[ds for ds in remaining.values() if all(dep in results for dep in ds['dependencies'])]
            if not ready:break
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futures={pool.submit(dataset_run,ds):ds['dataset'] for ds in ready}
                for future in as_completed(futures):
                    name=futures[future]
                    try:
                        result=future.result()
                        if result is not None:results[name]=result
                    except Exception as exc:
                        stop.set();state['datasets'].setdefault(name,{}) .update(status='provider_failure',error_type=type(exc).__name__)
                    del remaining[name];flush()
        for name,ds in remaining.items():state['datasets'][name]={'status':'blocked','dependencies':ds['dependencies']}
        flush()
        if stop.is_set():raise RuntimeError('Provider/controller failure; no new requests scheduled')
        if not results:raise RuntimeError('No dataset accepted; export blocked')
        seed=out/'export-seed';(seed/'output/adam/programs/nodes').mkdir(parents=True);(seed/'artifacts').mkdir()
        (seed/'output/adam/programs/run_node.py').write_text(NODE_WRAPPER);(seed/'output/adam/programs/run_export.py').write_text(EXPORT_WRAPPER)
        frames={};paths={}
        for ds in plan:
            name=ds['dataset']
            if name not in results:continue
            result=results[name];frames[name]=result['frame'][[v['Variable'] for v in definitions(spec,name)]].copy();path='artifacts/'+name+'-final.json';frames[name].to_json(seed/path,orient='table',index=False,double_precision=15);paths[name]=path
            for node in ds['nodes']:
                filename=name+'__'+node['name']+'.py';shutil.copy2(result['workspace']/'output/adam/programs/nodes'/filename,seed/'output/adam/programs/nodes'/filename)
        save(seed/'artifacts/datasets.json',paths)
        prompt=json.dumps({'task':'export','accepted_datasets':list(frames),'expected_dataset_files':[k.lower()+'.xpt' for k in frames],
            'metadata_source':'/inputs/specifications.json','sheet_headers':{k:spec['sheets'][k][0] for k in ['Datasets','Codelists','Value level']},
            'frame_schemas':{k:{c:str(v) for c,v in f.dtypes.items()} for k,f in frames.items()},'rules':'No clinical derivation or value changes. Read metadata via sheet header mapping and loop. Return only Python source, no tools.'},ensure_ascii=False)
        feedback='';accepted=None;export_record={'status':'running','attempts':[]};state['export']=export_record;flush()
        for attempt in (1,2):
            if not unchanged():raise ValueError('Frozen code/input drift')
            d=out/'export'/f'attempt-{attempt}';text=request(prompt+feedback,d,EXPORT_SYSTEM);w=d/'workspace';shutil.copytree(seed,w);program=w/'output/adam/programs/export.py';program.write_text(text);errors=[];execution=None
            try:
                code=shared.extract_code(text);ast.parse(code);program.write_text(code);before=manifest(w)
                execution=runtime.rebuild(w,['python','-B','output/adam/programs/run_export.py'],d/'execution.log',base['rebuild_timeout_seconds'])
                if execution['exit_code'] or execution['timed_out']:raise ValueError('Export execution failed: '+(d/'execution.log').read_text(errors='replace')[-4000:])
                after=manifest(w)
                if any(after.get(k)!=v for k,v in before.items()):raise ValueError('Export modified protected programs/artifacts')
                coverage,errors=export_checks(w,spec,frames)
            except Exception as exc:errors.append(str(exc));coverage={}
            save(d/'checks.private.json',{'passed':not errors,'errors':errors,'coverage':coverage,'execution':execution})
            export_record['attempts'].append({'attempt':attempt,'passed':not errors,'program_sha256':digest(w/'output/adam/programs/export.py'),'usage_sha256':digest(d/'usage.json'),'checks_sha256':digest(d/'checks.private.json')});flush()
            if not errors:save(d/'workspace-manifest.json',manifest(w));accepted=w;export_record.update(status='passed',accepted_attempt=attempt);flush();break
            feedback='\nPrevious reply:\n'+text+'\nConcrete export errors:\n'+json.dumps(errors)+'\nReturn corrected compact Python source; no tools or clinical value changes.'
        if accepted is None:export_record['status']='failed';raise RuntimeError('Combined export exhausted two attempts')
        package=out/'final-workspace';shutil.copytree(accepted,package);(package/'output/adam/programs/rebuild.py').write_text(replay_entry(plan,set(results)));before=manifest(package);save(out/'final-workspace-manifest.json',before)
        final_eval=out/'final-evaluation';final_eval.mkdir();print('Final evaluation: P21, auxiliary checks and independent rebuild',flush=True)
        evaluation=Evaluator(base,frozen['image'])(package,final_eval)
        if manifest(package)!=before:raise RuntimeError('Final evaluator modified package')
        save(out/'evaluation.private.json',evaluation);state['status']='completed' if len(results)==13 else 'completed_partial'
    except BaseException as exc:state.update(status='failed',error_type=type(exc).__name__,reason=str(exc));raise
    finally:
        state['finished_unix']=time.time();flush();archive_evidence(out,root)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare-freeze','run']);p.add_argument('--root',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--qualification',type=Path);p.add_argument('--readiness',type=Path);p.add_argument('--provider',choices=tuple(PROFILES));p.add_argument('--execute',action='store_true')
    a=p.parse_args();load_env(a.env_file);root=private_path(a.root)
    if a.action=='prepare-freeze':
        if not a.qualification or not a.provider or not a.readiness:p.error('--qualification, --provider and --readiness required')
        receipt=json.loads(a.readiness.read_text())
        if not receipt.get('qualified') or receipt.get('profile')!=PROFILES[a.provider]:raise ValueError('Exact provider nonclinical readiness required')
        project=Path(__file__).resolve().parents[3];plan=prepare(root,project,a.qualification)
        save(root/'provider-profile.json',{**PROFILES[a.provider],'response_model':receipt['response_model'],'readiness_sha256':digest(a.readiness)})
        shutil.copy2(a.readiness,root/'provider-readiness.json')
        frozen=payload(root);save(root/'freeze.json',{'payload':frozen,'sha256':fingerprint(frozen)});print('Frozen full DAG:',len(plan),'datasets,',sum(len(x['nodes']) for x in plan),'process nodes, 531 variables')
    else:
        if not a.execute:p.error('--execute required')
        run(root)

if __name__=='__main__':main()
