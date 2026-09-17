import unittest,tempfile,json
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from topdown.journal import Journal
from topdown.tracking import track_predictions,collect_board
from topdown.live_results import parse_finals
from topdown.model import stamp

class AutomaticTrackingTests(unittest.TestCase):
    def test_board_evidence_is_frozen_with_original_prediction(self):
        row=dict(kickoff='2099-09-12T16:00:00Z',tracking_group='all_projection',contract='c',
                 event='e',sport='nfl',home='BUF',away='DET',player='Player',kind='prop',
                 profileId='p',market='rush_tds',line=.5,side='Over',book='test',dec=2,
                 odds=100,prob=.55,ev=.1,updatedAt='2026-09-17T16:00:00Z',
                 n=12,profileDate='2026-09-10',push=0,trust={'state':'research'},
                 provenance={'schema_version':1,'model_source_sha256':'original',
                             'inputs':{'history.json':{'sha256':'history','generated_at':'2026-09-17'}}})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=Journal(root/'db')
            with patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps([row]))):
                self.assertEqual(collect_board(j,root,0),1)
            row['provenance']['model_source_sha256']='later'
            with patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps([row]))):
                self.assertEqual(collect_board(j,root,0),0)
            saved=j.rows('prediction')[0]
            self.assertEqual(saved['provenance']['model_source_sha256'],'original')
            self.assertEqual(saved['model_evidence']['n'],12)
            self.assertEqual(saved['market'],'player_rushing_tds')
            self.assertEqual(saved['model_version'],'board-tracking-2')
            self.assertFalse(saved['actionable']);j.db.close()
    def test_recovery_freezes_first_before_kickoff_without_promoting_alert(self):
        p=dict(id='original',event='e',selection='s',side='Over',observed_at='2026-09-12T12:00:00Z',kickoff='2026-09-12T16:00:00Z',actionable=False,odds=2,probability=.5)
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(Path(tmp)/'j.sqlite')
            self.assertEqual(track_predictions(j,[dict(p,id='later',observed_at='2026-09-12T13:00:00Z'),p]),1)
            self.assertEqual(track_predictions(j,[p]),0)
            row=j.rows('prediction')[0];self.assertFalse(row['actionable']);self.assertEqual(row['origin_prediction_id'],'original')
            self.assertEqual(track_predictions(j,[dict(p,selection='late',observed_at='2026-09-12T17:00:00Z')]),0);j.db.close()
    def test_live_score_requires_official_final_not_clock_or_score(self):
        e=dict(id='e',date='2026-09-12T16:00:00Z',status={'type':{'completed':False,'name':'STATUS_IN_PROGRESS'}},competitions=[{'competitors':[{'homeAway':side,'score':score,'team':{'displayName':name}} for side,score,name in [('home','21','Georgia Bulldogs'),('away','14','Western Kentucky Hilltoppers')]]}])
        now=stamp('2026-09-12T19:30:00Z')
        self.assertFalse(parse_finals({'events':[e]},'ncaa',now,{}))
        e['status']['type']={'completed':True,'name':'STATUS_FINAL'}
        self.assertEqual(len(parse_finals({'events':[e]},'ncaa',now,{})),1)
        self.assertFalse(parse_finals({'events':[e]},'ncaa',stamp('2026-09-12T15:00:00Z'),{}))
