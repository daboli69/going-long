"""Tests for scripts/charts_build.py with synthetic data only (no network, no licensed data)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import charts_build as cb  # noqa: E402

FLAGS = {'predictive', 'descriptive'}


def ep_rows(player, pos, team, weeks, exp, act, season=2026):
    return [{'season': str(season), 'week': float(w), 'player_id': player, 'full_name': player.upper(), 'position': pos, 'posteam': team,
             'total_fantasy_points_exp': e, 'total_fantasy_points': a} for w, e, a in zip(weeks, exp, act)]


class OpportunityTests(unittest.TestCase):
    def test_sums_residual_trend_and_filters(self):
        rows = (ep_rows('a', 'WR', 'AAA', [1, 2, 3, 4], [10, 12, 14, 16], [10, 20, 14, 10])      # exp 52, act 54
                + ep_rows('b', 'WR', 'BBB', [1, 2], [0.5, 1.0], [30, 30])                        # below the expected-volume floor
                + ep_rows('c', 'K', 'CCC', [1, 2], [9, 9], [9, 9])                               # not a skill position
                + ep_rows('d', 'RB', 'DDD', [1], [12], [12], season=2025))                       # other season
        out = cb.build_opportunity(pd.DataFrame(rows), 2026)
        players = {p['id']: p for p in out['data']['players']}
        self.assertEqual(set(players), {'a'})
        a = players['a']
        self.assertEqual((a['g'], a['exp'], a['act'], a['res']), (4, 52.0, 54.0, 2.0))
        self.assertEqual(a['trend3']['games'], [[2, 12.0, 20.0], [3, 14.0, 14.0], [4, 16.0, 10.0]])
        self.assertAlmostEqual(a['trend3']['res_pg'], (8 + 0 - 6) / 3, places=2)
        self.assertEqual(a['trend3']['prior_res_pg'], 0.0)
        self.assertEqual(out['as_of'], {'season': 2026, 'through_week': 4})

    def test_flags_are_valid_and_residual_is_not_predictive(self):
        out = cb.build_opportunity(pd.DataFrame(ep_rows('a', 'RB', 'AAA', [1, 2], [10, 10], [5, 15])), 2026)
        self.assertTrue(set(out['method_flags'].values()) <= FLAGS)
        self.assertEqual(out['method_flags']['res'], 'descriptive')

    def test_no_rows_is_unknown_not_empty_file(self):
        self.assertIsNone(cb.build_opportunity(pd.DataFrame(ep_rows('a', 'RB', 'AAA', [1], [10], [10], season=2025)), 2026))


class RolesTests(unittest.TestCase):
    def test_shares_and_missing_weeks(self):
        def wk(pid, team, week, pos, tgt, car, name=None):
            return {'player_id': pid, 'player_display_name': name or pid, 'position': pos, 'team': team, 'season': 2026, 'week': week, 'season_type': 'REG',
                    'targets': tgt, 'carries': car}
        weekly = pd.DataFrame([wk('wr1', 'AAA', 1, 'WR', 6, 0), wk('wr2', 'AAA', 1, 'WR', 4, 0), wk('rb1', 'AAA', 1, 'RB', 0, 10),
                               wk('wr1', 'AAA', 3, 'WR', 5, 0), wk('wr2', 'AAA', 3, 'WR', 5, 0), wk('rb1', 'AAA', 3, 'RB', 0, 10),
                               wk('ghost', 'AAA', 3, 'WR', 0, 0)])
        snaps = pd.DataFrame([{'season': 2026, 'game_type': 'REG', 'week': 1, 'pfr_player_id': 'P1', 'offense_pct': 0.9},
                              {'season': 2026, 'game_type': 'REG', 'week': 3, 'pfr_player_id': 'P1', 'offense_pct': 0.8}])
        out = cb.build_weekly_roles(weekly, snaps, {'P1': 'wr1'}, 2026)
        self.assertEqual(out['data']['weeks'], [1, 3])
        by = {p['id']: p for p in out['data']['players']}
        self.assertNotIn('ghost', by)
        self.assertEqual(by['wr1']['tgt'], [0.6, 0.5])
        self.assertEqual(by['wr1']['snap'], [0.9, 0.8])
        self.assertEqual(by['wr2']['snap'], [None, None])          # unknown, not zero
        self.assertEqual(by['rb1']['car'], [1.0, 1.0])
        self.assertIn('routes', out['unavailable_fields'])

    def test_only_last_n_weeks(self):
        weekly = pd.DataFrame([{'player_id': 'x', 'player_display_name': 'x', 'position': 'WR', 'team': 'AAA', 'season': 2026, 'week': w, 'season_type': 'REG',
                                'targets': 5, 'carries': 0} for w in range(1, 13)])
        snaps = pd.DataFrame(columns=['season', 'game_type', 'week', 'pfr_player_id', 'offense_pct'])
        out = cb.build_weekly_roles(weekly, snaps, {}, 2026, n_weeks=8)
        self.assertEqual(out['data']['weeks'], list(range(5, 13)))


class ScoringTests(unittest.TestCase):
    def profile(self, pid, **kw):
        sr = {'as_of': '2026-10-04', 'n': 12, 'confidence': 'ok', 'tier': 'PRIMARY', 'xtd_pg_l12': 0.5, 'td_pg_l12': 0.75, 'td_luck_l12': 0.25, 'xtd_pg_l6': 0.6,
              'xtd_share_l6': 0.4, 'rz_tgt_pg_l12': 1.0, 'inside5_touch_pg_l12': 0.8, 'gl_carry_pg_l12': 0.3, 'trend': {'d_xtd36': 0.1}}
        sr.update(kw.pop('sr', {}))
        return dict({'id': pid, 'name': pid, 'team': 'AAA', 'position': 'RB', 'last_game': '2026-10-04', 'scoring_role': sr}, **kw)

    def test_filters_and_fields(self):
        history = {'betting': {'profiles': {
            'a': self.profile('a'), 'low': self.profile('low', sr={'confidence': 'low'}), 'old': self.profile('old', last_game='2025-12-28'),
            'k': self.profile('k', position='K'), 'none': {'id': 'none', 'position': 'WR', 'last_game': '2026-10-01'}}}}
        out = cb.build_scoring_opportunity(history, 2026)
        rows = out['data']['players']
        self.assertEqual([x['id'] for x in rows], ['a'])
        self.assertEqual((rows[0]['xtd_pg'], rows[0]['td_pg'], rows[0]['td_luck'], rows[0]['in5_pg']), (0.5, 0.75, 0.25, 0.8))
        self.assertIn('inside_10', out['unavailable_fields'])
        self.assertTrue(set(out['method_flags'].values()) <= FLAGS)

    def test_empty_is_none(self):
        self.assertIsNone(cb.build_scoring_opportunity({'betting': {'profiles': {}}}, 2026))


class TeamTrendTests(unittest.TestCase):
    def test_pass_rate_over_expectation(self):
        def play(week, team, kind, xp, down=1, wp=0.5, hsr=1000, gid=None):
            return {'game_id': gid or f'g{week}{team}', 'season': 2026, 'week': week, 'season_type': 'REG', 'posteam': team, 'play_type': kind, 'down': down, 'wp': wp,
                    'half_seconds_remaining': hsr, 'xpass': xp}
        rows = [play(1, 'AAA', 'pass', 0.5), play(1, 'AAA', 'pass', 0.5), play(1, 'AAA', 'run', 0.5), play(1, 'AAA', 'run', 0.5, wp=0.95),  # last one not neutral
                play(1, 'AAA', 'no_play', 0.5), play(1, 'AAA', 'kickoff', None)]
        out = cb.build_team_trends(pd.DataFrame(rows), 2026)
        t = out['data']['teams']['AAA']
        self.assertEqual(t['plays'], [4.0])
        self.assertEqual(t['pass_rate'], [0.5])
        self.assertEqual(t['proe'], [0.0])
        self.assertAlmostEqual(t['proe_neutral'][0], (2 / 3 - 0.5) * 100, places=1)
        self.assertEqual(t['neutral_plays'], [3.0])
        self.assertEqual(t['season']['plays_pg'], 4.0)


def prediction(pid, contract, prob, status, market='player_receptions', group='best_model', observed='2026-09-20T10:00:00Z', kickoff='2026-09-20T17:00:00Z', push=0,
               settled='2026-09-21T01:00:00Z', player='SECRET NAME'):
    recs = [{'id': pid, 'kind': 'prediction', 'observed_at': observed,
             'payload': {'id': pid, 'tracking_group': group, 'canonical_contract': contract, 'market': market, 'probability': prob, 'player': player,
                         'observed_at': observed, 'kickoff': kickoff, 'model_evidence': {'push': push}}}]
    if status:
        recs.append({'id': 's' + pid, 'kind': 'settlement', 'observed_at': settled, 'payload': {'prediction_id': pid, 'status': status, 'observed_at': settled}})
    return recs


class CalibrationTests(unittest.TestCase):
    def test_first_observation_dedupe_and_exclusions(self):
        recs = []
        recs += prediction('1', 'c1', 0.8, 'win')
        recs += prediction('1b', 'c1', 0.2, 'win', observed='2026-09-20T12:00:00Z')              # later look at the same contract: ignored
        recs += prediction('2', 'c2', 0.4, 'loss')
        recs += prediction('3', 'c3', 0.9, 'refund')                                              # refund is not a win/loss
        recs += prediction('4', 'c4', 0.9, None)                                                  # unsettled
        recs += prediction('5', 'c5', 0.9, 'win', observed='2026-09-20T18:00:00Z')               # observed after kickoff: not a forecast
        recs += prediction('6', 'c1', 0.7, 'win', group='all_projection')                         # other group, same contract
        items, latest = cb.settled_items(recs)
        self.assertEqual(sorted((i['contract'].strip('"'), i['group']) for i in items), [('c1', 'all_projection'), ('c1', 'best_model'), ('c2', 'best_model')])
        out = cb.build_calibration(recs)
        self.assertEqual(out['data']['overall']['n'], 2)                                         # contract counted once overall
        self.assertEqual(out['data']['groups']['best_model']['n'], 2)
        self.assertAlmostEqual(out['data']['overall']['brier'], ((0.8 - 1) ** 2 + (0.4 - 0) ** 2) / 2, places=4)

    def test_push_conditioning_and_bins(self):
        recs = prediction('1', 'c1', 0.45, 'win', push=0.1) + prediction('2', 'c2', 0.5, 'loss')
        rel = cb.reliability([(i['p'], i['y']) for i in cb.settled_items(recs)[0]])
        self.assertAlmostEqual(sorted(b['mean_p'] for b in rel['bins'])[0], 0.5, places=3)
        self.assertEqual(rel['n'], 2)
        self.assertTrue(rel['low_n'])
        self.assertEqual(cb.reliability([]), None)

    def test_output_is_aggregate_only(self):
        recs = prediction('1', 'c1', 0.8, 'win') + prediction('2', 'c2', 0.3, 'loss')
        text = json.dumps(cb.build_calibration(recs))
        self.assertNotIn('SECRET NAME', text)
        self.assertNotIn('c1', text)

    def test_no_settlements_is_none(self):
        self.assertIsNone(cb.build_calibration(prediction('1', 'c1', 0.8, None)))


class WriteTests(unittest.TestCase):
    def payload(self, value=1):
        return cb.envelope('x', as_of={'season': 2026}, sources=[cb.src('s', 'nflverse')], method_flags={'a': 'descriptive'}, fields={}, notes=[], data={'v': value})

    def test_generated_at_is_stable_when_content_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            cb.write_chart(d, 'x', self.payload(1), '2026-01-01T00:00:00Z')
            cb.write_chart(d, 'x', self.payload(1), '2026-02-02T00:00:00Z')
            self.assertEqual(json.loads((Path(d) / 'x.json').read_text())['generated_at'], '2026-01-01T00:00:00Z')
            cb.write_chart(d, 'x', self.payload(2), '2026-03-03T00:00:00Z')
            self.assertEqual(json.loads((Path(d) / 'x.json').read_text())['generated_at'], '2026-03-03T00:00:00Z')

    def test_size_budget_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                cb.write_chart(d, 'big', self.payload('x' * (cb.MAX_BYTES + 10)), 'now')
            self.assertFalse((Path(d) / 'big.json').exists())

    def test_fit_budget_trims_lowest_ranked_rows(self):
        rows = [{'i': i, 'pad': 'x' * 1000} for i in range(1000)]
        out = cb.fit_budget(lambda rs: {'data': rs}, rows, 'data')
        kept = out['data']
        self.assertTrue(0 < len(kept) < 1000)
        self.assertEqual([r['i'] for r in kept], list(range(len(kept))))
        self.assertLessEqual(len(json.dumps(out, separators=(',', ':')).encode()), cb.MAX_BYTES)

    def test_helpers_never_turn_unknown_into_zero(self):
        self.assertIsNone(cb.r(None))
        self.assertIsNone(cb.r(float('nan')))
        self.assertEqual(cb.r(0), 0.0)


class PublishedFileTests(unittest.TestCase):
    def test_source_does_not_touch_licensed_data(self):
        text = (ROOT / 'scripts' / 'charts_build.py').read_text(encoding='utf-8').lower()
        for needle in ('fp_ingest', 'fantasypoints', 'fantasy_points.py', 'private/'):
            self.assertNotIn(needle, text.replace('ffopportunity weekly expected fantasy points', ''), needle)

    def test_committed_charts_meet_contract(self):
        directory = ROOT / 'data' / 'charts'
        files = sorted(p for p in directory.glob('*.json') if p.name != 'index.json') if directory.exists() else []
        for path in files:
            raw = path.read_bytes()
            self.assertLess(len(raw), 400_000, path.name)
            doc = json.loads(raw)
            for key in ('schema', 'as_of', 'provenance', 'method_flags', 'data', 'generated_at'):
                self.assertIn(key, doc, f'{path.name} {key}')
            self.assertEqual(doc['schema']['version'], cb.SCHEMA_VERSION)
            self.assertTrue(set(doc['method_flags'].values()) <= FLAGS, path.name)
            self.assertFalse(doc['provenance']['licensed_data_used'])
            self.assertNotIn('FantasyPoints', raw.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
