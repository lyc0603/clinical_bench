"""Fixed dependency order adapted to the frozen benchmark's ADSL rules."""
OUTPUT_FILES = {
    'adsl': 'output/adam/datasets/adsl.xpt',
    'define': 'output/adam/datasets/define.xml',
    'metadata': 'output/adam/metadata/adsl-metadata.json',
    'manifest': 'output/adam/manifest.json',
    'notes': 'output/adam/notes.md',
}

NODES = [
    ('ingest', [], 'Read DM and retain exactly the randomized subjects defined by GEN01. Return a single primary dataframe, not a collection of domains.'),
    ('merge_dm', ['STUDYID','USUBJID','SUBJID','ARM','RFSTDTC','RFENDTC'], 'Establish the subject-level base and copy the designated DM predecessors without altering identities.'),
    ('derive_treatment_vars', ['TRT01P','TRT01PN','TRT01A','TRT01AN'], 'Derive planned and actual treatment variables and explicit numeric mappings.'),
    ('derive_treatment_dates', ['RANDDT','TRTSDT','TRTEDT','RFENDT'], 'Derive the SV Visit 3 anchor, exposure/end dates and disposition fallback exactly as specified. Never use a DM fallback for randomization.'),
    ('derive_study_dates', ['VISIT1DT','DISONSDT'], 'Derive screening Visit 1 and disease-onset dates before dependent duration calculations.'),
    ('derive_duration', ['TRTDUR','AVGDD','CUMDOSE','DURDIS','DURDSGR1'], 'Derive treatment duration, exposure quantities and disease duration using already available dates.'),
    ('derive_flags', ['SAFFL','ITTFL','EFFFL'], 'Derive populations directly from source selections under POP01 and ADSL02; finalized efficacy datasets are not available.'),
    ('derive_disposition', ['DISCONFL','DSRAEFL','DTHFL','DCDECOD','DCREASCD','VISNUMEN'], 'Derive disposition/death information and last visit according to deterministic source selection rules.'),
    ('derive_completion', ['COMP8FL','COMP16FL','COMP24FL'], 'Derive completion flags after EFFFL; select actual source efficacy observations and visits rather than depending on future analysis datasets.'),
    ('derive_demographics', ['AGE','AGEGR1','AGEGR1N','AGEU','RACE','RACEN','SEX','ETHNIC','EDUCLVL'], 'Copy/derive demographics, mappings and education from the correct source variables.'),
    ('derive_site', ['SITEID','SITEGR1'], 'Derive site and site grouping using the frozen site map.'),
    ('derive_baselines', ['BMIBL','BMIBLGR1','HEIGHTBL','WEIGHTBL','MMSETOT'], 'Derive baseline measurements and MMSE with the exact assessment and duplicate handling rules.'),
    ('validate', [], 'Verify all 49 variables and the subject-level structure. Assert constraints; do not silently replace upstream values to make checks pass.'),
    ('apply_metadata', [], 'Preserve all 49 derived values, select the specified variable order and write output/adam/metadata/adsl-metadata.json with labels, lengths, formats and types from the frozen specification.'),
    ('export', [], 'Preserve the dataframe and export output/adam/datasets/adsl.xpt, Define-XML 2.0.0 at output/adam/datasets/define.xml with the 49 variable definitions, output/adam/manifest.json and output/adam/notes.md. Define-XML and adsl.xpt must be in the same datasets directory; use a relative leaf href of adsl.xpt. Use deterministic metadata and no run-dependent timestamps. Do not write or alter program files.'),
]
# Keep the in-memory plan identical to its JSON freeze representation.
NODES = [list(node) for node in NODES]

SYSTEM = '''You generate one narrow Python implementation for a fixed, benchmark-specific ADSL process DAG.
Return only concise executable Python code defining run(previous, inputs), where previous is a pandas DataFrame (None for ingest) and inputs is pathlib.Path('/inputs'). Return one pandas DataFrame.
You are not an autonomous planner. Implement only the assigned node and assigned variables. Do not change earlier derived variables, subject identities or the eligible population. Read additional source SDTM files when needed. Frozen specifications override legacy comments and guesses. Do not fabricate values or substitute different derivation rules.
No internet, subprocess model calls, package installation, reference ADaM, evaluator code, or credentials are available. Python 3.12, pandas 2.2.3, numpy 2.2.4, pyreadstat 1.3.6, lxml, openpyxl and pypdf are available. Source XPT can be read with pyreadstat.read_xport(..., disable_datetime_conversion=True). Numeric dates must be SAS days since 1960-01-01, not Python datetime objects. Use the actual supplied schema; the SC numeric value field and QS instruments must not be guessed.
The working directory is /workspace. Source filenames are case-sensitive lowercase. Use the exact source_files paths supplied in each node prompt; for example /inputs/Input/dm.xpt (never DM.xpt); specifications are JSON in inputs/'specifications.json' with sheets of header/row arrays. You may use the SAP if necessary, subject to frozen rule precedence. Do not read or modify other programs or upstream artifact files: the previous dataframe is already supplied. Only metadata/export nodes may create their designated deliverables. Do not print subject records.
Copy previous before modifying it. Numeric variables must be numeric pandas columns; character columns must contain strings or missing values. Do not convert missing numeric values to zero. Preserve full numeric precision. Include necessary imports and helper functions in this single file; no reliance on code from earlier nodes.
The controller executes, checks and saves each node separately. Local code/check failure permits one corrected attempt using the concrete error; provider errors do not trigger automatic retries. Use pyreadstat.write_xport(..., file_format_version=5, table_name='ADSL', column_labels=..., variable_format=...) for export. Character storage widths should respect the frozen specification; do not claim conformance or correct values merely because code executes.
'''

WRAPPER = '''import importlib.util
import sys
from pathlib import Path
import pandas as pd
program, previous, output = sys.argv[1:]
spec = importlib.util.spec_from_file_location('current_dag_node', program)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
frame = None if previous == '-' else pd.read_json(previous, orient='table')
result = module.run(frame, Path('/inputs'))
if not isinstance(result, pd.DataFrame):
    raise TypeError('Node must return one pandas DataFrame')
if result.columns.duplicated().any():
    raise ValueError('Duplicate output columns')
Path(output).parent.mkdir(parents=True, exist_ok=True)
result.to_json(output, orient='table', index=False, double_precision=15)
'''
