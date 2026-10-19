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
    value = {'deliverables_complete': True, 'conformance': {'status': 'valid', 'dataset_rule_pairs': 3,
             'report_usable': True, 'validation_coverage_complete': True},
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

    def test_repair_prompts_only_differ_in_feedback_availability(self):
        repair = prompts()
        feedback_shared, feedback_condition = repair['p21_feedback'].split('\n\n')
        review_shared, review_condition = repair['self_review'].split('\n\n')
        self.assertEqual(feedback_shared, review_shared)
        self.assertIn('Continue this same session.', feedback_shared)
        self.assertIn('no agent execution time limit.', feedback_shared)
        self.assertIn('Do not run Pinnacle 21 or other validators yourself.', feedback_shared)
        self.assertIn('it does not establish analytical correctness.', feedback_shared)
        self.assertEqual(
            'Your initial Pinnacle 21 report is available at\n'
            '/workspace/feedback/initial_p21.xlsx. Use it as additional feedback during your\n'
            'review.\n', feedback_condition)
        self.assertEqual(
            'No external validation feedback is available during your review.\n',
            review_condition)
    def test_all_agent_paths_have_no_execution_time_cap(self):
        self.assertIsNone(cfg()['phase_seconds'])
        rules=json.loads((HERE/'scoring-rules.json').read_text())
        self.assertIn('no agent execution time limit',rules['repair_policy'])
        for key in ('generate','self_review','p21_feedback','feedback_unavailable'):
            with self.subTest(prompt=key):
                self.assertIn('no agent execution time limit',' '.join(prompts()[key].split()))
                self.assertNotRegex(prompts()[key],r'30[- ](?:additional |minute|minutes)|1800')

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

    def test_unavailable_report_still_repairs_both_conditions(self):
        for condition in ('self_review','p21_feedback'):
            with tempfile.TemporaryDirectory() as t:
                FakeSession.calls = []
                item = dict(model='openai', condition=condition, repetition=1, workflow='w01')
                root = Path(t)/'run'
                workflow(cfg(), item, root, 'image', FakeSession,
                         lambda *args: {'conformance': {'status': 'unavailable', 'report_usable': False}})
                self.assertEqual([None,'session-1'], FakeSession.calls)
                self.assertEqual('completed', json.loads((root/'state.json').read_text())['status'])
                self.assertFalse((root/'final/workspace/feedback').exists())
                if condition == 'p21_feedback':
                    prompt=(root/'final/prompt.txt').read_text()
                    self.assertIn('report is unavailable',prompt)
                    self.assertNotIn('reason',prompt)

    def test_partial_report_still_delivered_and_repaired(self):
        with tempfile.TemporaryDirectory() as t:
            FakeSession.calls=[]
            def partial(work,out):
                result=evaluation(work,out)
                result.update(deliverables_complete=False)
                result['conformance'].update(status='valid_partial',validation_coverage_complete=False)
                save(out/'evaluation.json',result)
                return result
            root=Path(t)/'run'
            workflow(cfg(),dict(model='openai',condition='p21_feedback'),root,'image',FakeSession,partial)
            self.assertEqual([None,'session-1'],FakeSession.calls)
            self.assertTrue((root/'final/workspace/feedback/initial_p21.xlsx').exists())
            self.assertEqual('p21_report',json.loads((root/'state.json').read_text())['feedback']['mode'])

    def test_partial_coverage_does_not_become_finding_reduction(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            item=schedule(cfg())[0]
            for phase,count in [('initial',10),('final',1)]:
                value={'deliverables_complete':phase=='initial', 'conformance':{
                    'report_usable':True,'validation_coverage_complete':phase=='initial',
                    'dataset_rule_pairs':count}}
                save(root/item['workflow']/phase/'evaluation.json',value)
            rows=report(cfg(),root)
            self.assertEqual(18,len(rows))
            self.assertIsNone(rows[0]['within_workflow_pair_reduction'])


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
            summary=json.loads((Path(t)/'results.json').read_text())['condition_summary']
            self.assertEqual([9,9],[g['planned_denominator'] for g in summary.values()])
            self.assertEqual([9,9],[g['final_deliverables_unavailable'] for g in summary.values()])

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
