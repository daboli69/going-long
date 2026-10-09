"""Unit tests for scripts/going_score_build.py on synthetic data (no network)."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import going_score_build as gsb  # noqa: E402

PARAMS = {**gsb.DEFAULT_PARAMS, 'half_life': 4.0}
PRIORS = {'production': 10.0, 'opportunity': 9.0, 'team_share': 0.1, 'role': 60.0}


def make_player(pid, pos, ppr, xfp, snap=None, team='AAA', season=2025, start_week=1):
    rows = []
    for i, (p, x) in enumerate(zip(ppr, xfp)):
        week = start_week + i
        rows.append({'player_id': pid, 'name': pid, 'position': pos, 'team': team, 'season': season, 'week': week, 'attempts': 0, 'ppr': p, 'snap': (snap[i] if snap else 70.0),
                     'xfp': x, 'xfp_team': 40.0, 'xfp_share': x / 40.0, 'xfp_source': 'ffopportunity', 'key': season * 100 + week})
    return pd.DataFrame(rows)


def team_games_for(weeks, team='AAA', season=2025):
    return {team: np.array([season * 100 + w for w in weeks])}


class FeatureTests(unittest.TestCase):
    def test_features_use_only_prior_games(self):
        frame = make_player('p', 'WR', [10] * 6 + [99], [10] * 7)
        tg = team_games_for(range(1, 8))
        early = gsb.player_features(frame, tg, [202507], PARAMS, PRIORS)[0]
        self.assertLess(early['production'], 12.0)  # the 99-point week 7 game is not in week 7's features
        changed = frame.copy()
        changed.loc[changed.week == 7, ['ppr', 'xfp']] = [0.0, 0.0]
        again = gsb.player_features(changed, tg, [202507], PARAMS, PRIORS)[0]
        self.assertEqual(early['production'], again['production'])
        self.assertEqual(early['opportunity'], again['opportunity'])

    def test_min_games_gate(self):
        frame = make_player('p', 'WR', [10, 10], [10, 10])
        self.assertEqual(gsb.player_features(frame, team_games_for(range(1, 3)), [202503], PARAMS, PRIORS), [])

    def test_shrinkage_pulls_small_samples_to_prior(self):
        short = gsb.player_features(make_player('a', 'WR', [30] * 3, [30] * 3), team_games_for(range(1, 4)), [202504], PARAMS, PRIORS)[0]
        long = gsb.player_features(make_player('b', 'WR', [30] * 12, [30] * 12), team_games_for(range(1, 13)), [202513], PARAMS, PRIORS)[0]
        self.assertTrue(PRIORS['opportunity'] < short['opportunity'] < long['opportunity'] < 30)

    def test_recency_weighting_and_trend_sign(self):
        up = gsb.player_features(make_player('u', 'WR', [5] * 6 + [20] * 4, [5] * 6 + [20] * 4), team_games_for(range(1, 11)), [202511], PARAMS, PRIORS)[0]
        down = gsb.player_features(make_player('d', 'WR', [20] * 4 + [5] * 6, [20] * 4 + [5] * 6), team_games_for(range(1, 11)), [202511], PARAMS, PRIORS)[0]
        self.assertGreater(up['opportunity'], down['opportunity'])
        self.assertGreater(up['opp_trend'], 0)
        self.assertLess(down['opp_trend'], 0)

    def test_availability_counts_missed_team_games(self):
        full = gsb.player_features(make_player('p', 'RB', [10] * 4, [10] * 4), team_games_for(range(1, 5)), [202505], PARAMS, PRIORS)[0]['availability']
        frame2 = pd.concat([make_player('p', 'RB', [10] * 3, [10] * 3), make_player('p', 'RB', [10], [10], start_week=6)], ignore_index=True)
        missed = gsb.player_features(frame2, team_games_for(range(1, 8)), [202507], PARAMS, PRIORS)[0]['availability']
        self.assertGreater(full, missed)

    def test_champion_weights(self):
        w = gsb.season_weights_champion([2024, 2024, 2025, 2025, 2025], 2025)
        self.assertAlmostEqual(w.sum(), 1.0)
        self.assertAlmostEqual(w[2:].sum(), 0.8)


def config_for(weights):
    comps = {n: {'weight': weights.get(n, 0.0), 'mean': 0.0, 'sd': 1.0} for n in gsb.SCORED}
    return {'version': 't', 'params': {**PARAMS, 'min_games': 3, 'max_stale_team_games': 6}, 'positions': {'WR': {'priors': PRIORS, 'components': comps, 'anchors': {'low': -2.0, 'high': 2.0}}}}


class ScoringTests(unittest.TestCase):
    def table(self):
        rows = []
        for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0]):
            rows.append({'player_id': f'p{i}', 'position': 'WR', 'key': 202510, **{n: v for n in gsb.SCORED}})
        return pd.DataFrame(rows)

    def test_percentile_is_midrank_and_position_scoped(self):
        scored = gsb.score_table(self.table(), config_for({'opportunity': 1.0}))
        self.assertEqual(list(scored.pctile), [0.0, 25.0, 50.0, 75.0, 100.0])

    def test_missing_component_is_neutral(self):
        t = self.table()
        t.loc[2, 'role'] = np.nan
        z = gsb.zscores(t, config_for({'role': 1.0})['positions']['WR'])
        self.assertEqual(z['role'][2], 0.0)

    def test_absolute_clipped_and_monotone(self):
        cfg = config_for({'opportunity': 1.0})['positions']['WR']
        self.assertEqual(list(gsb.absolute_score([-9.0, 0.0, 9.0], cfg)), [0.0, 50.0, 100.0])

    def test_weights_renormalised_when_dropping(self):
        cfg = config_for({'opportunity': 0.5, 'role': 0.5})['positions']['WR']
        self.assertTrue(np.allclose(gsb.raw_score(self.table(), cfg), gsb.raw_score(self.table(), cfg, drop=('role',))))

    def test_tier_boundaries(self):
        self.assertEqual(gsb.tier_for(90)['id'], 'elite')
        self.assertEqual(gsb.tier_for(89.9)['id'], 'strong')
        self.assertEqual(gsb.tier_for(0)['id'], 'low')


class PanelTests(unittest.TestCase):
    def test_panel_drops_cameo_qb_and_recovers_zero_stat_snaps(self):
        base = {'season': 2025, 'week': 1, 'season_type': 'REG', 'team': 'AAA'}
        weekly = pd.DataFrame([
            {**base, 'player_id': 'q1', 'player_display_name': 'Q', 'position': 'QB', 'attempts': 30, 'fantasy_points_ppr': 20.0},
            {**base, 'player_id': 'q2', 'player_display_name': 'Cameo', 'position': 'QB', 'attempts': 2, 'fantasy_points_ppr': 1.0},
            {**base, 'player_id': 'w1', 'player_display_name': 'W', 'position': 'WR', 'attempts': 0, 'fantasy_points_ppr': 8.0}])
        snaps = pd.DataFrame([{'season': 2025, 'game_type': 'REG', 'week': 1, 'pfr_player_id': 'PfrW', 'position': 'WR', 'team': 'AAA', 'offense_snaps': 5, 'offense_pct': 0.1},
                              {'season': 2025, 'game_type': 'REG', 'week': 1, 'pfr_player_id': 'PfrZ', 'position': 'WR', 'team': 'AAA', 'offense_snaps': 3, 'offense_pct': 0.05}])
        players = pd.DataFrame([{'pfr_id': 'PfrW', 'gsis_id': 'w1', 'position': 'WR', 'display_name': 'W'}, {'pfr_id': 'PfrZ', 'gsis_id': 'z1', 'position': 'WR', 'display_name': 'Z'}])
        ffopp = pd.DataFrame([{'season': 2025, 'week': 1, 'player_id': 'w1', 'total_fantasy_points_exp': 7.0, 'total_fantasy_points_exp_team': 35.0}])
        panel, team_games, weeks = gsb.build_panel(weekly, snaps, players, ffopp)
        self.assertEqual(set(panel.player_id), {'q1', 'w1', 'z1'})
        z = panel[panel.player_id == 'z1'].iloc[0]
        self.assertEqual((z.ppr, z.xfp), (0.0, 0.0))
        w = panel[panel.player_id == 'w1'].iloc[0]
        self.assertAlmostEqual(w.xfp_share, 0.2)
        self.assertAlmostEqual(w.snap, 10.0)
        self.assertEqual(list(team_games['AAA']), [202501])
        self.assertEqual(weeks[2025], [1])

    def test_sleeper_link_requires_unique_match(self):
        roster = [{'id': 'g1', 'name': 'Same Name', 'position': 'WR'}, {'id': 'g2', 'name': 'Same Name', 'position': 'WR'}, {'id': 'g3', 'name': 'Only One', 'position': 'RB'}]
        pj = {'players': [{'name': 'Same Name', 'pos': 'WR', 'sleeper_id': '1'}, {'name': 'Only One', 'pos': 'RB', 'sleeper_id': '2'}]}
        self.assertEqual(gsb.sleeper_links(roster, pj), {'g3': '2'})


class EndToEndTests(unittest.TestCase):
    def test_build_output_schema_on_synthetic_league(self):
        tg = {'AAA': np.array([202500 + w for w in range(1, 11)])}
        panel = pd.concat([make_player(f'p{i}', 'WR', [5 + 2 * i] * 9, [5 + 2 * i] * 9) for i in range(6)], ignore_index=True)
        keys = [202503 + k for k in range(8)]
        table = gsb.asof_table(panel, tg, {2025: list(range(1, 10))}, PARAMS, {'WR': PRIORS}, extra_keys=keys)
        out = gsb.build_output(table, panel, config_for({'opportunity': 0.7, 'role': 0.3}), 'sha', None, None, None, '2025-11-01T00:00:00Z', 202510, keys, {'sources': []})
        self.assertEqual(out['schema'], 'going-score-v2')
        top = max(out['players'].values(), key=lambda p: p['score'])
        self.assertEqual((top['name'], top['score']), ('p5', 100.0))
        self.assertEqual(len(top['history']), 8)
        self.assertEqual(top['components']['production']['weight'], 0.0)
        self.assertAlmostEqual(sum(c['weight'] for c in top['components'].values()), 1.0, places=3)
        self.assertIn('not a better bet', out['meaning'])


if __name__ == '__main__':
    unittest.main()
