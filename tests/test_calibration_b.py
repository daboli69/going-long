import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import calibration_models as cm  # noqa: E402

CACHE = cm.FP_ROOT / 'research' / 'cache' / 'champion_2021_2025.parquet'
CANDIDATES = REPO / 'config' / 'calibration_candidates.json'


class MathTests(unittest.TestCase):
    def test_logistic_fit_recovers_parameters(self):
        rng = np.random.default_rng(1)
        x = rng.normal(0, 1.5, 40000)
        y = (rng.random(40000) < 1 / (1 + np.exp(-(0.3 + 0.7 * x)))).astype(float)
        a, b = cm.fit_logistic(x, y)
        self.assertAlmostEqual(a, 0.3, delta=0.06)
        self.assertAlmostEqual(b, 0.7, delta=0.06)

    def test_ridge_pulls_toward_center(self):
        rng = np.random.default_rng(2)
        x = rng.normal(0, 1, 300)
        y = (rng.random(300) < 1 / (1 + np.exp(-(0.0 + 0.4 * x)))).astype(float)
        free = cm.fit_logistic(x, y)
        pulled = cm.fit_logistic(x, y, ridge=1e6, center=(0.0, 1.0))
        self.assertLess(abs(pulled[1] - 1.0), abs(free[1] - 1.0))
        self.assertLess(abs(pulled[1] - 1.0), 0.01)

    def test_weighted_metrics_match_unweighted_with_unit_weights(self):
        rng = np.random.default_rng(3)
        p = rng.random(500)
        y = (rng.random(500) < p).astype(float)
        m = cm.point_metrics(p, y)
        self.assertAlmostEqual(m['brier'], float(((p - y) ** 2).mean()))
        from sklearn.metrics import roc_auc_score
        self.assertAlmostEqual(m['auc'], roc_auc_score(y, p), places=9)

    def test_bootstrap_ci_brackets_point_and_is_cluster_based(self):
        rng = np.random.default_rng(4)
        groups = np.repeat(np.arange(200), 5)
        p = rng.random(1000)
        y = (rng.random(1000) < p).astype(float)
        out = cm.bootstrap_metrics(p, y, groups, draws=120)
        lo, hi = out['ci95']['brier']
        self.assertLess(lo, out['point']['brier'])
        self.assertGreater(hi, out['point']['brier'])

    def test_isotonic_is_monotone_and_applies(self):
        rng = np.random.default_rng(5)
        p = rng.random(3000)
        y = (rng.random(3000) < p ** 2).astype(float)
        spec = cm.iso_fit(p, y)
        self.assertTrue(np.all(np.diff(spec['y']) >= -1e-12))
        out = cm.iso_apply(np.array([0.1, 0.5, 0.9]), spec)
        self.assertTrue(np.all(np.diff(out) >= 0))

    def test_js_reference_semantics_logistic_push_and_complement(self):
        spec = {'method': 'platt', 'a': -0.2, 'b': 0.78}
        p_over, push = 0.40, 0.10
        over = float(cm.apply_spec(p_over, spec, 'Over', push))
        under = float(cm.apply_spec(p_over, spec, 'Under', push))
        self.assertAlmostEqual(over + under, 1 - push, places=12)
        q = p_over / (1 - push)
        expected = (1 - push) / (1 + math.exp(-(spec['a'] + spec['b'] * math.log(q / (1 - q)))))
        self.assertAlmostEqual(over, expected, places=12)
        # the explicit Under form (a' = -a on logit(p_under)) agrees with the complement
        p_under = (1 - push) - p_over
        qu = p_under / (1 - push)
        under_direct = (1 - push) / (1 + math.exp(-(-spec['a'] + spec['b'] * math.log(qu / (1 - qu)))))
        self.assertAlmostEqual(under_direct, under, places=12)
        q0 = 0.35
        self.assertAlmostEqual(float(cm.apply_spec(q0, spec, 'Over')) + float(cm.apply_spec(q0, spec, 'Under')), 1.0, places=12)
        u0 = 1 - q0
        direct = 1 / (1 + math.exp(-(-spec['a'] + spec['b'] * math.log(u0 / (1 - u0)))))
        self.assertAlmostEqual(direct, float(cm.apply_spec(q0, spec, 'Under')), places=12)


@unittest.skipUnless(CACHE.exists(), 'private Champion frame cache not present')
class ReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = cm.load_frame()

    def test_vectorised_probabilities_match_research_and_production_functions(self):
        from trend_research import promotion_check as pc
        sys.path.insert(0, str(REPO / 'scripts'))
        pol = cm.policy()
        for market in ('receptions', 'rec_yds', 'rush_yds', 'atd'):
            rows, long = cm.build_long(self.frame, market)
            probs = cm.long_probs(rows, long, market)
            sample = long.sample(60, random_state=3)
            for index, r in sample.iterrows():
                j = long.index.get_loc(index)
                row = rows.iloc[int(r.row)].to_dict()
                self.assertAlmostEqual(pc.v1_over(market, row, r.line), probs['v1'][j], places=10)
                self.assertAlmostEqual(pc.v2_over(market, row, r.line, pol), probs['v2'][j], places=10)

    def test_lines_use_half_integers_and_outcomes_are_consistent(self):
        for market in cm.MARKETS:
            rows, long = cm.build_long(self.frame, market)
            self.assertTrue(np.all(np.isclose(long.line % 1, 0.5)))
            expected = (long.stat.to_numpy() > long.line.to_numpy()).astype(float)
            self.assertTrue(np.array_equal(expected, long.y.to_numpy()))
            self.assertTrue(long.groupby('row').is_main.sum().le(1).all())

    def test_no_future_information_in_features(self):
        # the frame's own window rule: a row's champion mean must not change when later seasons are dropped
        early = self.frame[self.frame.season <= 2023]
        rows_a, long_a = cm.build_long(early, 'receptions')
        rows_b, long_b = cm.build_long(self.frame, 'receptions')
        a = rows_a.set_index(['player_id', 'season', 'week']).champ_receptions
        b = rows_b.set_index(['player_id', 'season', 'week']).champ_receptions
        common = a.index.intersection(b.index)
        self.assertGreater(len(common), 1000)
        self.assertTrue(np.allclose(a.loc[common].to_numpy(), b.loc[common].to_numpy()))


class CandidateFileTests(unittest.TestCase):
    @unittest.skipUnless(CANDIDATES.exists(), 'run scripts/calibration_audit_b.py final first')
    def test_candidate_file_shape_and_symmetry(self):
        d = json.loads(CANDIDATES.read_text(encoding='utf-8'))
        self.assertEqual(set(d['markets']), set(cm.MARKETS))
        for market, sides in d['markets'].items():
            over, under = sides['Over'], sides['Under']
            for side in (over, under):
                self.assertIn(side['recommendation'], ('PROMOTE', 'SHADOW', 'REJECT', 'NO CORRECTION NEEDED'))
                self.assertEqual(side['training_window'], '2021-2023')
                self.assertIn('2025', side['holdout_window'])
            if over['method'] in ('platt', 'pooled_platt'):
                self.assertAlmostEqual(under['parameters']['a'], -over['parameters']['a'])
                self.assertEqual(under['parameters']['b'], over['parameters']['b'])
                self.assertGreater(over['parameters']['b'], 0)


if __name__ == '__main__':
    unittest.main()
