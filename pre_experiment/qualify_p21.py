"""Qualify current P21 on retained artifacts; no model calls or score replacement.

The P21 client may contact external services. Obtain authorization before execution.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from main_experiment.core import config, fingerprint, private_path
from main_experiment.runner import seal
from main_experiment.support import digest, manifest, save
from pre_experiment.paired_pilot import tool_manifest


def passing(summary):
    runs = summary.get('repeats', [])
    return (summary.get('source_datasets_and_cache_unchanged') is True and len(runs) == 2
            and all(r.get('validator_accepted') is True for r in runs)
            and summary.get('pairsets_equal') is True
            and runs[0]['unqualified_report'] == runs[1]['unqualified_report'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--baseline-root', type=Path, required=True)
    p.add_argument('--self-review-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--execute-p21', action='store_true')
    a = p.parse_args()
    if not a.execute_p21:
        p.error('--execute-p21 required; client connectivity must be authorized')
    c = config(a.config)
    initial_seal = seal(c)
    initial_tools = tool_manifest()
    out = private_path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    checks = []
    folders = {'openai':'smokes-v2','anthropic':'smokes-anthropic-post-topup','google':'smokes-google-new-key'}
    for model in c['models']:
        alias = model['id']
        for condition in ('p21_feedback','self_review'):
            source = a.baseline_root/folders[alias]/alias if condition=='p21_feedback' else a.self_review_root/alias
            for phase in ('initial','final'):
                checkpoint = source/phase
                destination = out/alias/condition/phase
                run = subprocess.run([sys.executable,'-m','pre_experiment.diagnose_p21',
                    '--config',str(a.config.resolve()),'--checkpoint',str(checkpoint.resolve()),
                    '--out',str(destination),'--repeats','2'],check=False)
                summary_path = destination/'summary.json'
                summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
                expected_sources = manifest(checkpoint/'workspace/output/adam/datasets')
                ok = (run.returncode==0 and passing(summary) and
                      summary.get('config_sha256')==fingerprint(c) and
                      summary.get('evaluator_code')==initial_seal['code'] and
                      summary.get('source_dataset_manifest')==expected_sources)
                checks.append({'model':alias,'condition':condition,'phase':phase,'qualified':ok,
                               'summary_sha256':digest(summary_path) if summary_path.exists() else None})
                save(out/'progress.json', {'checks':checks})
    unchanged = initial_seal == seal(c) and initial_tools == tool_manifest()
    receipt = {'schema':'paired-p21-qualification-v1','qualified':unchanged and all(r['qualified'] for r in checks),
               'seal_sha256':fingerprint(initial_seal),'checks':checks,
               'tools':initial_tools,'original_scores_changed':False,
               'interpretation':'Technical qualification only; repeat agreement does not prove full clinical correctness.'}
    save(out/'qualification.json',receipt)
    if not receipt['qualified']:
        raise SystemExit('P21 qualification failed; do not start new model workflows. Review retained diagnostics.')
    print('P21 qualification passed. Historical scores unchanged; paired pilot may now be frozen.')


if __name__ == '__main__':
    main()
