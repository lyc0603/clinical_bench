"""Predeclared dataset dependencies and process-variable ownership, not model planning."""
import re
from .storage import CHARACTER_STORAGE_CODE
from gxp_adsl.dag import NODES as ADSL_NODES

SYSTEM = '''Return ONLY a compact complete Python module defining run(previous, inputs, upstream) -> pandas.DataFrame.
NO TOOLS ARE AVAILABLE in this text-only API request. Never emit bash, invoke/XML tool calls, shell commands, test transcripts, simulated execution, package installs or internet/model calls. You cannot run tools. Include required imports and helpers in the one returned file.
previous is None at ingest, otherwise a pandas.DataFrame from the preceding process node. inputs is pathlib.Path('/inputs'), NEVER a dict. upstream is a dict mapping declared upstream ADaM dataset names to pandas.DataFrames generated earlier in this SAME run, NEVER reference answers. Exact source_files paths are supplied, lowercase. Source JSON specifications: inputs/'specifications.json'. Each spec['sheets'][sheet_name] is a LIST OF ROW ARRAYS, not a dict: sheet[0] is headers, sheet[1:] are rows; use [dict(zip(sheet[0], row)) for row in sheet[1:]]. Never call .get on a sheet array. SAP: inputs/'SAP.pdf'. Read XPT using pyreadstat.read_xport(..., disable_datetime_conversion=True). If source_schemas[domain][read_encoding] is non-null, also pass that exact encoding; TS requires cp1252 in this input package. Never rewrite source files. Python3.12, pandas2.2.3, numpy2.2.4, pyreadstat1.3.6 and lxml are installed.
Implement only this assigned process and its owned variables. Use full frozen variable algorithms, rule precedence, implementation details, parameter map, windows, value-level metadata and terminology; do not invent clinical rules. GEN01 randomized DM ARMCD Pbo/Xan_Lo/Xan_Hi only. All subject/date dependencies must respect the supplied specification. Do not print subject records.
At ingest create the COMPLETE required row universe, including specified derived parameters, summary records and LOCF records where applicable. You may calculate temporary source selections internally to decide these rows, but return only assigned ADaM columns and optional scalar __SRC_* donor/trace helpers. Do not create __ROWID: controller assigns it after ingest. For ADSL ingest return STUDYID/USUBJID keys only. At later nodes preserve exactly the rows, __ROWID, subject keys, helper columns and every earlier unowned value; do not add/drop/reorder rows or silently replace preceding derivations. Recompute additional temporary calculations internally from source if needed. The row-universe node must already include any required synthetic/derived records; there is no later row expansion.
Numeric dates are SAS days since 1960-01-01, missing numeric stays missing, full precision retained. Character values are strings or missing, respect declared lengths. Return previous.copy() plus assigned columns. Do not return unassigned ADaM columns. The validate node cannot modify values or fix upstream mistakes. Write NO files; controller saves JSON. Do not read/modify other programs or raw artifact paths, evaluator, credentials or unrelated runs. Only upstream frames declared for this dataset are visible. A local code/QC failure permits one corrected attempt; exhausted failure blocks dependent datasets. Correct execution/structure is not proof of clinical correctness.'''
EXPORT_SYSTEM = '''Return ONLY a compact complete Python module defining run(datasets, inputs). NO TOOLS ARE AVAILABLE. No bash/invoke/XML tool calls, simulated execution, package installs or network. Prefer generic loops under 300 lines; read metadata dynamically rather than hardcoding hundreds of variable definitions. Never write a custom XPT serializer. Use installed pyreadstat.write_xport(file_format_version=5,table_name=dataset_name,column_labels=...,variable_format=...) and lxml.etree.
datasets is a dict of complete pandas.DataFrames (internal __* helper columns already removed); inputs is pathlib.Path('/inputs'), NOT a dict. Read complete frozen specification JSON at inputs/'specifications.json'. IMPORTANT: every spec['sheets'][sheet_name] is a LIST OF ROW ARRAYS, NOT a dict with headers/rows keys. Parse with sheet=spec['sheets'][name]; records=[dict(zip(sheet[0],row)) for row in sheet[1:]]. Never call sheet.get(). Example: [['Variable','Type'],['AVAL','Numeric']]. In this format, ['sheets']['Datasets'] contains headers and rows for dataset labels/order; each dataset sheet has headers and rows with Order, Variable, Label, Type, Length, Format, Origin, Codelist OID and source metadata. Other sheets contain Codelists, Parameter map and Value level. Preserve approved labels/types/lengths/formats/order and all derived values. Do not implement clinical derivations or fill missing values with invented data. XPT dates are already SAS numeric dates. For character serialization, SAS blank/padding is equivalent to missing; do not truncate data.
Write exactly output/adam/datasets/<lowercase dataset>.xpt for each supplied dataset, one combined output/adam/datasets/define.xml (Define2.0.0), output/adam/metadata/spec-metadata.json, output/adam/manifest.json and output/adam/notes.md. Relative Define leaf hrefs are <lowercase dataset>.xpt because XML sits beside XPT. Include all variable ItemDefs with unique dataset-qualified OIDs. Use deterministic XML timestamps/metadata; disclose missing metadata rather than inventing it. No extra files in datasets/. Do not read/modify programs or intermediate artifact files. Return None. The controller independently checks delivered values and metadata structure; terminal P21 is not feedback.'''

NODE_WRAPPER = '''import importlib.util
import sys
from pathlib import Path
import json
import pandas as pd
program, previous_path, result_path, upstream_path = sys.argv[1:]
upstream={k:pd.read_json(v,orient='table') for k,v in json.loads(Path(upstream_path).read_text()).items()}
previous=None if previous_path=='-' else pd.read_json(previous_path,orient='table')
spec=importlib.util.spec_from_file_location('generated_node',program)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
result=module.run(previous,Path('/inputs'),upstream)
if not isinstance(result,pd.DataFrame) or result.columns.duplicated().any():raise ValueError('Return one dataframe with unique columns')
if previous is None:
    if '__ROWID' in result:raise ValueError('__ROWID is controller-owned')
    result=result.copy();result['__ROWID']=list(range(len(result)))
Path(result_path).parent.mkdir(parents=True,exist_ok=True)
result.to_json(result_path,orient='table',index=False,double_precision=15)
'''
EXPORT_WRAPPER = '''import importlib.util
from pathlib import Path
import json
import pandas as pd
paths=json.loads(Path('artifacts/datasets.json').read_text())
frames={k:pd.read_json(v,orient='table') for k,v in paths.items()}
'''+CHARACTER_STORAGE_CODE+'''
frozen=json.loads(Path('/inputs/specifications.json').read_text())['sheets']
for name,frame in frames.items():
    sheet=frozen[name]
    definitions={row['Variable']:row for row in (dict(zip(sheet[0],r)) for r in sheet[1:]) if row.get('Variable')}
    frames[name]=normalize_character_storage(frame,definitions)
spec=importlib.util.spec_from_file_location('generated_export','output/adam/programs/export.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.run(frames,Path('/inputs'))
'''
STRUCTURAL = {'STUDYID','USUBJID','SUBJID','PARAM','PARAMCD','PARAMN','PARAMTYP','PARCAT1',
              'AVISIT','AVISITN','VISIT','VISITNUM','ADT','ADTM','DTYPE','ATPT','ATPTN',
              'VSPOS','VSTPTNUM','VSTPT','AESEQ','LBSEQ','QSSEQ','CMSEQ','DSSEQ','EXSEQ','SRCSEQ','SRCDOM','SRCVAR'}


def definitions(spec, dataset):
    rows=spec['sheets'][dataset];return [dict(zip(rows[0],r)) for r in rows[1:] if r[1]]


def make_plan(spec):
    rows=spec['sheets']['Datasets'];inventory=[dict(zip(rows[0],r)) for r in rows[1:] if r[0]]
    names={r['Dataset'] for r in inventory};plan=[]
    for info in sorted(inventory,key=lambda r:(int(r['Build order']),[x['Dataset'] for x in inventory].index(r['Dataset']))):
        ds=info['Dataset'];defs=definitions(spec,ds);allnames=[r['Variable'] for r in defs]
        dependencies=[x.strip() for x in str(info['Source domains']).split(',') if x.strip() in names and x.strip()!=ds]
        if ds=='ADSL':
            nodes=[{'name':n,'owns':list(v),'task':t} for n,v,t in ADSL_NODES if n not in ('apply_metadata','export')]
        else:
            common={r['Variable'] for r in defs if str(r.get('Origin source') or '').startswith('ADSL.')}
            ingest={r['Variable'] for r in defs if r['Variable'] in STRUCTURAL or (r.get('Origin')=='Predecessor' and not str(r.get('Origin source') or '').startswith('ADSL.'))}
            common-=ingest
            residual=set(allnames)-ingest-common
            flags={r['Variable'] for r in defs if r['Variable'] in residual and (r['Variable']=='ASEQ' or r['Variable'].endswith(('FL','FN')) or r['Variable'].startswith(('AOCC','SHIFT','CRIT')) or r['Type']=='Character')}
            analysis=residual-flags
            groups=[('record_universe',ingest,'Create the complete source/parameter/derived/LOCF record universe and assigned source fields. Use declared upstream datasets. Preserve source donor identity in optional __SRC_* scalar fields. Read ALL dataset algorithms so no required derived rows are deferred.'),
                    ('subject_covariates',common,'Join/derive the assigned upstream ADSL subject covariates according to their target specifications without changing record identity or upstream rows.'),
                    ('analysis_values',analysis,'Derive assigned analysis values, dates, durations, baseline covariates, changes and numeric analysis quantities. Honor source selection, scoring, same-assessment, missingness, baseline and LOCF donor rules.'),
                    ('flags_sequence',flags,'Derive assigned flags, criteria/shifts, labels and final deterministic ASEQ. Required synthetic records already exist; do not change the row universe or earlier values.'),
                    ('validate',set(),'Assert full specified variable coverage, key/sequence consistency and specified business invariants. Do not replace upstream values.')]
            nodes=[{'name':n,'owns':[v for v in allnames if v in cols],'task':task} for n,cols,task in groups if cols or n=='validate']
        plan.append({'dataset':ds,'dependencies':dependencies,'metadata':info,'nodes':nodes})
    validate_plan(spec,plan)
    return plan


def validate_plan(spec,plan):
    seen=set();total=0
    for dataset in plan:
        ds=dataset['dataset']
        if ds in seen or not set(dataset['dependencies'])<=seen:raise ValueError('Dataset DAG duplicate, cycle or out-of-order dependency '+ds)
        seen.add(ds);expected=[r['Variable'] for r in definitions(spec,ds)];owned=[v for n in dataset['nodes'] for v in n['owns']]
        if len(owned)!=len(set(owned)) or set(owned)!=set(expected):raise ValueError('Variable ownership not exact '+ds)
        total+=len(expected)
    if len(plan)!=13 or total!=531:raise ValueError('Expected full benchmark: 13 datasets / 531 variables')
