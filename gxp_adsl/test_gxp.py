import ast
import io
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import pyreadstat

from .checks import check_frame, validate_plan, exported
from .dag import NODES, OUTPUT_FILES
from .run import request, rebuild_entry, extract_code, source_files, MODEL, prompt_for


class DAGTests(unittest.TestCase):
    def test_plan_exactly_49_unique_owned_variables(self):
        names=[v for _,cols,_ in NODES for v in cols]
        self.assertEqual(len(NODES),15)
        self.assertEqual(len(names),len(set(names)))
        spec={'sheets':{'ADSL':[['Order','Variable']]+[[i,v] for i,v in enumerate(names)]}}
        validate_plan(spec)
        bad=copy.deepcopy(spec);bad['sheets']['ADSL'][-1][1]='unexpected'
        with self.assertRaises(ValueError):validate_plan(bad)

    def test_dependencies_precede_duration_and_completion(self):
        order={name:i for i,(name,_,_) in enumerate(NODES)}
        self.assertLess(order['derive_study_dates'],order['derive_duration'])
        self.assertLess(order['derive_flags'],order['derive_completion'])
        self.assertLess(order['apply_metadata'],order['export'])

    def test_plan_survives_json_freeze_roundtrip(self):
        self.assertEqual(NODES,json.loads(json.dumps(NODES)))

    def test_population_and_protected_value_changes_are_rejected(self):
        base=pd.DataFrame({'STUDYID':['TEST','TEST'],'USUBJID':['synthetic1','synthetic2'],'AGE':[50,60]})
        defs={'STUDYID':{'Type':'Character'},'USUBJID':{'Type':'Character'},'AGE':{'Type':'Numeric'}}
        required=list(defs)
        self.assertEqual(check_frame(base,base,required,defs,base),[])
        changed=base.copy();changed.loc[0,'AGE']=1
        self.assertTrue(any('upstream' in x for x in check_frame(changed,base,required,defs,base)))
        self.assertTrue(check_frame(base.iloc[:1],base,required,defs))

    def test_boolean_not_accepted_as_sas_numeric(self):
        base=pd.DataFrame({'STUDYID':['TEST'],'USUBJID':['synthetic1'],'X':[True]})
        defs={'STUDYID':{'Type':'Character'},'USUBJID':{'Type':'Character'},'X':{'Type':'Numeric'}}
        self.assertTrue(any('numeric' in x for x in check_frame(base,base,list(defs),defs)))

    def test_sas_character_missing_and_padding_are_equivalent(self):
        base=pd.DataFrame({'STUDYID':['TEST','TEST'],'USUBJID':['synthetic1','synthetic2'],'X':[None,'Y']})
        after=base.copy();after['X']=['','Y  ']
        defs={k:{'Type':'Character'} for k in base}
        self.assertEqual(check_frame(after,base,list(defs),defs,base),[])

    def test_define_version_on_metadata_version_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=root/'output/adam/datasets';data.mkdir(parents=True)
            pyreadstat.write_xport(pd.DataFrame({'STUDYID':['SYNTH'],'AGE':[50.0]}),str(data/'adsl.xpt'),file_format_version=5)
            (data/'define.xml').write_text('<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3" xmlns:def="http://www.cdisc.org/ns/def/v2.0"><Study><MetaDataVersion def:DefineVersion="2.0.0"><ItemDef Name="STUDYID"/><ItemDef Name="AGE"/></MetaDataVersion></Study></ODM>')
            for name in ['output/adam/metadata/adsl-metadata.json','output/adam/manifest.json','output/adam/notes.md']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
            _,errors=exported(root,{'STUDYID':{'Type':'Character'},'AGE':{'Type':'Numeric'}})
            self.assertEqual(errors,[])
            # The historical wrong-directory failure must identify the required path.
            (data/'define.xml').rename(root/'output/adam/define.xml')
            _,errors=exported(root,{'STUDYID':{'Type':'Character'},'AGE':{'Type':'Numeric'}})
            self.assertEqual(len(errors),1)
            self.assertIn('Missing required deliverable: output/adam/datasets/define.xml',errors[0])
            self.assertIn('found output/adam/define.xml instead',errors[0])
            self.assertFalse((data/'define.xml').exists())  # Never silently promote rejected files.
            (data/'define.xml').write_text('<malformed')
            _,errors=exported(root,{'STUDYID':{'Type':'Character'},'AGE':{'Type':'Numeric'}})
            self.assertTrue(any('not parseable: XMLSyntaxError' in e for e in errors))
            self.assertFalse(any('Missing required deliverable' in e for e in errors))

    def test_export_prompt_uses_shared_exact_output_contract(self):
        spec={'sheets':{k:[] for k in ('Rules','Implementation details','Codelists','Windows')}}
        with patch('gxp_adsl.run.variables',return_value=[]):
            prompt=json.loads(prompt_for(14,set(),spec,{},None))
        self.assertEqual(prompt['required_output_files'],OUTPUT_FILES)
        self.assertEqual(prompt['required_output_files']['define'],'output/adam/datasets/define.xml')
        self.assertIn(OUTPUT_FILES['define'],prompt['task'])

    def test_api_failure_has_no_automatic_retry(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-test-key'}):
            with patch('urllib.request.urlopen',side_effect=TimeoutError('synthetic')) as call:
                with self.assertRaises(TimeoutError):request('nonclinical',Path(temp))
                self.assertEqual(call.call_count,1)
            self.assertTrue((Path(temp)/'provider-failure.json').is_file())

    def test_plain_and_single_fenced_code_with_prose(self):
        code = 'def run(previous, inputs):\n    return previous'
        for reply in (code, '```python\n'+code+'\n```',
                      'Path corrected.\n\n```python\n'+code+'\n```\nExplanation.',
                      '~~~python\n'+code+'\n~~~'):
            self.assertEqual(extract_code(reply), code)
            ast.parse(extract_code(reply))

    def test_ambiguous_incomplete_and_wrong_language_fences_rejected(self):
        for reply in ('```python\nx=1', '```python\nx=1\n```\n```python\nx=2\n```',
                      '```json\n{}\n```', '```python\n\n```', '```python\nx=1\n~~~'):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                extract_code(reply)

    def test_exact_lowercase_source_paths_are_explicit(self):
        paths = source_files()
        self.assertEqual(paths['DM'], '/inputs/Input/dm.xpt')
        self.assertEqual(len(paths), 8)
        for domain, path in paths.items():
            self.assertEqual(Path(path).name, domain.lower()+'.xpt')

    def test_truncated_reply_is_never_accepted_even_with_valid_code(self):
        result = {'model':MODEL, 'stop_reason':'max_tokens', 'usage':{'output_tokens':32768},
                  'content':[{'type':'text','text':'def run(previous, inputs): return previous'}]}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-test-key'}):
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(result).encode())) as call:
                with self.assertRaises(RuntimeError):request('nonclinical', Path(temp))
                self.assertEqual(call.call_count, 1)
            self.assertTrue((Path(temp)/'response.private.json').is_file())

    def test_rebuild_contains_every_node_in_dependency_order(self):
        text=rebuild_entry()
        for i,(name,_,_) in enumerate(NODES,1):self.assertIn(f'{i:02d}-{name}.py',text)
        compile(text,'rebuild.py','exec')


if __name__=='__main__':unittest.main()
