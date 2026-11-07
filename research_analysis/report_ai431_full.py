"""Stream-verify complete private evidence; publish only the 19 aggregate metrics."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile
import tempfile
import pyreadstat
from ai431_full.client import parse,tokens,body_for
from ai431_full.run import own_code,shared_code
from main_experiment.core import fingerprint
from main_experiment.support import digest,save,manifest
from research_analysis.report_gxp_full import METRICS
from research_analysis.supplementary_metrics import inventory,schema_counts

def read(path):return json.loads(Path(path).read_text())

def normalized_usage(profile, usage):
    # DeepInfra can omit cache details with JSON null; never invent zero usage.
    unknown_cache=(profile['kind']=='chat' and usage.get('prompt_tokens_details') is None and 'prompt_cache_hit_tokens' not in usage)
    counts=tokens(profile,{**usage,'prompt_tokens_details':usage.get('prompt_tokens_details') or {}} if unknown_cache else usage)
    if unknown_cache:counts['cached_input']=None
    return counts

def report(root,out):
    lock=read(root/'freeze.json');frozen=lock['payload']
    if fingerprint(frozen)!=lock['sha256'] or frozen['code']!=own_code() or frozen['shared_code']!=shared_code() or manifest(root/'inputs')!=frozen['inputs']:raise ValueError('Frozen code or input drift')
    receipt=read(root/'archive-receipt.json');archive=root/'run-evidence.tar.gz';expected=read(root/'evidence-manifest.private.json')
    if not receipt.get('verified_lossless') or digest(archive)!=receipt['sha256']:raise ValueError('Archive receipt/hash mismatch')
    selected={};observed={};metadata={}
    suffixes=('state.json','evaluation.private.json','checks.private.json','workspace-manifest.json','usage.json','request.private.json','response.private.json','provider-failure.json','completion-failure.json','p21-runtime-before.json')
    with tempfile.TemporaryDirectory(prefix='ai431-private-metrics-') as temporary,tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            path=PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or member.name in observed:raise ValueError('Unsafe or duplicate archive member')
            stream=tar.extractfile(member);h=hashlib.sha256();retain=member.name.endswith(suffixes) and '/workspace/' not in member.name;chunks=[]
            xpt=member.name.startswith('final-workspace/output/adam/datasets/') and member.name.endswith('.xpt')
            sink=(Path(temporary)/path.name).open('wb') if xpt else None
            try:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    h.update(block)
                    if retain:chunks.append(block)
                    if sink:sink.write(block)
            finally:
                stream.close()
                if sink:sink.close()
            observed[member.name]=h.hexdigest()
            if retain:selected[member.name]=json.loads(b''.join(chunks))
            if xpt:
                _,meta=pyreadstat.read_xport(str(Path(temporary)/path.name),metadataonly=True,disable_datetime_conversion=True)
                metadata[path.stem.upper()]={k:'Character' if v=='string' else 'Numeric' for k,v in meta.readstat_variable_types.items()}
    if observed!=expected:raise ValueError('Complete lossless archive verification failed')
    state=selected['state.json']
    if state['status'] not in ('completed','completed_partial','failed'):raise ValueError('Unfinished run')
    audit=[];sandbox=failed_sandbox=0;stages=Counter({k:0 for k in ('input_reading','code_execution','dataset_export','define_xml_generation','rebuilding','p21_validation')})
    def inspect_attempt(prefix,item,program):
        nonlocal sandbox,failed_sandbox
        if observed[prefix+'/workspace/'+program]!=item['program_sha256'] or observed[prefix+'/checks.private.json']!=item['checks_sha256'] or observed[prefix+'/usage.json']!=item['usage_sha256']:raise ValueError('Attempt receipt mismatch')
        checks=selected[prefix+'/checks.private.json']
        if item['passed']:
            workspace=selected[prefix+'/workspace-manifest.json'];actual={k[len(prefix+'/workspace/'):]:v for k,v in observed.items() if k.startswith(prefix+'/workspace/')}
            if workspace!=actual:raise ValueError('Accepted workspace manifest mismatch')
        execution=checks.get('execution')
        if execution:sandbox+=1;failed_sandbox+=int(execution['exit_code']!=0 or execution.get('timed_out',False))
        audit.append({'prefix':prefix,'program_sha256':item['program_sha256'],'checks_sha256':item['checks_sha256'],'usage_sha256':item['usage_sha256'],'passed':item['passed']})
        return checks
    for task in state['tasks']:
        for attempt in task['attempts']:
            prefix='datasets/'+task['dataset']+'/tasks/'+task['task']+'/attempt-'+str(attempt['attempt']);program='output/adam/programs/variables/'+task['dataset']+'__'+task['task']+'.py'
            checks=inspect_attempt(prefix,attempt,program)
            if not checks['passed']:
                errors=' '.join(checks['errors']);stage='input_reading' if any(t in errors for t in ('FileNotFoundError','PyreadstatError','UnicodeDecodeError','source_files')) else 'code_execution';stages[stage]+=1
    for attempt in state.get('export',{}).get('attempts',[]):
        prefix='export/attempt-'+str(attempt['attempt']);checks=inspect_attempt(prefix,attempt,'output/adam/programs/export.py')
        if not checks['passed']:
            errors=' '.join(checks['errors']);stages['define_xml_generation' if 'Define' in errors or 'define.xml' in errors else 'dataset_export']+=1
    usage=Counter();native=[];completions=[];unknown_cache_calls=0
    for path,raw in selected.items():
        if not path.endswith('/response.private.json'):continue
        prefix=path.removesuffix('/response.private.json');request=selected[prefix+'/request.private.json'];profile=frozen['provider_profile']
        if profile['kind']=='anthropic':system=request['system'];prompt=request['messages'][0]['content']
        elif profile['kind']=='gemini':system=request['systemInstruction']['parts'][0]['text'];prompt=request['contents'][0]['parts'][0]['text']
        elif profile['kind']=='chat':system=request['messages'][0]['content'];prompt=request['messages'][1]['content']
        else:system=request['instructions'];prompt=request['input']
        if request!=body_for(profile,prompt,system) or system not in (frozen['variable_system'],frozen['review_system'],frozen['export_system']):raise ValueError('Request settings drift')
        try:parsed=parse(profile,raw)
        except ValueError:
            # A rejected tool/format reply still consumes native usage.
            if prefix+'/completion-failure.json' not in selected:raise
            parsed={'usage':raw.get('usageMetadata',raw.get('usage',{})),'model':raw.get('modelVersion',raw.get('model')),'stop_reason':'rejected_format','normal':False}
        if parsed['model']!=profile['response_model']:raise ValueError('Returned model drift')
        if prefix+'/usage.json' in selected:
            usage_receipt=selected[prefix+'/usage.json']
            if parsed['usage']!=usage_receipt['usage'] or parsed['model']!=usage_receipt['model'] or parsed['stop_reason']!=usage_receipt['stop_reason']:raise ValueError('Native usage receipt drift')
        counts=normalized_usage(profile,parsed['usage'])
        if counts.get('cached_input') is None:unknown_cache_calls+=1
        for k,native_key in [('input_tokens','input'),('output_tokens','output'),('cache_read_input_tokens','cached_input')]:
            if counts.get(native_key) is not None:usage[k]+=counts.get(native_key,0)
        native.append({'request_sha256':observed[prefix+'/request.private.json'],'response_sha256':observed[path],'stop_reason':parsed['stop_reason'],'normalized_usage':counts,'review_call':prefix.startswith('reviews/')})
        if not parsed['normal']:completions.append({'task_path':prefix,'stop_reason':parsed['stop_reason'],'usage':counts})
    if unknown_cache_calls:usage['cache_read_input_tokens']=None
    evaluation=selected.get('evaluation.private.json',{});con=evaluation.get('conformance') or {};correct=evaluation.get('correctness') or {};checks={c['check']:c for c in correct.get('checks',[])}
    package_prefix='final-workspace/'
    actual_package={k[len(package_prefix):]:v for k,v in observed.items() if k.startswith(package_prefix)}
    if actual_package and actual_package!=selected.get('final-workspace-manifest.json'):raise ValueError('Final package manifest mismatch')
    if 'final-evaluation/p21-runtime-before.json' in selected and selected['final-evaluation/p21-runtime-before.json']!=frozen['p21_cache']:raise ValueError('P21 initial runtime drift')
    domains=[];delivered=matched=0
    for name,defs in inventory(root/'inputs/specifications.json').items():
        row={'dataset':name,'generation_status':state['datasets'].get(name,{}).get('status','blocked'),'delivered':name in metadata,'matched_variables':0,'expected_variables':len(defs),'rows':evaluation.get('content_profile',{}).get('datasets',{}).get(name,{}).get('rows')}
        if name in metadata:
            row.update(schema_counts(defs,metadata[name]));delivered+=1;matched+=row['matched_variables']
        domains.append(row)
    if evaluation.get('rebuild') and (evaluation['rebuild']['exit_code'] or evaluation['rebuild'].get('timed_out')) or evaluation.get('rebuild_error'):stages['rebuilding']+=1
    if evaluation and not con.get('report_usable'):stages['p21_validation']+=1
    complete=bool(evaluation.get('deliverables_complete')) and delivered==13
    severity=Counter()
    for issue in con.get('issues',[]):severity[issue.get('severity') or 'Unassigned']+=issue.get('findings',0)
    def selected_checks(names):return {n:{k:checks[n].get(k) for k in ('status','errors','assessed','coverage','qualification')} if n in checks else {'status':'unavailable','errors':None,'assessed':None} for n in names}
    coverage={n:c.get('coverage') for n,c in checks.items() if c.get('coverage') is not None}
    provider_failures=[{'task_path':p.removesuffix('/provider-failure.json'),**v} for p,v in selected.items() if p.endswith('/provider-failure.json')]
    values=[{'workflow_completed':state['status']=='completed','complete_packages':int(complete),'planned_packages':1},
        {'semantic_reproduced':evaluation.get('semantic_reproduced'),'byte_reproduced':evaluation.get('byte_reproduced')},
        {'report_usable':con.get('report_usable'),'full_validated_coverage':con.get('validation_coverage_complete'),'complete_package':complete},
        {'initial':None,'final_primary_dataset_rule_pairs':con.get('dataset_rule_pairs') if complete and con.get('validation_coverage_complete') else None,'observed_final_dataset_rule_pairs':con.get('dataset_rule_pairs'),'note':'Terminal-only P21, partial counts descriptive'},None,dict(severity) if con.get('report_usable') else None,None,
        selected_checks(['npi_mean_coverage','npi_mean_value']),selected_checks(['npi_baseline_covariate']),selected_checks(['tte_subject_coverage','tte_start_date','tte_event_status','tte_source_link','tte_event_date','tte_duration_arithmetic','tte_censor_convention']),
        {'scope':'Selected NPI/TTE expectations only','coverage':coverage or None},{'assessable':sum(c.get('status')=='scored' for c in checks.values()),'planned':10},None,dict(usage),(state['finished_unix']-state['started_unix'])/60,
        {'model_tool_calls':None,'sandbox_executions':sandbox,'failed_sandbox_executions':failed_sandbox,'note':'Direct native APIs; no model tool loop'},
        {'delivered':delivered,'expected':13,'rate':delivered/13},{'matched':matched,'expected':531,'rate':matched/531},
        {'observed_attempt_failure_counts':dict(stages),'failed_variable_tasks':sum(t['kind']=='variable' and t['status']=='failed' for t in state['tasks']),'failed_row_universe_tasks':sum(t['kind']=='row_universe' and t['status']=='failed' for t in state['tasks']),'failed_merge_qc_datasets':sum(d.get('status')=='failed_merge_qc' for d in state['datasets'].values()),'blocked_datasets':[d['dataset'] for d in domains if d['generation_status'].startswith('blocked')],'provider_http_or_transport_failures':len(provider_failures),'invalid_completion_calls':len(completions),'note':'Observed failures are distinct from blocked work; P21 findings are not validator execution failures.'}]
    candidate=None
    if not actual_package and state.get('export',{}).get('attempts'):
        last=state['export']['attempts'][-1];candidate_checks=selected['export/attempt-'+str(last['attempt'])+'/checks.private.json'];candidate_coverage=candidate_checks.get('coverage',{})
        candidate={'accepted':False,'export_attempt':last['attempt'],'readable_datasets':len(candidate_coverage),'expected_datasets':13,'matched_variables':sum(d['variables_matched'] for d in candidate_coverage.values()),'expected_variables':531,'datasets':candidate_coverage,'gate_error_count':len(candidate_checks['errors'])}
    summary={'scope':'Single excluded new full-benchmark AI-431-inspired attempt','architecture':frozen['architecture'],'status':state['status'],'model':frozen['model'],'provider':frozen['provider'],'provider_profile':frozen['provider_profile'],'freeze_sha256':lock['sha256'],'main_study_started':False,'unaccepted_terminal_candidate':candidate,
        'datasets':domains,'planned_variables':531,'passed_variable_tasks':sum(t['kind']=='variable' and t['status']=='passed' for t in state['tasks']),'passed_row_universe_tasks':sum(t['kind']=='row_universe' and t['status']=='passed' for t in state['tasks']),
        'failed_tasks':[{k:t[k] for k in ('dataset','task','kind','status')} for t in state['tasks'] if t['status']!='passed'],'repaired_tasks':[{k:t[k] for k in ('dataset','task','kind')} for t in state['tasks'] if t.get('accepted_attempt')==2],
        'generation_responses':len(native),'advisory_review_responses':sum(r['review_call'] for r in native),'native_usage':dict(usage),'cache_usage_unavailable_responses':unknown_cache_calls,'elapsed_seconds':state['finished_unix']-state['started_unix'],'export_status':state.get('export',{}).get('status','blocked'),'invalid_completions':completions,'provider_failures':provider_failures,
        'P21':{k:con.get(k) for k in ('report_usable','validation_coverage_complete','dataset_rule_pairs','finding_instances','distinct_rules','failure_code')},'metrics':[{'number':i+1,'metric':label,'value':value} for i,(label,value) in enumerate(zip(METRICS,values))],
        'limitations':['Independent full-benchmark adaptation, not author software or numerical replication.','Single nonrandomized exploratory attempt per planned endpoint; no causal superiority claims.','Immutable human-approved specifications; advisory model review does not reproduce interactive refinement.','Row universes are model-generated, without an exhaustive clinical row/value oracle.','Selected NPI/TTE checks and P21 do not certify every clinical derivation.','Terminal-only P21; initial/final reductions and new-rule counts unavailable.','Hosted model identities/defaults are provider assertions, not equal or fixed sampling/weights.','No prior generated clinical code or results reused; main-study freeze unchanged.']}
    out.mkdir(parents=True,exist_ok=False);save(out/'summary.json',summary)
    save(out/'audit.json',{'freeze_sha256':lock['sha256'],'archive_sha256':receipt['sha256'],'complete_file_manifest_stream_verified':True,'files':len(observed),'state_sha256':observed['state.json'],'code':frozen['code'],'shared_code':frozen['shared_code'],'attempts':audit,'native_responses':native,'reporter_sha256':digest(Path(__file__))})
    print(json.dumps({'model':frozen['model'],'status':state['status'],'passed_variables':summary['passed_variable_tasks'],'delivered':delivered,'matched_variables':matched,'responses':len(native)}),flush=True)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();report(a.root,a.out)

if __name__=='__main__':main()
