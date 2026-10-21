import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pre_experiment.diagnose_p21 import main


class DiagnosticIsolationTests(unittest.TestCase):
    def test_failed_validation_retains_diagnostics_without_rewriting_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root/'cache'
            cache.mkdir()
            (cache/'pinned.jar').write_bytes(b'fixed')
            workspace = root/'checkpoint/workspace/output/adam/datasets'
            workspace.mkdir(parents=True)
            (workspace/'adsl.xpt').write_bytes(b'original')
            config = root/'config.json'
            config.write_text(json.dumps({'p21':{'cache':str(cache)},'expected_datasets':['ADSL']}))
            output = root/'diagnostics'
            def failed(evaluator, workspace, directory):
                import shutil
                with tempfile.TemporaryDirectory(prefix='p21-', dir=directory) as tmp:
                    shutil.copytree(cache, Path(tmp)/'cache')
                    log = Path(tmp)/'cache/lib/p21-client-1.0.9.log'
                    log.parent.mkdir()
                    log.write_text('now ERROR source - callback failed\n')
                    raise RuntimeError('P21 runtime drift during validation')
            args = ['diagnose','--config',str(config),'--checkpoint',str(root/'checkpoint'),
                    '--out',str(output),'--repeats','2']
            with patch('sys.argv',args), patch('main_experiment.evaluate.Evaluator.p21',failed):
                main()
            summary = json.loads((output/'summary.json').read_text())
            self.assertFalse(summary['pairsets_equal'])
            self.assertTrue(summary['source_datasets_and_cache_unchanged'])
            self.assertEqual(len(list(output.glob('*/p21-*/cache/lib/*.log'))),2)
            self.assertEqual((workspace/'adsl.xpt').read_bytes(), b'original')
            self.assertEqual((cache/'pinned.jar').read_bytes(), b'fixed')
            with patch('sys.argv',args):
                with self.assertRaises(FileExistsError):
                    main()


if __name__ == '__main__':
    unittest.main()
