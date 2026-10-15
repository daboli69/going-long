import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from odds_history import Archive
import missions_history_export as export


def board(snapshot, books):
    return {'timestamp': snapshot, 'data': [{'id': 'ev', 'commence_time': '2025-10-12T17:00:00Z',
        'home_team': 'Kansas City Chiefs', 'away_team': 'Buffalo Bills', 'bookmakers': [
            {'key': key, 'last_update': snapshot, 'markets': [
                {'key': 'h2h', 'outcomes': [{'name': 'Kansas City Chiefs', 'price': h}, {'name': 'Buffalo Bills', 'price': a}]},
                {'key': 'spreads', 'outcomes': [{'name': 'Kansas City Chiefs', 'price': -110, 'point': -2.5}, {'name': 'Buffalo Bills', 'price': -110, 'point': 2.5}]},
                {'key': 'totals', 'outcomes': [{'name': 'Over', 'price': -110, 'point': 47.5}, {'name': 'Under', 'price': -110, 'point': 47.5}]},
                {'key': 'player_pass_yds', 'outcomes': [{'name': 'Over', 'description': 'QB', 'price': -110, 'point': 250.5}]}]}
            for key, (h, a) in books.items()]}]}


class MissionsHistoryExportTests(unittest.TestCase):
    def fixture(self, root, home_score=27, away_score=24, completed=True):
        for snapshot, books in [('2025-10-12T15:30:00Z', {'pinnacle': (-140, 120), 'draftkings': (-135, 115)}),
                                ('2025-10-12T16:30:00Z', {'pinnacle': (-150, 130), 'draftkings': (-145, 125), 'fanduel': (-148, 128)})]:
            body = board(snapshot, books)
            a = Archive(root, fetch=Mock(return_value=Mock(status_code=200, json=Mock(return_value=body), headers={
                'x-requests-last': '30', 'x-requests-used': '30', 'x-requests-remaining': '19970'})))
            a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': snapshot}, 30, 'provider-private')
        (Path(root) / 'plan.json').write_text(json.dumps({'cutoff': '2025-10-13T00:00:00Z'}))
        (Path(root) / 'schedule.json').write_text(json.dumps({'games': [
            {'game_id': '2025_06_BUF_KC', 'home': 'KC', 'away': 'BUF', 'season': 2025, 'completed': completed, 'kickoff': '2025-10-12T17:00:00Z'}]}))
        results = Path(root) / 'results.json'
        results.write_text(json.dumps({'games': [{'game_id': '2025_06_BUF_KC', 'completed': completed, 'home_score': home_score, 'away_score': away_score}]}))
        return results

    def test_outcomes_drop_pushes_and_follow_spread_and_total_signs(self):
        self.assertEqual(export.outcome('moneyline', 27, 24, 0), 1)
        self.assertIsNone(export.outcome('moneyline', 24, 24, 0))
        self.assertEqual(export.outcome('spread', 27, 24, -2.5), 1)   # KC -2.5 covers by 3
        self.assertEqual(export.outcome('spread', 27, 26, -2.5), 0)
        self.assertIsNone(export.outcome('spread', 27, 24, -3))
        self.assertEqual(export.outcome('total', 27, 24, 47.5), 1 if 51 > 47.5 else 0)
        self.assertEqual(export.outcome('total', 20, 24, 47.5), 0)

    def test_latest_pre_kickoff_board_only_paired_prices_and_no_props(self):
        with tempfile.TemporaryDirectory() as root:
            results = self.fixture(root)
            data = export.export(root, results)
            self.assertEqual({r['market'] for r in data['records']}, {'moneyline', 'spread', 'total'})
            ml = next(r for r in data['records'] if r['market'] == 'moneyline')
            self.assertEqual(ml['snapshotAt'], '2025-10-12T16:30:00+00:00')
            self.assertEqual(set(ml['quotes']), {'pinnacle', 'draftkings', 'fanduel'})
            self.assertEqual(ml['quotes']['pinnacle'], [-150, 130])
            self.assertEqual(ml['y'], 1)
            self.assertTrue(all(r['line'] in (None, -2.5, 47.5) for r in data['records']))
            self.assertNotIn('provider-private', json.dumps(data))

    def test_unscored_or_unverified_games_and_pushes_never_enter(self):
        with tempfile.TemporaryDirectory() as root:
            results = self.fixture(root, completed=False)
            self.assertEqual(export.export(root, results)['records'], [])
        with tempfile.TemporaryDirectory() as root:
            results = self.fixture(root, 24, 24)
            data = export.export(root, results)
            self.assertNotIn('moneyline', {r['market'] for r in data['records']})
            self.assertEqual(data['gaps']['push'] >= 1, True)

    def test_hypothetical_matchup_outside_actual_schedule_is_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            results = self.fixture(root)
            schedule = Path(root) / 'schedule.json'
            data = json.loads(schedule.read_text()); data['games'][0]['away'] = 'PHI'; schedule.write_text(json.dumps(data))
            self.assertEqual(export.export(root, results)['records'], [])


if __name__ == '__main__':
    unittest.main()
