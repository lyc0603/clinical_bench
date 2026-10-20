import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from derivation import score, paired_results
from experiment import save
from freeze_protocol import freeze
from protocol_lock import verify, verify_environment

HERE=Path(__file__).parent


class LockTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        source=self.root/'source';source.mkdir();(source/'SAP.txt').write_text('synthetic SAP')
        cache=self.root/'p21'
        (cache/'lib/engines').mkdir(parents=True);(cache/'configs').mkdir()
        (cache/'lib/p21-client-1.0.9.jar').write_text('synthetic jar')
        java=self.root/'java';java.write_text('synthetic java')
        self.config=json.loads((HERE/'config.example.json').read_text())
        self.config.update(study_root=str(source),input_allowlist=['SAP.txt'],repair_iterations=1)
        self.config['models']=[{'id':str(i),'model':'provider/model-v1','key_env':[]} for i in range(3)]
        self.config['p21'].update(cache=str(cache),java=str(java))
        with patch('freeze_protocol.subprocess.check_output',side_effect=['sha256:synthetic','synthetic versions']), patch('freeze_protocol.subprocess.run',return_value=subprocess.CompletedProcess([],0,'','java 1')):
            self.lock=freeze(self.config,self.root/'protocol')
        self.frozen=json.loads((self.root/'protocol/config.json').read_text())

    def tearDown(self):self.temp.cleanup()

    def test_valid_seal_and_environment(self):
        self.assertEqual(verify(self.frozen)['budget']['agent_calls'],27)
        verify_environment(self.lock,self.lock['environment'])

    def test_budget_drift_rejected(self):
        self.frozen['agent']['timeout_seconds']+=1
        with self.assertRaisesRegex(ValueError,'configuration changed'):verify(self.frozen)

    def test_input_drift_rejected(self):
        (Path(self.frozen['study_root'])/'SAP.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'inputs changed'):verify(self.frozen)

    def test_prompt_drift_rejected(self):
        Path(self.lock['prompt_files']['self_review']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'code/scoring rules changed'):verify(self.frozen)

    def test_runtime_drift_rejected(self):
        current=copy.deepcopy(self.lock['environment']);current['image_id']='changed'
        with self.assertRaisesRegex(ValueError,'runtime changed'):verify_environment(self.lock,current)

    def test_seal_and_overwrite_rejected(self):
        p=self.root/'protocol/protocol.lock.json';p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'seal changed'):verify(self.frozen)
        with self.assertRaisesRegex(ValueError,'never overwrite'):freeze(self.config,self.root/'protocol')


class DerivationTests(unittest.TestCase):
    def setUp(self):
        import pandas as pd
        import pyreadstat
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'source';self.data=self.root/'data'
        (self.source/'Input').mkdir(parents=True);self.data.mkdir()
        def write(root,name,rows):pyreadstat.write_xport(pd.DataFrame(rows),str(root/(name+'.xpt')))
        self.write=write
        write(self.source/'Input','dm',[dict(USUBJID='S',RFSTDTC='1960-01-01',RFENDTC='1960-03-01')])
        write(self.source/'Input','sv',[dict(USUBJID='S',VISITNUM=3.,SVSTDTC='1960-01-01')])
        write(self.source/'Input','qs',[dict(USUBJID='S',QSTESTCD='NPTOT',QSSEQ=1.,QSSTRESN=10.,QSDTC='1960-01-01'),dict(USUBJID='S',QSTESTCD='NPTOT',QSSEQ=2.,QSSTRESN=8.,QSDTC='1960-01-29')])
        write(self.data,'adqsn pix'.replace(' ',''),[dict(USUBJID='S',PARAMCD='NPTOTMN',AVISITN=98.,AVAL=8.,BASE=10.)])
        write(self.data,'adsl',[dict(USUBJID='S',ASEQ=1.)])
        write(self.data,'adae',[dict(USUBJID='S',ASEQ=1.,AESEQ=2.,ASTDT=30.,TRTSDT=0.,TRTEMFL='Y',CQ01NAM='DERM'),dict(USUBJID='S',ASEQ=2.,AESEQ=3.,ASTDT=30.,TRTSDT=0.,TRTEMFL='Y',CQ01NAM='DERM')])
        self.tte=dict(USUBJID='S',PARAMCD='TTDE',ASEQ=1.,CNSR=0.,ADT=30.,STARTDT=0.,AVAL=31.,SRCDOM='ADAE',SRCVAR='ASTDT',SRCSEQ=1.)
        write(self.data,'adtte',[self.tte])

    def tearDown(self):self.temp.cleanup()

    def checks(self):return {c['check']:c for c in score(self.source,self.data)['checks']}

    def test_source_means_and_baseline(self):
        c=self.checks()
        for name in ['npi_mean_coverage','npi_mean_value','npi_baseline_covariate','tte_source_link','tte_event_status']:
            self.assertEqual(c[name]['errors'],0,name)

    def test_same_date_wrong_event_detected(self):
        self.tte['SRCSEQ']=2.
        self.write(self.data,'adtte',[self.tte])
        c=self.checks()
        self.assertEqual(c['tte_source_link']['errors'],1)
        self.assertEqual(c['tte_event_date']['errors'],0)

    def test_missing_dataset_not_success(self):
        (self.data/'adqsn pix.xpt'.replace(' ','')).unlink()
        c=self.checks()
        self.assertEqual(c['npi_mean_value']['status'],'unavailable')
        self.assertIsNone(c['npi_mean_value']['errors'])

    def test_missing_trials_remain_in_paired_report(self):
        rules=HERE.parent/'docs/archive/legacy-paired-scoring-rules.json'
        save(self.root/'scoring-rules.json',json.loads(rules.read_text()))
        c={'protocol_lock':str(self.root/'protocol.lock.json'),'models':[{'id':'m'}], 'repetitions':3,'repair_iterations':1}
        rows=paired_results(c,self.root/'runsroot')
        self.assertEqual(len(rows),21)
        self.assertTrue(all(not r['eligible'] for r in rows))


class P21IsolationTests(unittest.TestCase):
    def test_bookkeeping_isolated_and_binary_drift_rejected(self):
        from experiment import Experiment
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cache=root/'canonical'
            (cache/'lib/engines').mkdir(parents=True);(cache/'configs').mkdir()
            (cache/'lib/p21-client-1.0.9.jar').write_text('jar')
            (cache/'lib/engines/app.data').write_text('original index')
            (cache/'lib/engines/engine.jar').write_text('original engine')
            e=Experiment({'models':[],'agent':{'image':'pinned'},'p21':{'cache':str(cache)},'protocol_lock':'test'},root)
            def bookkeeping(workspace,directory,isolated):
                (isolated/'lib/engines/app.data').write_text('changed index')
                return {'status':'valid'}
            stage=root/'stage';stage.mkdir()
            with patch.object(e,'_p21',side_effect=bookkeeping):
                r=e.p21(root/'workspace',stage)
            self.assertEqual(r['status'],'valid')
            self.assertTrue(r['p21_runtime_unchanged'])
            self.assertTrue(r['p21_bookkeeping_changed'])
            self.assertEqual((cache/'lib/engines/app.data').read_text(),'original index')
            self.assertEqual(list(stage.iterdir()),[])
            def drift(workspace,directory,isolated):
                (isolated/'lib/engines/engine.jar').write_text('changed engine')
                return {'status':'valid'}
            with patch.object(e,'_p21',side_effect=drift):r=e.p21(root/'workspace',stage)
            self.assertEqual(r['status'],'invalid_runtime')
            self.assertEqual((cache/'lib/engines/engine.jar').read_text(),'original engine')
