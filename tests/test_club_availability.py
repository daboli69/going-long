import io
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import availability_source as S
import espn_availability as ESPN
import nflmeta_source as N
import eligibility as E

NOW = datetime(2026, 10, 15, 22, 0, tzinfo=timezone.utc)
CHECKED = '2026-10-15T20:00:00Z'


def player(gid, team, name):
    return {'gsis_id': gid, 'espn_id': gid + '1', 'full_name': name, 'team': team, 'status': 'ACT',
            'position': 'WR', 'season': 2026, 'week': 6, 'game_type': 'REG'}


def club(team, ok=True, covered=True, checked=CHECKED):
    return {'report_kind': 'game_status', 'week': 6, 'team_abbr': team,
            'last_check_status': 'succeeded' if ok else 'failed',
            'coverage_status': 'complete' if covered else 'partial', 'last_checked_at': checked}


def weekly(reports, rows=()):
    return {'fetched_at': NOW.isoformat(), 'season': 2026, 'week': 6, 'rows': list(rows), 'availability_reports': reports}


def designation(team, name, status):
    return {'week': 6, 'season_year': 2026, 'season_type': 'REG', 'team_abbr': team, 'display_name': name, 'position': 'WR', 'game_status': status}


class PerClubTests(unittest.TestCase):
    def test_each_club_is_judged_alone_and_failures_never_clear_other_clubs(self):
        reports = [club('ATL'), club('HOU', ok=False), club('BUF', covered=False), club('DEN', checked='2026-10-10T00:00:00Z'), club('KC', checked='2026-10-16T09:00:00Z')]
        verified, unverified = N.verify_clubs(weekly(reports), 6, NOW)
        self.assertEqual(set(verified), {'ATL'})
        self.assertEqual(unverified, ['BUF', 'DEN', 'HOU', 'KC'])
        with self.assertRaises(RuntimeError):
            N.verify(weekly(reports), 6, NOW)   # the strict whole-league contract is unchanged
        self.assertEqual(N.verify_clubs(weekly([club('ATL'), club('ATL', ok=False)]), 6, NOW)[0], {})

    def load(self, reports, rows=(), espn_fails=True):
        import polars as pl
        buf = io.BytesIO()
        pl.DataFrame([{'season': 2026, 'season_type': 'REG', 'week': 6, 'gsis_id': 'zz', 'date_modified': None}], schema_overrides={'date_modified': pl.Utf8}).write_parquet(buf)
        response = mock.Mock(content=buf.getvalue(), headers={'Last-Modified': 'Thu, 15 Oct 2026 20:30:00 GMT'})
        roster = [player('a', 'ATL', 'Alpha Atl'), player('b', 'HOU', 'Bravo Hou'), player('c', 'ATL', 'Charlie Atl')]
        espn = mock.Mock(side_effect=RuntimeError('ESPN unavailable')) if espn_fails else mock.Mock(return_value=([], {'availability_verification': {'mode': 'explicit-player-reports', 'season': 2026, 'week': 6, 'players': {'b': {'team': 'HOU', 'reported_at': '2026-10-15T19:00:00Z'}}}, 'report_content_at': '2026-10-15T19:00:00Z', 'sha256': 'e' * 64}))
        with mock.patch.object(S.requests, 'get', return_value=response), \
                mock.patch.object(S.nflmeta_source, 'fetch_week', return_value=weekly(reports, rows)), \
                mock.patch.object(ESPN, 'fetch_explicit', espn):
            return S.load_source('injuries', 2026, NOW, roster)

    def test_verified_club_players_clear_and_unverified_club_players_stay_excluded(self):
        rows, meta = self.load([club('ATL'), club('HOU', ok=False)],
                               [designation('ATL', 'Charlie Atl', 'Out'), designation('HOU', 'Bravo Hou', 'Out')])
        scope = meta['availability_verification']
        self.assertEqual(scope['mode'], 'explicit-player-reports')
        self.assertEqual(set(scope['players']), {'a', 'c'})
        self.assertEqual(scope['players']['a'], {'team': 'ATL', 'reported_at': CHECKED})
        self.assertEqual(meta['nflmeta']['unverified_clubs'], ['HOU'])
        merged = {r['gsis_id']: r['report_status'] for r in rows if r.get('source') == 'nflmeta'}
        self.assertEqual(merged, {'c': 'Out'}, 'only the verified club contributes designations')

    def test_espn_adds_only_players_of_unverified_clubs_and_never_overrides_a_club_entry(self):
        _, meta = self.load([club('ATL'), club('HOU', ok=False)], espn_fails=False)
        self.assertEqual(set(meta['availability_verification']['players']), {'a', 'b', 'c'})
        self.assertEqual(meta['availability_verification']['players']['b']['team'], 'HOU')
        self.assertIn('ESPN', meta['provider'])

    def test_no_verified_club_and_no_espn_keeps_the_previous_snapshot(self):
        with self.assertRaises(RuntimeError):
            self.load([club('ATL', ok=False), club('HOU', ok=False)])

    def test_produced_scope_satisfies_the_existing_engine_contract(self):
        _, meta = self.load([club('ATL'), club('HOU', ok=False)])
        scope = meta['availability_verification']
        injury = {'season': 2026, 'week': 6, 'availability_verification': scope, 'source_content_at': None}
        roster = {'season': 2026, 'week': 6, 'availability_verification': scope, 'source_injury_at': None}
        accepted = E._verification(injury, roster)
        self.assertEqual(set(accepted), {'a', 'c'})
        self.assertTrue(E._verified_player('a', 'ATL', accepted, NOW))
        self.assertFalse(E._verified_player('b', 'HOU', accepted, NOW))


if __name__ == '__main__':
    unittest.main()
