"""Evidence-checked full-benchmark DAG results with the existing 19 metric labels."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import pyreadstat
from main_experiment.core import fingerprint,code_manifest
from main_experiment.support import digest,manifest,save
from research_analysis.supplementary_metrics import inventory,schema_counts
from gxp_full.run import own_code
from gxp_adsl import run as shared
from ai431_adsl.run import code_files as ai_code

METRICS=['Workflow completion and complete dataset packages','Reproducible final packages','Valid final P21 evaluations','Initial and final dataset-rule pairs','Reduction from initial to final','Final findings by severity','Newly introduced dataset-rule pairs','NPI summary errors / assessed records','NPI baseline errors / assessed records','TTE linkage errors / assessed records','Missing extra and duplicate expected records','Assessable checks / planned checks','Workflow API cost estimate in USD','Input and output tokens','End-to-end elapsed time in minutes','Tool calls and failed tool calls','Dataset Delivery Rate','Variable Coverage','Failure-stage distribution']


def read(path):return json.loads(path.read_text()) if path.is_file() else None


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--run-directory',type=Path);p.add_argument('--rebuild-diagnostics',type=Path);a=p.parse_args();root=a.root;run=a.run_directory or root/'run'
    lock=read(root/'freeze.json');frozen=lock['payload']
    multi='provider_profile' in frozen
    if multi:
        if 'resume_manifest' in frozen:
            from gxp_recovery.run import own_code as provider_code
            from gxp_models.run import own_code as transport_code
            if transport_code()!=frozen['native_transport_code']:raise ValueError('Native transport code drift')
        elif frozen.get('historical_program_reuse') is False:
            from gxp_fresh.run import own_code as provider_code
            from gxp_models.run import own_code as transport_code
            if transport_code()!=frozen['native_transport_code']:raise ValueError('Native transport code drift')
        else:
            from gxp_models.run import own_code as provider_code
        from gxp_models.client import parse,tokens,body_for
        execution_code=provider_code()
        if own_code()!=frozen['shared_architecture']:raise ValueError('Shared repaired architecture drift')
    else:execution_code=own_code()
    if execution_code!=frozen['code']:
        snapshot=root/'original-code-snapshot'
        execution_code={name:digest(snapshot/name) for name in frozen['code']} if snapshot.is_dir() else {}
    if fingerprint(frozen)!=lock['sha256'] or execution_code!=frozen['code'] or shared.tools()!=frozen['shared_gxp_helpers'] or (not multi and ai_code()!=frozen['shared_ai_transport']) or code_manifest()!=frozen['reused_main_code']:raise ValueError('Frozen lock/code drift')
    if manifest(root/'inputs')!=frozen['inputs']:raise ValueError('Frozen inputs changed')
    state=read(run/'state.json')
    if not state or state['status'] not in ('completed','completed_partial','failed'):raise ValueError('Run active or missing')
    audit=[];sandbox_runs=sandbox_failed=0;stages=Counter({x:0 for x in ['input_reading','code_execution','dataset_export','define_xml_generation','rebuilding','p21_validation']})
    for record in state['nodes']:
        for item in record['attempts']:
            d=run/'datasets'/record['dataset']/'nodes'/record['node']/f"attempt-{item['attempt']}";program=d/'workspace/output/adam/programs/nodes'/(record['dataset']+'__'+record['node']+'.py')
            if digest(program)!=item['program_sha256'] or digest(d/'checks.private.json')!=item['checks_sha256'] or digest(d/'usage.json')!=item['usage_sha256']:raise ValueError('Node attempt drift')
            if item['passed'] and manifest(d/'workspace')!=read(d/'workspace-manifest.json'):raise ValueError('Accepted node workspace drift')
            checks=read(d/'checks.private.json');execution=checks.get('execution')
            if execution:
                sandbox_runs+=1;sandbox_failed+=int(execution['exit_code']!=0 or execution['timed_out'])
            if not checks['passed']:
                text=' '.join(checks['errors']);stage='input_reading' if ('/inputs/' in text and any(x in text for x in ('FileNotFoundError','PyreadstatError','UnicodeDecodeError'))) else 'code_execution';stages[stage]+=1
            audit.append({'dataset':record['dataset'],'node':record['node'],'attempt':item['attempt'],'passed':item['passed'],'program_sha256':item['program_sha256'],'response_sha256':digest(d/'response.private.json'),'checks_sha256':item['checks_sha256'],'usage_sha256':item['usage_sha256']})
    for item in state.get('export',{}).get('attempts',[]):
        d=run/'export'/f"attempt-{item['attempt']}"
        if digest(d/'workspace/output/adam/programs/export.py')!=item['program_sha256'] or digest(d/'checks.private.json')!=item['checks_sha256']:raise ValueError('Export evidence drift')
        if item['passed'] and manifest(d/'workspace')!=read(d/'workspace-manifest.json'):raise ValueError('Accepted export drift')
        checks=read(d/'checks.private.json');execution=checks.get('execution')
        if execution:sandbox_runs+=1;sandbox_failed+=int(execution['exit_code']!=0 or execution['timed_out'])
        if not checks['passed']:
            text=' '.join(checks['errors']);stages['define_xml_generation' if 'Define' in text or 'define.xml' in text else 'dataset_export']+=1
        audit.append({'dataset':'combined','node':'export','attempt':item['attempt'],'passed':item['passed'],'program_sha256':item['program_sha256'],'response_sha256':digest(d/'response.private.json'),'checks_sha256':item['checks_sha256'],'usage_sha256':item['usage_sha256']})
    usage=Counter();native=[];unknown_cache_calls=0
    for path in sorted(run.rglob('usage.json')):
        u=read(path);response=read(path.parent/'response.private.json');request=read(path.parent/'request.private.json')
        if multi:
            profile=frozen['provider_profile'];parsed=parse(profile,response)
            if profile['kind']=='gemini':system=request['systemInstruction']['parts'][0]['text'];prompt=request['contents'][0]['parts'][0]['text']
            elif profile['kind']=='chat':system=request['messages'][0]['content'];prompt=request['messages'][1]['content']
            else:system=request['instructions'];prompt=request['input']
            if parsed['model']!=profile['response_model'] or parsed['usage']!=u['usage'] or request!=body_for(profile,prompt,system) or system not in (frozen['node_system'],frozen['export_system']):raise ValueError('Native identity/settings drift')
            normalized=tokens(profile,u['usage'])
            if not (path.parent/'reused-generation.json').is_file():
                if normalized.get('cached_input') is None:unknown_cache_calls+=1
                for key,native_key in (('input_tokens','input'),('output_tokens','output'),('cache_read_input_tokens','cached_input')):
                    if normalized.get(native_key) is not None:usage[key]+=normalized.get(native_key,0)
            reason=parsed['stop_reason']
        else:
            if response.get('model')!=frozen['model'] or response.get('usage')!=u['usage'] or request['model']!=frozen['model'] or request['max_tokens']!=frozen['max_tokens'] or request['system'] not in (frozen['node_system'],frozen['export_system']):raise ValueError('Native identity/settings drift')
            for k in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens'):usage[k]+=u['usage'].get(k,0)
            reason=response.get('stop_reason')
        native.append({'receipt_sha256':digest(path),'response_sha256':digest(path.parent/'response.private.json'),'stop_reason':reason,'native_usage':u['usage'],'reused_generation':(path.parent/'reused-generation.json').is_file()})
    if unknown_cache_calls:usage['cache_read_input_tokens']=None
    e=read(run/'evaluation.private.json') or {};con=e.get('conformance') or {};correct=e.get('correctness') or {};checks={x['check']:x for x in correct.get('checks',[])}
    if (run/'final-evaluation/p21-runtime-before.json').is_file() and read(run/'final-evaluation/p21-runtime-before.json')!=frozen['p21_cache']:raise ValueError('P21 initial runtime differs from freeze')
    package=run/'final-workspace';data=package/'output/adam/datasets'
    if package.exists() and manifest(package)!=read(run/'final-workspace-manifest.json'):raise ValueError('Delivered package drift')
    expected=inventory(root/'inputs/specifications.json');domains=[];matched_total=0;delivered=0
    for ds,defs in expected.items():
        row={'dataset':ds,'generation_status':state['datasets'].get(ds,{}).get('status','blocked'),'expected_variables':len(defs),'delivered':False,'matched_variables':0,'rows':None}
        path=data/(ds.lower()+'.xpt')
        if path.is_file():
            try:
                _,meta=pyreadstat.read_xport(str(path),metadataonly=True);actual={k:'Character' if v=='string' else 'Numeric' for k,v in meta.readstat_variable_types.items()};counts=schema_counts(defs,actual);row.update(counts);row.update(delivered=True,rows=e.get('content_profile',{}).get('datasets',{}).get(ds,{}).get('rows'));delivered+=1;matched_total+=counts['matched_variables']
            except Exception as exc:row['read_error_type']=type(exc).__name__
        domains.append(row)
    if e.get('rebuild') and (e['rebuild']['exit_code'] or e['rebuild'].get('timed_out')) or e.get('rebuild_error'):stages['rebuilding']+=1
    if e and not con.get('report_usable'):stages['p21_validation']+=1
    complete=bool(e.get('deliverables_complete')) and delivered==13
    primary=con.get('dataset_rule_pairs') if complete and con.get('validation_coverage_complete') else None
    severity=Counter()
    for issue in con.get('issues',[]):severity[issue.get('severity') or 'Unassigned']+=issue.get('findings',0)
    def selected(names):
        return {n:{k:checks[n].get(k) for k in ('status','errors','assessed','coverage','qualification')} if n in checks else {'status':'unavailable','errors':None,'assessed':None} for n in names}
    coverage={n:x.get('coverage') for n,x in checks.items() if x.get('coverage') is not None}
    metrics=[
        {'workflow_completed':state['status']=='completed','complete_packages':int(complete),'planned_packages':1},
        {'semantic_reproduced':e.get('semantic_reproduced'),'byte_reproduced':e.get('byte_reproduced')},
        {'report_usable':con.get('report_usable'),'full_validated_coverage':con.get('validation_coverage_complete'),'complete_package':complete},
        {'initial':None,'final_primary_dataset_rule_pairs':primary,'observed_final_dataset_rule_pairs':con.get('dataset_rule_pairs'),'note':'One terminal evaluation; partial counts descriptive only'},
        None,dict(severity) if con.get('report_usable') else None,None,
        selected(['npi_mean_coverage','npi_mean_value']),selected(['npi_baseline_covariate']),selected(['tte_subject_coverage','tte_start_date','tte_event_status','tte_source_link','tte_event_date','tte_duration_arithmetic','tte_censor_convention']),
        {'scope':'Selected NPI summary and TTDE source expectations only','coverage':coverage or None},
        {'assessable':sum(x.get('status')=='scored' for x in checks.values()),'planned':10},
        None,dict(usage),(state['finished_unix']-state['started_unix'])/60,
        {'model_tool_calls':None,'note':'Direct per-node API; no agent tool loop. Sandbox executions shown separately, not comparable tool counts.','sandbox_executions':sandbox_runs,'failed_sandbox_executions':sandbox_failed},
        {'delivered':delivered,'expected':13,'rate':delivered/13},
        {'matched':matched_total,'expected':531,'rate':matched_total/531},
        {'observed_attempt_failure_counts':dict(stages),'blocked_datasets':[d['dataset'] for d in domains if d['generation_status'].startswith('blocked')],'provider_failures':len(list(run.rglob('provider-failure.json'))),'note':'First-failing-stage attempt counts; skipped dependents are blocked, not observed failures. P21 findings are not validator failures.'}]
    candidate=None
    if not package.exists() and state.get('export',{}).get('attempts'):
        last=state['export']['attempts'][-1];d=run/'export'/f"attempt-{last['attempt']}"
        candidate_checks=read(d/'checks.private.json');cov=candidate_checks.get('coverage',{})
        candidate={'accepted':False,'export_attempt':last['attempt'],'readable_datasets':len(cov),'expected_datasets':13,'matched_variables':sum(x['variables_matched'] for x in cov.values()),'expected_variables':531,'datasets':cov,'errors':candidate_checks['errors'],'checks_sha256':digest(d/'checks.private.json')}
    summary={'scope':'One excluded full-benchmark GxP-inspired independent architecture extension','status':state['status'],'model':frozen['model'],'provider':frozen.get('provider'),'provider_profile':frozen.get('provider_profile'),'freeze_sha256':lock['sha256'],'main_study_started':False,
        'unaccepted_terminal_candidate':candidate,
        'datasets':domains,'planned_nodes':sum(len(d['nodes']) for d in frozen['plan']),'passed_nodes':sum(n['status']=='passed' for n in state['nodes']),
        'failed_nodes':[{'dataset':n['dataset'],'node':n['node'],'status':n['status']} for n in state['nodes'] if n['status'] in ('failed','provider_failure')],
        'repaired_nodes':[{'dataset':n['dataset'],'node':n['node']} for n in state['nodes'] if n.get('accepted_attempt')==2],
        'export_status':state.get('export',{}).get('status','blocked'),'generation_responses':sum(not n['reused_generation'] for n in native),'reused_generation_receipts':sum(n['reused_generation'] for n in native),'native_usage':dict(usage),'elapsed_seconds':state['finished_unix']-state['started_unix'],'started_unix':state['started_unix'],'finished_unix':state['finished_unix'],
        'P21':{k:con.get(k) for k in ('report_usable','validation_coverage_complete','dataset_rule_pairs','finding_instances','distinct_rules','issues','failure_code','report_sha256')},
        'metrics':[{'number':i+1,'metric':name,'value':v} for i,(name,v) in enumerate(zip(METRICS,metrics))],
        'limitations':['New 73-node/13-dataset extension, not author-supplied 13-dataset DAG or numerical replication.','Single development run; not randomized matched architecture comparison or a main-study allocation.','Local repairs are not initial/final complete-workflow conditions; reduction and new-rule metrics have no defined initial P21 comparator.','Auxiliary NPI/TTE checks retain original narrow/conditional limitations; not full clinical derivation certification.','Nonempty and fixed row-universe gates are explicit architecture-adaptation contracts, not exhaustive record correctness.','Qualification/preparation and earlier failed probes are excluded from measured runtime/token totals and retained separately.']}
    if 'resume_manifest' in frozen:
        summary.update(engineering_continuation=True,original_run_summary=frozen['resume_manifest']['original_summary'],original_freeze_sha256=frozen['resume_manifest']['original_freeze_sha256'])
        first=next(iter(frozen['resume_manifest']['reuse_steps'].values()))
        states=[parent/'state.json' for parent in Path(first['directory']).parents if (parent/'state.json').is_file()]
        matching=[p for p in states if digest(p)==frozen['resume_manifest']['original_state_sha256']]
        if len(matching)!=1:raise ValueError('Cannot verify original run timing')
        original_state=read(matching[0]);summary['original_timing']={k:original_state[k] for k in ('started_unix','finished_unix')}
    if a.rebuild_diagnostics:summary['supplementary_rebuild_diagnostics']=read(a.rebuild_diagnostics)
    a.out.mkdir(parents=True,exist_ok=False);save(a.out/'summary.json',summary)
    save(a.out/'audit.json',{'freeze_sha256':lock['sha256'],'state_sha256':digest(run/'state.json'),'evaluation_sha256':digest(run/'evaluation.private.json') if e else None,'code':frozen['code'],'reused_main_code':frozen['reused_main_code'],'attempts':audit,'native_receipts':native,'report_script_sha256':digest(Path(__file__))})
    with (a.out/'metrics.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['Number','Metric','Result']);w.writerows((i+1,n,json.dumps(v,ensure_ascii=False) if v is not None else 'Not applicable / unavailable') for i,(n,v) in enumerate(zip(METRICS,metrics)))
    text='# Full-benchmark Process-DAG results\n\nIndependent GxP-Agent-inspired 13-dataset/531-variable architecture extension. One excluded exploratory run with '+frozen['model']+' via '+frozen.get('provider','Anthropic official API')+'. Status: **'+state['status']+'**. Original author software does not provide this full DAG.\n\n| Dataset | Generation status | Delivered | Rows | Variable name/type coverage |\n|---|---|---|---:|---|\n'+''.join(f"| {d['dataset']} | {d['generation_status']} | {d['delivered']} | {d['rows'] if d['rows'] is not None else 'Unavailable'} | {d['matched_variables']}/{d['expected_variables']} |\n" for d in domains)
    if candidate:
        text+='\n## Unaccepted terminal export candidate\n\nThe table above counts only accepted final-package deliverables. The final export attempt nevertheless produced '+str(candidate['readable_datasets'])+'/13 readable candidate XPT files with '+str(candidate['matched_variables'])+'/531 matching variable names and types. These files were rejected by the export gate; they were not promoted to a final package. P21, independent rebuilding and auxiliary correctness checks were not run.\n\n| Dataset | Candidate rows | Matching names/types |\n|---|---:|---:|\n'+''.join(f"| {ds} | {v['rows']} | {v['variables_matched']}/{v['expected_variables']} |\n" for ds,v in candidate['datasets'].items())
        if not multi:text+='\nThe five mismatches are character variables exported as numeric: ADAE.AEACN, ADCM.CMCLASCD, ADCM.CMINGRD, ADCM.ATC1 and ADDS.DSSCAT. All five were entirely missing in the serialized export input. The exporter chose inferred frame dtype over the specified character storage class. Earlier node checks allowed all-missing columns without enforcing their storage dtype.\n\nExport attempt 1 failed before generated code execution: Docker input copy returned unexpected EOF. Export attempt 2 executed successfully but failed schema checks. These are distinct infrastructure and export-schema failures; neither is a P21 validator failure. Frozen code and generated programs were not changed after the run.\n'
        else:text+='\nCandidate output is not an accepted final package. Export-check error categories: '+json.dumps(candidate['errors'],ensure_ascii=False).replace('|','/')+'.\n'
    text+='\n## Existing 19 metric labels\n\n| No. | Metric | Result |\n|---:|---|---|\n'+''.join('| '+str(i+1)+' | '+name+' | '+(json.dumps(v,ensure_ascii=False).replace('|','/') if v is not None else 'Not applicable / unavailable')+' |\n' for i,(name,v) in enumerate(zip(METRICS,metrics)))
    text+='\n## Interpretation\n\n'+ '\n\n'.join(summary['limitations'])+'\n\nInitial/final reduction and newly introduced rule pairs are unavailable because P21 was terminal only; no invented initial scores. Model-tool counts are unavailable because there is no OpenCode agent tool loop; sandbox execution counts are reported separately. Complete deliverables and full validated coverage are required for the primary P21 count. Selected source checks, structural coverage and P21 do not establish all clinical values correct.\n\nThe DAG uses all22 source domains and the full unchanged specification. TS read encoding is explicitly cp1252; other domains use the default, with original source bytes unchanged. A failed unstarted preparation and first failed synthetic-export probe remain retained, not discarded clinical generations. Runtime uses a non-cloud temporary directory and is archived after termination. Provider credentials and raw clinical requests/outputs remain private. Neither the formal main-study lock nor historical ADSL outcomes were modified.\n'
    if con.get('issues'):text+='\n## Terminal P21 findings\n\n| Dataset | Rule | Message | Findings | Severity |\n|---|---|---|---:|---|\n'+''.join(f"| {x['dataset']} | {x['rule']} | {x['message']} | {x['findings']} | {x.get('severity') or 'Unassigned'} |\n" for x in con['issues'])
    text+='\nFreeze SHA-256: `'+lock['sha256']+'`.\n';(a.out/'README.md').write_text(text)
    (a.out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(a.out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('metrics','limitations','datasets')},indent=2))

if __name__=='__main__':main()
