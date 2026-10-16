import tempfile,unittest
from pathlib import Path
from topdown.journal import Journal
from topdown.tracking import track_predictions


def pred(i,**extra):
    return dict(id=i,event='e'+i,selection='s'+i,side='Over',kickoff='2026-09-12T17:00:00Z',observed_at='2026-09-12T12:00:00Z',**extra)


class JournalStreamingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.j=Journal(Path(self.tmp.name)/'j.sqlite')
        for p in (pred('plain',actionable=False),pred('act',actionable=True),pred('tracked',actionable=False,tracking_group='all_model')):
            self.j.append('prediction',p['id'],p)
        self.j.append('settlement','x',{'prediction_id':'act','observed_at':'2026-09-12T20:00:00Z'})
    def tearDown(self):
        self.j.db.close();self.tmp.cleanup()
    def test_iter_rows_matches_rows_and_filters(self):
        self.assertEqual(list(self.j.iter_rows('prediction')),self.j.rows('prediction'))
        used=[p['id'] for p in self.j.iter_rows('prediction',"COALESCE(json_extract(payload,'$.actionable'),0)!=0 OR COALESCE(json_extract(payload,'$.tracking_group'),'')!=''")]
        self.assertEqual(sorted(used),['act','tracked'])
    def test_id_queries(self):
        self.assertEqual(self.j.tracked_prediction_ids(),{'tracked'});self.assertEqual(self.j.settled_prediction_ids(),{'act'})
    def test_default_tracking_matches_explicit_list(self):
        self.assertEqual(track_predictions(self.j),2)  # plain + act, not the already tracked one
        self.assertEqual(track_predictions(self.j),0)
        self.assertEqual(track_predictions(self.j,self.j.rows('prediction')),0)

if __name__=='__main__':unittest.main()
