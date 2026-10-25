"""Excluded Gemini temperature sensitivity pilot: three initial-only attempts."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import time

from main_experiment.backend import DockerSession, capture
from main_experiment.core import config, fingerprint, private_path, prompts
from main_experiment.evaluate import Evaluator
from main_experiment.runner import seal
from main_experiment.support import digest, load_env, manifest, save
from pre_experiment.paired_pilot import qualification_valid

HERE = Path(__file__).resolve().parent
TEMPERATURES = [0.2, 0.6, 1.0]
MODEL = {'id': 'google', 'model': 'google/gemini-3.1-pro-preview',
         'key_env': 'GOOGLE_GENERATIVE_AI_API_KEY'}

def sampler(temperature):
    if temperature not in TEMPERATURES:
        raise ValueError('Only the three frozen temperatures are supported')
    # Disable incidental title generation, which otherwise selects another model.
    return {'agent': {'build': {'temperature': temperature}, 'title': {'disable': True}}}

def tools():
    return {p.name: digest(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py', '.md')}

def current(base_path, qualification):
    c = config(base_path)
    s = seal(c)
    q = json.loads(qualification.read_text())
    qualification_valid(q, s)
    for entry in q['checks']:
        p = qualification.parent / entry['model'] / entry['condition'] / entry['phase'] / 'summary.json'
        if digest(p) != entry['summary_sha256']:
            raise ValueError('P21 qualification evidence changed')
    cache = manifest(Path(c['p21']['cache']))
    if 'lib/engines/app.data' in cache:
        raise ValueError('P21 source cache must remain in qualified clean state')
    return c, {'base_seal': s, 'qualification_sha256': digest(qualification),
               'cache_source': cache, 'extension_tools': tools(), 'model': MODEL,
               'temperatures': TEMPERATURES, 'order': [1.0, 0.2, 0.6],
               'samplers': {str(t): sampler(t) for t in TEMPERATURES},
               'scope': 'excluded_gemini_temperature_initial_only_v1',
               'policy': 'One independent session per temperature; serial; no repair, automatic retry or agent time cap; failed attempts retained; no main-study launch.'}

class TemperatureSession(DockerSession):
    def start(self):
        if self.model != MODEL:
            raise ValueError('Only the frozen Gemini model is supported')
        super().start()
        settings = sampler(self.c['temperature'])
        capture(['docker', 'exec', self.name, 'python', '-c',
                 'from pathlib import Path;import sys;p=Path("/state/config/opencode/opencode.json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(sys.argv[1])',
                 json.dumps(settings)])
        resolved = json.loads(capture(['docker', 'exec', self.name, 'opencode', 'debug', 'config']))
        if resolved.get('agent', {}).get('build', {}).get('temperature') != self.c['temperature']:
            raise ValueError('OpenCode temperature configuration did not resolve')
        save(self.directory / 'sampling.json', {'requested_temperature': self.c['temperature'],
             'resolved_build_temperature': resolved['agent']['build']['temperature'],
             'title_disabled': True, 'top_p': 'pinned runtime default',
             'reasoning': 'pinned runtime default; transport qualification records effective value',
             'config_sha256': fingerprint(settings)})

    def phase(self, text, path, session=None):
        sid, history = super().phase(text, path, session)
        expected = sampler(self.c['temperature'])
        actual = json.loads(capture(['docker', 'exec', self.name, 'cat', '/state/config/opencode/opencode.json']))
        save(path / 'sampling-config-after.json', actual)
        # OpenCode adds this metadata field when normalizing its config.
        schema = actual.pop('$schema', None)
        if schema not in (None, 'https://opencode.ai/config.json'):
            raise RuntimeError('Unexpected sampling configuration schema')
        if actual != expected:
            raise RuntimeError('Sampling configuration changed during generation')
        assistants = [m['info'] for m in history['messages'] if m['info']['role'] == 'assistant']
        if not assistants or any(m.get('providerID') != 'google' or m.get('modelID') != 'gemini-3.1-pro-preview' for m in assistants):
            raise RuntimeError('Unexpected exported model identity')
        return sid, history

def smoke(c, t, directory, image):
    directory.mkdir(parents=True, exist_ok=False)
    empty = directory / 'empty-inputs'
    empty.mkdir()
    c = copy.deepcopy(c)
    c.update(inputs=str(empty.resolve()), models=[MODEL], temperature=t)
    a = TemperatureSession(c, MODEL, directory, image)
    result = {'qualified': False, 'temperature': t}
    try:
        a.start()
        phase = directory / 'probe'
        phase.mkdir()
        a.phase('Use bash once to run python -c "print(12345)". Do not inspect files. Then reply READY.', phase)
        agent = json.loads((phase / 'agent.json').read_text())
        if not agent.get('tool_calls'):
            raise ValueError('Readiness did not demonstrate tool use')
        result.update(qualified=True, agent_sha256=digest(phase / 'agent.json'))
    finally:
        a.stop()
        save(directory / 'qualification.json', result)

def initial(c, t, directory, image):
    directory.mkdir(parents=True, exist_ok=False)
    state = {'model': 'google', 'condition': 'initial_only', 'temperature': t,
             'repetition': 0, 'status': 'started', 'started_unix': time.time()}
    save(directory / 'state.json', state)
    c = copy.deepcopy(c)
    c.update(models=[MODEL], temperature=t)
    a = TemperatureSession(c, MODEL, directory, image)
    try:
        a.start()
        phase = directory / 'initial'
        phase.mkdir()
        text = prompts()['generate']
        (phase / 'prompt.txt').write_text(text)
        sid, _ = a.phase(text, phase)
        a.pause()
        original = manifest(a.workspace)
        shutil.copytree(a.workspace, phase / 'workspace')
        if manifest(phase / 'workspace') != original:
            raise RuntimeError('Checkpoint copy mismatch')
        save(phase / 'workspace-manifest.json', original)
        result = Evaluator(c, image)(phase / 'workspace', phase)
        if manifest(phase / 'workspace') != original:
            raise RuntimeError('Evaluator altered checkpoint')
        save(phase / 'checkpoint-manifest.json', manifest(phase))
        save(directory / 'initial-only.json', {
            'condition': 'initial_only', 'model': 'google', 'status': 'completed',
            'shared_initial': False, 'checkpoint': 'initial', 'finished_unix': time.time(),
            'started_unix': state['started_unix'], 'agent_sha256': digest(phase / 'agent.json'),
            'evaluation_sha256': digest(phase / 'evaluation.json'),
            'workspace_manifest_sha256': fingerprint(original), 'repair_metrics': 'not_applicable'})
        state.update(status='completed', session_id=sid)
        if not result.get('conformance', {}).get('report_usable'):
            raise RuntimeError('P21 unavailable; endpoint retained; scheduling stops for adjudication')
    except BaseException as exc:
        state.update(status='failed', reason=str(exc))
        raise
    finally:
        try:
            a.stop()
        finally:
            state['finished_unix'] = time.time()
            save(directory / 'state.json', state)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('smoke', 'freeze', 'run'))
    p.add_argument('--base-config', type=Path, required=True)
    p.add_argument('--qualification', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--env-file', type=Path)
    p.add_argument('--smoke', type=Path)
    p.add_argument('--transport', type=Path, required=True)
    p.add_argument('--lock', type=Path)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    if a.env_file:
        load_env(a.env_file)
    c, payload = current(a.base_config, a.qualification)
    transport = json.loads(a.transport.read_text())
    if transport.get('qualified') is not True or transport.get('tools') != tools():
        raise ValueError('Passing current offline transport qualification required')
    payload['transport_sha256'] = digest(a.transport)
    out = private_path(a.out)
    image = payload['base_seal']['runtime']['image']
    if a.action == 'smoke':
        if not a.execute or not a.env_file:
            p.error('smoke requires --execute and --env-file')
        out.mkdir(parents=True, exist_ok=False)
        for t in TEMPERATURES:
            smoke(c, t, out / str(t), image)
        save(out / 'qualification.json', {'qualified': True, 'tools': tools(), 'transport_sha256': digest(a.transport),
             'evidence': manifest(out)})
        print('All three Gemini nonclinical readiness probes passed.')
        return
    if not a.lock or not a.smoke:
        p.error('--lock and --smoke required')
    receipt = json.loads((a.smoke / 'qualification.json').read_text())
    if not receipt.get('qualified') or receipt.get('tools') != tools():
        raise ValueError('Passing current model readiness required')
    actual = manifest(a.smoke)
    actual.pop('qualification.json', None)
    if actual != receipt['evidence']:
        raise ValueError('Readiness evidence changed')
    payload['readiness_sha256'] = digest(a.smoke / 'qualification.json')
    lock_path = private_path(a.lock)
    if a.action == 'freeze':
        if lock_path.exists():
            raise ValueError('Preserve previous lock')
        save(lock_path, {'payload': payload, 'sha256': fingerprint(payload)})
        print('Excluded Gemini temperature pilot frozen; no clinical generation.')
        return
    if not a.execute or not a.env_file:
        p.error('run requires --execute and --env-file')
    lock = json.loads(lock_path.read_text())
    if lock != {'payload': payload, 'sha256': fingerprint(payload)}:
        raise ValueError('Freeze drift')
    if shutil.disk_usage(out.parent).free < 10 * 1024**3:
        raise ValueError('Less than 10 GiB free; do not start generation')
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'pilot-plan.json', lock)
    guard = out / '.running'
    guard.write_text(str(os.getpid()))
    try:
        for t in payload['order']:
            _, now = current(a.base_config, a.qualification)
            if now != {k: v for k, v in payload.items() if k not in ('transport_sha256', 'readiness_sha256')}:
                raise ValueError('Frozen base drift')
            initial(c, t, out / str(t), image)
    except BaseException as exc:
        save(out / 'interruption.json', {'type': type(exc).__name__, 'reason': str(exc), 'automatic_retry': False})
        raise
    else:
        guard.unlink()
        save(out / 'completed.json', {'main_study_started': False, 'endpoints': 3})

if __name__ == '__main__':
    main()
