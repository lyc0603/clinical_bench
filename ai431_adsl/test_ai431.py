import ast
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from .run import variable_qc, merge_variables, replay_entry, request, MODEL, context_for, SYSTEM, EXPORT_SYSTEM

class VariablePipelineTests(unittest.TestCase):
    def setUp(self):
        self.keys=pd.DataFrame({'USUBJID':['s1','s2']})
        self.defs=[{'Variable':'USUBJID','Type':'Character','Length':11},
                   {'Variable':'AGE','Type':'Numeric','Length':8},
                   {'Variable':'SEX','Type':'Character','Length':1}]
    def test_merge_aligns_shuffled_subject_keys(self):
        frames={'USUBJID':self.keys.copy(),'AGE':pd.DataFrame({'USUBJID':['s2','s1'],'AGE':[60,50]}),'SEX':pd.DataFrame({'USUBJID':['s1','s2'],'SEX':['F','M']})}
        merged=merge_variables(self.keys,frames,self.defs)
        self.assertEqual(list(merged.AGE),[50,60])
        self.assertEqual(list(merged),['USUBJID','AGE','SEX'])
    def test_rejects_missing_duplicate_extra_subjects_and_unowned_values(self):
        for frame in [pd.DataFrame({'USUBJID':['s1'],'AGE':[50]}),pd.DataFrame({'USUBJID':['s1','s1'],'AGE':[50,60]}),pd.DataFrame({'USUBJID':['s1','other'],'AGE':[50,60]}),pd.DataFrame({'USUBJID':['s1','s2'],'AGE':[50,60],'OTHER':[1,2]})]:
            self.assertTrue(variable_qc(frame,self.keys,self.defs[1]))
    def test_length_boolean_and_missingness_contract(self):
        self.assertTrue(variable_qc(pd.DataFrame({'USUBJID':['s1','s2'],'AGE':[True,False]}),self.keys,self.defs[1]))
        self.assertTrue(variable_qc(pd.DataFrame({'USUBJID':['s1','s2'],'SEX':['Female','M']}),self.keys,self.defs[2]))
        self.assertFalse(variable_qc(pd.DataFrame({'USUBJID':['s1','s2'],'AGE':[float('nan'),60]}),self.keys,self.defs[1]))
    def test_failed_variable_cannot_be_merged(self):
        with self.assertRaises(ValueError):merge_variables(self.keys,{'USUBJID':self.keys,'AGE':pd.DataFrame({'USUBJID':['s1'],'AGE':[50]})},self.defs[:2])
    def test_replay_contains_all_independent_variables_and_exact_key_merge(self):
        text=replay_entry(['USUBJID','AGE','SEX']);ast.parse(text)
        self.assertIn("validate='one_to_one'",text)
        self.assertIn("['python','-B'",text)
        self.assertIn('export.py',text)
    def test_export_has_dedicated_tool_free_library_contract(self):
        self.assertNotEqual(EXPORT_SYSTEM,SYSTEM)
        self.assertIn('NO TOOLS ARE AVAILABLE',EXPORT_SYSTEM)
        self.assertIn('pyreadstat.write_xport',EXPORT_SYSTEM)
        self.assertIn('NOT a dict',EXPORT_SYSTEM)
        response={'model':MODEL,'stop_reason':'end_turn','usage':{'output_tokens':10},'content':[{'type':'text','text':'def run(previous, inputs): return previous.copy()'}]}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic'}):
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
                code=request('synthetic export',Path(tmp),EXPORT_SYSTEM)
            ast.parse(code)
            body=json.loads((Path(tmp)/'request.private.json').read_text())
            self.assertEqual(body['system'],EXPORT_SYSTEM)
            self.assertNotIn('tools',body)

    def test_api_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic'}):
            with patch('urllib.request.urlopen',side_effect=TimeoutError) as call:
                with self.assertRaises(TimeoutError):request('synthetic',Path(tmp))
                self.assertEqual(call.call_count,1)
    def test_truncated_response_is_retained_and_rejected(self):
        response={'model':MODEL,'stop_reason':'max_tokens','usage':{'output_tokens':32768},'content':[{'type':'text','text':'incomplete'}]}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic'}):
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaises(RuntimeError):request('synthetic',Path(tmp))
            self.assertTrue((Path(tmp)/'response.private.json').is_file())

if __name__=='__main__':unittest.main()
