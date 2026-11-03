"""Nonclinical transport readiness, separate from experimental outcomes."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from main_experiment.support import save,load_env,digest
from .client import PROFILES,request
from gxp_adsl.run import extract_code


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:p.error('--execute required')
    load_env(a.env_file);a.out.mkdir(parents=True,exist_ok=False)
    def probe(profile):
        d=a.out/profile['id'];d.mkdir();receipt={'profile':profile,'clinical_inputs_used':False,'qualified':False}
        try:
            text=request(profile,'Return only a compact Python module defining run(previous, inputs, upstream) that returns previous.copy(). No tools; no records or research data are supplied.',d/'generation','Return only Python source. No tools are available.')
            code=extract_code(text);tree=ast.parse(code)
            if not any(isinstance(n,ast.FunctionDef) and n.name=='run' for n in tree.body):raise ValueError('Missing run function')
            usage=json.loads((d/'generation/usage.json').read_text());identity=usage['model']
            if profile['model'] not in identity:raise ValueError('Unrelated model response')
            receipt.update(qualified=True,response_model=identity,usage_sha256=digest(d/'generation/usage.json'))
        except Exception as exc:receipt.update(error_type=type(exc).__name__,http_status=getattr(exc,'code',None))
        save(d/'receipt.json',receipt);print(json.dumps({'id':profile['id'],'qualified':receipt['qualified'],'response_model':receipt.get('response_model'),'http_status':receipt.get('http_status')},ensure_ascii=False),flush=True)
        return receipt
    with ThreadPoolExecutor(max_workers=3) as pool:result=list(pool.map(probe,PROFILES.values()))
    save(a.out/'readiness.json',{'clinical_inputs_used':False,'checks':result})


if __name__=='__main__':main()
