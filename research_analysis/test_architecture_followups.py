"""Follow-up reporting keeps unknown usage and partial P21 distinct from success."""
import unittest
from gxp_models.client import PROFILES,tokens
from research_analysis.publish_architecture_followups import display

class FollowupReportingTests(unittest.TestCase):
    def test_missing_hosted_cache_details_are_not_zero_or_a_crash(self):
        usage=tokens(PROFILES['gpt_oss_20b'],{'prompt_tokens':17,'completion_tokens':23,'prompt_tokens_details':None,'completion_tokens_details':None})
        self.assertEqual(usage['input'],17);self.assertEqual(usage['output'],23);self.assertIsNone(usage['cached_input'])
    def test_rejected_context_without_usage_is_unavailable(self):
        value=display(14,None,{'architecture_group':'gxp'})
        self.assertIn('Unavailable',value);self.assertNotIn('Input 0',value)
    def test_partial_observed_pairs_do_not_become_primary_score(self):
        result=display(4,{'final_primary_dataset_rule_pairs':None,'observed_final_dataset_rule_pairs':25},{'architecture_group':'gxp'})
        self.assertEqual(result,'Primary unavailable; partial observed 25')
    def test_official_and_gateway_credentials_have_separate_destinations(self):
        official=PROFILES['openai_official'];gateway=PROFILES['gateway_sol']
        self.assertEqual(official['endpoint'],'https://api.openai.com/v1/responses')
        self.assertEqual(official['key_env'],'OPENAI_API_KEY');self.assertNotEqual(official['key_env'],gateway['key_env'])

if __name__=='__main__':unittest.main()
