"""Point-in-time reconstruction of GOING's production player-projection model (the Champion) from public nflverse data.

The production model (scripts/build_pipeline.py: build_profiles / season_fit / fit_stat) is, per player and market:
  * the last 12 REGULAR-SEASON offensive appearances (weekly stats plus zero-stat appearances found in the snap counts), at least 5 required
    (QBs: verified schedule starts within 730 days)
  * weights: when the window holds both current-season and earlier-season games, 80% of the weight is spread over the current-season games and
    20% over the earlier ones (unvalidated "product policy"); otherwise equal weights
  * the market mean is that weighted mean (Poisson lambda for counts; moment-matched lognormal on positive yardage preserves the mean)
This module recomputes exactly that for any (season, week) using only games played BEFORE that week, so the Champion can be benchmarked
out of sample without access to historical production snapshots. Fidelity is checked against the frozen 2026 records (`validate_against_tracker`).
"""
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW, MINIMUM = 12, 5
POSITIONS = {'QB', 'RB', 'WR', 'TE', 'FB'}
MARKET_COLUMNS = {'pass_yds': 'passing_yards', 'rush_yds': 'rushing_yards', 'rec_yds': 'receiving_yards', 'receptions': 'receptions',
                  'pass_tds': 'passing_tds', 'rush_tds': 'rushing_tds', 'rec_tds': 'receiving_tds', 'atd': 'touchdowns'}
COUNT_MARKETS = {'receptions', 'pass_tds', 'rush_tds', 'rec_tds', 'atd'}
WORKLOAD = ('attempts', 'carries', 'targets')
WEEKLY_URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'
SNAP_URL = 'https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.csv'
PLAYERS_URL = 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
GAMES_URL = 'https://github.com/nflverse/nfldata/raw/master/data/games.csv'
FFOPP_URL = 'https://github.com/ffverse/ffopportunity/releases/download/v1.0.0-data/ep_weekly_{season}.parquet'
WEEKLY_COLUMNS = ['player_id', 'player_display_name', 'position', 'team', 'opponent_team', 'season', 'week', 'season_type', 'passing_yards', 'passing_tds',
                  'attempts', 'carries', 'rushing_yards', 'rushing_tds', 'receptions', 'targets', 'receiving_yards', 'receiving_tds', 'special_teams_tds',
                  'def_tds', 'fumble_recovery_tds']


def _download(url, destination):
    destination = Path(destination)
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=180) as response:
            body = response.read()
        temporary = destination.with_suffix('.tmp')
        temporary.write_bytes(body)
        temporary.replace(destination)
    return destination


def cache(root):
    return Path(root) / 'research' / 'cache'


def load_weekly(root, seasons):
    frames = [pd.read_csv(_download(WEEKLY_URL.format(season=s), cache(root) / f'stats_player_week_{s}.csv'), usecols=WEEKLY_COLUMNS) for s in seasons]
    return pd.concat(frames, ignore_index=True)


def load_snaps(root, seasons):
    frames = [pd.read_csv(_download(SNAP_URL.format(season=s), cache(root) / f'snap_counts_{s}.csv'),
                          usecols=['season', 'game_type', 'week', 'pfr_player_id', 'position', 'team', 'offense_snaps']) for s in seasons]
    return pd.concat(frames, ignore_index=True)


def load_players(root):
    return pd.read_csv(_download(PLAYERS_URL, cache(root) / 'players.csv'), usecols=['gsis_id', 'pfr_id', 'position'])


def load_games(root):
    return pd.read_csv(_download(GAMES_URL, cache(root) / 'games.csv'))


def load_ffopp(root, seasons):
    frames = []
    for s in seasons:
        path = _download(FFOPP_URL.format(season=s), cache(root) / f'ep_weekly_{s}.parquet')
        frames.append(pd.read_parquet(path))
    out = pd.concat(frames, ignore_index=True)
    out['season'] = out['season'].astype(int)
    out['week'] = out['week'].astype(int)
    return out


def appearances(root, seasons):
    """One row per (player, season, week) offensive appearance, REGULAR season, with the stat columns the Champion uses."""
    weekly = load_weekly(root, seasons)
    weekly = weekly[(weekly.season_type == 'REG') & weekly.position.isin(POSITIONS)].copy()
    parts = weekly[['special_teams_tds', 'def_tds', 'fumble_recovery_tds', 'rushing_tds', 'receiving_tds']].fillna(0)
    weekly['touchdowns'] = parts.sum(axis=1)
    weekly = weekly.drop(columns=['season_type', 'special_teams_tds', 'def_tds', 'fumble_recovery_tds'])
    snaps = load_snaps(root, seasons)
    players = load_players(root).dropna(subset=['pfr_id', 'gsis_id'])
    pfr = dict(zip(players.pfr_id, players.gsis_id))
    position = dict(zip(players.gsis_id, players.position))
    snaps = snaps[(snaps.game_type == 'REG') & (snaps.offense_snaps.fillna(0) > 0)].copy()
    snaps['player_id'] = snaps.pfr_player_id.map(pfr)
    snaps = snaps.dropna(subset=['player_id'])
    snaps['position'] = snaps.player_id.map(position)
    snaps = snaps[snaps.position.isin(POSITIONS)]
    have = set(zip(weekly.player_id, weekly.season, weekly.week))
    extra = snaps[[(p, s, w) not in have for p, s, w in zip(snaps.player_id, snaps.season, snaps.week)]].drop_duplicates(['player_id', 'season', 'week'])
    zeros = {c: 0 for c in ['passing_yards', 'passing_tds', 'attempts', 'carries', 'rushing_yards', 'rushing_tds', 'receptions', 'targets', 'receiving_yards',
                            'receiving_tds', 'touchdowns']}
    extra = extra[['player_id', 'position', 'team', 'season', 'week']].assign(player_display_name=None, opponent_team=None, **zeros)
    out = pd.concat([weekly, extra], ignore_index=True)
    out = out.drop_duplicates(['player_id', 'season', 'week']).sort_values(['player_id', 'season', 'week']).reset_index(drop=True)
    for stat, share in (('carries', 'carry_share'), ('targets', 'target_share')):
        team_total = out.groupby(['season', 'week', 'team'])[stat].transform('sum')
        out[share] = np.where(team_total > 0, out[stat] / team_total.replace(0, np.nan), np.nan)
    return out


def verified_starts(games):
    """(season, week, team) -> starting QB id from the schedule."""
    starters = {}
    for row in games.itertuples():
        if getattr(row, 'game_type', 'REG') != 'REG':
            continue
        starters[(row.season, row.week, row.home_team)] = row.home_qb_id
        starters[(row.season, row.week, row.away_team)] = row.away_qb_id
    return starters


def season_weights(seasons, current):
    """The production policy (scripts/build_pipeline.py season_weights): 80% on current-season games, 20% on earlier ones."""
    now = sum(1 for s in seasons if s == current)
    before = sum(1 for s in seasons if s < current)
    return [(0.8 / now if before else 1 / now) if s == current else ((0.2 / before if now else 1 / before) if s < current else 0) for s in seasons]


def champion_frame(root, target_seasons, history_from=2019):
    """For every appearance in `target_seasons`, the Champion's inputs and market means using ONLY earlier games.

    Columns per market m: champ_m (the production mean), cur_m / prior_m (equal-weight means of the window's current-season / earlier-season games),
    plus k (current-season games in the window), n (window size), n_prior, and the actual outcome y_m.
    """
    games = appearances(root, range(history_from, max(target_seasons) + 1))
    schedule = load_games(root)
    starters = verified_starts(schedule)
    date = {(r.season, r.week, r.home_team): r.gameday for r in schedule.itertuples() if r.game_type == 'REG'}
    date.update({(r.season, r.week, r.away_team): r.gameday for r in schedule.itertuples() if r.game_type == 'REG'})
    rows = []
    for pid, frame in games.groupby('player_id', sort=False):
        frame = frame.reset_index(drop=True)
        seasons, weeks = frame.season.to_numpy(), frame.week.to_numpy()
        positions = frame.position.to_numpy()
        starts = np.array([starters.get((s, w, t)) == pid for s, w, t in zip(seasons, weeks, frame.team)])
        stats = {m: frame[c].to_numpy(dtype=float) for m, c in MARKET_COLUMNS.items()}
        work = {c: frame[c].to_numpy(dtype=float) for c in WORKLOAD}
        shares = {c: frame[c].to_numpy(dtype=float) for c in ('carry_share', 'target_share')}
        for i in range(len(frame)):
            if seasons[i] not in target_seasons:
                continue
            season = int(seasons[i])
            row = {'player_id': pid, 'season': season, 'week': int(weeks[i]), 'position': positions[i], 'team': frame.team[i], 'opponent': frame.opponent_team[i], 'start': bool(starts[i])}
            is_qb = positions[i] == 'QB'
            prior_idx = [j for j in range(i) if (not is_qb or starts[j])]
            window = prior_idx[-WINDOW:]
            if not window:
                continue
            w_seasons = [int(seasons[j]) for j in window]
            weights = np.array(season_weights(w_seasons, season))
            cur_mask = np.array([s == season for s in w_seasons])
            row.update(n=len(window), k=int(cur_mask.sum()), n_prior=int((~cur_mask).sum()))
            for m in MARKET_COLUMNS:
                values = stats[m][window]
                ok = ~np.isnan(values)
                if ok.sum() == 0:
                    row['champ_' + m] = np.nan
                    continue
                w = weights[ok]
                row['champ_' + m] = float((values[ok] * w).sum() / w.sum())
                row['cur_' + m] = float(values[ok][cur_mask[ok]].mean()) if (cur_mask & ok).any() else np.nan
                row['prior_' + m] = float(values[ok][~cur_mask[ok]].mean()) if ((~cur_mask) & ok).any() else np.nan
                row['y_' + m] = stats[m][i]
            for share in ('carry_share', 'target_share'):
                v = shares[share][window]
                ok = ~np.isnan(v)
                row['champ_' + share] = float((v[ok] * weights[ok]).sum() / weights[ok].sum()) if ok.any() else np.nan
                row['sd_' + share] = float(v[ok].std()) if ok.sum() > 1 else np.nan
                cur_v, pri_v = v[ok & cur_mask], v[ok & ~cur_mask]
                row['trend_' + share] = float(cur_v.mean() - pri_v.mean()) if len(cur_v) and len(pri_v) else np.nan
            for c in WORKLOAD:
                v = work[c][window]
                ok = ~np.isnan(v)
                row['champ_' + c] = float((v[ok] * weights[ok]).sum() / weights[ok].sum()) if ok.any() else np.nan
                row['cur_' + c] = float(v[ok & cur_mask].mean()) if (ok & cur_mask).any() else np.nan
                row['y_' + c] = work[c][i]
            rows.append(row)
    out = pd.DataFrame(rows)
    out['ready'] = out.n >= MINIMUM
    return out


def poisson_probabilities(lam, line, side):
    """The production count-market pricing (docs/BETTING_MODEL.md): P(over)=1-CDF(floor(L)), P(under)=CDF(ceil(L)-1), push is the remainder."""
    from scipy.stats import poisson
    over = 1 - poisson.cdf(np.floor(line), lam)
    under = poisson.cdf(np.ceil(line) - 1, lam)
    return over if side == 'Over' else under


def validate_against_tracker(root, records, week_of_event):
    """Compare reconstructed Poisson probabilities with the probability the production system froze, for count markets in 2026.

    `records` are tracker records; `week_of_event` maps (home, away, kickoff date) -> NFL week. Returns agreement statistics.
    """
    frame = champion_frame(root, {2026})
    index = {(r.player_id, r.week): r for r in frame.itertuples()}
    rows = []
    for r in records:
        if r['kind'] != 'prediction':
            continue
        p = r['payload']
        if p['market'] not in ('player_receptions', 'player_passing_tds') or not p.get('profile_id') or p['sport'] != 'nfl':
            continue
        week = week_of_event.get((p['home'], p['away'], str(p['kickoff'])[:10]))
        got = index.get((p['profile_id'], week))
        if got is None:
            continue
        lam = got.champ_receptions if p['market'] == 'player_receptions' else got.champ_pass_tds
        if lam != lam:
            continue
        mine = poisson_probabilities(lam, float(p['line']), p['side'])
        rows.append((p['probability'], float(mine), p['market']))
    arr = np.array([(a, b) for a, b, _ in rows])
    diff = np.abs(arr[:, 0] - arr[:, 1])
    return {'n': len(rows), 'median_abs_diff': float(np.median(diff)), 'share_within_0.02': float((diff <= 0.02).mean()), 'share_within_0.05': float((diff <= 0.05).mean()),
            'correlation': float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1])}
