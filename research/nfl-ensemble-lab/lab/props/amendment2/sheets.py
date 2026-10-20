"""Pure quote-contract, consensus, coherence and investigation-readiness rules."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from ..projections10 import price_gap, probability_summary

EXCHANGES = ("novig", "betfair", "smarkets", "sporttrade", "matchbook", "prophet", "kalshi", "polymarket")
DFS = ("underdog", "prizepicks", "sleeper", "chalkboard", "pick6")
KEY = ["game_id", "pid", "stat"]


def skew_flags(frame):
    """Presentation guard only; never changes an archived prediction."""
    d = frame.copy()
    mean = pd.to_numeric(d.get("our_mean", d.get("projection", pd.Series(index=d.index, dtype=float))), errors="coerce")
    median = pd.to_numeric(d.get("our_median", d.get("q50", pd.Series(index=d.index, dtype=float))), errors="coerce")
    line = pd.to_numeric(d.get("market_line", d.get("consensus_line", pd.Series(index=d.index, dtype=float))), errors="coerce")
    d["skew_artifact_flag"] = ((mean-line)*(median-line)).lt(0).fillna(False)
    return d


def classify(book, dfs=False):
    name = str(book or "").lower().replace(" ", "")
    if bool(dfs) or any(k in name for k in DFS):
        return "DFS-pickem"
    if any(k in name for k in EXCHANGES):
        return "exchange"
    return "alternate"


def consensus(frame):
    d = frame.copy()
    if "pid" not in d:
        d["pid"] = ""
    d["pid"] = d.pid.fillna("")
    if "dfs" not in d:
        d["dfs"] = False
    if "book" not in d:
        d["book"] = None
    d["line_type"] = [classify(b, bool(f) if pd.notna(f) else False) for b, f in zip(d.book, d.dfs)]
    d["consensus_line"], d["is_consensus_representative"] = np.nan, False
    for _, z in d.groupby(KEY, dropna=False, sort=False):
        traditional = z[z.line_type.eq("alternate") & z.market_line.notna() & z.book.notna()]
        votes = traditional.drop_duplicates(["book", "market_line"]).market_line.value_counts()
        if votes.empty:
            continue
        value = float(min(votes[votes.eq(votes.max())].index))
        d.loc[z.index, "consensus_line"] = value
        match = traditional[traditional.market_line.eq(value)]
        d.loc[match.index, "line_type"] = "consensus"
        representative = match.sort_values("book", kind="stable").index[0]
        d.loc[representative, "is_consensus_representative"] = True
    d["consensus_rule"] = "mode of latest unique traditional book lines; exclude DFS/exchanges; smallest numerical line breaks ties; alphabetically first representative book"
    # Contract compatibility is already represented by benchmark_scope_status.
    compatible = d.get("benchmark_scope_status", pd.Series(index=d.index, dtype=object)).isna()
    comparable = d.line_type.eq("consensus") & compatible
    if "gap" in d:
        d.loc[~comparable, "gap"] = np.nan
    return d


def compare(frame, distributions):
    """Reprice fixed archived distributions; never refit from new market quotes."""
    d = frame.copy()
    for col in ("p_over", "p_under", "p_push", "p_over_no_push", "gap", "market_probability", "no_vig_market_probability"):
        d[col] = np.nan
    d["market_probability_basis"] = "unavailable"
    for index, row in d.iterrows():
        stat, line = row.stat, row.get("market_line")
        if stat == "first_td":
            d.loc[index, "benchmark_scope_status"] = "first-TD settlement unverified against offensive-only regulation target"
            continue
        if pd.isna(line):
            continue
        if stat == "anytime_td" and line != .5:
            d.loc[index, "benchmark_scope_status"] = "binary ATD cannot price a multi-TD count contract"
            continue
        samples = distributions.get((row.game_id, str(row.get("pid") or ""), stat))
        if stat == "anytime_td":
            d.loc[index, ["p_over", "p_under", "p_push"]] = [row.projection, 1-row.projection, 0.]
            d.loc[index,"p_over_no_push"] = row.projection
        elif samples is not None:
            values = probability_summary(samples, float(line))
            for key in ("p_over", "p_under", "p_push", "p_over_no_push"):
                d.loc[index, key] = values[key]
        else:
            continue
        probability = float(d.loc[index, "p_over"])
        over, under = row.get("over_odds"), row.get("under_odds")
        over = float(over) if pd.notna(over) else None
        under = float(under) if pd.notna(under) else None
        gap = price_gap(probability, over, under)
        d.loc[index, "market_probability"] = gap.get("market_probability", np.nan)
        d.loc[index, "market_probability_basis"] = gap.get("gap_units", "unavailable")
        if over is not None and under is not None and abs(over) >= 100 and abs(under) >= 100:
            d.loc[index, "no_vig_market_probability"] = gap.get("market_probability", np.nan)
        if row.line_type == "consensus":
            d.loc[index, "gap"] = gap.get("gap", np.nan) if stat == "anytime_td" else row.projection-line
    return d


def coherence(frame, team_totals):
    """Report player eligibility gaps; never reconcile model outputs."""
    players = frame[frame.row_type.eq("player")].drop_duplicates(KEY)
    rows = []
    for (gid, team), d in players.groupby(["game_id", "team"]):
        totals = team_totals.get(gid, {}).get(team)
        if not totals:
            rows.append({"game_id": gid, "team": team, "coherence_flag": "unknown: team totals unavailable"})
            continue
        row = {"game_id": gid, "team": team, "coherence_flag": "coherent"}
        flags = []
        for stat in ("pass_yds", "rush_yds", "rec_yds", "rec", "pass_tds"):
            value = float(d.loc[d.stat.eq(stat), "projection"].sum())
            target = float(totals[stat])
            row["player_"+stat], row["team_"+stat], row["gap_"+stat] = value, target, value-target
            if abs(value-target)/max(abs(target),1) > .15:
                flags.append(stat+" eligible-player sum gap")
        row["team_passing_receiving_gap"] = totals["pass_yds"]-totals["rec_yds"]
        row["team_completions"] = totals["rec"]
        row["expected_offensive_td_count"] = totals["rush_tds"]+totals["rec_tds"]
        row["all_player_expected_td_scorers"] = totals["anytime_td"]
        row["eligible_player_atd_sum"] = float(d.loc[d.stat.eq("anytime_td"), "projection"].sum())
        row["atd_vs_td_count_gap"] = row["eligible_player_atd_sum"]-row["expected_offensive_td_count"]
        row["atd_semantics"] = "sum P(TD>=1) is expected unique scorers, not TD count; multiple TDs per player explain part of gap"
        if abs(row["team_passing_receiving_gap"]) > 1:
            flags.append("simulator passing/receiving accounting")
        if abs(row["atd_vs_td_count_gap"]) > .5:
            flags.append("ATD scorer/count definition or calibration gap")
        row["coherence_flag"] = "; ".join(flags) if flags else "coherent"
        rows.append(row)
    table = pd.DataFrame(rows)
    result = frame.merge(table[["game_id", "team", "coherence_flag"]], on=["game_id", "team"], how="left", validate="many_to_one")
    # A game needs both teams' accounting to be ready for the highest tier.
    game_flags = table.groupby("game_id").coherence_flag.agg(lambda x: "coherent" if x.eq("coherent").all() and len(x)==2 else "team coherence gaps")
    mask = result.row_type.eq("game")
    result.loc[mask, "coherence_flag"] = result.loc[mask, "game_id"].map(game_flags)
    return result, table


def leans(frame, stability, scenarios):
    d = frame.copy()
    d["our_mean"] = d.projection
    d["our_median"] = d.get("q50", np.nan)
    binary = d.stat.isin(["anytime_td", "first_td"])
    d.loc[binary, "our_median"] = np.nan
    d["median_note"] = np.where(binary, "binary/categorical probability; no continuous median", "predictive median")
    d["stability_flag"] = [stability.get((r.game_id, str(r.pid or ""), r.stat), "unknown") for r in d.itertuples()]
    d["scenario_sensitivity"] = [scenarios.get((r.game_id, str(r.pid or ""), r.stat), "unknown") for r in d.itertuples()]
    d["members_agree"] = False
    d["member_agreement"] = "comparable threshold unavailable; not a probability"
    for index, r in d.iterrows():
        threshold = r.get("market_probability") if r.stat in ("anytime_td", "first_td") else r.get("market_line")
        lo, hi = r.get("member_min"), r.get("member_max")
        if pd.notna(threshold) and pd.notna(lo) and pd.notna(hi):
            d.loc[index, "members_agree"] = bool(lo>threshold or hi<threshold)
            d.loc[index,"member_agreement"] = ("all member means on one side" if lo>threshold or hi<threshold else "member means disagree")+"; descriptive, not a probability"
    compatible = d.get("benchmark_scope_status", pd.Series(index=d.index, dtype=object)).isna()
    ready = d.line_type.eq("consensus") & d.line_status.eq("current") & compatible & d.gap.notna()
    strong = ready & d.stability_flag.eq("stable") & d.coherence_flag.eq("coherent") & d.members_agree & d.scenario_sensitivity.eq("robust")
    d["confidence_tier"] = np.select([strong, ready], ["A", "B"], default="C")
    d["investigation_note"] = ["; ".join(["projection differs from consensus; investigate assumptions" if pd.notna(r.gap) else "no compatible consensus comparison",
        "invalidators: late lineup news, role changes, stale prices, overtime/settlement mismatch, model/distribution error",
        "precision="+str(r.stability_flag), "coherence="+str(r.coherence_flag), "scenarios="+str(r.scenario_sensitivity),
        "unvalidated shadow model; no bet or stake recommendation"]) for r in d.itertuples()]
    width = (pd.to_numeric(d.get("q90"),errors="coerce")-pd.to_numeric(d.get("q10"),errors="coerce")).clip(lower=1)
    d["investigation_rank_score"] = abs(d.gap)/width
    d.loc[binary, "investigation_rank_score"] = abs(d.loc[binary,"gap"])
    d["investigation_rank_score"] = d.investigation_rank_score.fillna(-1)
    d = d.sort_values(["game_id", "confidence_tier", "investigation_rank_score"], ascending=[True,True,False], kind="stable")
    d["rank_in_game"] = d.groupby("game_id").cumcount()+1
    return d


def export(frame, stem, *, heading, context=""):
    frame = skew_flags(frame)
    stem.parent.mkdir(parents=True, exist_ok=True)
    # CSV is the lab's machine-readable data contract, not a workbook redesign.
    frame.to_csv(stem.with_suffix(".csv"), index=False)
    candidates=("rank_in_game", "name", "stat", "spread_display", "consensus_spread_display", "consensus_line",
        "our_mean" if "our_mean" in frame else "projection", "our_median" if "our_median" in frame else "q50", "q10", "q90",
        "p_over", "p_under", "no_vig_market_probability", "member_min", "member_max", "member_agreement", "stability_flag",
        "line_type", "line_status", "confidence_tier", "coherence_flag", "scenario_sensitivity", "investigation_note")
    cols = [c for c in candidates if c in frame]
    lines = ["# "+heading, "", context, "", "Confidence is investigation-readiness, not predictive accuracy. No validated advantage over closing markets has been established. Structural seed stability does not validate learned-member error or calibration.", "",
        "A: current compatible consensus, stable, coherent, all member means on one side, all required scenarios available and robust. B: current compatible consensus with uncertainty. C: stale, missing, nonconsensus or incompatible. First TD is offensive rushing/receiving in regulation; quote settlement is unverified, so price gaps are unavailable. Binary outcome quantiles are not confidence intervals on probabilities.", "",
        "Consensus rule: modal latest line across traditional books, excluding DFS/exchanges; lowest line breaks ties, alphabetical representative. Only consensus rows have gaps. Sum ATD probabilities counts expected distinct scorers, not total TDs. Game margins/lines use home minus away; spread_display gives team plus signed handicap. P(over/under) is strict; p_over_no_push conditions on no push.", ""]
    for gid, group in frame.groupby("game_id", sort=False):
        lines += ["## "+gid, "", "| "+" | ".join(cols)+" |", "| "+" | ".join(["---"]*len(cols))+" |"]
        for _, row in group.iterrows():
            def display(v):
                if v is None or (isinstance(v, (float,np.floating)) and not np.isfinite(v)):
                    return "unavailable"
                return f"{v:.3f}" if isinstance(v,(float,np.floating)) else str(v).replace("|", "/")
            lines.append("| "+" | ".join(display(row[c]) for c in cols)+" |")
        lines.append("")
    stem.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
