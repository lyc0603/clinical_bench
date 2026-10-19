"""Independent workflow controller. Never retries an uncertain invocation."""
import json
from pathlib import Path
import shutil
import time

from experiment.experiment import manifest, save
from .backend import DockerSession, message_ids
from .core import code_manifest, fingerprint, prompts, schedule, validate_inputs
from .evaluate import Evaluator, runtime


def seal(c):
    return {'input_validation': validate_inputs(c), 'config': c, 'inputs': manifest(Path(c['inputs'])), 'code': code_manifest(),
            'runtime': runtime(c), 'schedule': schedule(c), 'prompts': prompts()}


def verify(c, lock):
    if lock['seal'] != seal(c):
        raise RuntimeError('Frozen inputs, code, config, prompts or runtime changed')
    if lock['sha256'] != fingerprint(lock['seal']):
        raise RuntimeError('Freeze manifest integrity mismatch')


class FeedbackUnavailable(RuntimeError):
    pass


def workflow(c, item, directory, image, backend=DockerSession, evaluator=None):
    directory = Path(directory)
    if directory.exists():
        raise RuntimeError('Attempt already exists; preserve and adjudicate it, never silently retry')
    directory.mkdir(parents=True)
    model = next(m for m in c['models'] if m['id'] == item['model'])
    state = dict(item, status='started', started_unix=time.time())
    save(directory / 'state.json', state)
    agent = backend(c, model, directory, image)
    evaluate = evaluator or Evaluator(c, image)
    try:
        agent.start()
        sid, initial_history = None, None
        for phase in ('initial', 'final'):
            checkpoint = directory / phase
            checkpoint.mkdir()
            text = prompts()['generate' if phase == 'initial' else item['condition']]
            (checkpoint / 'prompt.txt').write_text(text)
            if phase == 'final':
                agent.resume()
            sid, history = agent.phase(text, checkpoint, sid)
            agent.pause()
            if initial_history:
                before, after = message_ids(initial_history), message_ids(history)
                if after[:len(before)] != before or len(after) <= len(before):
                    raise RuntimeError('Repair did not preserve and extend initial session history')
            else:
                initial_history = history
            # Validate all paths BEFORE copytree (which otherwise follows symlinks).
            before_copy = manifest(agent.workspace)
            shutil.copytree(agent.workspace, checkpoint / 'workspace')
            if manifest(checkpoint / 'workspace') != before_copy:
                raise RuntimeError('Checkpoint changed while copying')
            save(checkpoint / 'workspace-manifest.json', before_copy)
            result = evaluate(checkpoint / 'workspace', checkpoint)
            if manifest(checkpoint / 'workspace') != before_copy:
                raise RuntimeError('Evaluator altered checkpoint')
            save(checkpoint / 'checkpoint-manifest.json', manifest(checkpoint))
            if phase == 'initial' and item['condition'] == 'p21_feedback':
                if result['conformance'].get('status') not in ('valid', 'valid_qualified'):
                    raise FeedbackUnavailable('Initial P21 feedback unavailable; repair not invoked')
                feedback = agent.workspace / 'feedback'
                if feedback.exists():
                    raise RuntimeError('Unexpected pre-existing feedback directory')
                feedback.mkdir()
                shutil.copy2(checkpoint / 'p21_adam.xlsx', feedback / 'initial_p21.xlsx')
        state.update(status='completed', session_id=sid)
    except FeedbackUnavailable as exc:
        state.update(status='feedback_unavailable', reason=str(exc), session_id=sid)
    except Exception as exc:
        state.update(status='failed', reason=str(exc))
        raise
    finally:
        try:
            agent.stop()
        finally:
            state['finished_unix'] = time.time()
            save(directory / 'state.json', state)
    return state


def report(c, root):
    root = Path(root)
    rows = []
    for item in schedule(c):
        path = root / item['workflow']
        state = json.loads((path / 'state.json').read_text()) if (path / 'state.json').exists() else {'status': 'not_started'}
        row = dict(item, status=state['status'], reason=state.get('reason'))
        for phase in ('initial', 'final'):
            evidence = path / phase / 'evaluation.json'
            row[phase] = json.loads(evidence.read_text()) if evidence.exists() else None
        # Independent runs: only initial-to-final differences WITHIN each run.
        initial, final = [row[p] for p in ('initial', 'final')]
        good = lambda x: x and x.get('conformance', {}).get('status') in ('valid', 'valid_qualified')
        row['within_workflow_pair_reduction'] = (initial['conformance']['dataset_rule_pairs'] -
            final['conformance']['dataset_rule_pairs']) if good(initial) and good(final) else None
        rows.append(row)
    save(root / 'results.json', {'planned_denominator': 18, 'workflows': rows})
    lines = ['# Main experiment status', '', 'All 18 planned workflows are retained. NA means unavailable.', '',
             '| Workflow | Model | Condition | Repeat | Status |', '|---|---|---|---:|---|']
    lines += [f"| {r['workflow']} | {r['model']} | {r['condition']} | {r['repetition']} | {r['status']} |" for r in rows]
    lines += ['', 'See results.json for separate conformance, correctness, coverage and reproduction endpoints.',
              'Condition groups have independent initial generations; do not perform paired condition tests.']
    (root / 'summary.md').write_text('\n'.join(lines)+'\n')
    return rows
