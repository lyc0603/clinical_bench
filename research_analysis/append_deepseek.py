"""Preserve the nine published endpoints and append three DeepSeek endpoints."""
import argparse,csv,json
from pathlib import Path
from main_experiment.core import fingerprint
from main_experiment.support import digest,manifest,save
from pre_experiment.report_metrics import collect,read
from pre_experiment.report_paired import initial_only
from research_analysis.paired_provenance import annotate
from pilot_extensions.deepseek import tools


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--deepseek-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();d=read(a.previous);root=a.deepseek_root
    if len(d['records'])!=9 or len(d['metrics'])!=16:raise ValueError('Expected preserved nine-endpoint report')
    lock=read(root/'pilot-plan.json');payload=lock['payload']
    if fingerprint(payload)!=lock['sha256'] or payload['extension_tools']!=tools():raise ValueError('Invalid extension seal')
    if not ((root/'completed.json').exists() or (root/'interruption.json').exists()):raise ValueError('Execution is still active')
    paired=root/'paired/deepseek';feedback=root/'p21_feedback/deepseek'
    added=[collect(feedback,'deepseek','p21_feedback'),initial_only(paired,'deepseek'),collect(paired,'deepseek','self_review')]
    audit=[]
    for folder in (paired,feedback):
        state=read(folder/'state.json') or {'status':'not_started'};phases={}
        initial_ids=None
        for phase in ('initial','final'):
            f=folder/phase
            if not f.exists():continue
            e=read(f/'evaluation.json');agent=read(f/'agent.json') or {}
            history=read(f/'history.json')
            if history:
                if history!=read(f/'history.raw.json'):raise ValueError('History/raw mismatch')
                ids=[m['info']['id'] for m in history['messages']]
                if initial_ids is None:initial_ids=ids
                elif ids[:len(initial_ids)]!=initial_ids or len(ids)<=len(initial_ids):raise ValueError('Session continuity failed')
            if e:
                if manifest(f/'workspace')!=read(f/'workspace-manifest.json'):raise ValueError('Workspace drift')
                if (f/'checkpoint-manifest.json').exists():
                    actual=manifest(f);actual.pop('checkpoint-manifest.json')
                    if actual!=read(f/'checkpoint-manifest.json'):raise ValueError('Checkpoint drift')
                if not agent.get('completion',{}).get('normal'):raise ValueError('Evaluated endpoint lacks normal model completion')
            phases[phase]={'normal_completion':agent.get('completion',{}).get('normal'),
               'evaluation_sha256':digest(f/'evaluation.json') if e else None,
               'report_usable':(e or {}).get('conformance',{}).get('report_usable')}
        if (folder/'initial-only.json').exists():
            receipt=read(folder/'initial-only.json')
            if receipt['evaluation_sha256']!=digest(folder/'initial/evaluation.json'):raise ValueError('Initial-only receipt changed')
        audit.append({'condition':folder.parent.name,'controller_status':state['status'],'phases':phases})
    for r in added:
        folder=feedback if r['condition']=='p21_feedback' else paired
        phases=('initial',) if r['condition']=='initial_only' else ('initial','final')
        annotate(r,{ph:(read(folder/ph/'evaluation.json') or {}).get('conformance',{}) for ph in phases})
    old_records=d['records'][:];d['records']+=added
    d.update(scope='Excluded four-model exploratory comparison: paired initial-only/self-review and P21-feedback controls',
       extension_provenance={'previous_report_sha256':digest(a.previous),'extension_lock_sha256':lock['sha256'],
          'report_script_sha256':digest(Path(__file__)),'previous_nine_records_unchanged':d['records'][:9]==old_records})
    d['limitations'] += ['DeepSeek was added later: two independent generation sessions supply three endpoints. This is an exploratory extension, not a prespecified main-study model.',
      'DeepSeek telemetry costs use declared peak rates; actual off-peak billing may be lower. Readiness costs are excluded. The official model alias is mutable.']
    out=a.out;out.mkdir(parents=True,exist_ok=False);save(out/'metrics.json',d)
    headers=['No.','Metric']+[r['model']+' / '+r['condition'] for r in d['records']]
    rows=[[i+1,m]+[r['values'][i] for r in d['records']] for i,m in enumerate(d['metrics'])]
    with (out/'metrics.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
    lines=['# Four-model exploratory comparison','',d['scope'],'','| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    lines+=['| '+' | '.join(str(v).replace('\n','<br>').replace('|','/') for v in row)+' |' for row in rows]
    lines+=['','## Qualifications','']+['- '+s for s in d['limitations']]
    (out/'metrics.md').write_text('\n'.join(lines)+'\n')
    with (out/'auxiliary-checks.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['model','condition','phase','check','status','assessed','errors','missing','extra','duplicates'],lineterminator='\n');w.writeheader()
        for r in d['records']:
            for c in r['auxiliary_checks']:w.writerow({'model':r['model'],'condition':r['condition'],**c})
    save(out/'extension-audit.json',{'main_study_started':False,'previous_report_sha256':digest(a.previous),
       'previous_nine_records_unchanged':d['records'][:9]==old_records,'extension_lock_sha256':lock['sha256'],
       'script_sha256':digest(Path(__file__)),'records':audit,'limitation':'Local consistency audit; original failures and missing endpoints retained.'})
    print('Preserved nine records; appended three DeepSeek endpoints, with 16 metrics each.')


if __name__=='__main__':main()
