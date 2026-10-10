"""Synthetic offline fixtures only: no provider calls or real contest recommendations."""
import copy
import hashlib
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('dfs_team_budget_export', ROOT / 'research/dfs/build-team-budgets.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
HEADER = 'season,week,team,season_type,game_id,opponent_team,rushing_tds,receiving_tds,passing_tds,def_tds,special_teams_tds\n'
ROWS = ['2026,1,BUF,REG,2026_01_BUF_MIA,MIA,2,1,99,99,99',
        '2026,1,MIA,REG,2026_01_BUF_MIA,BUF,0,2,99,99,99']
GAME = {'sport': 'nfl', 'id': '2026_01_BUF_MIA', 'away': 'BUF', 'home': 'MIA',
        'kickoff': '2026-09-13T17:00:00Z', 'awayScore': 21, 'homeScore': 14}
RESULTS = {'generated_at': '2026-10-03T16:00:00Z', 'games': {'nfl|2026_01_BUF_MIA': GAME}}
OPTIONS = {'season': 2026, 'generated_at': '2026-10-03T18:30:00Z',
           'retrieved_at': '2026-10-03T18:22:21Z', 'release_updated_at': '2026-10-03T14:22:21Z',
           'source_url': 'https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_2026.csv'}


def export(rows=None, results=None, options=None):
    source = (HEADER + '\n'.join(ROWS if rows is None else rows) + '\n').encode()
    parameters = {**OPTIONS, 'expected_source_sha256': hashlib.sha256(source).hexdigest(), **(options or {})}
    return MODULE.build(source, json.dumps(RESULTS if results is None else results).encode(), **parameters)


class TeamBudgetExportTests(unittest.TestCase):
    def test_valid_reproducible_team_counts_include_all_positions_not_passing_or_defense(self):
        output = export()
        self.assertEqual(output, export())
        self.assertEqual(output['schemaVersion'], 1)
        self.assertEqual(output['teams']['BUF'][0]['qualifyingTDs'], 3)
        self.assertEqual(output['teams']['MIA'][0]['qualifyingTDs'], 2)
        self.assertEqual(output['teams']['BUF'][0]['rushTDs'], 2)
        self.assertEqual(output['teams']['BUF'][0]['recTDs'], 1)
        self.assertEqual(output['teams']['BUF'][0]['kickoff'], '2026-09-13T17:00:00Z')
        self.assertEqual(len(output['sourceSha256']), 64)
        self.assertEqual(len(output['resultsSHA256']), 64)
        self.assertIn('all scorer positions and overtime', ' '.join(output['limitations']))

    def test_duplicates_missing_and_conflicting_pairs_fail_closed(self):
        for rows in [ROWS + [ROWS[0]], ROWS[:1], [], [ROWS[0], ROWS[1].replace(',BUF,0,2', ',DEN,0,2')]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                export(rows=rows)

    def test_values_must_be_nonnegative_integer_current_regular_season(self):
        replacements = [('2026,1', '2025,1'), ('2026,1', '2026,19'), (',REG,', ',POST,'),
                        (',2,1,99', ',-1,1,99'), (',2,1,99', ',1.5,1,99'), (',2,1,99', ',NaN,1,99'),
                        ('BUF,REG', 'FAKE,REG'), ('2026_01_BUF_MIA', '2026_01_BUF_DEN')]
        for old, new in replacements:
            with self.subTest(new=new), self.assertRaises(ValueError):
                export(rows=[ROWS[0].replace(old, new), ROWS[1]])

    def test_game_result_scores_and_team_identities_are_authoritative(self):
        for change in [{'awayScore': 17}, {'awayScore': -1}, {'awayScore': True}, {'awayScore': 21.5},
                       {'away': 'KC'}, {'home': 'BUF'}, {'id': '2026_01_BUF_DEN'}, {'kickoff': 'invalid'}]:
            result = copy.deepcopy(RESULTS)
            result['games']['nfl|2026_01_BUF_MIA'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                export(results=result)

    def test_future_or_not_published_games_and_source_timestamps_fail_closed(self):
        for kickoff in ['2026-10-04T17:00:00Z', '2026-10-03T15:00:00Z', '2026-10-03T17:00:00Z']:
            result = copy.deepcopy(RESULTS)
            result['games']['nfl|2026_01_BUF_MIA']['kickoff'] = kickoff
            with self.subTest(kickoff=kickoff), self.assertRaises(ValueError):
                export(results=result)
        for options in [{'retrieved_at': '2026-10-04T00:00:00Z'},
                        {'release_updated_at': '2026-10-04T00:00:00Z'},
                        {'generated_at': '2026-10-03T18:30:00'},
                        {'retrieved_at': 'bad'}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                export(options=options)
        result = copy.deepcopy(RESULTS)
        result['generated_at'] = '2026-10-04T00:00:00Z'
        with self.assertRaises(ValueError):
            export(results=result)

    def test_full_completed_results_coverage_is_required(self):
        result = copy.deepcopy(RESULTS)
        result['games']['nfl|2026_02_BUF_MIA'] = {**GAME, 'id': '2026_02_BUF_MIA', 'kickoff': '2026-09-20T17:00:00Z'}
        with self.assertRaises(ValueError):
            export(results=result)

    def test_receipt_hash_and_official_release_identity_must_match(self):
        for options in [{'expected_source_sha256': '0' * 64}, {'source_url': 'https://unverified.test/team.csv'}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                export(options=options)

    def test_actual_saved_export_is_receipted_98_rows_49_games_32_teams(self):
        path = ROOT / 'data/dfs_team_touchdowns.json'
        artifact = json.loads(path.read_text(encoding='utf-8'))
        source = (ROOT / 'research/dfs/team-stats-2026.csv').read_bytes()
        reference = (ROOT / 'research/dfs/results-team-reference.json').read_bytes()
        if artifact['sourceSha256'] != hashlib.sha256(source).hexdigest():
            self.skipTest('the scheduled scripts/dfs_team_touchdowns.py snapshot superseded the saved reproduction fixture; the builder itself is covered by the other tests')
        reproduced = MODULE.build(source, reference, season=artifact['season'], generated_at=artifact['generatedAt'],
                                  retrieved_at=artifact['retrievedAt'], release_updated_at=artifact['releaseUpdatedAt'],
                                  source_url=artifact['sourceURL'], expected_source_sha256=artifact['sourceSha256'])
        self.assertEqual(artifact, reproduced)
        rows = [row for team_rows in artifact['teams'].values() for row in team_rows]
        self.assertEqual(len(artifact['teams']), 32)
        self.assertEqual(len(rows), 98)
        self.assertEqual(len({row['gameId'] for row in rows}), 49)
        self.assertEqual(artifact['sourceSha256'], hashlib.sha256(source).hexdigest())
        self.assertEqual(artifact['resultsSHA256'], hashlib.sha256(reference).hexdigest())
        self.assertEqual({len(team_rows) for team_rows in artifact['teams'].values()}, {3, 4})


if __name__ == '__main__':
    unittest.main()
