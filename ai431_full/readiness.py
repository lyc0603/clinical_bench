"""Synthetic-only native API probes, separate from measured outcomes."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from main_experiment.support import save,load_env,digest
from gxp_adsl.run import extract_code
from .client import PROFILES,request

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:p.error('--execute required')
    load_env(a.env_file);a.out.mkdir(parents=True,exist_ok=False)
    def probe(profile):
        directory=a.out/profile['id'];directory.mkdir();receipt={'profile':profile,'clinical_inputs_used':False,'qualified':False}
        try:
            text=request(profile,'Return only a Python module defining run(previous, inputs, upstream) that returns previous.copy(). Synthetic interface test only; no study data supplied.',directory/'generation','Return only compact Python code. No tools are available.')
            tree=ast.parse(extract_code(text))
            if not any(isinstance(n,ast.FunctionDef) and n.name=='run' for n in tree.body):raise ValueError('Missing run')
            usage=json.loads((directory/'generation/usage.json').read_text());identity=usage['model']
            if profile['model'] not in identity:raise ValueError('Unrelated returned model')
            receipt.update(qualified=True,response_model=identity,usage_sha256=digest(directory/'generation/usage.json'))
        except Exception as exc:receipt.update(error_type=type(exc).__name__,http_status=getattr(exc,'code',None))
        save(directory/'receipt.json',receipt);print(json.dumps({k:receipt.get(k) for k in ('qualified','response_model','http_status')}|{'provider_id':profile['id']}),flush=True);return receipt
    with ThreadPoolExecutor(max_workers=3) as pool:checks=list(pool.map(probe,PROFILES.values()))
    save(a.out/'readiness.json',{'clinical_inputs_used':False,'checks':checks})

if __name__=='__main__':main()
