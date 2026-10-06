import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_roster import normalize, bye_teams_for, latest_week

class RosterTests(unittest.TestCase):
    def test_all_positions_and_current_week_only(self):
        rows = [dict(season=2026, game_type='REG', week=2, gsis_id=str(i), team='BAL', position=p, status='ACT') for i,p in enumerate(['QB','OL','DL','LB','DB','P','K','LS'])]
        rows += [dict(rows[0], gsis_id='old', week=1), dict(rows[0], gsis_id='ir', status='RES')]
        result=normalize(rows, [], 2026)
        self.assertEqual(len(result['players']), 8)
        self.assertEqual(result['week'], 2)

    def rows(self, team, week, n=2, status='ACT'):
        return [dict(season=2026, game_type='REG', week=week, gsis_id=f'{team}{week}{i}', team=team, position='WR', status=status) for i in range(n)]

    def test_bye_week_team_is_carried_forward_from_its_latest_earlier_week(self):
        roster = self.rows('BAL', 4) + self.rows('KC', 3) + self.rows('KC', 4) + self.rows('BAL', 5) + self.rows('KC', 1)
        roster = [r for r in roster if not (r['team'] == 'KC' and r['week'] == 5)]
        result = normalize(roster, [], 2026, ['KC'])
        self.assertEqual(result['week'], 5)
        self.assertEqual(result['bye_carry_forward_teams'], ['KC'])
        kc = [p for p in result['players'] if p['team'] == 'KC']
        self.assertEqual({p['week'] for p in kc}, {4})
        self.assertTrue(all(p['bye_carry_forward'] for p in kc))
        self.assertEqual(len([p for p in result['players'] if p['team'] == 'BAL']), 2)
        self.assertFalse(any(p.get('bye_carry_forward') for p in result['players'] if p['team'] == 'BAL'))

    def test_non_bye_team_missing_from_the_latest_week_is_still_missing(self):
        roster = self.rows('BAL', 5) + self.rows('KC', 4)
        teams = {p['team'] for p in normalize(roster, [], 2026, [])['players']}
        self.assertEqual(teams, {'BAL'})  # build() then fails its 32-team safeguard

    def test_bye_teams_come_from_the_schedule_week_only(self):
        sched = [dict(season=2026, game_type='REG', week=w, home_team=h, away_team=a) for w, h, a in [(4, 'BAL', 'KC'), (4, 'DAL', 'NYG'), (5, 'BAL', 'DAL')]]
        self.assertEqual(bye_teams_for(sched, 2026, 5), ['KC', 'NYG'])
        self.assertEqual(bye_teams_for(sched, 2026, 4), [])
        self.assertEqual(bye_teams_for(sched, 2026, 9), [])  # unknown week: no teams assumed on bye
        self.assertEqual(latest_week(self.rows('BAL', 3) + self.rows('BAL', 5), 2026), 5)

    def test_injury_text_retained_without_invented_body_regions(self):
        roster=[dict(season=2026,game_type='REG',week=2,gsis_id='p',team='BAL',status='ACT')]
        injury=dict(season=2026,season_type='REG',week=2,gsis_id='p',report_status='Questionable',report_primary_injury='Hamstring',practice_status='Limited')
        self.assertEqual(normalize(roster,[injury],2026)['players'][0]['injury']['primary_injury'],'Hamstring')
        rest=dict(injury,report_status=None,report_primary_injury='Not injury related - resting player',practice_status='Full')
        self.assertIsNone(normalize(roster,[rest],2026)['players'][0]['injury'])
