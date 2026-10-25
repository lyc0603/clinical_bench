"""Audit and append three independent Llama 4 Scout exploratory endpoints."""
import argparse
import csv
import json
from pathlib import Path
from unittest.mock import patch

from main_experiment.core import fingerprint
from main_experiment.support import digest,manifest,save,load_env
from pre_experiment.report_metrics import collect,read
from pre_experiment.report_paired import initial_only
from research_analysis.paired_provenance import annotate
from llama_scout_experiment.run import current,CONDITIONS,MODEL
from llama_scout_extensions.deepinfra_backend import settings
import pre_experiment.report_metrics as legacy_report

def collect_endpoint(folder,condition):
    """Resolve no-tool turns only when exported current-turn evidence proves zero."""
    original_read=legacy_report.read;normalizations=[]
    def reporting_read(path):
        d=original_read(path)
        if path.name!='agent.json' or not d or d.get('tool_calls') is not None:
            return d
        completion=d.get('completion') or {}
        history=original_read(path.with_name('history.json')) or {}
        ids={x['message_id'] for x in completion.get('export_usage',[])}
        current=[m for m in history.get('messages',[]) if m.get('info',{}).get('id') in ids]
        parts=[p for m in current for p in m.get('parts',[]) if p.get('type')=='tool']
        if completion.get('normal') and current and not parts:
            normalizations.append({'phase':path.parent.name,'tool_calls':0,'tool_failures':0,
                'basis':'Normal exported current turn contains no tool parts; raw null telemetry preserved.'})
            return {**d,'tool_calls':0,'tool_failures':0}
        return d
    with patch.object(legacy_report,'read',side_effect=reporting_read):
        r=initial_only(folder,MODEL['id']) if condition=='initial_only' else collect(folder,MODEL['id'],condition)
    r['tool_count_reporting_normalizations']=normalizations
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('previous','root','out','base-config','qualification','readiness','transport','env-file','ripgrep'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();load_env(a.env_file)
    data=read(a.previous)
    if len(data['records'])!=21 or len(data['metrics'])!=16:
        raise ValueError('Expected twenty-one preserved endpoints with sixteen metrics')
    if not ((a.root/'completed.json').exists() or (a.root/'interruption.json').exists()):
        raise ValueError('Batch still active')
    lock=read(a.root/'pilot-plan.json');payload=lock['payload']
    _,now=current(a.base_config,a.qualification,a.readiness,a.transport,a.ripgrep)
    if lock['sha256']!=fingerprint(payload) or now!=payload:
        raise ValueError('Frozen evidence changed')
    historical=json.loads(json.dumps(data['records']))
    added=[];audit=[];sessions=[]
    for condition in CONDITIONS:
        folder=a.root/condition;state=read(folder/'state.json') or {'status':'not_started'}
        phases={};initial_ids=None
        for phase in ('initial',) if condition=='initial_only' else ('initial','final'):
            d=folder/phase
            if not d.exists():
                continue
            evaluation=read(d/'evaluation.json');agent=read(d/'agent.json') or {};history=read(d/'history.json')
            if history:
                if history!=read(d/'history.raw.json'):
                    raise ValueError('History export changed')
                info=history.get('info') or {}
                if phase=='initial' and info.get('id'):
                    sessions.append(info['id'])
                assistants=[m['info'] for m in history['messages'] if m['info']['role']=='assistant']
                if not assistants or any(x.get('providerID')!='deepinfra' or x.get('modelID')!='meta-llama/Llama-4-Scout-17B-16E-Instruct' for x in assistants):
                    raise ValueError('Provider/model identity mismatch')
                ids=[m['info']['id'] for m in history['messages']]
                if phase=='initial':initial_ids=ids
                elif initial_ids is None or ids[:len(initial_ids)]!=initial_ids or len(ids)<=len(initial_ids):
                    raise ValueError('Repair session continuity failed')
            if evaluation:
                key='generate' if phase=='initial' else condition
                if phase=='final' and condition=='p21_feedback' and not state.get('feedback',{}).get('report_usable'):
                    key='feedback_unavailable'
                if (d/'prompt.txt').read_text()!=payload['base_seal']['prompts'][key]:
                    raise ValueError('Prompt mismatch')
                if not agent.get('completion',{}).get('normal'):
                    raise ValueError('Evaluation lacks normal completion')
                post=read(d/'provider-config-after.json');schema=post.pop('$schema',None)
                if schema not in (None,'https://opencode.ai/config.json') or post!=settings(MODEL):
                    raise ValueError('Sampling changed')
                if manifest(d/'workspace')!=read(d/'workspace-manifest.json'):
                    raise ValueError('Workspace drift')
                actual=manifest(d);actual.pop('checkpoint-manifest.json',None)
                if actual!=read(d/'checkpoint-manifest.json'):
                    raise ValueError('Checkpoint drift')
            phases[phase]={'normal_completion':agent.get('completion',{}).get('normal'),
                'evaluation_sha256':digest(d/'evaluation.json') if evaluation else None,
                'report_usable':(evaluation or {}).get('conformance',{}).get('report_usable')}
        receipt=read(folder/'initial-only.json')
        if receipt:
            d=folder/'initial'
            if receipt['evaluation_sha256']!=digest(d/'evaluation.json') or receipt['agent_sha256']!=digest(d/'agent.json') or receipt['workspace_manifest_sha256']!=fingerprint(manifest(d/'workspace')):
                raise ValueError('Initial-only receipt changed')
        r=collect_endpoint(folder,condition)
        original={phase:(read(folder/phase/'evaluation.json') or {}).get('conformance',{}) for phase in phases}
        annotate(r,original)
        r.update(model_version=MODEL['model'],provider='deepinfra',temperature=1.0,reasoning_effort=None,
            repetition=0,shared_initial=False,controller_status=state['status'],
            endpoint_label='llama-4-scout (DeepInfra) / '+condition)
        added.append(r);audit.append({'condition':condition,'controller_status':state['status'],'phases':phases})
    if len(sessions)!=len(set(sessions)):
        raise ValueError('Conditions unexpectedly share an initial session')
    data['records']+=added
    assert data['records'][:21]==historical and all(len(r['values'])==16 for r in data['records'])
    data['scope']='Exploratory comparison preserving twenty-one historical endpoints and adding three independent DeepInfra Llama 4 Scout conditions'
    data['llama_scout_extension_provenance']={'previous_report_sha256':digest(a.previous),
        'extension_lock_sha256':lock['sha256'],'report_script_sha256':digest(Path(__file__)),
        'previous_twenty-one_records_unchanged':True,'main_study_started':False}
    data['limitations'] += [
        'Llama 4 Scout contributes one independent workflow per condition. Its three initial generations are not paired; historical initial-only/self-review shared-generation endpoints have a different dependence structure.',
        'DeepInfra settings are fixed at temperature 1.0, no reasoning-effort parameter and 16,384 maximum response tokens. The title helper is disabled and only the declared provider API is reachable. Hosted weights and server implementation are not independently pinned.',
        'One repetition per condition supports descriptive feasibility observations only. No temperature or causal feedback/model-size claims are supported.',
        'All three planned Llama 4 Scout conditions remain in the denominator, including failures and unscheduled conditions if execution stops. No automatic retries. Missing scores are unavailable, not zero.',
        'API cost estimates exclude technical qualification and are not invoices. The Llama conditions independently incur their own generation and repair costs.'
        ,'Llama 4 Scout uses qualified hash-pinned ripgrep support. The first nonclinical readiness attempt failed with empty tool arguments; a second diagnostic uses explicit synthetic tool parameters. All attempts are retained; study prompts are unchanged. Qualification costs are excluded from clinical workflow costs.'
        ,'Where native tool telemetry is null for a normal turn, a zero tool count is reported only if exported current-turn messages independently contain no tool parts. Raw telemetry is preserved and each such interpretation is recorded.'
    ]
    out=a.out;out.mkdir(parents=True,exist_ok=False);save(out/'metrics.json',data)
    headers=['No.','Metric']+[r.get('endpoint_label',r['model']+' / '+r['condition']) for r in data['records']]
    rows=[[i+1,m]+[r['values'][i] for r in data['records']] for i,m in enumerate(data['metrics'])]
    with (out/'metrics.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
    lines=['# Exploratory comparison including Llama 4 Scout','',data['scope'],'',
        '| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    lines+=['| '+' | '.join(str(x).replace('\n','<br>').replace('|','/') for x in r)+' |' for r in rows]
    lines+=['','## Interpretation limits','']+['- '+x for x in data['limitations']]
    (out/'metrics.md').write_text('\n'.join(lines)+'\n')
    save(out/'llama-scout-audit.json',{'main_study_started':False,'previous_twenty-one_records_unchanged':True,
        'previous_report_sha256':digest(a.previous),'extension_lock_sha256':lock['sha256'],
        'independent_initial_session_count':len(sessions),'records':audit})
    print('Preserved twenty-one endpoints and appended three Llama 4 Scout conditions, all sixteen metrics retained.')

if __name__=='__main__':
    main()
