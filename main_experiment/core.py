"""Public protocol utilities. Study data and evidence remain in private paths."""
import hashlib
import json
from pathlib import Path
import random
import shutil

from main_experiment.support import digest, manifest, save

HERE = Path(__file__).resolve().parent
CONDITIONS = ('self_review', 'p21_feedback')
MODELS = {'openai/gpt-6.1-sol', 'anthropic/claude-sonnet-5-5',
          'google/gemini-3.1-pro-preview'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def config(path):
    value = json.loads(Path(path).read_text())
    assert_protocol(value)
    return value


def assert_protocol(c):
    if {m['model'] for m in c['models']} != MODELS or len(c['models']) != 3:
        raise ValueError('Use the three prespecified model IDs; substitutions require a new protocol')
    if len({m['id'] for m in c['models']}) != 3:
        raise ValueError('Model IDs must be unique')
    if any(not m['id'].isalnum() or not m['key_env'].isidentifier() for m in c['models']):
        raise ValueError('Unsafe model alias or credential environment name')
    for key, expected in [('repetitions', 3), ('phase_seconds', None), ('cpus', 4),
                          ('memory', '8g'), ('rebuild_timeout_seconds', 1800)]:
        if c[key] != expected:
            raise ValueError(f'{key} must equal {expected!r}')
    if c['p21']['ct'] != '2026-03-27' or c['p21']['timeout_seconds'] != 900:
        raise ValueError('P21 CT or timeout differs from the protocol')
    expected = json.loads((HERE / 'config.example.json').read_text())['expected_datasets']
    if sorted(c['expected_datasets']) != sorted(expected):
        raise ValueError('Expected dataset set differs from the protocol')


def schedule(c):
    rows = [dict(model=m['id'], condition=condition, repetition=r)
            for m in c['models'] for condition in CONDITIONS for r in range(1, 4)]
    random.Random(c['seed']).shuffle(rows)
    return [dict(workflow=f'w{i:02d}', **row) for i, row in enumerate(rows, 1)]


def prompts():
    return {p.stem: p.read_text() for p in sorted((HERE / 'prompts').glob('*.txt'))}


def code_manifest():
    root = HERE.parent
    paths = list(HERE.rglob('*.py')) + list((HERE / 'prompts').glob('*.txt'))
    paths += list((HERE / 'network').glob('*.json'))
    paths += [HERE / 'config.example.json', HERE / 'requirements.txt', HERE / 'completion-policy.json',
              HERE / 'Dockerfile',
              HERE / 'requirements-evaluator.txt', HERE / 'scoring-rules.json',
              root / 'docs/main-study-protocol.md', root / 'docs/main-experiment-workflow.md',
              root / 'docs/p21-evaluator-amendment.md']
    return {str(p.relative_to(root)): digest(p) for p in sorted(paths)}


def private_path(path):
    p = Path(path).resolve()
    if p == HERE.parent or HERE.parent in p.parents:
        raise ValueError('Keep clinical inputs and run evidence outside the Git checkout')
    return p


def prepare(source, out, fix=False):
    """Export values, not spreadsheet macros/formulas, into an agent-only package."""
    import openpyxl
    source, out = Path(source).resolve(), private_path(out)
    provenance_path = out.parent / (out.name + '.provenance.json')
    if out.exists() or provenance_path.exists():
        raise ValueError('Preparation destination and provenance must not exist')
    workbook = source / 'ADaM_specifications_main_experiment.xlsx'
    book = openpyxl.load_workbook(workbook, data_only=False)
    corrections = []
    sheet = book['ADVS']
    if sheet['B16'].value != 'TRTA' or sheet['D16'].value != 'Character':
        raise ValueError('Known TRTA correction no longer matches workbook structure')
    if any(cell.data_type == 'f' for sheet_ in book for row in sheet_ for cell in row):
        raise ValueError('Formula cells require a reviewed calculated-value export')
    cells = ['H16', 'J16', 'P16']
    affected = [cell for cell in cells if 'ADSL.TRT01AN' in str(sheet[cell].value)]
    if affected and not fix:
        raise ValueError('ADVS.TRTA refers to numeric TRT01AN. Review then use --fix-trta-predecessor')
    for cell in affected:
        before = sheet[cell].value
        sheet[cell] = before.replace('ADSL.TRT01AN', 'ADSL.TRT01A')
        corrections.append(dict(sheet='ADVS', cell=cell, before=before, after=sheet[cell].value))
    sheets = {s.title: [[v.isoformat() if hasattr(v, 'isoformat') else v for v in row]
                        for row in s.iter_rows(values_only=True)] for s in book}
    xpts = sorted((source / 'Input').glob('*.xpt'))
    if len(xpts) != 22 or not (source / 'SAP.pdf').is_file():
        raise ValueError('Expected 22 source XPT files and SAP.pdf')
    # Reject symlinks before copying. Do not copy proposals, JSON duplicates or private notes.
    for p in [workbook, source / 'SAP.pdf', *xpts]:
        if p.is_symlink():
            raise ValueError(f'Symlink input: {p.name}')
    out.mkdir(parents=True)
    (out / 'Input').mkdir()
    for p in xpts:
        shutil.copy2(p, out / 'Input' / p.name)
    shutil.copy2(source / 'SAP.pdf', out / 'SAP.pdf')
    save(out / 'specifications.json', {'format': 'workbook cell-value export',
         'define_xml_version': '2.0.0', 'source_encoding': {'ts': 'WINDOWS-1252'},
         'sheets': sheets})
    provenance = {'workbook_sha256': digest(workbook), 'corrections': corrections,
                  'agent_inputs': manifest(out)}
    save(provenance_path, provenance)
    return provenance


def validate_inputs(c):
    import pyreadstat
    root = Path(c['inputs'])
    files = manifest(root)
    xpts = sorted((root / 'Input').glob('*.xpt'))
    allowed = {'SAP.pdf', 'specifications.json'} | {'Input/'+p.name for p in xpts}
    if len(xpts) != 22 or set(files) != allowed:
        raise ValueError('Prepared package must contain exactly 22 XPT, SAP.pdf and specifications.json')
    if not {'ae', 'dm', 'ex', 'sv', 'qs', 'ts'} <= {p.stem for p in xpts}:
        raise ValueError('Missing required source domains')
    specs = json.loads((root / 'specifications.json').read_text())
    if specs['define_xml_version'] != '2.0.0' or specs['source_encoding'] != {'ts': 'WINDOWS-1252'}:
        raise ValueError('Specification version or source encoding drift')
    counts = {}
    for p in xpts:
        kwargs = {'encoding': 'WINDOWS-1252'} if p.stem == 'ts' else {}
        frame, _ = pyreadstat.read_xport(str(p), disable_datetime_conversion=True, **kwargs)
        counts[p.stem] = len(frame)
    provenance = json.loads((root.parent / (root.name+'.provenance.json')).read_text())
    if provenance['agent_inputs'] != files:
        raise ValueError('Prepared package no longer matches preparation provenance')
    return {'counts': counts, 'provenance': provenance}
