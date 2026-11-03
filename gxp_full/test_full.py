import ast
import copy
from pathlib import Path
import tempfile
import unittest
import pandas as pd
from .plan import make_plan,validate_plan,NODE_WRAPPER,EXPORT_WRAPPER
from .checks import node_checks,equal_values
from .run import replay_entry,read_source_schema
from unittest.mock import patch
from types import SimpleNamespace
from .storage import normalize_character_storage


def synthetic_spec():
    names=['ADSL','ADAE','ADLBC','ADLBH','ADLBHY','ADQSADAS','ADQSCIBC','ADQSNPIX','ADTTE','ADVS','ADCM','ADDS','ADEX']
    counts=[49,58,47,47,44,43,39,43,28,38,37,26,32]
    from gxp_adsl.dag import NODES
    adsl=[v for _,cols,_ in NODES for v in cols]
    sheets={'Datasets':[['Dataset','Label','Structure','Source domains','Build order']]}
    for ds,count in zip(names,counts):
        deps='' if ds=='ADSL' else ('ADLBC, ADSL' if ds=='ADLBHY' else 'ADAE, ADSL' if ds=='ADTTE' else 'DM, ADSL')
        sheets['Datasets'].append([ds,'Synthetic','rows',deps,1 if ds=='ADSL' else 3 if ds in ('ADLBHY','ADTTE') else 2])
        vars=adsl if ds=='ADSL' else ['STUDYID','USUBJID','AGE','AVAL','TESTFL']+['X'+str(i) for i in range(count-5)]
        sheets[ds]=[['VariableIndex','Variable','Type','Length','Origin','Origin source']]+[[i,v,'Character' if v in ('STUDYID','USUBJID','TESTFL') else 'Numeric',12 if v in ('STUDYID','USUBJID') else 8,'Predecessor' if v in ('STUDYID','USUBJID') else 'Derived','ADSL.AGE' if ds!='ADSL' and v=='AGE' else None] for i,v in enumerate(vars)]
    return {'sheets':sheets}


class FullDAGTests(unittest.TestCase):
    def test_missing_character_storage_survives_json_and_xpt(self):
        import numpy as np
        import pyreadstat
        defs={'C':{'Type':'Character'},'N':{'Type':'Numeric'}}
        original=pd.DataFrame({'C':[np.nan,np.nan],'N':[1.25,np.nan]})
        normalized=normalize_character_storage(original,defs)
        self.assertTrue(original.C.isna().all())
        self.assertEqual(normalized.C.tolist(),['',''])
        pd.testing.assert_series_equal(original.N,normalized.N)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);normalized.to_json(path/'f.json',orient='table',index=False)
            reloaded=pd.read_json(path/'f.json',orient='table')
            pyreadstat.write_xport(reloaded,str(path/'f.xpt'),file_format_version=5)
            frame,meta=pyreadstat.read_xport(str(path/'f.xpt'))
            self.assertEqual(meta.readstat_variable_types['C'],'string')
            self.assertEqual(frame.C.tolist(),['',''])
    def test_character_normalization_rejects_nonmissing_numbers(self):
        with self.assertRaises(ValueError):normalize_character_storage(pd.DataFrame({'C':[123.0]}),{'C':{'Type':'Character'}})
    def test_all_missing_numeric_storage_cannot_pass_character_gate(self):
        f=pd.DataFrame({'STUDYID':['S'],'USUBJID':['u1'],'__ROWID':[0],'C':[float('nan')]})
        defs={c:{'Type':'Character','Length':12} for c in ('STUDYID','USUBJID','C')}
        self.assertIn('C: expected character storage even when entirely missing',node_checks(f,None,set(defs),defs,f[['STUDYID','USUBJID']],['C'],'ADAE'))
        fixed=normalize_character_storage(f,defs)
        self.assertEqual(node_checks(fixed,None,set(defs),defs,f[['STUDYID','USUBJID']],['C'],'ADAE'),[])
    def test_exact_full_coverage_unique_ownership_and_dependency_order(self):
        spec=synthetic_spec();plan=make_plan(spec)
        self.assertEqual(sum(len(n['owns']) for d in plan for n in d['nodes']),531)
        self.assertEqual(sum(len(d['nodes']) for d in plan),73)
        seen=[]
        for d in plan:
            self.assertTrue(set(d['dependencies'])<=set(seen));seen.append(d['dataset'])
        self.assertEqual(next(d['dependencies'] for d in plan if d['dataset']=='ADTTE'),['ADAE','ADSL'])
    def test_duplicate_ownership_and_cycle_are_rejected(self):
        spec=synthetic_spec();plan=make_plan(spec)
        bad=copy.deepcopy(plan);bad[0]['nodes'][1]['owns'].append('AGE')
        with self.assertRaises(ValueError):validate_plan(spec,bad)
        bad=copy.deepcopy(plan);bad[0]['dependencies']=['ADTTE']
        with self.assertRaises(ValueError):validate_plan(spec,bad)
    def test_missing_dataset_or_variable_cannot_pass(self):
        spec=synthetic_spec();plan=make_plan(spec)
        with self.assertRaises(ValueError):validate_plan(spec,plan[:-1])
        plan[0]['nodes'][1]['owns'].remove('STUDYID')
        with self.assertRaises(ValueError):validate_plan(spec,plan)
    def test_row_identity_and_prior_values_are_protected(self):
        f=pd.DataFrame({'STUDYID':['S','S'],'USUBJID':['u1','u2'],'__ROWID':[0,1],'AGE':[50,60]});defs={k:{'Type':'Character' if k in ('STUDYID','USUBJID') else 'Numeric','Length':12} for k in ('STUDYID','USUBJID','AGE')};expected=f[['STUDYID','USUBJID']]
        self.assertEqual(node_checks(f,f,set(defs),defs,expected,[],'ADSL'),[])
        changed=f.copy();changed.loc[0,'AGE']=0
        self.assertIn('Protected upstream values changed',node_checks(changed,f,set(defs),defs,expected,[],'ADSL'))
        self.assertTrue(node_checks(f.iloc[::-1],f,set(defs),defs,expected,[],'ADSL'))
    def test_eligibility_type_and_character_length_gates(self):
        f=pd.DataFrame({'STUDYID':['S'],'USUBJID':['u1'],'__ROWID':[0],'FLAG':['Y']});defs={k:{'Type':'Character','Length':1 if k=='FLAG' else 12} for k in ['STUDYID','USUBJID','FLAG']};expected=f[['STUDYID','USUBJID']]
        changed=f.copy();changed.loc[0,'FLAG']='TOO LONG'
        self.assertTrue(node_checks(changed,None,set(defs),defs,expected,['FLAG'],'ADAE'))
        changed=f.copy();changed.loc[0,'USUBJID']='unknown'
        self.assertTrue(node_checks(changed,None,set(defs),defs,expected,['FLAG'],'ADAE'))
    def test_sas_padding_normalization_does_not_change_numeric_gate(self):
        equal_values(pd.DataFrame({'C':[None,'Y']}),pd.DataFrame({'C':['','Y  ']}),{'C':{'Type':'Character'}})
        with self.assertRaises(AssertionError):equal_values(pd.DataFrame({'N':[1.0]}),pd.DataFrame({'N':[2.0]}),{'N':{'Type':'Numeric'}})
    def test_source_encoding_fallback_is_explicit_and_only_on_decode_failure(self):
        fake=pd.DataFrame({'TSVAL':['synthetic']});meta=SimpleNamespace(readstat_variable_types={'TSVAL':'string'})
        with patch('gxp_full.run.pyreadstat.read_xport',side_effect=[UnicodeDecodeError('utf-8',b'\x92',0,1,'synthetic'),(fake,meta)]) as read:
            schema=read_source_schema(Path('synthetic.xpt'))
            self.assertEqual(schema['read_encoding'],'cp1252')
            self.assertEqual(read.call_args.kwargs['encoding'],'cp1252')
        with patch('gxp_full.run.pyreadstat.read_xport',side_effect=OSError('synthetic')) as read:
            with self.assertRaises(OSError):read_source_schema(Path('synthetic.xpt'))
            self.assertEqual(read.call_count,1)

    def test_replay_wrapper_and_plan_survive_serialization(self):
        import json
        p=make_plan(synthetic_spec());self.assertEqual(p,json.loads(json.dumps(p)))
        text=replay_entry(p,{d['dataset'] for d in p});ast.parse(text);ast.parse(NODE_WRAPPER);ast.parse(EXPORT_WRAPPER)
        self.assertIn("['python','-B'",text);self.assertIn('run_export.py',text)
        self.assertNotIn('ANTHROPIC_API_KEY',text)

if __name__=='__main__':unittest.main()
