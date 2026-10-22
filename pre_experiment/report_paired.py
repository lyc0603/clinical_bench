"""Offline 16-metric table for new paired endpoints and historical P21 feedback."""
import argparse
import csv
import json
from pathlib import Path

from main_experiment.support import digest
from pre_experiment.report_metrics import METRICS, collect, flag, read, token_text


def initial_only(directory, model):
    r = collect(directory, model, 'initial_only')
    receipt = read(directory/'initial-only.json') or {}
    e = read(directory/'initial/evaluation.json') or {}
    c = e.get('conformance') or {}
    n = r['numeric']['initial']
    complete = receipt.get('status') == 'completed'
    r['status'] = 'completed' if complete else r['status'] if r['status'] != 'completed' else 'unavailable'
    r['values'][0] = (f'Status {r["status"]}; initial-only completed {int(complete)}/1; '
                      f'terminal 13 readable datasets {flag(n["readable_dataset_package"])}; '
                      f'file set {flag(n["dataset_set_complete"])}; required deliverables {flag(n["deliverables_complete"])}')
    r['values'][1] = f'Semantic {flag(n["semantic_reproduced"])}; exact bytes {flag(n["byte_reproduced"])}'
    datasets = c.get('validated_datasets')
    r['values'][2] = (f'Usable {flag(c.get("report_usable"))}; full coverage {c.get("validation_coverage_complete", "Unavailable")}; '
                      f'validated {str(len(datasets))+"/13" if datasets is not None else "Unavailable"}')
    if c.get('reason'):r['values'][2] += '; reason: '+c['reason']
    def value(key):return c.get(key) if c.get(key) is not None else 'Unavailable'
    r['values'][3] = f'Initial/terminal: pairs {value("dataset_rule_pairs")}, instances {value("finding_instances")}, distinct rules {value("distinct_rules")}; repair not applicable'
    r['unqualified_report_observations'] = [x for x in r['unqualified_report_observations'] if x['phase']=='initial']
    for x in r['unqualified_report_observations']:
        if 'dataset_rule_pairs' in x:
            r['values'][3] += f'\nUnqualified observed initial: {x["dataset_rule_pairs"]} pairs, {x["finding_instances"]} instances, {x["distinct_rules"]} distinct rules (not scored)'
    r['values'][4] = r['values'][6] = 'Not applicable: no repair phase'
    r['values'][5] = '; '.join(f'{key}: {count} pairs' for key,count in (n['severity_pairs'] or {}).items()) if n['severity_pairs'] is not None else 'Unavailable; no usable report'
    for index in (7,8,9,11):r['values'][index] = r['values'][index].split('; Final:',1)[0]
    r['values'][10] = '; '.join(x for x in r['values'][10].split('; ') if x.startswith('Initial '))
    cost=n['cost_estimate_usd']
    r['values'][12] = f'Generation ${cost:.4f}; repair not applicable; terminal cost ${cost:.4f} (estimate, not invoice)' if cost is not None else 'Unavailable; repair not applicable'
    if n['tokens']:
        t=n['tokens'];r['values'][13]=token_text('Generation',{'input':t['input'],'output':t['output'],'reasoning':t['reasoning'],'cache_read':t['cache_read'],'cache_write':t['cache_write']})+'; repair not applicable'
    else:r['values'][13]='Unavailable; repair not applicable'
    seconds=receipt.get('finished_unix',0)-receipt.get('started_unix',0) if complete else None
    r['values'][14]=f'Initial-only end to end {seconds/60:.2f} min' if seconds is not None else 'Unavailable'
    if n['agent_seconds'] is not None:r['values'][14]+=f'; generation agent {n["agent_seconds"]/60:.2f} min; repair not applicable'
    r['values'][15]=f'Generation {n["tool_calls"]} calls, {n["tool_failures"]} failed; repair not applicable'
    r['numeric']={'initial':n,'terminal':n,'workflow_seconds':seconds,'repair_applicable':False,
                  'pair_reduction':None,'guarded_pair_reduction':None,'new_pairs':None,'resolved_pairs':None}
    r['auxiliary_checks']=[x for x in r['auxiliary_checks'] if x['phase']=='initial']
    r['source_sha256']={key:value for key,value in r['source_sha256'].items() if not key.startswith('final/')}
    if receipt:r['source_sha256']['initial-only.json']=digest(directory/'initial-only.json')
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paired-root',type=Path,required=True)
    p.add_argument('--baseline-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--qualification-root',type=Path,required=True)
    a=p.parse_args()
    qualification = read(a.qualification_root/'qualification.json')
    if not qualification or qualification.get('qualified') is not True:
        raise ValueError('Current passing P21 qualification required for unified scoring')
    records=[]
    for model,folder in [('openai','smokes-v2'),('anthropic','smokes-anthropic-post-topup'),('google','smokes-google-new-key')]:
        current_paths = []
        for phase in ('initial','final'):
            root = a.qualification_root/model/'p21_feedback'/phase
            summary = read(root/'summary.json')
            entry = next((r for r in qualification['checks'] if r['model']==model and r['condition']=='p21_feedback' and r['phase']==phase), None)
            if (not summary or not entry or entry.get('qualified') is not True
                    or entry['summary_sha256'] != digest(root/'summary.json')
                    or len(summary.get('repeats', [])) != 2
                    or not all(r.get('validator_accepted') for r in summary['repeats'])):
                raise ValueError('Historical revalidation not accepted')
            current_paths.append(root/'1/unqualified-report-parse.json')
        records.extend([collect(a.baseline_root/folder/model,model,'p21_feedback',conformance_paths=current_paths),
                        initial_only(a.paired_root/model,model),collect(a.paired_root/model,model,'self_review')])
    data={'scope':'Excluded paired initial-only/self-review batch with nonconcurrent historical P21-feedback controls',
          'metrics':METRICS,'records':records,
          'qualification_sha256':digest(a.qualification_root/'qualification.json'),
          'limitations':['Initial-only and self-review share generation and are paired endpoints, not independent runs.',
                         'Do not sum both endpoint cumulative costs as batch spending; count each generation once.',
                         'Historical P21-feedback controls are nonconcurrent; descriptive comparisons only.',
                         'Repair metrics are not applicable to initial-only. Missing scores are not zero findings.',
                         'All failures remain in the planned denominator; no successful retry substitution.',
                         'Historical conformance scores use current accepted fixed-artifact revalidation; original scores remain unchanged in source evidence. Other historical metrics retain their original run measurements.']}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'metrics.json').write_text(json.dumps(data,indent=2)+'\n')
    headers=['No.','Metric']+[r['model']+' / '+r['condition'] for r in records]
    rows=[[i+1,name]+[r['values'][i] for r in records] for i,name in enumerate(METRICS)]
    with (a.out/'metrics.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
    lines=['# Paired pilot and historical controls','',data['scope'],'','| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    lines+=['| '+' | '.join(str(v).replace('\n','<br>').replace('|','/') for v in row)+' |' for row in rows]
    lines+=['','## Qualifications','']+['- '+x for x in data['limitations']]
    (a.out/'metrics.md').write_text('\n'.join(lines)+'\n')
    print('Saved 16 rows across 9 planned endpoints; no model or P21 calls.')


if __name__=='__main__':main()
