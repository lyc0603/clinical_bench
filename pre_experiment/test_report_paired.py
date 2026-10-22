import json
from pathlib import Path
import tempfile
import unittest

from pre_experiment.report_paired import initial_only


class InitialEndpointTests(unittest.TestCase):
    def test_initial_endpoint_never_inherits_review_cost_or_final_score(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'state.json').write_text(json.dumps({'status':'completed','started_unix':1,'finished_unix':100}))
            (root/'initial-only.json').write_text(json.dumps({'status':'completed','started_unix':1,'finished_unix':11}))
            for phase,pairs,cost in [('initial',8,1.25),('final',3,7.5)]:
                out=root/phase;out.mkdir()
                (out/'evaluation.json').write_text(json.dumps({'deliverables_complete':True,
                    'conformance':{'report_usable':True,'dataset_rule_pairs':pairs,'validation_coverage_complete':True,'issues':[]},
                    'correctness':{'checks':[]}}))
                (out/'agent.json').write_text(json.dumps({'seconds':5,'tool_calls':2,'tool_failures':0,
                    'completion':{'export_usage':[{'message_id':phase,'cost':cost,'tokens':{'input':10,'output':5}}]}}))
            result=initial_only(root,'google')
            self.assertEqual(result['numeric']['terminal']['dataset_rule_pairs'],8)
            self.assertEqual(result['numeric']['terminal']['cost_estimate_usd'],1.25)
            self.assertEqual(result['numeric']['workflow_seconds'],10)
            self.assertIn('Not applicable',result['values'][4])
            self.assertIn('$1.2500',result['values'][12])
            self.assertNotIn('$7.5000',result['values'][12])
            self.assertFalse(any(k.startswith('final/') for k in result['source_sha256']))

    def test_current_reassessment_does_not_rewrite_failed_controller(self):
        from pre_experiment.report_metrics import collect
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'state.json').write_text(json.dumps({'status':'failed'}))
            paths=[]
            for phase in ('initial','final'):
                d=root/phase;d.mkdir()
                (d/'evaluation.json').write_text(json.dumps({'conformance':{'report_usable':False},'deliverables_complete':True}))
                current=root/(phase+'-reassessment.json')
                current.write_text(json.dumps({'report_usable':True,'validation_coverage_complete':True,'dataset_rule_pairs':3,'issues':[]}))
                paths.append(current)
            original=(root/'final/evaluation.json').read_bytes()
            r=collect(root,'openai','self_review',conformance_paths=paths)
            self.assertEqual(r['status'],'failed')
            self.assertEqual(r['numeric']['final']['dataset_rule_pairs'],3)
            self.assertEqual((root/'final/evaluation.json').read_bytes(),original)
            self.assertIn('current_revalidation/final',r['source_sha256'])

    def test_unstarted_initial_only_is_not_completed(self):
        with tempfile.TemporaryDirectory() as t:
            r=initial_only(Path(t),'google')
            self.assertEqual(r['status'],'not_started')
            self.assertIsNone(r['numeric']['terminal']['dataset_rule_pairs'])
            self.assertIsNone(r['numeric']['workflow_seconds'])


if __name__=='__main__':unittest.main()
