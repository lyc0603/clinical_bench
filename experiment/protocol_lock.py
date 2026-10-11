"""Verify the sealed main-study protocol before any model calls."""
import json
from pathlib import Path


def verify(config):
    from experiment import digest, manifest, prompt
    if not config.get('protocol_lock'):
        return None  # Existing pilot configurations remain supported.
    path = Path(config['protocol_lock'])
    seal = path.with_suffix('.sha256').read_text().strip()
    if digest(path) != seal:
        raise ValueError('Protocol seal changed: create a new protocol version')
    lock = json.loads(path.read_text())
    actual = {k: v for k, v in config.items() if k != 'protocol_lock'}
    if actual != lock['config']:
        raise ValueError('Frozen main-study configuration changed')
    import sys
    import importlib.metadata
    host = {'python': sys.version, 'packages': {name: importlib.metadata.version(name)
            for name in ['numpy', 'pandas', 'pyreadstat']}}
    if host != lock['host_evaluator']:
        raise ValueError('Frozen host derivation runtime changed')
    for filename, expected in lock['code_hashes'].items():
        if digest(Path(filename)) != expected:
            raise ValueError('Frozen code/scoring rules changed: ' + filename)
    if manifest(Path(config['study_root'])) != lock['input_manifest']:
        raise ValueError('Frozen main-study inputs changed')
    for branch, stage in [('initial', 0), ('self_review', 1), ('p21_feedback', 1)]:
        text = Path(lock['prompt_files'][branch]).read_text()
        if prompt(config, stage, branch) != text:
            raise ValueError('Frozen prompt changed: ' + branch)
    return lock


def verify_environment(lock, current):
    if lock and current != lock['environment']:
        raise ValueError('Frozen image/P21 runtime changed: create a new protocol version')
