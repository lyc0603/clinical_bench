import copy
import unittest
from research_analysis.paired_provenance import annotate

class ProvenanceTests(unittest.TestCase):
    def test_reassessment_does_not_hide_failure_or_change_score(self):
        r={'condition':'self_review','status':'failed','values':['unchanged']*16,
           'numeric':{'final':{'dataset_rule_pairs':26}},'source_sha256':{'current_revalidation/final':'sha'}}
        r['values'][2]='Usable 1/1'
        before=copy.deepcopy(r)
        annotate(r,{'final':{'status':'unavailable','report_usable':False,'failure_code':'client_runtime_error'}})
        self.assertEqual(r['status'],'failed');self.assertEqual(r['numeric'],before['numeric'])
        self.assertIn('Original usable 0/1; client_runtime_error',r['values'][2])
        self.assertIsNone(r['original_p21']['final']['dataset_rule_pairs'])
        once=r['values'][2];annotate(r,{'final':{'status':'unavailable','report_usable':False,'failure_code':'client_runtime_error'}})
        self.assertEqual(r['values'][2],once)

if __name__=='__main__':unittest.main()
