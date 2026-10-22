import copy
import json
from pathlib import Path
import tempfile
import unittest

from main_experiment.support import digest,manifest,save
from pre_experiment.recover_paired import completed_evidence


class RecoveryEvidenceTests(unittest.TestCase):
    def fixture(self,root):
        model={'id':'openai','model':'openai/gpt-6.1-sol'}
        prior={'seal':{'prompts':{'generate':'initial prompt','self_review':'review prompt'}}}
        save(root/'state.json',{'status':'failed','reason':'P21 report unavailable or invalid; endpoint retained, scheduling stopped for adjudication'})
        initial=[{'info':{'id':'m1','role':'assistant','providerID':'openai','modelID':'gpt-6.1-sol'}}]
        for phase in ('initial','final'):
            p=root/phase;(p/'workspace').mkdir(parents=True);(p/'workspace/code.py').write_text(phase)
            save(p/'workspace-manifest.json',manifest(p/'workspace'))
            save(p/'agent.json',{'completion':{'normal':True}})
            history={'messages':initial if phase=='initial' else initial+[{'info':{'id':'m2','role':'assistant','providerID':'openai','modelID':'gpt-6.1-sol'}}]}
            save(p/'history.json',history);save(p/'history.raw.json',history)
            save(p/'evaluation.json',{'conformance':{'status':'unavailable'}})
            (p/'prompt.txt').write_text(prior['seal']['prompts']['generate' if phase=='initial' else 'self_review'])
        save(root/'initial-only.json',{'evaluation_sha256':digest(root/'initial/evaluation.json')})
        return model,prior

    def test_completed_agents_survive_validator_failure_without_fake_checkpoint_seal(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);model,prior=self.fixture(root)
            evidence=completed_evidence(root,model,prior)
            self.assertEqual(evidence['original_status'],'failed')
            self.assertFalse((root/'final/checkpoint-manifest.json').exists())
            self.assertIn('final/evaluation.json',evidence['source_sha256'])

    def test_uncertain_agent_or_changed_workspace_cannot_be_reused(self):
        for failure in ('agent','workspace','model','history'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as t:
                root=Path(t);model,prior=self.fixture(root)
                if failure=='agent':save(root/'final/agent.json',{'completion':{'normal':False}})
                elif failure=='workspace':(root/'final/workspace/code.py').write_text('changed')
                elif failure=='model':model['model']='openai/other'
                else:save(root/'final/history.raw.json',{'messages':[]})
                with self.assertRaises(ValueError):completed_evidence(root,model,prior)


if __name__=='__main__':unittest.main()
