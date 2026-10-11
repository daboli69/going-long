import copy
import csv
import io
import json
import unittest
from scripts import dfs_kickers as K


class KickerSnapshotTests(unittest.TestCase):
    def fixture(self):
        row = dict.fromkeys(K.FIELDS, '0')
        row.update(position='K', season='2026', week='1', game_id='2026_01_ATL_PIT', team='ATL', player_id='00-0025565', player_display_name='Nick Folk', fg_made_40_49='1', fg_made='1', fg_att='2', pat_made='2', pat_att='2')
        results = {'generated_at': '2026-10-11T20:00:00Z', 'sources': {'nfl': {'status': 'loaded', 'checked_at': '2026-10-11T19:59:00Z'}}, 'games': {'nfl|2026_01_ATL_PIT': {'sport': 'nfl', 'id': '2026_01_ATL_PIT', 'home': 'PIT', 'away': 'ATL', 'homeScore': 17, 'awayScore': 20, 'kickoff': '2026-09-13T17:00:00Z'}}}
        return row, results

    def build(self, rows, results):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        return K.build(stream.getvalue().encode(), json.dumps(results).encode(), season=2026, generated_at='2026-10-11T22:00:00Z', retrieved_at='2026-10-11T21:30:00Z', release_updated_at='2026-10-11T21:00:00Z')

    def test_actual_distance_counts_and_provenance(self):
        row, results = self.fixture()
        output = self.build([row], results)
        self.assertEqual(output['players']['00-0025565']['games'][0]['points'], 6)
        self.assertEqual(len(output['sourceSha256']), 64)
        self.assertEqual(len(output['resultsSHA256']), 64)
        self.assertEqual(output['season'], 2026)

    def test_counts_missing_negative_fraction_boolean_and_conflict_rejected(self):
        row, results = self.fixture()
        for key, bad in [('pat_made', ''), ('pat_made', '-1'), ('pat_made', '0.5'), ('pat_made', 'True'), ('fg_made', '0'), ('pat_att', '1')]:
            changed = dict(row)
            changed[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                self.build([changed], results)

    def test_duplicate_player_game_or_game_results_rejected(self):
        row, results = self.fixture()
        with self.assertRaises(ValueError):
            self.build([row, row], results)
        results['games']['duplicate'] = copy.deepcopy(next(iter(results['games'].values())))
        with self.assertRaises(ValueError):
            self.build([row], results)

    def test_exact_identity_and_week_required(self):
        row, results = self.fixture()
        for key, bad in [('team', 'BAL'), ('week', '2'), ('player_id', '123')]:
            changed = dict(row)
            changed[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.build([changed], results)

    def test_no_unmatched_nonfinal_or_prior_year_games(self):
        row, results = self.fixture()
        for mutate in [lambda r: r['games'].clear(), lambda r: next(iter(r['games'].values())).update(awayScore=None), lambda r: next(iter(r['games'].values())).update(kickoff='2026-10-11T21:30:00Z')]:
            r = copy.deepcopy(results)
            mutate(r)
            with self.assertRaises(ValueError):
                self.build([row], r)
        row['season'] = '2025'
        with self.assertRaises(ValueError):
            self.build([row], results)

    def test_kicker_points_cannot_exceed_team_final(self):
        row, results = self.fixture()
        next(iter(results['games'].values()))['awayScore'] = 1
        with self.assertRaises(ValueError):
            self.build([row], results)

    def test_timestamp_order_and_offset_required(self):
        for bad in ['2026-10-11T00:00:00', '2026-10-11T00:00:00+03:99', '2026-02-30T00:00:00Z', '2026-10-11T00:00:00+14:01']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                K.stamp(bad)
        row, results = self.fixture()
        with self.assertRaises(ValueError):
            K.build(b'', json.dumps(results).encode(), season=2026, generated_at='2026-10-11T22:00:00Z', retrieved_at='2026-10-11T21:00:00Z', release_updated_at='2026-10-12T00:00:00Z')

    def test_fresh_file_cannot_conceal_failed_or_stale_results_source(self):
        row, results = self.fixture()
        for changed in ['failed', 'stale']:
            r = copy.deepcopy(results)
            if changed == 'failed':
                r['sources']['nfl']['status'] = 'failed'
            else:
                r['sources']['nfl']['checked_at'] = '2026-10-01T00:00:00Z'
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.build([row], r)


if __name__ == '__main__':
    unittest.main()
