import sys,unittest,tempfile
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from topdown.model import *
from topdown.feed import normalize
from topdown.journal import Journal
from scan_markets import feedback

class TopDownTests(unittest.TestCase):
    def setUp(self):
        self.now=stamp('2026-09-13T16:00:00Z')
        self.quote={'event':'e','selection':'s','home':'H','away':'A','kickoff':'2026-09-13T17:00:00Z','updated_at':'2026-09-13T15:59:30Z','book':'pinnacle','prices':[-110,-110],'market':'totals','line':44.5,'sides':['Over','Under'],'no_refund':True}
        team=lambda name:dict(name=name,status='official_confirmed',source_url='https://www.nfl.com/news/report',source_sha256='a'*64,published_at='2026-09-13T15:30:00Z',verified_at='2026-09-13T15:35:00Z',inactive_players=[])
        self.reports={'e':{'event':'e','teams':[team('H'),team('A')]}}
        self.quotes=[self.quote,dict(self.quote,book='circa'),dict(self.quote,book='draftkings',prices=[120,-140])]
    def test_margin_and_shrinkage(self):
        f=fair_pair([-110,-110]);self.assertAlmostEqual(f['power'][0],.5);self.assertAlmostEqual(sum(f['proportional']),1)
        self.assertIsNone(fair_pair([100,200]));self.assertAlmostEqual(shrink_rating(30,1,20,1)['rating'],20+10/9)
        self.assertLess(shrink_rating(30,1,20,1)['data_weight'],shrink_rating(30,1,20,5)['data_weight'])
        dist=compound_points(3,2);self.assertAlmostEqual(sum(dist['mass'])+dist['omitted_tail'],1,places=12);self.assertLess(dist['omitted_tail'],.00001)
    def test_action_requires_reports_and_two_references(self):
        picks,_=evaluate(self.quotes,self.reports,self.now);p=next(p for p in picks if p['side']=='Over')
        self.assertTrue(p['actionable']);self.assertAlmostEqual(p['raw_probability'],.5);self.assertAlmostEqual(p['probability'],.49);self.assertAlmostEqual(p['ev'],.078);self.assertGreater(p['proposed_stake'],0)
        for qs,reports in [(self.quotes,{}),(self.quotes[::2],self.reports)]:
            self.assertFalse(any(p['actionable'] for p in evaluate(qs,reports,self.now,min_sharps=2)[0]))
    def test_future_stale_and_integer_quotes_block(self):
        for updated in ['2026-09-13T16:01:00Z','2026-09-13T15:00:00Z']:
            self.assertEqual(evaluate([dict(q,updated_at=updated) for q in self.quotes],self.reports,self.now)[0],[])
        self.assertFalse(any(p['actionable'] for p in evaluate([dict(q,no_refund=False,line=44) for q in self.quotes],self.reports,self.now)[0]))
    def test_time_alone_or_wrong_team_is_not_inactives(self):
        self.assertFalse(inactive_gate(None,self.quote,self.now));self.reports['e']['teams'][0]['name']='Wrong';self.assertFalse(inactive_gate(self.reports['e'],self.quote,self.now))
    def test_inactive_player_and_unofficial_source_block(self):
        for t in self.reports['e']['teams']:t['source_url']='https://example.com'
        self.assertFalse(inactive_gate(self.reports['e'],self.quote,self.now))
    def test_market_identity_and_no_mismatched_spread_pair(self):
        g={'home_team':'H','away_team':'A','commence_time':self.quote['kickoff'],'bookmakers':[{'key':'pinnacle','last_update':self.quote['updated_at'],'markets':[{'key':'spreads','outcomes':[{'name':'H','point':-3.5,'price':-110},{'name':'A','point':3,'price':-110}]}]}]}
        self.assertEqual(normalize([g],[]),[]);g['bookmakers'][0]['markets'][0]['outcomes'][1]['point']=3.5;self.assertEqual(len(normalize([g],[])),1)
    def test_journal_is_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(Path(tmp)/'log.sqlite');j.append('prediction','a',{'odds':2});j.append('prediction','a',{'odds':3});self.assertEqual(j.rows('prediction')[0]['odds'],2);j.db.close()
    def test_performance_deduplicates_and_excludes_future_outcomes(self):
        picks,_=evaluate(self.quotes,self.reports,self.now);p=next(p for p in picks if p['side']=='Over');result={'prediction_id':p['id'],'status':'win','observed_at':'2026-09-14T10:00:00Z'}
        self.assertEqual(performance([p],{p['id']:result},self.now),{})
        groups=performance([p,p],{p['id']:result},stamp('2026-09-15T00:00:00Z'));b=next(iter(groups.values()));self.assertEqual(b['bets'],1);self.assertAlmostEqual(b['profit'],120)
        self.assertEqual(feedback([p],{p['id']:result},self.now),0)
    def test_arbitrage_partition_and_gate(self):
        quotes=[dict(self.quote,book='draftkings',prices=[110,-130]),dict(self.quote,book='fanduel',prices=[-130,110])]
        arbs=evaluate(quotes,self.reports,self.now)[1];self.assertEqual(len(arbs),1);self.assertAlmostEqual(sum(arbs[0]['stakes_per_100']),100);self.assertAlmostEqual(arbs[0]['return_if_executable'],.05)

if __name__=='__main__':unittest.main()
