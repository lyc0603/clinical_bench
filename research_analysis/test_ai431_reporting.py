"""Synthetic evidence tests: failed endpoints never acquire invented P21 scores."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ai431_full.client import PROFILES,body_for
from gxp_models.archive import archive_evidence
from main_experiment.core import fingerprint
from main_experiment.support import save,manifest
from research_analysis.report_ai431_full import report

class EvidenceReportingTests(unittest.TestCase):
    def fixture(self,directory):
        root=directory/'root';run=directory/'execution';root.mkdir();run.mkdir();(root/'inputs').mkdir()
        sheets={'Datasets':[['Dataset']]+[['D'+str(i)] for i in range(13)]}
        for i in range(13):sheets['D'+str(i)]=[['Variable','Type']]+[['X'+str(j),'Numeric'] for j in range(51 if i==0 else 40)]
        save(root/'inputs/specifications.json',{'sheets':sheets})
        profile={**PROFILES['gpt_oss_20b'],'response_model':'openai/gpt-oss-20b'}
        frozen={'code':{},'shared_code':{},'inputs':manifest(root/'inputs'),'provider_profile':profile,'variable_system':'VARIABLE','review_system':'REVIEW','export_system':'EXPORT','architecture':'Synthetic only','model':profile['model'],'provider':profile['provider'],'p21_cache':{}}
        save(root/'freeze.json',{'payload':frozen,'sha256':fingerprint(frozen)})
        save(run/'state.json',{'status':'failed','started_unix':0.,'finished_unix':60.,'tasks':[],'datasets':{}})
        call=run/'reviews/D0';call.mkdir(parents=True)
        usage={'prompt_tokens':7,'completion_tokens':10,'prompt_tokens_details':{'cached_tokens':2}}
        save(call/'request.private.json',body_for(profile,'Synthetic only','REVIEW'))
        save(call/'response.private.json',{'model':profile['model'],'choices':[{'finish_reason':'length','message':{'content':'incomplete'}}],'usage':usage})
        save(call/'usage.json',{'model':profile['model'],'stop_reason':'length','usage':usage})
        save(call/'completion-failure.json',{'stop_reason':'length'})
        archive_evidence(run,root);return root
    def test_failed_truncated_run_has_tokens_but_no_p21_or_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);root=self.fixture(directory)
            with patch('research_analysis.report_ai431_full.own_code',return_value={}),patch('research_analysis.report_ai431_full.shared_code',return_value={}):summary=report(root,directory/'aggregates')
            self.assertEqual(len(summary['metrics']),19)
            self.assertIsNone(summary['metrics'][3]['value']['final_primary_dataset_rule_pairs'])
            self.assertEqual(summary['metrics'][16]['value']['delivered'],0)
            self.assertEqual(summary['metrics'][17]['value']['matched'],0)
            self.assertIsNone(summary['metrics'][12]['value'])
            self.assertEqual(summary['native_usage'],{'input_tokens':7,'output_tokens':10,'cache_read_input_tokens':2})
            self.assertEqual(summary['metrics'][18]['value']['invalid_completion_calls'],1)
    def test_changed_archive_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);root=self.fixture(directory)
            with (root/'run-evidence.tar.gz').open('ab') as stream:stream.write(b'changed')
            with patch('research_analysis.report_ai431_full.own_code',return_value={}),patch('research_analysis.report_ai431_full.shared_code',return_value={}):
                with self.assertRaises(ValueError):report(root,directory/'aggregates')

if __name__=='__main__':unittest.main()
