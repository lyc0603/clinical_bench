"""Single five-endpoint table, including readiness failures; aggregates only."""
import argparse
import copy
import csv
import json
from pathlib import Path
import shutil
from main_experiment.support import save,digest
from research_analysis.report_gxp_full import METRICS
from research_analysis.publish_gxp_models import display as existing_display

LABELS={'claude':'Claude Sonnet 5.5 — Anthropic official','gemini':'Gemini 3.1 Pro Preview — Google official','deepseek':'DeepSeek Flash — DeepSeek official','gateway_sol':'Gateway-claimed Sol 6.1 — unverified upstream','gpt_oss_20b':'gpt-oss-20b — DeepInfra'}

def read(path):return json.loads(Path(path).read_text())

def display(number,value,record):
    if record.get('not_started'):return 'Not started: '+record['status'] if number in (1,19) else 'Unavailable'
    if number==1:return record['status']+'; variables '+str(record['passed_variable_tasks'])+'/531'
    if number==19:
        if value is None:return 'Unavailable'
        failures=value['observed_attempt_failure_counts']
        return '; '.join(k+'='+str(v) for k,v in failures.items() if v)+f"; failed variables={value['failed_variable_tasks']}; failed row tasks={value['failed_row_universe_tasks']}; merge QC={value['failed_merge_qc_datasets']}; blocked datasets={len(value['blocked_datasets'])}; API failures={value['provider_http_or_transport_failures']}; incomplete/invalid replies={value['invalid_completion_calls']}"
    return existing_display(number,value,record)

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',type=Path,required=True);p.add_argument('--summaries',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-prelaunch-pending',action='store_true');a=p.parse_args()
    state=read(a.batch/'state.json');plan=read(a.batch/'plan.json');readiness=read(a.batch/'readiness/readiness.json')
    pending=[name for name,r in state['models'].items() if r['status']=='prelaunch_failure']
    if state['status'] not in (('completed','blocked_prelaunch') if a.allow_prelaunch_pending else ('completed',)) or pending and not a.allow_prelaunch_pending:raise ValueError('Do not publish unfinished batch as final; explicitly label pending prelaunch results')
    a.out.mkdir(parents=True,exist_ok=False);records=[];audits={}
    for name in plan['planned']:
        receipt=next(r for r in readiness['checks'] if r['profile']['id']==name)
        if not receipt['qualified'] or name in pending:
            if name in pending:
                root=Path(state['models'][name]['root'])
                if (root/'run-location.json').exists() or (root/'run-evidence.tar.gz').exists():raise ValueError('Pending model has a clinical start')
            record={'id':name,'label':LABELS[name],'not_started':True,'status':'disk_space_prelaunch_pending' if name in pending else 'readiness_http_'+str(receipt.get('http_status')),'provider':receipt['profile']['provider'],'model':receipt['profile']['model'],'clinical_inputs_transmitted':False,'main_study_started':False,'metrics':[{'number':i+1,'metric':label,'value':None} for i,label in enumerate(METRICS)]}
        else:
            source=a.summaries/name;record=copy.deepcopy(read(source/'summary.json'));record.update(id=name,label=LABELS[name]);target=a.out/name;target.mkdir()
            if len(record['metrics'])!=19 or [m['metric'] for m in record['metrics']]!=METRICS:raise ValueError('Metric labels differ')
            save(target/'summary.json',record);shutil.copy2(source/'audit.json',target/'audit.json');audits[name]={'summary_sha256':digest(source/'summary.json'),'audit_sha256':digest(source/'audit.json')}
            if (source/'merge-failure-adjudication.json').exists():shutil.copy2(source/'merge-failure-adjudication.json',target/'merge-failure-adjudication.json')
        records.append(record)
    rows=[[i+1,label]+[display(i+1,r['metrics'][i]['value'],r) for r in records] for i,label in enumerate(METRICS)];headers=['No.','Metric']+[r['label'] for r in records]
    save(a.out/'comparison.json',{'scope':'Five planned exploratory AI-431-inspired full-benchmark endpoints; no numerical reproduction or formal main study','interim_pending_models':pending,'comparison_complete':not pending,'main_study_started':False,'table_headers':headers,'table_rows':rows,'records':records})
    with (a.out/'comparison.csv').open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(headers);writer.writerows(rows)
    save(a.out/'readiness.json',readiness)
    save(a.out/'publication-audit.json',{'batch_plan_sha256':digest(a.batch/'plan.json'),'batch_state_sha256':digest(a.batch/'state.json'),'readiness_sha256':digest(a.batch/'readiness/readiness.json'),'source_aggregate_hashes':audits,'publisher_sha256':digest(Path(__file__)),'raw_clinical_artifacts_published':False})
    text=('# INTERIM — execution incomplete\n\nThree qualified endpoints have not started clinically because disk space is below the frozen 10 GiB threshold. This is a progress table, not a completed five-model comparison. Do not interpret their unavailable cells as model failures or zero performance.\n\n' if pending else '')+'# Full-benchmark AI-431-inspired five-model results\n\nIndependent implementation of the [PharmaSUG 2026 AI-431 architecture](https://pharmasug.org/proceedings/2026/AI/PharmaSUG-2026-AI-431.pdf): advisory specification review, independent variable generation, sandbox execution/local repair, QC, keyed merge and terminal evaluation. All 13 datasets / 531 variables are targeted. This is not author software or numerical reproduction, and is excluded from the formal main study.\n\n[Excel workbook](comparison.xlsx) · [CSV table](comparison.csv) · [Full metric components and per-model summaries](comparison.json). Unavailable is different from zero.\n\n'
    text+='| '+' | '.join(headers)+' |\n|---:|---|---|---|---|---|---|\n'+''.join('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |\n' for row in rows)
    text+='\n## Run status and failures\n\n'
    for record in records:
        if record.get('not_started'):
            if record['status']=='disk_space_prelaunch_pending':
                text+='- '+record['label']+': **not started clinically**; qualified API, but disk preflight failed. Frozen root and original errors retained. No clinical performance metrics; first attempt still pending.\n';continue
            text+='- '+record['label']+': readiness failed with HTTP403; no clinical generation or clinical inputs transmitted. A requested/returned gateway string does not authenticate an official OpenAI upstream. No recharge or model substitution occurred.\n';continue
        text+='- '+record['label']+': **'+record['status']+'**, '+str(record['passed_variable_tasks'])+'/531 variable tasks passed; '+str(record['passed_row_universe_tasks'])+'/12 row universes passed. Native responses: '+str(record['generation_responses'])+' (including '+str(record['advisory_review_responses'])+' advisory reviews). '
        if record['failed_tasks']:text+='Failed/blocked task details: ['+record['id']+'/summary.json]('+record['id']+'/summary.json). '
        if any(d['generation_status']=='failed_merge_qc' for d in record['datasets']):text+='Merged cross-variable QC failed; downstream datasets were blocked. Passing each variable locally does not establish cross-variable consistency. '
        if (a.out/record['id']/'merge-failure-adjudication.json').is_file():text+='[Exact merge-gate adjudication]('+record['id']+'/merge-failure-adjudication.json). '
        if record['invalid_completions']:text+='Rejected completion reasons: '+', '.join(str(r['stop_reason']) for r in record['invalid_completions'])+'. '
        text+='\n'
    text+='\n## Fixed design and interpretation\n\nFour qualified endpoints use the same frozen implementation and input bytes, three concurrent independent variable tasks, serial datasets and models, provider-default sampling/reasoning, maximum32768 output/reasoning tokens and two local code/QC attempts per task/export. Model order: Claude → Gemini → DeepSeek → gpt-oss-20b. No overall repair-time budget. API300-second and sandbox1800-second timeouts protect individual operations. Provider/default/hosted alias differences prevent equal-weight or equal-sampling claims. The gateway remains a separate unverified-provenance endpoint. gpt-oss-20b is hosted by DeepInfra, not run locally.\n\nApproved clinical specifications never change. Per-dataset model reviews are advisory and not fed to workers. Variable contexts are deterministically selected from the unchanged specifications, including dependency specifications, global rules/details, relevant value-level metadata/parameter map/codelists; full specifications remain readable offline. ADSL starts with controller randomized subject keys only. Other row universes are generated by the model; scalar row helpers and stable controller row IDs align repeated-subject records. Each variable worker sees no other current-dataset worker outputs/programs and independently recomputes intermediates. Exact keys, types, lengths, ownership and selected merged consistency checks gate keyed merging. There is no exhaustive clinical derivation or row-universe oracle.\n\nFailed independent variables block that dataset merge and dependent datasets; unrelated work can continue. Provider, invalid completion or controller failures stop new requests while retaining in-flight evidence. P21 is terminal only and never repair feedback. Final accepted delivery is distinguished from individual passed variables and rejected candidates. Complete delivery plus full validated coverage is required for the primary P21 metric; partial findings are descriptive only. No complete initial package was scored, so reduction and newly introduced rule metrics are unavailable. Auxiliary NPI/TTE checks have the benchmark\'s original narrow/conditional limits. Strict semantic and byte reconstruction scores are not relaxed for small floating differences.\n\nAll observed native usage includes failed/truncated calls, reviews and local repairs. Cached input is a subset of total input; Anthropic uncached/cache-read/cache-created components are normalized explicitly. USD cost is unavailable without verified billing. Model tool-call counts are N/A for tool-free direct APIs; sandbox counts are separate. One nonrandomized exploratory attempt cannot establish model or architecture superiority. Historical GxP and ADSL results stay unchanged and are not pooled into this cohort.\n\n## Privacy and reproduction\n\nSee [implementation, adaptation limits and commands](../../../ai431_full/README.md). Generated Python runs in the pinned network-disabled Docker image, without credentials, references, evaluator or other-run access. Full native requests/responses, clinical files/programs and every failure remain in private lossless archives with per-file stream-hash verification. Only aggregates, code and hashes are published. The formal main-study lock is unchanged.\n'
    (a.out/'README.md').write_text('\n'.join(line.rstrip() for line in text.splitlines())+'\n')
    (a.out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(a.out))+'\n' for p in sorted(a.out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    print('Published five planned endpoints / 19 metrics:',a.out)

if __name__=='__main__':main()
