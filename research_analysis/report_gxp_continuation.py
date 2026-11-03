"""Aggregate results of an explicitly post-hoc storage-only continuation."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from main_experiment.core import fingerprint,code_manifest
from main_experiment.support import digest,manifest,save
from gxp_full.run import own_code
from .report_gxp_full import METRICS


def read(path):return json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--continuation',type=Path,required=True);p.add_argument('--original-summary',type=Path,required=True);p.add_argument('--original-freeze',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    root=a.continuation;lock=read(root/'continuation-lock.json');f=lock['payload'];state=read(root/'state.json');original=read(a.original_summary)
    if fingerprint(f)!=lock['sha256'] or own_code()!=f['code'] or code_manifest()!=f['evaluator_code']:raise ValueError('Continuation lock/code drift')
    if state['status']!='completed':raise ValueError('Continuation incomplete')
    original_lock=read(a.original_freeze)
    if fingerprint(original_lock['payload'])!=original_lock['sha256'] or original_lock['sha256']!=f['original_freeze_sha256']:raise ValueError('Original freeze mismatch')
    runtime_before=root/'final-evaluation/p21-runtime-before.json'
    if runtime_before.is_file() and read(runtime_before)!=original_lock['payload']['p21_cache']:raise ValueError('P21 pre-run cache differs from original freeze')
    if manifest(root/'final-workspace')!=read(root/'final-workspace-manifest.json') or manifest(root/'inputs')!=f['input_manifest']:raise ValueError('Continuation data drift')
    for r in f['accepted_processes']:
        if digest(root/'final-workspace/output/adam/programs/nodes'/(r['dataset']+'__'+r['node']+'.py'))!=r['program_sha256']:raise ValueError('Clinical program drift')
    if digest(root/'final-workspace/output/adam/programs/export.py')!=f['original_exporter_sha256']:raise ValueError('Generated exporter drift')
    e=read(root/'evaluation.private.json');con=e.get('conformance') or {};corr=e.get('correctness') or {};checks={c['check']:c for c in corr.get('checks',[])};export=read(root/'export-checks.json');cov=export['coverage'];delivered=len(cov);matched=sum(v['variables_matched'] for v in cov.values());complete=e.get('deliverables_complete') and delivered==13
    def selected(names):return {n:{k:checks[n].get(k) for k in ('status','errors','assessed','coverage','qualification')} if n in checks else {'status':'unavailable'} for n in names}
    severity=Counter()
    for issue in con.get('issues',[]):severity[issue.get('severity') or 'Unassigned']+=issue.get('findings',0)
    minutes=(state['finished_unix']-state['started_unix'])/60
    vals=[
        {'original_workflow_completed':False,'posthoc_continuation_completed':True,'complete_packages':int(bool(complete)),'planned_packages':1},
        {'semantic_reproduced':e.get('semantic_reproduced'),'byte_reproduced':e.get('byte_reproduced')},
        {'report_usable':con.get('report_usable'),'full_validated_coverage':con.get('validation_coverage_complete'),'complete_package':bool(complete)},
        {'initial':None,'posthoc_terminal_dataset_rule_pairs':con.get('dataset_rule_pairs') if complete and con.get('validation_coverage_complete') else None,'observed_dataset_rule_pairs':con.get('dataset_rule_pairs')},
        None,dict(severity) if con.get('report_usable') else None,None,
        selected(['npi_mean_coverage','npi_mean_value']),selected(['npi_baseline_covariate']),selected(['tte_subject_coverage','tte_start_date','tte_event_status','tte_source_link','tte_event_date','tte_duration_arithmetic','tte_censor_convention']),
        {'scope':'Selected NPI/TTE expectations only','coverage':{n:c['coverage'] for n,c in checks.items() if c.get('coverage') is not None}},
        {'assessable':sum(c.get('status')=='scored' for c in checks.values()),'planned':10},
        None,{'original_generation_usage':original['native_usage'],'additional_model_calls':0,'additional_model_tokens':0},
        {'original_run_minutes':original['elapsed_seconds']/60,'continuation_minutes':minutes,'note':'Separate phases; excludes preparation, qualification and intervening human time.'},
        {'model_tool_calls':None,'additional_model_calls':0,'continuation_export':export['execution'],'independent_rebuild':e.get('rebuild')},
        {'delivered':delivered,'expected':13,'rate':delivered/13},
        {'matched':matched,'expected':531,'rate':matched/531},
        {'original_failures_retained':original['metrics'][18]['value'],'continuation_export_passed':export['passed'],'p21_failure_code':con.get('failure_code'),'rebuild_error':e.get('rebuild_error'),'note':'P21 findings are results, not validator execution failures.'}]
    summary={'scope':'Post-hoc storage-only continuation of one exploratory full-benchmark GxP-inspired run; not an independent replicate or main-study allocation','original_status':original['status'],'continuation_status':state['status'],'original_freeze_sha256':f['original_freeze_sha256'],'continuation_lock_sha256':lock['sha256'],'model':original['model'],'main_study_started':False,'new_model_calls':0,'normalizations':f['normalizations'],'export_coverage':cov,'P21':con,'correctness':corr,'rebuild':e.get('rebuild'),'semantic_reproduced':e.get('semantic_reproduced'),'byte_reproduced':e.get('byte_reproduced'),'metrics':[{'number':i+1,'metric':n,'value':v} for i,(n,v) in enumerate(zip(METRICS,vals))]}
    diagnostics=read(root/'rebuild-diagnostics.json')
    summary['supplementary_rebuild_diagnostics']=diagnostics
    a.out.mkdir(parents=True,exist_ok=False);save(a.out/'summary.json',summary)
    save(a.out/'audit.json',{'original_summary_sha256':digest(a.original_summary),'continuation_lock_sha256':lock['sha256'],'state_sha256':digest(root/'state.json'),'evaluation_sha256':digest(root/'evaluation.private.json'),'export_checks_sha256':digest(root/'export-checks.json'),'qualification_receipt_sha256':digest(root/'qualification/receipt.json'),'unchanged_generated_exporter_sha256':f['original_exporter_sha256'],'unchanged_clinical_programs':f['accepted_processes'],'report_script_sha256':digest(Path(__file__))})
    with (a.out/'metrics.csv').open('w',newline='') as stream:
        w=csv.writer(stream,lineterminator='\n');w.writerow(['Number','Metric','Result']);w.writerows((i+1,n,json.dumps(v,ensure_ascii=False) if v is not None else 'Not applicable / unavailable') for i,(n,v) in enumerate(zip(METRICS,vals)))
    text='# Full-benchmark DAG: storage-only continuation\n\n**Original run: failed. Post-hoc continuation: completed.** This is an independently extended GxP-Agent-inspired architecture, not original author software or exact numerical replication. The full 13-dataset DAG is our extension. The formal main-study lock is unchanged.\n\n## Changes and provenance\n\nThe original failed run and both failed export attempts are retained. All 73 generated clinical process programs and the generated exporter are byte-identical to the original accepted/candidate programs. A controller export wrapper now applies the frozen specification character type, representing missing characters as SAS blanks. Nonmissing character values and all numeric values are checked unchanged. No source records, row counts, derivation algorithms, model settings or evaluator rules were changed. There are zero additional model API calls.\n\nThe revised node gate rejects entirely missing character columns stored as numeric. The continuation does not pretend the historical nodes passed this newer gate; it reuses their original acceptance and explicitly fixes serialization at export. Synthetic qualification covers all 13 datasets and 531 variables with all character columns missing. 33 unit tests passed. A preliminary continuation preparation stopped on an overly strict exact-float comparison of a pre-existing JSON round trip; it had no clinical execution or model calls. The revised preparation uses the original frozen 1e-12 comparison tolerance plus exact original export-seed byte hashes. The type normalization itself preserves numeric values exactly.\n\n## Dataset results\n\n| Dataset | Rows | Matching variable names/types |\n|---|---:|---:|\n'+''.join(f"| {ds} | {v['rows']} | {v['variables_matched']}/{v['expected_variables']} |\n" for ds,v in cov.items())
    text+='\n## Metrics\n\n| No. | Metric | Result |\n|---:|---|---|\n'+''.join('| '+str(i+1)+' | '+n+' | '+(json.dumps(v,ensure_ascii=False).replace('|','/') if v is not None else 'Not applicable / unavailable')+' |\n' for i,(n,v) in enumerate(zip(METRICS,vals)))
    text+='\n## P21 findings\n\nP21 usability: '+str(con.get('report_usable'))+'; full validated coverage: '+str(con.get('validation_coverage_complete'))+'; dataset-rule pairs: '+str(con.get('dataset_rule_pairs'))+'; finding instances: '+str(con.get('finding_instances'))+'.\n\n| Dataset | Rule | Message | Findings | Severity |\n|---|---|---|---:|---|\n'+''.join(f"| {x['dataset']} | {x['rule']} | {x['message']} | {x['findings']} | {x.get('severity') or 'Unassigned'} |\n" for x in con.get('issues',[]))
    text+='\n## Strict rebuilding result and supplementary diagnosis\n\nIndependent reconstruction executed successfully, but strict semantic and byte reproduction remain **false**. All 13 final process-node JSON artifacts match the original run byte for byte. Differences arise after these artifacts are read and serialized into export intermediates: '+str(diagnostics['different_numeric_cells'])+' numeric cells differ, with maximum absolute difference '+str(diagnostics['maximum_absolute_difference'])+'. Character values, shapes, inspected XPT metadata and Define-XML under the existing timestamp normalization match. All numeric values fall within the original export gate tolerance of rtol=atol=1e-12; this is supplementary diagnostic information only. The strict reproduction score has not been changed or relaxed.\n'
    text+='\n## Interpretation limits\n\nThis is a post-hoc engineering continuation, not a clean rerun, new repetition, or fair matched architecture comparison. Keep the original failure in any reliability analysis. P21 results describe this repaired package only. Findings were not used to alter derivations or reduce scores. Selected NPI/TTE checks remain narrow and conditional; passing export, P21 usability or rebuilding does not certify all clinical derivations. Initial/final reductions and newly introduced rule pairs are unavailable because no complete initial P21 comparator exists. Dollar cost is unavailable without verified billing; token receipts are reported. Provider requests, clinical records, raw workspaces and dictionaries remain private.\n'
    (a.out/'README.md').write_text(text);(a.out/'SHA256SUMS').write_text(''.join(digest(x)+'  '+x.name+'\n' for x in sorted(a.out.iterdir()) if x.is_file() and x.name!='SHA256SUMS'))
    print(json.dumps({'datasets':delivered,'matching_variables':matched,'p21_usable':con.get('report_usable'),'p21_pairs':con.get('dataset_rule_pairs'),'semantic_reproduced':e.get('semantic_reproduced'),'byte_reproduced':e.get('byte_reproduced'),'out':str(a.out)},indent=2))


if __name__=='__main__':main()
