"""Variable independence and explicit keyed row alignment, no derivation templates."""
import json
import re
import pandas as pd
from gxp_full.plan import definitions, make_plan
from gxp_recovery.boundary import NORMALIZATION, EXPORT_WRAPPER

SYSTEM = '''Return only one compact complete Python module defining run(previous, inputs, upstream) -> pandas.DataFrame. This is a tool-free text API. No simulated tools, shell, internet, installations, model calls or printed records. inputs is pathlib.Path('/inputs'), never a dict. Exact case-sensitive source_files paths and XPT encodings are supplied. Read XPT using pyreadstat.read_xport(..., disable_datetime_conversion=True) and the supplied encoding when non-null. Specification JSON sheets are lists of row arrays: records=[dict(zip(sheet[0],row)) for row in sheet[1:]]. Read frozen specifications.json or SAP.pdf when useful. Python3.12/pandas2.2.3/numpy2.2.4/pyreadstat1.3.6/lxml are installed.
You implement one independent variable, or the explicitly identified row-universe task. No other variable workers' code or results are available. upstream contains only declared upstream datasets produced in THIS run, not reference outputs. Recompute any intermediate target variables from sources locally; never assume previous contains other derived variables. Follow the supplied frozen rules, parameter maps, edge cases, missingness and deterministic tie handling; no new clinical conventions. Numeric dates are SAS days since 1960-01-01. Preserve numeric precision, missingness and specified types/lengths. Source population is GEN01 randomized DM ARMCD Pbo/Xan_Lo/Xan_Hi only. No DM fallback for specified SV randomization anchor.
For task_type variable: previous contains __ROWID, USUBJID and optional __SRC_* row-identification helpers ONLY. Return exactly __ROWID, USUBJID and assigned variable (no duplicate USUBJID if assigned). Preserve keys and order; every supplied row exactly once. Do not change row count, add other target variables, or return helpers. Use row helpers to align independently recomputed source selections, derived parameter/summary and LOCF records. Do not write files. One local execution/QC repair is allowed.
For task_type row_universe: previous is None. Create the COMPLETE dataset record universe required by ALL its variable specifications, including derived parameters, summary and LOCF rows where required. Return USUBJID and optional scalar __SRC_* source/donor/parameter/visit/time/record identifiers ONLY, no other ADaM columns and no __ROWID. The controller assigns __ROWID. Row helpers must identify every repeated-subject row and its source or derived-record role so each variable can be computed independently. This task selects rows, not a block of clinical analysis variables. No later row expansion occurs. Do not read other programs, artifacts, credentials, evaluator or prior runs. QC is structural/selected consistency, not comprehensive clinical correctness.'''
REVIEW_SYSTEM = '''Review the supplied already human-approved frozen dataset specification and source schemas. Return a concise advisory list of ambiguity/edge-case risks, not code or rewritten specifications. No tools. Do not change the specification or authorize new clinical decisions. This review is retained but does not change variable-worker context.'''

WRAPPER = '''import importlib.util,json,sys
from pathlib import Path
import pandas as pd
program,previous_path,result_path,upstream_path,dataset=sys.argv[1:]
previous=None if previous_path=='-' else pd.read_json(previous_path,orient='table')
upstream={k:pd.read_json(v,orient='table') for k,v in json.loads(Path(upstream_path).read_text()).items()}
spec=importlib.util.spec_from_file_location('generated_variable',program)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
result=module.run(previous,Path('/inputs'),upstream)
if not isinstance(result,pd.DataFrame) or result.columns.duplicated().any():raise ValueError('Return one dataframe with unique columns')
if previous is None:
    if '__ROWID' in result:raise ValueError('__ROWID is controller-owned')
    result=result.copy();result['__ROWID']=list(range(len(result)))
'''+NORMALIZATION+'''
sheet=json.loads(Path('/inputs/specifications.json').read_text())['sheets'][dataset]
defs={r['Variable']:r for r in (dict(zip(sheet[0],row)) for row in sheet[1:]) if r.get('Variable')}
result=preserve_nullable_characters(result,defs)
Path(result_path).parent.mkdir(parents=True,exist_ok=True)
result.to_json(result_path,orient='table',index=False,double_precision=15)
'''

def plan(spec):
    # Reuse specification-derived dataset ordering/dependencies only, not GxP process nodes.
    return [{k:d[k] for k in ('dataset','dependencies','metadata')} | {'variables':definitions(spec,d['dataset'])} for d in make_plan(spec)]

def variable_qc(frame, keys, definition):
    name=definition['Variable'];errors=[]
    if not isinstance(frame,pd.DataFrame) or frame.columns.duplicated().any():return ['Expected dataframe with unique columns']
    if set(frame)!={'__ROWID','USUBJID',name}:return ['Return exact row keys and assigned variable only']
    if len(frame)!=len(keys) or frame.__ROWID.isna().any() or frame.__ROWID.duplicated().any():return ['Invalid row identity/count']
    if list(frame.__ROWID)!=list(keys.__ROWID) or list(frame.USUBJID)!=list(keys.USUBJID):errors.append('Row keys, order or subject mapping changed')
    s=frame[name]
    if definition['Type']=='Numeric':
        import numpy as np
        if not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):errors.append('Expected numeric, not boolean')
        elif np.isinf(s.to_numpy(dtype=float,na_value=np.nan)).any():errors.append('Infinite numeric value')
    else:
        if not (pd.api.types.is_object_dtype(s) or isinstance(s.dtype,pd.StringDtype)) or not all(isinstance(v,str) for v in s.dropna()):errors.append('Expected character storage')
        elif any(len(v.encode('utf-8'))>int(definition['Length']) for v in s.dropna()):errors.append('Character exceeds declared byte length')
    return errors

def row_qc(frame, expected):
    if not isinstance(frame,pd.DataFrame) or frame.columns.duplicated().any():return ['Expected dataframe with unique columns']
    if not {'USUBJID','__ROWID'}<=set(frame):return ['Missing subject/row identity']
    errors=[]
    if not len(frame) or frame.USUBJID.isna().any() or not set(frame.USUBJID)<=set(expected.USUBJID):errors.append('Empty or non-randomized/unknown subject universe')
    if frame.__ROWID.isna().any() or frame.__ROWID.duplicated().any():errors.append('Duplicate/missing row identity')
    if any(c not in ('USUBJID','__ROWID') and not c.startswith('__SRC_') for c in frame):errors.append('Row task returned target analysis columns')
    for c in frame:
        if c.startswith('__SRC_') and any(isinstance(v,(list,dict,tuple,set)) for v in frame[c].dropna()):errors.append('Non-scalar row helper')
    return errors

def merge_variables(keys,frames,defs):
    merged=keys[['__ROWID','USUBJID']].copy()
    for definition in defs:
        name=definition['Variable'];frame=frames[name];errors=variable_qc(frame,keys,definition)
        if errors:raise ValueError('Cannot merge rejected variable '+name+': '+str(errors))
        if name!='USUBJID':merged=merged.merge(frame,on=['__ROWID','USUBJID'],how='left',sort=False,validate='one_to_one')
    return merged[['__ROWID']+[v['Variable'] for v in defs]]

def context(spec,ds,schemas,definition=None):
    rows=ds['variables'];names={r['Variable'] for r in rows};needed={definition['Variable']} if definition else names.copy()
    while True:
        old=needed.copy()
        for row in rows:
            if row['Variable'] in needed:needed |= names & set(re.findall(r'\b[A-Z][A-Z0-9]*\b',str(row)))
        if old==needed:break
    def records(sheet):
        value=spec['sheets'][sheet];return [dict(zip(value[0],r)) for r in value[1:]]
    value_rows=[r for r in records('Value level') if r['Dataset']==ds['dataset'] and r['Parent variable'] in needed]
    parameter_rows=[r for r in records('Parameter map') if r['Dataset']==ds['dataset']]
    selected=[r for r in rows if r['Variable'] in needed]
    codes={r.get('Codelist OID') for r in selected+value_rows if r.get('Codelist OID')}
    code_rows=[r for r in records('Codelists') if r['Codelist OID'] in codes]
    def sheet(name,selected):
        headers=spec['sheets'][name][0];return [headers]+[[r.get(h) for h in headers] for r in selected]
    return {'task_type':'variable' if definition else 'row_universe','dataset':ds['metadata'],'assigned_variable':definition,'dependency_specifications':selected,
        'context_selection':'Current dataset and assigned/dependency variables for value-level metadata; current-dataset parameter map; referenced codelists. All rules and implementation details supplied. Complete unchanged specifications.json remains readable in /inputs.',
        'rules':spec['sheets']['Rules'],'implementation_details':spec['sheets']['Implementation details'],'parameter_map':sheet('Parameter map',parameter_rows),'value_level':sheet('Value level',value_rows),'windows':spec['sheets']['Windows'],'codelists':sheet('Codelists',code_rows),'site_map':spec['sheets']['Site map'] if ds['dataset']=='ADSL' else None,
        'source_schemas':schemas,'source_files':{d:'/inputs/Input/'+d.lower()+'.xpt' for d in schemas},'declared_upstream_datasets':ds['dependencies'],'no_reference_outputs':True}

def replay_entry(datasets,accepted):
    selected=[d for d in datasets if d['dataset'] in accepted]
    return '''from pathlib import Path
import json,subprocess,pandas as pd,pyreadstat
plan='''+repr(selected)+'''
Path('artifacts').mkdir(exist_ok=True)
latest={}
for ds in plan:
    name=ds['dataset'];prefix='artifacts/'+name
    upstream=prefix+'-upstream.json';Path(upstream).write_text(json.dumps({k:latest[k] for k in ds['dependencies']}))
    keys=prefix+'-keys.json'
    if name=='ADSL':
        dm,_=pyreadstat.read_xport('/inputs/Input/dm.xpt',disable_datetime_conversion=True)
        frame=dm.loc[dm.ARMCD.isin(['Pbo','Xan_Lo','Xan_Hi']),['USUBJID']].copy()
        if frame.USUBJID.duplicated().any():raise ValueError('Duplicate ADSL keys')
        frame['__ROWID']=list(range(len(frame)));frame.to_json(keys,orient='table',index=False,double_precision=15)
    else:
        subprocess.run(['python','-B','output/adam/programs/run_variable.py','output/adam/programs/variables/'+name+'__row_universe.py','-',keys,upstream,name],check=True)
    keyframe=pd.read_json(keys,orient='table');merged=keyframe[['__ROWID','USUBJID']].copy()
    for definition in ds['variables']:
        variable=definition['Variable'];result=prefix+'-'+variable+'.json'
        subprocess.run(['python','-B','output/adam/programs/run_variable.py','output/adam/programs/variables/'+name+'__'+variable+'.py',keys,result,upstream,name],check=True)
        frame=pd.read_json(result,orient='table')
        if set(frame)!={'__ROWID','USUBJID',variable} or len(frame)!=len(keyframe) or list(frame.__ROWID)!=list(keyframe.__ROWID) or list(frame.USUBJID)!=list(keyframe.USUBJID):raise ValueError('Replay variable identity mismatch')
        if variable!='USUBJID':merged=merged.merge(frame,on=['__ROWID','USUBJID'],how='left',validate='one_to_one',sort=False)
    final=prefix+'-final.json';merged[[v['Variable'] for v in ds['variables']]].to_json(final,orient='table',index=False,double_precision=15);latest[name]=final
Path('artifacts/datasets.json').write_text(json.dumps(latest))
subprocess.run(['python','-B','output/adam/programs/run_export.py'],check=True)
'''
