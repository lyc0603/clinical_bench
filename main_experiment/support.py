"""Main-study evidence utilities and P21 parsing, independent of the pilot runner.

Initially extracted without behavior changes from the historical runner.
Changes here are covered by the main-study seal.
"""
import hashlib
import json
import os
from pathlib import Path
import posixpath
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET

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

