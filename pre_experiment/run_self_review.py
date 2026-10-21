"""Run one independently initialized excluded self-review workflow per provider."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from main_experiment.core import config, private_path
from main_experiment.runner import verify, workflow
from main_experiment.support import digest, load_env, save


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--env-file', type=Path, required=True)
    p.add_argument('--lock', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    if not a.execute:
        p.error('--execute is required; provider calls incur charges')
    out = private_path(a.out)
    if out.exists():
        raise RuntimeError('Attempt directory exists; preserve it, never silently retry')
    c = config(a.config)
    lock = json.loads(a.lock.read_text())
    load_env(a.env_file)
    for model in c['models']:
        if not os.environ.get(model['key_env']):
            raise RuntimeError('Missing credential: '+model['key_env'])
    verify(c, lock)
    # Preserve relative shuffled order of the first self-review occurrence of
    # each provider, without reusing any initial package or existing session.
    items = []
    for item in lock['seal']['schedule']:
        if item['condition'] == 'self_review' and item['model'] not in {i['model'] for i in items}:
            items.append(dict(workflow='pilot-self-'+item['model'], model=item['model'],
                              condition='self_review', repetition=0))
    assert len(items) == len(c['models']) == 3
    out.mkdir(parents=True)
    save(out/'pilot-plan.json', {
        'excluded_from_main': True, 'condition': 'self_review', 'workflows': items,
        'source_lock_sha256': digest(a.lock), 'source_seal_sha256': lock['sha256'],
        'launcher_sha256': digest(Path(__file__)),
        'git_commit': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'comparison': 'Previously observed excluded P21-feedback smokes; nonconcurrent, descriptive only',
        'policy': 'One fresh generation and one same-session review per provider; no time cap; no silent retries; stop scheduling after failure',
    })
    guard = out/'.running'
    fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        for item in items:
            verify(c, lock)
            print('Starting excluded self-review: '+item['model'], flush=True)
            workflow(c, item, out/item['model'], lock['seal']['runtime']['image'])
            verify(c, lock)
            print('Completed excluded self-review: '+item['model'], flush=True)
    finally:
        guard.unlink()


if __name__ == '__main__':
    main()
