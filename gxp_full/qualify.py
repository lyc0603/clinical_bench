"""Nonclinical runtime/upstream/row identity and combined-export qualification."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import pandas as pd
import pyreadstat
from ai431_adsl.run import request
from gxp_adsl.run import extract_code
from main_experiment.support import load_env,save,manifest
from main_experiment.backend import capture
from main_experiment.rebuild import RebuildRuntime
from .plan import NODE_WRAPPER,EXPORT_WRAPPER,EXPORT_SYSTEM
from .checks import node_checks,export_checks


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);a=p.parse_args();load_env(a.env_file)
    root=a.root.resolve();root.mkdir(parents=True,exist_ok=False);(root/'inputs/Input').mkdir(parents=True)
    image=capture(['docker','image','inspect','--format','{{.Id}}','adam-experiment:main']);runtime=RebuildRuntime({'inputs':str(root/'inputs')},image)
    dm=pd.DataFrame({'STUDYID':['SYNTH']*3,'USUBJID':['syn1','syn2','screen'],'ARMCD':['Pbo','Xan_Lo','Scrnfail']});pyreadstat.write_xport(dm,str(root/'inputs/Input/dm.xpt'),file_format_version=5)
    w=root/'node-workspace';(w/'output/adam/programs').mkdir(parents=True);(w/'artifacts/upstream').mkdir(parents=True)
    upstream=pd.DataFrame({'STUDYID':['SYNTH','SYNTH'],'USUBJID':['syn1','syn2'],'AGE':[50.0,60.0]});upstream.to_json(w/'artifacts/upstream/ADSL.json',orient='table',index=False,double_precision=15);save(w/'artifacts/upstream.json',{'ADSL':'artifacts/upstream/ADSL.json'})
    (w/'output/adam/programs/run_node.py').write_text(NODE_WRAPPER)
    (w/'output/adam/programs/node.py').write_text("import pyreadstat\ndef run(previous,inputs,upstream):\n    dm,_=pyreadstat.read_xport(str(inputs/'Input/dm.xpt'),disable_datetime_conversion=True)\n    f=dm.loc[dm.ARMCD.isin(['Pbo','Xan_Lo','Xan_Hi']),['STUDYID','USUBJID']].copy()\n    return f.merge(upstream['ADSL'][['USUBJID','AGE']],on='USUBJID',validate='one_to_one')\n")
    before=manifest(w);e=runtime.rebuild(w,['python','-B','output/adam/programs/run_node.py','output/adam/programs/node.py','-','artifacts/result.json','artifacts/upstream.json'],root/'node.log',60)
    assert e['exit_code']==0 and not e['timed_out'];after=manifest(w);assert all(after.get(k)==v for k,v in before.items());assert set(after)-set(before)=={'artifacts/result.json'}
    f=pd.read_json(w/'artifacts/result.json',orient='table');defs={c:{'Type':'Character' if c in ('STUDYID','USUBJID') else 'Numeric','Length':12 if c in ('STUDYID','USUBJID') else 8} for c in ('STUDYID','USUBJID','AGE')};assert not node_checks(f,None,set(defs),defs,upstream,defs,'ADSL')
    names=['ADSL','ADAE','ADLBC','ADLBH','ADLBHY','ADQSADAS','ADQSCIBC','ADQSNPIX','ADTTE','ADVS','ADCM','ADDS','ADEX']
    columns=['Order','Variable','Label','Type','Length','Format','Origin','Codelist OID'];rows=[[1,'STUDYID','Study Identifier','Character',12,None,'Predecessor',None],[2,'USUBJID','Unique Subject Identifier','Character',11,None,'Predecessor',None],[3,'AVAL','Synthetic Analysis Value','Numeric',8,None,'Derived',None]]
    sheets={'Datasets':[['Dataset','Label','Structure','Source domains','Build order','Variables','Operational key / sort','Source class','Purpose']]+[[n,'Synthetic '+n,'subject/parameter','DM',1,3,'STUDYID, USUBJID','ADSL' if n=='ADSL' else 'BDS','Analysis'] for n in names],
        'Codelists':[['Codelist OID','Code','Decode']],'Value level':[['Dataset','Variable','Condition','Label','Type','Length','Format']]}
    for n in names:sheets[n]=[columns]+rows
    spec={'sheets':sheets};save(root/'inputs/specifications.json',spec)
    w=root/'export-workspace';(w/'output/adam/programs').mkdir(parents=True);(w/'artifacts').mkdir()
    frames={};paths={}
    for i,n in enumerate(names):
        frames[n]=pd.DataFrame({'STUDYID':['SYNTH']*2,'USUBJID':['syn1','syn2'],'AVAL':[float(i),float(i+1)]});path='artifacts/'+n+'.json';frames[n].to_json(w/path,orient='table',index=False,double_precision=15);paths[n]=path
    save(w/'artifacts/datasets.json',paths);(w/'output/adam/programs/run_export.py').write_text(EXPORT_WRAPPER)
    prompt=json.dumps({'task':'export','qualification':'Synthetic nonclinical frames only','accepted_datasets':names,'expected_dataset_files':[n.lower()+'.xpt' for n in names],'metadata_source':'/inputs/specifications.json','sheet_headers':{k:sheets[k][0] for k in ('Datasets','Codelists','Value level')},'frame_schemas':{n:{c:str(v) for c,v in f.dtypes.items()} for n,f in frames.items()},'rules':'No value changes; loop over metadata, return only compact Python source; no tools.'})
    print('Qualifying synthetic 13-dataset exporter via Claude',flush=True);text=request(prompt,root/'generation',EXPORT_SYSTEM);code=extract_code(text);ast.parse(code);(w/'output/adam/programs/export.py').write_text(code);before=manifest(w)
    e2=runtime.rebuild(w,['python','-B','output/adam/programs/run_export.py'],root/'export.log',120);assert e2['exit_code']==0 and not e2['timed_out'],e2
    after=manifest(w);assert all(after.get(k)==v for k,v in before.items());coverage,errors=export_checks(w,spec,frames);assert not errors,errors
    save(root/'receipt.json',{'passed':True,'clinical_inputs_used':False,'image':image,'node_execution':e,'export_execution':e2,'exported_datasets':13,'exported_variables':39,'values_preserved':True,'source_and_programs_unchanged':True,'node_wrapper_sha256':hashlib.sha256(NODE_WRAPPER.encode()).hexdigest(),'export_wrapper_sha256':hashlib.sha256(EXPORT_WRAPPER.encode()).hexdigest(),'export_system_sha256':hashlib.sha256(EXPORT_SYSTEM.encode()).hexdigest(),'generated_export_lines':len(code.splitlines())})
    print('Full runtime + synthetic 13-dataset export: PASS',flush=True)

if __name__=='__main__':main()
