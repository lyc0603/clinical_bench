"""Expose original validator failures alongside current scores; never change scores."""
import argparse
import csv
import json
from pathlib import Path

from main_experiment.support import digest
from pre_experiment.report_metrics import flag


def annotate(record, original):
    record['original_p21']={phase:{key:c.get(key) for key in ('status','report_usable','dataset_rule_pairs','finding_instances','distinct_rules','failure_code')}
                            for phase,c in original.items()}
    terminal='initial' if record['condition']=='initial_only' else 'final'
    c=original.get(terminal,{})
    current=record['values'][2].split('\nOriginal usable',1)[0]
    if current.startswith('Current '):current=current[len('Current '):]
    suffix='\nOriginal usable '+flag(c.get('report_usable'))
    if c.get('failure_code'):suffix+='; '+c['failure_code']
    reassessed=any(k.startswith('current_revalidation/') for k in record['source_sha256'])
    record['conformance_reassessed']=reassessed
    if reassessed:suffix+='; separately reassessed'
    record['values'][2]='Current '+current+suffix


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--source-map',type=Path,required=True)
    p.add_argument('--baseline-root',type=Path,required=True)
    a=p.parse_args();d=json.loads(a.report.read_text());mapping=json.loads(a.source_map.read_text())['model_directories']
    folders={'openai':'smokes-v2','anthropic':'smokes-anthropic-post-topup','google':'smokes-google-new-key'}
    for r in d['records']:
        source=(a.baseline_root/folders[r['model']]/r['model']) if r['condition']=='p21_feedback' else Path(mapping[r['model']])
        phases=('initial',) if r['condition']=='initial_only' else ('initial','final')
        original={}
        for phase in phases:
            f=source/phase/'evaluation.json'
            original[phase]=(json.loads(f.read_text()).get('conformance') or {}) if f.exists() else {}
        annotate(r,original)
    d['analysis_provenance']={'script_sha256':digest(Path(__file__)),
       'policy':'Only expose original versus current validation status; counts, costs, controller status and source files unchanged.'}
    note='Metric 3 shows original and current validator status separately. A successful reassessment does not erase an original technical failure; elapsed time and cost refer to original model workflows and exclude post-hoc host revalidation.'
    if note not in d['limitations']:d['limitations'].append(note)
    a.report.write_text(json.dumps(d,indent=2)+'\n')
    headers=['No.','Metric']+[r['model']+' / '+r['condition'] for r in d['records']]
    rows=[[i+1,m]+[r['values'][i] for r in d['records']] for i,m in enumerate(d['metrics'])]
    with a.report.with_suffix('.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
    lines=['# Paired pilot and historical controls','',d['scope'],'','| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    lines+=['| '+' | '.join(str(v).replace('\n','<br>').replace('|','/') for v in row)+' |' for row in rows]
    lines+=['','## Qualifications','']+['- '+x for x in d['limitations']]
    a.report.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print('Original failures exposed alongside current scores; no measurements replaced.')


if __name__=='__main__':main()
