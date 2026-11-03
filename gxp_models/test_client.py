import unittest
import tempfile
import json
from pathlib import Path
from .client import PROFILES,body_for,parse,tokens


class ClientTests(unittest.TestCase):
    def test_evidence_archive_preserves_and_verifies_all_files(self):
        from .archive import archive_evidence
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';source.mkdir();(source/'nested').mkdir();(source/'nested/raw.bin').write_bytes(b'\x00\xffunchanged');(source/'state.json').write_text('{"status":"failed"}');target=root/'archive';target.mkdir()
            archive_evidence(source,target)
            receipt=json.loads((target/'archive-receipt.json').read_text())
            self.assertTrue(receipt['verified_lossless']);self.assertEqual(receipt['files'],2);self.assertTrue((source/'nested/raw.bin').is_file())
            with self.assertRaises(ValueError):archive_evidence(source,target)
    def test_no_web_or_temperature_and_matching_limits(self):
        for profile in PROFILES.values():
            body=body_for(profile,'synthetic','system')
            self.assertNotIn('temperature',body);self.assertFalse(body.get('tools'))
            self.assertNotIn('reasoning',body);self.assertNotIn('thinking',body)
            limit=body.get('max_tokens',body.get('max_output_tokens',body.get('generationConfig',{}).get('maxOutputTokens')))
            self.assertEqual(limit,32768)
    def test_gemini_thoughts_not_executable_and_stop_required(self):
        raw={'modelVersion':'gemini-3.1-pro-preview','candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'private','thought':True},{'text':'def run(): pass'}]}}]}
        result=parse(PROFILES['gemini'],raw);self.assertTrue(result['normal']);self.assertEqual(result['text'],'def run(): pass')
        raw['candidates'][0]['finishReason']='MAX_TOKENS';self.assertFalse(parse(PROFILES['gemini'],raw)['normal'])
    def test_chat_rejects_tool_calls(self):
        with self.assertRaises(ValueError):parse(PROFILES['deepseek'],{'choices':[{'message':{'tool_calls':[{}]}}]})
    def test_responses_rejects_hidden_web_calls_and_incomplete(self):
        profile=PROFILES['gateway_sol']
        with self.assertRaises(ValueError):parse(profile,{'output':[{'type':'web_search_call'}]})
        self.assertFalse(parse(profile,{'model':'gpt-6.1-sol','status':'incomplete','output':[{'type':'message','content':[{'type':'output_text','text':'code'}]}]})['normal'])
    def test_token_buckets_do_not_double_count_thinking(self):
        self.assertEqual(tokens(PROFILES['gemini'],{'promptTokenCount':10,'candidatesTokenCount':20,'thoughtsTokenCount':5})['output'],25)
        self.assertEqual(tokens(PROFILES['deepseek'],{'prompt_tokens':10,'completion_tokens':20,'completion_tokens_details':{'reasoning_tokens':5}})['output'],20)


if __name__=='__main__':unittest.main()
