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

    def test_unstarted_initial_only_is_not_completed(self):
        with tempfile.TemporaryDirectory() as t:
            r=initial_only(Path(t),'google')
            self.assertEqual(r['status'],'not_started')
            self.assertIsNone(r['numeric']['terminal']['dataset_rule_pairs'])
            self.assertIsNone(r['numeric']['workflow_seconds'])


if __name__=='__main__':unittest.main()
