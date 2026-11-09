"""Append new attempts to both historical architecture tables, never replace failures."""
import argparse
import copy
import csv
import json
from pathlib import Path
import shutil
from main_experiment.support import save,digest
from research_analysis.report_gxp_full import METRICS
from research_analysis.publish_gxp_models import display as gxp_display
from research_analysis.publish_ai431_full import display as ai_display


def display(number,value,record):
    if record.get('context_window_incompatible') and number in (1,19):return 'HTTP400 context_length_exceeded: 159,397 input tokens; limit 131,072; no generated node'
    if number==14 and not value:return 'Unavailable: no native usage receipt'
    if number==4 and value and value.get('final_primary_dataset_rule_pairs') is None and value.get('observed_final_dataset_rule_pairs') is not None:
        return 'Primary unavailable; partial observed '+str(value['observed_final_dataset_rule_pairs'])
    if number==14 and value is not None:
        u=value.get('total_observed_usage',value.get('original_generation_usage',value))
        if u.get('cache_read_input_tokens') is None:return 'Input '+format(u['input_tokens'],',')+'; output '+format(u['output_tokens'],',')+'; cached input unavailable'
    return (ai_display if record['architecture_group']=='ai431' else gxp_display)(number,value,record)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    state=json.loads((a.batch/'state.json').read_text());plan=json.loads((a.batch/'plan.json').read_text())
    if state['status']!='completed':raise ValueError('Do not present unfinished attempts as complete')
    repo=Path(__file__).resolve().parents[1];records=[];sources=[]
    for architecture,folder in [('gxp','gxp-model-comparison-2026-11-02'),('ai431','ai431-full-models-2026-11-05')]:
        source=repo/'pre_experiment/results'/folder/'comparison.json';original=json.loads(source.read_text());sources.append({'path':str(source.relative_to(repo)),'sha256':digest(source)})
        for item in original['records']:
            r=copy.deepcopy(item);r.update(id=architecture+'_historical_'+r['id'],architecture_group=architecture,attempt_cohort='Historical retained outcome',historical_source=str(source.relative_to(repo)))
            records.append(r)
    labels={'ai431_gemini_retry':'Gemini 3.1 Pro Preview — Google official; credit-refill rerun Nov 8','ai431_openai_official':'GPT-6.1 Sol — OpenAI official; Nov 8','gxp_openai_official':'GPT-6.1 Sol — OpenAI official; fresh Nov 8','gxp_gpt_oss_20b':'gpt-oss-20b — DeepInfra; fresh Nov 8'}
    a.out.mkdir(parents=True,exist_ok=False);audits={}
    for item in plan['attempts']:
        key=item['id'];source=a.batch/'aggregates'/key;root=Path(item['root']);r=json.loads((source/'summary.json').read_text());r.update(id=key,label=labels[key],architecture_group=item['architecture'],attempt_cohort='New requested follow-up 2026-11-08')
        if key=='gxp_gpt_oss_20b':
            adjudication=json.loads((source/'failure-adjudication.json').read_text())
            if adjudication.get('provider_error_code')!='context_length_exceeded':raise ValueError('Unexpected context adjudication')
            r['context_window_incompatible']=True;r['clinical_api_request_attempts']=1;r['metrics'][13]['value']=None
            r['usage_interpretation']='No successful native response; billed usage is unknown, not zero'
        if r.get('unaccepted_terminal_candidate',{}):
            candidate=r['unaccepted_terminal_candidate']
            if candidate.get('errors'):candidate['errors']=['Detailed rejected-export diagnostics retained privately']
        if len(r['metrics'])!=19 or [m['metric'] for m in r['metrics']]!=METRICS:raise ValueError('Metric mismatch')
        target=a.out/key;target.mkdir();save(target/'summary.json',r);shutil.copy2(source/'audit.json',target/'audit.json')
        for name in ['timing-receipt.json','failure-adjudication.json','merge-failure-adjudication.json']:
            if (source/name).is_file():shutil.copy2(source/name,target/name)
        receipt=json.loads((root/'archive-receipt.json').read_text())
        if not receipt['verified_lossless'] or digest(root/'run-evidence.tar.gz')!=receipt['sha256']:raise ValueError('Evidence archive mismatch')
        audits[key]={'freeze_sha256':r['freeze_sha256'],'summary_sha256':digest(source/'summary.json'),'audit_sha256':digest(source/'audit.json'),'private_archive_sha256':receipt['sha256']};records.append(r)
    rows=[[i+1,name]+[display(i+1,r['metrics'][i]['value'],r) for r in records] for i,name in enumerate(METRICS)]
    headers=['No.','Metric']+[r['architecture_group'].upper()+' / '+r['label'] for r in records]
    save(a.out/'comparison.json',{'scope':'Both independently adapted architectures: historical attempts plus four requested follow-ups; not matched model or architecture controls','main_study_started':False,'comparison_complete':True,'records':records,'table_headers':headers,'table_rows':rows})
    with (a.out/'comparison.csv').open('w',newline='') as f:w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
    text='# GxP and AI-431: retained historical results and November 8 follow-ups\n\n[Excel workbook](comparison.xlsx) · [Unified 19-metric CSV](comparison.csv) · [All metric components](comparison.json). Historical failures and gateway 403 endpoints remain separate; official OpenAI results never replace or authenticate the gateway. These are nonrandomized exploratory attempts, excluded from the formal main study.\n\n'
    for architecture in ('gxp','ai431'):
        selected=[r for r in records if r['architecture_group']==architecture];text+='## '+architecture.upper()+' — all attempts\n\n| No. | Metric | '+' | '.join(r['label'] for r in selected)+' |\n|---:|---|'+''.join('---|' for _ in selected)+'\n'
        for i,name in enumerate(METRICS):text+='| '+str(i+1)+' | '+name+' | '+' | '.join(display(i+1,r['metrics'][i]['value'],r).replace('|','/').replace('\n',' ') for r in selected)+' |\n'
        text+='\n'
    text+='## New follow-up outcomes\n\n- Gemini AI-431: 46/49 ADSL variable tasks passed; AVGDD, CUMDOSE and COMP16FL exhausted two attempts. No API credit failure occurred in this rerun.\n- Official OpenAI AI-431: 48 variable tasks passed; RFSTDTC ended with a single transport TimeoutError after about 308 seconds. The key worked; this is not evidence of credit exhaustion. No automatic retry of that uncertain request.\n- Official OpenAI GxP: 72/73 nodes passed, ADCM.validate failed, and 12/13 datasets were exported with 494/531 variable-name/type coverage. P21 produced 25 observed dataset-rule pairs for the partial package; full validation coverage and the primary complete-package score are unavailable. Semantic and byte reconstruction both failed.\n- DeepInfra gpt-oss-20b GxP: the first clinical request was rejected with HTTP400 context_length_exceeded (159,397 input tokens versus a 131,072 limit). This is not a credit failure. No node program or native usage receipt was returned. Prompt truncation or context filtering would be a separate version, not a silent repair.\n\n'
    text+='## Interpretation and provenance\n\nGemini AI-431 was explicitly rerun after API credit refill; its prior failed result remains in the table. It uses the same original frozen experimental implementation in a new root. The other three attempts use new provider-profile pins: official api.openai.com Responses for Sol and DeepInfra for gpt-oss-20b. New GxP attempts start from zero using the previously qualified nullable-character serialization boundary; no historical programs, responses or clinical outputs are reused. They differ from the historical original GxP code version and the historical Claude/DeepSeek engineering continuations. This is not a balanced or causal architecture comparison.\n\nAll attempts target the same 13 datasets/531 variables and use frozen inputs, original architecture prompts/QC, provider-default sampling, 32768 output/reasoning cap, two local attempts and original terminal P21/rebuild/auxiliary checks. AI-431 has three variable workers; GxP has two dataset branches. No web tools, credentials or network are available to generated code. No manual clinical repairs or automatic transport retries. P21 is never repair feedback. Missing results are not zero; partial outputs do not establish a full-coverage primary P21 score. Dollar costs remain unavailable without verified billing. Native output includes reasoning where reported; unknown cached usage stays unavailable.\n\nFull clinical requests, outputs, programs and every failure remain private in verified lossless archives. Published records contain aggregates/code/hashes only. Follow-up-specific status, timing, token counts and failures are in each new summary; the original tables and original frozen evidence remain unchanged.\n'
    (a.out/'README.md').write_text(text)
    save(a.out/'publication-audit.json',{'historical_sources':sources,'new_attempts':audits,'batch_plan_sha256':digest(a.batch/'plan.json'),'batch_state_sha256':digest(a.batch/'state.json'),'publisher_sha256':digest(Path(__file__)),'raw_clinical_artifacts_published':False,'original_outcomes_retained':True})
    print('Published',len(records),'retained endpoints and all 19 metrics')

if __name__=='__main__':main()
