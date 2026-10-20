"""Completion fixtures are synthetic OpenCode exports, not provider qualification."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from main_experiment.completion import assess, smoke_evidence, validate_smoke_evidence
from main_experiment.backend import telemetry


def history(reason='stop'):
    return {'info':{'id':'session'},'messages':[
        {'info':{'id':'user','sessionID':'session','role':'user'},'parts':[]},
        {'info':{'id':'assistant','sessionID':'session','role':'assistant',
                 'parentID':'user','time':{'completed':1000},'finish':reason},
         'parts':[{'type':'step-finish','reason':reason}]}]}


def execution(reason='stop'):
    steps=[] if reason is None else [{'id':'part','messageID':'assistant','reason':reason}]
    return {'exit_code':0,'timed_out':False,'provider_errors':[],
            'session_ids':['session'],'steps':steps,'finish_reasons':[p['reason'] for p in steps]}


class CompletionTests(unittest.TestCase):
    def test_normal_provider_aliases_are_normalized_and_preserved(self):
        for provider,reason in [('openai','stop'),('anthropic','end_turn'),
                                ('anthropic','stop_sequence'),('google','STOP')]:
            result=assess(history(reason),[],'session',provider,execution(reason))
            self.assertTrue(result['normal'],result)
            self.assertEqual([reason,reason],result['export_finish_reasons'])
            self.assertEqual(reason.strip().lower().replace('_','-'),result['normalized_finish'])

    def test_missing_stdout_finish_uses_current_export(self):
        result=assess(history(),[],'session','openai',execution(None))
        self.assertTrue(result['normal'],result)
        self.assertTrue(result['stdout_finish_missing'])

    def test_stale_tool_calls_stdout_does_not_override_completed_new_message(self):
        run=execution('tool-calls');run['steps'][0]['messageID']='earlier-assistant'
        result=assess(history(),[],'session','openai',run)
        self.assertTrue(result['normal'],result)
        self.assertEqual(['tool-calls'],result['event_finish_reasons'])

    def test_missing_last_part_within_same_assistant_uses_exported_final_part(self):
        h=history();h['messages'][-1]['parts']=[
            {'id':'earlier','type':'step-finish','reason':'tool-calls'},
            {'id':'final','type':'step-finish','reason':'stop'}]
        run=execution('tool-calls');run['steps'][0]['id']='earlier'
        result=assess(h,[],'session','openai',run)
        self.assertTrue(result['normal'],result)
        self.assertTrue(result['stdout_finish_missing'])

    def test_current_stdout_part_absent_from_export_is_not_silently_ignored(self):
        h=history();h['messages'][-1]['parts'][0]['id']='export-final'
        self.assertFalse(assess(h,[],'session','openai',execution('length'))['normal'])

    def test_exit_zero_alone_or_final_text_is_not_completion(self):
        h=history();h['messages'][-1]['info'].pop('finish')
        h['messages'][-1]['parts']=[{'type':'text','text':'I am done'}]
        self.assertFalse(assess(h,[],'session','openai',execution())['normal'])
        h=history();h['messages'][-1]['info']['time']={}
        self.assertFalse(assess(h,[],'session','openai',execution())['normal'])

    def test_unknown_truncated_and_tool_turns_are_not_normal(self):
        for reason in ('length','max_tokens','MAX_TOKENS','tool-calls','tool_use',
                       'content-filter','SAFETY','error','other','unknown','provider-new-value'):
            with self.subTest(reason=reason):
                self.assertFalse(assess(history(reason),[],'session','openai',execution(reason))['normal'])
        # Raw aliases are provider-scoped, not a global acceptance list.
        self.assertFalse(assess(history('end_turn'),[],'session','openai',execution('end_turn'))['normal'])

    def test_conflicting_final_stdout_is_not_ignored(self):
        result=assess(history(),[],'session','openai',execution('length'))
        self.assertFalse(result['normal'])
        self.assertEqual('conflicting_or_unknown_final_event',result['reason'])

    def test_process_errors_and_export_errors_are_rejected(self):
        for changes in ({'exit_code':1},{'timed_out':True},{'provider_errors':[{'error':'API'}]}):
            run=execution();run.update(changes)
            self.assertFalse(assess(history(),[],'session','openai',run)['normal'])
        h=history();h['messages'][-1]['info']['error']={'name':'APIError'}
        self.assertFalse(assess(h,[],'session','openai',execution())['normal'])

    def test_no_new_turn_wrong_session_and_pending_tools_rejected(self):
        self.assertFalse(assess(history(),['user','assistant'],'session','openai',execution())['normal'])
        h=history();h['messages'][-1]['info']['parentID']='old-user'
        self.assertFalse(assess(h,[],'session','openai',execution())['normal'])
        h=history();h['info']['id']='wrong-session'
        self.assertFalse(assess(h,[],'session','openai',execution())['normal'])
        h=history();h['messages'][-1]['parts'].append({'type':'tool','state':{'status':'running'}})
        self.assertFalse(assess(h,[],'session','openai',execution())['normal'])

    def test_export_part_can_supply_reason_without_info_finish(self):
        h=history();h['messages'][-1]['info'].pop('finish')
        self.assertTrue(assess(h,[],'session','openai',execution(None))['normal'])

    def test_dedup_uses_latest_event_order_and_retains_unidentified_parts(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'events'
            def event(identity,reason):
                return {'type':'step_finish','sessionID':'session','part':{'id':identity,'reason':reason}}
            p.write_text('\n'.join(json.dumps(v) for v in [[],event('one','stop'),
                event('two','tool-calls'),event('one','length'),event(None,'STOP')]))
            parsed=telemetry(p)
            self.assertEqual(['tool-calls','length','STOP'],parsed['finish_reasons'])
            self.assertEqual(3,len(parsed['steps']))

    def test_smoke_receipt_requires_both_phases_current_policy_and_provider(self):
        model={'id':'openai','model':'openai/model'}
        completion=assess(history(),[],'session','openai',execution())
        evidence={'initial':completion,'final':copy.deepcopy(completion)}
        validate_smoke_evidence(evidence,model)
        for broken in ({}, {'initial':completion}):
            with self.assertRaises(ValueError):validate_smoke_evidence(broken,model)
        for field,value in [('provider','google'),('normal',False),('policy_sha256','stale'),
                            ('normalized_finish','length')]:
            broken=copy.deepcopy(evidence);broken['final'][field]=value
            with self.assertRaises(ValueError):validate_smoke_evidence(broken,model)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for phase in ('initial','final'):
                (root/phase).mkdir();(root/phase/'agent.json').write_text(json.dumps({'completion':completion}))
            self.assertEqual(evidence,smoke_evidence(root,model))
