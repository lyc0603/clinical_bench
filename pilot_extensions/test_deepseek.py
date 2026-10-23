import unittest
from main_experiment.test_completion import history,execution
from .deepseek_backend import completion,MODEL,DeepSeekEgress

class DeepSeekTests(unittest.TestCase):
    def h(self,reason='stop'):
        h=history(reason);h['messages'][-1]['info'].update(providerID='deepseek',modelID='deepseek-flash')
        return h

    def test_normal_completion_and_actual_identity(self):
        r=completion(self.h(),[],'session',execution())
        self.assertTrue(r['normal']);self.assertEqual(r['provider'],'deepseek')
        h=self.h();h['messages'][-1]['info']['modelID']='other'
        self.assertFalse(completion(h,[],'session',execution())['normal'])

    def test_truncated_unknown_and_pending_tools_rejected(self):
        for reason in ('length','tool-calls','end_turn','unknown'):
            self.assertFalse(completion(self.h(reason),[],'session',execution(reason))['normal'])
        h=self.h();h['messages'][-1]['parts'].append({'type':'tool','state':{'status':'running'}})
        self.assertFalse(completion(h,[],'session',execution())['normal'])

    def test_actual_error_not_hidden(self):
        e=execution();e['provider_errors']=[{'name':'APIError'}]
        self.assertFalse(completion(self.h(),[],'session',e)['normal'])

    def test_network_allows_only_official_host(self):
        class S:name='test'
        self.assertEqual(DeepSeekEgress(S(),None).allowed,['api.deepseek.com'])

if __name__=='__main__':unittest.main()
