import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from topdown.feed import normalize
from topdown.model import evaluate,stamp,market_gate
from topdown.journal import Journal
from settle_markets import settle


class CollegeTrackingTests(unittest.TestCase):
    def game(self):
        return {'home_team':'Alabama','away_team':'East Carolina Pirates','commence_time':'2026-09-12T17:00:00Z','bookmakers':[{'key':book,'last_update':'2026-09-12T15:59:30Z','markets':[{'key':'h2h','outcomes':[{'name':'Alabama Crimson Tide','price':prices[0]},{'name':'East Carolina','price':prices[1]}]}]} for book,prices in [('pinnacle',[-110,-110]),('betonline',[-110,-110]),('draftkings',[120,-140])]]}
    def test_school_mascot_names_join_and_no_college_props(self):
        q=normalize([self.game()],[{'market_key':'player_passing_yards'}],sport='ncaa')
        self.assertEqual(len(q),3);self.assertTrue(all(r['sport']=='ncaa' and r['no_refund'] for r in q));self.assertEqual(len({r['selection'] for r in q}),1)
        nfl=normalize([self.game()],[])
        self.assertTrue(all(r['event']!=q[0]['event'] for r in nfl))
    def test_college_final_window_and_nfl_inactive_gate_stays(self):
        now=stamp('2026-09-12T16:00:00Z');q=normalize([self.game()],[],sport='ncaa')
        picks,_=evaluate(q,{},now);p=next(p for p in picks if p['side_index']==0)
        self.assertTrue(p['actionable']);self.assertEqual(p['sport'],'ncaa');self.assertEqual(p['inactive_state'],'availability_not_independently_verified')
        self.assertFalse(market_gate({},dict(q[0],sport='nfl'),now));self.assertFalse(market_gate({},q[0],now-3600));self.assertFalse(market_gate({},q[0],stamp(q[0]['kickoff'])))
    def test_college_final_score_settlement_by_team_identity(self):
        now=stamp('2026-09-12T16:00:00Z');p=next(p for p in evaluate(normalize([self.game()],[],sport='ncaa'),{},now)[0] if p['side_index']==0)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir();j=Journal(root/'db');j.append('prediction',p['id'],p)
            (root/'data/history.json').write_text(json.dumps({'betting':{'team_names':{},'profiles':{}}}))
            (root/'data/results.json').write_text(json.dumps({'generated_at':'2026-09-13T06:00:00Z','games':{'ncaa|1':{'sport':'ncaa','home':'Alabama','away':'East Carolina','kickoff':p['kickoff'],'homeScore':35,'awayScore':10}},'players':{}}))
            settle(j,root,stamp('2026-09-13T07:00:00Z'));rows=j.rows('settlement');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'win');self.assertEqual(rows[0]['sport'],'ncaa');j.db.close()


if __name__=='__main__':unittest.main()
