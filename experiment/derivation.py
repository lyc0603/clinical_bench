"""Prespecified, host-only source checks. Never executes generated programs.

These checks cover selected derivations, not complete clinical correctness.
"""
import json
from pathlib import Path


def score(source, datasets):
    import numpy as np
    import pandas as pd
    import pyreadstat

    source, datasets = Path(source), Path(datasets)
    checks = []

    def read(root, name):
        return pyreadstat.read_xport(str(root / (name.lower() + '.xpt')),
                                   disable_datetime_conversion=True)[0]

    def dates(s):
        return (pd.to_datetime(s.str[:10], format='%Y-%m-%d', errors='coerce')
                - pd.Timestamp('1960-01-01')).dt.days

    def same(a, b):
        return np.isclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float),
                          rtol=1e-10, atol=1e-8, equal_nan=True)

    def add(name, n, errors, qualification=''):
        checks.append(dict(check=name, status='scored', assessed=int(n),
                           errors=int(errors), qualification=qualification))

    def unavailable(names, exc):
        for name in names:
            if not any(c['check'] == name for c in checks):
                checks.append(dict(check=name, status='unavailable', assessed=None,
                                   errors=None, reason=type(exc).__name__ + ': ' + str(exc)))

    npi_names = ['npi_mean_coverage', 'npi_mean_value', 'npi_baseline_covariate']
    try:
        qs, sv, dm = [read(source / 'Input', n) for n in ['QS', 'SV', 'DM']]
        q = qs[qs.QSTESTCD.eq('NPTOT') & qs.QSSTRESN.notna()].copy()
        visits = sv[sv.VISITNUM.eq(3)].copy()
        visits['date'] = dates(visits.SVSTDTC)
        rand = visits.groupby('USUBJID').date.min()
        rand = pd.Series(dm.USUBJID.map(rand).fillna(dates(dm.RFSTDTC)).to_numpy(), index=dm.USUBJID)
        q['date'] = dates(q.QSDTC)
        q['day'] = q.date - q.USUBJID.map(rand)
        selected = []
        for week in range(4, 25, 2):
            v = q[q.day.between(7*week-6, 7*week+7)].copy()
            v['distance'] = (v.day - 7*week).abs()
            selected.append(v.sort_values(['USUBJID', 'distance', 'date', 'QSSEQ']).drop_duplicates('USUBJID'))
        expected = pd.concat(selected).groupby('USUBJID').QSSTRESN.mean()
        base = q[q.day.lt(1)].copy()
        base['distance'] = (base.day - 1).abs()
        base = base.sort_values(['USUBJID', 'distance', 'date', 'QSSEQ']).drop_duplicates('USUBJID').set_index('USUBJID').QSSTRESN
        npi = read(datasets, 'ADQSNPIX')
        # Representation contract: AVISITN=98 identifies the Week4–24 summary;
        # baseline-copy rows are excluded without depending on DTYPE wording.
        means = npi[npi.PARAMCD.eq('NPTOTMN') & npi.AVISITN.eq(98)].copy()
        add('npi_mean_coverage', len(expected),
            len(set(expected.index) ^ set(means.USUBJID)) + means.USUBJID.duplicated().sum())
        note = 'SV VISITNUM=3 date, DM.RFSTDTC fallback; same-date tie uses QSSEQ; population filtering not assessed.'
        add('npi_mean_value', len(means), (~same(means.AVAL, means.USUBJID.map(expected))).sum(), note)
        add('npi_baseline_covariate', len(means), (~same(means.BASE, means.USUBJID.map(base))).sum(), note)
    except Exception as exc:
        unavailable(npi_names, exc)

    tte_names = ['tte_subject_coverage', 'tte_source_link', 'tte_event_date',
                 'tte_event_status', 'tte_duration_arithmetic', 'tte_censor_convention']
    try:
        t, ae, adsl = [read(datasets, n) for n in ['ADTTE', 'ADAE', 'ADSL']]
        t = t[t.PARAMCD.eq('TTDE')].copy()
        dm = read(source / 'Input', 'DM')
        add('tte_subject_coverage', len(adsl),
            len(set(adsl.USUBJID) ^ set(t.USUBJID)) + t.USUBJID.duplicated().sum())
        qualifying = ae[ae.TRTEMFL.eq('Y') & ae.CQ01NAM.ne('') & ae.ASTDT.notna() & ae.ASTDT.ge(ae.TRTSDT)]
        first = qualifying.sort_values(['USUBJID', 'ASTDT', 'AESEQ']).drop_duplicates('USUBJID').set_index('USUBJID')
        add('tte_event_status', len(t), t.CNSR.ne(t.USUBJID.isin(first.index).map({True: 0, False: 1})).sum(),
            'Conditional on exported query and treatment-emergent flags.')
        events = t[t.CNSR.eq(0)].copy()
        # Prefix all ADAE fields to prevent ambiguous merge suffixes.
        link = events.merge(ae.add_prefix('ae_'), left_on=['USUBJID','SRCSEQ'],
                            right_on=['ae_USUBJID','ae_ASEQ'], how='left', validate='many_to_one', indicator=True)
        bad = (link['_merge'].ne('both') | link.SRCDOM.ne('ADAE') | link.SRCVAR.ne('ASTDT')
               | link.ae_AESEQ.ne(link.USUBJID.map(first.AESEQ))
               | ~same(link.ADT, link.ae_ASTDT))
        add('tte_source_link', len(events), bad.sum(), 'Exact predecessor identity, including same-date events.')
        add('tte_event_date', len(events), (~same(events.ADT, events.USUBJID.map(first.ASTDT))).sum(),
            'Conditional on exported treatment-emergent and dermatologic query flags; no medical adjudication.')
        add('tte_duration_arithmetic', len(t), (~same(t.AVAL, t.ADT-t.STARTDT+1)).sum(),
            'Implemented +1 convention; SAP does not explicitly prescribe it.')
        cens = t[t.CNSR.eq(1)]
        end = pd.Series(dates(dm.RFENDTC).to_numpy(), index=dm.USUBJID)
        add('tte_censor_convention', len(cens), (~same(cens.ADT, cens.USUBJID.map(end))).sum(),
            'DM.RFENDTC convention; not independently established by SAP.')
    except Exception as exc:
        unavailable(tte_names, exc)
    # A zero denominator is unavailable, never a zero-error success.
    for c in checks:
        if c['status'] == 'scored' and c['assessed'] == 0:
            c.update(status='unavailable', errors=None, reason='No assessable records')
    return {'scope': 'Selected independent derivation checks; not full SAP certification',
            'checks': checks, 'complete': all(c['status'] == 'scored' for c in checks)}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--datasets', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.write_text(json.dumps(score(a.source, a.datasets), indent=2) + '\n')


def paired_results(config, root):
    """Independent per-check comparisons, with all planned trials retained."""
    rules_path = Path(config['protocol_lock']).parent / 'scoring-rules.json'
    rules = json.loads(rules_path.read_text())
    names = rules['derivation_primary'] + rules['derivation_conditional'] + rules['derivation_exploratory']
    pairs = []
    for model in config['models']:
        for rep in range(1, config['repetitions']+1):
            trial = Path(root) / 'runs' / model['id'] / ('run_%02d' % rep)
            data = {}
            for branch, index in [('initial',0), ('self_review',config['repair_iterations']),
                                  ('p21_feedback',config['repair_iterations'])]:
                path = trial / branch / ('iteration_%02d' % index) / 'derivation.json'
                data[branch] = {c['check']:c for c in json.loads(path.read_text())['checks']} if path.exists() else {}
            for name in names:
                stages = {b:d.get(name,{}) for b,d in data.items()}
                coverage = rules['coverage_dependencies'].get(name)
                eligible = all(c.get('status') == 'scored' for c in stages.values())
                eligible = eligible and all(d.get(coverage,{}).get('errors') == 0 for d in data.values())
                eligible = eligible and len({c.get('assessed') for c in stages.values()}) == 1
                row = {'model':model['id'],'run':'run_%02d' % rep,'check':name,'eligible':eligible,
                       'stages':{b:{k:c.get(k) for k in ['status','assessed','errors']} for b,c in stages.items()}}
                if eligible:
                    row['feedback_advantage_errors'] = stages['self_review']['errors']-stages['p21_feedback']['errors']
                else:
                    row['reason'] = 'Missing/unavailable check, failed coverage, or unequal assessed denominators'
                pairs.append(row)
    return pairs
