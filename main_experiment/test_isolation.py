"""Main runtime must remain independent of historical pilot implementation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from main_experiment.core import code_manifest
from main_experiment.rebuild import RebuildRuntime


class IsolationTests(unittest.TestCase):
    def test_import_and_manifest_without_pilot(self):
        script = '''
import importlib.abc
import sys
class BlockPilot(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'experiment' or fullname.startswith('experiment.'):
            raise ImportError('Pilot dependency forbidden')
sys.meta_path.insert(0, BlockPilot())
import main_experiment.__main__
from main_experiment.core import code_manifest
import json
print(json.dumps(code_manifest()))
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, check=True)
        manifest = json.loads(result.stdout)
        self.assertFalse(any(p.startswith('experiment/') for p in manifest))
        for name in ('support.py', 'rebuild.py', 'Dockerfile', 'requirements-evaluator.txt'):
            self.assertIn('main_experiment/' + name, manifest)
        self.assertEqual(manifest, code_manifest())

    def test_reconstruction_retains_offline_boundary_and_timeout_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / 'replay'
            workspace.mkdir()
            (workspace / 'deleted-by-rebuild').write_text('old')
            runtime = RebuildRuntime({'inputs': str(root / 'inputs')}, 'image')
            calls = []
            def docker(argv, **kwargs):
                calls.append(argv)
                if argv[:2] == ['docker', 'cp'] and ':/workspace/.' in argv[2]:
                    (Path(argv[3]) / 'rebuilt').write_text('new')
                return subprocess.CompletedProcess(argv, 0)
            execution = {'exit_code': None, 'seconds': 1, 'timed_out': True}
            with patch('main_experiment.rebuild.subprocess.run', side_effect=docker), \
                 patch('main_experiment.rebuild.command', return_value=execution):
                self.assertEqual(execution, runtime.rebuild(workspace, ['python', 'rebuild.py'], root/'log', 1800))
            self.assertEqual(['rebuilt'], [p.name for p in workspace.iterdir()])
            creates = [c for c in calls if c[:2] == ['docker', 'create']]
            for c in creates:
                self.assertEqual('none', c[c.index('--network') + 1])
            agent = next(c for c in creates if '--cap-drop=ALL' in c)
            self.assertIn('--security-opt=no-new-privileges', agent)
            self.assertTrue(any('dst=/inputs,readonly' in a for a in agent))
            self.assertTrue(any(c[:3] == ['docker', 'volume', 'rm'] for c in calls))
