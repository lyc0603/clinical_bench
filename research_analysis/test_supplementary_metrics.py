import json
from pathlib import Path
import tempfile
import unittest

from research_analysis.supplementary_metrics import schema_counts, stage_states, tool_evidence


class SupplementaryTests(unittest.TestCase):
    def test_names_and_storage_types_both_required(self):
        result = schema_counts({'A': 'Numeric', 'B': 'Character', 'C': 'Numeric'},
                               {'A': 'Character', 'B': 'Character', 'c': 'Numeric', 'EXTRA': 'Numeric'})
        self.assertEqual(result, {'expected_variables': 3, 'matched_variables': 1,
            'missing_variables': 1, 'wrong_type_variables': 1, 'extra_variables': 2})

    def test_absent_dataset_keeps_entire_denominator(self):
        self.assertEqual(schema_counts({'A': 'Numeric', 'B': 'Character'}, {})['matched_variables'], 0)
        self.assertEqual(schema_counts({'A': 'Numeric', 'B': 'Character'}, {})['expected_variables'], 2)

    def test_blocked_validation_is_not_an_independent_runtime_failure(self):
        tools = dict(input_errors=0, execution_errors=0, available=True, execution_attempts=0)
        with tempfile.TemporaryDirectory() as temp:
            result = stage_states(tools, 0, False, {'conformance': {'failure_code': 'client_runtime_error'}}, Path(temp))
        self.assertEqual(result['dataset_export'], 'failed')
        self.assertEqual(result['rebuilding'], 'blocked')
        self.assertEqual(result['p21_validation'], 'blocked')
        self.assertEqual(result['code_execution'], 'not_observed')

    def test_direct_validator_failure_when_prerequisites_present(self):
        tools = dict(input_errors=0, execution_errors=0, available=False, execution_attempts=0)
        with tempfile.TemporaryDirectory() as temp:
            result = stage_states(tools, 13, True, {'conformance': {'report_usable': False}}, Path(temp))
        self.assertEqual(result['p21_validation'], 'failed')
        self.assertEqual(result['input_reading'], 'unavailable')

    def test_current_phase_dedup_and_unclassified_errors(self):
        events = [
            {'type': 'tool_use', 'part': {'id': 'one', 'tool': 'read', 'state': {'status': 'error', 'input': {'filePath': '/inputs/missing.xpt'}}}},
            {'type': 'tool_use', 'part': {'id': 'two', 'tool': 'glob', 'state': {'status': 'error', 'input': {}}}},
            {'type': 'tool_use', 'part': {'id': 'three', 'tool': 'bash', 'state': {'status': 'completed', 'input': {'command': 'python derive.py'}, 'metadata': {'exit': 1}}}},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'agent.jsonl'
            path.write_text('\n'.join(json.dumps(x) for x in events + [events[0]]))
            result = tool_evidence(path)
        self.assertEqual(result['input_errors'], 1)
        self.assertEqual(result['execution_errors'], 1)
        self.assertEqual(result['unclassified_tool_errors'], 1)


if __name__ == '__main__':
    unittest.main()
