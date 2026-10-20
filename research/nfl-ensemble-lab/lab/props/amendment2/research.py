"""Amendment 2: 2022 benchmarks/closing-feature ablation and DEV game blends."""
from __future__ import annotations
import argparse
import json
import joblib
import numpy as np
import pandas as pd
from ...config import RAW_DIR
from ...ingest import canonical_game_id, normalize_team
from ..ensemble import TARGETS
from ..ensemble.data import OUT
from ..ensemble.features import FEATURES, eligible
from ..ensemble.members import Members
from ..ensemble.run import learned_predictions, merge_structural, structural_rows, chronological_combinations
from ..ensemble.combine import loss_rows
from ..ensemble.research import clustered_difference

DEST = OUT / "amendment2" / "research"


def write(name, value):
    DEST.mkdir(parents=True, exist_ok=True)
    path = DEST / name
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)
    return value


def closing_games():
    d = pd.read_csv(RAW_DIR / "games.csv", usecols=["season", "week", "away_team", "home_team", "spread_line", "total_line"])
    d["game_id"] = [canonical_game_id(s, w, normalize_team(a), normalize_team(h))
                    for s, w, a, h in d[["season", "week", "away_team", "home_team"]].itertuples(index=False, name=None)]
    return d


def ci(d, a, b, stat):
    return clustered_difference(d.game_id, loss_rows(stat, d.actual, d[a]) - loss_rows(stat, d.actual, d[b]), seed=20261020)


def benchmarks():
    DEST.mkdir(parents=True, exist_ok=True)
    baseline = pd.read_parquet(OUT.parent / "dev" / "player_games.parquet")
    reference = pd.read_parquet(OUT / "dev_predictions.parquet")
    assert set(baseline.season) == {2022} == set(reference.season)
    # Exact player/stat intersection. v1 can have extra retrospective starters;
    # those cannot silently change the ensemble's prospective eligibility pool.
    joined = reference.merge(baseline[["game_id", "pid", "stat", "actual", "sim_mean", "base_mean"]],
                             on=["game_id", "pid", "stat"], suffixes=("", "_v1"), validate="one_to_one")
    if not np.allclose(joined.actual, joined.actual_v1):
        raise ValueError("Benchmark and ensemble outcomes differ")
    result = {"requested_rows": len(reference), "requested_games": reference.game_id.nunique(),
              "original_v1_rows": len(baseline), "matched_rows": len(joined), "matched_games": joined.game_id.nunique(),
              "unmatched_ensemble_rows": len(reference) - len(joined),
              "limitation": "Original v1 uses closing anchors and retrospective first passer/target-week roster; only four supported stats. Not a pregame independent comparator.", "results": []}
    for stat in TARGETS:
        d = joined[joined.stat.eq(stat)]
        if d.empty:
            result["results"].append({"stat": stat, "status": "original v1/baseline B unsupported; no values invented"})
            continue
        for member in ("equal", "weighted", "stacked", "sim_mean", "base_mean"):
            row = {"stat": stat, "method": member, "n": len(d), "games": d.game_id.nunique(),
                   "metric": "Poisson deviance" if stat == "rec" else "MAE",
                   "loss": float(loss_rows(stat, d.actual, d[member]).mean())}
            for comparator in ("sim_mean", "base_mean"):
                row["vs_" + comparator] = ci(d, member, comparator, stat)
            result["results"].append(row)
    joined.to_parquet(DEST / "benchmark_matched2022.parquet", index=False)
    from ...config import REPORTS_DIR
    flat=[]
    for r in result["results"]:
        row={k:v for k,v in r.items() if not isinstance(v,dict)}
        for baseline in ("sim_mean","base_mean"):
            value=r.get("vs_"+baseline)
            if value:
                row.update({"delta_vs_"+baseline:value["difference"],"ci95_low_vs_"+baseline:value["ci95"][0],"ci95_high_vs_"+baseline:value["ci95"][1]})
        flat.append(row)
    report=pd.DataFrame(flat)
    stem=REPORTS_DIR/"run_20261020"/"B3_COMPARISON_2022"
    report.to_csv(stem.with_suffix(".csv"),index=False)
    columns=list(report.columns)
    lines=["# Original v1 / baseline B versus ensembles — 2022", "",
        f"Requested ensemble rows {len(reference)} / {reference.game_id.nunique()} games; exact matched rows {len(joined)} / {joined.game_id.nunique()} games. All methods within each stat use identical rows. Original v1/B cover four stats and use closing anchors/retrospective eligibility. TD targets unsupported, not invented. Negative deltas favor the row method; paired game-cluster 95% CIs, 2,000 draws seed 20261020.","",
        "| "+" | ".join(columns)+" |","| "+" | ".join(["---"]*len(columns))+" |"]
    for _,r in report.iterrows():
        values=["unavailable" if pd.isna(r[c]) else f"{r[c]:.4f}" if isinstance(r[c],float) else str(r[c]) for c in columns]
        lines.append("| "+" | ".join(values)+" |")
    stem.with_suffix(".md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return write("benchmarks2022.json", result)


def market_ablation(threads=14, log=print):
    frame = pd.read_parquet(OUT / "features.parquet")
    frame = frame[frame.season.between(2016, 2022)].merge(closing_games()[["game_id", "spread_line", "total_line"]], on="game_id", validate="many_to_one")
    frame["closing_team_points"] = (frame.total_line + np.where(frame.home.eq(1), frame.spread_line, -frame.spread_line)) / 2
    directory = DEST / "market_members"
    directory.mkdir(parents=True, exist_ok=True)
    for stat in TARGETS:
        path = directory / f"{stat}.joblib"
        if path.exists():
            continue
        tr = frame[frame.season.le(2021) & eligible(frame, stat) & frame[stat].notna() & frame.closing_team_points.notna()]
        model = Members().fit(tr, stat, FEATURES + ["closing_team_points"], threads, log)
        joblib.dump(model, path)
    wide = learned_predictions(frame[frame.season.eq(2022)], directory, log)
    wide = wide[wide.actual.notna()]
    wide = merge_structural(wide, structural_rows(2022))
    predicted = chronological_combinations(wide)
    predicted["variant"] = "market-informed closing team-points feature; retrospective-information ablation"
    predicted.to_parquet(DEST / "market_feature_predictions2022.parquet", index=False)
    ref = pd.read_parquet(OUT / "dev_predictions.parquet")
    d = predicted.merge(ref[["game_id", "pid", "stat", "equal", "actual"]], on=["game_id", "pid", "stat"], suffixes=("", "_ind"), validate="one_to_one")
    assert np.allclose(d.actual, d.actual_ind)
    results = []
    for stat, z in d.groupby("stat"):
        row = {"stat": stat, "n": len(z), "games": z.game_id.nunique(), "difference": ci(z, "equal", "equal_ind", stat)}
        if stat == "anytime_td":
            from ...metrics import log_loss
            row["log_loss_difference"] = log_loss(z.actual, z.equal) - log_loss(z.actual, z.equal_ind)
        results.append(row)
    return write("market_feature2022.json", {"split": "fit <=2021 / walk-forward 2022", "results": results,
        "limitation": "Closing lines have retrospective information; not archived pregame prices and never independent/default features."})


def blends():
    d = pd.read_parquet(OUT / "game_dev_predictions.parquet").merge(closing_games()[["game_id", "spread_line", "total_line"]], on="game_id", validate="many_to_one")
    assert set(d.season) == {2019, 2020, 2021, 2022}
    levels = np.arange(1, 100) / 100
    results = []
    all_rows = []
    for stat, z in d.groupby("stat"):
        z = z.sort_values(["season", "game_id"]).copy()
        z["market"] = z["spread_line" if stat == "margin" else "total_line"]
        if z.market.isna().any():
            raise ValueError("Missing DEV closing lines")
        z["blend"], z["weight"], z["crps_blend"], z["crps_market"] = np.nan, np.nan, np.nan, np.nan
        for season in sorted(z.season.unique()):
            prior, cur = z[z.season.lt(season)], z[z.season.eq(season)]
            x = prior.prediction - prior.market
            y = prior.actual - prior.market
            w = float(np.clip(np.dot(x, y) / np.dot(x, x), 0, 1)) if len(prior) and np.dot(x, x) else 0.
            z.loc[cur.index, "blend"] = cur.market + w * (cur.prediction - cur.market)
            z.loc[cur.index, "weight"] = w
            if not len(prior):
                continue
            for key in ("blend", "market"):
                center = cur.market + w * (cur.prediction - cur.market) if key == "blend" else cur.market
                residual = prior.actual - (prior.market + w * (prior.prediction - prior.market) if key == "blend" else prior.market)
                q = center.to_numpy()[:, None] + np.quantile(residual, levels)[None, :]
                error = cur.actual.to_numpy()[:, None] - q
                z.loc[cur.index, "crps_" + key] = 2 * np.maximum(levels * error, (levels - 1) * error).mean(1)
        e, m = z.blend - z.actual, z.market - z.actual
        metrics = {"mae": clustered_difference(z.game_id, abs(e) - abs(m), seed=20261020)}
        index = np.random.default_rng(20261020).integers(0, len(z), (2000, len(z)))
        draws = np.sqrt(np.square(e.to_numpy())[index].mean(1)) - np.sqrt(np.square(m.to_numpy())[index].mean(1))
        metrics["rmse"] = {"n": len(z), "difference": float(np.sqrt(np.square(e).mean()) - np.sqrt(np.square(m).mean())), "ci95": np.quantile(draws, [.025, .975]).tolist()}
        a = z.dropna(subset=["crps_blend", "crps_market"])
        metrics["crps"] = clustered_difference(a.game_id, a.crps_blend - a.crps_market, seed=20261020)
        results.append({"stat": stat, "metrics": metrics, "weights": z.groupby("season").weight.first().to_dict(), "status": "development only; no promotion"})
        all_rows.append(z)
    pd.concat(all_rows).to_parquet(DEST / "game_blend_dev.parquet", index=False)
    return write("game_blends.json", results)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["benchmarks", "market", "blends"])
    p.add_argument("--threads", type=int, default=14)
    a = p.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    print(json.dumps(market_ablation(a.threads) if a.command == "market" else benchmarks() if a.command == "benchmarks" else blends(), indent=2))
