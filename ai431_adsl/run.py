"""Frozen, variable-level AI-431 architectural adaptation; no original author code."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.request

import pandas as pd
import pyreadstat
from main_experiment.core import fingerprint
from main_experiment.backend import capture
from main_experiment.evaluate import Evaluator, semantic
from main_experiment.rebuild import RebuildRuntime
from main_experiment.support import digest, manifest, save, load_env
from gxp_adsl import run as shared
from gxp_adsl.checks import variables, eligible, check_frame, exported, source_checks
from gxp_adsl.dag import WRAPPER, OUTPUT_FILES

MODEL = 'claude-sonnet-5-5'
MAX_TOKENS = 32768
WORKERS = 3
SYSTEM = '''You implement one independent variable in a fixed AI-431-inspired ADSL pipeline.
Return only concise Python defining run(previous, inputs) -> pandas.DataFrame, with all imports/helpers in this file. inputs is pathlib.Path('/inputs'), NEVER a dict or subscriptable mapping. previous is a pandas.DataFrame containing only the randomized USUBJID keys, not other derived variables. For a variable task return exactly USUBJID and the assigned variable (only USUBJID if it is assigned), one row for every supplied subject. Read source SDTM and recompute any needed intermediate variables locally according to the supplied frozen rules; do not read other tasks, programs, reference ADaM, credentials or evaluator code. Never use other variable workers' outputs. No internet, package installation, model calls or human edits are available. Do not print patient records.
You have no tools or tool-call protocol in this API request. Never emit invoke/bash/XML calls, shell commands, prose or simulated execution. Return Python source only. Use exact lowercase source_files paths. Read XPT with pyreadstat.read_xport(..., disable_datetime_conversion=True). Runtime is Python3.12, pandas2.2.3, numpy2.2.4, pyreadstat1.3.6, lxml/openpyxl/pypdf. Source specs are /inputs/specifications.json, SAP /inputs/SAP.pdf. Use SAS numeric dates (days since 1960-01-01), retain full precision, numeric missing not zero, Character values strings or missing. Respect specified character lengths and codelists. Missing flags can be blank. GEN01 randomized DM ARMCD Pbo/Xan_Lo/Xan_Hi only. No DM fallback for SV Visit3 treatment/randomization date. Resolve duplicate candidates as specified. Frozen rules outrank conventions; no new clinical decisions.
The controller executes offline and checks keys, type/length/missingness before merging; one local repair is allowed. Variables cannot write files. For task_type export only: previous is the complete merged dataframe. Preserve all values; write every required_output_files path exactly, including output/adam/datasets/define.xml beside adsl.xpt; use relative XPT leaf href adsl.xpt. Create metadata, manifest, notes. XPT version5 table_name ADSL; Define2.0.0. Return previous unchanged. Do not read/modify program files or input artifact files. No variable-generation logic belongs in export. Do not claim clinical correctness or zero P21 findings.'''
EXPORT_SYSTEM = """Return only a concise, complete Python module defining run(previous, inputs).
This is a text-only code-generation request: NO TOOLS ARE AVAILABLE. Do not emit or simulate bash, invoke, XML tool calls, shell commands, execution attempts, test transcripts or repeated tool requests. You cannot run commands. Do not write custom XPT binary/IBM floating-point serializers. Use installed pyreadstat.write_xport(..., file_format_version=5, table_name='ADSL', column_labels=..., variable_format=...) and lxml.etree for Define-XML. Keep code compact (prefer loops and generic metadata handling rather than hardcoded blocks for each variable).
previous is the fully merged pandas.DataFrame with 49 derived variables. inputs is pathlib.Path('/inputs'), NOT a dict. Read approved metadata from inputs/'specifications.json' JSON sheets/header-row arrays. Preserve all derived values, subject keys, missingness and numeric precision; no new clinical derivations. Numeric dates are already SAS days. No internet, package installs, credentials, references or other programs. Runtime includes pandas, numpy, pyreadstat1.3.6, lxml, json, pathlib.
Write all required_output_files at their exact paths relative to /workspace. Define-XML 2.0.0 at output/adam/datasets/define.xml beside adsl.xpt; its leaf references adsl.xpt. Write metadata JSON, manifest JSON and notes too. Apply the original frozen labels/types/order/formats without inventing replacements. Avoid run-dependent XML timestamps. Return previous.copy() unchanged. Do not read or modify program or intermediate artifact files. Do not claim P21 success. Return source code only, preferably under 250 lines. No commentary and no tool syntax."""
REVIEW_SYSTEM = '''You review an already human-approved frozen ADSL specification for an AI-431 architecture pilot. Do not modify specifications, propose new clinical conventions, or generate patient data/code. Return JSON with observations (array), potential_blockers (array), and note. Describe ambiguities with exact variable/rule references, distinguishing resolved frozen conventions from unresolved contradictions. This review is a retained advisory audit, not permission to change the approved input or an independent correctness oracle.'''


def code_files():
    return {p.name: digest(p) for p in sorted(Path(__file__).parent.iterdir()) if p.suffix in ('.py','.md')}


def frozen_payload(root):
    base = shared.payload(root)
    qualification=json.loads((root/'nonclinical-export-qualification.json').read_text())
    if qualification.get('passed') is not True or qualification.get('clinical_inputs_used') is not False or qualification.get('export_system_sha256')!=hashlib.sha256(EXPORT_SYSTEM.encode()).hexdigest() or qualification.get('image')!=base['image']:
        raise ValueError('Passing same-prompt, same-image nonclinical export qualification required')
    return {'architecture':'Independent AI-431-inspired variable-generation/execution/QC/merge adaptation',
        'shared_input_runtime_evaluator':base, 'implementation':code_files(),
        'variable_system':SYSTEM,'export_system':EXPORT_SYSTEM,'review_system':REVIEW_SYSTEM,'workers':WORKERS,
        'execution_storage':'Non-cloud /private/tmp execution workspace; archive immutable evidence to root/run at termination; retain temporary copy',
        'model':MODEL,'max_tokens':MAX_TOKENS,'max_attempts':2,
        'variable_plan':[v['Variable'] for v in variables(json.loads((root/'inputs/specifications.json').read_text()))],
        'review_policy':'Advisory review on already approved frozen specs; no spec edits or human repair in measured run',
        'failure_policy':'Retain all completed variable tasks. No merge/export unless all 49 pass. Provider failures cancel pending work; already in-flight requests finish and remain recorded. No automatic transport retry.',
        'controller_contribution':'Only GEN01 subject keys, strict one-to-one keyed merge, replay packaging. No clinical variable values prefilled. Export code generated independently.',
        'nonclinical_variable_runtime_sha256':digest(root/'nonclinical-variable-runtime.json'),
        'nonclinical_export_qualification_sha256':digest(root/'nonclinical-export-qualification.json'),
        'P21_feedback':False,'main_study_started':False}


def request(prompt, directory, system=SYSTEM):
    directory.mkdir(parents=True,exist_ok=True)
    body={'model':MODEL,'max_tokens':MAX_TOKENS,'system':system,'messages':[{'role':'user','content':prompt}]}
    save(directory/'request.private.json',body)
    req=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(body).encode(),
        headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01','content-type':'application/json'})
    started=time.time()
    try:
        with urllib.request.urlopen(req,timeout=300) as response: raw=json.load(response)
    except Exception as exc:
        save(directory/'provider-failure.json',{'type':type(exc).__name__,'status':getattr(exc,'code',None),'seconds':time.time()-started})
        raise
    save(directory/'response.private.json',raw)
    save(directory/'usage.json',{'model':raw.get('model'),'stop_reason':raw.get('stop_reason'),'usage':raw.get('usage'),'seconds':time.time()-started})
    if raw.get('model')!=MODEL or raw.get('stop_reason')!='end_turn':
        raise RuntimeError('Uncertain provider identity/completion; no automatic retry')
    return '\n'.join(x['text'] for x in raw.get('content',[]) if x['type']=='text').strip()


def variable_qc(frame, keys, definition):
    name=definition['Variable']; errors=[]
    if not isinstance(frame,pd.DataFrame) or frame.columns.duplicated().any():return ['Expected dataframe with unique columns']
    if set(frame)!=set(['USUBJID',name]):return ['Return only USUBJID and assigned variable '+name]
    if frame.USUBJID.isna().any() or frame.USUBJID.duplicated().any() or len(frame)!=len(keys) or set(frame.USUBJID)!=set(keys.USUBJID):
        errors.append('Subject keys differ from exact unique GEN01 randomized population')
    s=frame[name]
    if definition['Type']=='Numeric':
        if not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):errors.append(name+': expected numeric type, not boolean')
    else:
        if not s.dropna().map(lambda x:isinstance(x,str)).all():errors.append(name+': expected string or missing')
        elif s.dropna().map(lambda x:len(x.encode('utf-8'))>int(definition['Length'])).any():errors.append(name+': exceeds specified character length')
    if name=='ITTFL' and not s.eq('Y').all():errors.append('ITTFL must be Y for retained randomized subjects')
    return errors


def merge_variables(keys, frames, definitions):
    merged=keys.copy()
    for definition in definitions:
        name=definition['Variable']; frame=frames[name]
        errors=variable_qc(frame,keys,definition)
        if errors:raise ValueError('Cannot merge rejected variable '+name+': '+str(errors))
        if name!='USUBJID':merged=merged.merge(frame,on='USUBJID',how='left',validate='one_to_one',sort=False)
    return merged[[v['Variable'] for v in definitions]]


def context_for(definition, spec, schemas):
    # Dependency context comes only from the frozen spec, never another worker's generated code.
    rows=variables(spec); names={r['Variable'] for r in rows}; needed={definition['Variable']}
    while True:
        more=set(needed)
        for row in rows:
            if row['Variable'] in needed:
                more.update(names & set(re.findall(r'\b[A-Z][A-Z0-9]*\b',str(row['Derivation']))))
        if more==needed:break
        needed=more
    selected=[r for r in rows if r['Variable'] in needed]
    return {'task_type':'variable','assigned_variable':definition,
        'dependency_specifications':selected,'rules':spec['sheets']['Rules'],
        'implementation_details':spec['sheets']['Implementation details'],
        'codelists':spec['sheets']['Codelists'],'windows':spec['sheets']['Windows'],
        'site_map':spec['sheets']['Site map'] if 'SITEGR1' in needed else None,
        'source_schemas':schemas,'source_files':shared.source_files(),
        'contract':'Return exact subject keys plus assigned variable only; recompute dependencies from source locally; write no files.'}


def replay_entry(names):
    # Deterministic orchestration only; GEN01 key selection is the sole controller data selection.
    return '''from pathlib import Path
import subprocess
import pandas as pd
import pyreadstat
names = '''+repr(names)+'''
dm,_=pyreadstat.read_xport('/inputs/Input/dm.xpt',disable_datetime_conversion=True)
keys=dm.loc[dm.ARMCD.isin(['Pbo','Xan_Lo','Xan_Hi']),['USUBJID']].copy()
if keys.USUBJID.duplicated().any():raise ValueError('Duplicate source keys')
Path('artifacts').mkdir(exist_ok=True)
keys.to_json('artifacts/keys.json',orient='table',index=False,double_precision=15)
merged=keys.copy()
for name in names:
    subprocess.run(['python','-B','output/adam/programs/run_task.py','output/adam/programs/variables/'+name+'.py','artifacts/keys.json','artifacts/'+name+'.json'],check=True)
    frame=pd.read_json('artifacts/'+name+'.json',orient='table')
    if set(frame)!=set(['USUBJID',name]) or frame.USUBJID.duplicated().any() or set(frame.USUBJID)!=set(keys.USUBJID) or len(frame)!=len(keys):raise ValueError('Variable replay key/column mismatch')
    if name!='USUBJID':merged=merged.merge(frame,on='USUBJID',how='left',validate='one_to_one',sort=False)
merged[names].to_json('artifacts/merged.json',orient='table',index=False,double_precision=15)
subprocess.run(['python','-B','output/adam/programs/run_task.py','output/adam/programs/export.py','artifacts/merged.json','artifacts/exported.json'],check=True)
'''


def run(root):
    frozen=json.loads((root/'freeze.json').read_text()); payload=frozen_payload(root)
    if frozen!={'payload':payload,'sha256':fingerprint(payload)}:raise ValueError('Freeze drift')
    if not os.environ.get('ANTHROPIC_API_KEY'):raise ValueError('Missing ANTHROPIC_API_KEY')
    if shutil.disk_usage(root).free<10*1024**3:raise ValueError('Need 10 GiB free')
    if (root/'run').exists():raise ValueError('Preserve existing run archive')
    out=Path('/private/tmp')/(root.name+'-execution');out.mkdir(exist_ok=False)
    save(root/'run-location.json',{'execution_directory':str(out),'archive_directory':str(root/'run')})
    save(out/'plan.json',frozen)
    base=json.loads((root/'base-config.private.json').read_text());image=payload['shared_input_runtime_evaluator']['image']
    runtime=RebuildRuntime({**base,'inputs':str(root/'inputs')},image)
    spec=json.loads((root/'inputs/specifications.json').read_text());defs=variables(spec);schemas=json.loads((root/'source-schemas.json').read_text())
    expected=eligible(root/'inputs');keys=expected[['USUBJID']].copy()
    state={'status':'running','started_unix':time.time(),'records':[],'main_study_started':False}; lock=threading.Lock();stop=threading.Event()
    save(out/'state.json',state)
    def update(record):
        with lock:
            existing=next((i for i,r in enumerate(state['records']) if r['task']==record['task']),None)
            if existing is None:state['records'].append(record)
            else:state['records'][existing]=record
            save(out/'state.json',state)
    def task(name,prompt,definition=None,export_seed=None):
        if stop.is_set():return None
        record={'task':name,'status':'running','attempts':[]};update(record)
        try:
            feedback=''
            for attempt in (1,2):
                if code_files()!=payload['implementation'] or shared.tools()!=payload['shared_input_runtime_evaluator']['code'] or manifest(root/'inputs')!=payload['shared_input_runtime_evaluator']['inputs']:
                    stop.set();raise ValueError('Frozen code/input drift')
                d=out/'tasks'/name/f'attempt-{attempt}';text=request(prompt+feedback,d,EXPORT_SYSTEM if export_seed else SYSTEM)
                w=d/'workspace'
                if export_seed:shutil.copytree(export_seed,w)
                else:
                    (w/'artifacts').mkdir(parents=True)
                    keys.to_json(w/'artifacts/keys.json',orient='table',index=False,double_precision=15)
                    (w/'output/adam/programs/variables').mkdir(parents=True)
                    (w/'output/adam/programs/run_task.py').write_text(WRAPPER)
                program='output/adam/programs/export.py' if export_seed else 'output/adam/programs/variables/'+name+'.py'
                previous='artifacts/merged.json' if export_seed else 'artifacts/keys.json'
                artifact='artifacts/result.json';(w/program).write_text(text)
                errors=[];execution=None;frame=None
                try:
                    code=shared.extract_code(text);ast.parse(code);(w/program).write_text(code)
                    protected=manifest(w)
                    execution=runtime.rebuild(w,['python','-B','output/adam/programs/run_task.py',program,previous,artifact],d/'execution.log',base['rebuild_timeout_seconds'])
                    if execution['exit_code']!=0 or execution['timed_out']:raise ValueError('Execution failed: '+(d/'execution.log').read_text(errors='replace')[-4000:])
                    after=manifest(w)
                    if any(after.get(k)!=v for k,v in protected.items()):raise ValueError('Protected program/input artifact changed')
                    frame=pd.read_json(w/artifact,orient='table')
                    if definition:
                        errors=variable_qc(frame,keys,definition)
                        if not errors and set(after)-set(protected)!={artifact}:errors.append('Variable task wrote undeclared files')
                    else:
                        prior=pd.read_json(w/previous,orient='table'); definitions={v['Variable']:v for v in defs}
                        errors=check_frame(frame,expected,list(definitions),definitions,prior)
                        xpt,extra=exported(w,definitions);errors+=extra
                        if xpt is not None and not errors:
                            # Same normalization as the earlier architecture export check.
                            for a in (frame,xpt):
                                for key,v in definitions.items():
                                    if v['Type']=='Character':a[key]=a[key].fillna('').astype('string').str.rstrip()
                            pd.testing.assert_frame_equal(frame.set_index('USUBJID').sort_index(),xpt.set_index('USUBJID').sort_index()[frame.set_index('USUBJID').columns],check_dtype=False,rtol=1e-12,atol=1e-12)
                except Exception as exc:errors.append(str(exc))
                save(d/'checks.private.json',{'passed':not errors,'errors':errors,'execution':execution,'missing_count':int(frame[name].isna().sum()) if definition and frame is not None and name in frame else None})
                item={'attempt':attempt,'passed':not errors,'usage_sha256':digest(d/'usage.json'),'program_sha256':digest(w/program),'checks_sha256':digest(d/'checks.private.json')};record['attempts'].append(item)
                if not errors:
                    save(d/'workspace-manifest.json',manifest(w));record.update(status='passed',accepted_attempt=attempt);update(record)
                    print(name+': passed attempt '+str(attempt),flush=True);return {'workspace':w,'frame':frame,'program':program}
                update(record)
                feedback='\nPrevious complete reply:\n'+text+'\nConcrete execution/QC errors:\n'+json.dumps(errors)+'\nReturn one corrected complete Python implementation for the same task.'
            record['status']='failed';update(record);print(name+': exhausted two attempts',flush=True);return None
        except Exception as exc:
            record.update(status='provider_or_controller_failure',error_type=type(exc).__name__);update(record);stop.set();raise
    try:
        review=request(json.dumps({'frozen_specification':spec,'source_schemas':schemas,'instruction':'Retain advisory review only; approved specification is immutable.'}),out/'review',REVIEW_SYSTEM)
        save(out/'review/advisory.private.json',{'text':review,'applied_to_specification':False,'human_confirmation':'Existing approved frozen specification; no new edits'})
        results={};failures=[]
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures={pool.submit(task,v['Variable'],json.dumps(context_for(v,spec,schemas),ensure_ascii=False),v):v['Variable'] for v in defs}
            for future in as_completed(futures):
                name=futures[future]
                try:results[name]=future.result()
                except Exception as exc:failures.append({'task':name,'type':type(exc).__name__})
        if failures:raise RuntimeError('Provider/controller failures; all in-flight evidence retained: '+str(failures))
        if any(not results.get(v['Variable']) for v in defs):raise RuntimeError('At least one variable did not pass; merge/export blocked')
        merged=merge_variables(keys,{k:v['frame'] for k,v in results.items()},defs)
        definition_map={v['Variable']:v for v in defs};errors=check_frame(merged,expected,list(definition_map),definition_map)
        save(out/'merge-checks.private.json',{'passed':not errors,'errors':errors})
        if errors:raise RuntimeError('Merged cross-variable invariants failed; no manual repair')
        seed=out/'merged-seed';(seed/'output/adam/programs/variables').mkdir(parents=True);(seed/'artifacts').mkdir()
        (seed/'output/adam/programs/run_task.py').write_text(WRAPPER)
        for name,result in results.items():shutil.copy2(result['workspace']/result['program'],seed/result['program'])
        merged.to_json(seed/'artifacts/merged.json',orient='table',index=False,double_precision=15)
        prompt=json.dumps({'task_type':'export','required_output_files':OUTPUT_FILES,'variable_metadata':[{k:v.get(k) for k in ('Variable','Label','Type','Length','Format','Origin','Codelist OID','Source item OID','Origin source')} for v in defs],'codelists':spec['sheets']['Codelists'],'metadata_source':'/inputs/specifications.json','upstream_schema':{k:str(v) for k,v in merged.dtypes.items()},'contract':'Preserve previous values and export exact required paths. Write metadata, manifest and notes as well. Dataset label per frozen spec. No new derivations.'},ensure_ascii=False)
        final=task('export',prompt,export_seed=seed)
        if not final:raise RuntimeError('Export exhausted two attempts')
        package=out/'final-workspace';shutil.copytree(final['workspace'],package)
        (package/'output/adam/programs/rebuild.py').write_text(replay_entry([v['Variable'] for v in defs]));before=manifest(package)
        save(out/'final-workspace-manifest.json',before)
        evaluation={'dataset_delivery':1,'variable_coverage':49,'subjects':len(merged),'selected_source_checks':source_checks(merged,root/'inputs')}
        replay=out/'replay';(replay/'output/adam').mkdir(parents=True);shutil.copytree(package/'output/adam/programs',replay/'output/adam/programs')
        execution=runtime.rebuild(replay,['python','output/adam/programs/rebuild.py'],out/'rebuild.log',base['rebuild_timeout_seconds'])
        evaluation.update(rebuild_execution=execution,semantic_reproduced=execution['exit_code']==0 and not execution['timed_out'] and semantic(package/'output/adam/datasets',replay/'output/adam/datasets'),byte_reproduced=execution['exit_code']==0 and manifest(package/'output/adam/datasets')==manifest(replay/'output/adam/datasets'))
        save(out/'evaluation.private.json',evaluation)
        final_eval=out/'final-evaluation';final_eval.mkdir()
        try:evaluation['conformance']=Evaluator({**base,'expected_datasets':['ADSL']},image).p21(package,final_eval)
        except Exception as exc:evaluation['conformance']={'report_usable':False,'failure_code':getattr(exc,'code','evaluation_error'),'error_type':type(exc).__name__}
        if manifest(package)!=before:raise RuntimeError('Final evaluator altered package')
        save(out/'evaluation.private.json',evaluation);state['status']='completed'
    except BaseException as exc:
        state.update(status='failed',error_type=type(exc).__name__,reason=str(exc));raise
    finally:
        state['finished_unix']=time.time();save(out/'state.json',state)
        shutil.copytree(out,root/'run')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare-freeze','run']);p.add_argument('--root',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--execute',action='store_true')
    a=p.parse_args();load_env(a.env_file);root=shared.private_path(a.root)
    if a.action=='prepare-freeze':
        repo=Path(__file__).resolve().parents[1];project=repo.parents[1]
        base=json.loads((project/'experiments/config.gemini-temperature-qualified.local.json').read_text())
        shared.prepare(base,root,project/'experiments/gxp-adsl-access-20261028/nonclinical.json',project/'experiments/gxp-adsl-runtime-smoke-20261028/receipt.json')
        shutil.copy2(project/'experiments/ai431-adsl-runtime-smoke-20261101/receipt.json',root/'nonclinical-variable-runtime.json')
        technical=json.loads((root/'nonclinical-variable-runtime.json').read_text())
        if not technical.get('passed') or technical.get('clinical_inputs_used') is not False:raise ValueError('Passing nonclinical variable runtime receipt required')
        shutil.copy2('/private/tmp/ai431-export-qualification-v2/receipt.json',root/'nonclinical-export-qualification.json')
        frozen=frozen_payload(root);save(root/'freeze.json',{'payload':frozen,'sha256':fingerprint(frozen)})
        print('Frozen independent AI-431-inspired ADSL pilot: 49 variable tasks, concurrency 3, two attempts maximum.')
    else:
        if not a.execute:p.error('run requires --execute')
        run(root)

if __name__=='__main__':main()
