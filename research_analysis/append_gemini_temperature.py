"""Append three planned temperature endpoints without changing historical records."""
import argparse
import csv
import json
from pathlib import Path

from main_experiment.core import fingerprint
from main_experiment.support import digest, manifest, save, load_env
from pre_experiment.report_metrics import read
from pre_experiment.report_paired import initial_only
from research_analysis.paired_provenance import annotate
from temperature_extensions.gemini import current, tools, sampler, TEMPERATURES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'root', 'out', 'base-config', 'qualification', 'transport', 'smoke', 'env-file'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    load_env(a.env_file)
    data = read(a.previous)
    if len(data['records']) != 12 or len(data['metrics']) != 16:
        raise ValueError('Expected original twelve-endpoint, sixteen-metric report')
    if not ((a.root/'completed.json').exists() or (a.root/'interruption.json').exists()):
        raise ValueError('Batch has not reached a terminal controller state')
    lock = read(a.root/'pilot-plan.json')
    payload = lock['payload']
    if fingerprint(payload) != lock['sha256'] or payload['extension_tools'] != tools():
        raise ValueError('Invalid extension seal')
    _, now = current(a.base_config, a.qualification)
    if now != {k:v for k,v in payload.items() if k not in ('transport_sha256','readiness_sha256')}:
        raise ValueError('Frozen base changed')
    if digest(a.transport) != payload['transport_sha256'] or digest(a.smoke/'qualification.json') != payload['readiness_sha256']:
        raise ValueError('Qualification receipt changed')
    readiness = read(a.smoke/'qualification.json')
    actual = manifest(a.smoke); actual.pop('qualification.json', None)
    if not readiness.get('qualified') or actual != readiness['evidence']:
        raise ValueError('Readiness evidence changed')
    historical = json.loads(json.dumps(data['records']))
    added, audit = [], []
    for t in TEMPERATURES:
        folder = a.root/str(t); phase = folder/'initial'
        state = read(folder/'state.json') or {'status':'not_started'}
        evaluation = read(phase/'evaluation.json') or {}
        receipt = read(folder/'initial-only.json')
        sampling = read(folder/'sampling.json')
        if sampling and (sampling['requested_temperature'] != t or sampling['resolved_build_temperature'] != t):
            raise ValueError('Temperature identity mismatch')
        agent = read(phase/'agent.json') or {}
        history = read(phase/'history.json')
        if history:
            if history != read(phase/'history.raw.json'):
                raise ValueError('History export mismatch')
            assistants = [m['info'] for m in history['messages'] if m['info']['role']=='assistant']
            if not assistants or any(m.get('providerID')!='google' or m.get('modelID')!='gemini-3.1-pro-preview' for m in assistants):
                raise ValueError('Unexpected model identity')
        if evaluation:
            if (phase/'prompt.txt').read_text() != payload['base_seal']['prompts']['generate']:
                raise ValueError('Frozen prompt changed')
            if not agent.get('completion',{}).get('normal'):
                raise ValueError('Evaluated endpoint lacks normal model completion')
            post = read(phase/'sampling-config-after.json')
            schema = post.pop('$schema',None)
            if schema not in (None,'https://opencode.ai/config.json') or post != sampler(t):
                raise ValueError('Post-generation sampling mismatch')
            if manifest(phase/'workspace') != read(phase/'workspace-manifest.json'):
                raise ValueError('Workspace changed')
            actual = manifest(phase); actual.pop('checkpoint-manifest.json',None)
            if actual != read(phase/'checkpoint-manifest.json'):
                raise ValueError('Checkpoint changed')
        if receipt:
            if receipt['evaluation_sha256'] != digest(phase/'evaluation.json') or receipt['agent_sha256'] != digest(phase/'agent.json'):
                raise ValueError('Endpoint receipt changed')
            if receipt['workspace_manifest_sha256'] != fingerprint(manifest(phase/'workspace')):
                raise ValueError('Endpoint workspace changed')
        r = initial_only(folder,'google')
        annotate(r,{'initial':evaluation.get('conformance',{})})
        r.update(temperature=t, repetition=0, shared_initial=False,
                 model_version='google/gemini-3.1-pro-preview',
                 endpoint_label=f'google / initial_only / temperature {t}',
                 controller_status=state['status'])
        added.append(r)
        audit.append({'temperature':t,'controller_status':state['status'],
                      'normal_completion':agent.get('completion',{}).get('normal'),
                      'p21_report_usable':evaluation.get('conformance',{}).get('report_usable'),
                      'sampling_sha256':digest(folder/'sampling.json') if sampling else None,
                      'evaluation_sha256':digest(phase/'evaluation.json') if evaluation else None})
    data['records'] += added
    assert data['records'][:12] == historical
    assert all(len(r['values']) == 16 for r in data['records'])
    data['scope'] = 'Exploratory four-model comparison plus three independent Gemini initial-only temperature endpoints'
    data['temperature_extension_provenance'] = {'previous_report_sha256':digest(a.previous),
        'extension_lock_sha256':lock['sha256'],'report_script_sha256':digest(Path(__file__)),
        'previous_twelve_records_unchanged':True,'main_study_started':False}
    data['limitations'] += [
        'Temperature 0.2, 0.6 and 1.0 each have one independent initial-only attempt, in fixed order 1.0, 0.2, 0.6. Descriptive sensitivity observations only; no causal or significance claims.',
        'The title helper is disabled for all new temperature endpoints. Historical default-setting endpoints are nonconcurrent contextual controls. New temperature 1.0 is the matched-setting reference within this batch.',
        'Gemini preview is a mutable provider endpoint. Serialized temperature acceptance does not verify server-side sampling internals.',
        'All planned temperature endpoints remain in the table, including failures and not-started endpoints after a scheduling interruption. No automatic generation retries.',
        'Temperature endpoints have no repair phase. Cost estimates exclude nonclinical qualification calls and are not invoices. P21 conformance does not establish clinical derivation correctness.'
    ]
    out=a.out; out.mkdir(parents=True,exist_ok=False)
    save(out/'metrics.json',data)
    headers=['No.','Metric']+[r.get('endpoint_label',r['model']+' / '+r['condition']) for r in data['records']]
    rows=[[i+1,m]+[r['values'][i] for r in data['records']] for i,m in enumerate(data['metrics'])]
    with (out/'metrics.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n'); w.writerow(headers); w.writerows(rows)
    lines=['# Exploratory results with Gemini temperature sensitivity','',data['scope'],'',
           '| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    lines += ['| '+' | '.join(str(v).replace('\n','<br>').replace('|','/') for v in row)+' |' for row in rows]
    lines += ['','## Interpretation limits','']+['- '+s for s in data['limitations']]
    (out/'metrics.md').write_text('\n'.join(lines)+'\n')
    save(out/'temperature-audit.json',{'main_study_started':False,
        'previous_twelve_records_unchanged':True,'extension_lock_sha256':lock['sha256'],
        'previous_report_sha256':digest(a.previous),'records':audit})
    print('Preserved twelve historical endpoints and appended all three planned temperature endpoints, each with sixteen metrics.')


if __name__ == '__main__':
    main()
