import tempfile
from pathlib import Path
import unittest
import pandas as pd
from .boundary import preserve_nullable_characters,NODE_WRAPPER
from gxp_full.checks import equal_values
from .checks import node_checks


class BoundaryTests(unittest.TestCase):
    def test_null_character_dtype_and_null_semantics_survive_json(self):
        f=pd.DataFrame({'STUDYID':['S'],'USUBJID':['u1'],'__ROWID':[0],'C':[None],'N':[1.23456789]});defs={k:{'Type':'Numeric' if k=='N' else 'Character','Length':12} for k in ('STUDYID','USUBJID','C','N')}
        fixed=preserve_nullable_characters(f,defs)
        pd.testing.assert_series_equal(fixed.USUBJID,f.USUBJID,check_exact=True)
        pd.testing.assert_frame_equal(preserve_nullable_characters(fixed,defs),fixed)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'f.json';fixed.to_json(p,orient='table',index=False,double_precision=15);back=pd.read_json(p,orient='table')
            self.assertIsInstance(back.C.dtype,pd.StringDtype);self.assertTrue(back.C.isna().all());pd.testing.assert_series_equal(fixed.N,f.N,check_exact=True);equal_values(f,back,defs)
            self.assertEqual(node_checks(back,None,set(defs),defs,f[['STUDYID','USUBJID']],['C','N'],'ADAE'),[])
    def test_nonmissing_numeric_is_not_coerced_to_character(self):
        with self.assertRaises(ValueError):preserve_nullable_characters(pd.DataFrame({'C':[1]}),{'C':{'Type':'Character'}})
    def test_wrapper_keeps_program_contract_and_adds_boundary_before_write(self):
        import ast
        ast.parse(NODE_WRAPPER);self.assertLess(NODE_WRAPPER.index('result=preserve_nullable_characters'),NODE_WRAPPER.index('result.to_json'))


if __name__=='__main__':unittest.main()
