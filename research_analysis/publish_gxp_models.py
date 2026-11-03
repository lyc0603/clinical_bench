"""Publish reviewed aggregates only; one 19-row table, no clinical artifacts."""
import argparse
import copy
import csv
import json
from pathlib import Path
import shutil
from main_experiment.support import save,digest
from .report_gxp_full import METRICS


def read(p):return json.loads(p.read_text())


def display(number,value,record):
    if record.get('not_started'):return 'Not started: readiness HTTP 403' if number in (1,19) else 'Unavailable'
    if value is None:return 'Not applicable / unavailable'
    if number==1:
        if record.get('engineering_continuation'):return 'Original controller-blocked; continuation '+record['status']
        return 'Original failed; post-hoc continuation completed' if record.get('historical') else record['status']
    if number==2:return 'Unavailable' if value.get('semantic_reproduced') is None else 'Semantic '+str(value.get('semantic_reproduced'))+'; bytes '+str(value.get('byte_reproduced'))
    if number==3:return 'Unavailable' if value.get('report_usable') is None else 'Usable '+str(value.get('report_usable'))+'; full coverage '+str(value.get('full_validated_coverage'))
    if number==4:
        x=value.get('posthoc_terminal_dataset_rule_pairs',value.get('final_primary_dataset_rule_pairs'))
        return str(x) if x is not None else 'Unavailable'
    if number in (8,9,10):
        return '; '.join(n.replace('npi_','').replace('tte_','')+': '+(str(v.get('errors'))+'/'+str(v.get('assessed')) if v.get('status')=='scored' else 'unavailable') for n,v in value.items())
    if number==11:
        coverage=value.get('coverage') or {}
        return '; '.join(('NPI' if n.startswith('npi') else 'TTE')+' missing/extra/duplicates '+str(v.get('missing'))+'/'+str(v.get('extra'))+'/'+str(v.get('duplicates')) for n,v in coverage.items()) or 'Unavailable'
    if number==12:return str(value['assessable'])+'/'+str(value['planned'])
    if number==14:
        u=value.get('total_observed_usage',value.get('original_generation_usage',value))
        return 'Input '+format(u.get('input_tokens',0),',')+'; output '+format(u.get('output_tokens',0),',')+'; cached input '+format(u.get('cache_read_input_tokens',0),',')
    if number==15:
        if isinstance(value,dict):
            prefix=f"Overall {value['overall_including_engineering_gaps_minutes']:.2f}; " if 'overall_including_engineering_gaps_minutes' in value else ''
            return prefix+f"Original {value['original_run_minutes']:.2f}; continuation {value['continuation_minutes']:.2f}"
        return f'{value:.2f}'
    if number==16:return 'Model tool calls N/A; '+str(record.get('generation_responses','unavailable'))+' recorded API responses'
    if number==17:return str(value['delivered'])+'/'+str(value['expected'])
    if number==18:return str(value['matched'])+'/'+str(value['expected'])
    if number==19:
        if record.get('historical'):return 'Original export failed; storage-only continuation completed; strict reproduction false'
        if record.get('engineering_continuation'):return 'Original controller null-character failure; continuation stopped at ADQSADAS: output/reasoning cap (length)'
        counts=value.get('observed_attempt_failure_counts',{})
        return ', '.join(k+'='+str(v) for k,v in counts.items() if v)+'; blocked datasets='+str(len(value.get('blocked_datasets',[])))+'; provider failures='+str(value.get('provider_failures',0))
    return json.dumps(value,ensure_ascii=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',type=Path,required=True);p.add_argument('--claude',type=Path,required=True);p.add_argument('--readiness',type=Path,required=True);p.add_argument('--deepseek-continuation',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    batch=read(a.batch/'state.json')
    if batch['status']!='completed':raise ValueError('Do not publish an unfinished batch')
    a.out.mkdir(parents=True,exist_ok=False);records=[]
    for name,label,source in [('claude','Claude Sonnet 5.5 — historical continuation',a.claude),('gemini','Gemini 3.1 Pro Preview — Google official',a.batch/'gemini'),('deepseek','DeepSeek Flash — DeepSeek official',a.deepseek_continuation or a.batch/'deepseek')]:
        record=copy.deepcopy(read(source/'summary.json'));record.update(id=name,label=label,historical=name=='claude')
        if len(record['metrics'])!=19 or [m['number'] for m in record['metrics']]!=list(range(1,20)):raise ValueError('Missing metric')
        # Candidate execution errors may include printed records; retain only
        # error categories in public output. Full evidence stays private.
        candidate=record.get('unaccepted_terminal_candidate')
        if candidate and candidate.get('errors'):candidate['errors']=['Detailed rejected-export diagnostics retained privately']
        if name=='claude':record['generation_responses']=76
        if record.get('engineering_continuation'):
            original=record['original_run_summary'];record['label']+=' — engineering continuation'
            record['metrics'][0]['value'].update(original_workflow_completed=False,posthoc_continuation=True)
            new_usage=record['native_usage'];old_usage=original['native_usage'];combined={k:new_usage.get(k,0)+old_usage.get(k,0) for k in new_usage.keys()|old_usage.keys()}
            record['metrics'][13]['value']={'original_generation_usage':old_usage,'continuation_new_usage':new_usage,'total_observed_usage':combined,'reused_receipts_excluded_from_new_tokens':True}
            record['metrics'][14]['value']={'original_run_minutes':original['elapsed_seconds']/60,'continuation_minutes':record['elapsed_seconds']/60,'note':'Separate phases, not a clean end-to-end repetition'}
            if record.get('original_timing'):
                record['metrics'][14]['value'].update(overall_including_engineering_gaps_minutes=(record['finished_unix']-record['original_timing']['started_unix'])/60,note='Overall includes intervening human engineering, preparation and diagnostics. Phase timings do not. Not comparable clean-run latency.')
            record['generation_responses']+=original['generation_responses']
        records.append(record);target=a.out/name;target.mkdir();save(target/'summary.json',record);shutil.copy2(source/'audit.json',target/'audit.json')
        if name=='deepseek':
            adjudication=a.batch/'deepseek/controller-failure-adjudication.json'
            if adjudication.exists():shutil.copy2(adjudication,target/adjudication.name)
            if a.deepseek_continuation:save(target/'original-run-summary.json',read(a.batch/'deepseek/summary.json'))
        if name=='gemini' and (a.batch/'gemini/input-failure-adjudication.json').is_file():shutil.copy2(a.batch/'gemini/input-failure-adjudication.json',target/'input-failure-adjudication.json')
    readiness=read(a.readiness);gateway=next(c for c in readiness['checks'] if c['profile']['id']=='gateway_sol')
    if gateway['qualified'] or gateway.get('http_status')!=403:raise ValueError('Gateway planned-status adjudication needs review')
    blocked={'id':'gateway_sol','label':'Gateway-claimed Sol 6.1 — unverified upstream','not_started':True,'status':'readiness_failed_http_403','provider':gateway['profile']['provider'],'requested_model':gateway['profile']['model'],'returned_model':None,'clinical_inputs_transmitted':False,'upstream_identity_independently_verified':False,'metrics':[{'number':i+1,'metric':n,'value':None} for i,n in enumerate(METRICS)]};records.append(blocked)
    rows=[]
    for i,name in enumerate(METRICS):rows.append([i+1,name]+[display(i+1,r['metrics'][i]['value'],r) for r in records])
    headers=['No.','Metric']+[r['label'] for r in records]
    with (a.out/'comparison.csv').open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(headers);writer.writerows(rows)
    save(a.out/'comparison.json',{'scope':'Single exploratory full-DAG attempts; historical Claude continuation is a reference, not matched control','main_study_started':False,'planned_new_models':3,'started_new_models':2,'readiness_failed_models':1,'table_headers':headers,'table_rows':rows,'records':records})
    save(a.out/'publication-audit.json',{'batch_plan_sha256':digest(a.batch/'plan.json'),'batch_state_sha256':digest(a.batch/'state.json'),'readiness_sha256':digest(a.readiness),'source_summary_sha256':{k:digest(v/'summary.json') for k,v in [('claude',a.claude),('gemini',a.batch/'gemini'),('deepseek_original',a.batch/'deepseek'),('deepseek_reported',a.deepseek_continuation or a.batch/'deepseek')]},'publisher_sha256':digest(Path(__file__)),'raw_clinical_files_published':False})
    text='# Full-benchmark GxP-inspired model comparison\n\nOne new full-DAG exploratory attempt was planned for each of Gemini, DeepSeek and gateway-claimed Sol. Gemini and DeepSeek passed nonclinical readiness and were started once; the gateway returned HTTP 403 before clinical generation. No substitute model was selected. Gemini failed during ADSL merge because generated code used a wrong source path or nonexistent JSON field. DeepSeek was blocked by the controller character-storage boundary: its explicit object character container became numeric after JSON read, confirmed by a synthetic reproduction. Its original failure is retained and must not be interpreted as a model clinical-value error. '
    if a.deepseek_continuation:text+='The separately labelled DeepSeek engineering continuation reexecutes six unedited historical node programs under a nullable-character boundary fix before generating remaining nodes; reused receipts do not incur new model calls and are not double-counted. The continuation passed 27/73 nodes, then ADQSADAS record_universe returned length at 32,768 completion tokens (30,682 reasoning tokens); the incomplete response was rejected and remaining scheduling stopped. No final export or P21 evaluation occurred. '
    text+='The historical Claude failed-and-continued case is a separate reference. This is not a randomized matched experiment or a formal main-study repetition.\n\n## All 19 metric labels\n\n'
    text+='| '+' | '.join(headers)+' |\n|---:|---|---|---|---|---|\n'+''.join('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |\n' for row in rows)
    text+='\nDetailed machine-readable values: [comparison.json](comparison.json). Spreadsheet-compatible table: [comparison.csv](comparison.csv). Per-model evidence summaries: [Claude](claude/summary.json), [Gemini](gemini/summary.json), [DeepSeek](deepseek/summary.json).\n\n## Design and interpretation\n\nThe original Gemini and DeepSeek attempts use the same repaired 73-process-node DAG; the DeepSeek continuation adds the documented nullable-character controller fix. All target all 13 datasets/531 variables, full specification context, provider-default temperature/reasoning, output/reasoning cap32768, two local attempts per node/export, and at most two concurrent dataset branches. Models run serially in Gemini → DeepSeek order. No web tools are supplied; generated Python executes offline in the same pinned Docker image. P21 is terminal only and never feeds repairs. Full inputs, clinical programs and results are not shared across new models.\n\nThe historical Claude run used the earlier all-missing-character gate and then an explicitly post-hoc export-storage continuation. Its original failure stays in the record; it is not a clean same-version control. Hosted aliases and provider defaults do not establish fixed or equal weights/sampling. The third-party gateway model string would not authenticate an official OpenAI upstream even if available.\n\nUnavailable metrics are not zero. A partial package cannot provide the primary complete-coverage P21 score. Candidate export coverage is descriptive and separate from accepted final delivery. There is no complete initial P21 comparator, so reduction and newly introduced rule pairs are N/A. Native token receipts include thinking where reported; cached input is a subset of input, not an additional token total. Dollar cost is unavailable without verified billing/rates. Model tool counts are N/A for these direct API calls; sandbox counts remain in detailed records.\n\nAuxiliary checks cover selected NPI/TTE expectations only and cannot certify all clinical derivations. P21 findings, a validator execution failure, model code failure and provider readiness failure are different outcomes. Strict semantic/byte reproduction scores are retained even for tiny floating serialization differences; no tolerance relaxation is used to improve a score. Single attempts do not support superiority or causal claims.\n\n## Reproduction and privacy\n\nSee [provider runner](../../../gxp_models/README.md), [architecture](../../../gxp_full/README.md), [engineering continuation](../../../gxp_recovery/README.md) and [original ADSL adaptation](../../../gxp_adsl/README.md). All failed attempts, source/runtime pins, native responses and usage receipts remain in private, lossless hash-verified evidence archives. The repository contains code and aggregate measurements only; no credentials, patient records, raw model requests, SDTM/ADaM files or dictionaries are published. The formal main-study lock is unchanged.\n'
    (a.out/'README.md').write_text(text)
    (a.out/'SHA256SUMS').write_text(''.join(digest(x)+'  '+str(x.relative_to(a.out))+'\n' for x in sorted(a.out.rglob('*')) if x.is_file() and x.name!='SHA256SUMS'))
    print('Published aggregate table:',a.out)


if __name__=='__main__':main()
