import json
from pathlib import Path
import tempfile
import unittest

from pre_experiment.report_metrics import METRICS, collect


class MissingEvidenceTests(unittest.TestCase):
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
        self.assertEqual(result['values'][5], 'Unavailable; no usable report')
        self.assertIn('Unavailable', result['values'][9])


if __name__ == '__main__':
    unittest.main()
