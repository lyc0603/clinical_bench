import copy
import json
from pathlib import Path
import tempfile
import unittest

from main_experiment.core import fingerprint
from main_experiment.test_main import FakeSession, cfg, evaluation
from pre_experiment.paired_pilot import paired_workflow, qualification_valid, tool_manifest
from pre_experiment.qualify_p21 import passing


class PairedPilotTests(unittest.TestCase):
    def test_shared_initial_is_immutable_and_review_extends_same_session(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t)/'pair';FakeSession.calls=[]
            item={'workflow':'pair','model':'google','condition':'self_review','repetition':0}
            paired_workflow(cfg(),item,directory,'image',backend=FakeSession,evaluator=evaluation)
            self.assertEqual(FakeSession.calls,[None,'session-1'])
            self.assertEqual((directory/'initial/workspace/program.txt').read_text(),'initial')
            self.assertEqual((directory/'final/workspace/program.txt').read_text(),'repaired')
            self.assertFalse((directory/'live/feedback').exists())
            receipt=json.loads((directory/'initial-only.json').read_text())
            self.assertEqual(receipt['condition'],'initial_only')
            self.assertEqual(receipt['repair_metrics'],'not_applicable')
            with self.assertRaisesRegex(RuntimeError,'Attempt already exists'):
                paired_workflow(cfg(),item,directory,'image',backend=FakeSession,evaluator=evaluation)

    def test_failed_review_does_not_discard_initial_only_endpoint(self):
        class FailedReview(FakeSession):
            def phase(self,text,path,session=None):
                if session:raise RuntimeError('synthetic review failure')
                return super().phase(text,path,session)
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t)/'pair'
            item={'model':'google','condition':'self_review','repetition':0}
            with self.assertRaisesRegex(RuntimeError,'synthetic review failure'):
                paired_workflow(cfg(),item,directory,'image',backend=FailedReview,evaluator=evaluation)
            self.assertTrue((directory/'initial-only.json').exists())
            self.assertEqual(json.loads((directory/'state.json').read_text())['status'],'failed')

    def test_initial_p21_failure_stops_before_paid_review_and_retains_endpoint(self):
        def unavailable(work,out):
            result=evaluation(work,out)
            result['conformance']['report_usable']=False
            (out/'evaluation.json').write_text(json.dumps(result))
            return result
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t)/'pair';FakeSession.calls=[]
            with self.assertRaisesRegex(RuntimeError,'scheduling stopped'):
                paired_workflow(cfg(),{'model':'google','condition':'self_review'},directory,'image',backend=FakeSession,evaluator=unavailable)
            self.assertEqual(FakeSession.calls,[None])
            self.assertTrue((directory/'initial-only.json').exists())

    def test_qualification_rejects_missing_coverage_drift_and_failed_checks(self):
        current={'config':cfg()}
        checks=[{'model':m['id'],'condition':c,'phase':p,'qualified':True}
                for m in cfg()['models'] for c in ('self_review','p21_feedback') for p in ('initial','final')]
        valid={'schema':'paired-p21-qualification-v1','qualified':True,'seal_sha256':fingerprint(current),
               'tools':tool_manifest(),'checks':checks}
        qualification_valid(valid,current)
        for mutate in (lambda r:r['checks'].pop(),lambda r:r.update(seal_sha256='old'),
                       lambda r:r.update(tools={}),lambda r:r['checks'][0].update(qualified=False)):
            r=copy.deepcopy(valid);mutate(r)
            with self.assertRaises(ValueError):qualification_valid(r,current)

    def test_parseable_or_inconsistent_reports_do_not_pass_qualification(self):
        run={'validator_accepted':True,'unqualified_report':{'dataset_rule_pairs':3}}
        summary={'source_datasets_and_cache_unchanged':True,'pairsets_equal':True,'repeats':[copy.deepcopy(run),copy.deepcopy(run)]}
        self.assertTrue(passing(summary))
        summary['repeats'][1]['validator_accepted']=False
        self.assertFalse(passing(summary))
        summary['repeats'][1]['validator_accepted']=True
        summary['repeats'][1]['unqualified_report']['dataset_rule_pairs']=4
        self.assertFalse(passing(summary))


if __name__=='__main__':
    unittest.main()
