"""Supplementary numerical diagnostics; never overrides strict evaluator results."""
import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
import pyreadstat
from lxml import etree
from main_experiment.support import save,digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--continuation',type=Path,required=True);p.add_argument('--original-execution',type=Path,required=True);p.add_argument('--original-freeze',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args();root=a.continuation;original=a.original_execution
    left=root/'final-workspace/output/adam/datasets';right=root/'final-evaluation/replay/output/adam/datasets';plan=json.loads(a.original_freeze.read_text())['payload']['plan'];old=json.loads((original/'state.json').read_text());rows=[];total=0;maximum=0.0
    for ds in plan:
        name=ds['dataset'];x,m=pyreadstat.read_xport(str(left/(name.lower()+'.xpt')),disable_datetime_conversion=True);y,n=pyreadstat.read_xport(str(right/(name.lower()+'.xpt')),disable_datetime_conversion=True)
        if x.shape!=y.shape or list(x)!=list(y):raise ValueError('Row/column structure differs')
        differing=[];tolerant=True;character_equal=True
        for c in x:
            if pd.api.types.is_numeric_dtype(x[c]) and pd.api.types.is_numeric_dtype(y[c]):
                mask=(x[c]!=y[c])&~(x[c].isna()&y[c].isna());count=int(mask.sum())
                tolerant=tolerant and bool(np.allclose(x[c].to_numpy(),y[c].to_numpy(),rtol=1e-12,atol=1e-12,equal_nan=True))
                if count:
                    delta=float((x[c]-y[c]).abs().max());differing.append({'variable':c,'different_cells':count,'maximum_absolute_difference':delta});total+=count;maximum=max(maximum,delta)
            else:character_equal=character_equal and x[c].equals(y[c])
        last=ds['nodes'][-1]['name'];record=next(v for v in old['nodes'] if v['dataset']==name and v['node']==last);old_json=original/'datasets'/name/'nodes'/last/f"attempt-{record['accepted_attempt']}"/'workspace/artifacts'/f"{len(ds['nodes'])-1}-result.json";new_json=root/'final-evaluation/replay/artifacts'/f"{name}-{len(ds['nodes'])-1}.json"
        rows.append({'dataset':name,'strict_data_equal':x.equals(y),'character_values_equal':character_equal,'numeric_values_within_original_export_gate_tolerance':tolerant,'metadata_differences':[k for k in ('column_labels','original_variable_types','variable_storage_width','file_label','table_name') if getattr(m,k,None)!=getattr(n,k,None)],'different_numeric_columns':differing,'final_process_json_byte_identical':digest(old_json)==digest(new_json),'export_intermediate_json_byte_identical':digest(original/'export-seed/artifacts'/(name+'-final.json'))==digest(root/'final-evaluation/replay/artifacts'/(name+'-final.json'))})
    parser=etree.XMLParser(resolve_entities=False,no_network=True,remove_blank_text=True);trees=[etree.parse(str(d/'define.xml'),parser) for d in (left,right)]
    for tree in trees:tree.getroot().attrib.pop('CreationDateTime',None)
    result={'supplementary_only':True,'strict_evaluator_result_unchanged':True,'different_numeric_cells':total,'maximum_absolute_difference':maximum,'tolerance_source':'Existing original export gate rtol=atol=1e-12; diagnostic only, not the strict semantic metric','all_final_process_json_byte_identical':all(r['final_process_json_byte_identical'] for r in rows),'define_equal_under_existing_timestamp_normalization':etree.tostring(trees[0],method='c14n')==etree.tostring(trees[1],method='c14n'),'datasets':rows,'script_sha256':digest(Path(__file__))}
    save(a.out or root/'rebuild-diagnostics.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('datasets','script_sha256')},indent=2))


if __name__=='__main__':main()
