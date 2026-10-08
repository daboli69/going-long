"""Champion benchmarks that need no historical odds: reconstructed player-mean accuracy by market and season, the game-score model against the
closing market lines (public schedule data), and the production tracker's own out-of-sample record (benchmark.py)."""
import json
from pathlib import Path

import numpy as np
from scipy.stats import poisson

from . import benchmark, champion
from .experiments2 import MARKET_RULES, _eligible, champion_rows


def player_means(root):
    frame = champion_rows(root)
    out = {}
    for market, (positions, _, is_count) in MARKET_RULES.items():
        rows = _eligible(frame, market)
        block = {}
        for season, part in rows.groupby('season'):
            y, p = part['y_' + market].to_numpy(float), part['champ_' + market].to_numpy(float)
            item = {'n': int(len(y)), 'mae': float(np.abs(y - p).mean()), 'rmse': float(np.sqrt(((y - p) ** 2).mean())), 'bias': float((p - y).mean()), 'mean_actual': float(y.mean())}
            early = part.week <= 6
            if early.any():
                item['mae_weeks1_6'] = float(np.abs(y[early.to_numpy()] - p[early.to_numpy()]).mean())
            if is_count:
                item['poisson_log_score'] = float(poisson.logpmf(y, np.maximum(p, 0.01)).mean())
                if market in ('receptions', 'pass_tds'):
                    item['variance_to_mean_actual'] = float(y.var() / max(y.mean(), 1e-9))
            block[str(season)] = item
        out[market] = block
    return out


def game_model(root, seasons=range(2021, 2026), window=12, minimum=5):
    """Production team-score model, walk-forward, versus the closing market spread and total (nflverse schedule lines)."""
    games = champion.load_games(root)
    games = games[(games.game_type == 'REG') & games.home_score.notna()].sort_values(['season', 'week', 'gameday']).reset_index(drop=True)
    history = {}
    rows = []
    for row in games.itertuples():
        def team_stats(team):
            h = history.get(team, [])[-window:]
            return h
        home_h, away_h = team_stats(row.home_team), team_stats(row.away_team)
        if len(home_h) >= minimum and len(away_h) >= minimum and row.season in seasons:
            def wmean(h, idx):
                seasons_ = [x[0] for x in h]
                w = np.array(champion.season_weights(seasons_, row.season), float)
                v = np.array([x[idx] for x in h], float)
                return float((v * w).sum() / w.sum())
            home_pts = (wmean(home_h, 1) + wmean(away_h, 2)) / 2
            away_pts = (wmean(away_h, 1) + wmean(home_h, 2)) / 2
            rows.append({'season': row.season, 'margin': row.home_score - row.away_score, 'total': row.home_score + row.away_score,
                         'pred_margin': home_pts - away_pts, 'pred_total': home_pts + away_pts, 'mkt_margin': row.spread_line, 'mkt_total': row.total_line})
        history.setdefault(row.home_team, []).append((row.season, row.home_score, row.away_score))
        history.setdefault(row.away_team, []).append((row.season, row.away_score, row.home_score))
    import pandas as pd
    frame = pd.DataFrame(rows).dropna(subset=['mkt_margin', 'mkt_total'])
    out = {}
    for season, part in frame.groupby('season'):
        out[str(season)] = {'n': int(len(part)), 'champion_margin_rmse': float(np.sqrt(((part.margin - part.pred_margin) ** 2).mean())),
                            'market_margin_rmse': float(np.sqrt(((part.margin - part.mkt_margin) ** 2).mean())),
                            'champion_total_rmse': float(np.sqrt(((part.total - part.pred_total) ** 2).mean())),
                            'market_total_rmse': float(np.sqrt(((part.total - part.mkt_total) ** 2).mean()))}
    out['pooled'] = {'n': int(len(frame)), **{k: float(np.sqrt(((frame[a] - frame[b]) ** 2).mean())) for k, a, b in
                                              (('champion_margin_rmse', 'margin', 'pred_margin'), ('market_margin_rmse', 'margin', 'mkt_margin'),
                                               ('champion_total_rmse', 'total', 'pred_total'), ('market_total_rmse', 'total', 'mkt_total'))}}
    return out


def run(root, tracker_records, path):
    result = {'version': 1, 'note': 'Champion benchmarks without historical odds, plus the production tracker record. No ROI claims for reconstructed history: no historical prop lines exist.',
              'player_mean_accuracy_reconstructed_champion': player_means(root), 'game_model_vs_closing_market': game_model(root),
              'tracker_2026': benchmark.benchmark(tracker_records)}
    Path(path).write_text(json.dumps(result, indent=1, sort_keys=True, default=float) + '\n', encoding='utf-8')
    return result
