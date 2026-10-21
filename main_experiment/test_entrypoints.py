"""Guard against freezing the wrong protocol and misinterpreting controller locks."""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from main_experiment.support import digest, save
from main_experiment.__main__ import main, smoke_qualified
from main_experiment.core import HERE, code_manifest, fingerprint
from main_experiment.test_main import cfg

ROOT=HERE.parent


def invocation(out,lock):
    return ['main_experiment','run','--config','unused-config.json',
            '--out',str(out),'--lock',str(lock),'--execute']


class EntryPointTests(unittest.TestCase):
    def test_smoke_technical_eligibility_keeps_bad_auxiliary_outcomes(self):
        e = dict(deliverables_complete=True, semantic_reproduced=True,
                 conformance=dict(report_usable=True, validation_coverage_complete=True),
                 correctness=dict(complete=False, errors=254), content_guard="review_required")
        self.assertTrue(smoke_qualified([e, e]))
        self.assertFalse(smoke_qualified([e]))
        for key in ("deliverables_complete", "semantic_reproduced"):
            self.assertFalse(smoke_qualified([e, dict(e, **{key: False})]))
        for key in ("report_usable", "validation_coverage_complete"):
            bad = dict(e, conformance=dict(e["conformance"], **{key: False}))
            self.assertFalse(smoke_qualified([e, bad]))

    def test_preflight_catalog_passes_only_selected_credential_name(self):
        c=cfg()
        def capture(argv, **kwargs):
            if argv[-1] == '--help':
                self.assertTrue(kwargs.get('include_stderr'))
                return '--session --format'
            provider=argv[-1]
            model=next(m for m in c['models'] if m['model'].split('/')[0] == provider)
            self.assertIn(model['key_env'],argv)
            self.assertNotIn('secret-value',argv)
            self.assertIn('OPENCODE_DISABLE_MODELS_FETCH=true',argv)
            for other in c['models']:
                if other is not model:self.assertNotIn(other['key_env'],argv)
            self.assertEqual('none',argv[argv.index('--network')+1])
            return model['model']
        with patch('sys.argv',['main_experiment','preflight']), \
             patch('main_experiment.__main__.config',return_value=c), \
             patch('main_experiment.__main__.load_env'), \
             patch('main_experiment.__main__.seal',return_value={'runtime':{'image':'synthetic'}}), \
             patch.dict('os.environ',{m['key_env']:'secret-value' for m in c['models']}), \
             patch('main_experiment.__main__.capture',side_effect=capture):
            main()

    def prepare(self,root):
        out=root/'run';lock=root/'freeze.json'
        item={'workflow':'w01','model':'openai','condition':'self_review','repetition':1}
        save(lock,{'seal':{'schedule':[item],'runtime':{'image':'synthetic'}},'sha256':'synthetic'})
        return out,lock

    def mocks(self,stack,out,lock,work):
        stack.enter_context(patch('sys.argv',invocation(out,lock)))
        stack.enter_context(patch('main_experiment.__main__.config',return_value=cfg()))
        stack.enter_context(patch('main_experiment.__main__.load_env'))
        stack.enter_context(patch('main_experiment.__main__.verify'))
        stack.enter_context(patch('main_experiment.__main__.report'))
        return stack.enter_context(patch('main_experiment.__main__.workflow',side_effect=work))

    def test_normal_and_python_exception_unwind_remove_guard(self):
        for error in (None,RuntimeError('synthetic failure'),KeyboardInterrupt(),SystemExit(7)):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as t,ExitStack() as stack:
                out,lock=self.prepare(Path(t))
                def work(*args):
                    self.assertTrue((out/'.running').exists())
                    if error is not None:raise error
                self.mocks(stack,out,lock,work)
                if error is None:main()
                else:
                    with self.assertRaises(type(error)):main()
                self.assertFalse((out/'.running').exists())

    def test_removed_guard_does_not_authorize_retrying_failed_workflow(self):
        with tempfile.TemporaryDirectory() as t,ExitStack() as stack:
            out,lock=self.prepare(Path(t))
            def fail(c,item,directory,image):
                save(directory/'state.json',dict(item,status='failed',reason='synthetic'))
                raise RuntimeError('synthetic agent failure')
            work=self.mocks(stack,out,lock,fail)
            with self.assertRaisesRegex(RuntimeError,'synthetic agent failure'):main()
            self.assertFalse((out/'.running').exists())
            with self.assertRaisesRegex(RuntimeError,'requires adjudication'):main()
            self.assertEqual(1,work.call_count)

    def test_abrupt_exit_retains_guard_and_second_controller_cannot_remove_it(self):
        with tempfile.TemporaryDirectory() as t:
            out,lock=self.prepare(Path(t))
            script='''
import os,sys
from pathlib import Path
from unittest.mock import patch
from main_experiment.__main__ import main, smoke_qualified
from main_experiment.test_main import cfg
out,lock=sys.argv[1:]
sys.argv=['main_experiment','run','--config','unused','--out',out,'--lock',lock,'--execute']
with patch('main_experiment.__main__.config',return_value=cfg()), \\
     patch('main_experiment.__main__.load_env'), \\
     patch('main_experiment.__main__.verify'), \\
     patch('main_experiment.__main__.workflow',side_effect=lambda *args: os._exit(23)):
    main()
'''
            result=subprocess.run([sys.executable,'-c',script,str(out),str(lock)],cwd=ROOT,
                                  capture_output=True,text=True,timeout=15)
            self.assertEqual(23,result.returncode,result.stderr)
            self.assertTrue((out/'.running').exists())
            with ExitStack() as stack:
                work=self.mocks(stack,out,lock,lambda *args:None)
                with self.assertRaises(FileExistsError):main()
                work.assert_not_called()
            self.assertTrue((out/'.running').exists())

    def test_legacy_freeze_requires_explicit_opt_in_before_reading_config(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'must-not-exist'
            result=subprocess.run([sys.executable,str(ROOT/'experiment/freeze_protocol.py'),
                '--config','nonexistent-config.json','--out',str(out)],cwd=ROOT,
                capture_output=True,text=True,timeout=15)
            self.assertEqual(2,result.returncode)
            self.assertIn('python -m main_experiment freeze',result.stderr)
            self.assertIn('--legacy-paired',result.stderr)
            self.assertFalse(out.exists())

    def test_freeze_rejects_receipts_without_provider_completion_proof(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);smokes=root/'smokes';smokes.mkdir();lock=root/'lock.json'
            seal={'synthetic':'current'}
            save(smokes/'openai.receipt.json',{'qualified':True,'seal_sha256':fingerprint(seal)})
            argv=['main_experiment','freeze','--out',str(root/'run'),
                  '--smokes',str(smokes),'--lock',str(lock)]
            with patch('sys.argv',argv), patch('main_experiment.__main__.config',return_value=cfg()), \
                    patch('main_experiment.__main__.load_env'), \
                    patch('main_experiment.__main__.seal',return_value=seal):
                with self.assertRaisesRegex(ValueError,'completion evidence'):main()
            self.assertFalse(lock.exists())

    def test_current_protocol_documents_are_sealed(self):
        files=code_manifest()
        for name in ('docs/main-study-protocol.md','docs/main-experiment-workflow.md'):
            self.assertEqual(digest(ROOT/name),files[name])
        readme=(ROOT/'README.md').read_text()
        self.assertIn('python -m main_experiment freeze',readme)
        self.assertNotIn('python3 experiment/freeze_protocol.py',readme)
        redirect=json.loads((ROOT/'docs/scoring-rules.json').read_text())
        self.assertEqual('../main_experiment/scoring-rules.json',redirect['current_contract'])
        self.assertTrue((ROOT/'docs'/redirect['current_contract']).resolve().is_file())
