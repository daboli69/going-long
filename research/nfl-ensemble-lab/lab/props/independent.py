"""Football-only shadow margin/total anchors. Never reads a market feature."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import models

FEATURES = ["diff_rating_margin", "diff_rating_epa", "diff_qb_eff", "ctx_home_field", "ctx_rest_diff",
            "ctx_week", "ctx_dome", "ctx_retractable", "p3_mx_home_off_vs_away_def", "p3_mx_away_off_vs_home_def"]
FEATURES += [f"{side}_blend_{stat}" for side in ("home", "away")
             for stat in ("plays", "sec_per_play", "epa_pp", "d_epa_pp", "pass_rate", "pass_epa", "rush_epa")]


def spread_label(home, away, margin):
    """margin is home minus away. Display the favored team's signed handicap."""
    if not np.isfinite(margin):
        return "unavailable"
    if abs(margin) < 0.05:
        return f"{home} +0.0"
    return f"{home if margin > 0 else away} {-abs(margin):+.1f}"


class IndependentAnchor:
    def fit(self, frame, max_season=2021):
        if max_season > 2021:
            raise ValueError("Phase 10 anchor fit is capped at 2021")
        tr = frame[(frame["season"] <= max_season) & frame["home_score"].notna() & frame["away_score"].notna()].sort_values("kickoff_utc")
        self.columns = [c for c in FEATURES if c in tr and tr[c].notna().any()]
        if len(tr) < 100 or not self.columns:
            raise ValueError("Insufficient football-only training rows/features")
        X = tr[self.columns].to_numpy(float)
        self.models, self.residuals = {}, {}
        for name, y in (("margin", tr["home_score"] - tr["away_score"]),
                        ("total", tr["home_score"] + tr["away_score"])):
            model = models.make("reg", "logreg", {"alpha": 300.0}).fit(X, y.to_numpy())
            self.models[name] = model
            # Chronological out-of-fold residuals; no in-sample interval calibration.
            residuals = []
            for season in sorted(tr["season"].unique()):
                earlier, target = tr["season"].to_numpy() < season, tr["season"].to_numpy() == season
                if earlier.sum() < 100:
                    continue
                m = models.make("reg", "logreg", {"alpha": 300.0}).fit(X[earlier], y.to_numpy()[earlier])
                residuals.extend(y.to_numpy()[target] - m.predict(X[target]))
            if not residuals:
                raise ValueError("No earlier-season residuals for intervals")
            self.residuals[name] = np.asarray(residuals)
        self.train_max_season, self.train_rows = max_season, len(tr)
        return self

    def predict(self, frame):
        X = frame[self.columns].to_numpy(float)
        result = pd.DataFrame(index=frame.index)
        for name, model in self.models.items():
            center = model.predict(X)
            if name == "total":
                center = np.maximum(center, 0)
            result[name] = center
            for q in (10, 50, 90):
                values = center + np.quantile(self.residuals[name], q / 100)
                result[f"{name}_q{q}"] = np.maximum(values, 0) if name == "total" else values
        result["home_points"] = np.maximum((result["total"] + result["margin"]) / 2, 0)
        result["away_points"] = np.maximum((result["total"] - result["margin"]) / 2, 0)
        return result


def chronological_context(frame):
    """Earlier-season-only anchors for training/development, <=2021 fit for prospective."""
    results = []
    for season in sorted(frame["season"].unique()):
        target = frame[frame["season"] == season]
        try:
            anchor = IndependentAnchor().fit(frame, min(int(season) - 1, 2021))
            predictions = anchor.predict(target)
        except ValueError:
            # Training warm-up only; no season's own outcomes determine these constants.
            predictions = pd.DataFrame({"margin": 0.0, "total": 44.0}, index=target.index)
        results.append(pd.DataFrame({"game_id": target["game_id"], "ind_margin": predictions["margin"],
                                     "ind_total": predictions["total"]}))
    return pd.concat(results, ignore_index=True)


def simulate_anchor(tables, teams, players, anchor_points, n, seed, mode="independent"):
    """Same frozen play engine, separately supplied targets. No market lookup here."""
    from . import sim
    if mode not in ("independent", "market"):
        raise ValueError(mode)
    efficiency, verified = sim.calibrate_v2(tables, teams, players, anchor_points,
                                           np.random.default_rng(seed))
    return sim.simulate(tables, teams, players, n, efficiency, np.random.default_rng(seed + 1), record_td=True) | {
        "anchor_mode": mode, "anchor_points": list(map(float, anchor_points)), "calibrated_points": verified}
