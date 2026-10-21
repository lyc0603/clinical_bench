import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pre_experiment.report_metrics import METRICS, collect, readable_package


class MissingEvidenceTests(unittest.TestCase):
    def test_file_presence_does_not_certify_readability(self):
        self.assertIsNone(readable_package({'dataset_set_complete': True}))
        profiles = {str(i): {'status': 'available'} for i in range(13)}
        e = {'dataset_set_complete': True, 'content_profile': {'datasets': profiles}}
        self.assertTrue(readable_package(e))
        profiles['0']['status'] = 'unavailable'
        self.assertFalse(readable_package(e))

    def test_unstarted_run_is_not_a_zero_error_success(self):
        with tempfile.TemporaryDirectory() as d:
            result = collect(Path(d), 'google', 'self_review')
        self.assertEqual(len(result['values']), len(METRICS))
        self.assertIn('completed 0/1', result['values'][0])
        self.assertIn('Unavailable', result['values'][7])
        self.assertEqual(result['values'][12], 'Unavailable')

    def test_evaluator_failure_keeps_rebuild_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'final').mkdir()
            (root/'final/evaluation.json').write_text(json.dumps({
                'conformance': None, 'correctness': None,
                'semantic_reproduced': None, 'byte_reproduced': None}))
            result = collect(root, 'google', 'self_review')
        self.assertIn('Unavailable', result['values'][1])
        self.assertIn('validated Unavailable', result['values'][2])
        self.assertIn('pairs Unavailable', result['values'][3])
        self.assertEqual(result['values'][5], 'Unavailable; no usable report')
        self.assertIn('Unavailable', result['values'][9])

    def test_diagnostic_report_does_not_promote_failed_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'final').mkdir()
            source = root/'final/evaluation.json'
            original = json.dumps({'conformance': {'report_usable': False, 'dataset_rule_pairs': None},
                                   'correctness': None, 'semantic_reproduced': None, 'byte_reproduced': None})
            source.write_text(original)
            (root/'final/p21_adam.xlsx').write_bytes(b'placeholder')
            with patch('pre_experiment.report_metrics.report_metrics', return_value={
                'dataset_rule_pairs': 77, 'finding_instances': 1000, 'distinct_rules': 8,
                'report_sha256': 'synthetic'}):
                result = collect(root, 'google', 'self_review')
            self.assertEqual(source.read_text(), original)
        self.assertIsNone(result['numeric']['final']['dataset_rule_pairs'])
        self.assertIsNone(result['numeric']['pair_reduction'])
        self.assertEqual(result['values'][5], 'Unavailable; no usable report')
        self.assertIn('Unqualified observed final: 77 pairs', result['values'][3])


if __name__ == '__main__':
    unittest.main()
