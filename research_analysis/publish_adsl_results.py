"""Publish aggregate ADSL architecture results without study data or raw requests."""
import argparse
import csv
import json
from pathlib import Path
import shutil
from main_experiment.core import fingerprint
from main_experiment.support import digest, manifest, save


def read(path):
    return json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-experiments',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    sources={
        'gxp-agent':('gxp-adsl-20261101-v5','gxp-adsl-2026-11-01-complete'),
        'ai431':('ai431-adsl-20261101-v2','ai431-adsl-2026-11-01-v2')}
    verified={};provenance={}
    for name,(run_id,report_id) in sources.items():
        root=a.private_experiments/run_id;report=repo/'pre_experiment/results'/report_id
        summary=read(report/'summary.json');audit=read(report/'audit.json');lock=read(root/'freeze.json')
        if fingerprint(lock['payload'])!=lock['sha256'] or lock['sha256']!=summary['freeze_sha256']:
            raise ValueError('Freeze mismatch '+name)
        if digest(root/'run/state.json')!=audit['state_sha256'] or digest(root/'run/evaluation.private.json')!=audit['evaluation_sha256']:
            raise ValueError('Outcome evidence drift '+name)
        if read(root/'run/state.json')['status']!='completed':raise ValueError('Outcome not complete '+name)
        if manifest(root/'run/final-workspace')!=read(root/'run/final-workspace-manifest.json'):
            raise ValueError('Final package drift '+name)
        e=read(root/'run/evaluation.private.json');con=e['conformance']
        if e['subjects']!=254 or e['variable_coverage']!=49 or not e['semantic_reproduced'] or not con['report_usable']:
            raise ValueError('Unexpected outcome '+name)
        if digest(root/'run/final-evaluation/p21_adam.xlsx')!=con['report_sha256']:
            raise ValueError('P21 report drift '+name)
        verified[name]=(summary,e,lock)
        provenance[name]={'run_id':run_id,'source_report_id':report_id,'freeze_sha256':lock['sha256'],
            'source_summary_sha256':digest(report/'summary.json'),'source_readme_sha256':digest(report/'README.md'),
            'state_sha256':audit['state_sha256'],'evaluation_sha256':audit['evaluation_sha256'],
            'p21_report_sha256':con['report_sha256']}
    out=a.out;out.mkdir(parents=True,exist_ok=False)
    for name,(_,report_id) in sources.items():
        source=repo/'pre_experiment/results'/report_id;target=out/name;target.mkdir()
        files=['summary.json','audit.json','rebuild-byte-diagnostic.json']
        files+=['steps.csv','results-table.json'] if name=='gxp-agent' else []
        for filename in files:shutil.copy2(source/filename,target/filename)
        text=(source/'README.md').read_text()
        text=text.replace('See advisory-review.json.','The full model advisory review remains private; its unadjudicated count is reported in summary.json.')
        text+='\n\nThis is the public aggregate report. Raw clinical artifacts, full model advisory text, generated code and provider requests remain private. Publication source hashes and a cross-architecture comparison are in the parent directory.\n'
        (target/'README.md').write_text(text)
        save(target/'p21-findings.json',verified[name][1]['conformance']['issues'])
        payload=verified[name][2]['payload'];base=payload.get('shared_input_runtime_evaluator',payload)
        settings={'model':payload.get('model',base['model']),'max_tokens':payload.get('max_tokens',base['max_tokens']),
            'sampling':base['sampling'],'image':base['image'],'python_version':base['python_version'],
            'expected_subjects':254,'expected_variables':49,'expected_datasets':1,
            'max_attempts_per_task':2,'P21_feedback':False,'human_clinical_code_repair':False,
            'source_schemas_sha256':base['source_schemas_sha256'],'source_provenance_sha256':base['source_provenance_sha256'],
            'controller_code_hashes':payload.get('implementation',base['code']),
            'reused_main_code_hashes':base['reused_main_code']}
        if name=='ai431':settings.update(variable_tasks=49,max_concurrency=3,review='advisory; frozen specification unchanged',export='separate generated export task')
        else:settings.update(process_nodes=15,max_concurrency=1)
        save(target/'run-settings.json',settings)
    g,ge,_=verified['gxp-agent'];i,ie,_=verified['ai431']
    pairs=[
        ('Model','claude-sonnet-5-5','claude-sonnet-5-5','Same hosted API identifier; immutable weights not established'),
        ('Implementation unit','15 serial process nodes','49 independent variable tasks + review + export','Different decomposition and resource budgets'),
        ('Accepted first-attempt units','13 / 15','49 / 49 variable tasks','Different unit denominators; export also first-attempt accepted'),
        ('Locally repaired units',2,0,'GxP derive_completion/apply_metadata; no manual clinical code edits'),
        ('Final dataset delivery','1 / 1','1 / 1','ADSL only'),
        ('Variable name/type coverage','49 / 49','49 / 49','Does not establish value accuracy'),
        ('Subjects',254,254,'Exact randomized subject identities checked'),
        ('Independent rebuild','Succeeded','Succeeded','Offline clean replay'),
        ('Semantic reproducibility',True,True,'Data/Define semantic comparison'),
        ('Byte equality',False,False,'XPT writer timestamps differ; Define bytes identical'),
        ('P21 report usable',True,True,'Usability does not mean zero findings'),
        ('P21 validation coverage','Complete','Complete','One expected ADaM dataset'),
        ('P21 dataset-rule pairs',ge['conformance']['dataset_rule_pairs'],ie['conformance']['dataset_rule_pairs'],'Lower is better; descriptive only'),
        ('P21 finding instances',ge['conformance']['finding_instances'],ie['conformance']['finding_instances'],'All reported findings concern labels'),
        ('P21 distinct rules',ge['conformance']['distinct_rules'],ie['conformance']['distinct_rules'],'Native severity unassigned'),
        ('Selected source checks','13 checks / 3302 assessments / 0 errors','13 checks / 3302 assessments / 0 errors','11 DM predecessor variables + 2 SV anchor dates; not all derivations'),
        ('Native input tokens',g['native_usage']['input_tokens'],i['native_usage']['input_tokens'],'Includes failed local attempts and AI-431 advisory review'),
        ('Native output tokens',g['native_usage']['output_tokens'],i['native_usage']['output_tokens'],'Provider telemetry, not billed cost'),
        ('Generation responses',len(read(repo/'pre_experiment/results'/sources['gxp-agent'][1]/'audit.json')['attempts']),i['native_completed_response_count'],'AI-431: 49 variables + review + export'),
        ('Workflow elapsed seconds',round(g['elapsed_seconds'],3),round(i['elapsed_seconds'],3),'Includes terminal evaluation; preparation excluded'),
        ('Completed runs under final implementation',1,1,'Separate development runs; not randomized concurrent comparison'),
        ('Verified billed cost','Unavailable','Unavailable','No rate-based estimate or balance inferred')]
    with (out/'comparison.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(['Measure','GxP-Agent-inspired','AI-431-inspired','Interpretation']);w.writerows(pairs)
    save(out/'comparison.json',[dict(zip(['measure','gxp_agent_inspired','ai431_inspired','interpretation'],row)) for row in pairs])
    history=[
        {'run_id':'gxp-adsl-20261028-v2','architecture':'GxP-inspired','status':'failed','accepted_units':'12/15 nodes','reason':'Validate response truncated at 8192 output tokens'},
        {'run_id':'gxp-adsl-20261031-v3','architecture':'GxP-inspired','status':'failed','accepted_units':'7/15 nodes','reason':'Uppercase source path then repair prose rejected by strict parser'},
        {'run_id':'gxp-adsl-20261101-v4','architecture':'GxP-inspired','status':'failed','accepted_units':'14/15 nodes','reason':'Define export path underspecified; checker required a different directory'},
        {'run_id':'gxp-adsl-20261101-v5','architecture':'GxP-inspired','status':'completed','accepted_units':'15/15 nodes','reason':'Published completed adaptation'},
        {'run_id':'ai431-adsl-20261101-v1','architecture':'AI-431-inspired','status':'failed','accepted_units':'49/49 variables; merge passed','reason':'Accepted workspace file missing during packaging; filesystem root cause not established'},
        {'run_id':'ai431-adsl-20261101-v1/recovery-continuation','architecture':'AI-431-inspired','status':'failed','accepted_units':'Original variable programs reused with exact hashes, not regenerated','reason':'Post-hoc infrastructure continuation; simulated unavailable bash tools repeated until export truncation at 32768'},
        {'run_id':'ai431-adsl-20261101-v2','architecture':'AI-431-inspired','status':'completed','accepted_units':'49/49 variables + export','reason':'New full run; explicit Path interface, dedicated tool-free export, non-cloud execution storage'}]
    for entry in history:
        folder=a.private_experiments/entry['run_id'];lockpath=folder/'freeze.json'
        if lockpath.is_file():entry['freeze_sha256']=read(lockpath)['sha256']
    save(out/'development-history.json',history)
    text='# ADSL architecture-adaptation pilots — 2026-11-01\n\nTwo completed, excluded exploratory ADSL runs using Claude Sonnet 5.5: an independently implemented GxP-Agent-inspired Process-DAG and an independently implemented PharmaSUG AI-431-inspired variable pipeline. These are architecture adaptations, not author software or numerical replications. Both delivered 254 subjects and 49 named/typed variables, reproduced semantically, and produced usable P21 reports. Neither was zero-finding.\n\n| Measure | GxP-Agent-inspired | AI-431-inspired | Interpretation |\n|---|---|---|---|\n'+''.join('| '+' | '.join(str(x) for x in row)+' |\n' for row in pairs)
    text+='\n## Detailed results\n\n- [GxP-inspired result table and methodology](gxp-agent/README.md)\n- [AI-431-inspired result table and methodology](ai431/README.md)\n- [Machine-readable comparison](comparison.csv) and [JSON](comparison.json)\n- [Retained development history](development-history.json)\n- [Publication provenance](publication-provenance.json) and [file checksums](SHA256SUMS)\n\n## What these observations support\n\nThe completed runs demonstrate that the benchmark input/evaluation boundary can be exercised by two alternative ADSL generation architectures. They do not establish one architecture is superior. Each final implementation has one measured run; designs have different units, concurrency, prompts and call budgets and were revised after earlier failures. Outputs are descriptive case studies, not matched randomized repetitions or estimates of original-paper performance.\n\nGxP adaptation uses Python/pandas/pyreadstat and an adapted dependency order rather than original R/pharmaverse. AI-431 adapts only the already-confirmed-specification generation/execution/QC/merge workflow; its model review is advisory, without interactive human specification refinement or human code rescue. It flagged eight potential specification/subset blockers that remain unadjudicated. These are model flags, not confirmed errors. Neither structural checks, selected direct-source checks nor P21 establishes all clinical derivations are correct.\n\nP21 is an independent terminal evaluator and is not returned for repair. Both use ADSL-only expected dataset coverage, ADaMIG1.3, FDA2508.1, CT2026-03-27, MedDRA8.0 and client1.0.9. Findings: GxP AD0018/AD0320/AD0509; AI-431 AD0018/AD0509, one instance each. Severity is unassigned in the native reports. Byte-equality remains false because of XPT writer timestamp fields, although Define bytes are identical and semantic comparisons pass.\n\nRun usage includes all recorded clinical-run responses, including failed local candidates and the AI-431 advisory review. Nonclinical qualification and earlier failed development attempts are not included in final-run token/time totals and must not be treated as free: AI-431 export qualification separately consumed 4999 input/4917 output tokens. Original failed attempts remain in development-history.json and private evidence; final successes do not replace them.\n\n## Development transparency\n\n| Run | Status | Accepted work | Stopping reason / role |\n|---|---|---|---|\n'+''.join('| '+x['run_id']+' | '+x['status']+' | '+x['accepted_units']+' | '+x['reason']+' |\n' for x in history)
    text+='\nAn initial GxP preparation was superseded before clinical generation to refine technical checks; it is not a discarded clinical run. The three earlier GxP failures and the AI-431 failure/continuation are development evidence under different freezes and are not extra replicates of the final implementations.\n\n## Scope and privacy\n\nThese ADSL-only denominators are 1 dataset / 49 variables. Do not append them to the historical full-study 13-dataset / 531-variable table as comparable endpoints. The existing formal main-study lock and runtime code are unchanged by this publication. This commit publishes result aggregates and evidence hashes only; it does not distribute the local architecture runner code, clinical inputs, generated patient-level outputs, model requests/replies, full advisory text, P21 workbook, dictionaries or API credentials. Collaborators can review tables and leave GitHub comments/issues; private evidence requires separate controlled access.\n\nArchitecture references: [GxP-Agent](https://arxiv.org/html/2608.16890v1), [PharmaSUG 2026 AI-431](https://pharmasug.org/proceedings/2026/AI/PharmaSUG-2026-AI-431.pdf).\n'
    (out/'README.md').write_text(text)
    save(out/'publication-provenance.json',{'source_outcomes_verified':True,'sources':provenance,'publication_script_sha256':digest(Path(__file__)),'raw_clinical_data_published':False})
    files=[f for f in out.rglob('*') if f.is_file() and f.name!='SHA256SUMS']
    (out/'SHA256SUMS').write_text(''.join(digest(f)+'  '+str(f.relative_to(out))+'\n' for f in sorted(files)))
    print('Published aggregate bundle:',out,'files',len(files)+1)

if __name__=='__main__':main()
