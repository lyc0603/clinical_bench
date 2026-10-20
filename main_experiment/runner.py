"""Independent workflow controller. Never retries an uncertain invocation."""
import json
from pathlib import Path
import shutil
import time

from main_experiment.support import manifest, save
from .backend import DockerSession, message_ids
from .core import code_manifest, fingerprint, prompts, schedule, validate_inputs
from .evaluate import Evaluator, runtime
from .coverage import compare


def seal(c):
    return {'input_validation': validate_inputs(c), 'config': c, 'inputs': manifest(Path(c['inputs'])), 'code': code_manifest(),
            'runtime': runtime(c), 'schedule': schedule(c), 'prompts': prompts()}


def verify(c, lock):
    if lock['seal'] != seal(c):
        raise RuntimeError('Frozen inputs, code, config, prompts or runtime changed')
    if lock['sha256'] != fingerprint(lock['seal']):
        raise RuntimeError('Freeze manifest integrity mismatch')


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
            prompt_key = 'generate' if phase == 'initial' else item['condition']
            if phase == 'final' and item['condition'] == 'p21_feedback' and not state['feedback']['report_usable']:
                prompt_key = 'feedback_unavailable'
            text = prompts()[prompt_key]
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
                conformance = result.get('conformance') or {}
                usable = conformance.get('report_usable', False)
                state['feedback'] = {'report_usable': usable,
                    'mode': 'p21_report' if usable else 'self_review_fallback'}
                save(directory / 'state.json', state)
                if not usable:
                    continue
                feedback = agent.workspace / 'feedback'
                if feedback.exists():
                    raise RuntimeError('Unexpected pre-existing feedback directory')
                feedback.mkdir()
                shutil.copy2(checkpoint / 'p21_adam.xlsx', feedback / 'initial_p21.xlsx')
        state.update(status='completed', session_id=sid)
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
        row = dict(item, status=state['status'], reason=state.get('reason'), feedback=state.get('feedback'))
        for phase in ('initial', 'final'):
            evidence = path / phase / 'evaluation.json'
            row[phase] = json.loads(evidence.read_text()) if evidence.exists() else None
        # Independent runs: only initial-to-final differences WITHIN each run.
        initial, final = [row[p] for p in ('initial', 'final')]
        def good(x):
            c = (x or {}).get('conformance') or {}
            return bool(x and x.get('deliverables_complete') and c.get('report_usable') and
                        c.get('validation_coverage_complete') and c.get('dataset_rule_pairs') is not None)
        row['within_workflow_pair_reduction'] = (initial['conformance']['dataset_rule_pairs'] -
            final['conformance']['dataset_rule_pairs']) if good(initial) and good(final) else None
        row['content_guard'] = compare(initial, final)
        reduction = row['within_workflow_pair_reduction']
        row['guarded_pair_reduction'] = (reduction if row['content_guard']['status'] ==
                                        'no_detected_regression' else None)
        row['improved_without_detected_regression'] = (reduction > 0 if reduction is not None and
            row['content_guard']['status'] == 'no_detected_regression' else None)
        rows.append(row)
    groups = {}
    for condition in ('self_review', 'p21_feedback'):
        group = [r for r in rows if r['condition'] == condition]
        finals = [r['final'] for r in group]
        groups[condition] = {
            'planned_denominator': len(group),
            'content_review_required': sum(r['content_guard']['status'] == 'review_required' for r in group),
            'content_guard_unavailable': sum(bool(r['content_guard']['unavailable']) for r in group),
            'improved_without_detected_regression': sum(r['improved_without_detected_regression'] is True for r in group),
            'completed_workflows': sum(r['status'] == 'completed' for r in group),
            'final_deliverables_complete': sum(bool(f and f.get('deliverables_complete')) for f in finals),
            'final_deliverables_unavailable': sum(f is None or 'deliverables_complete' not in f for f in finals),
            'final_report_usable': sum(bool(f and (f.get('conformance') or {}).get('report_usable')) for f in finals),
            'self_review_fallbacks': sum((r.get('feedback') or {}).get('mode') == 'self_review_fallback' for r in group)}
    save(root / 'results.json', {'planned_denominator': 18, 'condition_summary': groups, 'workflows': rows})
    lines = ['# Main experiment status', '', 'All 18 planned workflows are retained. NA means unavailable.', '',
             '| Workflow | Model | Condition | Repeat | Status |', '|---|---|---|---:|---|']
    lines += [f"| {r['workflow']} | {r['model']} | {r['condition']} | {r['repetition']} | {r['status']} |" for r in rows]
    lines += ['', 'See results.json for separate conformance, correctness, coverage and reproduction endpoints.',
              'Condition groups have independent initial generations; do not perform paired condition tests.',
              'Guarded reductions additionally require available content screening and no detected coverage or independent-check regression. Flags require review; raw reductions alone are not effective improvement.',
              'Finding reductions require complete deliverables and full validation coverage at both checkpoints; partial reports are feedback, not evidence of improvement.']
    (root / 'summary.md').write_text('\n'.join(lines)+'\n')
    return rows
