import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import scoring_role as sr  # noqa: E402
import td_shadow as ts  # noqa: E402

RATES = {'rates': {'carry': {'z1': .5, 'z2': .4, 'z3_5': .3, 'z6_10': .1, 'z11_20': .05, 'far': .01}, 'target': {'z1': .5, 'z2': .3, 'z3_5': .4, 'z6_10': .3, 'z11_20': .1, 'far': .02}},
         'long_td': {'min_yards': 30, 'shrink_tds': 8, 'league_share': .1}}


def play(week, yl, pid='P', team='AAA', kind='carry', date=None, drive=1, **extra):
    row = {'game_id': f'g{week}', 'play_id': float(len(extra) + yl * 7 + week), 'season': 2026, 'week': week, 'season_type': 'REG', 'posteam': team, 'yardline_100': float(yl), 'fixed_drive': drive,
           'game_date': date or f'2026-09-{week:02d}', 'qtr': 1, 'touchdown': 0}
    if kind == 'carry':
        row.update(rush_attempt=1, rusher_player_id=pid)
    else:
        row.update(pass_attempt=1, receiver_player_id=pid, air_yards=10.0)
    row.update(extra)
    return row


def profile(weeks, team='AAA', position='RB'):
    return {'id': 'P', 'team': team, 'position': position, 'games': [{'season': 2026, 'week': w, 'date': f'2026-09-{w:02d}'} for w in weeks]}


class WindowTests(unittest.TestCase):
    def test_games_on_or_after_build_date_never_enter_windows(self):
        weeks = list(range(1, 15))
        rows = [play(w, 3) for w in weeks[:-1]] + [play(14, 1, date='2026-09-14')] * 30  # huge xTD in the build-date game
        p = {'P': profile(weeks)}
        sr.attach(p, rows, {}, '2026-09-14', RATES)
        role = p['P']['scoring_role']
        self.assertEqual(role['as_of'], '2026-09-13')
        self.assertEqual(role['n'], 12)  # 13 earlier games, window caps at 12
        self.assertAlmostEqual(role['xtd_pg_l12'], .3)  # one 3-yard carry per game at .3, the build-date game excluded

    def test_window_uses_only_the_players_last_appearances(self):
        weeks = [1, 2, 3, 5, 9, 10, 11]  # missed games: windows count appearances
        rows = [play(w, 1 if w >= 9 else 15) for w in weeks]
        p = {'P': profile(weeks)}
        sr.attach(p, rows, {}, '2026-09-30', RATES)
        r = p['P']['scoring_role']
        self.assertAlmostEqual(r['xtd_pg_l6'], (.05 * 3 + .5 * 3) / 6, places=3)  # last six appearances: weeks 3,5 (.05) ... 9,10,11 (.5)

    def test_zero_touch_appearance_counts_as_zero_and_low_confidence(self):
        weeks = [1, 2, 3]
        rows = [play(1, 1), play(2, 1, pid='OTHER'), play(3, 1, pid='OTHER')]
        p = {'P': profile(weeks)}
        sr.attach(p, rows, {}, '2026-09-30', RATES)
        r = p['P']['scoring_role']
        self.assertEqual(r['confidence'], 'low')
        self.assertIsNone(r['xtd_pg_l12'])
        self.assertIsNone(r['tier'])
        self.assertEqual(r['n'], 3)

    def test_share_and_first_td_and_non_skill_positions(self):
        weeks = list(range(1, 7))
        rows = [play(w, 3) for w in weeks] + [play(w, 3, pid='MATE') for w in weeks] + [play(w, 3, pid='MATE') for w in weeks]
        p = {'P': profile(weeks), 'K': dict(profile(weeks), id='K', position='K')}
        sr.attach(p, rows, {}, '2026-09-30', RATES)
        self.assertAlmostEqual(p['P']['scoring_role']['xtd_share_l6'], 1 / 3, places=3)
        self.assertNotIn('scoring_role', p['K'])

    def test_snap_share_uses_only_earlier_games(self):
        weeks = list(range(1, 8))
        rows = [play(w, 3) for w in weeks]
        snaps = {('P', 2026, w): .5 for w in weeks[:-1]} | {('P', 2026, 7): 1.0}
        p = {'P': profile(weeks)}
        sr.attach(p, rows, snaps, '2026-09-07', RATES)  # week 7 (2026-09-07) is the build date
        self.assertAlmostEqual(p['P']['scoring_role']['snap_pct_l3'], .5)


class TierTests(unittest.TestCase):
    def test_tier_thresholds(self):
        self.assertEqual([sr.tier(x) for x in (.30, .2999, .15, .1499, .05, .0499, 0)], ['PRIMARY', 'SECONDARY', 'SECONDARY', 'TERTIARY', 'TERTIARY', 'FRINGE', 'FRINGE'])
        self.assertIsNone(sr.tier(None))


class ConditionalLogitTests(unittest.TestCase):
    RECIPE = {'game': {'first': {'k': .9, 'u': -.4}, 'last': {'k': .8, 'u': -.1}, 'king': {'k': .8, 'u': .3}}}

    def test_probabilities_sum_to_one_with_other(self):
        probs, other = ts.softmax_with_other([0.2, -1.0, 1.5, 0.0], -.4)
        self.assertAlmostEqual(sum(probs) + other, 1.0, places=12)
        self.assertTrue(all(0 < p < 1 for p in probs))

    def test_order_follows_score_and_is_translation_invariant(self):
        a, _ = ts.softmax_with_other([1.0, 2.0, 3.0], 0.0)
        self.assertTrue(a[0] < a[1] < a[2])
        b, ob = ts.softmax_with_other([1001.0, 1002.0, 1003.0], 1000.0)  # no overflow
        self.assertAlmostEqual(sum(b) + ob, 1.0, places=12)

    def test_game_probabilities_per_market(self):
        c = [{'score': 0.5, 'king_extra': .2}, {'score': -0.5, 'king_extra': -.1}]
        probs, other = ts.game_probabilities(c, self.RECIPE)
        for m in ('first', 'last', 'king'):
            self.assertAlmostEqual(sum(probs[m]) + other[m], 1.0, places=12)

    def test_anytime_score_clips_and_fills(self):
        recipe = {'anytime': {'coefficients_raw': {'intercept': -2, 'log_champion_rate': .2, 'xtd12': 1, 'xshare6': 1, 'snap3': 1, 'inside5_touch12': 0}, 'rate_floor': .01,
                              'winsor': {k: {'median': .1, 'lo': 0, 'hi': 1} for k in ('xtd12', 'xshare6', 'snap3', 'inside5_touch12')}},
                  'features_map': {'xtd12': 'xtd_pg_l12', 'xshare6': 'xtd_share_l6', 'snap3': 'snap_pct_l3', 'inside5_touch12': 'inside5_touch_pg_l12'}}
        s, used = ts.anytime_score(0.0, {'xtd_pg_l12': 5.0, 'xtd_share_l6': None, 'snap_pct_l3': .5, 'inside5_touch_pg_l12': 1}, recipe)
        self.assertEqual(used['xtd_pg_l12'], 1)  # winsorised
        self.assertEqual(used['xtd_share_l6'], .1)  # median fill
        self.assertAlmostEqual(s, -2 + .2 * math.log(.01) + 1 + .1 + .5)


class AvailabilityGateTests(unittest.TestCase):
    CUT = '2026-09-13'

    def test_only_active_players_and_fallback_without_entry(self):
        cur = {'A': {'roster_status': 'ACT'}, 'R': {'roster_status': 'RES'}, 'D': {'roster_status': 'DEV'}}
        mk = lambda i, last='2026-10-04', pos='RB': {'id': i, 'position': pos, 'last_game': last}
        self.assertTrue(ts.eligible(mk('A'), cur, self.CUT))
        self.assertFalse(ts.eligible(mk('R'), cur, self.CUT))
        self.assertFalse(ts.eligible(mk('D'), cur, self.CUT))
        self.assertTrue(ts.eligible(mk('N'), cur, self.CUT))
        self.assertFalse(ts.eligible(mk('N', last='2026-08-01'), cur, self.CUT))

    def test_backup_qb_needs_a_rushing_role(self):
        cur = {'Q1': {'roster_status': 'ACT', 'depth_rank': 1, 'rush_share': 0}, 'Q2': {'roster_status': 'ACT', 'depth_rank': 2, 'rush_share': 0.01},
               'Q3': {'roster_status': 'ACT', 'depth_rank': 2, 'rush_share': 0.2}}
        q = lambda i: {'id': i, 'position': 'QB', 'last_game': '2026-10-04'}
        self.assertTrue(ts.eligible(q('Q1'), cur, self.CUT))
        self.assertFalse(ts.eligible(q('Q2'), cur, self.CUT))
        self.assertTrue(ts.eligible(q('Q3'), cur, self.CUT))

    def test_supersede_refused_after_first_kickoff(self):
        games = [{'gameday': '2026-10-11', 'gametime': '13:00'}]
        kick = ts.first_kickoff(games)
        self.assertEqual(kick.utcoffset().total_seconds(), -4 * 3600)


if __name__ == '__main__':
    unittest.main()
