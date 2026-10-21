"""Offline reporting only: one 16-row table for six excluded pilot examples."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

from main_experiment.coverage import compare

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


def collect(directory, model, condition):
    """Keep missing/failed runs explicit, never replace unavailable with zero errors."""
    state = read(directory/'state.json') or {'status': 'not_started'}
    es = [read(directory/phase/'evaluation.json') for phase in ('initial', 'final')]
    agents = [read(directory/phase/'agent.json') for phase in ('initial', 'final')]
    values = ['Unavailable'] * len(METRICS)
    status = state['status']
    values[0] = f'Status {status}; completed {int(status == "completed")}/1'
    final = es[1]
    if final:
        values[0] += f'; final 13 datasets {flag(final.get("dataset_set_complete"))}; required deliverables {flag(final.get("deliverables_complete"))}'
        values[1] = f'Semantic {flag(final.get("semantic_reproduced"))}; exact bytes {flag(final.get("byte_reproduced"))}'
        c = final.get('conformance') or {}
        values[2] = f'Usable {int(c.get("report_usable") is True)}/1; full coverage {c.get("validation_coverage_complete", "Unavailable")}; validated {len(c.get("validated_datasets") or [])}/13'
        severity = defaultdict(set)
        for issue in c.get('issues', []):
            severity[issue['severity']].add((issue['dataset'], issue['rule']))
        values[5] = ('; '.join(f'{name}: {len(pairs)} pairs' for name, pairs in sorted(severity.items())) or 'No recorded pairs') if c.get('report_usable') else 'Unavailable; no usable report'
    values[3] = '; '.join(f'{phase}: pairs {((e or {}).get("conformance") or {}).get("dataset_rule_pairs", "Unavailable")}, instances {((e or {}).get("conformance") or {}).get("finding_instances", "Unavailable")}, distinct rules {((e or {}).get("conformance") or {}).get("distinct_rules", "Unavailable")}' for phase, e in zip(('Initial', 'Final'), es))
    guard = compare(*es)
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
    return {'model': model, 'condition': condition, 'status': status, 'values': values, 'source_sha256': hashes}


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
    (a.out/'metrics.json').write_text(json.dumps(data, indent=2)+'\n')
    headers = ['No.', 'Metric'] + [r['model']+' / '+r['condition'] for r in records]
    rows = [[i+1, name] + [r['values'][i] for r in records] for i, name in enumerate(METRICS)]
    with (a.out/'metrics.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    lines = ['# Excluded pre experiment metrics', '', data['scope'], '', data['mapping'], '', '| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']
    lines += ['| '+' | '.join(str(v).replace('\n', '<br>').replace('|', '/') for v in row)+' |' for row in rows]
    lines += ['', '## Qualifications', ''] + ['- '+note for note in data['limitations']]
    (a.out/'metrics.md').write_text('\n'.join(lines)+'\n')
    print('Saved 16 reporting rows across six planned examples; no provider calls.')


if __name__ == '__main__':
    main()
