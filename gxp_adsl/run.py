"""Prepare/freeze and run one independent ADSL-only Process-DAG feasibility pilot."""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request

import pandas as pd
import pyreadstat

from main_experiment.backend import capture
from main_experiment.core import code_manifest, fingerprint, private_path
from main_experiment.evaluate import Evaluator, semantic
from main_experiment.rebuild import RebuildRuntime
from main_experiment.support import digest, load_env, manifest, save
from .dag import NODES, SYSTEM, WRAPPER, OUTPUT_FILES
from .checks import variables, eligible, check_frame, exported, source_checks, validate_plan

HERE = Path(__file__).resolve().parent
MODEL = 'claude-sonnet-5-5'
DOMAINS = ['dm','sv','ex','ds','qs','vs','sc','mh']
MAX_TOKENS = 32768


def tools():
    return {p.name: digest(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.md')}


def prepare(base, root, receipt, runtime_receipt):
    if root.exists():
        raise ValueError('Preserve existing pilot; preparation requires a new directory')
    root.mkdir(parents=True)
    target = root/'inputs'; (target/'Input').mkdir(parents=True)
    source = Path(base['inputs'])
    spec = json.loads((source/'specifications.json').read_text())
    validate_plan(spec)
    selected = ['I01','I02','I03','I04','I05','I06','I11','I12','I13']
    rows = variables(spec)
    ids = {'GEN01'}
    for row in rows:
        ids.update(re.findall(r'\b[A-Z]+\d+\b', str(row['Rule IDs'])))
    sheets = spec['sheets']
    codes = {r['Codelist OID'] for r in rows if r.get('Codelist OID')}
    subset = {'format': 'ADSL-only subset of frozen benchmark cell-value specification',
        'define_xml_version': '2.0.0', 'source_specifications_sha256': digest(source/'specifications.json'),
        'sheets': {'ReadMe': sheets['ReadMe'], 'ADSL': sheets['ADSL'],
            'Rules': [sheets['Rules'][0]]+[r for r in sheets['Rules'][1:] if r[0] in ids],
            'Implementation details': [sheets['Implementation details'][0]]+[r for r in sheets['Implementation details'][1:] if r[0] in selected],
            'Windows': sheets['Windows'], 'Site map': sheets['Site map'],
            'Codelists': [sheets['Codelists'][0]]+[r for r in sheets['Codelists'][1:] if r[0] in codes]}}
    save(target/'specifications.json', subset)
    shutil.copy2(source/'SAP.pdf', target/'SAP.pdf')
    schemas = {}
    for domain in DOMAINS:
        p = source/'Input'/(domain+'.xpt')
        shutil.copy2(p, target/'Input'/p.name)
        frame, metadata = pyreadstat.read_xport(str(p), disable_datetime_conversion=True)
        schemas[domain.upper()] = {'rows': len(frame), 'columns': metadata.readstat_variable_types}
    save(root/'source-schemas.json', schemas)
    ready = json.loads(receipt.read_text())
    if ready.get('model') != MODEL or ready.get('stop_reason') != 'end_turn':
        raise ValueError('Exact-model nonclinical connection receipt required')
    shutil.copy2(receipt, root/'nonclinical-connection.json')
    technical=json.loads(runtime_receipt.read_text())
    if technical.get('passed') is not True or technical.get('clinical_inputs_used') is not False:
        raise ValueError('Passing nonclinical sandbox receipt required')
    shutil.copy2(runtime_receipt,root/'nonclinical-runtime.json')
    save(root/'source-provenance.json', {'base_input_specifications_sha256': digest(source/'specifications.json'),
        'selected_original_inputs': {str(p.relative_to(source)): digest(p) for p in
            [source/'SAP.pdf', *[source/'Input'/(d+'.xpt') for d in DOMAINS]]},
        'scope': 'ADSL only; full-study reference ADaM and evaluator are not agent inputs'})
    save(root/'base-config.private.json', base)
    return subset


def payload(root):
    base = json.loads((root/'base-config.private.json').read_text())
    image = capture(['docker','image','inspect','--format','{{.Id}}',base['image']])
    python_version = capture(['docker','run','--rm','--network','none',image,'python','--version'])
    spec = json.loads((root/'inputs/specifications.json').read_text()); validate_plan(spec)
    if json.loads((root/'nonclinical-runtime.json').read_text())['image'] != image:
        raise ValueError('Nonclinical runtime evidence uses another image')
    if json.loads((root/'nonclinical-runtime.json').read_text())['wrapper_sha256'] != hashlib.sha256(WRAPPER.encode()).hexdigest():
        raise ValueError('Nonclinical runtime wrapper differs from frozen code')
    return {'architecture': 'independent GxP-Agent-inspired ADSL Process-DAG; Python adaptation, not original R implementation',
        'model': MODEL, 'provider': 'Anthropic direct Messages API', 'max_tokens': MAX_TOKENS,
        'sampling': 'provider defaults; no temperature or reasoning override; no claim of immutable hosted weights',
        'nodes': NODES, 'system_prompt': SYSTEM, 'wrapper': WRAPPER,
        'max_attempts_per_node': 2, 'provider_retry': False,
        'code': tools(), 'reused_main_code': code_manifest(), 'image': image, 'python_version':python_version,
        'inputs': manifest(root/'inputs'), 'source_schemas_sha256': digest(root/'source-schemas.json'),
        'source_provenance_sha256': digest(root/'source-provenance.json'),
        'connection_sha256': digest(root/'nonclinical-connection.json'),
        'nonclinical_runtime_sha256': digest(root/'nonclinical-runtime.json'),
        'base_config_sha256': digest(root/'base-config.private.json'),
        'p21_cache':manifest(Path(base['p21']['cache'])),
        'p21_support_inputs':{d:digest(Path(base['inputs'])/'Input'/(d.lower()+'.xpt')) for d in base['p21']['support_domains']},
        'expected_subjects': len(eligible(root/'inputs')), 'expected_variables': 49,
        'P21_feedback': False, 'main_study_started': False,
        'policy': 'One excluded pilot. Fixed sequential dependency order. Fresh narrow model context per node; one local code/QC repair. Fail closed and block dependents on exhausted or uncertain failure. No manual clinical code edits. Offline sandbox execution and independent final rebuild/P21; P21 findings are never returned to the model.'}


def request(prompt, directory):
    body = {'model': MODEL, 'max_tokens': MAX_TOKENS, 'system': SYSTEM,
            'messages': [{'role':'user','content':prompt}]}
    save(directory/'request.private.json', body)
    headers = {'x-api-key': os.environ['ANTHROPIC_API_KEY'],
               'anthropic-version':'2023-06-01', 'content-type':'application/json'}
    req = urllib.request.Request('https://api.anthropic.com/v1/messages',
                                 data=json.dumps(body).encode(), headers=headers)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.load(response)
    except Exception as error:
        save(directory/'provider-failure.json', {'type':type(error).__name__,
            'status':getattr(error,'code',None),'seconds':time.time()-started,
            'policy':'No automatic API retry; preserve uncertain request and stop scheduling'})
        raise
    save(directory/'response.private.json', result)
    save(directory/'usage.json', {'model':result.get('model'), 'stop_reason':result.get('stop_reason'),
        'usage':result.get('usage'), 'seconds':time.time()-started})
    if result.get('model') != MODEL or result.get('stop_reason') != 'end_turn':
        raise RuntimeError('Provider identity or completion is uncertain; no automatic retry')
    text = '\n'.join(x['text'] for x in result.get('content',[]) if x.get('type')=='text').strip()
    return text


def extract_code(text):
    """Accept plain Python or one unambiguous Python fence with surrounding prose."""
    lines = text.strip().splitlines()
    markers = [(i, line.strip()) for i, line in enumerate(lines)
               if line.lstrip().startswith(('```', '~~~'))]
    if not markers:
        return text.strip()
    if len(markers) != 2:
        raise ValueError('Expected exactly one complete Python code block; multiple or incomplete blocks rejected')
    (start, opening), (end, closing) = markers
    if opening not in ('```python', '```py', '```', '~~~python', '~~~py', '~~~') or closing != opening[:3]:
        raise ValueError('Expected one Python code block with matching delimiters')
    code = '\n'.join(lines[start+1:end]).strip()
    if not code:
        raise ValueError('Empty Python code block')
    return code


def source_files():
    return {domain.upper(): '/inputs/Input/'+domain+'.xpt' for domain in DOMAINS}


def prompt_for(index, required, specs, schemas, previous):
    name, owned, task = NODES[index]
    rows = variables(specs)
    target = rows if name in ('validate','apply_metadata','export') else [r for r in rows if r['Variable'] in owned]
    context = {'node':name, 'task':task, 'assigned_variables':owned,
        'cumulative_required_variables':sorted(required), 'expected_ADSL_population':'GEN01 randomized DM ARMCD in Pbo, Xan_Lo, Xan_Hi; exclude screening failures',
        'node_variable_specifications':target,
        'rules':specs['sheets']['Rules'], 'implementation_details':specs['sheets']['Implementation details'],
        'codelists':specs['sheets']['Codelists'], 'windows':specs['sheets']['Windows'],
        'site_map':specs['sheets']['Site map'] if name=='derive_site' else None,
        'source_schemas':schemas,
        'source_files':source_files(),
        'input_path_contract':'Use these exact case-sensitive absolute paths. Do not construct uppercase filenames.',
        'upstream_schema': {str(k):str(v) for k,v in previous.dtypes.items()} if previous is not None else None,
        'upstream_rows':len(previous) if previous is not None else None,
        'required_output_files':OUTPUT_FILES if name in ('apply_metadata','export') else None,
        'output_path_contract':'Paths are relative to /workspace; create files at these exact paths. Define-XML belongs beside adsl.xpt in output/adam/datasets, not output/adam. Metadata node writes only metadata; export writes the other deliverables.',
        'output_contract':'Return a dataframe; controller saves the intermediate artifact. Metadata/export must additionally create their designated files. No reference output is supplied.'}
    return json.dumps(context, ensure_ascii=False, indent=2)


def rebuild_entry():
    commands = []
    previous = '-'
    for i,(name,_,_) in enumerate(NODES,1):
        artifact = f'artifacts/{i:02d}-{name}.json'
        commands.append(['python','output/adam/programs/run_node.py',f'output/adam/programs/nodes/{i:02d}-{name}.py',previous,artifact])
        previous = artifact
    return 'import subprocess\n\nfor command in '+repr(commands)+':\n    subprocess.run(command, check=True)\n'


def run(root):
    lock = json.loads((root/'freeze.json').read_text())
    current = payload(root)
    if lock != {'payload': current, 'sha256': fingerprint(current)}:
        raise ValueError('Freeze drift')
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ValueError('Missing local ANTHROPIC_API_KEY')
    if shutil.disk_usage(root).free < 10*1024**3:
        raise ValueError('Require at least 10 GiB free before starting this pilot')
    out = root/'run'; out.mkdir(exist_ok=False)
    save(out/'plan.json', lock)
    base = json.loads((root/'base-config.private.json').read_text())
    config = {**base, 'inputs':str(root/'inputs')}
    runtime = RebuildRuntime(config, current['image'])
    spec = json.loads((root/'inputs/specifications.json').read_text())
    definitions = {x['Variable']:x for x in variables(spec)}
    expected = eligible(root/'inputs')
    schemas = json.loads((root/'source-schemas.json').read_text())
    accepted = out/'seed'; (accepted/'output/adam/programs/nodes').mkdir(parents=True)
    (accepted/'output/adam/programs/run_node.py').write_text(WRAPPER)
    required = {'STUDYID','USUBJID'}
    previous_path = '-'; previous = None; records = []
    state = {'status':'running','started_unix':time.time(),'main_study_started':False,'records':records}
    save(out/'state.json', state)
    try:
        for index,(name,owned,_) in enumerate(NODES):
            if tools() != current['code'] or manifest(root/'inputs') != current['inputs']:
                raise ValueError('Frozen code or input drift during run')
            print(f'Node {index+1}/15: {name}', flush=True)
            required.update(owned)
            node = {'node':name,'status':'running','attempts':[]}; records.append(node)
            original_prompt = prompt_for(index, required, spec, schemas, previous)
            feedback = ''
            succeeded = False
            for attempt in (1,2):
                directory = out/'nodes'/f'{index+1:02d}-{name}'/f'attempt-{attempt}'
                directory.mkdir(parents=True)
                code = request(original_prompt+feedback, directory)
                candidate = directory/'workspace'; shutil.copytree(accepted, candidate)
                program = f'output/adam/programs/nodes/{index+1:02d}-{name}.py'
                artifact = f'artifacts/{index+1:02d}-{name}.json'
                (candidate/program).write_text(code)
                errors = []
                execution = None
                try:
                    code = extract_code(code)
                    (candidate/program).write_text(code)
                    protected = manifest(candidate)
                    tree = ast.parse(code)
                    if not any(isinstance(n,ast.FunctionDef) and n.name=='run' for n in tree.body):
                        raise ValueError('Expected top-level run(previous, inputs) function')
                    execution = runtime.rebuild(candidate,
                        ['python','output/adam/programs/run_node.py',program,previous_path,artifact],
                        directory/'execution.log',base['rebuild_timeout_seconds'])
                    if execution['exit_code'] != 0 or execution['timed_out']:
                        raise ValueError('Node execution failed: '+(directory/'execution.log').read_text(errors='replace')[-4000:])
                    after = manifest(candidate)
                    if any(after.get(k) != v for k,v in protected.items()):
                        raise ValueError('Node modified or removed protected upstream artifacts/programs')
                    frame = pd.read_json(candidate/artifact, orient='table')
                    errors = check_frame(frame, expected, required, definitions, previous, owned)
                    if name=='apply_metadata' and not (candidate/OUTPUT_FILES['metadata']).is_file():
                        errors.append('Metadata JSON not delivered')
                    if name=='export':
                        xpt, extra = exported(candidate, definitions); errors += extra
                        if xpt is not None and not errors:
                            try:
                                left,right=[x.set_index('USUBJID')[list(k for k in definitions if k!='USUBJID')].sort_index().copy() for x in (frame,xpt)]
                                for key,definition in definitions.items():
                                    if key!='USUBJID' and definition['Type']=='Character':
                                        left[key]=left[key].fillna('').astype('string').str.rstrip()
                                        right[key]=right[key].fillna('').astype('string').str.rstrip()
                                pd.testing.assert_frame_equal(left,right,check_dtype=False,rtol=1e-12,atol=1e-12)
                            except AssertionError:
                                errors.append('Exported values differ from the checked intermediate dataframe')
                except Exception as error:
                    errors.append(str(error))
                passed = not errors
                save(directory/'checks.private.json', {'passed':passed,'errors':errors,
                    'required_variables':sorted(required),'execution':execution})
                node['attempts'].append({'attempt':attempt,'passed':passed,'error_count':len(errors),
                    'usage_sha256':digest(directory/'usage.json'), 'program_sha256':digest(candidate/program),
                    'checks_sha256':digest(directory/'checks.private.json')})
                save(out/'state.json', state)
                if passed:
                    save(directory/'workspace-manifest.json',manifest(candidate))
                    accepted = candidate; previous_path = artifact; previous = frame
                    node.update(status='passed',accepted_attempt=attempt)
                    succeeded = True
                    break
                feedback = '\n\nPrevious implementation:\n'+code+'\n\nConcrete execution/check errors:\n'+json.dumps(errors)+'\nReturn one corrected complete Python implementation for this same node.'
            if not succeeded:
                node['status']='failed'
                state['blocked_nodes']=[n[0] for n in NODES[index+1:]]
                raise RuntimeError('Node exhausted two attempts: '+name)
            save(out/'state.json', state)
        package = out/'final-workspace'; shutil.copytree(accepted, package)
        (package/'output/adam/programs/rebuild.py').write_text(rebuild_entry())
        before = manifest(package)
        evaluation = {'expected_datasets':1,'expected_variables':49,'main_study_started':False,
            'dataset_delivery':1,'variable_coverage':49,'subjects':len(previous),
            'selected_source_checks':source_checks(previous,root/'inputs')}
        replay = out/'replay'; (replay/'output/adam').mkdir(parents=True)
        shutil.copytree(package/'output/adam/programs',replay/'output/adam/programs')
        execution = runtime.rebuild(replay,['python','output/adam/programs/rebuild.py'],out/'rebuild.log',base['rebuild_timeout_seconds'])
        evaluation['rebuild_execution']=execution
        evaluation['semantic_reproduced']=execution['exit_code']==0 and not execution['timed_out'] and semantic(package/'output/adam/datasets',replay/'output/adam/datasets')
        evaluation['byte_reproduced']=execution['exit_code']==0 and manifest(package/'output/adam/datasets')==manifest(replay/'output/adam/datasets')
        save(out/'evaluation.private.json',evaluation)
        final_eval=out/'final-evaluation'; final_eval.mkdir()
        # Original clean-cache P21 wrapper; only expected_datasets changes to ADSL.
        evaluator=Evaluator({**base,'expected_datasets':['ADSL']},current['image'])
        try:
            evaluation['conformance']=evaluator.p21(package,final_eval)
        except Exception as error:
            evaluation['conformance']={'report_usable':False,'dataset_rule_pairs':None,
                'failure_code':getattr(error,'code','evaluation_error'),'error_type':type(error).__name__}
        if manifest(package)!=before:
            raise RuntimeError('Final evaluator altered delivered workspace')
        save(out/'final-workspace-manifest.json', before)
        save(out/'evaluation.private.json',evaluation)
        state['status']='completed'
    except BaseException as error:
        state.update(status='failed',error_type=type(error).__name__,reason=str(error))
        raise
    finally:
        state['finished_unix']=time.time(); save(out/'state.json',state)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare-freeze','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--env-file',type=Path,required=True)
    p.add_argument('--base-config',type=Path)
    p.add_argument('--connection-receipt',type=Path)
    p.add_argument('--runtime-receipt',type=Path)
    p.add_argument('--execute',action='store_true')
    a=p.parse_args(); load_env(a.env_file); root=private_path(a.root)
    if a.action=='prepare-freeze':
        if not a.base_config or not a.connection_receipt or not a.runtime_receipt:
            p.error('prepare-freeze requires base-config and nonclinical connection/runtime receipts')
        prepare(json.loads(a.base_config.read_text()),root,a.connection_receipt,a.runtime_receipt)
        frozen=payload(root); save(root/'freeze.json',{'payload':frozen,'sha256':fingerprint(frozen)})
        print('Frozen independent ADSL Process-DAG pilot: 15 nodes, 49 variables, '+str(frozen['expected_subjects'])+' eligible subjects.')
    else:
        if not a.execute:p.error('run requires --execute')
        run(root)


if __name__=='__main__':main()
