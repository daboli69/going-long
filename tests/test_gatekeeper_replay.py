import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import test_topdown
from topdown.model import evaluate,ev_hurdle,stamp
from backtest_topdown import replay


class GateReplayTests(unittest.TestCase):
    def setUp(self):
        f=test_topdown.TopDownTests();f.setUp();self.f=f
    def test_pinnacle_fallback_and_no_pinnacle_block(self):
        f=self.f
        picks=evaluate(f.quotes[::2],f.reports,f.now)[0]
        p=next(p for p in picks if p['side']=='Over')
        self.assertTrue(p['actionable']);self.assertTrue(p['single_source']);self.assertAlmostEqual(p['ev_threshold'],.035)
        self.assertFalse(any(p['actionable'] for p in evaluate(f.quotes[1:],f.reports,f.now)[0]))
        self.assertAlmostEqual(ev_hurdle(1.5,False),.025)
        self.assertAlmostEqual(ev_hurdle(1.5,True),.03)
    def test_alignment_boundary_and_pending(self):
        f=self.f
        for gap,allowed in [(60,True),(61,False)]:
            from datetime import datetime,timezone
            qs=[dict(q,updated_at=datetime.fromtimestamp(f.now-10-(gap if q['book']=='draftkings' else 0),timezone.utc).isoformat()) for q in f.quotes]
            p=next(p for p in evaluate(qs,f.reports,f.now)[0] if p['side']=='Over')
            self.assertEqual(p['actionable'],allowed);self.assertEqual(p['timestamp_delta_seconds'],gap)
        qs=[dict(q,kickoff='2026-09-14T17:00:00Z') for q in f.quotes]
        p=evaluate(qs,{},f.now)[0][0];self.assertEqual(p['inactive_state'],'pending_inactives');self.assertFalse(p['actionable'])
    def test_replay_actual_profit_and_matching_close(self):
        f=self.f
        d={'snapshots':[{'observed_at':'2026-09-13T16:00:00Z','quotes':f.quotes,'reports':f.reports}], 'outcomes':[{'selection':'s','actual':50,'observed_at':'2026-09-13T22:00:00Z'}], 'closes':[{'selection':'s','book':'pinnacle','prices':[-110,-110],'quoted_at':'2026-09-13T16:59:00Z'}]}
        r=replay(d);self.assertEqual(r['graded'],1);b=next(iter(r['bands'].values()));self.assertAlmostEqual(b['roi'],1.2);self.assertAlmostEqual(b['mean_price_advantage'],.1)
        d['closes'][0]['selection']='wrong-line';self.assertIsNone(next(iter(replay(d)['bands'].values()))['mean_price_advantage'])
        d['snapshots'][0]['reports']={};self.assertEqual(replay(d)['graded'],0)
    def test_future_outcome_cannot_train_first_fold(self):
        f=self.f
        d={'snapshots':[{'observed_at':'2026-09-13T16:00:00Z','quotes':f.quotes,'reports':f.reports}], 'outcomes':[{'selection':'s','actual':0,'observed_at':'2026-09-20T22:00:00Z'}]}
        self.assertEqual(replay(d)['folds'][0]['available_settlements'],0)
        self.assertEqual(replay(d)['folds'][0]['penalty'],0)


if __name__=='__main__':unittest.main()
