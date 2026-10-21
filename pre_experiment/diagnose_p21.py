"""Retain diagnostics from the installed P21 evaluator; never rescore a run."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from main_experiment.evaluate import Evaluator, conformance_metrics
from main_experiment.support import manifest, save


def differences(before, after):
    return {name: {'before': before.get(name), 'after': after.get(name)}
            for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--repeats', type=int, default=2, choices=range(1, 4))
    a = p.parse_args()
    a.out = a.out.resolve()
    a.checkpoint = a.checkpoint.resolve()
    a.out.mkdir(parents=True, exist_ok=False)
    c = json.loads(a.config.read_text())
    workspace = a.checkpoint / 'workspace'
    source = manifest(workspace / 'output/adam/datasets')
    cache_before = manifest(Path(c['p21']['cache']))
    evaluator = object.__new__(Evaluator)
    evaluator.c = c
    mkdtemp = tempfile.mkdtemp
    class RetainedTemporaryDirectory:
        def __init__(self, **kwargs):
            self.path = mkdtemp(**kwargs)
        def __enter__(self):
            return self.path
        def __exit__(self, *args):
            return False
    results = []
    for index in range(a.repeats):
        out = a.out / str(index + 1)
        out.mkdir()
        error = None
        try:
            # The evaluator invocation and gate are unchanged; only cleanup is disabled.
            with patch('main_experiment.evaluate.tempfile.TemporaryDirectory', RetainedTemporaryDirectory):
                evaluator.p21(workspace, out)
        except Exception as exc:
            error = str(exc)
        copied_cache = out / 'p21-failed-runtime'
        if not copied_cache.exists():
            copied_cache = next(out.glob('p21-*/cache'))
        changes = differences(cache_before, manifest(copied_cache))
        log = copied_cache / 'lib/p21-client-1.0.9.log'
        text = log.read_text(errors='replace') if log.exists() else ''
        errors = Counter(line.split(' ERROR ', 1)[1].split(' - ', 1)[-1] for line in text.splitlines() if ' ERROR ' in line)
        report = out / 'p21_adam.xlsx'
        parsed = None
        parse_error = None
        if report.exists():
            try:
                actual = {x.stem.upper() for x in (workspace/'output/adam/datasets').glob('*.xpt')}
                parsed = conformance_metrics(report, c['expected_datasets'], actual,
                    ['FDA 2508.1', '1.0.9', c['p21']['ct'], 'ADaM-IG 1.3 (FDA).xml', 'MedDRA', '8.0'])
                save(out/'unqualified-report-parse.json', parsed)
            except Exception as exc:
                parse_error = type(exc).__name__ + ': ' + str(exc)
        pairset = sorted({(item['dataset'], item['rule']) for item in (parsed or {}).get('issues', [])})
        result = {'repeat': index+1, 'frozen_gate_error': error, 'runtime_changes': changes,
                  'client_error_messages': dict(errors), 'parse_error': parse_error,
                  'unqualified_report': {k: (parsed or {}).get(k) for k in
                     ('dataset_rule_pairs','finding_instances','validation_coverage_complete','distinct_rules')},
                  'unqualified_pairs': pairset}
        save(out/'diagnostic.json', result)
        results.append(result)
        print(json.dumps({'repeat':index+1, 'gate_error':error, 'changed_paths':list(changes),
                          'client_errors':sum(errors.values()), 'unqualified_report':result['unqualified_report']}), flush=True)
    assert manifest(workspace/'output/adam/datasets') == source, 'Source datasets changed'
    assert manifest(Path(c['p21']['cache'])) == cache_before, 'Source P21 cache changed'
    save(a.out/'summary.json', {'diagnostic_only':True, 'original_scores_changed':False,
         'source_datasets_and_cache_unchanged':True, 'repeats':results,
         'pairsets_equal': all(r['unqualified_report']['dataset_rule_pairs'] is not None for r in results) and all(r['unqualified_pairs']==results[0]['unqualified_pairs'] for r in results),
         'limitation':'Parseable reports are unqualified observations; repeated agreement does not prove callback errors harmless.'})


if __name__ == '__main__':
    main()
