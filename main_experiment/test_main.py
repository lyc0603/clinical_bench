"""Offline synthetic protocol tests. No clinical data, Docker or API keys needed."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiment.experiment import save
from main_experiment.backend import message_ids, telemetry
from main_experiment.core import HERE, assert_protocol, manifest, prompts, schedule
from main_experiment.runner import report, workflow


def cfg():
    return json.loads((HERE / 'config.example.json').read_text())


class FakeSession:
    calls = []
    wrong_session = False

    def __init__(self, c, model, directory, image):
        self.workspace = directory / 'live'

    def start(self):
        self.workspace.mkdir()

    def phase(self, text, path, session=None):
        self.calls.append(session)
        (self.workspace / 'program.txt').write_text('initial' if not session else 'repaired')
        messages = [{'info': {'id': 'm1'}}]
        if session:
            messages += [{'info': {'id': 'm2'}}]
        return 'session-1', {'messages': messages}

    def pause(self):
        pass

    def resume(self):
        pass

    def stop(self):
        pass


def evaluation(work, out):
    (out / 'p21_adam.xlsx').write_bytes(b'synthetic report, not a real workbook')
    value = {'conformance': {'status': 'valid', 'dataset_rule_pairs': 3},
             'correctness': {'complete': True}, 'semantic_reproduced': True}
    save(out / 'evaluation.json', value)
    return value


class ProtocolTests(unittest.TestCase):
    def test_schedule(self):
        c = cfg()
        rows = schedule(c)
        self.assertEqual(18, len(rows))
        self.assertEqual(rows, schedule(c))
        self.assertEqual(18, len({(r['model'], r['condition'], r['repetition']) for r in rows}))
        for condition in ('self_review', 'p21_feedback'):
            self.assertEqual(9, sum(r['condition'] == condition for r in rows))

    def test_reject_drift(self):
        for key, value in [('phase_seconds', 1800), ('phase_seconds', 1801), ('repetitions', 4), ('cpus', 8)]:
            c = cfg(); c[key] = value
            with self.assertRaises(ValueError):
                assert_protocol(c)
        c = cfg(); c['models'][0]['model'] = 'openai/other'
        with self.assertRaises(ValueError):
            assert_protocol(c)

    def test_prompts(self):
        self.assertNotIn('initial_p21.xlsx', prompts()['generate'])
        self.assertIn('2.0.0', prompts()['generate'])
        self.assertNotIn('initial_p21.xlsx', prompts()['self_review'])

    def test_history_requires_unique_ids(self):
        for value in ({}, {'messages': []}, {'messages': [{'info': {'id': 'a'}}, {'info': {'id': 'a'}}]}):
            with self.assertRaises(ValueError):
                message_ids(value)

    def test_telemetry_deduplicates(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'events'
            event = {'type': 'step_finish', 'sessionID': 's', 'part': {'id': 'p', 'reason': 'stop', 'tokens': {'input': 7}}}
            p.write_text('diagnostic\n'+json.dumps(event)+'\n'+json.dumps(event)+'\n')
            result = telemetry(p)
            self.assertTrue(result['terminal'])
            self.assertEqual(1, len(result['steps']))
            self.assertEqual(['s'], result['session_ids'])
            self.assertIsNone(result['tool_calls'])

    def test_error_is_not_completion(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'events'; p.write_text(json.dumps({'type': 'error', 'error': {'name': 'APIError'}}))
            self.assertFalse(telemetry(p)['terminal'])

    def test_both_conditions_use_same_session(self):
        for condition in ('self_review', 'p21_feedback'):
            with tempfile.TemporaryDirectory() as t:
                FakeSession.calls = []
                root = Path(t) / 'workflow'
                item = dict(model='openai', condition=condition, repetition=1, workflow='w01')
                result = workflow(cfg(), item, root, 'image', FakeSession, evaluation)
                self.assertEqual('completed', result['status'])
                self.assertEqual([None, 'session-1'], FakeSession.calls)
                self.assertEqual('initial', (root / 'initial/workspace/program.txt').read_text())
                self.assertEqual('repaired', (root / 'final/workspace/program.txt').read_text())
                self.assertEqual(condition == 'p21_feedback', (root / 'final/workspace/feedback/initial_p21.xlsx').exists())
                with self.assertRaises(RuntimeError):
                    workflow(cfg(), item, root, 'image', FakeSession, evaluation)

    def test_feedback_failure_blocks_repair(self):
        with tempfile.TemporaryDirectory() as t:
            FakeSession.calls = []
            item = dict(model='openai', condition='p21_feedback', repetition=1, workflow='w01')
            workflow(cfg(), item, Path(t)/'run', 'image', FakeSession,
                     lambda *args: {'conformance': {'status': 'unavailable'}})
            self.assertEqual([None], FakeSession.calls)
            self.assertEqual('feedback_unavailable', json.loads((Path(t)/'run/state.json').read_text())['status'])

    def test_history_fork_blocks_success(self):
        class Fork(FakeSession):
            def phase(self, text, path, session=None):
                sid, history = super().phase(text, path, session)
                if session:
                    history['messages'][0]['info']['id'] = 'different'
                return sid, history
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(RuntimeError):
                workflow(cfg(), dict(model='openai', condition='self_review'), Path(t)/'run', 'image', Fork, evaluation)

    def test_all_planned_denominators(self):
        with tempfile.TemporaryDirectory() as t:
            rows = report(cfg(), Path(t))
            self.assertEqual(18, len(rows))
            self.assertTrue(all(r['initial'] is None and r['final'] is None for r in rows))
            self.assertTrue(all(r['within_workflow_pair_reduction'] is None for r in rows))

    def test_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t); (p/'link').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                manifest(p)

    def test_semantic_define_timestamp_only(self):
        from main_experiment.evaluate import semantic
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t)/'a', Path(t)/'b'; a.mkdir(); b.mkdir()
            (a/'define.xml').write_text('<ODM CreationDateTime="one"><Study Name="A"/></ODM>')
            (b/'define.xml').write_text('<ODM CreationDateTime="two"><Study Name="A"/></ODM>')
            self.assertTrue(semantic(a,b))
            (b/'define.xml').write_text('<ODM CreationDateTime="two"><Study Name="B"/></ODM>')
            self.assertFalse(semantic(a,b))


if __name__ == '__main__':
    unittest.main()
