"""Structural/selected consistency gates, not a comprehensive clinical oracle."""
from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat
from lxml import etree
from .plan import definitions


def equal_values(left,right,defs):
    a=left.copy();b=right.copy()
    for name in a:
        if name in defs and defs[name]['Type']=='Character':
            a[name]=a[name].fillna('').astype('string').str.rstrip();b[name]=b[name].fillna('').astype('string').str.rstrip()
    pd.testing.assert_frame_equal(a,b,check_dtype=False,rtol=1e-12,atol=1e-12)


def node_checks(frame,previous,required,defs,expected,owned,dataset):
    errors=[]
    if not {'STUDYID','USUBJID','__ROWID'}<=set(frame):return ['Missing subject identity or controller row identity']
    if frame.__ROWID.isna().any() or frame.__ROWID.duplicated().any():errors.append('Invalid or duplicate controller row identities')
    if not set(frame.USUBJID)<=set(expected.USUBJID):errors.append('Non-randomized or unknown subjects included')
    if not set(frame.STUDYID)<=set(expected.STUDYID):errors.append('Unknown study identity')
    if dataset=='ADSL':
        actual=list(frame[['STUDYID','USUBJID']].itertuples(index=False,name=None));want=set(expected[['STUDYID','USUBJID']].itertuples(index=False,name=None))
        if len(actual)!=len(want) or set(actual)!=want:errors.append('ADSL does not contain exact unique GEN01 population')
    if not len(frame):errors.append('Empty dataset is not accepted in this benchmark extension')
    missing=set(required)-set(frame)
    if missing:errors.append('Missing assigned variables: '+','.join(sorted(missing)))
    extra=set(frame)-set(required)-{'__ROWID'}
    if any(not x.startswith('__SRC_') for x in extra):errors.append('Unassigned columns returned')
    for name in set(required)&set(frame):
        s=frame[name];d=defs[name]
        if d['Type']=='Numeric':
            if not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):errors.append(name+': expected numeric, not boolean')
            elif np.isinf(s.to_numpy(dtype=float,na_value=np.nan)).any():errors.append(name+': infinite value')
        else:
            if not (pd.api.types.is_object_dtype(s) or isinstance(s.dtype,pd.StringDtype)):errors.append(name+': expected character storage even when entirely missing')
            elif not s.dropna().map(lambda v:isinstance(v,str)).all():errors.append(name+': expected character or missing')
            elif s.dropna().map(lambda v:len(v.encode('utf-8'))>int(d['Length'])).any():errors.append(name+': character value exceeds declared length')
    for name in extra:
        if name.startswith('__SRC_') and frame[name].dropna().map(lambda x:isinstance(x,(dict,list,tuple,set))).any():errors.append('Source helper must be scalar')
    if previous is not None:
        if len(frame)!=len(previous) or list(frame.__ROWID)!=list(previous.__ROWID):errors.append('Row universe or order changed after ingest')
        else:
            protected=[c for c in previous if c not in owned]
            if not set(protected)<=set(frame):errors.append('Protected upstream columns removed')
            else:
                try:equal_values(previous[protected],frame[protected],defs)
                except AssertionError:errors.append('Protected upstream values changed')
    if {'TRTSDT','TRTEDT','TRTDUR'}<=set(required) and dataset=='ADSL':
        mask=frame.TRTSDT.notna()&frame.TRTEDT.notna()&frame.TRTEDT.ge(frame.TRTSDT)
        if not np.allclose(frame.loc[mask,'TRTDUR'],frame.loc[mask,'TRTEDT']-frame.loc[mask,'TRTSDT']+1):errors.append('ADSL inclusive treatment duration invariant failed')
    if 'ASEQ' in required and {'USUBJID','ASEQ'}<=set(frame):
        if frame.ASEQ.isna().any() or frame.duplicated(['USUBJID','ASEQ']).any():errors.append('ASEQ missing or duplicate within subject')
    return errors


def export_checks(workspace,spec,frames):
    workspace=Path(workspace);data=workspace/'output/adam/datasets';errors=[]
    expected={k.lower()+'.xpt' for k in frames}|{'define.xml'}
    actual={p.name for p in data.iterdir()} if data.is_dir() else set()
    if actual!=expected:errors.append('Dataset file inventory mismatch; missing='+str(sorted(expected-actual))+' extra='+str(sorted(actual-expected)))
    coverage={}
    for name,prior in frames.items():
        defs={v['Variable']:v for v in definitions(spec,name)}
        try:
            frame,meta=pyreadstat.read_xport(str(data/(name.lower()+'.xpt')),disable_datetime_conversion=True)
            matched=sum(k in meta.readstat_variable_types and (meta.readstat_variable_types[k]=='string')==(v['Type']=='Character') for k,v in defs.items());coverage[name]={'rows':len(frame),'variables_matched':matched,'expected_variables':len(defs)}
            if list(frame)!=list(defs) or matched!=len(defs):errors.append(name+': variable name/type/order mismatch')
            else:
                try:equal_values(prior[list(defs)].reset_index(drop=True),frame,defs)
                except AssertionError:errors.append(name+': XPT values differ from accepted frame')
        except Exception as exc:errors.append(name+': XPT unreadable '+type(exc).__name__)
    define=data/'define.xml'
    if not define.is_file():errors.append('Missing output/adam/datasets/define.xml')
    else:
        try:
            tree=etree.parse(str(define),etree.XMLParser(resolve_entities=False,no_network=True));root=tree.getroot();ns={'o':'http://www.cdisc.org/ns/odm/v1.3','d':'http://www.cdisc.org/ns/def/v2.0'}
            versions=[root.get('{'+ns['d']+'}DefineVersion')]+[x.get('{'+ns['d']+'}DefineVersion') for x in root.findall('.//o:MetaDataVersion',ns)]
            if etree.QName(root).localname!='ODM' or '2.0.0' not in versions:errors.append('Expected ODM DefineVersion2.0.0')
            items={x.get('OID'):x.get('Name') for x in root.findall('.//o:ItemDef',ns)}
            groups={x.get('Name'):x for x in root.findall('.//o:ItemGroupDef',ns)}
            for name in frames:
                group=groups.get(name)
                if group is None:errors.append('Missing Define ItemGroupDef '+name);continue
                got={items.get(x.get('ItemOID')) for x in group.findall('o:ItemRef',ns)}
                if not {v['Variable'] for v in definitions(spec,name)}<=got:errors.append('Define variable references incomplete '+name)
        except Exception as exc:errors.append('Define-XML parse failed '+type(exc).__name__)
    for name in ['output/adam/metadata/spec-metadata.json','output/adam/manifest.json','output/adam/notes.md']:
        if not (workspace/name).is_file():errors.append('Missing required deliverable '+name)
    return coverage,errors
