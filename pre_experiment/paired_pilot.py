"""Excluded paired initial-only/self-review pilot; never launches the main study."""
import argparse
import json
import os
from pathlib import Path
import time

from main_experiment.core import config, fingerprint, private_path
from main_experiment.evaluate import Evaluator
from main_experiment.runner import seal, workflow
from main_experiment.support import digest, load_env, manifest, save

HERE = Path(__file__).resolve().parent


def tool_manifest():
    paths = sorted(HERE.glob('*.py')) + [HERE/'PAIRED-PILOT.md']
    return {p.name: digest(p) for p in paths}


def qualification_valid(receipt, current):
    if receipt.get('schema') != 'paired-p21-qualification-v1' or receipt.get('qualified') is not True:
        raise ValueError('A passing current P21 qualification is required')
    if receipt.get('tools') != tool_manifest():
        raise ValueError('Qualification does not match current pilot tools')
    if receipt.get('seal_sha256') != fingerprint(current):
        raise ValueError('Qualification does not match current inputs, config, evaluator and runtime')
    expected = {(m['id'], c, p) for m in current['config']['models']
                for c in ('self_review', 'p21_feedback') for p in ('initial', 'final')}
    records = receipt.get('checks', [])
    if len(records) != len(expected) or {(r['model'], r['condition'], r['phase']) for r in records} != expected:
        raise ValueError('Qualification must cover both phases of both conditions for all models')
    if not all(r.get('qualified') is True for r in records):
        raise ValueError('Qualification includes failed checks')


def paired_workflow(c, item, directory, image, backend=None, evaluator=None):
    """One initial generation supplies two endpoints; review extends its session."""
    directory = Path(directory)
    evaluate = evaluator or Evaluator(c, image)
    def checkpoint(workspace, phase_directory):
        original = manifest(workspace)
        result = evaluate(workspace, phase_directory)
        if manifest(workspace) != original:
            raise RuntimeError('Evaluator altered checkpoint; endpoint not accepted')
        if phase_directory.name == 'initial':
            # Retain the baseline endpoint even if the later review fails.
            save(directory/'initial-only.json', {
                'condition':'initial_only', 'model':item['model'], 'status':'completed',
                'shared_initial':True, 'checkpoint':'initial', 'finished_unix':time.time(),
                'started_unix':json.loads((directory/'state.json').read_text())['started_unix'],
                'agent_sha256':digest(phase_directory/'agent.json') if (phase_directory/'agent.json').exists() else None,
                'evaluation_sha256':digest(phase_directory/'evaluation.json'),
                'workspace_manifest_sha256':fingerprint(manifest(workspace)),
                'repair_metrics':'not_applicable',
            })
        if not (result.get('conformance') or {}).get('report_usable'):
            raise RuntimeError('P21 report unavailable or invalid; endpoint retained, scheduling stopped for adjudication')
        return result
    options = {'evaluator':checkpoint}
    if backend is not None:
        options['backend'] = backend
    return workflow(c, item, directory, image, **options)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('freeze','run'))
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--lock', type=Path, required=True)
    p.add_argument('--qualification', type=Path)
    p.add_argument('--env-file', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    c = config(a.config)
    current = seal(c)
    lock_path = private_path(a.lock)
    if a.action == 'freeze':
        if not a.qualification:
            p.error('--qualification is required; diagnostics must pass first')
        receipt = json.loads(a.qualification.read_text())
        qualification_valid(receipt, current)
        if lock_path.exists():
            raise ValueError('Preserve existing freeze; select a new path')
        items = [dict(workflow='paired-'+m['id'], model=m['id'], condition='self_review', repetition=0)
                 for m in c['models']]
        payload = {'scope':'excluded_paired_pilot_v1', 'seal':current, 'tools':tool_manifest(),
                   'qualification_sha256':digest(a.qualification), 'qualification':receipt,
                   'workflows':items, 'endpoints':['initial_only','self_review'],
                   'policy':'Shared initial generation; same-session review; serial; no silent retries; no agent time cap'}
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        save(lock_path, {'payload':payload,'sha256':fingerprint(payload)})
        print('Paired pilot frozen; no model calls made.')
        return
    if not a.execute or not a.env_file or not a.out:
        p.error('run requires --execute, --env-file and a fresh --out; calls incur charges')
    lock = json.loads(lock_path.read_text())
    payload = lock['payload']
    def verify():
        if lock['sha256'] != fingerprint(payload) or payload['scope'] != 'excluded_paired_pilot_v1':
            raise ValueError('Invalid paired pilot freeze')
        if payload['seal'] != seal(c) or payload['tools'] != tool_manifest():
            raise ValueError('Paired pilot inputs, runtime, code or tools changed; refreeze required')
        qualification_valid(payload['qualification'], payload['seal'])
    verify()
    out = private_path(a.out)
    if out.exists():
        raise ValueError('Attempt exists; never overwrite or silently retry')
    load_env(a.env_file)
    if any(not os.environ.get(m['key_env']) for m in c['models']):
        raise ValueError('Missing provider credential')
    out.mkdir(parents=True)
    save(out/'pilot-plan.json',lock)
    guard = out/'.running'
    guard.write_text(str(os.getpid()))
    try:
        for item in payload['workflows']:
            verify()
            paired_workflow(c,item,out/item['model'],payload['seal']['runtime']['image'])
            verify()
    except BaseException as exc:
        save(out/'interruption.json', {'reason':str(exc),'type':type(exc).__name__,
             'policy':'Scheduling stopped; guard retained for adjudication; no automatic resume'})
        raise
    else:
        guard.unlink()
        save(out/'completed.json', {'status':'completed','main_study':False,'paired_endpoints':6})


if __name__ == '__main__':
    main()
