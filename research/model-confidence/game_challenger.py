"""Current-season opponent adjustment, isolated from production forecasting.

Fixed-policy ridge attack/prevention ratings; no market line enters fitting.
Public historical scores are revised data, not immutable contemporaneous feeds.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean
from zoneinfo import ZoneInfo

ALPHA = 3.0
VENUE_PRIOR = 64.0
ITERATIONS = 24


def centered_ridge(numerators, counts):
    """Exact zero-sum constrained ridge block, including unequal team counts."""
    denominators = {t: counts[t]+ALPHA for t in numerators}
    lagrange = sum(numerators[t]/denominators[t] for t in numerators)/sum(1/d for d in denominators.values())
    return {t: (numerators[t]-lagrange)/denominators[t] for t in numerators}


def load_games(path):
    result = []
    seen = set()
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['game_type'] != 'REG' or not 2016 <= int(r['season']) <= 2025:
                continue
            if not all(r.get(k) for k in ['gametime', 'home_score', 'away_score']):
                continue
            if r['game_id'] in seen:
                raise ValueError('Duplicate game identity')
            seen.add(r['game_id'])
            kickoff = datetime.fromisoformat(r['gameday']+'T'+r['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).timestamp()
            result.append(dict(id=r['game_id'], season=int(r['season']), week=int(r['week']),
                               kickoff=kickoff, home=r['home_team'], away=r['away_team'],
                               home_score=float(r['home_score']), away_score=float(r['away_score']),
                               neutral=r['location'] == 'Neutral',
                               margin_close=float(r['spread_line']) if r['spread_line'] else None,
                               total_close=float(r['total_line']) if r['total_line'] else None))
    return sorted(result, key=lambda g: (g['kickoff'], g['id']))


def fit(games, season, cutoff):
    """Only current-season scores conservatively available before cutoff."""
    rows = [g for g in games if g['season'] == season and g['kickoff']+43200 < cutoff]
    if not rows:
        return None
    scored, allowed = defaultdict(list), defaultdict(list)
    observations = []
    for g in rows:
        for team, opp, points, conceded, venue in [(g['home'],g['away'],g['home_score'],g['away_score'],0 if g['neutral'] else .5), (g['away'],g['home'],g['away_score'],g['home_score'],0 if g['neutral'] else -.5)]:
            if not all(math.isfinite(x) and x >= 0 for x in (points,conceded)):
                raise ValueError('Invalid completed scores')
            scored[team].append(points); allowed[team].append(conceded)
            observations.append((team,opp,points,venue))
    league = mean(x[2] for x in observations)
    venue_rows = [g for g in rows if not g['neutral']]
    home_adv = sum(g['home_score']-g['away_score'] for g in venue_rows)/(len(venue_rows)+VENUE_PRIOR)
    teams = sorted(scored)
    attack = dict.fromkeys(teams,0.0); defense = dict.fromkeys(teams,0.0)
    offense_rows = {t:[r for r in observations if r[0] == t] for t in teams}
    defense_rows = {t:[r for r in observations if r[1] == t] for t in teams}
    for _ in range(ITERATIONS):
        attack = centered_ridge({t:sum(points-league-venue*home_adv-defense[opp] for _,opp,points,venue in offense_rows[t]) for t in teams}, {t:len(offense_rows[t]) for t in teams})
        defense = centered_ridge({t:sum(points-league-venue*home_adv-attack[off] for off,_,points,venue in defense_rows[t]) for t in teams}, {t:len(defense_rows[t]) for t in teams})
    return dict(league=league, home_adv=home_adv, attack=attack, defense=defense,
                scored=scored, allowed=allowed, latest=max(g['kickoff']+43200 for g in rows), cutoff=cutoff)


def forecast(model, game):
    if not model or any(len(model['scored'].get(t,[])) < 3 for t in (game['home'],game['away'])):
        return None
    h,a = game['home'],game['away']
    home = model['league']+(0 if game['neutral'] else model['home_adv']/2)+model['attack'][h]+model['defense'][a]
    away = model['league']-(0 if game['neutral'] else model['home_adv']/2)+model['attack'][a]+model['defense'][h]
    basic_h = (mean(model['scored'][h])+mean(model['allowed'][a]))/2
    basic_a = (mean(model['scored'][a])+mean(model['allowed'][h]))/2
    return dict(margin=home-away, total=home+away, home_score_estimate=home, away_score_estimate=away,
                baseline_margin=basic_h-basic_a, baseline_total=basic_h+basic_a,
                home_games=len(model['scored'][h]), away_games=len(model['scored'][a]))


def replay(games):
    folds = defaultdict(list)
    for g in games:
        folds[(g['season'],g['week'])].append(g)
    predictions = []
    for (season,week),test in sorted(folds.items()):
        cutoff = min(g['kickoff'] for g in test)
        model = fit(games,season,cutoff)
        for g in test:
            p = forecast(model,g)
            if p:
                predictions.append(dict(**g, **p, actual_margin=g['home_score']-g['away_score'],
                                        actual_total=g['home_score']+g['away_score'],
                                        cutoff=cutoff, latest_training_score=model['latest']))
    return predictions


def quantile(values,p):
    s = sorted(values); k = (len(s)-1)*p; lo = int(k); hi = math.ceil(k)
    return s[lo]+(s[hi]-s[lo])*(k-lo)


def metrics(rows,market):
    actual = 'actual_'+market
    result = {'n':len(rows)}
    for name,key in [('challenger',market),('baseline','baseline_'+market),('closing_line',market+'_close')]:
        sample = [r for r in rows if r.get(key) is not None]
        errors = [r[actual]-r[key] for r in sample]
        result[name] = {'n':len(sample), 'mae':mean(abs(e) for e in errors), 'rmse':math.sqrt(mean(e*e for e in errors))} if errors else None
    return result


def improvement_ci(rows,market):
    groups = defaultdict(list)
    for r in rows:
        groups[(r['season'],r['week'])].append(abs(r['actual_'+market]-r['baseline_'+market])-abs(r['actual_'+market]-r[market]))
    groups = list(groups.values()); rng = random.Random(20261011); values = []
    for _ in range(2000):
        sample = [v for _ in groups for v in rng.choice(groups)]
        values.append(mean(sample))
    return [quantile(values,.025),quantile(values,.975)]


def evaluate(rows):
    noise = [r for r in rows if r['season'] <= 2022]
    held = [r for r in rows if r['season'] >= 2024]
    report = {'protocol':'GAME_PROTOCOL.json','promotion_eligible':False,'markets':{}}
    for m in ['margin','total']:
        item = metrics(held,m)
        improvement = item['baseline']['mae']-item['challenger']['mae']
        interval = improvement_ci(held,m)
        low,high = [quantile([r['actual_'+m]-r[m] for r in noise],p) for p in [.1,.9]]
        coverage = mean(low <= r['actual_'+m]-r[m] <= high for r in held)
        seasons = {str(y):metrics([r for r in held if r['season'] == y],m) for y in [2024,2025]}
        accepted = improvement >= .25 and interval[0] > 0 and .75 <= coverage <= .85 and all(v['challenger']['mae']-v['baseline']['mae'] <= .25 for v in seasons.values())
        item.update(mae_improvement=improvement, paired_week_cluster_ci_95=interval,
                    prediction_interval_80={'noise_games':len(noise),'residual_lower':low,'residual_upper':high,'coverage':coverage},
                    seasons=seasons, development_2023=metrics([r for r in rows if r['season'] == 2023],m),
                    research_acceptance='contender' if accepted else 'rejected')
        report['markets'][m] = item
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--csv',required=True); p.add_argument('--output',required=True)
    args = p.parse_args(); games = load_games(args.csv); rows = replay(games); report = evaluate(rows)
    report.update(public_input_sha256=hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),eligible_games=len(rows),
                  limitation='Revised public data; closing lines are later diagnostic benchmarks, not pregame executable prices. Locked historical period has been used in earlier audits; future holdout remains required.')
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,allow_nan=False))
