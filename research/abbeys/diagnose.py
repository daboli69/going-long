"""Offline, current-season-only NFL score-method diagnostic. No network or odds."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import json
import math
import random

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "nfl_betting.json"
EXPECTED_SHA256 = "2b30cffe0399403dac23baf9230ec7f4b3e6486b0aa86f23b8d56909c65c19ca"
OUTPUT = Path(__file__).with_name("diagnostic-20261003.json")


def read_games():
    raw = INPUT.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Schedule snapshot differs from registered input hash")
    doc = json.loads(raw)
    games = defaultdict(list)
    seen = set()
    for row in doc["games"]:
        season, week = row.get("season"), row.get("week")
        if season not in (2024, 2025, 2026) or not isinstance(week, int) or not 1 <= week <= 18:
            continue
        gid = row.get("game_id")
        if not gid or gid in seen:
            raise ValueError(f"Duplicate or missing game ID: {gid}")
        seen.add(gid)
        home, away = row.get("home"), row.get("away")
        if not home or not away or home == away:
            raise ValueError(f"Invalid teams: {gid}")
        kickoff = datetime.fromisoformat(row["kickoff"].replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            raise ValueError(f"Timezone missing: {gid}")
        hs, aws = row.get("home_score"), row.get("away_score")
        completed = hs is not None and aws is not None
        if (hs is None) != (aws is None) or any(
            not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0
            for x in (hs, aws) if x is not None
        ):
            raise ValueError(f"Invalid scores: {gid}")
        games[season].append(dict(id=gid, week=week, kickoff=kickoff, home=home,
                                  away=away, hs=hs, aws=aws, completed=completed))
    for season in games:
        games[season].sort(key=lambda x: (x["week"], x["kickoff"], x["id"]))
    return games, digest, doc.get("generated_at")


def baseline(train, game, recent=False):
    if recent:
        last_week = max(x["week"] for x in train)
        base = [x for x in train if x["week"] >= last_week - 3]
    else:
        base = train
    mu = sum(x["hs"] + x["aws"] for x in base) / (2 * len(base))
    h = sum(x["hs"] - x["aws"] for x in base) / len(base)

    def team_mean(team, field):
        rows = [x for x in train if x["home"] == team or x["away"] == team]
        if recent:
            rows = rows[-4:]
        if not rows:
            return mu
        vals = [(x["hs"] if x["home"] == team else x["aws"])
                if field == "for" else
                (x["aws"] if x["home"] == team else x["hs"])
                for x in rows]
        return sum(vals) / len(vals)

    home = (team_mean(game["home"], "for") + team_mean(game["away"], "against")) / 2 + h / 2
    away = (team_mean(game["away"], "for") + team_mean(game["home"], "against")) / 2 - h / 2
    return home, away


def adjusted_fit(train, teams):
    """OLS with sum-to-zero offense/defense via last-team reference coding."""
    ordered = sorted(teams)
    index = {team: i for i, team in enumerate(ordered)}
    n = len(ordered)
    if n != 32:
        return None, {"rank": None, "columns": 2 * n, "reason": "team_universe_not_32"}
    rows, y = [], []

    def effect(vector, team, offset):
        i = index[team]
        if i == n - 1:
            vector[offset:offset+n-1] = -1
        else:
            vector[offset+i] = 1

    for g in train:
        for scoring, opponent, score, venue in (
            (g["home"], g["away"], g["hs"], .5),
            (g["away"], g["home"], g["aws"], -.5),
        ):
            row = np.zeros(2*n)
            row[0], row[1] = 1, venue
            effect(row, scoring, 2)
            effect(row, opponent, n+1)
            rows.append(row)
            y.append(score)
    design = np.asarray(rows)
    rank = int(np.linalg.matrix_rank(design))
    meta = {"rank": rank, "columns": 2*n, "training_games": len(train)}
    if rank < 2*n:
        return None, meta
    coefficients = np.linalg.lstsq(design, np.asarray(y), rcond=None)[0]
    return (coefficients, ordered), meta


def adjusted_predict(fit, game):
    coefficients, teams = fit
    n = len(teams)
    index = {team: i for i, team in enumerate(teams)}

    def effect(team, offset):
        i = index[team]
        return -sum(coefficients[offset:offset+n-1]) if i == n-1 else coefficients[offset+i]

    home = coefficients[0] + coefficients[1]/2 + effect(game["home"], 2) + effect(game["away"], n+1)
    away = coefficients[0] - coefficients[1]/2 + effect(game["away"], 2) + effect(game["home"], n+1)
    return float(max(0, home)), float(max(0, away)), bool(home < 0 or away < 0)


def predictions(games, season):
    season_games = games[season]
    teams = {x["home"] for x in season_games} | {x["away"] for x in season_games}
    weekly = defaultdict(list)
    for game in season_games:
        weekly[game["week"]].append(game)
    output = []
    for week, targets in sorted(weekly.items()):
        if week < 4:
            continue
        if season == 2026 and week > 4:
            continue  # prospective holdout: no later-week estimates from stale data
        origin = min(x["kickoff"] for x in targets) - timedelta(hours=12)
        train = [x for x in season_games if x["completed"] and x["week"] < week
                 and x["kickoff"] + timedelta(hours=12) < origin]
        counts = Counter(team for x in train for team in (x["home"], x["away"]))
        fit, meta = adjusted_fit(train, teams) if train else (None, {"rank": 0, "columns": 64})
        for game in targets:
            n = min(counts[game["home"]], counts[game["away"]])
            row = {"id": game["id"], "week": week, "origin": origin.isoformat(),
                   "min_team_games": n, "completed": game["completed"],
                   "rank": meta["rank"], "columns": meta["columns"]}
            if n >= 3:
                row["B"] = baseline(train, game)
                row["R"] = baseline(train, game, recent=True)
                if fit:
                    row["C"] = adjusted_predict(fit, game)
            if season in (2024, 2025) and game["completed"]:
                row["actual"] = (game["hs"], game["aws"])
            output.append(row)
    return output


def metric(rows, method, kind):
    def errors(row):
        p, a = row[method], row["actual"]
        if kind == "margin":
            return [(p[0] - p[1]) - (a[0] - a[1])]
        if kind == "total":
            return [(p[0] + p[1]) - (a[0] + a[1])]
        return [p[0]-a[0], p[1]-a[1]]
    vals = [e for row in rows for e in errors(row)]
    return {"rmse": math.sqrt(sum(e*e for e in vals)/len(vals)),
            "mae": sum(abs(e) for e in vals)/len(vals),
            "bias": sum(vals)/len(vals)}


def summarize(rows, challenger, seed):
    paired = [x for x in rows if "actual" in x and "B" in x and challenger in x]
    if not paired:
        return {"paired_games": 0}
    out = {"paired_games": len(paired), "weekly_clusters": len({x["week"] for x in paired}),
           "B": {k: metric(paired, "B", k) for k in ("margin", "score", "total")},
           challenger: {k: metric(paired, challenger, k) for k in ("margin", "score", "total")}}
    for method in ("B", challenger):
        eligible = [x for x in paired if x["actual"][0] != x["actual"][1]
                    and x[method][0] != x[method][1]]
        out[method]["winner"] = {"correct": sum(
            (x[method][0] > x[method][1]) == (x["actual"][0] > x["actual"][1]) for x in eligible),
            "denominator": len(eligible)}
        out[method]["rounded_exact_scores"] = sum(
            tuple(round(v) for v in x[method][:2]) == tuple(x["actual"]) for x in paired)
    byweek = defaultdict(list)
    for row in paired:
        byweek[row["week"]].append(row)
    keys = sorted(byweek)
    rng = random.Random(seed)
    out["paired_rmse_improvement_95_week_bootstrap"] = {}
    for kind in ("margin", "score", "total"):
        draws = []
        for _ in range(2000):
            sample = [row for _ in keys for row in byweek[rng.choice(keys)]]
            draws.append(metric(sample, "B", kind)["rmse"] - metric(sample, challenger, kind)["rmse"])
        draws.sort()
        out["paired_rmse_improvement_95_week_bootstrap"][kind] = [draws[49], draws[1949]]
    return out


def main():
    games, digest, generated = read_games()
    report = {"status": "RETROSPECTIVE_DIAGNOSTIC_ONLY", "source_sha256": digest,
              "source_generated_at": generated, "source_revision": "2b3d85355c144017594b7b240a434571e57c5767",
              "holdout_2026_weeks_5_18": "LOCKED_UNTIL_2027-01-09_12_ET",
              "seasons": {}}
    for season in (2024, 2025, 2026):
        rows = predictions(games, season)
        coverage = Counter("no_three_games" if "B" not in x else
                           "B_only_rank_deficient" if "C" not in x else "paired"
                           for x in rows)
        item = {"scheduled_week4_plus": len(rows), "coverage": dict(coverage),
                "week4_counts": dict(Counter("no_three_games" if "B" not in x else
                                             "B_only_rank_deficient" if "C" not in x else "paired"
                                             for x in rows if x["week"] == 4))}
        if season in (2024, 2025):
            item["B_vs_C"] = summarize(rows, "C", 20261003+season)
            item["B_vs_R_exploratory"] = summarize(rows, "R", 20261013+season)
        report["seasons"][str(season)] = item
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "coverage": {k:v["coverage"] for k,v in report["seasons"].items()}}, indent=2))


if __name__ == "__main__":
    main()
