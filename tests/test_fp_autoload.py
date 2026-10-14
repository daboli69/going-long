import csv
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from fp_autoload import prediction_period, main
from fp_ingest.parse import parse_export
from fp_ingest.store import inbox_files
from fp_ingest.weekly import inspect_file, model_inputs, sync
from fp_ingest.features import player_context

NOW = dt.datetime(2026, 10, 13, 21, tzinfo=dt.timezone.utc)
REG = {'tables': {}}

def data(games=1, season=2026, exported='2026-10-13 19:59', name='Player'):
    out=io.StringIO();w=csv.writer(out)
    w.writerow(['','Player Details','Player Details','Player Details','Player Details','FP','FP','FP'])
    w.writerow(['Season','Rank','Name','Team','G','TM RB XFP','BACKFIELD XFP %','XFP/G'])
    w.writerow([season,1,name,'BUF',games,12,25,''])
    w.writerow([season,'','League Avg','','',10,20,3]);w.writerow([])
    w.writerow([f'Exported from Data Suite 2.0 by Example on {exported} UTC'])
    return out.getvalue().encode()

class AutoloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.inbox=self.root/'Inbox';self.week=self.inbox/'Week 6';self.week.mkdir(parents=True)
    def put(self,folder,name='bell.csv',**kwargs):
        p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data(**kwargs));return p
    def inspect(self,p):return inspect_file(p,self.inbox,REG,2026,6,NOW,{})
    def test_leading_season_uppercase_rank_footer_and_real_blank_are_preserved(self):
        p=parse_export(data());self.assertEqual(len(p['rows']),2);self.assertEqual(p['columns'][0],'Player Details.Season');self.assertEqual(p['rows'][0][-1],'')
        self.assertIn('export_receipt:',p['notes'][0]);self.assertEqual(parse_export(data().replace(b'Rank',b'RANK'))['headers'][1],'RANK')
    def test_week_six_is_week_five_observation_not_future_week_six(self):
        i,d=self.inspect(self.put(self.week));self.assertEqual(i['scope'],'prior_week');self.assertEqual(i['observed_week'],5);self.assertEqual(len(d['records']),1);self.assertEqual(len(d['reference_rows']),1);self.assertIsNone(d['records'][0]['FP.XFP/G'])
    def test_season_and_weekly_coexist_without_adding_or_duplicate_inflation(self):
        self.put(self.week,'bell.csv');self.put(self.week,'bell (1).csv',games=5)
        self.put(self.week,'duplicate.csv');r=sync(self.root,REG,2026,6,NOW);self.assertEqual(r['accepted'],2)
        d=model_inputs(self.root,2026,6,NOW);self.assertEqual({x['scope'] for x in d},{'prior_week','season_to_date'})
    def test_week_seven_suffix_means_prior_week_and_rejects_cumulative(self):
        p=self.put(self.inbox/'Week 7','bell (1).csv',games=5)
        i,d=inspect_file(p,self.inbox,REG,2026,7,NOW,{});self.assertIsNone(d);self.assertIn('G exceeds one',i['problem'])
        p.write_bytes(data());i,d=inspect_file(p,self.inbox,REG,2026,7,NOW,{});self.assertEqual(d['observed_week'],6)
    def test_future_folder_historical_season_old_receipt_and_future_games_hold(self):
        for p in [self.put(self.inbox/'Week 7'),self.put(self.week,'old.csv',season=2025),self.put(self.week,'stale.csv',exported='2026-09-30 12:00'),self.put(self.week,'future.csv',games=6),self.put(self.week,'clock.csv',exported='2026-10-14 12:00')]:
            self.assertIsNone(self.inspect(p)[1])
    def test_explicit_invalid_or_historical_season_cannot_be_inferred(self):
        for season in ['2025.0', '2025x', '', '2026x', '2026.5']:
            self.assertIsNone(self.inspect(self.put(self.week, season=season))[1])
        self.assertIsNotNone(self.inspect(self.put(self.week, season='2026.0'))[1])
        p=self.put(self.week);p.write_bytes(p.read_bytes().replace(b'2026,,League Avg', b',,League Avg'))
        self.assertIsNotNone(self.inspect(p)[1])
    def test_overwritten_weekly_file_survives_as_verified_separate_archive(self):
        path=self.put(self.week);sync(self.root,REG,2026,6,NOW)
        path.write_bytes(data(games=5));r=sync(self.root,REG,2026,6,NOW)
        self.assertEqual(r['accepted'],2)
        d=model_inputs(self.root,2026,6,NOW)
        self.assertEqual({x['scope'] for x in d},{'prior_week','season_to_date'})
        archived=next(x for x in d if x['scope']=='prior_week')
        self.assertEqual(archived['source'],'immutable_raw_archive')
        (self.root/'raw/inbox-autoload'/f"{archived['sha256']}.csv").write_text('corrupt')
        self.assertEqual(sync(self.root,REG,2026,6,NOW)['accepted'],1)
    def test_known_at_is_immutable_no_retrospective_prediction_backfill(self):
        self.put(self.week);sync(self.root,REG,2026,6,NOW);later=NOW+dt.timedelta(minutes=5);sync(self.root,REG,2026,6,later)
        d=model_inputs(self.root,2026,6,later);self.assertEqual(d[0]['known_at'],NOW.isoformat());self.assertEqual(model_inputs(self.root,2026,6,NOW-dt.timedelta(seconds=1)),[])
        with self.assertRaises(ValueError):model_inputs(self.root,2026,7,NOW)
    def test_recursive_files_include_root_and_week_without_modifying_input(self):
        a=self.put(self.inbox,'root.csv',games=5);b=self.put(self.week);before=b.read_bytes();self.assertEqual(set(inbox_files(self.inbox)),{a,b});sync(self.root,REG,2026,6,NOW);self.assertEqual(b.read_bytes(),before)
    def test_period_comes_from_future_schedule_not_stale_roster_or_largest_folder(self):
        self.assertEqual(prediction_period({'week':5,'games':[{'season':2026,'week':6,'kickoff':'2026-10-16T00:15:00Z'},{'season':2026,'week':7,'kickoff':'2026-10-23T00:15:00Z'}]},NOW),(2026,6))
        with self.assertRaises(ValueError):prediction_period({'week':6,'games':[]},NOW)
    def test_copying_identical_bytes_to_next_week_cannot_relabel_observations(self):
        p=self.put(self.week);sync(self.root,REG,2026,6,NOW)
        next_folder=self.inbox/'Week 7';next_folder.mkdir();(next_folder/'bell (1).csv').write_bytes(p.read_bytes())
        r=sync(self.root,REG,2026,7,NOW+dt.timedelta(days=7));self.assertEqual(r['accepted'],0);self.assertTrue(any('another observation week' in x.get('problem','') for x in r['outcomes']))
    def test_fresh_download_of_outdated_season_totals_is_not_current(self):
        i,d=self.inspect(self.put(self.week,games=4));self.assertIsNone(d);self.assertIn('trail',i['problem'])
    def test_private_publish_is_change_only_and_validates_the_server_receipt(self):
        target=self.root/'model_inputs';target.mkdir();(target/'current.json').write_text(json.dumps({'datasets':[{'sha256':'toy','scope':'prior_week'}]}))
        schedule=self.root/'schedule.json';schedule.write_text('{}')
        report={'season':2026,'prediction_week':6,'files_scanned':1,'accepted':1,'sync':'local_only_backend_not_configured'}
        response=io.StringIO(json.dumps({'ok':True,'season':2026,'week':6,'datasets':1}));response.status=200
        with patch('fp_autoload.prediction_period',return_value=(2026,6)),patch('fp_autoload.sync',return_value=report),patch.dict('os.environ',{'GOING_FP_INGEST_URL':'https://going-long.vercel.app/api/fp-ingest','GOING_FP_INGEST_TOKEN':'a'*32},clear=True),patch('fp_autoload.urllib.request.urlopen',return_value=response) as send:
            self.assertEqual(main(['--root',str(self.root),'--schedule',str(schedule)]),0);self.assertEqual(main(['--root',str(self.root),'--schedule',str(schedule)]),0);self.assertEqual(send.call_count,1)
            self.assertEqual(json.loads((target/'status.json').read_text())['sync'],'private_backend_unchanged_no_upload')
    def test_new_folder_unnumbered_one_game_is_not_guessed_as_weekly(self):
        p=self.put(self.inbox/'Week 7');i,d=inspect_file(p,self.inbox,REG,2026,7,NOW,{});self.assertIsNone(d);self.assertIn('conflicts',i['problem'])
    def test_private_player_adapter_matches_exact_identity_and_keeps_scope_variants(self):
        self.put(self.week);sync(self.root,REG,2026,6,NOW)
        profile={'name':'Player','team':'BUF','position':None}
        # Fixture intentionally lacks POS: remains team context, never a guessed player match.
        result=player_context(self.root,profile,2026,6,NOW);self.assertEqual(result['player'],{});self.assertEqual(result['model_status'],'research_features_not_promoted')

if __name__=='__main__':unittest.main()
