"""Runtime boundary tests with subprocesses replaced by deterministic doubles."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from main_experiment.backend import DockerSession
from main_experiment.core import fingerprint
from main_experiment.evaluate import Evaluator, meddra
from main_experiment.runner import verify
from main_experiment.test_main import cfg
from main_experiment.test_completion import history


class BoundaryTests(unittest.TestCase):
    def test_capture_help_combines_stderr_but_json_default_does_not(self):
        import sys
        from main_experiment.backend import capture
        command=[sys.executable,'-c',"import sys; print('--session --format',file=sys.stderr)"]
        self.assertEqual('',capture(command))
        self.assertEqual('--session --format',capture(command,include_stderr=True))

    def test_freeze_detects_drift_and_integrity(self):
        value = {'code': 'original'}
        lock = {'seal': value, 'sha256': fingerprint(value)}
        with patch('main_experiment.runner.seal', return_value=value):
            verify({}, lock)
            with self.assertRaises(RuntimeError):
                verify({}, dict(lock, sha256='changed'))
        with patch('main_experiment.runner.seal', return_value={'code':'changed'}):
            with self.assertRaises(RuntimeError):
                verify({}, lock)

    def test_backend_uses_explicit_session_and_secret_name_only(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            agent = DockerSession(cfg(), cfg()['models'][0], root, 'sha256:image')
            argv_seen = []
            def command(argv, cwd, log, timeout):
                self.assertIsNone(timeout)
                argv_seen.extend(argv)
                log.write_text(json.dumps({'type':'step_finish','sessionID':'same',
                    'part':{'id':'step','reason':'stop'}})+'\n')
                return {'exit_code':0,'timed_out':False,'seconds':1.}
            baseline=history();baseline['messages'][0]['info']['id']='old-user'
            baseline['messages'][1]['info'].update(id='old-assistant',parentID='old-user')
            exported=history();exported['info']['id']='same'
            for message in exported['messages']:message['info']['sessionID']='same'
            exported['messages']=baseline['messages']+exported['messages']
            baseline['info']['id']='same'
            for message in baseline['messages']:message['info']['sessionID']='same'
            with patch.dict('os.environ', {'OPENAI_API_KEY':'private-value'}), \
                    patch('main_experiment.backend.command', side_effect=command), \
                    patch('main_experiment.backend.capture', side_effect=[json.dumps(baseline),json.dumps(exported)]):
                sid, _ = agent.phase('repair',root,'same')
            self.assertEqual('same',sid)
            self.assertEqual('same',argv_seen[argv_seen.index('--session')+1])
            self.assertIn('OPENAI_API_KEY',argv_seen)
            self.assertNotIn('private-value',argv_seen)

    def test_phase_exports_completed_turn_when_stdout_has_no_finish(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);agent=DockerSession(cfg(),cfg()['models'][0],root,'image')
            def command(argv,cwd,log,timeout):
                log.write_text(json.dumps({'type':'text','sessionID':'session',
                    'part':{'messageID':'assistant','text':'done'}}))
                return {'exit_code':0,'timed_out':False,'seconds':1.}
            with patch.dict('os.environ',{'OPENAI_API_KEY':'value'}), \
                    patch('main_experiment.backend.command',side_effect=command) as called, \
                    patch('main_experiment.backend.capture',return_value=json.dumps(history())):
                sid,_=agent.phase('generate',root)
            self.assertEqual('session',sid)
            called.assert_called_once()
            decision=json.loads((root/'completion.json').read_text())
            self.assertTrue(decision['normal'])
            self.assertTrue(decision['stdout_finish_missing'])

    def test_timeout_stops_container_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); agent=DockerSession(cfg(),cfg()['models'][0],root,'image')
            def command(argv,cwd,log,timeout):
                log.write_text('')
                return {'exit_code':None,'timed_out':True,'seconds':1800.}
            with patch.dict('os.environ',{'OPENAI_API_KEY':'value'}), \
                    patch('main_experiment.backend.command',side_effect=command), \
                    patch('main_experiment.backend.capture',return_value='') as capture:
                with self.assertRaises(RuntimeError):
                    agent.phase('generate',root)
                capture.assert_called_once_with(['docker','stop','--time','1',agent.name])
            self.assertTrue(json.loads((root/'agent.json').read_text())['timed_out'])

    def test_backend_session_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); agent=DockerSession(cfg(),cfg()['models'][0],root,'image')
            def command(argv,cwd,log,timeout):
                log.write_text(json.dumps({'type':'step_finish','sessionID':'wrong',
                    'part':{'id':'p','reason':'stop'}}))
                return {'exit_code':0,'timed_out':False,'seconds':1.}
            with patch.dict('os.environ',{'OPENAI_API_KEY':'value'}), \
                    patch('main_experiment.backend.command',side_effect=command), \
                    patch('main_experiment.backend.capture',return_value=json.dumps(history())):
                with self.assertRaises(RuntimeError):
                    agent.phase('repair',root,'expected')
            self.assertTrue((root/'agent.json').exists())

    def test_dictionary_wrong_version_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'manifest.json';p.write_text(json.dumps({'version':'9.0','language':'English'}))
            with self.assertRaises(ValueError):
                meddra({'p21':{'meddra_manifest':str(p)}})

    def test_p21_explicit_dictionary_and_disposable_cache(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cache=root/'cache';cache.mkdir();(cache/'rules').write_text('fixed')
            inputs=root/'inputs/Input';inputs.mkdir(parents=True)
            for name in ('ae','dm','ex'):
                (inputs/(name+'.xpt')).write_text('synthetic')
            c=cfg();c['inputs']=str(inputs.parent);c['p21']['cache']=str(cache)
            out=root/'evaluation';out.mkdir();argv_seen=[]
            (root/'workspace/output/adam/datasets').mkdir(parents=True)
            def command(argv,cwd,log,timeout):
                argv_seen.extend(argv)
                report=Path(next(x.split('=',1)[1] for x in argv if x.startswith('--report=')))
                report.write_bytes(b'synthetic')
                return {'exit_code':5,'timed_out':False,'seconds':1.}
            with patch('main_experiment.evaluate.command',side_effect=command), \
                    patch('main_experiment.evaluate.conformance_metrics',return_value={'status':'valid','report_usable':True}):
                result=Evaluator(c,'image').p21(root/'workspace',out)
            self.assertEqual('valid',result['status'])
            self.assertIn('--meddra.version=8.0',argv_seen)
            self.assertNotIn(str(cache/'lib/p21-client-1.0.9.jar'),argv_seen)
            self.assertEqual(['rules'],[p.name for p in cache.iterdir()])
