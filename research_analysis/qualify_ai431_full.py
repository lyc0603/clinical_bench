"""Synthetic-only qualification of independent row alignment, replay and export boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import pandas as pd
import pyreadstat
from main_experiment.support import save,load_env,digest,manifest
from main_experiment.backend import capture
from main_experiment.rebuild import RebuildRuntime
from ai431_full.design import WRAPPER,EXPORT_WRAPPER,replay_entry,variable_qc,row_qc
from gxp_full.plan import definitions
from gxp_full.checks import export_checks

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--synthetic-exporter',type=Path,required=True);a=p.parse_args();load_env(a.env_file);a.out.mkdir(exist_ok=False)
    config=json.loads((a.source/'base-config.private.json').read_text());image=capture(['docker','image','inspect','--format','{{.Id}}',config['image']])
    test=a.out/'replay';(test/'inputs/Input').mkdir(parents=True);workspace=test/'workspace';(workspace/'output/adam/programs/variables').mkdir(parents=True);(workspace/'artifacts').mkdir()
    headers=['Variable','Type','Length'];rows=[['USUBJID','Character',8],['C','Character',8],['N','Numeric',8]]
    save(test/'inputs/specifications.json',{'sheets':{'ADSL':[headers]+rows,'ADTEST':[headers]+rows}})
    pyreadstat.write_xport(pd.DataFrame({'USUBJID':['s1','s2'],'ARMCD':['Pbo','Xan_Lo']}),test/'inputs/Input/dm.xpt',file_format_version=5)
    datasets=[{'dataset':'ADSL','dependencies':[],'variables':[dict(zip(headers,r)) for r in rows]},{'dataset':'ADTEST','dependencies':['ADSL'],'variables':[dict(zip(headers,r)) for r in rows]}]
    (workspace/'output/adam/programs/run_variable.py').write_text(WRAPPER)
    for ds in datasets:
        name=ds['dataset']
        for variable in ('USUBJID','C','N'):
            assignment="frame['C']=pd.Series([None]*len(frame),dtype=object)" if variable=='C' else "frame['N']=[1.25]+[float('nan')]*(len(frame)-1)" if variable=='N' else ''
            (workspace/'output/adam/programs/variables'/(name+'__'+variable+'.py')).write_text("import pandas as pd\ndef run(previous,inputs,upstream):\n frame=previous[['__ROWID','USUBJID']].copy()\n "+assignment+"\n return frame\n")
    (workspace/'output/adam/programs/variables/ADTEST__row_universe.py').write_text("import pandas as pd\ndef run(previous,inputs,upstream):\n assert set(upstream)=={'ADSL'}\n return pd.DataFrame({'USUBJID':['s1','s1','s2'],'__SRC_SEQ':[1,2,1]})\n")
    # Nonclinical collector, never used as a clinical export implementation.
    (workspace/'output/adam/programs/run_export.py').write_text("import json\nfrom pathlib import Path\npaths=json.loads(Path('artifacts/datasets.json').read_text())\nPath('artifacts/synthetic-replay-complete.json').write_text(json.dumps(paths))\n")
    (workspace/'output/adam/programs/rebuild.py').write_text(replay_entry(datasets,{'ADSL','ADTEST'}))
    before=manifest(workspace);execution=RebuildRuntime({'inputs':str(test/'inputs')},image).rebuild(workspace,['python','-B','output/adam/programs/rebuild.py'],test/'execution.log',180)
    if execution['exit_code'] or execution['timed_out']:raise ValueError('Synthetic independent replay failed')
    if any(manifest(workspace).get(k)!=v for k,v in before.items()):raise ValueError('Replay modified protected files')
    keys=pd.read_json(workspace/'artifacts/ADTEST-keys.json',orient='table');frame=pd.read_json(workspace/'artifacts/ADTEST-C.json',orient='table')
    if row_qc(keys,pd.DataFrame({'USUBJID':['s1','s2']})) or variable_qc(frame,keys,dict(zip(headers,rows[1]))) or not frame.C.isna().all() or not isinstance(frame.C.dtype,pd.StringDtype):raise ValueError('Row/null boundary mismatch')
    final=pd.read_json(workspace/'artifacts/ADTEST-final.json',orient='table')
    if list(final.USUBJID)!=['s1','s1','s2'] or final.N.iloc[0]!=1.25 or not final.N.iloc[1:].isna().all():raise ValueError('Independent merge altered row/numeric/missing values')
    eq=a.out/'export';(eq/'inputs').mkdir(parents=True);shutil.copy2(a.source/'inputs/specifications.json',eq/'inputs/specifications.json');spec=json.loads((eq/'inputs/specifications.json').read_text());ew=eq/'workspace';(ew/'output/adam/programs').mkdir(parents=True);(ew/'artifacts').mkdir();frames={};paths={}
    for ds in [r[0] for r in spec['sheets']['Datasets'][1:] if r[0]]:
        defs=definitions(spec,ds);frame=pd.DataFrame({v['Variable']:pd.Series([None,None],dtype='string') if v['Type']=='Character' else [1.25,float('nan')] for v in defs});frames[ds]=frame;path='artifacts/'+ds+'.json';frame.to_json(ew/path,orient='table',index=False,double_precision=15);paths[ds]=path
    save(ew/'artifacts/datasets.json',paths);(ew/'output/adam/programs/run_export.py').write_text(EXPORT_WRAPPER);shutil.copy2(a.synthetic_exporter,ew/'output/adam/programs/export.py')
    export_execution=RebuildRuntime({'inputs':str(eq/'inputs')},image).rebuild(ew,['python','-B','output/adam/programs/run_export.py'],eq/'execution.log',180)
    if export_execution['exit_code'] or export_execution['timed_out']:raise ValueError('Synthetic export execution failed')
    coverage,errors=export_checks(ew,spec,frames)
    if errors:raise ValueError('Synthetic export gate failed: '+str(errors))
    save(a.out/'receipt.json',{'passed':True,'clinical_inputs_used':False,'model_calls':0,'image':image,'wrapper_sha256':hashlib.sha256(WRAPPER.encode()).hexdigest(),'export_wrapper_sha256':hashlib.sha256(EXPORT_WRAPPER.encode()).hexdigest(),'replay_execution':execution,'export_execution':export_execution,'synthetic_datasets':len(coverage),'synthetic_variables':sum(x['variables_matched'] for x in coverage.values()),'missing_character_and_numeric_semantics_preserved':True,'repeated_subject_alignment_verified':True,'new_provider_export_competence_preselected':False,'synthetic_only_exporter_sha256':digest(a.synthetic_exporter),'qualifier_sha256':digest(Path(__file__))})
    print('PASS: offline independent replay, repeated-subject merge, null storage and 13/531 synthetic export',flush=True)

if __name__=='__main__':main()
