"""Research-only opportunity -> efficiency forecasts. No odds or win probabilities.

Raw profile archives without exact appearance/receipt identity are intentionally
unsupported. Training and forecast functions accept sanitized caller-supplied rows;
this module never downloads data or loads private files.
"""
from datetime import datetime
import math

SCHEMA = "going-props-opportunity-prior-v1"
MARKETS = {
    "pass_yds": ("attempts", "pass_yds"),
    "pass_tds": ("attempts", "pass_tds"),
    "receptions": ("targets", "receptions"),
    "rec_yds": ("targets", "receptions", "rec_yds"),
    "rush_yds": ("carries", "rush_yds"),
}


def _time(value):
    if not isinstance(value, str):
        raise ValueError("Explicit timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return parsed.timestamp()


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _rows(rows, market, cutoff):
    if market not in MARKETS or not isinstance(rows, list):
        raise ValueError("Unsupported market or appearance input")
    seen, out = set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed appearance")
        for key in ("player_id", "team", "game_id", "position"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError("Exact appearance identity required")
        if not isinstance(row.get("season"), int) or isinstance(row["season"], bool):
            raise ValueError("Explicit season required")
        kick, at = _time(row.get("kickoff")), _time(row.get("available_at"))
        if at <= kick:
            raise ValueError("Outcome receipt must follow kickoff")
        if kick >= cutoff or at >= cutoff:
            # Future/late receipt rows never enter either fitting or prediction.
            continue
        if row.get("game_type") != "REG" or row.get("completed") is not True:
            raise ValueError("Completed regular-season appearance required")
        if row.get("participated") is not True:
            raise ValueError("Participation must be explicitly verified")
        identity = (row["player_id"], row["game_id"])
        if identity in seen:
            raise ValueError("Duplicate athlete-game appearance")
        seen.add(identity)
        if market.startswith("pass_"):
            if row["position"] != "QB":
                raise ValueError("Passing forecast requires a QB")
            if row.get("verified_start") is not True:
                continue
        fields = MARKETS[market]
        if any(not _finite(row.get(f)) for f in fields):
            raise ValueError("Observed opportunity/efficiency feature missing")
        count_fields = {fields[0]} | ({"receptions"} if "receptions" in fields else set()) | ({"pass_tds"} if market == "pass_tds" else set())
        if any(row[f] < 0 or not float(row[f]).is_integer() for f in count_fields):
            raise ValueError("Opportunity/count observations must be nonnegative integers")
        if "receptions" in fields and row["receptions"] > row["targets"]:
            raise ValueError("Catches exceed targets")
        if market == "pass_tds" and row["pass_tds"] > row["attempts"]:
            raise ValueError("Passing touchdowns exceed attempts")
        if row[fields[0]] == 0 and any(row[f] != 0 for f in fields[1:]):
            raise ValueError("Production without observed opportunity")
        if market == "rec_yds" and row["receptions"] == 0 and row["rec_yds"] != 0:
            raise ValueError("Receiving yards without a reception")
        out.append(row)
    return sorted(out, key=lambda r: (_time(r["kickoff"]), r["game_id"]))


def fit_prior(rows, *, market, position, trained_through, demand_prior_games,
              efficiency_prior_opportunities):
    """Fit aggregate training priors with caller-declared frozen regularization.

    This does not select hyperparameters or evaluate the holdout. Training rows
    may span seasons; current player form used in predict() never does.
    """
    cutoff = _time(trained_through)
    if not position or any(not _finite(x) or x <= 0 for x in (demand_prior_games, efficiency_prior_opportunities)):
        raise ValueError("Positive declared prior strengths required")
    selected = [r for r in _rows(rows, market, cutoff) if r["position"] == position]
    if not selected:
        raise ValueError("No complete earlier training appearances")
    opp = sum(r[MARKETS[market][0]] for r in selected)
    if opp <= 0:
        raise ValueError("Training opportunity unavailable")
    rates = {MARKETS[market][1]: sum(r[MARKETS[market][1]] for r in selected) / opp}
    if market == "rec_yds":
        catches = sum(r["receptions"] for r in selected)
        if catches <= 0:
            raise ValueError("Training yards-per-catch exposure unavailable")
        rates["yards_per_catch"] = sum(r["rec_yds"] for r in selected) / catches
    return {"schema": SCHEMA, "market": market, "position": position,
            "trained_through": trained_through, "training_seasons": sorted({r["season"] for r in selected}),
            "training_appearances": len(selected), "training_players": len({r["player_id"] for r in selected}),
            "demand_mean": opp / len(selected), "rates": rates,
            "demand_prior_games": demand_prior_games,
            "efficiency_prior_opportunities": efficiency_prior_opportunities,
            "regularization_status": "caller-frozen sensitivity; not a validated optimum"}


def predict(rows, *, player_id, team, position, season, market, decision_at,
            roster_at, roster_verified, prior):
    """Forecast from exact current-team appearances or return an explicit blocker."""
    def blocked(reason):
        return {"status": "withheld", "market": market, "mean": None, "reason": reason}
    try:
        decision = _time(decision_at)
        if not roster_verified or not player_id or not team or _time(roster_at) >= decision or decision-_time(roster_at) > 86400:
            return blocked("Fresh exact-team roster verification required")
        if not isinstance(season, int) or isinstance(season, bool) or market not in MARKETS:
            return blocked("Supported market and explicit forecast season required")
        if not isinstance(prior, dict) or prior.get("schema") != SCHEMA or prior.get("market") != market or prior.get("position") != position or _time(prior.get("trained_through")) >= decision:
            return blocked("Matching earlier training artifact required")
        if any(not _finite(prior.get(k)) or prior[k] <= 0 for k in ("demand_mean", "demand_prior_games", "efficiency_prior_opportunities")):
            return blocked("Malformed demand/prior coefficients")
        rates = prior.get("rates", {})
        needed = [MARKETS[market][1]] + (["yards_per_catch"] if market == "rec_yds" else [])
        if any(not _finite(rates.get(k)) for k in needed):
            return blocked("Observed training efficiency coefficients required")
        if market in ("receptions", "rec_yds", "pass_tds") and not 0 <= rates[MARKETS[market][1]] <= 1:
            return blocked("Invalid count/target efficiency prior")
        # Exact-player rows only; no missing identity can be guessed from a profile.
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get("player_id") for r in rows):
            return blocked("Exact per-appearance player identity required")
        player_rows = [r for r in rows if r["player_id"] == player_id and r.get("season") == season]
        current = _rows(player_rows, market, decision)
        if any(r["position"] != position for r in current):
            return blocked("Contradictory current player position")
        # A return/trade cannot reuse earlier appearances on a previous stint.
        last_other = max((_time(r["kickoff"]) for r in current if r["team"] != team), default=-math.inf)
        current = [r for r in current if r["team"] == team and _time(r["kickoff"]) > last_other]
        if len(current) < 2:
            return blocked("At least two complete current-team current-season appearances required")
        fields = MARKETS[market]
        opp = sum(r[fields[0]] for r in current)
        if opp <= 0:
            return blocked("Observed current opportunity unavailable")
        n, dg, strength = len(current), prior["demand_prior_games"], prior["efficiency_prior_opportunities"]
        demand = (opp + dg*prior["demand_mean"]) / (n+dg)
        first = (sum(r[fields[1]] for r in current) + strength*rates[fields[1]]) / (opp+strength)
        efficiency = first
        stages = {fields[1]+"_per_"+fields[0]: first}
        if market == "rec_yds":
            catches = sum(r["receptions"] for r in current)
            ypc = (sum(r["rec_yds"] for r in current)+strength*rates["yards_per_catch"]) / (catches+strength)
            efficiency *= ypc
            stages["yards_per_catch"] = ypc
        mean = demand*efficiency
        if not math.isfinite(mean):
            return blocked("Nonfinite forecast")
        return {"status": "experimental", "market": market, "player_id": player_id,
                "team": team, "season": season, "mean": mean, "demand": demand,
                "efficiency_stages": stages, "current_games": n, "observed_opportunity": opp,
                "latest_game": current[-1]["game_id"], "latest_receipt": max(r["available_at"] for r in current),
                "prior_trained_through": prior["trained_through"],
                "uncertainty": "Not calibrated; residual distribution and win probability withheld",
                "limitation": "Two-stage shrinkage is research-only; no matchup/price or profitability claim"}
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return blocked(str(error))
