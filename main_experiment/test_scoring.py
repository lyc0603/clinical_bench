"""Synthetic source truth fixtures for scoring boundaries and corruption."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from main_experiment.derivation import score


def fixtures():
    frames = {
        'dm': pd.DataFrame({'USUBJID': ['P','A','S'], 'ARMCD': ['Pbo','Xan_Lo','Scrn'],
                            'RFENDTC': ['1960-04-10']*3}),
        'sv': pd.DataFrame({'USUBJID': ['P','A'], 'VISITNUM': [3,3], 'SVSTDTC': ['1960-01-11']*2}),
        'qs': pd.DataFrame({'USUBJID': ['P','P','P','A','A','S'], 'QSTESTCD': ['NPTOT']*6,
                           'QSSTRESN': [5.,9.,11.,2.,4.,99.], 'QSSEQ': [1,2,3,1,2,1],
                           'QSDTC': ['1960-01-12','1960-02-08','1960-02-22','1960-01-11','1960-02-08','1960-02-08']}),
        'ex': pd.DataFrame({'USUBJID': ['P','A','S'], 'EXTRT': ['PLACEBO','XANOMELINE','PLACEBO'],
                           'EXDOSE': [0.,1.,0.], 'EXSTDTC': ['1960-01-11']*3}),
        'adqsnpix': pd.DataFrame({'USUBJID': ['P','A'], 'PARAMCD': ['NPTOTMN']*2,
                                  'AVISITN': [98,98], 'AVAL': [10.,4.], 'BASE': [5.,2.]}),
        'adsl': pd.DataFrame({'USUBJID': ['P','A']}),
        'adae': pd.DataFrame({'USUBJID': ['P','P','P'], 'TRTEMFL': ['Y']*3,
                             'CQ01NAM': ['DERMATOLOGIC EVENTS']*3, 'ASTDT': [20.,20.,101.],
                             'TRTSDT': [10.]*3, 'AESEQ': [1,2,3], 'ASEQ': [11,12,13]}),
        'adtte': pd.DataFrame({'USUBJID': ['P','A'], 'PARAMCD': ['TTDE']*2,
                              'CNSR': [0,1], 'SRCDOM': ['ADAE','ADSL'], 'SRCVAR': ['ASTDT','RFENDT'],
                              'SRCSEQ': [11.,float('nan')], 'ADT': [20.,100.],
                              'STARTDT': [10.,10.], 'AVAL': [11.,91.]})}
    return frames


def evaluate(frames):
    def read(path, **kwargs):
        return frames[Path(path).stem].copy(), None
    with patch('pyreadstat.read_xport', side_effect=read):
        result = score(Path('/synthetic/source'), Path('/synthetic/datasets'))
    return {c['check']: c for c in result['checks']}


class ScoringTests(unittest.TestCase):
    def test_correct_including_day_one_baseline_and_zero_dose_placebo(self):
        checks = evaluate(fixtures())
        self.assertTrue(all(c['status']=='scored' and c['errors']==0 for c in checks.values()), checks)
        self.assertEqual(2, checks['tte_subject_coverage']['assessed'])

    def test_baseline_corruption_detected(self):
        f = fixtures(); f['adqsnpix'].loc[0,'BASE'] = 99
        self.assertEqual(1, evaluate(f)['npi_baseline_covariate']['errors'])

    def test_identical_date_wrong_predecessor_detected(self):
        f = fixtures(); f['adtte'].loc[0,'SRCSEQ'] = 12
        self.assertEqual(1, evaluate(f)['tte_source_link']['errors'])

    def test_event_after_followup_not_eligible(self):
        f = fixtures(); f['adae'].loc[:1,'CQ01NAM'] = 'OTHER QUERY'
        self.assertEqual(1, evaluate(f)['tte_event_status']['errors'])

    def test_duplicate_anchor_same_date_allowed_conflict_unavailable(self):
        f = fixtures(); f['sv'] = pd.concat([f['sv'],f['sv'].iloc[[0]]], ignore_index=True)
        self.assertEqual('scored', evaluate(f)['npi_mean_value']['status'])
        f['sv'].loc[2,'SVSTDTC'] = '1960-01-12'
        check = evaluate(f)['npi_mean_value']
        self.assertEqual('unavailable', check['status'])
        self.assertIsNone(check['errors'])

    def test_missing_anchor_no_dm_fallback(self):
        f = fixtures(); f['sv'] = f['sv'].iloc[:1]
        self.assertEqual('unavailable', evaluate(f)['npi_mean_value']['status'])

    def test_wrong_start_and_censor_link_detected(self):
        f = fixtures(); f['adtte'].loc[0,'STARTDT'] = 9
        f['adtte'].loc[1,'SRCDOM'] = 'AE'
        checks = evaluate(f)
        self.assertEqual(1, checks['tte_start_date']['errors'])
        self.assertEqual(1, checks['tte_censor_convention']['errors'])

    def test_missing_followup_unavailable(self):
        f = fixtures(); f['dm'].loc[0,'RFENDTC'] = ''
        self.assertEqual('unavailable', evaluate(f)['tte_event_status']['status'])

    def test_coverage_components_retained(self):
        f = fixtures(); f['adqsnpix'] = pd.concat([f['adqsnpix'].iloc[[0]]]*2, ignore_index=True)
        self.assertEqual({'missing':1,'extra':0,'duplicates':1}, evaluate(f)['npi_mean_coverage']['coverage'])

    def test_semantic_xpt_values_labels_and_timestamp(self):
        import pyreadstat
        from main_experiment.evaluate import semantic
        with tempfile.TemporaryDirectory() as t:
            a,b = Path(t)/'a',Path(t)/'b'; a.mkdir();b.mkdir()
            df = pd.DataFrame({'ID':['A'], 'VALUE':[2.]})
            pyreadstat.write_xport(df,str(a/'ad.xpt'),table_name='AD',column_labels=['ID','Value'])
            pyreadstat.write_xport(df,str(b/'ad.xpt'),table_name='AD',column_labels=['ID','Value'])
            self.assertTrue(semantic(a,b))
            pyreadstat.write_xport(df,str(b/'ad.xpt'),table_name='AD',column_labels=['ID','Changed'])
            self.assertFalse(semantic(a,b))
            df.loc[0,'VALUE']=3.
            pyreadstat.write_xport(df,str(b/'ad.xpt'),table_name='AD',column_labels=['ID','Value'])
            self.assertFalse(semantic(a,b))
