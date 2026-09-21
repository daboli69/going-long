import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_roster import normalize

class RosterTests(unittest.TestCase):
    def test_all_positions_and_current_week_only(self):
        rows = [dict(season=2026, game_type='REG', week=2, gsis_id=str(i), team='BAL', position=p, status='ACT') for i,p in enumerate(['QB','OL','DL','LB','DB','P','K','LS'])]
        rows += [dict(rows[0], gsis_id='old', week=1), dict(rows[0], gsis_id='ir', status='RES')]
        result=normalize(rows, [], 2026)
        self.assertEqual(len(result['players']), 8)
        self.assertEqual(result['week'], 2)

    def test_injury_text_retained_without_invented_body_regions(self):
        roster=[dict(season=2026,game_type='REG',week=2,gsis_id='p',team='BAL',status='ACT')]
        injury=dict(season=2026,season_type='REG',week=2,gsis_id='p',report_status='Questionable',report_primary_injury='Hamstring',practice_status='Limited')
        self.assertEqual(normalize(roster,[injury],2026)['players'][0]['injury']['primary_injury'],'Hamstring')
        rest=dict(injury,report_status=None,report_primary_injury='Not injury related - resting player',practice_status='Full')
        self.assertIsNone(normalize(roster,[rest],2026)['players'][0]['injury'])
