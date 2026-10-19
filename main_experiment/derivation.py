"""Prespecified, host-only source checks. Never executes generated programs.

These checks cover selected derivations, not complete clinical correctness.
"""
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
        if q.duplicated(['USUBJID', 'QSSEQ']).any():
            raise ValueError('Duplicate NPTOT source sequences')
        visits = sv[sv.VISITNUM.eq(3)].copy()
        visits['date'] = dates(visits.SVSTDTC)
        randomized = dm[dm.ARMCD.isin(['Pbo', 'Xan_Lo', 'Xan_Hi'])].USUBJID
        visits = visits[visits.USUBJID.isin(randomized)].drop_duplicates(['USUBJID', 'date'])
        if visits.USUBJID.duplicated().any() or visits.date.isna().any() or set(visits.USUBJID) != set(randomized):
            raise ValueError('Randomization anchor must be unique, complete SV VISITNUM=3; no DM fallback')
        rand = visits.set_index('USUBJID').date
        q = q[q.USUBJID.isin(randomized)].copy()
        q['date'] = dates(q.QSDTC)
        q['day'] = q.date - q.USUBJID.map(rand)
        selected = []
        for week in range(4, 25, 2):
            v = q[q.day.between(7*week-6, 7*week+7)].copy()
            v['distance'] = (v.day - 7*week).abs()
            selected.append(v.sort_values(['USUBJID', 'distance', 'date', 'QSSEQ']).drop_duplicates('USUBJID'))
        expected = pd.concat(selected).groupby('USUBJID').QSSTRESN.mean()
        base = q[q.day.le(1)].copy()
        base['distance'] = (base.day - 1).abs()
        base = base.sort_values(['USUBJID', 'distance', 'date', 'QSSEQ']).drop_duplicates('USUBJID').set_index('USUBJID').QSSTRESN
        npi = read(datasets, 'ADQSNPIX')
        # Representation contract: AVISITN=98 identifies the Week4–24 summary;
        # baseline-copy rows are excluded without depending on DTYPE wording.
        means = npi[npi.PARAMCD.eq('NPTOTMN') & npi.AVISITN.eq(98)].copy()
        coverage = {'missing': len(set(expected.index)-set(means.USUBJID)),
                    'extra': len(set(means.USUBJID)-set(expected.index)),
                    'duplicates': int(means.USUBJID.duplicated().sum())}
        add('npi_mean_coverage', len(expected),
            len(set(expected.index) ^ set(means.USUBJID)) + means.USUBJID.duplicated().sum())
        checks[-1]['coverage'] = coverage
        note = 'Randomized DM arms; unique complete SV VISITNUM=3 anchor; baseline day <=1; ties distance/date/QSSEQ.'
        add('npi_mean_value', len(means), (~same(means.AVAL, means.USUBJID.map(expected))).sum(), note)
        add('npi_baseline_covariate', len(means), (~same(means.BASE, means.USUBJID.map(base))).sum(), note)
    except Exception as exc:
        unavailable(npi_names, exc)

    tte_names = ['tte_start_date', 'tte_subject_coverage', 'tte_source_link', 'tte_event_date',
                 'tte_event_status', 'tte_duration_arithmetic', 'tte_censor_convention']
    try:
        t, ae = [read(datasets, n) for n in ['ADTTE', 'ADAE']]
        t = t[t.PARAMCD.eq('TTDE')].copy()
        dm = read(source / 'Input', 'DM')
        ex = read(source / 'Input', 'EX')
        arm = dm.set_index('USUBJID').ARMCD
        exarm = ex.USUBJID.map(arm)
        complete = dates(ex.EXSTDTC).notna()
        placebo = exarm.eq('Pbo') & ex.EXTRT.eq('PLACEBO') & ex.EXDOSE.ge(0)
        active = exarm.isin(['Xan_Lo', 'Xan_Hi']) & ex.EXTRT.eq('XANOMELINE') & ex.EXDOSE.gt(0)
        safety = set(ex.loc[complete & (placebo | active), 'USUBJID'])
        add('tte_subject_coverage', len(safety),
            len(safety ^ set(t.USUBJID)) + t.USUBJID.duplicated().sum(),
            'POP01 source DM arms and complete randomized-treatment EX evidence; placebo dose >=0, active >0')
        end = pd.Series(dates(dm.RFENDTC).to_numpy(), index=dm.USUBJID)
        checks[-1]['coverage'] = {'missing': len(safety-set(t.USUBJID)),
            'extra': len(set(t.USUBJID)-safety), 'duplicates': int(t.USUBJID.duplicated().sum())}
        visits = read(source / 'Input', 'SV')
        visits = visits[visits.VISITNUM.eq(3)].copy()
        visits['date'] = dates(visits.SVSTDTC)
        visits = visits[visits.USUBJID.isin(safety)].drop_duplicates(['USUBJID', 'date'])
        if visits.USUBJID.duplicated().any() or visits.date.isna().any() or set(visits.USUBJID) != safety:
            raise ValueError('Safety subjects lack unique complete SV randomization anchors')
        start = visits.set_index('USUBJID').date
        if end.reindex(sorted(safety)).isna().any() or (end.reindex(start.index) < start).any():
            raise ValueError('Missing or invalid safety follow-up; not a fabricated censor')
        add('tte_start_date', len(t), (~same(t.STARTDT, t.USUBJID.map(start))).sum())
        qualifying = ae[ae.TRTEMFL.eq('Y') & ae.CQ01NAM.eq('DERMATOLOGIC EVENTS') & ae.ASTDT.notna() & ae.ASTDT.ge(ae.USUBJID.map(start)) & ae.ASTDT.le(ae.USUBJID.map(end))]
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
        add('tte_censor_convention', len(cens),
            ((~same(cens.ADT, cens.USUBJID.map(end))) | cens.SRCDOM.ne('ADSL') |
             cens.SRCVAR.ne('RFENDT') | cens.SRCSEQ.notna()).sum(),
            'DM.RFENDTC convention; not independently established by SAP.')
    except Exception as exc:
        unavailable(tte_names, exc)
    # A zero denominator is unavailable, never a zero-error success.
    for c in checks:
        if c['status'] == 'scored' and c['assessed'] == 0:
            c.update(status='unavailable', errors=None, reason='No assessable records')
    return {'scope': 'Selected independent derivation checks; not full SAP certification',
            'checks': checks, 'complete': all(c['status'] == 'scored' for c in checks)}
