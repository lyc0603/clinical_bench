#!/usr/bin/env python3
"""Isolated, resumable generation / self-review / P21-feedback experiment.

Host orchestration uses only Python's standard library. Agent code executes in
Docker; P21 executes on the host using the existing qualified local installation.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import posixpath
import random
import shutil
import subprocess
import time
import tempfile
import uuid
import zipfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def manifest(root):
    if root.is_symlink():
        raise ValueError(f"Symlink not allowed in evidence: {root}")
    result = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError(f"Symlink not allowed in evidence: {p}")
        if p.is_file():
            result[str(p.relative_to(root))] = digest(p)
    return result


def command(argv, cwd, log, timeout, env=None):
    start = time.monotonic()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:
        try:
            proc = subprocess.run(argv, cwd=cwd, env=env, stdout=f,
                                  stderr=subprocess.STDOUT, timeout=timeout)
            return {"exit_code": proc.returncode, "seconds": time.monotonic() - start,
                    "timed_out": False}
        except subprocess.TimeoutExpired:
            return {"exit_code": None, "seconds": time.monotonic() - start,
                    "timed_out": True}


def xlsx_rows(path):
    """Read sparse XLSX cells including shared strings, without openpyxl."""
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            for item in ET.fromstring(z.read("xl/sharedStrings.xml")):
                strings.append("".join(t.text or "" for t in item.findall(".//s:t", NS)))
        relationships = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in relationships}
        book = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = {}
        for sheet in book.find("s:sheets", NS):
            rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = targets[rid]
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            rows = []
            for row in ET.fromstring(z.read(target)).findall(".//s:sheetData/s:row", NS):
                values = []
                for cell in row.findall("s:c", NS):
                    letters = "".join(c for c in cell.get("r", "") if c.isalpha())
                    column = 0
                    for letter in letters:
                        column = column * 26 + ord(letter.upper()) - 64
                    while len(values) < column:
                        values.append(None)
                    v = cell.find("s:v", NS)
                    value = v.text if v is not None else None
                    if cell.get("t") == "s":
                        value = strings[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                    values[column - 1] = value
                rows.append(values)
            sheets[sheet.get("name")] = rows
        return sheets


def report_metrics(path, expected, pins, allowed_qualifications=()):
    sheets = xlsx_rows(path)
    summary = "\n".join(str(v) for row in sheets["Validation Summary"] for v in row if v)
    issues, domain = [], None
    header_seen = False
    for row in sheets["Issue Summary"]:
        row = row + [None] * (5 - len(row))
        if row[1] == "Pinnacle 21 ID":
            header_seen = True
            continue
        if not header_seen:
            continue
        if row[0]:
            domain = row[0]
        if row[1]:
            issues.append({"dataset": domain, "rule": row[1], "message": row[2],
                           "severity": row[3] or "Unassigned", "findings": int(float(row[4]))})
    if not header_seen:
        raise ValueError("Unrecognized Issue Summary format")
    datasets = {}
    for row in sheets["Dataset Summary"]:
        if len(row) >= 6 and str(row[3]).lower().endswith(".xpt") and str(row[0]).upper().startswith("AD"):
            datasets[str(row[0]).upper()] = {"records": int(float(row[4])),
                                           "rejects": int(float(row[5]))}
    mismatches = [token for token in pins if token not in summary]
    warning = "problems with your validator installation" in summary.lower()
    problems, in_problems = [], False
    for row in sheets["Validation Summary"]:
        if row and row[0] == "Problem":
            in_problems = True
            continue
        if in_problems and row and row[0]:
            problems.append(row[0])
    warning_allowed = warning and bool(problems) and all(p in allowed_qualifications for p in problems)
    valid = set(datasets) == set(expected) and (not warning or warning_allowed) and not mismatches
    status = "valid_qualified" if valid and warning else "valid" if valid else "invalid_validation"
    return {"status": status,
            "finding_instances": sum(i["findings"] for i in issues),
            "distinct_rules": len({i["rule"] for i in issues}),
            "dataset_rule_pairs": len({(i["dataset"], i["rule"]) for i in issues}),
            "datasets": datasets, "issues": issues, "installation_warning": warning,
            "qualification_problems": problems,
            "missing_configuration_tokens": mismatches, "validation_summary": summary,
            "report_sha256": digest(path)}


def prompt(config, stage, branch):
    common = (
        "You are a clinical statistical programming agent. Use only the supplied study files "
        "and your knowledge; do not browse, call other agents/models, or search for solutions. "
        "Inputs and documents are read-only under /inputs, with links in /workspace. "
        "Generate Python production programs and ADaM XPT datasets plus Define-XML 2.1. "
        "Use ADaMIG 1.3, ADaM Model 2.1 and CT " + config["p21"]["ct"] + ". "
        "Required datasets: " + ", ".join(config["expected_datasets"]) + ". "
        "Write datasets and define.xml in output/adam/datasets. Write a single entrypoint "
        "output/adam/programs/rebuild.py that rebuilds ALL datasets and metadata from source "
        "when called with python. Resolve paths relative to this workspace, not your home. "
        "Use fixed creation timestamps so rebuilding produces identical artifact bytes. "
        "Do not install packages: available libraries are preinstalled in the image. "
        "Do not remove required datasets, discard records, clear values, or fabricate source "
        "values just to suppress findings. Document unresolved decisions. Maintain notes.md "
        "with decisions and changes so a fresh session can continue. Do not run P21 yourself. "
        "Finish by running your rebuild entrypoint. "
    )
    if stage == 0:
        return common + "Build the complete initial package using SDTM, SAP, and supplied metadata."
    if branch == "self_review":
        return common + "Review and improve the existing package using source documents, data, code, notes, and execution logs. No external validation feedback is provided."
    return common + "Review and repair the existing package. Read feedback/p21_adam.xlsx and feedback/metrics.json for the preceding package's P21 findings. Diagnose findings and modify production code and metadata consistently."


class Experiment:
    def __init__(self, config, root):
        self.cfg, self.root = config, root
        self.source = root / "frozen_inputs"
        self.models = {m["id"]: m for m in config["models"]}
        self.image = config["agent"]["image"]

    def preflight(self):
        c = self.cfg
        ids = [m["id"] for m in c["models"]]
        if len(ids) != len(set(ids)):
            raise ValueError("Model IDs must be unique")
        for m in c["models"]:
            if not m["id"].replace("_", "").replace("-", "").isalnum():
                raise ValueError("Model IDs may contain only letters, digits, _ and -")
            if "REPLACE" in m["model"]:
                raise ValueError("Replace example model IDs before running")
            for key in m.get("key_env", []):
                if not os.environ.get(key):
                    raise ValueError(f"Missing environment variable {key}")
        if c["repetitions"] < 1 or c["repair_iterations"] < 1:
            raise ValueError("Repetitions and repair iterations must be positive")
        subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, check=True)
        image = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", self.image], text=True).strip()
        p = c["p21"]
        cache = Path(p["cache"])
        files = [Path(p["java"]), cache / "lib/p21-client-1.0.9.jar",
                 cache / "configs/2508.1/ADaM-IG 1.3 (FDA).xml"]
        for f in files:
            if not f.is_file():
                raise ValueError(f"Missing P21 runtime file: {f}")
        # Pin the actual image ID and cache content, not a mutable tag alone.
        cache_manifest = {"jar": digest(files[1]), "configs": manifest(cache / "configs"),
                          "engines": manifest(cache / "lib/engines")}
        save(self.root / "environment.json", {"image_id": image, "p21_runtime": cache_manifest,
                                              "java_sha256": digest(Path(p["java"]))})
        self.image = image
        # Check model IDs without sending any study material or inference prompt.
        for model in c["models"]:
            provider = model["model"].split("/", 1)[0]
            argv = ["docker", "run", "--rm", "-e", "HOME=/tmp/agent-home"]
            for key in model.get("key_env", []):
                argv += ["-e", key]
            argv += [image, "opencode", "models", provider]
            catalog = subprocess.run(argv, capture_output=True, text=True, timeout=120)
            if catalog.returncode != 0 or model["model"] not in catalog.stdout.splitlines():
                raise ValueError(f"Model ID not available in the pinned agent catalog: {model['model']}. Verify the exact API model ID; do not silently substitute a CLI default.")

    def freeze(self):
        study = Path(self.cfg["study_root"])
        self.source.mkdir(parents=True)
        for name in self.cfg["input_allowlist"]:
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Input allowlist must contain relative paths")
            src, dst = study / relative, self.source / relative
            if src.is_symlink():
                raise ValueError(f"Source symlink is not permitted: {src}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        save(self.root / "input_manifest.json", manifest(self.source))

    def workspace(self, path, previous=None):
        path.mkdir(parents=True)
        if previous:
            allowed = {str(Path(name)): "/inputs/" + name for name in self.cfg["input_allowlist"]}
            for entry in previous.rglob("*"):
                if entry.is_symlink():
                    name = str(entry.relative_to(previous))
                    if allowed.get(name) != os.readlink(entry):
                        raise ValueError(f"Unexpected agent-created symlink: {name}")
            shutil.copytree(previous, path, dirs_exist_ok=True, symlinks=True)
        # Only these known links point to the read-only mount. Other symlinks
        # are rejected before scoring/copying evidence.
        for name in self.cfg["input_allowlist"]:
            dest = path / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_symlink():
                dest.unlink()
            elif dest.exists():
                raise ValueError(f"Unexpected writable input: {dest}")
            dest.symlink_to("/inputs/" + name, target_is_directory=(self.source / name).is_dir())

    def docker(self, workspace, argv, log, timeout, model=None, network="none"):
        name = "adam-exp-" + uuid.uuid4().hex[:12]
        inputs_volume, work_volume = name + "-inputs", name + "-work"
        loader = name + "-loader"
        cmd = ["docker", "create", "--name", name, "--init", "--cap-drop=ALL",
               "--security-opt=no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
               "--cpus", str(self.cfg["agent"]["cpus"]), "--memory", self.cfg["agent"]["memory"],
               "--pids-limit", "256", "--network", network, "-e", "HOME=/tmp/agent-home",
               "-e", "OPENCODE_CONFIG_CONTENT=" + json.dumps({"permission": {
                   "*": "allow", "webfetch": "deny", "websearch": "deny", "task": "deny",
                   "external_directory": "allow"}}),
               "--mount", f"type=volume,src={work_volume},dst=/workspace",
               "--mount", f"type=volume,src={inputs_volume},dst=/inputs,readonly", "-w", "/workspace"]
        if model:
            for key in model.get("key_env", []):
                cmd += ["-e", key]  # Pass names only; never put key values in saved config.
        cmd += [self.image] + argv
        created = False
        try:
            # XPT readers/writers issue many small operations. Keep execution
            # on Docker-local storage rather than macOS shared mount paths.
            for volume in (inputs_volume, work_volume):
                subprocess.run(["docker", "volume", "create", volume], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["docker", "create", "--name", loader, "--network", "none",
                            "--mount", f"type=volume,src={inputs_volume},dst=/inputs",
                            "--mount", f"type=volume,src={work_volume},dst=/workspace",
                            self.image, "chown", "-R", f"{os.getuid()}:{os.getgid()}", "/workspace"], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["docker", "cp", str(self.source) + "/.", loader + ":/inputs"], check=True)
            subprocess.run(["docker", "cp", str(workspace) + "/.", loader + ":/workspace"], check=True)
            subprocess.run(["docker", "start", "-a", loader], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            created = True
            return command(["docker", "start", "-a", name], self.root, log, timeout)
        finally:
            try:
                if created:
                    subprocess.run(["docker", "stop", "-t", "1", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    # Preserve even partially generated evidence after a timeout.
                    returned = workspace.with_name(workspace.name + "-returned-" + uuid.uuid4().hex[:8])
                    returned.mkdir()
                    subprocess.run(["docker", "cp", name + ":/workspace/.", str(returned)], check=True)
                    # Replace rather than merge: agent deletions must survive.
                    shutil.rmtree(workspace)
                    returned.rename(workspace)
            finally:
                subprocess.run(["docker", "rm", "-f", name, loader], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["docker", "volume", "rm", work_volume, inputs_volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def agent(self, workspace, model, text, stage_dir):
        (stage_dir / "prompt.txt").write_text(text)
        argv = [arg.replace("{model}", model["model"]).replace("{prompt}", text)
                for arg in self.cfg["agent"]["command"]]
        result = self.docker(workspace, argv, stage_dir / "agent.jsonl",
                             self.cfg["agent"]["timeout_seconds"], model, "bridge")
        # OpenCode reports completed-step usage; missing instrumentation stays null.
        tokens, cost, seen = 0, 0.0, False
        provider_error = False
        for line in (stage_dir / "agent.jsonl").read_text(errors="replace").splitlines():
            try:
                event = json.loads(line)
                if event.get("type") == "error" and event.get("error", {}).get("name") in {"APIError", "ProviderAuthError"}:
                    provider_error = True
                part = event.get("part", {})
                if event.get("type") == "step_finish" and isinstance(part.get("tokens"), dict):
                    t = part["tokens"]
                    tokens += sum(t.get(k, 0) or 0 for k in ["input", "output", "reasoning"])
                    cache = t.get("cache", {})
                    tokens += (cache.get("read", 0) or 0) + (cache.get("write", 0) or 0)
                    cost += part.get("cost", 0) or 0
                    seen = True
            except (ValueError, TypeError):
                pass
        result.update({"provider_error": provider_error,
                       "reported_tokens": tokens if seen else None,
                       "reported_cost_usd": cost if seen else None,
                       "budget_note": "Fixed wall-time per call; token totals are recorded, not hard-capped."})
        return result

    def evaluate(self, workspace, directory):
        dataset = workspace / "output/adam/datasets"
        expected = set(self.cfg["expected_datasets"])
        actual = {p.stem.upper() for p in dataset.glob("*.xpt")}
        result = {"status": "failed", "expected_datasets": sorted(expected),
                  "actual_datasets": sorted(actual), "reproduced": False}
        if actual != expected or not (dataset / "define.xml").is_file():
            result["reason"] = "Missing/extra datasets or missing Define-XML"
            return result
        before = manifest(dataset)
        replay = directory / "replay"
        self.workspace(replay, workspace)
        # Delete ALL generated outputs, preserving only programs and agent notes.
        output = replay / "output/adam"
        for child in list(output.iterdir()):
            if child.name != "programs":
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        rebuild = self.docker(replay, ["python", "output/adam/programs/rebuild.py"],
                              directory / "rebuild.log", self.cfg["rebuild_timeout_seconds"])
        result["rebuild"] = rebuild
        result["reproduced"] = rebuild["exit_code"] == 0 and manifest(replay / "output/adam/datasets") == before
        result["reproducibility_definition"] = "Exact dataset and Define-XML byte hashes; timestamp differences also fail."
        result.update(self.p21(workspace, directory))
        if self.cfg.get("derivation_checks"):
            from derivation import score
            save(directory / "derivation.json", score(self.source, dataset))
        result["dataset_manifest"] = before
        return result

    def p21(self, workspace, directory):
        cache = Path(self.cfg["p21"]["cache"])
        if not self.cfg.get("protocol_lock"):
            return self._p21(workspace, directory, cache)
        # P21 writes engine bookkeeping during validation. Give each call a
        # disposable cache so canonical pinned binaries/rules remain unchanged.
        with tempfile.TemporaryDirectory(prefix=".p21-runtime-", dir=directory) as temp:
            isolated = Path(temp) / "cache"
            shutil.copytree(cache, isolated)
            before = {"jar": digest(isolated / "lib/p21-client-1.0.9.jar"),
                      "configs": manifest(isolated / "configs"),
                      "engines": manifest(isolated / "lib/engines")}
            result = self._p21(workspace, directory, isolated)
            after = {"jar": digest(isolated / "lib/p21-client-1.0.9.jar"),
                     "configs": manifest(isolated / "configs"),
                     "engines": manifest(isolated / "lib/engines")}
            bookkeeping_changed = before["engines"].get("app.data") != after["engines"].get("app.data")
            # Only the engine index state is writable; binaries and rules must match.
            before["engines"].pop("app.data", None)
            after["engines"].pop("app.data", None)
            result["p21_runtime_unchanged"] = before == after
            result["p21_bookkeeping_changed"] = bookkeeping_changed
            if before != after:
                result.update(status="invalid_runtime", reason="P21 binaries/rules changed during validation")
            return result

    def _p21(self, workspace, directory, cache):
        p = self.cfg["p21"]
        data = workspace / "output/adam/datasets"
        report = directory / "p21_adam.xlsx"
        if report.exists():
            raise ValueError("Refusing to reuse an existing P21 report")
        # Supporting SDTM is intentionally fixed to match your previous runs.
        support = directory / "p21_support"
        support.mkdir()
        for dom in p["support_domains"]:
            shutil.copy2(self.source / "Input" / f"{dom.lower()}.xpt", support / f"{dom.lower()}.xpt")
        argv = [p["java"], "-jar", str(cache / "lib/p21-client-1.0.9.jar"),
                "--engine.version=FDA 2508.1", "--engine.folder=" + str(cache / "lib/engines"),
                "--standard=adam", "--standard.version=1.3", "--config=" + str(cache / "configs"),
                "--source.define=" + str(data / "define.xml"), "--source.adam=" + str(data),
                "--source.sdtm=" + str(support), "--cdisc.ct.adam.version=" + p["ct"],
                "--cdisc.ct.sdtm.version=" + p["ct"], "--report=" + str(report)]
        execution = command(argv, cache, directory / "p21.log", p["timeout_seconds"])
        if execution["timed_out"] or not report.exists():
            return {"status": "failed_validation", "reason": "P21 timeout or no fresh report",
                    "p21_execution": execution}
        metrics = report_metrics(report, self.cfg["expected_datasets"],
                                 ["FDA 2508.1", "1.0.9", p["ct"], "ADaM-IG 1.3"],
                                 p.get("allowed_qualifications", []))
        metrics["p21_execution"] = execution  # Exit 5 may still yield completed reports.
        return metrics

    def stage(self, trial, model, branch, index, previous):
        stage = trial / branch / f"iteration_{index:02d}"
        if (stage / "result.json").exists():
            return stage / "workspace", json.loads((stage / "result.json").read_text())
        if stage.exists():
            # Never retry a partially executed trial silently.
            raise RuntimeError(f"Interrupted stage retained at {stage}; adjudicate it before retrying")
        if self.cfg.get("protocol_lock"):
            from protocol_lock import verify, verify_environment
            locked = verify(self.cfg)
            cache = Path(self.cfg["p21"]["cache"])
            current = {"image_id": self.image, "p21_runtime": {
                "jar": digest(cache / "lib/p21-client-1.0.9.jar"),
                "configs": manifest(cache / "configs"), "engines": manifest(cache / "lib/engines")},
                "java_sha256": digest(Path(self.cfg["p21"]["java"]))}
            verify_environment(locked, current)
        stage.mkdir(parents=True)
        workspace = stage / "workspace"
        self.workspace(workspace, previous)
        feedback = workspace / "feedback"
        if feedback.exists():
            shutil.rmtree(feedback)
        if branch == "p21_feedback":
            preceding = previous.parent
            feedback.mkdir()
            if (preceding / "p21_adam.xlsx").exists():
                shutil.copy2(preceding / "p21_adam.xlsx", feedback / "p21_adam.xlsx")
            shutil.copy2(preceding / "result.json", feedback / "metrics.json")
        start_manifest = manifest(workspace / "output") if (workspace / "output").exists() else {}
        save(stage / "starting_output_manifest.json", start_manifest)
        agent_result = self.agent(workspace, model, prompt(self.cfg, index, branch), stage)
        try:
            if agent_result["exit_code"] != 0:
                result = {"status": "agent_failed", "reproduced": False}
            else:
                result = self.evaluate(workspace, stage)
        except Exception as exc:
            result = {"status": "evaluation_failed", "reason": str(exc), "reproduced": False}
        result["agent"] = agent_result
        save(stage / "result.json", result)
        self.summarize()
        if agent_result.get("provider_error"):
            raise RuntimeError("Provider API failed; pilot stopped. Check private agent log and account access before starting a new run.")
        return workspace, result

    def run_trial(self, model, repetition):
        trial = self.root / "runs" / model["id"] / f"run_{repetition:02d}"
        initial, _ = self.stage(trial, model, "initial", 0, None)
        branches = ["self_review", "p21_feedback"]
        random.Random(self.cfg["seed"] + repetition).shuffle(branches)
        for branch in branches:
            previous = initial
            for index in range(1, self.cfg["repair_iterations"] + 1):
                # Both branches receive the full number of iterations. No
                # stopping based on hidden scores; fresh agent session each time.
                previous, _ = self.stage(trial, model, branch, index, previous)

    def summarize(self):
        rows = []
        for file in sorted((self.root / "runs").glob("*/*/*/iteration_*/result.json")):
            model, rep, branch, iteration = file.relative_to(self.root / "runs").parts[:4]
            value = json.loads(file.read_text())
            agent = value.get("agent", {})
            rows.append({"model": model, "run": rep, "branch": branch, "iteration": iteration,
                         "status": value["status"], "reproduced": value.get("reproduced"),
                         "finding_instances": value.get("finding_instances"),
                         "dataset_rule_pairs": value.get("dataset_rule_pairs"),
                         "distinct_rules": value.get("distinct_rules"),
                         "records": sum(d["records"] for d in value.get("datasets", {}).values()) if "datasets" in value else None,
                         "agent_seconds": agent.get("seconds"), "tokens": agent.get("reported_tokens"),
                         "cost_usd": agent.get("reported_cost_usd")})
        if rows:
            with (self.root / "results.csv").open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        pairs = []
        for model in self.models:
            for rep in range(1, self.cfg["repetitions"] + 1):
                trial = self.root / "runs" / model / f"run_{rep:02d}"
                paths = [trial / "initial/iteration_00/result.json"] + [
                    trial / branch / f"iteration_{self.cfg['repair_iterations']:02d}/result.json"
                    for branch in ["self_review", "p21_feedback"]]
                if not all(p.exists() for p in paths):
                    continue
                initial, control, feedback = [json.loads(p.read_text()) for p in paths]
                eligible = all(v["status"] in ["valid", "valid_qualified"] and v.get("reproduced") for v in [initial, control, feedback])
                eligible = eligible and all(v.get("qualification_problems", []) == initial.get("qualification_problems", []) for v in [control, feedback])
                pair = {"model": model, "run": rep, "eligible": eligible}
                if eligible:
                    pair.update({"self_review_pair_reduction": initial["dataset_rule_pairs"] - control["dataset_rule_pairs"],
                                 "p21_pair_reduction": initial["dataset_rule_pairs"] - feedback["dataset_rule_pairs"],
                                 "feedback_advantage_pairs": control["dataset_rule_pairs"] - feedback["dataset_rule_pairs"],
                                 "record_count_changes": {branch: {d: val["datasets"][d]["records"] - initial["datasets"][d]["records"] for d in initial["datasets"]}
                                                          for branch, val in [("self_review", control), ("p21_feedback", feedback)]},
                                 "new_dataset_rule_pairs": {branch: sorted([list(k) for k in
                                     {(i["dataset"], i["rule"]) for i in val["issues"]} -
                                     {(i["dataset"], i["rule"]) for i in initial["issues"]}])
                                     for branch, val in [("self_review", control), ("p21_feedback", feedback)]}})
                pairs.append(pair)
        save(self.root / "paired_results.json", pairs)
        lines = ["# Experiment results", "", "Scope: P21 ADaM conformance; not analytical correctness.", "",
                 "| Model | Completed pairs | Eligible pairs | Mean feedback advantage (dataset-rule pairs) |",
                 "|---|---:|---:|---:|"]
        for model in self.models:
            group = [p for p in pairs if p["model"] == model]
            good = [p for p in group if p["eligible"]]
            average = f"{sum(p['feedback_advantage_pairs'] for p in good) / len(good):.2f}" if good else "NA"
            lines.append(f"| {model} | {len(group)} | {len(good)} | {average} |")
        lines += ["", "Positive advantage means fewer final dataset-rule pairs in the P21-feedback branch.",
                  "Ineligible attempts remain in results.csv; do not treat eligible-only averages as overall success rates.",
                  "Record-count changes and new findings are retained in paired_results.json for review."]
        if self.cfg.get("derivation_checks"):
            derivation_rows = []
            for file in sorted((self.root / "runs").glob("*/*/*/iteration_*/result.json")):
                model, rep, branch, iteration = file.relative_to(self.root / "runs").parts[:4]
                evidence = file.parent / "derivation.json"
                checks = json.loads(evidence.read_text())["checks"] if evidence.exists() else [
                    {"check": "evaluation", "status": "unavailable", "assessed": None,
                     "errors": None, "reason": "No independent derivation result"}]
                for c in checks:
                    derivation_rows.append(dict(model=model, run=rep, branch=branch,
                        iteration=iteration, check=c["check"], status=c["status"],
                        assessed=c.get("assessed"), errors=c.get("errors"),
                        qualification=c.get("qualification", c.get("reason", ""))))
            if derivation_rows:
                with (self.root / "derivation_results.csv").open("w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(derivation_rows[0]))
                    writer.writeheader()
                    writer.writerows(derivation_rows)
            if self.cfg.get("protocol_lock"):
                from derivation import paired_results
                save(self.root / "derivation_paired_results.json", paired_results(self.cfg, self.root))
            lines += ["", "Independent derivation results are reported separately in derivation_results.csv.",
                      "No combined conformance/correctness score. Unavailable checks are not zero-error results."]
        (self.root / "summary.md").write_text("\n".join(lines) + "\n")


def load_config(path):
    """Resolve environment placeholders without saving credentials."""
    config = json.loads(path.read_text())
    for container, key in [(config, "study_root"), (config["p21"], "java"), (config["p21"], "cache")]:
        container[key] = os.path.expandvars(os.path.expanduser(container[key]))
    return config


def load_env(path):
    """Load literal KEY=value entries without shell execution or interpolation."""
    if not path.exists():
        return
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key.isidentifier():
            raise ValueError(f"Invalid environment entry on line {number}; expected KEY=value")
        if value[:1] in ["'", '"']:
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed quote on environment line {number}")
            value = value[1:-1]
        if value and not os.environ.get(key):
            os.environ[key] = value


def doctor(config):
    """Read-only diagnostics; never calls a model or launches P21."""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "ready": bool(ok), "detail": detail})

    study = Path(config["study_root"])
    for name in config["input_allowlist"]:
        add("input:" + name, (study / name).exists(), str(study / name))
    docker_bin = shutil.which("docker")
    add("docker_cli", docker_bin is not None, docker_bin or "Install Docker/OrbStack")
    if docker_bin:
        try:
            result = subprocess.run([docker_bin, "info", "--format", "{{.ServerVersion}}"],
                                    capture_output=True, text=True, timeout=15)
            add("docker_engine", result.returncode == 0, result.stdout.strip() or "Start your Docker engine")
            image = subprocess.run([docker_bin, "image", "inspect", config["agent"]["image"]],
                                   capture_output=True, text=True, timeout=15)
            add("agent_image", image.returncode == 0, config["agent"]["image"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            add("docker_engine", False, type(exc).__name__)
    cache = Path(config["p21"]["cache"])
    for name, path in [("p21_java", Path(config["p21"]["java"])),
                       ("p21_client", cache / "lib/p21-client-1.0.9.jar"),
                       ("p21_configuration", cache / "configs/2508.1/ADaM-IG 1.3 (FDA).xml")]:
        add(name, path.is_file(), str(path))
    for model in config["models"]:
        add("model:" + model["id"], "REPLACE" not in model["model"], model["model"])
        for key in model.get("key_env", []):
            add("credential:" + key, bool(os.environ.get(key)), "Present" if os.environ.get(key) else "Not set; never paste keys into chat")
    return {"ready": all(c["ready"] for c in checks), "checks": checks,
            "note": "No model calls, validation runs, credential values, or study uploads."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["doctor", "plan", "preflight", "run", "summarize"])
    parser.add_argument("--config", type=Path, default=HERE / "config.local.json")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--env-file", type=Path, default=HERE.parent / ".env.local")
    args = parser.parse_args()
    load_env(args.env_file)
    if not args.config.exists():
        parser.error("Create experiment/config.local.json from config.example.json first")
    config = load_config(args.config)
    if args.action == "doctor":
        print(json.dumps(doctor(config), indent=2))
        return
    if args.out is None:
        parser.error("--out is required except for doctor")
    root = args.out.resolve()
    if root == HERE.parent or HERE.parent in root.parents:
        parser.error("Keep raw runs outside the repository: use a private output directory")
    from protocol_lock import verify, verify_environment
    frozen_protocol = verify(config)
    exp = Experiment(config, root)
    if args.action == "plan":
        calls = len(config["models"]) * config["repetitions"] * (1 + 2 * config["repair_iterations"])
        print(json.dumps({"agent_calls": calls, "maximum_agent_hours": calls * config["agent"]["timeout_seconds"] / 3600,
                          "models": config["models"], "out": str(root),
                          "token_budget": "not hard-capped; fixed wall-time limits",
                          "requires": "Docker engine, prepared agent image, provider keys, qualified P21 runtime"}, indent=2))
        return
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".running"
    if args.action == "summarize":
        exp.summarize()
        return
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit("Experiment is locked. Check for an active process before removing .running")
    os.close(fd)
    try:
        saved = root / "config.json"
        if saved.exists() and json.loads(saved.read_text()) != config:
            raise ValueError("Configuration changed: use a new output directory")
        protocol = {"runner_sha256": digest(Path(__file__)),
                    "dockerfile_sha256": digest(HERE / "Dockerfile")}
        protocol_file = root / "protocol.json"
        if protocol_file.exists() and json.loads(protocol_file.read_text()) != protocol:
            raise ValueError("Runner changed: use a new output directory")
        prior_environment = json.loads((root / "environment.json").read_text()) if (root / "environment.json").exists() else None
        exp.preflight()
        current_environment = json.loads((root / "environment.json").read_text())
        verify_environment(frozen_protocol, current_environment)
        if prior_environment and prior_environment != current_environment:
            save(root / "environment.json", prior_environment)
            raise ValueError("Runtime changed: use a new output directory")
        if args.action == "preflight":
            print("Preflight passed; no agent calls or P21 validation executed.")
            return
        save(saved, config)
        save(protocol_file, protocol)
        if not exp.source.exists():
            exp.freeze()
        if manifest(exp.source) != json.loads((root / "input_manifest.json").read_text()):
            raise ValueError("Frozen input hashes changed")
        schedule_path = root / "schedule.json"
        if not schedule_path.exists():
            schedule = [[m["id"], r] for m in config["models"] for r in range(1, config["repetitions"] + 1)]
            random.Random(config["seed"]).shuffle(schedule)
            save(schedule_path, schedule)
        for model, repetition in json.loads(schedule_path.read_text()):
            print(f"Running {model} / repetition {repetition}", flush=True)
            exp.run_trial(exp.models[model], repetition)
        exp.summarize()
        print(f"Completed. Results: {root / 'results.csv'}")
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
