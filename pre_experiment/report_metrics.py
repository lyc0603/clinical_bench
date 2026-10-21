"""Offline reporting only: one 16-row table for six excluded pilot examples."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

from main_experiment.coverage import compare
from main_experiment.support import report_metrics

METRICS = [
    'Workflow completion and complete dataset packages',
    'Reproducible final packages', 'Valid final P21 evaluations',
    'Initial and final dataset-rule pairs', 'Reduction from initial to final',
    'Final findings by severity', 'Newly introduced dataset-rule pairs',
    'NPI summary errors / assessed records', 'NPI baseline errors / assessed records',
    'TTE linkage errors / assessed records', 'Missing extra and duplicate expected records',
    'Assessable checks / planned checks', 'Workflow API cost estimate in USD',
    'Input and output tokens', 'End-to-end elapsed time in minutes',
    'Tool calls and failed tool calls',
]


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def flag(value):
    return 'Unavailable' if value is None else str(int(bool(value)))+'/1'


def metric_value(conformance, name):
    value = ((conformance or {}).get('conformance') or {}).get(name)
    return 'Unavailable' if value is None else value


def readable_package(e):
    if e.get('dataset_set_complete') is not True:
        return e.get('dataset_set_complete')
    profiles = (e.get('content_profile') or {}).get('datasets')
    if not profiles:
        return None
    return len(profiles) == 13 and all(p.get('status') == 'available' for p in profiles.values())


def phase_numbers(evaluation, agent):
    e, a = evaluation or {}, agent or {}
    c = e.get('conformance') or {}
    usage = (a.get('completion') or {}).get('export_usage')
    tokens = None
    if usage is not None:
        tokens = {key: sum((item.get('tokens') or {}).get(key) or 0 for item in usage) for key in ('input', 'output', 'reasoning')}
        for key in ('read', 'write'):
            tokens['cache_'+key] = sum(((item.get('tokens') or {}).get('cache') or {}).get(key) or 0 for item in usage)
        tokens['normalized_input'] = tokens['input'] + tokens['cache_read'] + tokens['cache_write']
        tokens['normalized_output'] = tokens['output'] + tokens['reasoning']
    severity = defaultdict(set)
    if c.get('report_usable'):
        for issue in c.get('issues', []):
            severity[issue['severity']].add((issue['dataset'], issue['rule']))
    return {
        'dataset_set_complete': e.get('dataset_set_complete'),
        'readable_dataset_package': readable_package(e),
        'deliverables_complete': e.get('deliverables_complete'),
        'semantic_reproduced': e.get('semantic_reproduced'), 'byte_reproduced': e.get('byte_reproduced'),
        'report_usable': c.get('report_usable'), 'validation_coverage_complete': c.get('validation_coverage_complete'),
        'dataset_rule_pairs': c.get('dataset_rule_pairs'), 'finding_instances': c.get('finding_instances'),
        'distinct_rules': c.get('distinct_rules'),
        'severity_pairs': {name: len(pairs) for name, pairs in severity.items()} if c.get('report_usable') else None,
        'cost_estimate_usd': sum(item['cost'] for item in usage) if usage is not None and all(item.get('cost') is not None for item in usage) else None,
        'tokens': tokens, 'agent_seconds': a.get('seconds'), 'tool_calls': a.get('tool_calls'),
        'tool_failures': a.get('tool_failures'),
    }


def collect(directory, model, condition):
    """Keep missing/failed runs explicit, never replace unavailable with zero errors."""
    state = read(directory/'state.json') or {'status': 'not_started'}
    es = [read(directory/phase/'evaluation.json') for phase in ('initial', 'final')]
    agents = [read(directory/phase/'agent.json') for phase in ('initial', 'final')]
    values = ['Unavailable'] * len(METRICS)
    observed = []
    for phase, e in zip(('initial', 'final'), es):
        path = directory/phase/'p21_adam.xlsx'
        if e and path.exists() and not (e.get('conformance') or {}).get('report_usable'):
            try:
                domains = sorted(p.stem.upper() for p in (directory/phase/'workspace/output/adam/datasets').glob('*.xpt'))
                parsed = report_metrics(path, domains, ['FDA 2508.1', '1.0.9', '2026-03-27', 'ADaM-IG 1.3 (FDA).xml', 'MedDRA', '8.0'])
                observed.append({'phase': phase, 'qualification': 'Unqualified observed report only; original runtime-integrity failure unchanged', **{key: parsed[key] for key in ('dataset_rule_pairs', 'finding_instances', 'distinct_rules', 'report_sha256')}})
            except Exception as error:
                observed.append({'phase': phase, 'qualification': 'Saved report could not be parsed', 'parse_error_type': type(error).__name__})
    status = state['status']
    values[0] = f'Status {status}; completed {int(status == "completed")}/1'
    final = es[1]
    if final:
        values[0] += f'; final 13 readable datasets {flag(readable_package(final))}; file set {flag(final.get("dataset_set_complete"))}; required deliverables {flag(final.get("deliverables_complete"))}'
        values[1] = f'Semantic {flag(final.get("semantic_reproduced"))}; exact bytes {flag(final.get("byte_reproduced"))}'
        c = final.get('conformance') or {}
        validated = c.get('validated_datasets')
        coverage = 'Unavailable' if validated is None else str(len(validated))+'/13'
        values[2] = f'Usable {flag(c.get("report_usable"))}; full coverage {c.get("validation_coverage_complete", "Unavailable")}; validated {coverage}'
        if c.get('reason'):
            values[2] += '; reason: '+c['reason']
        severity = defaultdict(set)
        for issue in c.get('issues', []):
            severity[issue['severity']].add((issue['dataset'], issue['rule']))
        values[5] = ('; '.join(f'{name}: {len(pairs)} pairs' for name, pairs in sorted(severity.items())) or 'No recorded pairs') if c.get('report_usable') else 'Unavailable; no usable report'
    values[3] = '; '.join(f'{phase}: pairs {metric_value(e, "dataset_rule_pairs")}, instances {metric_value(e, "finding_instances")}, distinct rules {metric_value(e, "distinct_rules")}' for phase, e in zip(('Initial', 'Final'), es))
    observed_lines = []
    for item in observed:
        if 'dataset_rule_pairs' in item:
            observed_lines.append(f'Unqualified observed {item["phase"]}: {item["dataset_rule_pairs"]:,} pairs, {item["finding_instances"]:,} instances, {item["distinct_rules"]:,} distinct rules (not scored)')
    if observed_lines:
        values[3] = '\n'.join(observed_lines + [values[3]])
    guard = compare(*es)
    values[4] = f'Raw Unavailable; guarded Unavailable; {guard["status"]}; {len(guard["flags"])} flags'
    complete = all(e and e.get('deliverables_complete') and (e.get('conformance') or {}).get('validation_coverage_complete') and (e.get('conformance') or {}).get('dataset_rule_pairs') is not None for e in es)
    if complete:
        pairsets = [{(i['dataset'], i['rule']) for i in e['conformance']['issues']} for e in es]
        reduction = len(pairsets[0]) - len(pairsets[1])
        guarded = reduction if guard['status'] == 'no_detected_regression' else 'Unavailable'
        values[4] = f'Raw {reduction}; guarded {guarded}; {guard["status"]}; {len(guard["flags"])} flags'
        values[6] = f'New {len(pairsets[1]-pairsets[0])}; resolved {len(pairsets[0]-pairsets[1])}; persistent {len(pairsets[0]&pairsets[1])}'
    checks = [{x['check']: x for x in ((e or {}).get('correctness') or {}).get('checks', [])} for e in es]
    for idx, name in ((7, 'npi_mean_value'), (8, 'npi_baseline_covariate'), (9, 'tte_source_link')):
        parts = []
        for phase, checkset in zip(('Initial', 'Final'), checks):
            c = checkset.get(name)
            text = f'{c["errors"]}/{c["assessed"]} errors/assessed' if c and c['status'] == 'scored' else 'Unavailable (assessed '+str((c or {}).get('assessed', 'unknown'))+')'
            parts.append(phase+': '+text)
        values[idx] = '; '.join(parts)
    coverage = []
    for phase, checkset in zip(('Initial', 'Final'), checks):
        for label, name in (('NPI', 'npi_mean_coverage'), ('TTE', 'tte_subject_coverage')):
            c = checkset.get(name, {}).get('coverage')
            coverage.append(f'{phase} {label}: missing {c["missing"]}, extra {c["extra"]}, duplicates {c["duplicates"]}' if c else f'{phase} {label}: Unavailable')
    values[10] = '; '.join(coverage)
    values[11] = '; '.join(f'{phase}: {sum(c["status"] == "scored" for c in checkset.values())}/{len(checkset)} planned checks' if checkset else phase+': Unavailable' for phase, checkset in zip(('Initial', 'Final'), checks)) + '; applicable denominator not adjudicated'
    usages = [(a or {}).get('completion', {}).get('export_usage') for a in agents]
    if all(u is not None for u in usages):
        ids = [item['message_id'] for usage in usages for item in usage]
        if len(ids) != len(set(ids)):
            raise ValueError('Overlapping usage message IDs')
        costs = [sum(item.get('cost') or 0 for item in usage) for usage in usages]
        values[12] = f'Generation ${costs[0]:.4f}; repair ${costs[1]:.4f}; total ${sum(costs):.4f} (estimate, not invoice)'
        token_parts = []
        totals = defaultdict(int)
        for phase, usage in zip(('Generation', 'Repair'), usages):
            t = {key: sum((item.get('tokens') or {}).get(key) or 0 for item in usage) for key in ('input', 'output', 'reasoning')}
            for key in ('read', 'write'):
                t['cache_'+key] = sum(((item.get('tokens') or {}).get('cache') or {}).get(key) or 0 for item in usage)
            for key, value in t.items():
                totals[key] += value
            token_parts.append(token_text(phase, t))
        values[13] = '\n'.join(token_parts + [token_text('Total', totals)])
    if state.get('finished_unix') and state.get('started_unix'):
        values[14] = f'End to end {(state["finished_unix"]-state["started_unix"])/60:.2f} min'
        if all(a and 'seconds' in a for a in agents):
            values[14] += f'; agent total {sum(a["seconds"] for a in agents)/60:.2f}; generation {agents[0]["seconds"]/60:.2f}; repair {agents[1]["seconds"]/60:.2f} min'
    if all(a and 'tool_calls' in a for a in agents):
        values[15] = '; '.join(f'{phase}: {a["tool_calls"]} calls, {a["tool_failures"]} failed' for phase, a in zip(('Generation', 'Repair'), agents))
        values[15] += f'; total {sum(a["tool_calls"] for a in agents)} calls, {sum(a["tool_failures"] for a in agents)} failed'
    hashes = {}
    for path in [directory/'state.json'] + [directory/phase/name for phase in ('initial', 'final') for name in ('evaluation.json', 'agent.json', 'checkpoint-manifest.json')]:
        if path.exists():
            hashes[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    detail = []
    for phase, checkset in zip(('initial', 'final'), checks):
        for check in checkset.values():
            item = {'phase': phase, **{key: check.get(key) for key in ('check', 'status', 'assessed', 'errors')}}
            item.update({key: (check.get('coverage') or {}).get(key) for key in ('missing', 'extra', 'duplicates')})
            detail.append(item)
    numbers = {phase: phase_numbers(e, a) for phase, e, a in zip(('initial', 'final'), es, agents)}
    numbers['workflow_seconds'] = state['finished_unix']-state['started_unix'] if state.get('finished_unix') and state.get('started_unix') else None
    numbers['content_guard_status'] = guard['status']
    numbers['content_guard_flags'] = len(guard['flags'])
    numbers['pair_reduction'] = reduction if complete else None
    numbers['guarded_pair_reduction'] = reduction if complete and guard['status'] == 'no_detected_regression' else None
    numbers['new_pairs'] = sorted(pairsets[1]-pairsets[0]) if complete else None
    numbers['resolved_pairs'] = sorted(pairsets[0]-pairsets[1]) if complete else None
    return {'model': model, 'condition': condition, 'status': status, 'values': values, 'source_sha256': hashes, 'auxiliary_checks': detail, 'numeric': numbers, 'unqualified_report_observations': observed}


def token_text(phase, t):
    return f'{phase}: input {t["input"]+t["cache_read"]+t["cache_write"]:,}; output {t["output"]+t["reasoning"]:,}; uncached {t["input"]:,}; cache read {t["cache_read"]:,}; cache write {t["cache_write"]:,}; text output {t["output"]:,}; reasoning {t["reasoning"]:,}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-root', type=Path, required=True)
    p.add_argument('--self-review-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    records = []
    for model, folder in [('openai', 'smokes-v2'), ('anthropic', 'smokes-anthropic-post-topup'), ('google', 'smokes-google-new-key')]:
        records.append(collect(a.baseline_root/folder/model, model, 'p21_feedback'))
        records.append(collect(a.self_review_root/model, model, 'self_review'))
    a.out.mkdir(parents=True, exist_ok=True)
    data = {'scope': 'Excluded nonconcurrent pre-experiment; one workflow per model and condition; no main-study observations',
            'mapping': '18 original reporting rows combined into 16: completion with dataset delivery; initial with final pair counts',
            'metrics': METRICS, 'records': records,
            'limitations': ['Descriptive only; baseline smokes were already observed before self-review runs.', 'All workflows use the same OpenCode framework; ReAct is not a separate condition.', 'Costs are normalized telemetry estimates, not actual invoices or total historical qualification expenditure.', 'Input includes cached read/write; output includes reasoning. Provider billing semantics are not independently reconciled.', 'Applicable check denominator is not adjudicated; report planned-check coverage.', 'Content guards and selected derivation checks do not establish full clinical correctness.']}
    adjudication = read(a.self_review_root/'technical-adjudication.json')
    if adjudication:
        data['technical_adjudication'] = adjudication
        data['limitations'] += ['Self-review P21 outcomes affected by the runtime-integrity rule remain unavailable. Saved-report observations are explicitly unqualified diagnostic counts, not substituted scores or evidence of effective improvement.', 'A host-only P21 diagnostic overlapped Google review. After Google completed, scheduling paused; the original seal was verified before remaining providers resumed. Timing is descriptive and may include host-load effects.']
    (a.out/'metrics.json').write_text(json.dumps(data, indent=2)+'\n')
    headers = ['No.', 'Metric'] + [r['model']+' / '+r['condition'] for r in records]
    rows = [[i+1, name] + [r['values'][i] for r in records] for i, name in enumerate(METRICS)]
    with (a.out/'metrics.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    with (a.out/'auxiliary-checks.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['model', 'condition', 'phase', 'check', 'status', 'assessed', 'errors', 'missing', 'extra', 'duplicates'])
        writer.writeheader()
        for record in records:
            for check in record['auxiliary_checks']:
                writer.writerow({'model': record['model'], 'condition': record['condition'], **check})
    lines = ['# Excluded pre experiment metrics', '', data['scope'], '', data['mapping'], '', '| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']
    lines += ['| '+' | '.join(str(v).replace('\n', '<br>').replace('|', '/') for v in row)+' |' for row in rows]
    lines += ['', '## Qualifications', ''] + ['- '+note for note in data['limitations']]
    (a.out/'metrics.md').write_text('\n'.join(lines)+'\n')
    print('Saved 16 reporting rows across six planned examples; no provider calls.')


if __name__ == '__main__':
    main()
