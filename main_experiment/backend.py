"""One Docker container and one OpenCode session per independent workflow."""
import json
import os
from pathlib import Path
import subprocess
import uuid

from experiment.experiment import command, save
from .egress import Egress


def capture(argv, timeout=60):
    return subprocess.run(argv, check=True, capture_output=True, text=True,
                          timeout=timeout).stdout.strip()


def events(path):
    result = []
    for line in Path(path).read_text(errors='replace').splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # Native diagnostics remain in the raw log.
    return result


def telemetry(log):
    rows = events(log)
    sessions = {e.get('sessionID') or e.get('part', {}).get('sessionID') for e in rows}
    sessions.discard(None)
    steps = {}
    tools = {}
    errors = []
    for e in rows:
        part = e.get('part', {})
        if e.get('type') == 'error':
            errors.append(e.get('error', e))
        if e.get('type') == 'step_finish':
            # Part IDs avoid summing re-emitted provider events twice.
            identity = part.get('id')
            if identity:
                steps[identity] = part
        if e.get('type') == 'tool_use' and part.get('id'):
            tools[part['id']] = part
    finishes = [s.get('reason') for s in steps.values()]
    # Unknown telemetry is null, never an invented zero.
    return {'session_ids': sorted(sessions), 'provider_errors': errors,
            'finish_reasons': finishes, 'steps': list(steps.values()),
            'tool_calls': len(tools) if tools else None,
            'tool_failures': sum(p.get('state', {}).get('status') == 'error' for p in tools.values()) if tools else None,
            'terminal': bool(finishes and finishes[-1] in ('stop', 'end_turn')) and not errors}


def message_ids(export):
    messages = export.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('OpenCode export lacks ordered messages')
    ids = [m.get('info', {}).get('id') for m in messages]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError('OpenCode export lacks unique message identities')
    return ids


class DockerSession:
    def __init__(self, c, model, directory, image):
        self.c, self.model, self.directory, self.image = c, model, Path(directory), image
        self.name = 'cb-' + uuid.uuid4().hex
        self.workspace = self.directory / 'live'
        self.egress = Egress(self, capture)

    def start(self):
        self.workspace.mkdir()
        self.egress.start()
        # State is a private named volume, never mounted into controller evaluation.
        self.volume = self.name + '-state'
        capture(['docker', 'volume', 'create', self.volume])
        argv = ['docker', 'run', '-d', '--name', self.name, '--network', 'bridge',
                '--dns', '127.0.0.1', '--cpus', str(self.c['cpus']),
                '--memory', self.c['memory'], '--memory-swap', self.c['memory'],
                '--pids-limit', '256', '--user', f'{os.getuid()}:{os.getgid()}',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '-e', 'HOME=/state', '-e', 'XDG_DATA_HOME=/state/data',
                '-e', 'XDG_CONFIG_HOME=/state/config',
                '-e', 'OPENCODE_CONFIG_CONTENT=' + json.dumps({'permission': {
                    '*': 'allow', 'webfetch': 'deny', 'websearch': 'deny', 'task': 'deny'}, 'enabled_providers': [self.model['model'].split('/')[0]]}),
                '-v', str(Path(self.c['inputs']).resolve()) + ':/inputs:ro',
                '-v', str(self.workspace.resolve()) + ':/workspace',
                '-v', self.volume + ':/state', '-w', '/workspace',
                self.image, 'sleep', 'infinity']
        # Match persistent state ownership to the invoking host UID.
        capture(['docker', 'run', '--rm', '--network', 'none', '-v', self.volume + ':/state',
                 self.image, 'chown', f'{os.getuid()}:{os.getgid()}', '/state'])
        for key, value in self.egress.environment().items():
            argv[3:3] = ['-e', key+'='+value]
        capture(argv)
        self.egress.restrict()
        save(self.directory / 'container.json', {'container': self.name, 'state_volume': self.volume})

    def phase(self, text, path, session=None):
        # Secret VALUE goes only to Docker's environment, never argv/log/config.
        key = self.model['key_env']
        if not os.environ.get(key):
            raise ValueError(f'Missing credential environment variable {key}')
        argv = ['docker', 'exec', '-e', key, self.name, 'opencode', 'run',
                '--format', 'json', '--model', self.model['model']]
        if session:
            argv += ['--session', session]
        argv.append(text)
        result = command(argv, self.directory, path / 'agent.jsonl', self.c['phase_seconds'])
        # A host timeout alone would leave docker exec running. Stop the whole
        # workflow immediately so the active-time budget cannot be exceeded.
        if result['timed_out']:
            capture(['docker', 'stop', '--time', '1', self.name])
        result.update(telemetry(path / 'agent.jsonl'))
        save(path / 'agent.json', result)
        if result['exit_code'] != 0 or result['timed_out'] or not result['terminal']:
            raise RuntimeError('Agent phase failed, timed out, or lacks a recognized terminal event; inspect private log')
        if len(result['session_ids']) != 1 or (session and result['session_ids'] != [session]):
            raise RuntimeError('Session identity mismatch; refusing to fork or continue another session')
        sid = result['session_ids'][0]
        raw = capture(['docker', 'exec', self.name, 'opencode', 'export', sid])
        history = json.loads(raw)
        message_ids(history)
        save(path / 'history.json', history)
        save(path / 'agent.json', result)
        return sid, history

    def pause(self):
        capture(['docker', 'pause', self.name])

    def resume(self):
        capture(['docker', 'unpause', self.name])

    def stop(self):
        subprocess.run(['docker', 'unpause', self.name], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30)
        subprocess.run(['docker', 'stop', '--time', '1', self.name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        self.egress.stop()
        # Retain stopped container, gateway and volume for audit; never retry.
