"""Immutable prospective shadow forecasts and a readable weekly projection sheet.

Called through python -m lab.props.weekly projections. Never scores outcomes.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import poisson

from ..archive10 import freshness
from ..config import REPORTS_DIR, LAB_ROOT
from ..data_pipeline import FEATURE_STORE
from ..ensemble import vote
from .ensemble import COUNTS, YARDS
from .ensemble.combine import first_td_reweight
from .ensemble.data import OUT
from .ensemble.frozen import load as frozen_config
from .ensemble.run import learned_predictions, merge_structural, chronological_combinations
from .ensemble.structural import local_game_lines
from .independent import IndependentAnchor, spread_label
from .lines import archived_lines


def price_gap(probability, over, under):
    from ..market81 import american_to_prob, novig
    if over is None or not np.isfinite(over) or abs(over) < 100:
        return {"gap": None, "gap_units": "probability benchmark unavailable"}
    raw = float(american_to_prob(over))
    if under is not None and np.isfinite(under) and abs(under) >= 100:
        implied = float(novig(raw, float(american_to_prob(under))))
        basis = "probability vs multiplicative no-vig price"
    else:
        implied, basis = raw, "probability vs raw implied price; vig remains"
    return {"market_probability": implied, "gap": probability - implied, "gap_units": basis}


def probability_summary(samples, line):
    samples = np.asarray(samples, float)
    if not len(samples) or not np.isfinite(samples).all() or not np.isfinite(line):
        raise ValueError("A real line and finite model samples are required")
    over, under, push = float((samples > line).mean()), float((samples < line).mean()), float((samples == line).mean())
    return {"p_over": over, "p_under": under, "p_push": push,
            "p_over_no_push": over / (over + under) if over + under else None}


def distribution(row, development, structural, n=1000):
    """Equal mixture of actual named members; no odds enter this distribution."""
    rng = np.random.default_rng(20261019)
    stat = row["stat"]
    pools = []
    if stat == "anytime_td":
        return rng.binomial(1, float(row["equal"]), n), "Bernoulli outcome quantiles; ensemble projection is the TD probability, not a probability confidence interval"
    for member in row["members"].split(","):
        if member in ("sim_independent", "simulator_v1"):
            match = structural[(structural["game_id"] == row["game_id"]) & (structural["pid"] == row["pid"])
                               & (structural["stat"] == stat) & (structural["member"] == member)]
            if len(match):
                x = np.asarray(match.iloc[0]["samples"], float)
                pools.append(rng.choice(x, n, replace=True))
        elif stat in COUNTS:
            pools.append(rng.poisson(max(float(row[member]), 1e-6), n))
        else:
            history = development[development["stat"] == stat].dropna(subset=[member, "actual"])
            if len(history) < 100:
                continue
            residual = history["actual"].to_numpy() - history[member].to_numpy()
            residual -= residual.mean()
            pools.append(float(row[member]) + rng.choice(residual, n, replace=True))
    if not pools:
        raise ValueError("No justified distribution available")
    return np.concatenate(pools), "equal member mixture: centered 2022 OOF residuals / Poisson rates / structural samples"


def matching_lines(lines, game, pid, stat):
    if lines.empty:
        return lines
    d = lines[(lines["home"] == game.home_team) & (lines["away"] == game.away_team)
              & (lines["gsis_id"] == pid) & (lines["stat"] == stat) & lines["pregame_verified"] & lines["period"].eq("FULL")].copy()
    if d.empty:
        return d
    d = d[(pd.to_datetime(d["kickoff"], utc=True, format="mixed") - game.kickoff_utc).abs() <= pd.Timedelta(minutes=15)]
    return d.sort_values(["quote_time", "available_at"]).groupby("book").tail(1)


def binary_contract_corrections(frame):
    """A binary TD>=1 model cannot price a TD-count threshold such as 1.5.

    Preserve model projections and quote provenance. Never turn an unsupported
    market into a spurious zero probability. Older immutable forecasts are
    corrected in derived reports through an explicit append-only correction.
    """
    result = frame.copy()
    if "market_line" not in result or "stat" not in result:
        return result, result.iloc[:0]
    point = pd.to_numeric(result["market_line"], errors="coerce")
    bad = result["stat"].isin(["anytime_td", "first_td"]) & point.notna() & ~np.isclose(point, .5)
    corrections = result[bad].copy()
    if bad.any():
        for key in ("p_over", "p_under", "p_push", "p_over_no_push", "gap", "market_probability"):
            if key in result:
                result.loc[bad, key] = None
        result.loc[bad, "benchmark_scope_status"] = "unsupported TD-count threshold; binary anytime/first-TD model is not comparable"
    return result, corrections


def first_td_contract_corrections(frame):
    """Quoted first-TD settlement is unknown; our offensive-only target is explicit."""
    result = frame.copy()
    if "stat" not in result or "book" not in result:
        return result, result.iloc[:0]
    bad = result["stat"].eq("first_td") & result["book"].notna()
    corrections = result[bad].copy()
    if bad.any():
        for key in ("p_over", "p_under", "p_push", "p_over_no_push", "gap", "market_probability"):
            if key in result:
                result.loc[bad, key] = None
        result.loc[bad, "benchmark_scope_status"] = "first-TD quote settlement unverified against offensive-only regulation target"
    return result, corrections


def forecast(week=None, season=2026, log=print, distribution_sink=None):
    config = frozen_config()
    if season != 2026:
        raise ValueError("Phase 10 projection archives are prospective 2026 only")
    fit = json.loads((OUT / "production_fit.json").read_text())
    if fit["frozen_config_sha256"] != config["config_sha256"]:
        raise ValueError("Recent fit does not match committed frozen configuration")
    frame = pd.read_parquet(OUT / "features_production.parquet")
    games = pd.read_parquet(FEATURE_STORE)
    now = pd.Timestamp.now(tz="UTC")
    upcoming = games[(games["season"] == season) & ~games["completed"] & (games["kickoff_utc"] > now)
                     & games["game_id"].isin(frame["game_id"])]
    if week is not None:
        upcoming = upcoming[upcoming["week"] == week]
    frame = frame[frame["game_id"].isin(upcoming["game_id"])]
    if frame.empty:
        return {"archived": [], "reason": "no eligible unplayed games"}
    learned = learned_predictions(frame, Path(fit["directory"]), log)
    files = sorted((OUT / "structural_prospective2026_recent").glob("*.parquet"))
    structural = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True) if files else pd.DataFrame()
    if structural.empty:
        raise ValueError("Recent structural forecasts are required before the projection archive")
    learned = merge_structural(learned, structural)
    development = pd.read_parquet(OUT / "dev_predictions.parquet")
    combined = chronological_combinations(learned, previous=development)
    market = chronological_combinations(learned, previous=development, variant="market-informed")
    market_values = market.set_index(["game_id", "pid", "stat"])["equal"]
    lines = archived_lines(asof=now)
    if len(lines):
        quote_kickoffs = pd.to_datetime(lines["kickoff"], utc=True, errors="coerce", format="mixed")
        # Historical archives can contain nearly a million rows. Filter to the
        # actual upcoming horizon once before per-player/book matching.
        lines = lines[(quote_kickoffs >= upcoming["kickoff_utc"].min() - pd.Timedelta(minutes=15)) &
                      (quote_kickoffs <= upcoming["kickoff_utc"].max() + pd.Timedelta(minutes=15))].copy()
    game_lines = local_game_lines(upcoming, now)
    anchor = IndependentAnchor().fit(games)
    rows, archived, errors = [], [], []
    directory = OUT / "forecasts2026"
    directory.mkdir(parents=True, exist_ok=True)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=LAB_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    for game in upcoming.sort_values(["week", "game_id"]).itertuples(index=False):
        archive_path = directory / f"{game.game_id}.json"
        if archive_path.exists():
            old = json.loads(archive_path.read_text())
            rows.extend(old["rows"])
            archived.append(game.game_id)
            continue
        if game.week <= fit["training_last_completed_week"]:
            errors.append({"game_id": game.game_id, "error": "training week reaches forecast week"})
            continue
        game_rows = []
        try:
            pred = anchor.predict(games[games["game_id"] == game.game_id]).iloc[0]
            benchmark = game_lines.get(game.game_id, {})
            structural_meta = json.loads((OUT / "structural_prospective2026_recent" / f"{game.game_id}.json").read_text())
            simulations = {g["member"]: g for g in structural_meta["games"]}
            for stat in ("margin", "total"):
                value = float(pred[stat])
                line = benchmark.get(stat)
                r = {"row_type": "game", "game_id": game.game_id, "week": game.week, "team": game.home_team,
                     "name": f"{game.away_team} at {game.home_team}", "stat": stat, "variant": "independent",
                     "projection": value, "spread_display": spread_label(game.home_team, game.away_team, value) if stat == "margin" else None,
                     "q10": float(pred[f"{stat}_q10"]), "q50": float(pred[f"{stat}_q50"]), "q90": float(pred[f"{stat}_q90"]),
                     "interval_source": "chronological pre-2022 game-anchor residuals", "market_line": line,
                     "interval_units": "home-minus-away points" if stat == "margin" else "total points",
                     "gap": value - line if line is not None else None, "line_status": "unavailable",
                     "training_cutoff_date": fit["training_cutoff_date"], "game_anchor_fit_max_season": 2021}
                if line is not None:
                    r.update(freshness(benchmark.get(stat + "_quote_time") or benchmark.get("quote_time"), now))
                    x = np.asarray(simulations["sim_independent"][stat + "_samples"])
                    summary = probability_summary(x, float(line))
                    r.update(summary)
                    if stat == "margin":
                        r["p_home_cover"] = r["p_over"]
                    r["probability_source"] = "independent structural distribution; strict cover/over; pushes separate"
                for mode in ("sim_independent", "simulator_v1"):
                    if mode in simulations:
                        label = "market_anchored" if mode == "simulator_v1" else mode
                        r[label + "_projection"] = simulations[mode][stat + "_mean"]
                        r[label + "_q10_50_90"] = simulations[mode][stat + "_q10_50_90"]
                r["structural_fit"] = "frozen v1 engine with separate Phase10 recent weighted tables; original v1 evaluation unchanged"
                game_rows.append(r)
            for row in combined[combined["game_id"] == game.game_id].to_dict("records"):
                samples, source = distribution(row, development, structural)
                if distribution_sink is not None:
                    distribution_sink(row, samples)
                q = np.quantile(samples, [.1, .5, .9])
                base = {"row_type": "player", "game_id": game.game_id, "week": game.week, "team": row["team"],
                    "pid": row["pid"], "name": row["name"], "stat": row["stat"], "variant": "independent",
                    "projection": float(row["equal"]), "weighted_projection": float(row["weighted"]),
                    "stacked_projection": float(row["stacked"]), "member_min": float(row["member_min"]),
                    "member_max": float(row["member_max"]), "members": row["members"], "q10": float(q[0]), "q50": float(q[1]),
                    "q90": float(q[2]), "interval_source": source, "calibration": row["calibration"],
                    "market_informed_projection": float(market_values.loc[(game.game_id, row["pid"], row["stat"])]),
                    "training_cutoff_date": fit["training_cutoff_date"], "market_line": None, "line_status": "unavailable"}
                base["scope"] = "regulation-only player targets; no overtime"
                base["market_informed_status"] = "structural-member comparison only; unvalidated without 2022 quote history"
                base["member_projections"] = {k: float(row[k]) for k in row["members"].split(",")}
                if row["stat"] == "anytime_td":
                    agreement = vote({k: float(row[k]) for k in row["members"].split(",")})
                    base["agreement_description"] = f"{agreement['home_votes']} of {agreement['n_models']} members above 50% TD probability; descriptive only"
                for quantile in (10, 50, 90):
                    key = f"q{quantile}"
                    base["quantile_head_" + key] = float(row[key]) if key in row and pd.notna(row[key]) else None
                if row["stat"] == "pass_tds":
                    base["passing_td_distribution"] = {str(k): float((samples == k).mean()) for k in range(5)} | {
                        "5+": float((samples >= 5).mean())}
                matched = matching_lines(lines, game, row["pid"], row["stat"])
                if matched.empty:
                    game_rows.append(base)
                else:
                    for line in matched.to_dict("records"):
                        line_value = line.get("line")
                        r = base | {"market_line": line_value, "book": line["book"], "quote_time": line["quote_time"],
                            "line_status": line["line_status"], "line_age_hours": line["line_age_hours"], "dfs": line["dfs"],
                            "over_odds": line["over_odds"], "under_odds": line["under_odds"], "market_archive": line["archive"]}
                        r["identity_mapping_source"] = line.get("identity_mapping_source")
                        if line_value is not None and np.isfinite(line_value):
                            r.update(probability_summary(samples, float(line_value)))
                            r["gap"] = base["projection"] - float(line_value)
                            if row["stat"] != "anytime_td":
                                means = [float(row[k]) for k in row["members"].split(",")]
                                r["agreement_description"] = f"{sum(v > line_value for v in means)} of {len(means)} member means above the line; descriptive only"
                            if row["stat"] == "anytime_td":
                                if line_value == .5:
                                    r.update(p_over=base["projection"], p_under=1 - base["projection"], p_push=0., p_over_no_push=base["projection"])
                                r.update(price_gap(base["projection"], line["over_odds"], line["under_odds"]))
                        game_rows.append(r)
            sim = simulations["sim_independent"]
            ids = sorted(sim["first_td"])
            first = np.array([sim["first_td"][pid] for pid in ids])
            any_rows = structural[(structural["game_id"] == game.game_id) & (structural["member"] == "sim_independent")
                                  & (structural["stat"] == "anytime_td")].drop_duplicates("pid").set_index("pid")
            td_rows = combined[(combined["game_id"] == game.game_id) & (combined["stat"] == "anytime_td")].set_index("pid")
            sa = [float(any_rows.loc[pid, "anytime_td"]) if pid in any_rows.index else 0 for pid in ids]
            ea = [float(td_rows.loc[pid, "equal"]) if pid in td_rows.index else value for pid, value in zip(ids, sa)]
            reweighted = first_td_reweight(first, sa, ea, sim["no_offensive_td"])
            names = frame[frame["game_id"] == game.game_id].drop_duplicates("pid").set_index("pid")
            for i, pid in enumerate(ids + ["no_offensive_td"]):
                first_row = {"row_type": "first_td", "game_id": game.game_id, "week": game.week, "pid": pid,
                    "name": names.loc[pid, "name"] if pid in names.index else "No offensive rushing/receiving TD" if pid == "no_offensive_td" else pid,
                    "team": names.loc[pid, "team"] if pid in names.index else None,
                    "stat": "first_td", "variant": "independent", "projection": float(reweighted[i]),
                    "structural_probability": float(first[i]) if i < len(first) else float(sim["no_offensive_td"]),
                    "training_cutoff_date": fit["training_cutoff_date"],
                    "definition": "first offensive rushing/receiving TD; passing/defensive/special-teams TDs excluded"}
                matched = matching_lines(lines, game, pid, "first_td")
                if matched.empty:
                    game_rows.append(first_row)
                else:
                    for line in matched.to_dict("records"):
                        game_rows.append(first_row | {"book": line["book"], "over_odds": line["over_odds"],
                            "under_odds": line["under_odds"], "line_status": line["line_status"], "line_age_hours": line["line_age_hours"],
                            "market_archive": line["archive"]} | price_gap(float(reweighted[i]), line["over_odds"], line["under_odds"]))
            created = pd.Timestamp.now(tz="UTC")
            if created >= game.kickoff_utc:
                raise ValueError("Game started before forecast archive could be written")
            payload = {"game_id": game.game_id, "season": 2026, "week": game.week, "generated_at": created.isoformat(),
                "kickoff": game.kickoff_utc.isoformat(), "training_cutoff_date": fit["training_cutoff_date"],
                "training_last_completed_week": fit["training_last_completed_week"], "frozen_config_sha256": config["config_sha256"],
                "code_revision": revision, "status": "unpromoted shadow reference; historical primary comparison blocked",
                "scope": "player targets/simulations regulation-only; defensive/special-teams TDs excluded; independent game heads fit final scores",
                "feature_cutoff": now.isoformat(), "rows": json.loads(pd.DataFrame(game_rows).to_json(orient="records"))}
            corrected, _ = binary_contract_corrections(pd.DataFrame(payload["rows"]))
            corrected, _ = first_td_contract_corrections(corrected)
            payload["rows"] = json.loads(corrected.to_json(orient="records"))
            payload["rows_sha256"] = hashlib.sha256(json.dumps(payload["rows"], sort_keys=True).encode()).hexdigest()
            with archive_path.open("x", encoding="utf-8") as fh:
                json.dump(payload, fh, allow_nan=False)
            rows.extend(payload["rows"])
            archived.append(game.game_id)
            log(f"archived projections {game.game_id}: {len(game_rows)} rows")
        except Exception as exc:
            errors.append({"game_id": game.game_id, "error": repr(exc)})
            log(f"FAILED projection {game.game_id}: {exc}; skipped")
    table = pd.DataFrame(rows)
    paths = []
    for w, group in table.groupby("week") if len(table) else []:
        paths.extend(write_sheet(group, int(w)))
    return {"archived": archived, "errors": errors, "reports": paths}


def write_sheet(frame, week):
    from .amendment2.sheets import skew_flags
    frame = skew_flags(frame)
    nonnegative = frame["stat"].isin(["pass_yds", "pass_tds", "rush_yds", "rec_yds", "rec", "anytime_td", "total"])
    for key in ("q10", "q50", "q90", "quantile_head_q10", "quantile_head_q50", "quantile_head_q90"):
        if key in frame:
            frame.loc[nonnegative, key] = pd.to_numeric(frame.loc[nonnegative, key], errors="coerce").clip(lower=0)
    frame, corrections = binary_contract_corrections(frame)
    if len(corrections):
        directory = OUT / "forecast_corrections"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"binary_contract_scope_v1_2026_w{week}.json"
        if not path.exists():
            record = {"recorded_at": pd.Timestamp.now(tz="UTC").isoformat(), "correction": "benchmark comparison only; model forecasts unchanged",
                      "reason": "Binary TD>=1 / first-TD targets cannot price a TD-count line other than 0.5",
                      "record_key_fields": ["game_id", "pid", "stat", "book", "market_line"],
                      "cleared_fields": {k: None for k in ("p_over", "p_under", "p_push", "p_over_no_push", "gap", "market_probability")},
                      "original_rows": json.loads(corrections.to_json(orient="records"))}
            with path.open("x", encoding="utf-8") as fh:
                json.dump(record, fh, allow_nan=False)
    frame, first_corrections = first_td_contract_corrections(frame)
    if len(first_corrections):
        directory = OUT / "forecast_corrections"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"first_td_settlement_scope_v1_2026_w{week}.json"
        if not path.exists():
            record = {"recorded_at": pd.Timestamp.now(tz="UTC").isoformat(), "correction": "benchmark comparison only; model forecasts unchanged",
                      "reason": "Quote settlement is not verified to match first offensive rushing/receiving TD in regulation",
                      "record_key_fields": ["game_id", "pid", "stat", "book"],
                      "cleared_fields": {k: None for k in ("p_over", "p_under", "p_push", "p_over_no_push", "gap", "market_probability")},
                      "original_rows": json.loads(first_corrections.to_json(orient="records"))}
            with path.open("x", encoding="utf-8") as fh:
                json.dump(record, fh, allow_nan=False)
    stem = REPORTS_DIR / f"projections_2026_w{week}"
    frame.to_csv(stem.with_suffix(".csv"), index=False)
    columns = ["name", "stat", "projection", "q10", "q50", "q90", "market_line", "p_over", "gap", "line_status"]
    lines = [f"# NFL shadow projections — 2026 week {week}", "", "Training cutoff: " + str(frame["training_cutoff_date"].iloc[0]), "",
        "Independent projections exclude market inputs. Market-anchored outputs are benchmarks. Unpromoted experimental forecasts.", "",
        "Margin intervals use home-minus-away points; the spread display is the favored team's handicap. Player intervals describe outcomes; anytime-TD quantiles are binary outcomes, not confidence bounds on the probability.", "",
        "TD-count quote thresholds other than 0.5 are not comparable to binary anytime/first-TD forecasts; their over probabilities and gaps are unavailable.", "",
        "First-TD quote settlement rules are unverified against our offensive-only regulation target; price comparisons are unavailable.", "",
        "First TD means the first offensive rushing/receiving TD in regulation; excludes passing, defensive and special-teams TDs.", ""]
    for gid, game in frame.groupby("game_id", sort=False):
        lines += ["## " + gid, "", "| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for row in game.to_dict("records"):
            def display(value):
                if value is None or (isinstance(value, float) and not np.isfinite(value)):
                    return "—"
                return f"{value:.3f}" if isinstance(value, float) else str(value)
            lines.append("| " + " | ".join(display(row.get("spread_display") if c == "projection" and row.get("stat") == "margin" else row.get(c)) for c in columns) + " |")
        lines.append("")
    stem.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    payload = {"week": week, "training_cutoff_date": str(frame["training_cutoff_date"].iloc[0]),
               "rows": json.loads(frame.to_json(orient="records"))}
    stem.with_suffix(".json").write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    paths = [str(stem.with_suffix(".csv")), str(stem.with_suffix(".md"))]
    # Optional local Artifact Tool export. CSV/Markdown do not depend on Node.
    # The configured runtime is provided by Codex; no package is downloaded.
    node = os.environ.get("NFL_LAB_ARTIFACT_NODE")
    workspace = os.environ.get("NFL_LAB_ARTIFACT_WORKSPACE")
    if node and workspace:
        completed = subprocess.run([node, str(LAB_ROOT / "scripts" / "projections_xlsx.mjs"),
                                    str(stem.with_suffix(".json")), workspace], cwd=LAB_ROOT, check=False,
                                    capture_output=True, text=True, encoding="utf-8")
        if completed.returncode == 0 and stem.with_suffix(".xlsx").exists():
            paths.append(str(stem.with_suffix(".xlsx")))
        else:
            (REPORTS_DIR / "run_20261019" / f"xlsx_w{week}_error.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return paths
