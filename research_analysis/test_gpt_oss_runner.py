"""Offline checks for checkpoint immutability and retained pilot failures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from main_experiment.support import save
from open_model_experiment.run import initial_only

class FakeSession:
    def __init__(self,c,model,directory,image):
        self.workspace=directory/'live';self.stopped=False
    def start(self):
        self.workspace.mkdir();(self.workspace/'artifact.txt').write_text('original')
    def phase(self,text,path,session=None):
        save(path/'agent.json',{'terminal':True});return 'test-session',{}
    def pause(self):pass
    def stop(self):self.stopped=True

class InitialOnlyTests(unittest.TestCase):
    def run_case(self,evaluate):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        d=Path(temp.name)/'attempt';instances=[]
        def make(*args):
            a=FakeSession(*args);instances.append(a);return a
        with patch('open_model_experiment.run.DeepInfraSession',side_effect=make),patch('open_model_experiment.run.Evaluator',return_value=evaluate):
            try:
                initial_only({},d,'dummy')
                error=None
            except RuntimeError as exc:
                error=exc
        return d,instances,error

    def test_unusable_p21_does_not_gate_initial_only_completion(self):
        def evaluate(workspace,phase):
            save(phase/'evaluation.json',{'conformance':{'report_usable':False}})
        d,agents,error=self.run_case(evaluate)
        self.assertIsNone(error)
        self.assertEqual(json.loads((d/'state.json').read_text())['status'],'completed')
        receipt=json.loads((d/'initial-only.json').read_text())
        self.assertFalse(receipt['shared_initial'])
        self.assertTrue(agents[0].stopped)

    def test_evaluator_mutation_rejected_and_retained(self):
        def evaluate(workspace,phase):
            (workspace/'artifact.txt').write_text('altered')
            save(phase/'evaluation.json',{})
        d,agents,error=self.run_case(evaluate)
        self.assertRegex(str(error),'Evaluator altered checkpoint')
        self.assertEqual(json.loads((d/'state.json').read_text())['status'],'failed')
        self.assertFalse((d/'initial-only.json').exists())
        self.assertEqual((d/'initial/workspace/artifact.txt').read_text(),'altered')
        self.assertTrue(agents[0].stopped)

    def test_evaluator_failure_retained_without_endpoint_receipt(self):
        def evaluate(workspace,phase):
            raise RuntimeError('synthetic technical interruption')
        d,agents,error=self.run_case(evaluate)
        self.assertIsNotNone(error)
        self.assertEqual(json.loads((d/'state.json').read_text())['status'],'failed')
        self.assertTrue((d/'initial/workspace/artifact.txt').exists())
        self.assertFalse((d/'initial-only.json').exists())
        self.assertTrue(agents[0].stopped)

if __name__=='__main__':unittest.main()
