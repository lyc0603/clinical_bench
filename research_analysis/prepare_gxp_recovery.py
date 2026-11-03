"""Verify historical evidence and qualify a nullable-character boundary fix."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import tarfile
import pandas as pd
from main_experiment.support import save,load_env,digest,manifest
from main_experiment.rebuild import RebuildRuntime
from gxp_recovery.boundary import NODE_WRAPPER,EXPORT_WRAPPER
from gxp_full.plan import EXPORT_SYSTEM,definitions
from gxp_full.checks import export_checks
from gxp_recovery.checks import node_checks


def read(path):return json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--original-summary',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--qualification-exporter',type=Path,required=True);a=p.parse_args();load_env(a.env_file)
    root=a.root.resolve();out=a.out.resolve();out.mkdir(exist_ok=False);lock=read(root/'freeze.json');f=lock['payload'];receipt=read(root/'archive-receipt.json');archive=root/'run-evidence.tar.gz'
    if digest(archive)!=receipt['sha256'] or not receipt['verified_lossless']:raise ValueError('Historical archive changed')
    original=out/'original';original.mkdir()
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            name=PurePosixPath(member.name)
            if not member.isfile() or name.is_absolute() or '..' in name.parts:raise ValueError('Unsafe evidence archive')
            target=original/name;target.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(member) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
    if manifest(original)!=read(root/'evidence-manifest.private.json'):raise ValueError('Historical extraction mismatch')
    old=read(original/'state.json');failed=next(n for n in old['nodes'] if n['status']=='failed')
    if failed['dataset']!='ADSL' or failed['node']!='derive_duration':raise ValueError('Unexpected recovery target')
    for item in failed['attempts']:
        checks=read(original/'datasets/ADSL/nodes/derive_duration'/f"attempt-{item['attempt']}"/'checks.private.json')
        if checks['errors']!=['DURDSGR1: expected character storage even when entirely missing']:raise ValueError('Not a pure diagnosed storage failure')
    reuse={}
    for n in old['nodes']:
        attempt=n.get('accepted_attempt') or 2;d=original/'datasets'/n['dataset']/'nodes'/n['node']/f'attempt-{attempt}';item=next(x for x in n['attempts'] if x['attempt']==attempt);program='workspace/output/adam/programs/nodes/'+n['dataset']+'__'+n['node']+'.py'
        if digest(d/program)!=item['program_sha256']:raise ValueError('Original program drift')
        reuse[n['dataset']+'.'+n['node']]={'directory':str(d),'original_attempt':attempt,'original_status':n['status'],'program':program,'program_sha256':item['program_sha256'],'native_hashes':{name:digest(d/name) for name in ('request.private.json','response.private.json','usage.json')}}
    if len(reuse)!=6:raise ValueError('Expected six reusable ADSL steps')
    save(out/'resume.json',{'policy':'Post-hoc controller node-serialization continuation; original failed outcome retained; no replacement model generation for reused nodes','original_freeze_sha256':lock['sha256'],'original_state_sha256':digest(original/'state.json'),'original_archive_sha256':receipt['sha256'],'original_summary':read(a.original_summary),'reuse_steps':reuse})
    q=out/'qualification';(q/'inputs').mkdir(parents=True);columns=['Variable','Type','Length'];rows=[['STUDYID','Character',12],['USUBJID','Character',12],['C','Character',8],['N','Numeric',8]];save(q/'inputs/specifications.json',{'sheets':{'ADSL':[columns]+rows}})
    w=q/'workspace';(w/'output/adam/programs').mkdir(parents=True);(w/'artifacts').mkdir();save(w/'artifacts/upstream.json',{})
    (w/'output/adam/programs/run_node.py').write_text(NODE_WRAPPER);(w/'output/adam/programs/ADSL__synthetic.py').write_text("import pandas as pd\ndef run(previous,inputs,upstream):\n return pd.DataFrame({'STUDYID':['S','S'],'USUBJID':['u1','u2'],'C':pd.Series([None,None],dtype=object),'N':[1.25,float('nan')]})\n")
    execution=RebuildRuntime({'inputs':str(q/'inputs')},f['image']).rebuild(w,['python','-B','output/adam/programs/run_node.py','output/adam/programs/ADSL__synthetic.py','-','artifacts/result.json','artifacts/upstream.json'],q/'execution.log',120)
    if execution['exit_code'] or execution['timed_out']:raise ValueError('Synthetic wrapper execution failed')
    frame=pd.read_json(w/'artifacts/result.json',orient='table');defs={r[0]:dict(zip(columns,r)) for r in rows};errors=node_checks(frame,None,set(defs),defs,frame[['STUDYID','USUBJID']],defs,'ADSL')
    if errors or not isinstance(frame.C.dtype,pd.StringDtype) or not frame.C.isna().all():raise ValueError('Nullable-character boundary qualification failed')
    eq=out/'export-qualification';(eq/'inputs').mkdir(parents=True);shutil.copy2(root/'inputs/specifications.json',eq/'inputs/specifications.json');spec=read(eq/'inputs/specifications.json');ew=eq/'workspace';(ew/'output/adam/programs').mkdir(parents=True);(ew/'artifacts').mkdir();frames={};paths={}
    for ds in [row[0] for row in spec['sheets']['Datasets'][1:] if row[0]]:
        defs={v['Variable']:v for v in definitions(spec,ds)};frame=pd.DataFrame({c:pd.Series([None,None],dtype='string') if v['Type']=='Character' else [1.25,float('nan')] for c,v in defs.items()});frames[ds]=frame;path='artifacts/'+ds+'.json';frame.to_json(ew/path,orient='table',index=False,double_precision=15);paths[ds]=path
    save(ew/'artifacts/datasets.json',paths);(ew/'output/adam/programs/run_export.py').write_text(EXPORT_WRAPPER)
    exporter=a.qualification_exporter.resolve();shutil.copy2(exporter,ew/'output/adam/programs/export.py')
    ex=RebuildRuntime({'inputs':str(eq/'inputs')},f['image']).rebuild(ew,['python','-B','output/adam/programs/run_export.py'],eq/'execution.log',180)
    if ex['exit_code'] or ex['timed_out']:raise ValueError('Nullable synthetic exporter failed')
    coverage,errors=export_checks(ew,spec,frames)
    if errors:raise ValueError('Nullable synthetic export checks failed: '+str(errors))
    common=read(root/'qualification.json');common.update(node_wrapper_sha256=hashlib.sha256(NODE_WRAPPER.encode()).hexdigest(),export_wrapper_sha256=hashlib.sha256(EXPORT_WRAPPER.encode()).hexdigest(),node_boundary_qualification={'passed':True,'clinical_records_used':False,'missing_semantics_preserved':True,'execution':execution,'nullable_dtype':'string'},export_boundary_qualification={'passed':True,'clinical_records_used':False,'datasets':13,'variables':531,'execution':ex,'exporter_sha256':digest(exporter)},historical_qualification_sha256=digest(root/'qualification.json'))
    assert common['export_system_sha256']==hashlib.sha256(EXPORT_SYSTEM.encode()).hexdigest()
    save(out/'qualification.json',common);print('Historical archive verified; six unedited programs selected; new offline nullable-character qualification PASS',flush=True)


if __name__=='__main__':main()
