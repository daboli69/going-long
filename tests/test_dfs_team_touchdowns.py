"""Synthetic offline fixtures only: no network, no provider calls."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('dfs_team_touchdowns', ROOT / 'scripts' / 'dfs_team_touchdowns.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HEADER = 'season,week,team,season_type,game_id,opponent_team,rushing_tds,receiving_tds,passing_tds,def_tds,special_teams_tds\n'
ROWS = ['2026,1,BUF,REG,2026_01_BUF_MIA,MIA,2,1,99,99,99',
        '2026,1,MIA,REG,2026_01_BUF_MIA,BUF,0,2,99,99,99',
        # a game the results snapshot does not list yet (finished after the release)
        '2026,2,BUF,REG,2026_02_BUF_NYJ,NYJ,1,0,9,9,9',
        '2026,2,NYJ,REG,2026_02_BUF_NYJ,BUF,0,0,9,9,9']
CSV = (HEADER + '\n'.join(ROWS) + '\n').encode()
GAME = {'sport': 'nfl', 'id': '2026_01_BUF_MIA', 'away': 'BUF', 'home': 'MIA', 'kickoff': '2026-09-13T17:00:00+00:00', 'awayScore': 21, 'homeScore': 14}
LATE = {'sport': 'nfl', 'id': '2026_02_BUF_NYJ', 'away': 'BUF', 'home': 'NYJ', 'kickoff': '2026-09-20T17:00:00+00:00', 'awayScore': 10, 'homeScore': 3}
RESULTS = {'generated_at': '2026-10-03T16:00:00Z', 'games': {'nfl|2026_01_BUF_MIA': GAME}}
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


class TeamTouchdownRefreshTests(unittest.TestCase):
    def test_builds_from_games_present_in_both_sources_and_records_dropped_rows(self):
        out = MODULE.refresh(CSV, RESULTS, season=2026, now=NOW, retrieved_at=NOW, release_updated_at='2026-10-04T08:00:00Z')
        self.assertEqual(sorted(out['teams']), ['BUF', 'MIA'])
        self.assertEqual(out['droppedRows'], 2)
        self.assertEqual(out['generatedAt'], '2026-10-04T12:00:00Z')
        self.assertEqual(out['releaseUpdatedAt'], '2026-10-04T08:00:00Z')
        self.assertEqual(out['teams']['BUF'][0]['qualifyingTDs'], 3)  # rushing + receiving only; passing/def/ST columns are never added
        self.assertNotEqual(out['downloadedSourceSha256'], out['sourceSha256'])

    def test_game_that_kicked_off_after_the_release_is_not_used(self):
        results = {**RESULTS, 'games': {**RESULTS['games'], 'nfl|2026_02_BUF_NYJ': LATE}}
        out = MODULE.refresh(CSV, results, season=2026, now=NOW, retrieved_at=NOW, release_updated_at='2026-09-19T00:00:00Z')
        self.assertEqual(sorted(out['teams']), ['BUF', 'MIA'])
        self.assertEqual({row['gameId'] for rows in out['teams'].values() for row in rows}, {'2026_01_BUF_MIA'})

    def test_refuses_when_no_games_overlap(self):
        with self.assertRaises(ValueError):
            MODULE.refresh(CSV, {'generated_at': '2026-10-03T16:00:00Z', 'games': {}}, season=2026, now=NOW, retrieved_at=NOW, release_updated_at='2026-10-04T08:00:00Z')

    def test_scores_bound_the_counts(self):
        bad = (HEADER + '2026,1,BUF,REG,2026_01_BUF_MIA,MIA,9,0,0,0,0\n2026,1,MIA,REG,2026_01_BUF_MIA,BUF,0,0,0,0,0\n').encode()
        with self.assertRaises(ValueError):
            MODULE.refresh(bad, RESULTS, season=2026, now=NOW, retrieved_at=NOW, release_updated_at='2026-10-04T08:00:00Z')

    def test_main_keeps_the_old_snapshot_when_the_download_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / 'snapshot.json'
            target.write_text('{"old":true}', encoding='utf-8')
            results = pathlib.Path(folder) / 'results.json'
            results.write_text(json.dumps(RESULTS), encoding='utf-8')
            with mock.patch.object(MODULE, 'release_updated_at', side_effect=OSError('offline')):
                code = MODULE.main(['--results', str(results), '--output', str(target), '--season', '2026'])
            self.assertEqual(code, 1)
            self.assertEqual(target.read_text(encoding='utf-8'), '{"old":true}')

    def test_main_writes_atomically_on_success(self):
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / 'snapshot.json'
            results = pathlib.Path(folder) / 'results.json'
            results.write_text(json.dumps(RESULTS), encoding='utf-8')
            with mock.patch.object(MODULE, 'release_updated_at', return_value='2026-10-04T08:00:00Z'), mock.patch.object(MODULE, '_get', return_value=CSV):
                code = MODULE.main(['--results', str(results), '--output', str(target), '--season', '2026'])
            self.assertEqual(code, 0)
            written = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(written['schemaVersion'], 1)
            self.assertEqual(sorted(written['teams']), ['BUF', 'MIA'])
            self.assertEqual([p.name for p in pathlib.Path(folder).glob('*.tmp')], [])


if __name__ == '__main__':
    unittest.main()
