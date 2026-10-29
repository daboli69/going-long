"""Probability-of-playing model and expected-lineup features.

For every team-game the candidate set is: players who played for the team in its previous 10 games (results dated
before the game day) plus players on the official injury report selected for that game (latest report published at least
one hour before the day's first tipoff). The play-probability model is refit once per season on earlier seasons only.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from . import data, metrics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_nba_xgb'
STATUSES = ['Out', 'Doubtful', 'Questionable', 'Probable', 'Available', 'NotYetSubmitted', 'NotListed']
REASONS = ['injury', 'rest', 'gleague', 'personal', 'suspension', 'health_safety', 'not_with_team', 'other']
HISTORY = 10
MIN_PRIOR = 12.0


def reason_category(text) -> str:
    t = str(text or '').lower()
    for key, cat in (('g league', 'gleague'), ('two-way', 'gleague'), ('assignment', 'gleague'), ('rest', 'rest'),
                     ('management', 'rest'), ('personal', 'personal'), ('suspension', 'suspension'),
                     ('health and safety', 'health_safety'), ('not with team', 'not_with_team'),
                     ('injury', 'injury'), ('illness', 'injury'), ('soreness', 'injury')):
        if key in t:
            return cat
    return 'other'


def load_inputs():
    games, _ = data.load()
    pb = pd.read_parquet(ROOT / 'data' / 'cache' / 'player_boxes.parquet')
    pb = pb[pb.game_id.astype(str).isin(games.game_id)].copy()
    pb['game_id'] = pb.game_id.astype(str)
    pb['athlete_id'] = pb.athlete_id.astype('int64')
    pb['team_id'] = pb.team_id.astype(str)
    pb['minutes'] = pd.to_numeric(pb.minutes, errors='coerce').fillna(0.0)
    pb['played'] = (pb.minutes > 0) & ~pb.did_not_play.fillna(False).astype(bool)
    inj = pd.read_parquet(ROOT / 'data' / 'cache' / 'injury_reports.parquet')
    inj = inj[inj.game_id.notna() & inj.athlete_id.notna()].copy()
    inj['game_id'] = inj.game_id.astype(str)
    inj['athlete_id'] = inj.athlete_id.astype('int64')
    inj['team_id'] = inj.team_id.astype(str)
    return games, pb, inj


def candidate_rows(games: pd.DataFrame, pb: pd.DataFrame, inj: pd.DataFrame, labelled=True, leak_history=False) -> pd.DataFrame:
    """One row per (team-game, candidate player) with only information available before the game day."""
    # labelled: only verified completed games; otherwise also the not-yet-played schedule (used for live forecasts)
    g = games[games.completed & games.verified].copy() if labelled else games[(games.completed & games.verified) | ~games.completed].copy()
    g = g[g.season >= 2021].sort_values(['game_date', 'tipoff_utc', 'game_id'])
    played = pb[pb.played].groupby(['team_id', 'game_id']).apply(
        lambda d: dict(zip(d.athlete_id, d.minutes)), include_groups=False).to_dict()
    box_ids = set(pb.game_id)
    injmap = {k: v for k, v in inj.groupby(['game_id', 'team_id'])}
    history = defaultdict(list)                 # team -> list of (date, game_id, {athlete: minutes})
    season_games = defaultdict(int)
    rows = []
    for r in g.itertuples(index=False):
        for team, opp in ((r.home_id, r.away_id), (r.away_id, r.home_id)):
            past = history[team][-HISTORY:]
            if leak_history:                    # planted leak used only by the mutation test
                past = (past + [(r.game_date, r.game_id, played.get((team, r.game_id), {}))])[-HISTORY:]
            cand = {}
            for k, (_, _, mins) in enumerate(past):
                for a in mins:
                    cand.setdefault(a, [])
            ir = injmap.get((r.game_id, team))
            status, reason, nys, lead = {}, {}, {}, {}
            if ir is not None:
                for x in ir.itertuples(index=False):
                    status[x.athlete_id] = x.status
                    reason[x.athlete_id] = x.reason
                    nys[x.athlete_id] = bool(x.not_yet_submitted)
                    lead[x.athlete_id] = (pd.Timestamp(r.tipoff_utc) - pd.Timestamp(x.available_at)).total_seconds() / 3600.0
                    cand.setdefault(x.athlete_id, [])
            actual = played.get((team, r.game_id), {}) if r.game_id in box_ids else {}
            n_prev = len(history[team])
            for a in cand:
                seq = [mins.get(a) for (_, _, mins) in past]           # None where not played
                gp = sum(m is not None for m in seq)
                ws = [(0.8 ** (len(seq) - 1 - i), m) for i, m in enumerate(seq) if m is not None]
                avgmin = sum(w * m for w, m in ws) / sum(w for w, _ in ws) if ws else np.nan
                streak = 0
                for m in reversed(seq):
                    if m is None:
                        streak += 1
                    else:
                        break
                st = status.get(a)
                if st is None:
                    st = 'NotListed'
                elif nys.get(a):
                    st = 'NotYetSubmitted'
                rows.append((r.game_id, r.season, r.game_date, team, a, st, reason_category(reason.get(a)), gp,
                             avgmin, streak, n_prev, lead.get(a, np.nan), float(a in actual), actual.get(a, 0.0)))
        for team in (r.home_id, r.away_id):
            if r.completed:
                history[team].append((r.game_date, r.game_id, played.get((team, r.game_id), {})))
    cols = ['game_id', 'season', 'game_date', 'team_id', 'athlete_id', 'status', 'reason_cat', 'gp_last10', 'avg_min',
            'streak_missed', 'team_games_before', 'report_lead_hours', 'played', 'minutes']
    return pd.DataFrame(rows, columns=cols)


def design(df: pd.DataFrame) -> np.ndarray:
    S = np.stack([(df.status == s).values for s in STATUSES[:-1]], 1).astype(float)
    R = np.stack([(df.reason_cat == r).values for r in REASONS], 1).astype(float)
    # status x reason interaction for listed-and-not-available statuses
    out_inj = ((df.status == 'Out') & (df.reason_cat == 'injury')).values[:, None].astype(float)
    q_inj = ((df.status.isin(['Questionable', 'Doubtful'])) & (df.reason_cat == 'injury')).values[:, None].astype(float)
    num = np.column_stack([df.gp_last10.fillna(0) / HISTORY, df.avg_min.fillna(MIN_PRIOR).clip(0, 40) / 40.0,
                           np.minimum(df.streak_missed.fillna(0), HISTORY) / HISTORY])
    return np.hstack([S, R, out_inj, q_inj, num])


def fit_play_model(train: pd.DataFrame):
    return LogisticRegression(C=1.0, max_iter=2000).fit(design(train), train.played.values)


def predict_play(model, df: pd.DataFrame, floor=0.0):
    return model.predict_proba(design(df))[:, 1]


def evaluate_play_model(cands: pd.DataFrame, first_season=2023):
    """Walk-forward: season T scored by a model fit on injury-era seasons < T. Compared with a status-rate table."""
    out = {}
    for T in sorted(cands.season.unique()):
        if T < first_season:
            continue
        tr, te = cands[(cands.season >= 2022) & (cands.season < T)], cands[cands.season == T]
        m = fit_play_model(tr)
        p = predict_play(m, te)
        rate = tr.groupby('status').played.mean()
        p0 = te.status.map(rate).fillna(tr.played.mean()).values
        y = te.played.values
        out[int(T)] = {'n': int(len(te)), 'model_log_loss': metrics.logloss(y, p), 'status_rate_log_loss': metrics.logloss(y, p0),
                       'constant_log_loss': metrics.logloss(y, np.full(len(y), tr.played.mean())),
                       'model_brier': metrics.brier(y, p), 'calibration': metrics.calibration(y, p)}
    return out


def team_value(cands_game: pd.DataFrame, p: np.ndarray, rating: dict, scale=240.0):
    """Minutes-weighted sum of RAPM net ratings with expected minutes = P(play) x recent minutes, rescaled to 240."""
    e = cands_game.avg_min.fillna(MIN_PRIOR).clip(4, 38).values
    m = p * e
    tot = m.sum()
    if tot <= 0:
        return 0.0
    m = m * (scale / tot)
    net = np.array([rating.get(int(a), 0.0) for a in cands_game.athlete_id.values])
    return float((m / 48.0 * net).sum())


def build_game_features(cands: pd.DataFrame, games: pd.DataFrame, ratings: pd.DataFrame, log=print, seasons=None) -> pd.DataFrame:
    """Per-game availability features. Play model for season T is fit on injury-era seasons < T only."""
    ratings = ratings.sort_values('refit_day')
    by_day = {d: dict(zip(g.athlete_id.astype(int), g.net)) for d, g in ratings.groupby('refit_day')}
    days = np.array(sorted(by_day))
    g = games.set_index('game_id')
    rows = []
    models_by_season = {}
    for T in sorted(cands.season.unique()):
        if seasons is not None and T not in seasons:
            continue
        tr = cands[(cands.season >= 2022) & (cands.season < T)]
        models_by_season[T] = fit_play_model(tr) if len(tr) > 500 else None
    for gid, grp in cands.groupby('game_id', sort=False):
        T = int(grp.season.iloc[0])
        if seasons is not None and T not in seasons:
            continue
        model = models_by_season[T]
        if model is None:
            continue
        info = g.loc[gid]
        day = int(np.datetime64(info.game_date, 'D').astype('int64'))
        k = np.searchsorted(days, day, side='right') - 1           # latest refit on or before the game day
        if k < 0:
            continue
        rating = by_day[days[k]]
        res = {'game_id': gid, 'rapm_refit_day': int(days[k])}
        for side, team in (('home', info.home_id), ('away', info.away_id)):
            cg = grp[grp.team_id == team]
            if cg.empty:
                continue
            p = predict_play(model, cg)
            exp_val = team_value(cg, p, rating)
            usual = ((cg.gp_last10 >= 5) & (cg.avg_min.fillna(0) >= 10)).values
            p_full = np.where(usual, 1.0, p)
            full_val = team_value(cg, p_full, rating)
            actual = cg.minutes.values
            m = actual * (240.0 / actual.sum()) if actual.sum() > 0 else actual
            net = np.array([rating.get(int(a), 0.0) for a in cg.athlete_id.values])
            res[f'{side}_exp_value'] = exp_val
            res[f'{side}_full_value'] = full_val
            res[f'{side}_oracle_value'] = float((m / 48.0 * net).sum())      # retrospective, diagnostic only
            res[f'{side}_exp_missing_min'] = float(((1 - p) * cg.avg_min.fillna(MIN_PRIOR).clip(4, 38).values * usual).sum())
        rows.append(res)
    f = pd.DataFrame(rows)
    f['avail_value_diff'] = f.home_exp_value - f.away_exp_value
    f['avail_effect_diff'] = (f.home_exp_value - f.home_full_value) - (f.away_exp_value - f.away_full_value)
    f['full_value_diff'] = f.home_full_value - f.away_full_value
    f['missing_min_diff'] = f.away_exp_missing_min - f.home_exp_missing_min
    f['oracle_value_diff'] = f.home_oracle_value - f.away_oracle_value
    return f


def main(log=print):
    games, pb, inj = load_inputs()
    cands = candidate_rows(games, pb, inj)
    cands.to_parquet(OUT / 'avail_candidates.parquet', index=False)
    log('candidates', cands.shape, 'injury-listed share', float((cands.status != 'NotListed').mean()))
    ev = evaluate_play_model(cands)
    (ROOT / 'docs' / 'NBA_AVAIL_PLAYMODEL_EVAL.json').write_text(json.dumps(ev, indent=2, default=float), encoding='utf-8')
    for k, v in ev.items():
        log(k, {a: round(b, 4) for a, b in v.items() if isinstance(b, float)})
    ratings = pd.read_parquet(OUT / 'rapm_ratings.parquet')
    f = build_game_features(cands, games, ratings, log)
    f.to_parquet(OUT / 'avail_features.parquet', index=False)
    log('features', f.shape)


if __name__ == '__main__':
    main()
