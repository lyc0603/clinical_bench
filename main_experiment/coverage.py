"""Host-only conservative screening; flags require review, never automatic waivers."""
from collections import Counter
import hashlib
import json
from pathlib import Path


def profile(datasets, expected):
    import pyreadstat
    result = {'status': 'available', 'datasets': {}}
    for domain in expected:
        path = Path(datasets) / (domain.lower() + '.xpt')
        try:
            frame, _ = pyreadstat.read_xport(str(path), disable_datetime_conversion=True)
            present = frame.notna()
            for col in frame.select_dtypes(include=['object', 'string']).columns:
                present[col] &= frame[col].astype('string').str.strip().ne('').fillna(False)
            def coverage(columns):
                # Hash identities so reports contain counts rather than subject identifiers.
                if not all(c in frame for c in columns):
                    return None
                rows = frame.loc[present[columns].all(axis=1), columns]
                return dict(Counter(hashlib.sha256(json.dumps(list(row), default=str).encode()).hexdigest()
                                    for row in rows.itertuples(index=False, name=None)))
            result['datasets'][domain] = {'status': 'available', 'rows': len(frame),
                'nonmissing': {c: int(present[c].sum()) for c in frame},
                'subjects': coverage(['USUBJID']),
                'subject_parameters': coverage(['USUBJID', 'PARAMCD'])}
        except Exception as exc:
            result['status'] = 'unavailable'
            result['datasets'][domain] = {'status': 'unavailable', 'reason': type(exc).__name__ + ': ' + str(exc)}
    return result


def compare(initial, final):
    """No detected regression is limited to measured coverage and independent checks."""
    flags = []
    unavailable = []
    before, after = [(x or {}).get('content_profile') or {} for x in (initial, final)]
    domains = set(before.get('datasets', {})) | set(after.get('datasets', {}))
    if not domains:
        unavailable.append('content_profiles_missing')
    for domain in sorted(domains):
        a, b = [x.get('datasets', {}).get(domain, {}) for x in (before, after)]
        if any(x.get('status') != 'available' for x in (a, b)):
            unavailable.append(domain + ':profile_unavailable')
            continue
        if b['rows'] == 0:
            flags.append(domain + ':empty_dataset')
        if b['rows'] < a['rows']:
            flags.append(domain + ':row_count_decreased')
        for col, count in a['nonmissing'].items():
            if col not in b['nonmissing']:
                flags.append(domain + ':column_removed:' + col)
            elif b['nonmissing'][col] < count:
                flags.append(domain + ':nonmissing_count_decreased:' + col)
        for key in ('subjects', 'subject_parameters'):
            if a[key] is not None and b[key] is None:
                flags.append(domain + ':' + key + '_unavailable')
            elif a[key] is not None:
                if set(a[key]) - set(b[key]):
                    flags.append(domain + ':' + key + '_lost')
                if any(b[key].get(k, 0) < n for k, n in a[key].items()):
                    flags.append(domain + ':' + key + '_record_coverage_decreased')
    independent = ('npi_mean_coverage', 'npi_mean_value', 'npi_baseline_covariate')
    checks = [{c['check']: c for c in ((x or {}).get('correctness') or {}).get('checks', [])}
              for x in (initial, final)]
    for name in independent:
        a, b = [x.get(name, {}) for x in checks]
        if any(x.get('status') != 'scored' for x in (a, b)):
            unavailable.append(name + ':unavailable')
        elif b['errors'] > a['errors'] or b['assessed'] < a['assessed']:
            flags.append(name + ':independent_check_regression')
    return {'status': 'review_required' if flags else 'unavailable' if unavailable else 'no_detected_regression',
            'flags': flags, 'unavailable': unavailable,
            'qualification': 'Conservative screening, not full derivation correctness. Legitimate duplicate removal may flag; no automatic adjudication or waiver.'}
