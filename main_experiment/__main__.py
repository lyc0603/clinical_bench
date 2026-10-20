"""Reviewable main-study CLI. Planning and preflight never invoke a model."""
import argparse
import json
from pathlib import Path
import os

from experiment.experiment import load_env, manifest, save
from .backend import capture
from .completion import smoke_evidence, validate_smoke_evidence
from .core import config, fingerprint, prepare, private_path, schedule
from .runner import report, seal, verify, workflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare-inputs', 'plan', 'preflight', 'smoke', 'freeze', 'run', 'report'])
    parser.add_argument('--config', type=Path, default=Path('main_experiment/config.local.json'))
    parser.add_argument('--env-file', type=Path, default=Path('.env.local'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--smokes', type=Path)
    parser.add_argument('--lock', type=Path)
    parser.add_argument('--model', help='Configured model alias; smoke only')
    parser.add_argument('--execute', action='store_true', help='Explicitly allow paid provider invocations')
    parser.add_argument('--fix-trta-predecessor', action='store_true')
    a = parser.parse_args()
    if a.action == 'prepare-inputs':
        if not a.source or not a.out:
            parser.error('prepare-inputs requires --source and --out')
        print(json.dumps(prepare(a.source, a.out, a.fix_trta_predecessor), indent=2))
        return
    c = config(a.config)
    if a.action == 'plan':
        print(json.dumps({'workflows': schedule(c), 'planned_workflows': 18,
              'maximum_phase_invocations': 36, 'maximum_active_agent_hours': None,
              'provider_request_count': 'variable; not equivalent to phase invocations'}, indent=2))
        return
    load_env(a.env_file)
    if a.action == 'preflight':
        current = seal(c)
        capabilities = capture(['docker', 'run', '--rm', '--network', 'none',
                                current['runtime']['image'], 'opencode', 'run', '--help'])
        if '--session' not in capabilities or '--format' not in capabilities:
            raise RuntimeError('Pinned OpenCode lacks required session/JSON capabilities')
        for model in c['models']:
            if not os.environ.get(model['key_env']):
                raise RuntimeError('Missing credential: '+model['key_env'])
            catalog = capture(['docker', 'run', '--rm', '--network', 'none',
                               current['runtime']['image'], 'opencode', 'models', model['model'].split('/')[0]])
            if model['model'] not in catalog.splitlines():
                raise RuntimeError('Exact configured model absent from pinned runtime catalog: '+model['model'])
        print(json.dumps({'local_preflight': 'passed', 'seal_sha256': fingerprint(current),
                          'provider_access': 'not tested; requires excluded smoke'}, indent=2))
        return
    if not a.out:
        parser.error('--out is required')
    out = private_path(a.out)
    if a.action == 'report':
        out.mkdir(parents=True, exist_ok=True)
        report(c, out)
        return
    if a.action == 'freeze':
        if not a.smokes or not a.lock:
            parser.error('freeze requires --smokes and --lock')
        current = seal(c)
        receipts = []
        for model in c['models']:
            receipt = json.loads((a.smokes / (model['id']+'.receipt.json')).read_text())
            if receipt['seal_sha256'] != fingerprint(current) or not receipt['qualified']:
                raise RuntimeError('Smoke missing, unqualified or stale: '+model['id'])
            validate_smoke_evidence(receipt.get('completion_evidence',{}),model)
            receipts.append(receipt)
        lock = private_path(a.lock)
        if lock.exists():
            raise RuntimeError('Freeze lock already exists')
        save(lock, {'seal': current, 'sha256': fingerprint(current), 'smokes': receipts})
        print('Frozen protocol written; no main runs started.')
        return
    if not a.execute:
        parser.error('smoke/run requires --execute (can incur provider charges)')
    out.mkdir(parents=True, exist_ok=True)
    # Exclusive concurrency guard: normal Python unwinding removes it.
    # Termination bypassing finally (e.g. SIGKILL) may retain it. Workflow
    # states/checkpoint seals separately block retries after any failure.
    guard = out / '.running'
    fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        if a.action == 'smoke':
            current = seal(c)
            if a.model not in {m['id'] for m in c['models']}:
                parser.error('smoke requires a configured --model alias')
            item = dict(workflow='smoke', model=a.model, condition='p21_feedback', repetition=0)
            directory = out / a.model
            state = workflow(c, item, directory, current['runtime']['image'])
            if state['status'] != 'completed':
                raise RuntimeError('Smoke incomplete; qualification receipt not issued')
            evaluations = [json.loads((directory / phase / 'evaluation.json').read_text()) for phase in ('initial', 'final')]
            qualified = all(e['conformance'].get('report_usable') is True and e.get('deliverables_complete') is True and
                            e['semantic_reproduced'] is True and e['correctness'].get('complete') is True
                            for e in evaluations)
            # Ensure no runtime/config/input drift across the qualification.
            if seal(c) != current:
                raise RuntimeError('Seal changed during smoke')
            save(out / (a.model+'.receipt.json'), {'model': a.model, 'excluded_from_main': True,
                 'seal_sha256': fingerprint(current), 'qualified': qualified,
                 'completion_evidence': smoke_evidence(directory,next(m for m in c['models'] if m['id']==a.model))})
            if not qualified:
                raise RuntimeError('Smoke executed but qualification failed; inspect endpoint evidence')
        else:
            if not a.lock:
                parser.error('run requires --lock')
            lock = json.loads(a.lock.read_text())
            verify(c, lock)
            binding = out / 'run-lock.json'
            if binding.exists():
                if json.loads(binding.read_text()) != lock:
                    raise RuntimeError('Output directory belongs to another frozen protocol')
            else:
                if any(out.glob('w[0-9][0-9]')):
                    raise RuntimeError('Existing workflows lack a protocol binding')
                save(binding, lock)
            # Skip completed evidence only; failed/interrupted paths halt scheduling.
            for item in lock['seal']['schedule']:
                directory = out / item['workflow']
                if directory.exists():
                    state = json.loads((directory / 'state.json').read_text())
                    if state['status'] != 'completed':
                        raise RuntimeError('Failed/interrupted workflow requires adjudication: '+item['workflow'])
                    for phase in ('initial', 'final'):
                        checkpoint = directory / phase
                        recorded = json.loads((checkpoint / 'checkpoint-manifest.json').read_text())
                        actual = manifest(checkpoint)
                        actual.pop('checkpoint-manifest.json', None)
                        if actual != recorded:
                            raise RuntimeError('Completed checkpoint was altered')
                    continue
                verify(c, lock)
                workflow(c, item, directory, lock['seal']['runtime']['image'])
                verify(c, lock)
                report(c, out)
    finally:
        guard.unlink()
        if a.action == 'run':
            report(c, out)


if __name__ == '__main__':
    main()
