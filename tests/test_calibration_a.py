import unittest
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calibration_audit_a as c


class CalibrationAuditA(unittest.TestCase):
    def test_logistic_recalibration_recovers_known_slope(self):
        rng = np.random.default_rng(1)
        p = rng.uniform(.05, .95, 20000)
        y = (rng.random(20000) < 1 / (1 + np.exp(-(0.3 + 0.5 * c.logit(p))))).astype(float)
        a, b = c.fit_cal(c.logit(p), y, np.ones_like(p))
        self.assertAlmostEqual(a, 0.3, delta=0.08)
        self.assertAlmostEqual(b, 0.5, delta=0.08)

    def test_perfectly_calibrated_has_unit_slope_and_small_ece(self):
        rng = np.random.default_rng(2)
        p = rng.uniform(.05, .95, 20000)
        y = (rng.random(20000) < p).astype(float)
        idx = np.clip(np.digitize(p, c.EDGES[1:-1]), 0, 9)
        m = c.metrics(p, y, np.ones_like(p), idx, np.zeros(len(p), int), np.full(len(p), np.nan))
        self.assertAlmostEqual(m['slope'], 1.0, delta=0.08)
        self.assertLess(m['ece'], 0.02)

    def test_unidentified_fit_is_nan_not_zero(self):
        a, b = c.fit_cal(np.zeros(10), np.array([0, 1] * 5, float), np.ones(10))
        self.assertTrue(np.isnan(a) and np.isnan(b))

    def test_grade_rules(self):
        self.assertEqual(c.grade('player_receptions', 'Over', 4.5, 5), 'win')
        self.assertEqual(c.grade('player_receptions', 'Under', 4.0, 4), 'refund')
        self.assertEqual(c.grade('spreads', 'Away', -3.5, 1.5), 'loss')   # actual = home margin + home line
        self.assertEqual(c.grade('h2h', 'Home', 0, 0.0), 'refund')
        self.assertEqual(c.grade('atd', 'Yes', 0.5, 1), 'win')
        self.assertIsNone(c.grade('atd', 'Yes', 0.5, float('nan')))

    def test_cohort_port(self):
        self.assertEqual(c.model_cohort({'model_cohort': 'x'}), 'x')
        self.assertEqual(c.model_cohort({'model_evidence': {'gameSeasonEvidence': {'policy': '80% current / 20% historical'}}}), 'current-80-20')
        self.assertEqual(c.model_cohort({'model_evidence': {}}), 'legacy')

    def test_wilson_bounds(self):
        lo, hi = c.wilson(5, 10)
        self.assertTrue(0 < lo < .5 < hi < 1)


if __name__ == '__main__':
    unittest.main()
