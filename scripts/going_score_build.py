#!/usr/bin/env python
"""GOING Score v2: a player-level situation index for QB / RB / WR / TE, built from PUBLIC data only.

    python scripts/going_score_build.py                  # reads nflverse (cached under .cache/going_score), data/history.json, data/nfl_roster.json
    python scripts/going_score_build.py --offline        # use only cached files

Writes data/going_score.json (schema going-score-v2). The score answers "how good is this player's underlying opportunity and how is it changing",
computed ONLY from games played before the as-of week. It is NOT a projection, a probability, an edge or a bet recommendation: a higher score is
not a better bet. Definition, validation and limits: docs/GOING_SCORE.md; pre-registered experiment P4-1 in research/trend-intelligence/LEDGER.md.

Components (z-scored against frozen development-season statistics, then weighted with the frozen config/going_score_weights.json):
  opportunity   exponentially weighted expected fantasy points per game (ffopportunity xFP), shrunk to the position mean
  team_share    the player's share of his team's xFP
  efficiency    actual PPR minus xFP per game, shrunk hard (luck-prone)
  role          snap share
  availability  share of the team's last 8 games the player appeared in
  opp_trend     last-3 xFP minus the preceding six games (damped)
  role_trend    last-3 snap share minus the preceding six games (damped)
Production (EW PPR/game) is shown for context with weight 0: it equals opportunity + efficiency, so weighting it too would double count.
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eligibility  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SCHEMA = 'going-score-v2'
POSITIONS = ('QB', 'RB', 'WR', 'TE')
SCORED = ('opportunity', 'team_share', 'efficiency', 'role', 'availability', 'opp_trend', 'role_trend')
DISPLAY_ONLY = ('production',)
ALL_COMPONENTS = ('production',) + SCORED
URLS = {
    'weekly': 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv',
    'snaps': 'https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.csv',
    'players': 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv',
    'ffopp': 'https://github.com/ffverse/ffopportunity/releases/download/v1.0.0-data/ep_weekly_{season}.parquet',
}
WEEKLY_COLS = ['player_id', 'player_display_name', 'position', 'team', 'season', 'week', 'season_type', 'attempts', 'fantasy_points_ppr']
DEFAULT_PARAMS = {'window': 12, 'half_life': 5.0, 'offseason_discount': 0.7, 'min_games': 3, 'max_stale_team_games': 6, 'availability_window': 8,
                  'availability_prior': 0.85, 'availability_k': 2.0, 'trend_k': 3.0, 'qb_min_attempts': 10,
                  'shrink_k': {'opportunity': 3.0, 'team_share': 3.0, 'efficiency': 8.0, 'role': 3.0, 'production': 3.0}}
ROLE_RULE_SNAP = 8.0  # same descriptive threshold as scripts/build_pipeline.py ROLE_RULE: L3 vs L6 snap share, in points
TIERS = ((90, 'elite', 'Elite'), (75, 'strong', 'Strong'), (50, 'solid', 'Solid'), (25, 'modest', 'Modest'), (0, 'low', 'Low'))
EXPLAIN = {
    'production': 'Recent PPR points per game (recency-weighted, shrunk). Context only: it is opportunity plus efficiency, so it carries no weight of its own.',
    'opportunity': 'Expected fantasy points per game from the volume and quality of touches/targets (recency-weighted, shrunk to the position average).',
    'team_share': "Share of the team's expected fantasy points this player commands.",
    'efficiency': 'Actual minus expected points per game. Shrunk heavily because it is mostly luck; small weight.',
    'role': 'Share of offensive snaps (deployment level).',
    'availability': "Share of the team's last 8 games the player appeared in.",
    'opp_trend': 'Last three games of expected points versus the six before: is the opportunity rising or falling.',
    'role_trend': 'Last three games of snap share versus the six before.',
}


# ---------------------------------------------------------------- data access

def _fetch(url, dest, offline=False, refresh=False):
    dest = Path(dest)
    if dest.exists() and (offline or not refresh):
        return dest
    if offline:
        raise FileNotFoundError(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as response:
        body = response.read()
    tmp = dest.with_suffix(dest.suffix + '.tmp')
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dest


def load_public(cache_dir, seasons, current, offline=False):
    """(weekly, snaps, players, ffopp). The current season is refreshed on every run; earlier seasons are cached."""
    cache = Path(cache_dir)
    weekly, snaps, ffopp = [], [], []
    for s in seasons:
        refresh = s == current
        weekly.append(pd.read_csv(_fetch(URLS['weekly'].format(season=s), cache / f'stats_player_week_{s}.csv', offline, refresh), usecols=WEEKLY_COLS, low_memory=False))
        try:
            snaps.append(pd.read_csv(_fetch(URLS['snaps'].format(season=s), cache / f'snap_counts_{s}.csv', offline, refresh),
                                     usecols=['season', 'game_type', 'week', 'pfr_player_id', 'position', 'team', 'offense_snaps', 'offense_pct']))
        except Exception as exc:  # noqa: BLE001  snaps are optional context: a missing season degrades `role`, not the build
            print(f'[going_score] snaps {s} unavailable: {exc!r}', file=sys.stderr)
        try:
            frame = pd.read_parquet(_fetch(URLS['ffopp'].format(season=s), cache / f'ep_weekly_{s}.parquet', offline, refresh),
                                    columns=['season', 'week', 'player_id', 'total_fantasy_points_exp', 'total_fantasy_points_exp_team'])
            ffopp.append(frame)
        except Exception as exc:  # noqa: BLE001
            print(f'[going_score] ffopportunity {s} unavailable: {exc!r}', file=sys.stderr)
    players = pd.read_csv(_fetch(URLS['players'], cache / 'players.csv', offline, True if not offline else False), low_memory=False)
    return (pd.concat(weekly, ignore_index=True), pd.concat(snaps, ignore_index=True) if snaps else pd.DataFrame(),
            players, pd.concat(ffopp, ignore_index=True) if ffopp else pd.DataFrame())


# ---------------------------------------------------------------- panel

def key_of(season, week):
    return int(season) * 100 + int(week)


def build_panel(weekly, snaps, players, ffopp, qb_min_attempts=10):
    """One row per (player, season, week) offensive appearance (REG season, QB/RB/WR/TE) plus the team's game calendar.

    Zero-stat appearances are recovered from snap counts. QB games with fewer than `qb_min_attempts` attempts are dropped (trick plays and mop-up cameos)."""
    w = weekly[(weekly.season_type == 'REG')].copy()
    team_games = {t: np.array(sorted(set(key_of(s, k) for s, k in zip(g.season, g.week))), dtype=int) for t, g in w.groupby('team')}
    league_weeks = {int(s): sorted(set(int(k) for k in g.week)) for s, g in w.groupby('season')}
    skill = w[w.position.isin(POSITIONS)][['player_id', 'player_display_name', 'position', 'team', 'season', 'week', 'attempts', 'fantasy_points_ppr']].copy()
    skill = skill.rename(columns={'fantasy_points_ppr': 'ppr', 'player_display_name': 'name'})
    skill['ppr'] = skill.ppr.fillna(0.0)
    skill = skill[~((skill.position == 'QB') & (skill.attempts.fillna(0) < qb_min_attempts))]
    skill['season'] = skill.season.astype(int)
    skill['week'] = skill.week.astype(int)
    if snaps is not None and len(snaps) and players is not None and len(players):
        pm = players.dropna(subset=['pfr_id', 'gsis_id']).drop_duplicates('pfr_id')
        to_gsis = dict(zip(pm.pfr_id, pm.gsis_id))
        pos_of = dict(zip(pm.gsis_id, pm.position))
        name_of = dict(zip(pm.gsis_id, pm.display_name))
        sn = snaps[(snaps.game_type == 'REG') & (snaps.offense_snaps.fillna(0) > 0)].copy()
        sn['player_id'] = sn.pfr_player_id.map(to_gsis)
        sn = sn.dropna(subset=['player_id'])
        sn['season'] = sn.season.astype(int)
        sn['week'] = sn.week.astype(int)
        sn['snap'] = sn.offense_pct.astype(float) * 100.0
        sn = sn.drop_duplicates(['player_id', 'season', 'week'])
        skill = skill.merge(sn[['player_id', 'season', 'week', 'snap']], on=['player_id', 'season', 'week'], how='left')
        have = set(zip(skill.player_id, skill.season, skill.week))
        extra = sn[[(p, s, k) not in have for p, s, k in zip(sn.player_id, sn.season, sn.week)]].copy()
        extra['position'] = extra.player_id.map(pos_of)
        extra = extra[extra.position.isin(POSITIONS) & (extra.position != 'QB')]
        extra['name'] = extra.player_id.map(name_of)
        extra['ppr'] = 0.0
        extra['attempts'] = 0.0
        skill = pd.concat([skill, extra[['player_id', 'name', 'position', 'team', 'season', 'week', 'attempts', 'ppr', 'snap']]], ignore_index=True)
    else:
        skill['snap'] = np.nan
    if ffopp is not None and len(ffopp):
        e = ffopp.drop_duplicates(['player_id', 'season', 'week']).copy()
        e['season'] = e.season.astype(int)
        e['week'] = e.week.astype(int)
        e = e.rename(columns={'total_fantasy_points_exp': 'xfp', 'total_fantasy_points_exp_team': 'xfp_team'})
        skill = skill.merge(e[['player_id', 'season', 'week', 'xfp', 'xfp_team']], on=['player_id', 'season', 'week'], how='left')
    else:
        skill['xfp'] = np.nan
        skill['xfp_team'] = np.nan
    has_ep = skill.xfp.notna()
    skill['xfp_source'] = np.where(has_ep, 'ffopportunity', 'none')
    # a snap-only appearance without an ffopportunity row really had no expected opportunity; a missing ffopportunity season stays missing
    ep_seasons = set(ffopp.season.astype(int)) if ffopp is not None and len(ffopp) else set()
    zero_fill = skill.xfp.isna() & skill.season.isin(ep_seasons)
    skill.loc[zero_fill, 'xfp'] = 0.0
    skill.loc[zero_fill, 'xfp_team'] = np.nan
    skill['xfp_share'] = np.where(skill.xfp_team.fillna(0) > 0, skill.xfp / skill.xfp_team.replace(0, np.nan), np.nan)
    skill.loc[zero_fill, 'xfp_share'] = 0.0
    skill['key'] = skill.season * 100 + skill.week
    skill = skill.drop_duplicates(['player_id', 'season', 'week']).sort_values(['player_id', 'key']).reset_index(drop=True)
    return skill, team_games, league_weeks


# ---------------------------------------------------------------- features (point in time)

def _shrunk_ew(x, w, prior, k):
    m = ~np.isnan(x)
    if not m.any():
        return float(prior)
    return float(((w[m] * x[m]).sum() + k * prior) / (w[m].sum() + k))


def _trend(x, k):
    """Mean of the most recent three minus mean of the preceding (up to) six, damped by sample size. 0 when undefined. x is oldest-first."""
    recent = x[-3:]
    old = x[-9:-3]
    recent, old = recent[~np.isnan(recent)], old[~np.isnan(old)]
    if len(recent) < 2 or len(old) < 3:
        return 0.0
    return float((recent.mean() - old.mean()) * len(old) / (len(old) + k))


def season_weights_champion(seasons, current):
    """Production Champion policy: 80% spread over current-season games and 20% over earlier ones when both exist."""
    now = sum(1 for s in seasons if s == current)
    before = sum(1 for s in seasons if s < current)
    return np.array([(0.8 / now if before else 1 / now) if s == current else ((0.2 / before if now else 1 / before) if s < current else 0) for s in seasons])


def player_features(frame, team_games, keys, params, priors, first_team_key=None):
    """Features for one player at each as-of key in `keys` using ONLY rows with key < as-of key. `frame` is the player's rows sorted by key."""
    keys_arr = frame.key.to_numpy()
    seasons = frame.season.to_numpy()
    teams = frame.team.to_numpy()
    ppr, xfp, share, snap = (frame[c].to_numpy(dtype=float) for c in ('ppr', 'xfp', 'xfp_share', 'snap'))
    attempts_ok = np.ones(len(frame), bool)
    played_keys = set(keys_arr.tolist())
    window, H, disc, kk = params['window'], params['half_life'], params['offseason_discount'], params['shrink_k']
    first_with_team = {}
    for t, k in zip(teams, keys_arr):
        first_with_team.setdefault(t, k)
    rows = []
    for K in keys:
        end = int(np.searchsorted(keys_arr, K, side='left'))
        if end < params['min_games']:
            continue
        lo = max(0, end - window)
        sl = slice(lo, end)
        cur_season = K // 100
        ages = np.arange(end - lo - 1, -1, -1, dtype=float)
        w = 0.5 ** (ages / H) * np.where(seasons[sl] < cur_season, disc, 1.0)
        last_team = teams[end - 1]
        tg = team_games.get(last_team, np.array([], dtype=int))
        t_end = int(np.searchsorted(tg, K, side='left'))
        last_key = keys_arr[end - 1]
        since_last = int(((tg > last_key) & (tg < K)).sum())
        recent_tg = tg[max(0, t_end - params['availability_window']):t_end]
        recent_tg = recent_tg[recent_tg >= first_with_team.get(last_team, 0)]
        played = sum(1 for g in recent_tg if g in played_keys)
        avail = (played + params['availability_k'] * params['availability_prior']) / (len(recent_tg) + params['availability_k'])
        eff = ppr[sl] - xfp[sl]
        champ_w = season_weights_champion(seasons[sl].tolist(), cur_season)
        rows.append({
            'player_id': frame.player_id.iloc[0], 'key': int(K), 'season': int(cur_season), 'week': int(K % 100), 'n_prior': int(end), 'n_window': int(end - lo),
            'since_last': since_last, 'last_team': last_team,
            'production': _shrunk_ew(ppr[sl], w, priors['production'], kk['production']),
            'opportunity': _shrunk_ew(xfp[sl], w, priors['opportunity'], kk['opportunity']),
            'team_share': _shrunk_ew(share[sl], w, priors['team_share'], kk['team_share']),
            'efficiency': _shrunk_ew(eff, w, 0.0, kk['efficiency']),
            'role': _shrunk_ew(snap[sl], w, priors['role'], kk['role']),
            'availability': float(avail),
            'opp_trend': _trend(xfp[sl], params['trend_k']),
            'role_trend': _trend(snap[sl], params['trend_k']),
            'snap_l3': float(np.nanmean(snap[sl][-3:])) if (~np.isnan(snap[sl][-3:])).any() else np.nan,
            'snap_l6': float(np.nanmean(snap[sl][-6:])) if (~np.isnan(snap[sl][-6:])).any() else np.nan,
            'ppr_l6': float(ppr[sl][-6:].mean()),
            'ppr_mean_window': float(ppr[sl].mean()),
            'champion_ppr': float((ppr[sl] * champ_w).sum() / champ_w.sum()) if champ_w.sum() > 0 else np.nan,
            'role_snap_l2': float(np.nanmean(snap[sl][-2:])) if (~np.isnan(snap[sl][-2:])).any() else np.nan,
            'role_snap_prior6': float(np.nanmean(snap[sl][-8:-2])) if len(snap[sl][-8:-2]) >= 4 and (~np.isnan(snap[sl][-8:-2])).any() else np.nan,
        })
    return rows


def position_priors(panel, seasons):
    """Position means of single-game values over `seasons` (fixed from development data, then frozen in the config)."""
    out = {}
    for pos in POSITIONS:
        d = panel[(panel.position == pos) & panel.season.isin(seasons)]
        out[pos] = {'production': float(d.ppr.mean()), 'opportunity': float(d.xfp.mean()), 'team_share': float(d.xfp_share.mean()), 'role': float(d.snap.mean())}
    return out


def asof_table(panel, team_games, league_weeks, params, priors_by_pos, all_week_seasons=(), appearance_seasons=(), extra_keys=None):
    """Point-in-time feature rows for every (player, as-of key) that is relevant: the player's own appearance weeks in `appearance_seasons`
    and every league week of `all_week_seasons`. Eligibility (>= min_games prior, and appearing at the key or seen within the stale limit) is applied here."""
    out = []
    all_keys = [key_of(s, w) for s in all_week_seasons for w in league_weeks.get(s, [])]
    if extra_keys:
        all_keys = sorted(set(all_keys) | set(extra_keys))
    for pid, frame in panel.groupby('player_id', sort=False):
        pos = frame.position.iloc[-1]
        if pos not in POSITIONS:
            continue
        frame = frame.sort_values('key').reset_index(drop=True)
        appear = frame.key[frame.season.isin(appearance_seasons)].tolist()
        keys = sorted(set(appear) | set(all_keys))
        rows = player_features(frame, team_games, keys, params, priors_by_pos[pos])
        appear_set = set(appear)
        have = frame.set_index('key')
        for r in rows:
            appeared = r['key'] in have.index
            if not appeared and r['since_last'] > params['max_stale_team_games']:
                continue
            r['position'] = pos
            r['team'] = r['last_team']
            r['name'] = frame.name.iloc[-1]
            r['appeared'] = appeared
            if appeared:
                row = have.loc[r['key']]
                r['y1'] = float(row['ppr'])
                r['team_now'] = row['team']
            out.append(r)
    table = pd.DataFrame(out)
    if table.empty:
        return table
    return add_next3(table, panel)


def add_next3(table, panel):
    """y3: mean PPR over the player's appearances in the calendar weeks w..w+2 of the same season (>= 2 appearances), for rows where he appears at w."""
    p = panel[['player_id', 'season', 'week', 'ppr']]
    look = {}
    for pid, s, w, y in zip(p.player_id, p.season, p.week, p.ppr):
        look[(pid, s, w)] = y
    y3 = []
    for pid, s, w, app in zip(table.player_id, table.season, table.week, table.appeared):
        if not app:
            y3.append(np.nan)
            continue
        vals = [look[(pid, s, w + d)] for d in range(3) if (pid, s, w + d) in look]
        y3.append(float(np.mean(vals)) if len(vals) >= 2 else np.nan)
    table = table.copy()
    table['y3'] = y3
    return table


# ---------------------------------------------------------------- scoring

def zscores(table, cfg_pos):
    z = {}
    for name in SCORED:
        c = cfg_pos['components'][name]
        v = table[name].to_numpy(dtype=float)
        z[name] = np.where(np.isnan(v), 0.0, (v - c['mean']) / c['sd'])
    return z


def raw_score(table, cfg_pos, drop=()):
    z = zscores(table, cfg_pos)
    weights = {n: cfg_pos['components'][n]['weight'] for n in SCORED if n not in drop}
    total = sum(weights.values()) or 1.0
    return sum(weights[n] / total * z[n] for n in weights)


def absolute_score(raw, cfg_pos):
    lo, hi = cfg_pos['anchors']['low'], cfg_pos['anchors']['high']
    return np.clip(100.0 * (np.asarray(raw) - lo) / (hi - lo), 0, 100)


def pool_percentile(values, groups):
    """Mid-rank percentile 0-100 within each group (same convention as shared/going-score.js)."""
    s = pd.Series(values)
    g = pd.Series(groups)
    n = s.groupby(g).transform('count')
    r = s.groupby(g).rank(method='average')
    return np.where(n > 1, 100.0 * (r - 1) / (n - 1).replace(0, np.nan), 50.0)


def tier_for(percentile):
    for floor, ident, label in TIERS:
        if percentile >= floor:
            return {'id': ident, 'label': label}
    return {'id': 'low', 'label': 'Low'}


def load_config(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def score_table(table, config):
    """Adds raw_score, abs_score and position percentile (within each as-of key) to a feature table."""
    table = table.copy()
    table['raw_score'] = np.nan
    table['abs_score'] = np.nan
    for pos in POSITIONS:
        m = (table.position == pos).to_numpy()
        if not m.any() or pos not in config['positions']:
            continue
        sub = table[m]
        r = raw_score(sub, config['positions'][pos])
        table.loc[m, 'raw_score'] = r
        table.loc[m, 'abs_score'] = absolute_score(r, config['positions'][pos])
    table['pctile'] = np.nan
    ok = table.raw_score.notna()
    table.loc[ok, 'pctile'] = pool_percentile(table.loc[ok, 'raw_score'].to_numpy(), (table.loc[ok, 'position'] + '|' + table.loc[ok, 'key'].astype(str)).to_numpy())
    return table


# ---------------------------------------------------------------- output

def _norm_name(name):
    return ''.join(ch for ch in str(name or '').lower() if ch.isalnum())


def sleeper_links(roster_players, players_json):
    """gsis_id -> sleeper_id where (normalised name, position) is unique on both sides. Never guessed."""
    side = {}
    for p in (players_json or {}).get('players', []):
        side.setdefault((_norm_name(p.get('name')), p.get('pos')), []).append(str(p.get('sleeper_id')))
    out = {}
    counts = {}
    for p in roster_players:
        counts[(_norm_name(p.get('name')), p.get('position'))] = counts.get((_norm_name(p.get('name')), p.get('position')), 0) + 1
    for p in roster_players:
        key = (_norm_name(p.get('name')), p.get('position'))
        if counts[key] == 1 and len(side.get(key, [])) == 1:
            out[p['id']] = side[key][0]
    return out


def history_crosscheck(history, links, table):
    """Compares data/history.json season PPR/game (sleeper-keyed) with this build's own prior-season value for linked players. Provenance only."""
    if not history or not links:
        return None
    return {'history_generated_at': history.get('generated_at'), 'linked_players': len(links)}


def unavailable_ids():
    """Confirmed-unavailable gsis ids (scripts/eligibility.py, the mirror of shared/going-eligibility.js)."""
    return eligibility.confirmed_unavailable()


def build_output(table, panel, config, cfg_sha, roster, history, players_csv, as_of, current_key, history_keys, provenance, sleeper=None):
    scored = score_table(table, config)
    pool = scored[(scored.n_prior >= config['params']['min_games'])].copy()
    now = pool[pool.key == current_key]
    # Players who cannot play (reserve/injured list, practice squad, released, retired, exempt, suspended) are not ranked: the injury file knows more than the all-ACT roster file.
    unavailable = unavailable_ids()
    if unavailable:
        now = now[~now.player_id.isin(unavailable)]
    bye_teams = set((roster or {}).get('bye_carry_forward_teams') or [])
    by_key = {k: g.set_index('player_id') for k, g in pool.groupby('key')}
    roster_by = {p['id']: p for p in (roster or {}).get('players', [])}
    rookies = {}
    if players_csv is not None and len(players_csv):
        rookies = dict(zip(players_csv.gsis_id, players_csv.rookie_season))
    played_ppr = {(p, k): y for p, k, y in zip(panel.player_id, panel.key, panel.ppr)}
    players = {}
    for pos in POSITIONS:
        grp = now[now.position == pos]
        if grp.empty:
            continue
        cfg_pos = config['positions'][pos]
        comp_pct = {n: pool_percentile(grp[n].to_numpy(), np.zeros(len(grp))) for n in ALL_COMPONENTS}
        order = grp.raw_score.rank(ascending=False, method='min')
        z = zscores(grp, cfg_pos)
        for i, (_, r) in enumerate(grp.iterrows()):
            pid = r.player_id
            comps = {}
            for n in ALL_COMPONENTS:
                weight = 0.0 if n in DISPLAY_ONLY else cfg_pos['components'][n]['weight']
                total_w = sum(cfg_pos['components'][m]['weight'] for m in SCORED) or 1.0
                weight_norm = weight / total_w
                entry = {'raw': round(float(r[n]), 4), 'percentile': round(float(comp_pct[n][i]), 1), 'weight': round(weight_norm, 4), 'explanation': EXPLAIN[n]}
                if n in SCORED:
                    entry['z'] = round(float(z[n][i]), 3)
                    entry['contribution'] = round(weight_norm * float(z[n][i]), 4)
                comps[n] = entry
            hist = []
            for hk in history_keys:
                g = by_key.get(hk)
                if g is not None and pid in g.index and g.loc[pid, 'position'] == pos:
                    h = g.loc[pid]
                    hist.append({'season': hk // 100, 'week': hk % 100, 'score': round(float(h.pctile), 1), 'absolute': round(float(h.abs_score), 1),
                                 'played': (pid, hk) in played_ppr, 'ppr': round(float(played_ppr[(pid, hk)]), 1) if (pid, hk) in played_ppr else None})
                else:
                    hist.append({'season': hk // 100, 'week': hk % 100, 'score': None, 'absolute': None, 'played': (pid, hk) in played_ppr,
                                 'ppr': round(float(played_ppr[(pid, hk)]), 1) if (pid, hk) in played_ppr else None})
            valid = [h for h in hist if h['absolute'] is not None]
            d1 = round(valid[-1]['absolute'] - valid[-2]['absolute'], 1) if len(valid) >= 2 else None
            d3 = round(valid[-1]['absolute'] - valid[-4]['absolute'], 1) if len(valid) >= 4 else None
            flags = []
            rr = roster_by.get(pid, {})
            if rr.get('team') in bye_teams:
                flags.append('BYE:' + str(rr['team']))
            if rr.get('roster_status') and rr['roster_status'] != 'ACT':
                flags.append('ROSTER:' + str(rr['roster_status']))
            if rr.get('injury'):
                inj = rr['injury']
                if isinstance(inj, dict):
                    inj = ' '.join(str(x) for x in (inj.get('report_status') or inj.get('practice_status'), inj.get('primary_injury')) if x)
                flags.append('INJURY:' + str(inj)[:60])
            l3, l6 = r.snap_l3, r.snap_l6
            if pos != 'QB' and not (np.isnan(l3) or np.isnan(l6)):
                if l3 - l6 >= ROLE_RULE_SNAP:
                    flags.append('ROLE_UP')
                elif l3 - l6 <= -ROLE_RULE_SNAP:
                    flags.append('ROLE_DOWN')
            if r.n_prior < 6:
                flags.append('LIMITED_SAMPLE')
            if rookies.get(pid) == r.season:
                flags.append('ROOKIE')
            if r.availability < 0.6:
                flags.append('AVAILABILITY_RISK')
            players[pid] = {
                'name': r['name'], 'position': pos, 'team': (rr.get('team') or r.team), 'sleeper_id': (sleeper or {}).get(pid), 'season': int(r.season), 'week': int(r.week),
                'score': round(float(r.pctile), 1), 'absolute': round(float(r.abs_score), 1), 'tier': tier_for(float(r.pctile)),
                'rank': int(order.iloc[i]), 'of': int(len(grp)), 'games_used': int(r.n_window),
                'components': comps, 'history': hist, 'delta_1w': d1, 'delta_3w': d3, 'flags': flags,
            }
    movers = [(pid, p['delta_3w']) for pid, p in players.items() if p['delta_3w'] is not None]
    movers.sort(key=lambda x: x[1])
    risers = [{'id': pid, 'name': players[pid]['name'], 'position': players[pid]['position'], 'delta_3w': d} for pid, d in movers[::-1][:15] if d > 0]
    fallers = [{'id': pid, 'name': players[pid]['name'], 'position': players[pid]['position'], 'delta_3w': d} for pid, d in movers[:15] if d < 0]
    return {
        'schema': SCHEMA, 'methodology_version': config['version'], 'as_of': as_of, 'season': current_key // 100, 'week': current_key % 100,
        'meaning': 'Player-level situation index: opportunity, role, availability and how they are changing, from games before this week. Not a projection, a probability or a betting edge; a higher score is not a better bet.',
        'score_definition': 'score = percentile (0-100) of the weighted component z-score among eligible players at the same position; absolute = the same z-score mapped to 0-100 with frozen development anchors',
        'tiers': [{'id': i, 'label': l, 'min_percentile': f} for f, i, l in TIERS], 'eligibility': {'min_prior_games': config['params']['min_games'], 'max_team_games_since_last_appearance': config['params']['max_stale_team_games']},
        'weights': {pos: {n: round(config['positions'][pos]['components'][n]['weight'], 4) for n in SCORED} for pos in POSITIONS if pos in config['positions']},
        'availability': eligibility.freshness(), 'provenance': provenance, 'config_sha256': cfg_sha, 'counts': {pos: int((now.position == pos).sum()) for pos in POSITIONS},
        'players': players, 'risers': risers, 'fallers': fallers,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--cache', default=str(REPO / '.cache' / 'going_score'))
    ap.add_argument('--out', default=str(REPO / 'data' / 'going_score.json'))
    ap.add_argument('--config', default=str(REPO / 'config' / 'going_score_weights.json'))
    ap.add_argument('--history', default=str(REPO / 'data' / 'history.json'))
    ap.add_argument('--roster', default=str(REPO / 'data' / 'nfl_roster.json'))
    ap.add_argument('--players-json', default=str(REPO / 'data' / 'players.json'))
    ap.add_argument('--season', type=int, default=None)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--first-season', type=int, default=None)
    args = ap.parse_args(argv)
    cfg_path = Path(args.config)
    config = load_config(cfg_path)
    cfg_sha = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
    now = datetime.now(timezone.utc)
    season = args.season or now.year
    first = args.first_season or season - 2
    seasons = list(range(first, season + 1))
    weekly, snaps, players, ffopp = load_public(args.cache, seasons, season, args.offline)
    panel, team_games, league_weeks = build_panel(weekly, snaps, players, ffopp, config['params']['qb_min_attempts'])
    last = int(panel[panel.season == season].week.max()) if (panel.season == season).any() else None
    if last is None:
        raise SystemExit(f'no {season} regular-season data yet')
    all_weeks = sorted(key_of(s, w) for s in league_weeks for w in league_weeks[s])
    nxt = key_of(season, last + 1)
    keys_all = all_weeks + ([nxt] if nxt not in all_weeks else [])
    history_keys = keys_all[-8:]
    params = {**DEFAULT_PARAMS, **config['params']}
    priors = {pos: config['positions'][pos]['priors'] for pos in POSITIONS if pos in config['positions']}
    table = asof_table(panel, team_games, league_weeks, params, priors, all_week_seasons=(), appearance_seasons=(), extra_keys=history_keys)
    roster = json.loads(Path(args.roster).read_text(encoding='utf-8')) if Path(args.roster).exists() else None
    history = json.loads(Path(args.history).read_text(encoding='utf-8')) if Path(args.history).exists() else None
    pj = json.loads(Path(args.players_json).read_text(encoding='utf-8')) if Path(args.players_json).exists() else None
    links = sleeper_links((roster or {}).get('players', []), pj) if roster else {}
    provenance = {
        'sources': [{'name': 'nflverse player stats', 'url': URLS['weekly'], 'public': True}, {'name': 'nflverse snap counts', 'url': URLS['snaps'], 'public': True},
                    {'name': 'ffverse ffopportunity expected points', 'url': URLS['ffopp'], 'public': True}, {'name': 'nflverse players', 'url': URLS['players'], 'public': True},
                    {'name': 'GOING nfl_roster.json (nflverse rosters/injuries) for flags', 'public': True}],
        'licensed_data_used': False, 'seasons': seasons, 'last_stats_week': {'season': season, 'week': last},
        'ffopportunity_rows': int(len(ffopp)), 'history_json_generated_at': (history or {}).get('generated_at'), 'history_linked_players': len(links),
        'weights_fit': config.get('fit'), 'validation': config.get('validation_ref'),
    }
    out = build_output(table, panel, config, cfg_sha, roster, history, players, now.strftime('%Y-%m-%dT%H:%M:%SZ'), nxt, history_keys, provenance, links)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"[going_score] wrote {args.out}: {sum(out['counts'].values())} players, week {out['season']}-{out['week']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
