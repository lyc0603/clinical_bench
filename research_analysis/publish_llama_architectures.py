"""Append two frozen Llama architecture attempts without rewriting historical outcomes."""
import argparse
import copy
import csv
import json
from pathlib import Path
import shutil
import tarfile
from main_experiment.support import digest, save
from research_analysis.publish_architecture_followups import display
from research_analysis.report_gxp_full import METRICS


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'batch', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    previous = json.loads(a.previous.read_text())
    state = json.loads((a.batch/'state.json').read_text())
    plan = json.loads((a.batch/'plan.json').read_text())
    if len(previous['records']) != 13 or state['status'] != 'completed':
        raise ValueError('Require thirteen historical endpoints and two finished attempts')
    if {x['id'] for x in plan['attempts']} != {'gxp_llama_scout', 'ai431_llama_scout'}:
        raise ValueError('Unexpected attempt set')
    records = copy.deepcopy(previous['records'])
    a.out.mkdir(parents=True, exist_ok=False)
    audit = {}
    for item in plan['attempts']:
        key = item['id']; source = a.batch/'aggregates'/key; root = Path(item['root'])
        r = json.loads((source/'summary.json').read_text())
        if [x['metric'] for x in r['metrics']] != METRICS:
            raise ValueError('Metric mismatch')
        receipt = json.loads((root/'archive-receipt.json').read_text())
        if not receipt['verified_lossless'] or digest(root/'run-evidence.tar.gz') != receipt['sha256']:
            raise ValueError('Archive mismatch')
        r.update(id=key, label='Llama 4 Scout — DeepInfra; fresh Nov 9',
                 architecture_group=item['architecture'], attempt_cohort='New independent Llama attempts 2026-11-09')
        if key == 'gxp_llama_scout':
            with tarfile.open(root/'run-evidence.tar.gz') as archive:
                errors = [archive.extractfile(m).read().decode() for m in archive
                          if m.name.endswith('error-response.private.bin')]
            if len(errors) != 1 or not all(s in errors[0] for s in ('131072', '98305', '32768')):
                raise ValueError('Context failure evidence differs from adjudication')
            # The API supplies a lower bound, not an exact tokenized prompt length.
            r['provider_failure_adjudication'] = {
                'http_status': 400, 'category': 'context_window_incompatible',
                'reported_context_limit': 131072, 'requested_output_tokens': 32768,
                'reported_input_token_lower_bound': 98305,
                'exact_input_tokens_known': False, 'clinical_api_request_attempts': 1,
                'note': 'Service rejected first request before generation. No prompt truncation or budget change.'}
            r['metrics'][13]['value'] = None
            r['usage_interpretation'] = 'No native response receipt; usage and billed cost unknown, not zero'
        candidate = r.get('unaccepted_terminal_candidate')
        if candidate and candidate.get('errors'):
            candidate['errors'] = ['Rejected-export diagnostics retained privately']
        target = a.out/key; target.mkdir(); save(target/'summary.json', r)
        shutil.copy2(source/'audit.json', target/'audit.json')
        for name in ('timing-receipt.json', 'failure-adjudication.json', 'merge-failure-adjudication.json'):
            if (source/name).is_file(): shutil.copy2(source/name, target/name)
        audit[key] = {'source_summary_sha256': digest(source/'summary.json'),
                      'private_archive_sha256': receipt['sha256'], 'freeze_sha256': r['freeze_sha256']}
        records.append(r)
    assert records[:13] == previous['records']
    def cell(n, r):
        if r['id'] == 'gxp_llama_scout' and n in (1, 19):
            return 'HTTP400: context limit 131,072; input at least 98,305 + output reservation 32,768; no generated node'
        return display(n, r['metrics'][n-1]['value'], r)
    rows = [[i+1, name] + [cell(i+1, r) for r in records] for i, name in enumerate(METRICS)]
    headers = ['No.', 'Metric'] + [r['architecture_group'].upper()+' / '+r['label'] for r in records]
    save(a.out/'comparison.json', {'scope': 'Historical outcomes plus two independent Llama architecture attempts',
         'main_study_started': False, 'comparison_complete': True, 'records': records,
         'table_headers': headers, 'table_rows': rows})
    with (a.out/'comparison.csv').open('w', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(headers); w.writerows(rows)
    text = '# Architecture results including Llama 4 Scout\n\n[Excel workbook](comparison.xlsx) · [Unified 19-metric CSV](comparison.csv) · [Metric components](comparison.json). All thirteen previous endpoints are preserved unchanged. Two independent attempts are appended.\n\n'
    for architecture in ('gxp', 'ai431'):
        selected = [r for r in records if r['architecture_group'] == architecture]
        text += '## '+architecture.upper()+'\n\n| No. | Metric | '+' | '.join(r['label'] for r in selected)+' |\n|---:|---|'+''.join('---|' for _ in selected)+'\n'
        for i, name in enumerate(METRICS):
            text += '| '+str(i+1)+' | '+name+' | '+' | '.join(cell(i+1, r).replace('|','/').replace('\n',' ') for r in selected)+' |\n'
        text += '\n'
    text += '## Interpretation\n\nBoth attempts use DeepInfra-hosted meta-llama/Llama-4-Scout-17B-16E-Instruct, not local inference. Provider assertions do not pin exact deployed weights. The independent adaptations target 13 datasets and 531 variables using the existing frozen inputs, prompts, gates, two attempts per task, provider-default sampling and 32,768 output-token cap. GxP uses two dataset branches; AI-431 uses three variable workers. No manual clinical repairs, prompt truncation, automatic transport retries or changes to clinical rules occurred. The main study has not started.\n\nGxP was rejected on its first clinical API request because the service reported a 131,072 context limit. The reported input count of at least 98,305 is a lower bound, not exact token usage. Together with the 32,768 output reservation it exceeds that limit. This is an API/context compatibility outcome, not evidence of P21 failure or clinical derivation quality. Billed usage is unknown.\n\nFailures and unavailable metrics remain in the denominator. These nonconcurrent, single-attempt observations do not establish causal architecture or model superiority. Historical engineering continuations remain explicitly labelled. Full requests, generated code, data and errors are retained privately in verified lossless archives; only aggregate metrics and provenance hashes are public. See each new summary for observed task counts, timing and token receipts.\n'
    (a.out/'README.md').write_text(text)
    save(a.out/'publication-audit.json', {'previous_comparison_sha256': digest(a.previous),
         'previous_thirteen_records_unchanged': True, 'new_attempts': audit,
         'batch_plan_sha256': digest(a.batch/'plan.json'), 'batch_state_sha256': digest(a.batch/'state.json'),
         'raw_clinical_artifacts_published': False, 'publisher_sha256': digest(Path(__file__))})
    print('Published 15 endpoints, 19 metrics; prior 13 records unchanged')


if __name__ == '__main__': main()
