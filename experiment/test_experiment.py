import copy
import json
from pathlib import Path
import tempfile
import unittest
import os
import zipfile
import xml.etree.ElementTree as ET

from experiment import Experiment, manifest, report_metrics, save, load_config, load_env


CONFIG = json.loads((Path(__file__).parent / "config.example.json").read_text())


def synthetic_report(path, issues=None, warning=None):
    """Minimal synthetic P21 workbook, containing no actual clinical records."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    summary = [["Configuration: ADaM-IG 1.3 (FDA).xml"], ["Validation Engine Name: FDA 2508.1"],
               ["Software Version: 1.0.9"], ["CDISC ADaM CT Version: 2026-03-27"],
               ["CDISC SDTM CT Version: 2026-03-27"]]
    if warning:
        summary += [["Problems with your Validator installation detected"],
                    ["Problem", "Details", "Link"], [warning, "Synthetic qualification", ""]]
    sheets = {"Validation Summary": summary,
              "Dataset Summary": [["Domain", "Label", "Class", "Source", "Records", "Rejects"],
                                  ["ADSL", "Subjects", "ADAM", "adsl.xpt", 2, 0]],
              "Issue Summary": [["Source", "Pinnacle 21 ID", "Message", "Severity", "Found"]] + (issues or [])}
    book = ET.Element("workbook", xmlns=ns)
    elements = ET.SubElement(book, "sheets")
    relationships = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    with zipfile.ZipFile(path, "w") as z:
        for index, (name, rows) in enumerate(sheets.items(), 1):
            ET.SubElement(elements, "sheet", name=name, sheetId=str(index),
                          attrib={"{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id": f"rId{index}"})
            ET.SubElement(relationships, "Relationship", Id=f"rId{index}", Target=f"worksheets/sheet{index}.xml")
            sheet = ET.Element("worksheet", xmlns=ns)
            data = ET.SubElement(sheet, "sheetData")
            for row_index, values in enumerate(rows, 1):
                row = ET.SubElement(data, "row", r=str(row_index))
                for column, value in enumerate(values):
                    if value is None:
                        continue
                    cell = ET.SubElement(row, "c", r=f"{chr(65 + column)}{row_index}", t="inlineStr")
                    ET.SubElement(ET.SubElement(cell, "is"), "t").text = str(value)
            z.writestr(f"xl/worksheets/sheet{index}.xml", ET.tostring(sheet))
        z.writestr("xl/workbook.xml", ET.tostring(book))
        z.writestr("xl/_rels/workbook.xml.rels", ET.tostring(relationships))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.report = Path(self.temp.name) / "report.xlsx"
        synthetic_report(self.report, [["ADSL"], [None, "AD0018", "Synthetic label finding", None, 3],
                                       [None, "AD0047", "Synthetic missing variable", None, 1]], "MedDRA not configured")

    def tearDown(self):
        self.temp.cleanup()

    def test_sparse_issue_rows_and_qualifications(self):
        pins = ["FDA 2508.1", "1.0.9", "2026-03-27", "ADaM-IG 1.3"]
        baseline = report_metrics(self.report, ["ADSL"], pins)
        final = report_metrics(self.report, ["ADSL"], pins, ["MedDRA not configured"])
        self.assertEqual(baseline["finding_instances"], 4)
        self.assertEqual(baseline["dataset_rule_pairs"], 2)
        self.assertEqual(baseline["distinct_rules"], 2)
        self.assertEqual(final["issues"][0]["dataset"], "ADSL")
        self.assertEqual(final["status"], "valid_qualified")
        self.assertEqual(baseline["status"], "invalid_validation")

    def test_missing_domain_or_wrong_configuration_invalidates_score(self):
        result = report_metrics(self.report, ["ADSL", "ADVS"], ["NOT-A-REAL-ENGINE"])
        self.assertEqual(result["status"], "invalid_validation")
        self.assertEqual(result["missing_configuration_tokens"], ["NOT-A-REAL-ENGINE"])

    def test_unexpected_warning_blocks_scoring(self):
        synthetic_report(self.report, warning="Incompatible CLI")
        result = report_metrics(self.report, ["ADSL"], [], ["MedDRA not configured"])
        self.assertEqual(result["status"], "invalid_validation")

    def test_zero_findings_requires_complete_report(self):
        synthetic_report(self.report)
        result = report_metrics(self.report, ["ADSL"], [])
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["finding_instances"], 0)


class ConfigurationTests(unittest.TestCase):
    def test_env_is_literal_and_does_not_execute_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "env"
            key = "CLINICAL_BENCH_TEST_LITERAL"
            file.write_text(key + "='$(never_execute_this)'\n")
            previous = os.environ.pop(key, None)
            try:
                load_env(file)
                self.assertEqual(os.environ[key], "$(never_execute_this)")
            finally:
                os.environ.pop(key, None)
                if previous is not None:
                    os.environ[key] = previous

    def test_config_expands_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "config.json"
            file.write_text(json.dumps(CONFIG))
            previous = os.environ.get("CLINICAL_BENCH_STUDY_ROOT")
            os.environ["CLINICAL_BENCH_STUDY_ROOT"] = directory
            try:
                self.assertEqual(load_config(file)["study_root"], directory)
            finally:
                if previous is None:
                    os.environ.pop("CLINICAL_BENCH_STUDY_ROOT", None)
                else:
                    os.environ["CLINICAL_BENCH_STUDY_ROOT"] = previous


class MockExperiment(Experiment):
    def __init__(self, config, root):
        super().__init__(config, root)
        self.calls = []
        self.fail_validation = False

    @staticmethod
    def outputs(workspace):
        data = workspace / "output/adam/datasets"
        data.mkdir(parents=True, exist_ok=True)
        (data / "adsl.xpt").write_text("deterministic mock dataset")
        (data / "define.xml").write_text("deterministic mock metadata")
        programs = workspace / "output/adam/programs"
        programs.mkdir(parents=True, exist_ok=True)
        (programs / "rebuild.py").write_text("# mock entrypoint")

    def agent(self, workspace, model, text, stage_dir):
        branch = stage_dir.parent.name
        self.calls.append(branch)
        # Isolation is checked on actual prepared workspaces, not prompt text.
        if branch == "self_review":
            assert not (workspace / "feedback").exists()
            assert not list(workspace.rglob("p21*.xlsx"))
        if branch == "p21_feedback":
            assert (workspace / "feedback/metrics.json").exists()
        self.outputs(workspace)
        return {"exit_code": 0, "seconds": 1, "reported_tokens": None, "reported_cost_usd": None}

    def docker(self, workspace, argv, log, timeout, model=None, network="none"):
        assert network == "none"
        assert not (workspace / "output/adam/datasets").exists()
        self.outputs(workspace)
        log.write_text("mock clean rebuild")
        return {"exit_code": 0, "seconds": 0, "timed_out": False}

    def p21(self, workspace, directory):
        if self.fail_validation:
            return {"status": "failed_validation", "reason": "no fresh report"}
        (directory / "p21_adam.xlsx").write_text("mock report")
        findings = 0 if directory.parent.name == "p21_feedback" else 1
        return {"status": "valid", "finding_instances": findings,
                "dataset_rule_pairs": findings, "distinct_rules": findings,
                "issues": [{"dataset": "ADSL", "rule": "TEST", "findings": 1}] if findings else [],
                "datasets": {"ADSL": {"records": 2, "rejects": 0}}}


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = copy.deepcopy(CONFIG)
        self.config.update({"models": [{"id": "mock", "model": "mock/model", "key_env": []}],
                            "expected_datasets": ["ADSL"], "input_allowlist": ["Input", "SAP.pdf"],
                            "repetitions": 1, "repair_iterations": 1})
        self.exp = MockExperiment(self.config, self.root)
        self.exp.source.mkdir()
        (self.exp.source / "Input").mkdir()
        (self.exp.source / "SAP.pdf").write_text("mock SAP")

    def tearDown(self):
        self.temp.cleanup()

    def test_identical_starts_isolated_feedback_and_resume(self):
        self.exp.run_trial(self.config["models"][0], 1)
        trial = self.root / "runs/mock/run_01"
        starts = [json.loads((trial / b / "iteration_01/starting_output_manifest.json").read_text())
                  for b in ["self_review", "p21_feedback"]]
        self.assertEqual(starts[0], starts[1])
        self.assertEqual(len(self.exp.calls), 3)
        pair = json.loads((self.root / "paired_results.json").read_text())[0]
        self.assertTrue(pair["eligible"])
        self.assertEqual(pair["feedback_advantage_pairs"], 1)
        self.exp.run_trial(self.config["models"][0], 1)
        self.assertEqual(len(self.exp.calls), 3, "Resume must not rerun completed attempts")

    def test_validator_failure_remains_failure_not_zero(self):
        self.exp.fail_validation = True
        self.exp.run_trial(self.config["models"][0], 1)
        result = json.loads((self.root / "runs/mock/run_01/initial/iteration_00/result.json").read_text())
        self.assertEqual(result["status"], "failed_validation")
        self.assertNotIn("finding_instances", result)
        self.assertFalse(json.loads((self.root / "paired_results.json").read_text())[0]["eligible"])

    def test_missing_dataset_fails(self):
        workspace = self.root / "missing"
        workspace.mkdir()
        result = self.exp.evaluate(workspace, self.root)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("finding_instances", result)

    def test_provider_error_stops_before_repair_calls(self):
        calls = []

        def failed_provider(workspace, argv, log, timeout, model=None, network="none"):
            calls.append(network)
            log.write_text(json.dumps({"type": "error", "error": {"name": "APIError"}}) + "\n")
            return {"exit_code": 1, "seconds": 0, "timed_out": False}

        self.exp.docker = failed_provider
        self.exp.agent = Experiment.agent.__get__(self.exp)
        with self.assertRaisesRegex(RuntimeError, "Provider API failed"):
            self.exp.run_trial(self.config["models"][0], 1)
        self.assertEqual(calls, ["bridge"])
        result = json.loads((self.root / "runs/mock/run_01/initial/iteration_00/result.json").read_text())
        self.assertEqual(result["status"], "agent_failed")
        self.assertTrue(result["agent"]["provider_error"])

    def test_partial_stage_cannot_be_silently_retried(self):
        trial = self.root / "runs/mock/run_01"
        (trial / "initial/iteration_00").mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, "Interrupted stage"):
            self.exp.run_trial(self.config["models"][0], 1)

    def test_symlink_outputs_rejected(self):
        data = self.root / "symlink-output"
        data.mkdir()
        (data / "adsl.xpt").symlink_to(self.exp.source / "SAP.pdf")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            manifest(data)

    def test_nondeterministic_rebuild_is_not_eligible(self):
        original = self.exp.docker

        def differing_rebuild(workspace, *args, **kwargs):
            result = original(workspace, *args, **kwargs)
            (workspace / "output/adam/datasets/adsl.xpt").write_text("changed values")
            return result

        self.exp.docker = differing_rebuild
        self.exp.run_trial(self.config["models"][0], 1)
        pair = json.loads((self.root / "paired_results.json").read_text())[0]
        self.assertFalse(pair["eligible"])


if __name__ == "__main__":
    unittest.main()
