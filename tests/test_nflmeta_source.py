import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nflmeta_source as nm  # noqa: E402

NOW = datetime(2026, 10, 11, 2, 0, tzinfo=timezone.utc)
KEY = 'NFLMeta_test_key_never_logged'
TEAMS = ['ARI', 'ATL', 'BAL', 'BUF', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'LAC', 'LAR',
         'LV', 'MIA', 'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS']


def club_reports(checked='2026-10-11T01:34:28.208Z', status='succeeded', coverage='complete', teams=TEAMS, week=5):
    return [{'team_abbr': t, 'week': week, 'report_kind': 'game_status', 'coverage_status': coverage,
             'last_checked_at': checked, 'last_check_status': status} for t in teams]


def meta_row(name, team, status, game_status=None, position='RB', week=5):
    return {'season_year': 2026, 'week': week, 'season_type': 'REG', 'team_abbr': team, 'display_name': name,
            'position': position, 'report_status': status, 'game_status': game_status or status,
            'practice_status': 'Did Not Participate In Practice', 'report_primary_injury': 'Hamstring'}


def roster(gsis, name, team, position='RB'):
    return {'season': 2026, 'week': 5, 'gsis_id': gsis, 'full_name': name, 'team': team, 'position': position, 'status': 'ACT'}


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class Session:
    def __init__(self, pages, status=200):
        self.pages, self.status, self.calls = pages, status, []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({'url': url, 'params': dict(params), 'headers': dict(headers)})
        return Response(self.pages[len(self.calls) - 1], self.status)


def page(rows, has_more=False, total=None, week=5):
    return {'data': rows, 'meta': {'season_year': 2026, 'week': week, 'has_more': has_more, 'total': total,
                                   'availability_reports': club_reports()}}


class MergeTests(unittest.TestCase):
    def test_out_designation_matches_exact_roster_identity_with_aliases_and_suffixes(self):
        rows, stats = nm.merge([], [roster('00-1', 'Kyren Williams', 'LA'), roster('00-2', 'Marvin Harrison Jr.', 'ARI', 'WR')],
                               {'rows': [meta_row('Kyren Williams', 'LAR', 'Out'), meta_row('Marvin Harrison', 'ARI', 'Questionable', position='WR')]},
                               2026, 5, '2026-10-11T01:34:28+00:00')
        by = {r['gsis_id']: r for r in rows}
        self.assertEqual(by['00-1']['report_status'], 'Out')
        self.assertEqual(by['00-1']['team'], 'LA')
        self.assertEqual(by['00-1']['full_name'], 'Kyren Williams')
        self.assertEqual(by['00-1']['date_modified'], '2026-10-11T01:34:28+00:00')
        self.assertEqual(by['00-2']['report_status'], 'Questionable')
        self.assertEqual(stats['matched'], 2)

    def test_confirmed_inactive_becomes_blocking_status(self):
        rows, _ = nm.merge([], [roster('00-1', 'A Player', 'DAL')], {'rows': [meta_row('A Player', 'DAL', None, 'Inactive')]}, 2026, 5, 'T')
        self.assertEqual(rows[0]['report_status'], 'Inactive')
        self.assertEqual(nm.severity('Inactive'), 4)

    def test_practice_only_rows_never_clear_or_add_anyone(self):
        rows, stats = nm.merge([], [roster('00-1', 'A Player', 'DAL')], {'rows': [meta_row('A Player', 'DAL', None)]}, 2026, 5, 'T')
        self.assertEqual(rows, [])
        self.assertEqual(stats['designations'], 0)

    def test_ambiguous_names_fail_closed_for_every_candidate(self):
        rows, stats = nm.merge([], [roster('00-1', 'Josh Smith', 'NYJ', 'WR'), roster('00-2', 'Josh Smith', 'NYJ', 'WR')],
                               {'rows': [meta_row('Josh Smith', 'NYJ', 'Out', position='WR')]}, 2026, 5, 'T')
        self.assertEqual({r['gsis_id'] for r in rows}, {'00-1', '00-2'})
        self.assertEqual(stats['ambiguous'], 1)

    def test_position_narrows_same_name_on_one_team(self):
        rows, _ = nm.merge([], [roster('00-1', 'Josh Smith', 'NYJ', 'WR'), roster('00-2', 'Josh Smith', 'NYJ', 'LB')],
                           {'rows': [meta_row('Josh Smith', 'NYJ', 'Out', position='LB')]}, 2026, 5, 'T')
        self.assertEqual([r['gsis_id'] for r in rows], ['00-2'])

    def test_nickname_falls_back_to_same_club_surname_and_position(self):
        rows, stats = nm.merge([], [roster('00-1', 'Josh Palmer', 'BUF', 'WR'), roster('00-2', 'Ty Palmer', 'BUF', 'LB'), roster('00-3', 'Al Palmer', 'NE', 'WR')],
                               {'rows': [meta_row('Joshua Palmer', 'BUF', 'Out', position='WR')]}, 2026, 5, 'T')
        self.assertEqual([r['gsis_id'] for r in rows], ['00-1'])
        self.assertEqual(stats['surname_fallback'], 1)
        rows, _ = nm.merge([], [roster('00-4', 'Rob Beal Jr.', 'MIA', 'DL')], {'rows': [meta_row('Robert Beal Jr.', 'MIA', 'Out', position='EDGE')]}, 2026, 5, 'T')
        self.assertEqual([r['gsis_id'] for r in rows], ['00-4'])

    def test_team_scoping_prevents_cross_team_joins(self):
        rows, stats = nm.merge([], [roster('00-1', 'Josh Allen', 'BUF', 'QB')], {'rows': [meta_row('Josh Allen', 'JAX', 'Out', position='LB')]}, 2026, 5, 'T')
        self.assertEqual(rows, [])
        self.assertEqual(stats['unresolved'], 1)

    def test_less_severe_status_never_downgrades_nflverse_designation(self):
        nflverse = [{'season': 2026, 'season_type': 'REG', 'week': 5, 'gsis_id': '00-1', 'full_name': 'A Player', 'team': 'PHI', 'report_status': 'Out'}]
        rows, stats = nm.merge(nflverse, [roster('00-1', 'A Player', 'PHI')], {'rows': [meta_row('A Player', 'PHI', 'Questionable')]}, 2026, 5, 'T')
        self.assertEqual(rows, nflverse)
        self.assertEqual(stats['kept_more_severe'], 1)

    def test_other_week_rows_ignored(self):
        rows, _ = nm.merge([], [roster('00-1', 'A Player', 'PHI')], {'rows': [meta_row('A Player', 'PHI', 'Out', week=4)]}, 2026, 5, 'T')
        self.assertEqual(rows, [])


class VerifyTests(unittest.TestCase):
    def test_recent_successful_club_reports_verify_with_oldest_clock(self):
        reports = club_reports()
        reports[0]['last_checked_at'] = '2026-10-10T20:00:00Z'
        result = nm.verify({'availability_reports': reports}, 5, NOW)
        self.assertEqual(result['clubs'], 30)
        self.assertEqual(result['verified_at'], '2026-10-10T20:00:00+00:00')

    def test_stale_failed_unknown_partial_coverage_and_few_clubs(self):
        with self.assertRaises(RuntimeError):
            nm.verify({'availability_reports': club_reports(checked='2026-10-09T10:00:00Z')}, 5, NOW)
        with self.assertRaises(RuntimeError):
            nm.verify({'availability_reports': club_reports(status='unknown')}, 5, NOW)
        with self.assertRaises(RuntimeError):
            nm.verify({'availability_reports': club_reports(coverage='unpublished')}, 5, NOW)
        with self.assertRaises(RuntimeError):
            nm.verify({'availability_reports': club_reports(teams=TEAMS[:10])}, 5, NOW)
        with self.assertRaises(RuntimeError):
            nm.verify({'availability_reports': club_reports(checked='2026-10-11T09:00:00Z')}, 5, NOW)
        with self.assertRaises(RuntimeError):
            nm.verify({'availability_reports': club_reports(checked='2026-10-11 01:00:00')}, 5, NOW)
        with self.assertRaises(RuntimeError):
            nm.verify({'availability_reports': club_reports(week=4)}, 5, NOW)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def test_no_key_means_no_request(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(nm.fetch_week(2026, 5, NOW, session=Session([]), cache_dir=self.dir.name))

    def test_paginates_caches_and_never_writes_key(self):
        session = Session([page([meta_row('A', 'PHI', 'Out')] * 100, True, 101), page([meta_row('B', 'PHI', 'Out')], False, 101)])
        with mock.patch.dict(os.environ, {'NFLMETA_API_KEY': KEY}):
            doc = nm.fetch_week(2026, 5, NOW, session=session, cache_dir=self.dir.name)
            again = nm.fetch_week(2026, 5, NOW + timedelta(minutes=10), session=Session([]), cache_dir=self.dir.name)
        self.assertEqual(len(doc['rows']), 101)
        self.assertEqual([c['params']['offset'] for c in session.calls], [0, 100])
        self.assertEqual(session.calls[0]['headers']['X-NFLMeta-Key'], KEY)
        self.assertEqual(len(again['rows']), 101)
        for path in Path(self.dir.name).iterdir():
            self.assertNotIn(KEY, path.read_text(encoding='utf-8'))

    def test_expired_cache_refetches(self):
        with mock.patch.dict(os.environ, {'NFLMETA_API_KEY': KEY}):
            nm.fetch_week(2026, 5, NOW, session=Session([page([])]), cache_dir=self.dir.name)
            session = Session([page([meta_row('A', 'PHI', 'Out')])])
            doc = nm.fetch_week(2026, 5, NOW + timedelta(minutes=45), session=session, cache_dir=self.dir.name)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(len(doc['rows']), 1)

    def test_http_errors_incomplete_and_wrong_week_raise_without_key(self):
        cases = [Session([page([])], status=429), Session([page([], total=5)]), Session([page([], week=4)]),
                 Session([{'data': None, 'meta': {}}]), Session([page([], True, 9), page([], True, 9)])]
        with mock.patch.dict(os.environ, {'NFLMETA_API_KEY': KEY}):
            for session in cases:
                with self.assertRaises(RuntimeError) as caught:
                    nm.fetch_week(2026, 5, NOW, session=session, cache_dir=tempfile.mkdtemp(dir=self.dir.name))
                self.assertNotIn(KEY, str(caught.exception))


class LoadSourceTests(unittest.TestCase):
    """The availability source needs NFLMeta verification when nflverse rows are undated."""

    def run_load(self, weekly, verify_error=None):
        import io
        import polars as pl
        import availability_source as av
        rows = [{'season': 2026, 'season_type': 'REG', 'week': 5, 'gsis_id': '00-1', 'full_name': 'A Player', 'team': 'PHI',
                 'report_status': None, 'practice_status': 'Did Not Participate In Practice', 'date_modified': None}]
        content = io.BytesIO(); pl.DataFrame(rows).write_parquet(content)
        response = mock.Mock(content=content.getvalue(), headers={'Last-Modified': 'Sat, 10 Oct 2026 13:33:06 GMT'})
        response.raise_for_status = lambda: None
        verify = mock.Mock(side_effect=verify_error) if verify_error else mock.Mock(return_value={'verified_at': '2026-10-11T01:34:28+00:00', 'clubs': 30})
        with mock.patch.object(av.requests, 'get', return_value=response), \
             mock.patch.object(av.nflmeta_source, 'fetch_week', return_value=weekly), \
             mock.patch.object(av.nflmeta_source, 'verify', verify):
            return av.load_source('injuries', 2026, NOW, roster=[roster('00-1', 'A Player', 'PHI')])

    def test_verified_designations_supply_dated_content(self):
        rows, meta = self.run_load({'rows': [meta_row('A Player', 'PHI', 'Out')]})
        self.assertEqual([r['report_status'] for r in rows if r.get('source') == 'nflmeta'], ['Out'])
        self.assertEqual(meta['content_at'], '2026-10-10T13:33:06+00:00')
        self.assertEqual(meta['nflmeta']['verified_at'], '2026-10-11T01:34:28+00:00')
        self.assertEqual(meta['nflmeta']['appended'], 1)
        # No merged report may be newer than the snapshot content clock (repeat refreshes must publish).
        self.assertTrue(all(r['date_modified'] <= meta['content_at'] for r in rows if r.get('source') == 'nflmeta'))

    def test_repeat_refresh_is_not_blocked_by_its_own_previous_reports(self):
        import availability_source as av
        rows, meta = self.run_load({'rows': [meta_row('A Player', 'PHI', 'Out')]})
        previous = {'source_content_at': meta['content_at'], 'source_roster_at': meta['content_at'],
                    'sources': {'injuries': dict(meta)}, 'current_reports': {'PHI|aplayer': {'reported_at': av.source_stamp(rows[-1]['date_modified'])}}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'injury_context.json'; path.write_text(json.dumps(previous), encoding='utf-8')
            payload = {'source_content_at': meta['content_at'], 'source_roster_at': meta['content_at'], 'sources': {'injuries': dict(meta)}}
            with mock.patch.object(av, 'datetime', wraps=datetime) as clock:
                clock.now.return_value = NOW
                av.preserve_newer(path, payload)

    def test_missing_key_or_failed_verification_keeps_gate_closed(self):
        with self.assertRaises(RuntimeError):
            self.run_load(None)
        with self.assertRaises(RuntimeError):
            self.run_load({'rows': [meta_row('A Player', 'PHI', 'Out')]}, verify_error=RuntimeError('stale'))


if __name__ == '__main__':
    unittest.main()
