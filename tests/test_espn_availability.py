import copy
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import espn_availability as ESPN
import eligibility as E

NOW = datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc)
AT = '2026-10-14T20:00:00Z'


def player(gid='a', eid='100', team='ATL', name='A Player'):
    return {'gsis_id': gid, 'espn_id': eid, 'full_name': name, 'team': team,
            'status': 'ACT', 'position': 'WR', 'season': 2026, 'week': 6, 'game_type': 'REG'}


def report(eid='100', status='Active', date='2026-10-14T20:00Z'):
    return {'status': status, 'date': date, 'athlete': {'displayName': 'A Player',
            'team': {'id': '1', 'abbreviation': 'ATL'},
            'links': [{'href': f'https://www.espn.com/nfl/player/_/id/{eid}/a-player'}]}}


def doc(rows=None):
    return {'timestamp': '2099-01-01T00:00:00Z', 'status': 'success',
            'season': {'year': 2026, 'type': 2}, 'injuries': [{'id': '1', 'injuries': rows or [report()]}]}


class ExplicitReportTests(unittest.TestCase):
    def test_single_dated_nflverse_row_without_full_coverage_still_uses_restricted_fallback(self):
        import availability_source as S
        import io
        import polars as pl
        buf = io.BytesIO()
        pl.DataFrame([{'season': 2026, 'season_type': 'REG', 'week': 6, 'gsis_id': 'a', 'date_modified': AT}]).write_parquet(buf)
        response = mock.Mock(content=buf.getvalue(), headers={'Last-Modified': 'Wed, 14 Oct 2026 20:00:00 GMT'})
        explicit = ESPN.merge_explicit(doc(), [player()], 2026, 6, NOW)
        with mock.patch.object(S.requests, 'get', return_value=response), mock.patch.object(S.nflmeta_source, 'fetch_week', return_value=None), mock.patch.object(ESPN, 'fetch_explicit', return_value=explicit) as fallback:
            _, metadata = S.load_source('injuries', 2026, NOW, [player()])
        fallback.assert_called_once()
        self.assertEqual(metadata['availability_verification']['mode'], 'explicit-player-reports')

    def test_exact_identity_and_real_report_clock_not_endpoint_timestamp(self):
        rows, meta = ESPN.merge_explicit(doc(), [player()], 2026, 6, NOW)
        self.assertEqual(rows[0]['date_modified'], AT)
        self.assertEqual(rows[0]['report_status'], 'active')
        self.assertEqual(meta['report_content_at'], AT)
        self.assertEqual(set(meta['availability_verification']['players']), {'a'})

    def test_capped_list_does_not_clear_unlisted_teammates(self):
        _, meta = ESPN.merge_explicit(doc(), [player(), player('b', '101', name='Other Player')], 2026, 6, NOW)
        self.assertNotIn('b', meta['availability_verification']['players'])

    def test_identity_disagreements_never_clear(self):
        bad_rows = [report(eid='101'), report()]
        bad_rows[1]['athlete']['displayName'] = 'Different Player'
        for row in bad_rows:
            with self.assertRaises(RuntimeError):
                ESPN.merge_explicit(doc([row]), [player()], 2026, 6, NOW)
        p = player(); p['team'] = 'BUF'
        with self.assertRaises(RuntimeError):
            ESPN.merge_explicit(doc(), [p], 2026, 6, NOW)
        with self.assertRaises(RuntimeError):
            ESPN.merge_explicit(doc(), [player(), player('different')], 2026, 6, NOW)

    def test_stale_missing_future_and_unsupported_reports_cannot_verify(self):
        for r in [report(date=None), report(date='2026-10-10T20:00Z'), report(date='2026-10-15T20:00Z'), report(status='Mystery')]:
            with self.assertRaises(RuntimeError):
                ESPN.merge_explicit(doc([r]), [player()], 2026, 6, NOW)

    def test_wrong_season_and_non_regular_feeds_fail_closed(self):
        for season in [{'year': 2025, 'type': 2}, {'year': 2026, 'type': 1}]:
            d = doc(); d['season'] = season
            with self.assertRaises(RuntimeError):
                ESPN.merge_explicit(d, [player()], 2026, 6, NOW)

    def test_latest_report_wins_old_out_not_resurrected(self):
        rows, _ = ESPN.merge_explicit(doc([report(status='Out', date='2026-10-13T20:00Z'), report()]), [player()], 2026, 6, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['report_status'], 'active')

    def test_old_severe_report_stays_an_exclusion_but_cannot_clear(self):
        old = report('101', 'Out', '2026-10-01T20:00Z')
        rows, meta = ESPN.merge_explicit(doc([report(), old]), [player(), player('b', '101')], 2026, 6, NOW)
        self.assertEqual(next(r for r in rows if r['gsis_id'] == 'b')['report_status'], 'Out')
        self.assertNotIn('b', meta['availability_verification']['players'])

    def test_same_time_contradiction_is_not_cleared(self):
        with self.assertRaises(RuntimeError):
            ESPN.merge_explicit(doc([report(), report(status='Out')]), [player()], 2026, 6, NOW)

    def test_foreign_or_conflicting_link_ids_not_trusted(self):
        for href in ['https://evil.example/nfl/player/_/id/100/a', 'https://www.espn.com/nba/player/_/id/100/a']:
            r = report(); r['athlete']['links'][0]['href'] = href
            with self.assertRaises(RuntimeError):
                ESPN.merge_explicit(doc([r]), [player()], 2026, 6, NOW)


def snapshots():
    rows = [dict(id=g, team='ATL', roster_status='ACT') for g in ['a', 'b', 'out', 'stale']]
    roster = {'season': 2026, 'week': 6, 'injury_week': 6, 'generated_at': AT,
              'source_roster_at': AT, 'source_injury_at': AT, 'players': rows}
    injury = {'season': 2026, 'generated_at': AT, 'source_content_at': AT, 'source_roster_at': AT,
              'current_players': {g: {'gsis_id': g, 'team': 'ATL', 'roster_status': 'ACT'} for g in ['a', 'b', 'out', 'stale']},
              'current_reports': {'out': {'gsis_id': 'out', 'report_status': 'Out', 'week': 6}}}
    scope = {'mode': 'explicit-player-reports', 'season': 2026, 'week': 6,
             'players': {g: {'team': 'ATL', 'reported_at': AT if g != 'stale' else '2026-10-10T20:00:00Z'} for g in ['a', 'out', 'stale']}}
    for d in (injury, roster):
        d['availability_verification'] = copy.deepcopy(scope)
    injury['restricted_source_content_at'] = injury.pop('source_content_at')
    roster['restricted_source_injury_at'] = roster.pop('source_injury_at')
    injury['source_content_at'] = roster['source_injury_at'] = None
    return injury, roster


class RestrictedEligibilityTests(unittest.TestCase):
    def test_producers_force_legacy_engines_to_stay_paused(self):
        import availability_source as S
        i, r = snapshots()
        for d, key in ((i, 'source_content_at'), (r, 'source_injury_at')):
            d[key] = d.pop('restricted_' + key)
            source = {'availability_verification': d.pop('availability_verification')}
            S.scoped_snapshot(d, source)
            self.assertIsNone(d[key])
            self.assertEqual(d['restricted_' + key], AT)
            self.assertEqual(d['schema_version'], 2)
        self.assertTrue(E.freshness(NOW, i, r)['ok'])

    def test_both_snapshot_builders_preserve_more_severe_current_week_source(self):
        import build_roster as R
        import injury_context as I
        base = {'season': 2026, 'season_type': 'REG', 'week': 6, 'gsis_id': 'a', 'full_name': 'A Player', 'team': 'ATL', 'position': 'WR', 'report_status': 'Out', 'date_modified': None}
        explicit, _ = ESPN.merge_explicit(doc(), [player()], 2026, 6, NOW)
        rows = [base] + explicit
        r = R.normalize([player()], rows, 2026)
        self.assertEqual(r['players'][0]['injury']['report_status'], 'Out')
        _, reports, _, _, _ = I.build_current(2026, rows, [], [player()], {}, [], [])
        self.assertEqual(next(iter(reports.values()))['report_status'], 'Out')

    def test_repeated_explicit_refresh_accepts_same_reports_but_rejects_rollback(self):
        import tempfile
        import availability_source as S
        i, _ = snapshots()
        i['restricted_source_content_at'] = '2026-10-14T12:00:00Z'
        i['current_reports'] = {'a': {'gsis_id': 'a', 'report_status': 'active', 'reported_at': AT}}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(S, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            path = Path(folder) / 'previous.json'; path.write_text(json.dumps(i))
            S.preserve_newer(path, copy.deepcopy(i))
            bad = copy.deepcopy(i); bad['current_reports']['a']['reported_at'] = '2026-10-14T19:00:00Z'
            with self.assertRaises(RuntimeError):
                S.preserve_newer(path, bad)

    def test_explicit_scope_and_adversarial_mutations_have_javascript_python_parity(self):
        cases = [snapshots()]
        for mutate in [lambda i, r: r.pop('availability_verification'),
                       lambda i, r: r['availability_verification'].update(week=5),
                       lambda i, r: i['availability_verification'].update(players={}),
                       lambda i, r: r['availability_verification'].update(extra=True),
                       lambda i, r: i['availability_verification']['players']['a'].update(reported_at='bad'),
                       lambda i, r: r['availability_verification']['players']['a'].update(team='BUF')]:
            i, r = snapshots(); mutate(i, r); cases.append((i, r))
        cases.append((None, snapshots()[1]))
        profiles = {g: {'team': 'ATL'} for g in ['a', 'b', 'out', 'stale', 'missing']}
        values = [{'injury': i, 'roster': r, 'profiles': profiles} for i, r in cases]
        expected = [{'fresh': E.freshness(NOW, i, r)['ok'], 'blocked': sorted(E.blocked_ids(profiles, i, r, NOW))} for i, r in cases]
        self.assertEqual(expected[0], {'fresh': True, 'blocked': ['b', 'missing', 'out', 'stale']})
        js = "const E=require('./shared/going-eligibility.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(c=>{const e=E.create({...c,now:Date.parse('2026-10-14T21:00:00Z')});return {fresh:e.fresh.ok,blocked:[...e.blockedIds(c.profiles)].sort()};}))));"
        got = subprocess.check_output(['node', '-e', js], input=json.dumps(values).encode(), cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(json.loads(got), expected)

    def test_existing_out_is_not_cleared_by_fresh_explicit_verification(self):
        i, r = snapshots()
        self.assertIn('out', E.blocked_ids({'out': {'team': 'ATL'}}, i, r, NOW))

    def test_allowlisted_report_expires_despite_fresh_snapshot_generation(self):
        i, r = snapshots()
        for d in (i, r):
            d['availability_verification']['players']['a']['reported_at'] = '2026-10-12T20:00:00Z'
        self.assertIn('a', E.blocked_ids({'a': {'team': 'ATL'}}, i, r, NOW))


if __name__ == '__main__':
    unittest.main()
