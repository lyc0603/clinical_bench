"""Historical paired-design freezer; current main study uses python -m main_experiment freeze."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

from experiment import digest, manifest, prompt, save

HERE = Path(__file__).resolve().parent


def freeze(config, out):
    out = out.resolve()
    if out.exists():
        raise ValueError('Use a new protocol directory; never overwrite a frozen protocol')
    if len(config['models']) != 3 or config['repetitions'] != 3 or config['repair_iterations'] != 1:
        raise ValueError('This protocol requires 3 models × 3 generations × 1 repair per branch')
    for model in config['models']:
        name = model['model']
        if '/' not in name or any(s in name.lower() for s in ['replace', 'latest', 'default', 'auto']):
            raise ValueError('Use explicit provider/model IDs, not defaults or latest aliases')
    image = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}',
                                     config['agent']['image']], text=True).strip()
    versions = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', image,
        'sh', '-c', 'opencode --version; python --version; node --version; python -m pip freeze'], text=True)
    p21 = config['p21']
    cache = Path(p21['cache'])
    environment = {'image_id': image, 'p21_runtime': {
        'jar': digest(cache / 'lib/p21-client-1.0.9.jar'),
        'configs': manifest(cache / 'configs'), 'engines': manifest(cache / 'lib/engines')},
        'java_sha256': digest(Path(p21['java']))}
    java_version = subprocess.run([p21['java'], '-version'], capture_output=True, text=True, check=True)
    host = {'python': sys.version, 'packages': {name: importlib.metadata.version(name)
                                             for name in ['numpy', 'pandas', 'pyreadstat']}}
    original = Path(config['study_root'])
    out.mkdir(parents=True)
    frozen = out / 'frozen_inputs'
    frozen.mkdir()
    for name in config['input_allowlist']:
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Input allowlist must contain relative paths')
        src, dst = original / rel, frozen / rel
        manifest(src) if src.is_dir() else None
        if src.is_symlink():
            raise ValueError('Input symlinks are not allowed')
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
    config = json.loads(json.dumps(config))
    config.update(study_root=str(frozen), derivation_checks=True,
                  protocol_lock=str(out / 'protocol.lock.json'))
    config['agent']['image'] = image
    prompts = {}
    for branch, stage in [('initial',0), ('self_review',1), ('p21_feedback',1)]:
        path = out / 'prompts' / (branch + '.txt')
        path.parent.mkdir(exist_ok=True)
        path.write_text(prompt(config, stage, branch))
        prompts[branch] = str(path)
    shutil.copy2(HERE.parent / 'docs/archive/legacy-paired-protocol.md', out / 'PROTOCOL.md')
    shutil.copy2(HERE.parent / 'docs/archive/legacy-paired-scoring-rules.json', out / 'scoring-rules.json')
    save(out / 'config.json', config)
    schedule = [[m['id'], r] for m in config['models'] for r in range(1,4)]
    random.Random(config['seed']).shuffle(schedule)
    save(out / 'schedule.json', schedule)
    tracked = [HERE / x for x in ['experiment.py','Dockerfile','derivation.py','protocol_lock.py','freeze_protocol.py']]
    tracked += [out / 'PROTOCOL.md', out / 'scoring-rules.json', out / 'schedule.json'] + [Path(p) for p in prompts.values()]
    lock = {'protocol_version':out.name, 'frozen_utc':datetime.now(timezone.utc).isoformat(),
        'config':{k:v for k,v in config.items() if k != 'protocol_lock'},
        'input_manifest':manifest(frozen), 'environment':environment,
        'host_evaluator':host, 'agent_versions':versions, 'java_version':java_version.stderr or java_version.stdout,
        'prompt_files':prompts, 'code_hashes':{str(p):digest(p) for p in tracked},
        'budget':{'agent_calls':27,'seconds_per_call':config['agent']['timeout_seconds'],
                  'maximum_agent_hours':27*config['agent']['timeout_seconds']/3600,
                  'token_cap':None,'retry_policy':'No automatic retries or silent model substitutions'},
        'sampling':'No sampling/reasoning overrides; provider defaults are uncontrolled. No provider seed is imposed.',
        'backend_limit':'Exact API IDs do not guarantee immutable provider weights, especially preview models.',
        'launch_readiness':'Separate preflight required: provider credentials, model catalog and account access'}
    path = out / 'protocol.lock.json'
    save(path, lock)
    path.with_suffix('.sha256').write_text(digest(path)+'\n')
    return lock


if __name__ == '__main__':
    from experiment import load_config, load_env
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--legacy-paired',action='store_true',
        help='Explicitly select the superseded 9-pair/27-invocation design; not the current main study')
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--env-file',type=Path,default=HERE.parent / '.env.local')
    a=p.parse_args()
    if not a.legacy_paired:
        p.error('Historical paired freezer disabled by default. Use python -m main_experiment freeze for the current main study; --legacy-paired is for historical reproduction only.')
    load_env(a.env_file)
    lock=freeze(load_config(a.config),a.out)
    print(json.dumps({'protocol':str(a.out.resolve()),'models':[m['model'] for m in lock['config']['models']],
                      'agent_calls':27,'seal':digest(a.out / 'protocol.lock.json')},indent=2))
