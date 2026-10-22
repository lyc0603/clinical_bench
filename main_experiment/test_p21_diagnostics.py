"""P21 gates distinguish mutable logging from actual validation failures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from main_experiment.evaluate import Evaluator, P21ValidationError
from main_experiment.test_main import cfg


class P21DiagnosticTests(unittest.TestCase):
    def run_case(self, root, mutation, error_code=None, timed_out=False, report=True, stdout="Validation: Process completed.\n"):
        cache=root/'cache';cache.mkdir();(cache/'rules').write_text('fixed')
        inputs=root/'inputs/Input';inputs.mkdir(parents=True)
        for name in ('ae','dm','ex'):
            (inputs/(name+'.xpt')).write_text('synthetic')
        c=cfg();c['inputs']=str(inputs.parent);c['p21']['cache']=str(cache)
        c['p21']['java_options']=['-XX:ActiveProcessorCount=1']
        out=root/'evaluation';out.mkdir()
        (root/'workspace/output/adam/datasets').mkdir(parents=True)
        def execute(argv,cwd,log,timeout):
            self.assertEqual(argv[1:3],['-XX:ActiveProcessorCount=1','-jar'])
            mutation(cwd)
            log.write_text(stdout)
            if report:
                Path(next(x.split('=',1)[1] for x in argv if x.startswith('--report='))).write_bytes(b'synthetic')
            return {'exit_code':5,'timed_out':timed_out,'seconds':1.}
        evaluator=Evaluator(c,'image')
        with patch('main_experiment.evaluate.command',side_effect=execute), patch('main_experiment.evaluate.conformance_metrics',return_value={'status':'valid','report_usable':True}) as parser:
            if error_code:
                with self.assertRaises(P21ValidationError) as failure:
                    evaluator.p21(root/'workspace',out)
                self.assertEqual(failure.exception.code,error_code)
                parser.assert_not_called()
                self.assertTrue((out/'p21-failed-runtime').is_dir())
            else:
                self.assertTrue(evaluator.p21(root/'workspace',out)['report_usable'])
                self.assertFalse((out/'p21-failed-runtime').exists())
        evidence=json.loads((out/'p21-diagnostics.json').read_text())
        self.assertEqual(evidence['execution']['exit_code'],5)
        self.assertEqual(evidence['failure_code'],error_code)
        self.assertTrue((out/'p21-runtime-before.json').exists())
        self.assertTrue((out/'p21-runtime-after.json').exists())
        self.assertEqual((cache/'rules').read_text(),'fixed')
        with self.assertRaisesRegex(ValueError,'fresh output directory'):
            evaluator.p21(root/'workspace',out)
        return evidence

    def test_unreviewed_jvm_options_rejected(self):
        from main_experiment.core import assert_protocol
        c=cfg();c['p21']['java_options']=['-XX:ActiveProcessorCount=1']
        assert_protocol(c)
        for options in (['-XX:ActiveProcessorCount=2'], ['-javaagent:unknown.jar'], None):
            c['p21']['java_options']=options
            with self.assertRaises(ValueError):assert_protocol(c)

    @staticmethod
    def log(cache,text):
        path=cache/'lib/p21-client-1.0.9.log';path.parent.mkdir();path.write_text(text)

    def test_informational_log_is_mutable_without_invalidating_report(self):
        with tempfile.TemporaryDirectory() as t:
            e=self.run_case(Path(t),lambda cache:self.log(cache,'INFO completed\n'))
            self.assertEqual(e['immutable_changed_paths'],[])
            self.assertEqual(e['mutable_changed_paths'],['lib/p21-client-1.0.9.log'])

    def test_callback_error_report_stays_unavailable(self):
        with tempfile.TemporaryDirectory() as t:
            e=self.run_case(Path(t),lambda cache:self.log(cache,'ERROR callback failed\njava.util.NoSuchElementException: null\n'),'client_runtime_error')
            self.assertGreater(e['client_error_markers'],0)

    def test_stdout_error_is_rejected_without_client_log(self):
        with tempfile.TemporaryDirectory() as t:
            e=self.run_case(Path(t),lambda cache:None,'client_runtime_error',stdout='ERROR validation failed\n')
            self.assertEqual(e['client_error_markers'],0)
            self.assertGreater(e['stdout_error_markers'],0)

    def test_only_explicit_engine_state_path_is_mutable(self):
        def mutate(cache):
            path=cache/'lib/engines/app.data';path.parent.mkdir(parents=True);path.write_text('state')
        with tempfile.TemporaryDirectory() as t:
            e=self.run_case(Path(t),mutate)
            self.assertEqual(e['mutable_changed_paths'],['lib/engines/app.data'])

    def test_actual_rule_change_rejected_and_retained(self):
        with tempfile.TemporaryDirectory() as t:
            e=self.run_case(Path(t),lambda cache:(cache/'rules').write_text('changed'),'runtime_integrity')
            self.assertEqual(e['immutable_changed_paths'],['rules'])

    def test_timeout_and_missing_report_remain_distinct(self):
        for code,timeout in [('timeout',True),('missing_report',False)]:
            with self.subTest(code=code),tempfile.TemporaryDirectory() as t:
                self.run_case(Path(t),lambda cache:None,code,timed_out=timeout,report=False)


if __name__=='__main__':
    unittest.main()
