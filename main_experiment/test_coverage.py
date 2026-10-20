import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main_experiment.coverage import compare, profile
from main_experiment.runner import report
from main_experiment.support import save
from main_experiment.test_main import cfg


def evaluation():
    return {'content_profile': {'status': 'available', 'datasets': {'ADSL': {
        'status': 'available', 'rows': 2, 'nonmissing': {'USUBJID': 2, 'AGE': 2},
        'subjects': {'a': 1, 'b': 1}, 'subject_parameters': None}}},
        'correctness': {'checks': [{'check': n, 'status': 'scored', 'assessed': 2, 'errors': 0}
            for n in ('npi_mean_coverage', 'npi_mean_value', 'npi_baseline_covariate')]},
        'deliverables_complete': True, 'conformance': {'report_usable': True,
            'validation_coverage_complete': True, 'dataset_rule_pairs': 3}}


class CoverageTests(unittest.TestCase):
    def test_unchanged_and_improved_checks(self):
        a = evaluation()
        self.assertEqual('no_detected_regression', compare(a, copy.deepcopy(a))['status'])
        a['correctness']['checks'][0]['errors'] = 1
        self.assertEqual('no_detected_regression', compare(a, evaluation())['status'])

    def test_same_size_subject_replacement_and_cleared_values(self):
        a, b = evaluation(), evaluation()
        b['content_profile']['datasets']['ADSL']['subjects'] = {'a': 1, 'c': 1}
        b['content_profile']['datasets']['ADSL']['nonmissing']['AGE'] = 0
        result = compare(a, b)
        self.assertEqual('review_required', result['status'])
        self.assertIn('ADSL:subjects_lost', result['flags'])
        self.assertIn('ADSL:nonmissing_count_decreased:AGE', result['flags'])

    def test_deletions_empty_missing_profiles_and_check_regression(self):
        a, b = evaluation(), evaluation()
        d = b['content_profile']['datasets']['ADSL']
        d['rows'] = 0
        del d['nonmissing']['AGE']
        b['correctness']['checks'][0]['errors'] = 1
        flags = compare(a, b)['flags']
        self.assertIn('ADSL:empty_dataset', flags)
        self.assertIn('ADSL:column_removed:AGE', flags)
        self.assertIn('npi_mean_coverage:independent_check_regression', flags)
        self.assertEqual('unavailable', compare(None, None)['status'])
        del b['correctness']
        self.assertTrue(compare(a, b)['unavailable'])

    def test_profile_detects_blank_strings_and_read_failures(self):
        import pandas as pd
        frame = pd.DataFrame({'USUBJID': ['a', 'b'], 'PARAMCD': ['X', ' '], 'AVAL': [1., None]})
        with patch('pyreadstat.read_xport', return_value=(frame, None)):
            result = profile(Path('/synthetic'), ['ADTEST'])['datasets']['ADTEST']
        self.assertEqual(1, result['nonmissing']['PARAMCD'])
        self.assertEqual(1, len(result['subject_parameters']))
        with patch('pyreadstat.read_xport', side_effect=ValueError('bad')):
            self.assertEqual('unavailable', profile(Path('/synthetic'), ['ADTEST'])['status'])

    def test_reporting_retains_raw_reduction_but_blocks_guarded_improvement(self):
        a, b = evaluation(), evaluation()
        b['conformance']['dataset_rule_pairs'] = 0
        b['content_profile']['datasets']['ADSL']['rows'] = 1
        item = {'workflow': 'w01', 'model': 'openai', 'condition': 'self_review', 'repetition': 1}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save(root/'w01/initial/evaluation.json', a)
            save(root/'w01/final/evaluation.json', b)
            with patch('main_experiment.runner.schedule', return_value=[item]):
                row = report(cfg(), root)[0]
            self.assertEqual(3, row['within_workflow_pair_reduction'])
            self.assertIsNone(row['guarded_pair_reduction'])
            self.assertIsNone(row['improved_without_detected_regression'])
