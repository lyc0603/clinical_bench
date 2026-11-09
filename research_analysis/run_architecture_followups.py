"""Serial, explicitly planned architecture follow-ups; never rerun a started root."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from main_experiment.support import save,digest,manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--execute',action='store_true')
    a=p.parse_args()
    if not a.execute:p.error('--execute required')
    plan=json.loads((a.batch/'plan.json').read_text())
    state={'status':'running','started_unix':time.time(),'attempts':{},'launcher_sha256':digest(Path(__file__))}
    if (a.batch/'state.json').exists():raise ValueError('Preserve prior orchestration; adjudicate before resuming')
    save(a.batch/'state.json',state)
    for attempt in plan['attempts']:
        key=attempt['id'];root=Path(attempt['root']);code=Path(attempt['code']);f=json.loads((root/'freeze.json').read_text())
        entry={'status':'pending','root':str(root),'freeze_sha256':f['sha256']};state['attempts'][key]=entry;save(a.batch/'state.json',state)
        if attempt.get('already_inflight'):
            if not (root/'run-location.json').is_file():raise ValueError('Expected existing clinical start')
            print('WAIT already-authorized in-flight attempt',key,flush=True)
            while not (root/'archive-receipt.json').exists():time.sleep(10)
        else:
            if (root/'run-location.json').exists() or (root/'run-evidence.tar.gz').exists():raise ValueError('Never automatically repeat a clinical attempt')
            if shutil.disk_usage(root).free<10*1024**3:
                entry['status']='blocked_disk_before_clinical_start';state['status']='blocked_prelaunch';save(a.batch/'state.json',state);return
            entry['status']='running';save(a.batch/'state.json',state);print('START',key,flush=True)
            with (a.batch/(key+'.private.log')).open('w') as log:
                result=subprocess.run([sys.executable,'-m',attempt['module'],'run','--root',str(root),'--env-file',str(a.env_file),'--execute'],cwd=code,stdout=log,stderr=subprocess.STDOUT)
            entry['exit_code']=result.returncode
        if not (root/'archive-receipt.json').exists():
            entry['status']='runner_ended_without_verified_archive';state['status']='needs_adjudication';save(a.batch/'state.json',state);return
        execution=Path(json.loads((root/'run-location.json').read_text())['execution']);observed=json.loads((execution/'state.json').read_text())
        entry['status']=observed['status'];save(a.batch/'state.json',state)
        args=[sys.executable,'-m',attempt['reporter'],'--root',str(root),'--out',str(a.batch/'aggregates'/key)]
        if attempt['architecture']=='gxp':args+=['--run-directory',str(execution)]
        with (a.batch/(key+'-report.private.log')).open('w') as log:result=subprocess.run(args,cwd=code,stdout=log,stderr=subprocess.STDOUT)
        entry['report_exit_code']=result.returncode
        if result.returncode:
            entry['report_status']='needs_posthoc_adjudication';save(a.batch/'state.json',state)
        else:
            receipt=json.loads((root/'archive-receipt.json').read_text())
            if not receipt['verified_lossless'] or digest(root/'run-evidence.tar.gz')!=receipt['sha256'] or manifest(execution)!=json.loads((root/'evidence-manifest.private.json').read_text()):raise ValueError('Refuse duplicate cleanup without exact verified archive')
            save(root/'duplicate-cleanup-receipt.json',{'verified_lossless':True,'archive_sha256':receipt['sha256'],'duplicate_execution_removed':str(execution),'time_unix':time.time()});shutil.rmtree(execution)
            entry['report_status']='completed';save(a.batch/'state.json',state)
        print('END',key,entry['status'],'report',entry['report_exit_code'],flush=True)
    state['status']='completed' if all(v.get('report_exit_code')==0 for v in state['attempts'].values()) else 'clinical_attempts_ended_reporting_incomplete';state['finished_unix']=time.time();save(a.batch/'state.json',state)

if __name__=='__main__':main()
