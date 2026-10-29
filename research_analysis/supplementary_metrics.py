"""Retrospective, offline coverage and failure-stage analysis of frozen artifacts."""
import argparse
import copy
import csv
import json
import re
from collections import Counter
from pathlib import Path

from lxml import etree
import pyreadstat

from main_experiment.support import digest, save

METRICS = ['Dataset Delivery Rate', 'Variable Coverage', 'Failure-stage distribution']
STAGES = ['input_reading', 'code_execution', 'dataset_export',
          'define_xml_generation', 'rebuilding', 'p21_validation']


def read(path):
    return json.loads(path.read_text()) if path.is_file() else None


def inventory(path):
    sheets = read(path)['sheets']
    domains = [r[0] for r in sheets['Datasets'][1:] if r[0]]
    result = {}
    for domain in domains:
        rows = sheets[domain]
        columns = {name: i for i, name in enumerate(rows[0])}
        variables = {}
        for row in rows[1:]:
            name = row[columns['Variable']]
            if not name:
                continue
            kind = row[columns['Type']]
            if name in variables or kind not in ('Numeric', 'Character'):
                raise ValueError('Invalid frozen variable inventory')
            variables[name] = kind
        result[domain] = variables
    if len(result) != 13 or sum(map(len, result.values())) != 531:
        raise ValueError('Expected thirteen datasets and 531 dataset-variable pairs')
    return result


def schema_counts(expected, actual):
    """Exact case-sensitive names and XPT numeric/character storage classes."""
    matched = sum(actual.get(k) == v for k, v in expected.items())
    return {'expected_variables': len(expected), 'matched_variables': matched,
            'missing_variables': sum(k not in actual for k in expected),
            'wrong_type_variables': sum(k in actual and actual[k] != v for k, v in expected.items()),
            'extra_variables': len(set(actual) - set(expected))}


def tool_evidence(path):
    """Current-phase events only: final history exports include the initial turn."""
    if not path.is_file():
        return {'available': False, 'input_errors': 0, 'execution_errors': 0,
                'execution_attempts': 0, 'unclassified_tool_errors': 0}
    events = {}
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = row.get('part') or {}
        if row.get('type') == 'tool_use' and part.get('id'):
            events[part['id']] = part
    counts = dict(available=True, input_errors=0, execution_errors=0,
                  execution_attempts=0, unclassified_tool_errors=0)
    for part in events.values():
        state = part.get('state') or {}
        args = state.get('input') or {}
        if not isinstance(args, dict):
            args = {}
        metadata = state.get('metadata') or {}
        text = str(state.get('error') or '') + '\n' + str(state.get('output') or '')
        command = str(args.get('command') or '')
        exit_code = metadata.get('exit', metadata.get('exitCode', metadata.get('exit_code')))
        nonzero = exit_code is not None and str(exit_code) != '0'
        failed = state.get('status') == 'error' or nonzero or bool(re.search(r'Process exited with code [1-9]\d*', text))
        executable = part.get('tool') == 'bash' and bool(re.search(r'\b(?:python[\d.]*|Rscript|sas|R\s+-[ef])\b', command))
        if executable:
            counts['execution_attempts'] += 1
        input_target = any(str(args.get(k) or '').startswith('/inputs/') for k in ('filePath', 'path'))
        input_error = failed and (input_target or
            ('/inputs/' in text and bool(re.search(r'FileNotFoundError|PermissionError|No such file|cannot open|unable to open', text, re.I))))
        execution_error = failed and executable
        counts['input_errors'] += int(input_error)
        counts['execution_errors'] += int(execution_error)
        counts['unclassified_tool_errors'] += int(failed and not input_error and not execution_error)
    return counts


def stage_states(tools, delivery, define_ok, evaluation, workspace):
    result = {
        'input_reading': 'failed' if tools['input_errors'] else 'no_failure_observed' if tools['available'] else 'unavailable',
        'code_execution': 'failed' if tools['execution_errors'] else 'no_failure_observed' if tools['execution_attempts'] else 'not_observed',
        'dataset_export': 'no_failure_observed' if delivery == 13 else 'failed',
        'define_xml_generation': 'no_failure_observed' if define_ok else 'failed',
    }
    rebuild = evaluation.get('rebuild') or {}
    program = workspace / 'output/adam/programs/rebuild.py'
    if not program.is_file():
        result['rebuilding'] = 'blocked'
    elif evaluation.get('rebuild_error') or rebuild.get('timed_out') or rebuild.get('exit_code') not in (None, 0):
        result['rebuilding'] = 'failed'
    elif evaluation.get('semantic_reproduced') is False:
        result['rebuilding'] = 'failed'
    elif evaluation.get('semantic_reproduced') is True:
        result['rebuilding'] = 'no_failure_observed'
    else:
        result['rebuilding'] = 'unavailable'
    p21 = evaluation.get('conformance') or {}
    if p21.get('report_usable') is True:
        result['p21_validation'] = 'usable_report'
    elif not define_ok or delivery == 0:
        result['p21_validation'] = 'blocked'
    elif p21.get('report_usable') is False or p21.get('failure_code'):
        result['p21_validation'] = 'failed'
    else:
        result['p21_validation'] = 'unavailable'
    return result


def phase_metrics(directory, expected):
    evaluation = read(directory / 'evaluation.json')
    workspace = directory / 'workspace'
    wm = read(directory / 'workspace-manifest.json')
    if evaluation is None or not workspace.is_dir() or wm is None:
        return {'status': 'unavailable', 'reason': 'Retained evaluated workspace or manifest unavailable',
                'stages': {k: 'unavailable' for k in STAGES}}
    def verified(path):
        key = str(path.relative_to(workspace))
        if not path.is_file():
            if key in wm:
                raise ValueError('Retained artifact lost: ' + key)
            return False
        if key not in wm or digest(path) != wm[key]:
            raise ValueError('Measured artifact differs from retained manifest: ' + key)
        return True
    datasets = workspace / 'output/adam/datasets'
    counts = {}
    file_hashes = {}
    for domain, variables in expected.items():
        path = datasets / (domain.lower() + '.xpt')
        if not verified(path):
            counts[domain] = {'status': 'missing', **schema_counts(variables, {})}
            continue
        file_hashes[path.name] = digest(path)
        try:
            prior_profile = (evaluation.get('content_profile') or {}).get('datasets', {}).get(domain, {})
            # A full-read evaluator profile already establishes readability for
            # this hash-verified file. Re-read its schema without loading rows.
            _, metadata = pyreadstat.read_xport(str(path), disable_datetime_conversion=True,
                                               metadataonly=prior_profile.get('status') == 'available')
            actual = {k: 'Character' if v == 'string' else 'Numeric' if v in
                      ('double', 'float', 'int8', 'int16', 'int32') else 'Unknown'
                      for k, v in metadata.readstat_variable_types.items()}
            counts[domain] = {'status': 'readable', **schema_counts(variables, actual)}
        except Exception as error:
            counts[domain] = {'status': 'unreadable', 'error_type': type(error).__name__,
                              'expected_variables': len(variables), 'matched_variables': None}
    delivered = sum(x['status'] == 'readable' for x in counts.values())
    unmatched_schema = sum(x['expected_variables'] for x in counts.values() if x['status'] == 'unreadable')
    matched = sum(x['matched_variables'] or 0 for x in counts.values())
    total = sum(map(len, expected.values()))
    define = datasets / 'define.xml'
    define_ok = False
    if verified(define):
        file_hashes['define.xml'] = digest(define)
        try:
            root = etree.parse(str(define), etree.XMLParser(resolve_entities=False, no_network=True)).getroot()
            define_ok = etree.QName(root).localname == 'ODM'
        except etree.XMLSyntaxError:
            pass
    verified(workspace / 'output/adam/programs/rebuild.py')
    checkpoint = read(directory / 'checkpoint-manifest.json')
    log = directory / 'agent.jsonl'
    if checkpoint and log.is_file() and digest(log) != checkpoint.get('agent.jsonl'):
        raise ValueError('Tool evidence differs from checkpoint manifest')
    tools = tool_evidence(log)
    stages = stage_states(tools, delivered, define_ok, evaluation, workspace)
    agent = read(directory / 'agent.json') or {}
    sources = {name: digest(directory / name) for name in
               ('evaluation.json', 'workspace-manifest.json', 'agent.jsonl') if (directory / name).is_file()}
    return {'status': 'assessed', 'dataset_delivery': {'delivered': delivered, 'expected': 13, 'rate': delivered / 13},
            'variable_coverage': {'matched': matched if not unmatched_schema else None, 'expected': total,
                'rate': matched / total if not unmatched_schema else None,
                'confirmed_matched': matched, 'unassessed_variables': unmatched_schema},
            'datasets': counts, 'stages': stages, 'tool_evidence': tools,
            'original_p21_failure_code': (evaluation.get('conformance') or {}).get('failure_code'),
            'controller_or_provider_failure': bool(agent.get('provider_errors')) or
                agent.get('completion', {}).get('normal') is False or agent.get('exit_code') not in (None, 0),
            'source_sha256': sources, 'dataset_file_sha256': file_hashes}


def display_rate(value, numerator, denominator):
    if not value or value.get('rate') is None:
        return 'Unavailable'
    return f"{value[numerator]}/{value[denominator]} ({100 * value['rate']:.1f}%)"


def stage_text(value):
    if value['status'] != 'assessed':
        return 'Unavailable'
    failed = [k for k, v in value['stages'].items() if v == 'failed']
    blocked = [k for k, v in value['stages'].items() if v == 'blocked']
    label = 'Failed: ' + (', '.join(failed) or 'none observed')
    if blocked:
        label += '; Blocked: ' + ', '.join(blocked)
    if value['controller_or_provider_failure']:
        label += '; controller/provider failure recorded separately'
    if value['tool_evidence']['unclassified_tool_errors']:
        label += '; unclassified tool errors: ' + str(value['tool_evidence']['unclassified_tool_errors'])
    return label


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'source-map', 'specifications', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    data = read(args.previous)
    original = copy.deepcopy(data)
    if len(data['metrics']) != 16 or len(data['records']) != 24:
        raise ValueError('Expected unchanged 16-metric, 24-endpoint source report')
    expected = inventory(args.specifications)
    mapping = read(args.source_map)
    if [x['index'] for x in mapping] != list(range(24)):
        raise ValueError('Source mapping must cover all endpoints in original order')
    audit = []
    for index, (record, entry) in enumerate(zip(data['records'], mapping)):
        print('Auditing endpoint ' + str(index + 1) + '/24', flush=True)
        source = Path(entry['source'])
        for name, sha in record['source_sha256'].items():
            if name.startswith('current_revalidation/'):
                continue
            if digest(source / name) != sha:
                raise ValueError('Source receipt changed: ' + name)
        phases = ('initial',) if record['condition'] == 'initial_only' else ('initial', 'final')
        values = {phase: phase_metrics(source / phase, expected) for phase in phases}
        terminal = 'initial' if record['condition'] == 'initial_only' else 'final'
        values['terminal'] = copy.deepcopy(values[terminal])
        record['supplementary_metrics'] = values
        rows = [[], [], []]
        for phase in phases:
            value = values[phase]
            label = 'Initial/terminal' if record['condition'] == 'initial_only' else phase.title()
            rows[0].append(label + ': ' + display_rate(value.get('dataset_delivery'), 'delivered', 'expected'))
            rows[1].append(label + ': ' + display_rate(value.get('variable_coverage'), 'matched', 'expected'))
            rows[2].append(label + ': ' + stage_text(value))
        record['values'] += ['\n'.join(row) for row in rows]
        assert record['values'][:16] == original['records'][index]['values']
        audit.append({'endpoint_index': index, 'source_state_sha256': digest(source / 'state.json'),
                      'phases': {phase: values[phase].get('source_sha256') for phase in phases}})
    data['metrics'] += METRICS
    data['scope'] = 'Retrospective 19-metric exploratory table across 24 retained endpoints; original sixteen metrics unchanged'
    data['supplementary_analysis'] = {'date': '2026-10-28', 'prespecified': False,
        'previous_report_sha256': digest(args.previous), 'specifications_sha256': digest(args.specifications),
        'script_sha256': digest(Path(__file__)), 'source_map_sha256': digest(args.source_map),
        'expected_datasets': 13, 'expected_dataset_variable_pairs': 531,
        'original_sixteen_metrics_unchanged': True, 'new_model_or_validator_calls': 0,
        'definitions': {
            'dataset_delivery': 'Readable expected lowercase XPT files / 13; absent or unreadable files do not count. Extra datasets do not increase numerator.',
            'variable_coverage': 'Sum of expected exact-case dataset-variable names with correct Numeric/Character XPT storage class / 531. Missing datasets contribute zero. Unreadable schemas make the exact overall rate unavailable. Length, format, values and row completeness are not assessed.',
            'failure_stages': 'Nonexclusive observed phase-level stage indicators. Failed includes missing required delivery; blocked means known missing prerequisites. Counts are endpoints, not error-event counts. No failure observed does not prove successful execution. Original P21 execution is used; reassessment never erases original failure. Usable reports with findings do not count as validator execution failures.'}}
    data['limitations'] += [
        'The three added metrics are retrospective exploratory analyses defined after seeing pilot outcomes; the original sixteen metrics, scores and records are preserved.',
        'Delivery and variable coverage assess retained evaluated snapshots, including a snapshot from a failed controller where available. They do not establish task success, correct records, correct values, metadata conformance or reproducibility.',
        'Failure-stage indicators are nonexclusive and include downstream consequences. Missing datasets/Define-XML are delivery failures, not proof of a particular failed export command. Blocked rebuild/P21 stages are distinguished from direct failures.',
        'Input/code failures require direct current-phase tool execution evidence. No observed failure is not proof of a stage passing; unclassified tool errors and controller/provider failures remain separate. Recovered tool failures remain counted in that phase.',
        'Distribution denominators are table endpoints, not independent trials: some historical initial-only and self-review endpoints share an initial generation; model settings and historical environments differ. Do not use pooled counts for causal or inferential comparisons.',
        'P21 failure classification uses original evaluation receipts, while original metric 3 can show later reassessment. These answer different questions and must not be conflated.'
    ]
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'metrics.json', data)
    save(out / 'supplementary-audit.json', {'analysis': data['supplementary_analysis'], 'endpoints': audit})
    headers = ['No.', 'Metric'] + [r.get('endpoint_label', r['model'] + ' / ' + r['condition']) for r in data['records']]
    rows = [[i + 1, m] + [r['values'][i] for r in data['records']] for i, m in enumerate(data['metrics'])]
    with (out / 'metrics.csv').open('w', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(headers); w.writerows(rows)
    lines = ['# Exploratory results: 19 metrics across 24 endpoints', '', data['scope'], '',
             '| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    lines += ['| ' + ' | '.join(str(x).replace('\n', '<br>').replace('|', '/') for x in row) + ' |' for row in rows]
    lines += ['', '## Interpretation limits', ''] + ['- ' + x for x in data['limitations']]
    (out / 'metrics.md').write_text('\n'.join(lines) + '\n')
    distribution = []
    for phase in ('initial', 'final', 'terminal'):
        endpoints = [r for r in data['records'] if phase in r['supplementary_metrics']]
        for stage in STAGES:
            states = Counter(r['supplementary_metrics'][phase]['stages'][stage] for r in endpoints)
            distribution.append({'phase': phase, 'stage': stage, 'endpoints': len(endpoints),
                **{k: states[k] for k in ('failed', 'blocked', 'unavailable', 'not_observed', 'no_failure_observed', 'usable_report')}})
    save(out / 'failure-stage-distribution.json', distribution)
    with (out / 'failure-stage-distribution.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(distribution[0]), lineterminator='\n'); w.writeheader(); w.writerows(distribution)
    print('Added three retrospective metrics to all 24 endpoints; original sixteen values unchanged.')


if __name__ == '__main__':
    main()
