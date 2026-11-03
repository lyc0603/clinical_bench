"""Controller-only source-derived checks; never a full derivation oracle."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat
from lxml import etree

from .dag import NODES, OUTPUT_FILES


def variables(spec):
    rows = spec['sheets']['ADSL']
    return [dict(zip(rows[0], row)) for row in rows[1:] if row[1]]


def eligible(inputs):
    dm, _ = pyreadstat.read_xport(str(Path(inputs)/'Input/dm.xpt'), disable_datetime_conversion=True)
    frame = dm[dm.ARMCD.isin(['Pbo','Xan_Lo','Xan_Hi'])].copy()
    if frame.USUBJID.duplicated().any():
        raise ValueError('Source randomized population is not unique')
    return frame


def check_frame(frame, expected, required, definitions, previous=None, owned=()):
    errors = []
    if not {'STUDYID','USUBJID'} <= set(frame):
        return ['Missing subject identity columns']
    keys = ['STUDYID','USUBJID']
    actual = list(frame[keys].itertuples(index=False, name=None))
    want = set(expected[keys].itertuples(index=False, name=None))
    if len(actual) != len(want) or len(set(actual)) != len(actual) or set(actual) != want:
        errors.append('Output does not contain exactly one row per GEN01 randomized subject')
    missing = sorted(set(required) - set(frame))
    if missing:
        errors.append('Missing cumulative variables: '+','.join(missing))
    for name in sorted(set(required) & set(frame)):
        series = frame[name]
        kind = definitions[name]['Type']
        if kind == 'Numeric' and (not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series)):
            errors.append(name+': expected numeric column')
        if kind == 'Character' and not series.dropna().map(lambda x: isinstance(x, str)).all():
            errors.append(name+': expected character values')
    if previous is not None and not errors:
        protected = [k for k in sorted(required) if k in previous and k not in owned]
        left = previous.set_index(keys).sort_index()
        right = frame.set_index(keys).sort_index()
        for name in protected:
            if name in keys:
                continue
            try:
                a,b=left[name],right[name]
                if definitions[name]['Type']=='Character':
                    a,b=[x.fillna('').astype('string').str.rstrip() for x in (a,b)]
                pd.testing.assert_series_equal(a, b, check_dtype=False,
                    check_names=False, rtol=1e-12, atol=1e-12)
            except AssertionError:
                errors.append(name+': upstream values changed outside assigned ownership')
    if 'ITTFL' in required and 'ITTFL' in frame and not frame.ITTFL.eq('Y').all():
        errors.append('ITTFL must be Y for all retained randomized subjects')
    if {'SAFFL','TRTSDT'} <= set(required) and {'SAFFL','TRTSDT'} <= set(frame):
        if (frame.SAFFL.eq('Y') & frame.TRTSDT.isna()).any():
            errors.append('SAFFL=Y has missing TRTSDT')
    if {'TRTSDT','TRTEDT','TRTDUR'} <= set(required) and {'TRTSDT','TRTEDT','TRTDUR'} <= set(frame):
        mask = frame.TRTSDT.notna() & frame.TRTEDT.notna() & frame.TRTEDT.ge(frame.TRTSDT)
        if not np.allclose(frame.loc[mask,'TRTDUR'], frame.loc[mask,'TRTEDT']-frame.loc[mask,'TRTSDT']+1, equal_nan=False):
            errors.append('TRTDUR does not satisfy the frozen inclusive-duration rule')
    return errors


def exported(workspace, definitions):
    workspace = Path(workspace)
    data = workspace/OUTPUT_FILES['adsl']
    define = workspace/OUTPUT_FILES['define']
    errors = []
    try:
        frame, meta = pyreadstat.read_xport(str(data), disable_datetime_conversion=True)
        if set(frame) != set(definitions):
            errors.append('Export variable inventory is not exactly the 49 specified variables')
        for name, definition in definitions.items():
            actual = meta.readstat_variable_types.get(name)
            if actual is None or (actual == 'string') != (definition['Type'] == 'Character'):
                errors.append(name+': XPT storage type mismatch')
    except Exception as exc:
        frame = None
        errors.append('XPT is not readable: '+type(exc).__name__)
    try:
        if not define.is_file():
            raise FileNotFoundError(OUTPUT_FILES['define'])
        root = etree.parse(str(define), etree.XMLParser(resolve_entities=False, no_network=True)).getroot()
        version_attribute='{http://www.cdisc.org/ns/def/v2.0}DefineVersion'
        versions=[root.get(version_attribute)]+[x.get(version_attribute) for x in root.findall('.//{http://www.cdisc.org/ns/odm/v1.3}MetaDataVersion')]
        if etree.QName(root).localname != 'ODM' or '2.0.0' not in versions:
            errors.append('Expected ODM with DefineVersion 2.0.0')
        names = {x.get('Name') for x in root.findall('.//{http://www.cdisc.org/ns/odm/v1.3}ItemDef')}
        if not set(definitions) <= names:
            errors.append('Define-XML does not declare all 49 variables')
    except FileNotFoundError:
        alternate = workspace/'output/adam/define.xml'
        hint = '; found output/adam/define.xml instead; write the XML beside adsl.xpt at the required path' if alternate.is_file() else ''
        errors.append('Missing required deliverable: '+OUTPUT_FILES['define']+hint)
    except Exception as exc:
        errors.append('Define-XML at '+OUTPUT_FILES['define']+' is not parseable: '+type(exc).__name__)
    for name in [OUTPUT_FILES[key] for key in ('metadata','manifest','notes')]:
        if not (Path(workspace)/name).is_file():
            errors.append('Missing required deliverable: '+name)
    return frame, errors


def source_checks(frame, inputs):
    """Selected direct-source checks; no reference ADaM or agent flags used as an oracle."""
    dm = eligible(inputs).set_index('USUBJID')
    a = frame.set_index('USUBJID').reindex(dm.index)
    checks = []
    for name in ['STUDYID','SUBJID','ARM','RFSTDTC','RFENDTC','AGE','AGEU','SEX','RACE','ETHNIC','SITEID']:
        if name not in a or name not in dm:
            checks.append({'check': 'DM predecessor '+name, 'assessed': 0, 'errors': None})
            continue
        if pd.api.types.is_numeric_dtype(dm[name]):
            equal = np.isclose(pd.to_numeric(a[name], errors='coerce'), dm[name], equal_nan=True)
        else:
            equal = a[name].fillna('').eq(dm[name].fillna(''))
        checks.append({'check': 'DM predecessor '+name, 'assessed': len(dm), 'errors': int((~equal).sum())})
    sv, _ = pyreadstat.read_xport(str(Path(inputs)/'Input/sv.xpt'), disable_datetime_conversion=True)
    sv = sv[sv.VISITNUM.eq(3) & sv.USUBJID.isin(dm.index)].copy()
    complete = sv.SVSTDTC.astype('string').str.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T.*)?', na=False)
    sv['anchor'] = pd.to_datetime(sv.SVSTDTC.where(complete).astype('string').str[:10], errors='coerce')
    reference = sv.groupby('USUBJID').anchor.agg(lambda x: x.dropna().iloc[0] if x.dropna().nunique()==1 else pd.NaT).reindex(dm.index)
    days = (reference-pd.Timestamp('1960-01-01')).dt.days
    for name in ['TRTSDT','RANDDT']:
        if name not in a:
            checks.append({'check': 'SV Visit3 '+name, 'assessed': 0, 'errors': None})
        else:
            correct = np.isclose(pd.to_numeric(a[name], errors='coerce'), days, equal_nan=True)
            checks.append({'check': 'SV Visit3 '+name, 'assessed': len(days), 'errors': int((~correct).sum())})
    return checks


def validate_plan(spec):
    names = [x['Variable'] for x in variables(spec)]
    assigned = [x for _, cols, _ in NODES for x in cols]
    if len(names)!=49 or len(set(assigned))!=49 or sorted(names)!=sorted(assigned):
        raise ValueError('Node ownership must cover each of the 49 variables exactly once')
