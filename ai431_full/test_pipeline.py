import ast
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from .design import variable_qc,row_qc,merge_variables,replay_entry,WRAPPER,context
from .client import PROFILES,body_for,parse,tokens,request

class PipelineTests(unittest.TestCase):
    def setUp(self):
        # Repeated subjects require row keys, not merely a subject merge.
        self.keys=pd.DataFrame({'__ROWID':[0,1,2],'USUBJID':['s1','s1','s2'],'__SRC_SEQ':[1,2,1]})
        self.definition={'Variable':'AVAL','Type':'Numeric','Length':8}
        self.frame=self.keys[['__ROWID','USUBJID']].assign(AVAL=[1.,2.,float('nan')])
    def test_duplicate_subject_rows_merge_without_cartesian_product(self):
        defs=[{'Variable':'USUBJID','Type':'Character','Length':8},self.definition]
        result=merge_variables(self.keys,{'USUBJID':self.keys[['__ROWID','USUBJID']],'AVAL':self.frame},defs)
        self.assertEqual(len(result),3);self.assertEqual(result.AVAL.iloc[1],2.)
    def test_wrong_row_mapping_order_duplicates_or_missing_rejected(self):
        for frame in [self.frame.iloc[::-1],self.frame.iloc[:2],self.frame.assign(__ROWID=[0,0,2]),self.frame.assign(USUBJID=['s1','s2','s2'])]:self.assertTrue(variable_qc(frame,self.keys,self.definition))
    def test_unassigned_values_rejected(self):
        self.assertTrue(variable_qc(self.frame.assign(BASE=3),self.keys,self.definition))
    def test_numeric_bool_infinity_and_missing(self):
        self.assertFalse(variable_qc(self.frame,self.keys,self.definition))
        self.assertTrue(variable_qc(self.frame.assign(AVAL=[True,False,True]),self.keys,self.definition))
        self.assertTrue(variable_qc(self.frame.assign(AVAL=[1.,float('inf'),2.]),self.keys,self.definition))
    def test_nullable_character_storage_and_length(self):
        definition={'Variable':'C','Type':'Character','Length':1}
        frame=self.keys[['__ROWID','USUBJID']].assign(C=pd.Series([None]*3,dtype='string'))
        self.assertFalse(variable_qc(frame,self.keys,definition))
        self.assertTrue(variable_qc(frame.assign(C=['FF','M','F']),self.keys,definition))
    def test_record_universe_cannot_supply_analysis_values(self):
        self.assertFalse(row_qc(self.keys,pd.DataFrame({'USUBJID':['s1','s2']})))
        self.assertTrue(row_qc(self.keys.assign(AVAL=3),pd.DataFrame({'USUBJID':['s1','s2']})))
        self.assertTrue(row_qc(self.keys,pd.DataFrame({'USUBJID':['s1']})))
    def test_replay_syntax_and_no_other_variable_outputs(self):
        text=replay_entry([{'dataset':'ADSL','dependencies':[],'variables':[{'Variable':'USUBJID'}]}],{'ADSL'})
        ast.parse(text);ast.parse(WRAPPER)
        self.assertIn("validate='one_to_one'",text)
        self.assertIn('run_variable.py',text)
    def test_provider_defaults_and_issuer_binding(self):
        for profile in PROFILES.values():
            body=body_for(profile,'x','y');self.assertNotIn('temperature',body);self.assertNotIn('reasoning_effort',body)
            self.assertNotIn('reasoning',body)
        self.assertEqual(PROFILES['gateway_sol']['key_env'],'GATEWAY_API_KEY')
        self.assertEqual(PROFILES['gpt_oss_20b']['key_env'],'DEEPINFRA_API_KEY')
    def test_anthropic_cache_accounting(self):
        value=tokens(PROFILES['claude'],{'input_tokens':10,'cache_read_input_tokens':20,'cache_creation_input_tokens':30,'output_tokens':5})
        self.assertEqual(value['input'],60);self.assertEqual(value['cached_input'],20)
    def test_truncation_and_tool_calls_rejected(self):
        profile=PROFILES['gpt_oss_20b'];raw={'model':profile['model'],'choices':[{'finish_reason':'length','message':{'content':'partial'}}],'usage':{'completion_tokens':32768}}
        self.assertFalse(parse(profile,raw)['normal'])
        raw['choices'][0]['message']['tool_calls']=[{}]
        with self.assertRaises(ValueError):parse(profile,raw)
    def test_transport_timeout_not_retried_or_redirected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'DEEPINFRA_API_KEY':'synthetic'}):
            with patch('urllib.request.OpenerDirector.open',side_effect=TimeoutError) as call:
                with self.assertRaises(TimeoutError):request(PROFILES['gpt_oss_20b'],'x',Path(tmp)/'call','y')
                self.assertEqual(call.call_count,1)
    def test_context_keeps_dependencies_and_only_matching_value_metadata(self):
        rows=[{'Variable':'AVAL','Derivation':'Use BASE','Codelist OID':'CL1'},{'Variable':'BASE','Derivation':'From source','Codelist OID':None},{'Variable':'UNRELATED','Derivation':'Other','Codelist OID':'CL2'}]
        spec={'sheets':{'Rules':[['Rule ID'],['GEN01']],'Implementation details':[['ID']],'Windows':[['Instrument']],'Site map':[['SITEID']],
            'Value level':[['Dataset','Parent variable','Codelist OID'],['ADTEST','BASE','CL1'],['ADTEST','UNRELATED','CL2'],['OTHER','AVAL','CL3']],
            'Parameter map':[['Dataset','PARAMCD'],['ADTEST','P1'],['OTHER','P2']],
            'Codelists':[['Codelist OID','Code'],['CL1','A'],['CL2','B'],['CL3','C']]}}
        result=context(spec,{'dataset':'ADTEST','metadata':{},'variables':rows,'dependencies':[]},{},rows[0])
        self.assertEqual({r['Variable'] for r in result['dependency_specifications']},{'AVAL','BASE'})
        self.assertEqual(len(result['value_level']),2);self.assertEqual(result['codelists'][1],['CL1','A'])
        self.assertEqual(result['rules'],spec['sheets']['Rules'])

if __name__=='__main__':unittest.main()
