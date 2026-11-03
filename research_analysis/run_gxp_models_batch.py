"""Serial model execution, one planned workflow each; no automatic rerun."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from main_experiment.support import save,digest,manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--batch',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);a=p.parse_args();study=a.study.resolve();batch=a.batch.resolve()
    for provider in ('gemini','deepseek'):
        root=study/f'gxp-models-{provider}-20261102-v1';lock=root/'freeze.json'
        if not lock.is_file():raise ValueError('Freeze required before batch launch: '+provider)
        if (root/'run-evidence.tar.gz').exists():raise ValueError('Never restart a completed planned attempt')
    state={'status':'running','models':{},'model_order':['gemini','deepseek'],'gateway_sol':'not_started_readiness_http_403'};save(batch/'state.json',state)
    for provider in state['model_order']:
        root=study/f'gxp-models-{provider}-20261102-v1';log=batch/(provider+'.log');state['models'][provider]={'status':'running','freeze_sha256':json.loads((root/'freeze.json').read_text())['sha256']};save(batch/'state.json',state)
        print('Starting '+provider+' full DAG',flush=True)
        with log.open('w') as stream:
            result=subprocess.run([sys.executable,'-m','gxp_models.run','run','--root',str(root),'--env-file',str(a.env_file.resolve()),'--execute'],stdout=stream,stderr=subprocess.STDOUT)
        execution=Path('/private/tmp')/(root.name+'-execution');s=json.loads((execution/'state.json').read_text());state['models'][provider].update(status=s['status'],exit_code=result.returncode);save(batch/'state.json',state)
        print(provider+' terminal status: '+s['status']+'; auditing retained evidence',flush=True)
        subprocess.run([sys.executable,'-m','research_analysis.report_gxp_full','--root',str(root),'--run-directory',str(execution),'--out',str(batch/provider)],check=True)
        receipt=json.loads((root/'archive-receipt.json').read_text());expected=json.loads((root/'evidence-manifest.private.json').read_text());archive=root/'run-evidence.tar.gz'
        if not receipt['verified_lossless'] or digest(archive)!=receipt['sha256'] or manifest(execution)!=expected:raise ValueError('Refuse cleanup without exact immutable evidence archive')
        # The complete, stream-verified private archive keeps every attempt and
        # clinical artifact. Remove only its duplicate to protect remaining disk.
        shutil.rmtree(execution);save(root/'duplicate-cleanup-receipt.json',{'duplicate_execution_removed':True,'archived_evidence_preserved':True,'archive_sha256':receipt['sha256'],'aggregate_audit_sha256':digest(batch/provider/'audit.json'),'finished_unix':time.time()})
        print(provider+' report saved; lossless archive retained, duplicate execution copy removed',flush=True)
    state['status']='completed';save(batch/'state.json',state)


if __name__=='__main__':main()
