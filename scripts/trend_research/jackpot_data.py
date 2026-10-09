"""Point-in-time scoring-role data for the Jackpot TD markets (anytime / first / last TD, longest TD).

Everything here is built from FREE public nflverse data (play-by-play, weekly stats, snap counts, schedule lines). Every pre-game feature of a player-game is a function of
that player's EARLIER appearances (``shift(1)`` before any rolling window) or of pre-game information (closing schedule line, who was active). The outcome columns (``y_*``)
are never used as features. See experiments11.py for the pre-registered use.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from . import champion

PBP_URL = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet'
PBP_COLS = ['game_id', 'play_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'qtr', 'yardline_100', 'play_type', 'rush_attempt', 'pass_attempt', 'qb_kneel',
            'qb_spike', 'touchdown', 'td_team', 'td_player_id', 'rusher_player_id', 'receiver_player_id', 'air_yards', 'yards_gained', 'two_point_attempt', 'no_play',
            'play_deleted', 'kickoff_attempt', 'punt_attempt', 'return_yards', 'fumble', 'fumble_recovery_1_team', 'fumble_recovery_1_yards', 'fumble_recovery_2_team',
            'fumble_recovery_2_yards', 'pass_touchdown', 'score_differential', 'fixed_drive', 'game_seconds_remaining']
ZONES = [('z1', 0, 1), ('z2', 1, 2), ('z3_5', 2, 5), ('z6_10', 5, 10), ('z11_20', 10, 20)]  # yardline_100 in (lo, hi]


def load_pbp(root, seasons):
    frames = []
    for s in seasons:
        path = champion._download(PBP_URL.format(season=s), champion.cache(root) / f'pbp_{s}.parquet')
        import pyarrow.parquet as pq
        have = set(pq.ParquetFile(path).schema.names)
        frame = pd.read_parquet(path, columns=[c for c in PBP_COLS if c in have])
        for missing in PBP_COLS:
            if missing not in frame.columns:
                frame[missing] = np.nan
        frames.append(frame[frame.season_type == 'REG'])
    return pd.concat(frames, ignore_index=True)


# ------------------------------------------------------------------ touchdown events
def td_events(pbp):
    """One row per touchdown (not 2-pt tries, not nullified plays) in game order: scorer, scoring team, kind, distance, order within the game."""
    t = pbp[(pbp.touchdown == 1) & (pbp.two_point_attempt.fillna(0) != 1) & (pbp.no_play.fillna(0) != 1) & (pbp.play_deleted.fillna(0) != 1)
            & (pbp.play_type != 'no_play') & pbp.td_team.notna()].copy()
    ret = (t.kickoff_attempt.fillna(0) == 1) | (t.punt_attempt.fillna(0) == 1)
    defense = (~ret) & (t.td_team != t.posteam)
    t['kind'] = np.where(ret, 'return', np.where(defense, 'defense', np.where(t.pass_touchdown == 1, 'receive', 'rush')))
    dist = np.where(t.kind.isin(['return', 'defense']), t.return_yards, t.yards_gained)
    for i in (1, 2):  # defensive fumble-return TDs: use the recovery return yards, as king_endzone.td_event does
        mask = (t.kind == 'defense') & (t.fumble == 1) & (t[f'fumble_recovery_{i}_team'] == t.td_team)
        dist = np.where(mask, t[f'fumble_recovery_{i}_yards'], dist)
    t['distance'] = pd.to_numeric(dist, errors='coerce')
    t = t.sort_values(['game_id', 'play_id']).reset_index(drop=True)
    t['n_td'] = t.groupby('game_id').game_id.transform('size')
    t['td_idx'] = t.groupby('game_id').cumcount()
    t['is_first'] = t.td_idx == 0
    t['is_last'] = t.td_idx == t.n_td - 1
    valid = t.distance.between(0, 109)
    longest = t.assign(_d=t.distance.where(valid)).groupby('game_id')._d.transform('max')
    t['is_longest'] = valid & (t.distance == longest)
    return t[['game_id', 'season', 'week', 'play_id', 'posteam', 'td_team', 'td_player_id', 'kind', 'distance', 'qtr', 'yardline_100', 'n_td', 'td_idx', 'is_first',
              'is_last', 'is_longest', 'fixed_drive', 'game_seconds_remaining']]


# ------------------------------------------------------------------ opportunities
def opportunity_plays(pbp):
    """Designed carries (incl. scrambles, excl. kneels) and targets with their zone and script flags, one row per play-player."""
    p = pbp[(pbp.no_play.fillna(0) != 1) & (pbp.play_deleted.fillna(0) != 1) & (pbp.play_type != 'no_play') & (pbp.qb_kneel.fillna(0) != 1) & (pbp.qb_spike.fillna(0) != 1)
            & pbp.posteam.notna() & pbp.yardline_100.notna()].copy()
    rush = p[(p.rush_attempt == 1) & p.rusher_player_id.notna()].assign(player_id=lambda d: d.rusher_player_id, kind='car')
    tgt = p[(p.pass_attempt == 1) & p.receiver_player_id.notna()].assign(player_id=lambda d: d.receiver_player_id, kind='tgt')
    ops = pd.concat([rush, tgt], ignore_index=True)
    # the team's possession ordinal in the game (1 = its first drive): first two possessions are the "opening script"
    team_drive = ops.groupby(['game_id', 'posteam']).fixed_drive.rank(method='dense')
    ops['open'] = team_drive <= 2
    ops['late_lead'] = (ops.qtr >= 4) & (ops.score_differential > 0)
    ops['air'] = ops.air_yards.where(ops.kind == 'tgt')
    return ops


def zone_rates(ops, events, seasons):
    """League TD conversion per opportunity in each yard-line zone and type (carry / target); fitted on `seasons` only."""
    ops = ops[ops.season.isin(seasons)]
    scored = events[(events.kind.isin(['rush', 'receive'])) & events.season.isin(seasons)]
    key = scored[['game_id', 'play_id']].assign(td=1)
    ops = ops.merge(key, on=['game_id', 'play_id'], how='left')
    ops['td'] = ops.td.fillna(0)
    rates = {}
    for kind in ('car', 'tgt'):
        for name, lo, hi in ZONES:
            sub = ops[(ops.kind == kind) & (ops.yardline_100 > lo) & (ops.yardline_100 <= hi)]
            rates[(kind, name)] = float(sub.td.mean()) if len(sub) else 0.0
        far = ops[(ops.kind == kind) & (ops.yardline_100 > 20)]
        rates[(kind, 'far')] = float(far.td.mean())
    return rates


def player_game_opportunity(ops, rates):
    """Per (player, game): carries / targets by zone, expected TDs from those opportunities, opening-script and late-lead counts."""
    o = ops.copy()
    cols = {}
    xtd = np.zeros(len(o))
    for kind in ('car', 'tgt'):
        k = o.kind == kind
        for name, lo, hi in ZONES:
            m = k & (o.yardline_100 > lo) & (o.yardline_100 <= hi)
            xtd += np.where(m, rates[(kind, name)], 0.0)
        xtd += np.where(k & (o.yardline_100 > 20), rates[(kind, 'far')], 0.0)
    o['xtd'] = xtd
    o['car'] = (o.kind == 'car').astype(float)
    o['tgt'] = (o.kind == 'tgt').astype(float)
    o['rz_car'] = o.car * (o.yardline_100 <= 20)
    o['i10_car'] = o.car * (o.yardline_100 <= 10)
    o['i5_car'] = o.car * (o.yardline_100 <= 5)
    o['gl_car'] = o.car * (o.yardline_100 <= 2)
    o['rz_tgt'] = o.tgt * (o.yardline_100 <= 20)
    o['i10_tgt'] = o.tgt * (o.yardline_100 <= 10)
    o['i5_tgt'] = o.tgt * (o.yardline_100 <= 5)
    o['open_opp'] = (o.open).astype(float)
    o['late_car'] = o.car * o.late_lead
    o['air_sum'] = o.air.fillna(0)
    o['air_n'] = o.air.notna().astype(float)
    sums = ['xtd', 'car', 'tgt', 'rz_car', 'i10_car', 'i5_car', 'gl_car', 'rz_tgt', 'i10_tgt', 'i5_tgt', 'open_opp', 'late_car', 'air_sum', 'air_n']
    g = o.groupby(['game_id', 'player_id', 'posteam'], as_index=False)[sums].sum()
    # team denominators for shares
    team = o.groupby(['game_id', 'posteam'], as_index=False).agg(t_open=('open_opp', 'sum'), t_late_car=('late_car', 'sum'), t_xtd=('xtd', 'sum'))
    g = g.merge(team, on=['game_id', 'posteam'])
    g['open_share'] = g.open_opp / g.t_open.replace(0, np.nan)
    g['late_share'] = g.late_car / g.t_late_car.replace(0, np.nan)
    g['xtd_share'] = g.xtd / g.t_xtd.replace(0, np.nan)
    return g.rename(columns={'posteam': 'team'})


# ------------------------------------------------------------------ appearances + outcomes
def build_player_games(root, seasons, rates_seasons):
    """One row per offensive appearance (QB/RB/WR/TE) with opportunities, outcomes (y_any / y_first / y_last / y_longest) and game keys."""
    pbp = load_pbp(root, seasons)
    events = td_events(pbp)
    ops = opportunity_plays(pbp)
    rates = zone_rates(ops, events, rates_seasons)
    opp = player_game_opportunity(ops, rates)
    apps = champion.appearances(root, seasons)
    games = champion.load_games(root)
    games = games[games.game_type == 'REG']
    key = {}
    for r in games.itertuples():
        key[(r.season, r.week, r.home_team)] = (r.game_id, r.away_team, 1, r.spread_line, r.total_line, r.gameday)
        key[(r.season, r.week, r.away_team)] = (r.game_id, r.home_team, 0, r.spread_line, r.total_line, r.gameday)
    info = [key.get((s, w, t)) for s, w, t in zip(apps.season, apps.week, apps.team)]
    apps = apps[[i is not None for i in info]].copy()
    info = [i for i in info if i is not None]
    apps['game_id'] = [i[0] for i in info]
    apps['opp_team'] = [i[1] for i in info]
    apps['home'] = [i[2] for i in info]
    spread, total = np.array([i[3] for i in info], float), np.array([i[4] for i in info], float)
    # nflverse spread_line is the HOME team's expected margin of victory-negative convention: positive = home favoured
    margin = np.where(apps.home == 1, spread, -spread)
    apps['team_margin_line'] = margin
    apps['team_implied'] = (total + margin) / 2
    apps['opp_implied'] = (total - margin) / 2
    apps['game_total'] = total
    apps['date'] = [i[5] for i in info]
    apps = apps[apps.position.isin(['QB', 'RB', 'WR', 'TE'])]
    apps = apps.merge(opp.drop(columns=['team']), on=['game_id', 'player_id'], how='left')
    zero = [c for c in opp.columns if c not in ('game_id', 'player_id', 'team', 'open_share', 'late_share', 'xtd_share', 't_open', 't_late_car', 't_xtd')]
    apps[zero] = apps[zero].fillna(0.0)
    apps[['open_share', 'late_share', 'xtd_share']] = apps[['open_share', 'late_share', 'xtd_share']].fillna(0.0)
    # outcomes
    scorers = events[events.td_player_id.notna()]
    anyt = scorers.groupby(['game_id', 'td_player_id']).size().rename('y_tds')
    apps = apps.merge(anyt, left_on=['game_id', 'player_id'], right_index=True, how='left')
    apps['y_tds'] = apps.y_tds.fillna(0)
    apps['y_any'] = (apps.y_tds > 0).astype(int)
    for flag in ('first', 'last', 'longest'):
        who = scorers[scorers['is_' + flag]].groupby(['game_id', 'td_player_id']).size().rename('y_' + flag)
        apps = apps.merge(who, left_on=['game_id', 'player_id'], right_index=True, how='left')
        apps['y_' + flag] = apps['y_' + flag].fillna(0).astype(float)
    # the player's own TD distances (for long-TD propensity): TD rows by scorer
    return apps.reset_index(drop=True), events, rates


# ------------------------------------------------------------------ rolling, strictly-before features
def _prior_roll(frame, cols, n, how='mean'):
    """Per-player rolling window over the player's OWN previous appearances (shift(1) first, so the current game never enters)."""
    g = frame.groupby('player_id', sort=False)[cols]
    shifted = g.shift(1)
    shifted['player_id'] = frame.player_id.values
    roll = shifted.groupby('player_id', sort=False)[cols].rolling(n, min_periods=1)
    out = (roll.mean() if how == 'mean' else roll.sum()).reset_index(level=0, drop=True)
    return out.reindex(frame.index)


def add_features(apps, events, root):
    """Adds every candidate pre-game feature. `apps` must be sorted by player, season, week (done here)."""
    a = apps.sort_values(['player_id', 'season', 'week']).reset_index(drop=True)
    new = {}
    base_cols = ['xtd', 'y_tds', 'rz_car', 'i10_car', 'i5_car', 'gl_car', 'rz_tgt', 'i10_tgt', 'i5_tgt', 'xtd_share', 'open_share', 'late_share', 'carries', 'targets',
                 'offense_pct']
    snaps = champion.load_snaps(root, sorted(a.season.unique()))
    snaps = snaps[(snaps.game_type == 'REG') & snaps.offense_snaps.notna()]
    players = champion.load_players(root).dropna(subset=['pfr_id', 'gsis_id'])
    snaps = snaps.assign(player_id=snaps.pfr_player_id.map(dict(zip(players.pfr_id, players.gsis_id)))).dropna(subset=['player_id'])
    snaps = snaps.drop_duplicates(['player_id', 'season', 'week'])[['player_id', 'season', 'week', 'offense_pct']]
    a = a.merge(snaps, on=['player_id', 'season', 'week'], how='left')
    a['offense_pct'] = a.offense_pct.astype(float)
    a = a.sort_values(['player_id', 'season', 'week']).reset_index(drop=True)
    for n in (3, 6, 12):
        r = _prior_roll(a, base_cols, n)
        for c in base_cols:
            new[f'{c}__L{n}'] = r[c]
    r12 = _prior_roll(a, ['rz_car', 'rz_tgt', 'air_sum', 'air_n'], 12, 'sum')
    new['adot__L12'] = r12['air_sum'] / r12['air_n'].replace(0, np.nan)
    new['cnt__L12'] = a.groupby('player_id').cumcount().clip(upper=12)
    a = pd.concat([a, pd.DataFrame(new, index=a.index)], axis=1)
    # long-TD propensity from the player's own earlier touchdowns (strictly earlier games)
    ev = events[events.td_player_id.notna() & events.kind.isin(['rush', 'receive'])].copy()
    ev['long'] = (ev.distance >= 30).astype(float)
    ev = ev.merge(a[['game_id', 'player_id', 'season', 'week']].rename(columns={'player_id': 'td_player_id', 'season': 's2', 'week': 'w2'}), on=['game_id', 'td_player_id'], how='left')
    per = ev.groupby(['td_player_id', 'game_id'], as_index=False).agg(n=('long', 'size'), long=('long', 'sum'))
    per = per.rename(columns={'td_player_id': 'player_id', 'n': 'td_n', 'long': 'td_long'})
    a = a.merge(per, on=['player_id', 'game_id'], how='left')
    a[['td_n', 'td_long']] = a[['td_n', 'td_long']].fillna(0)
    a = a.sort_values(['player_id', 'season', 'week']).reset_index(drop=True)
    cum = a.groupby('player_id')[['td_n', 'td_long']].cumsum() - a[['td_n', 'td_long']]  # strictly earlier games only
    a['prior_td_n'], a['prior_td_long'] = cum.td_n, cum.td_long
    # team context: implied total is a pre-game line; win probability from the spread (normal, sd 13.5)
    from scipy.stats import norm
    a['team_win_p'] = norm.cdf(a.team_margin_line / 13.5)
    a = _vacated(a)
    a = _team_open(a, events)
    return a


def _vacated(a):
    """Injury-created opportunity: expected-TD mass (L6 per-game xTD) of teammates who were regulars in the team's previous 6 games and are ABSENT this game
    (known pre-game from inactives), allocated to each active player by his own share of the active players' L6 xTD. The `present` flag uses the same appearance table
    the Champion uses (snaps > 0 or a stat line), i.e. what the inactive list reveals about 90 minutes before kickoff."""
    a = a.copy()
    a['key'] = a.season * 100 + a.week
    a['xtd6'] = a['xtd__L6'].fillna(0.0)
    vac = {}
    for team, frame in a.groupby('team', sort=False):
        order = sorted(frame.key.unique())
        by_game = {k: g for k, g in frame.groupby('key')}
        for i, k in enumerate(order):
            window = order[max(0, i - 6):i]
            if len(window) < 3:
                continue
            present = set(by_game[k].player_id)
            hist = pd.concat([by_game[w] for w in window])
            counts = hist.groupby('player_id').size()
            regulars = counts[counts >= 3].index
            gone = [p for p in regulars if p not in present]
            if not gone:
                vac[(team, k)] = 0.0
                continue
            # the absent player's mean xTD over his appearances in the window (what he used to take); taken from the rows of the window itself
            lost = hist[hist.player_id.isin(gone)].groupby('player_id').xtd.mean().sum()
            vac[(team, k)] = float(lost)
    a['team_vacated_xtd'] = [vac.get((t, k), np.nan) for t, k in zip(a.team, a.key)]
    tot = a.groupby(['team', 'key']).xtd6.transform('sum')
    share = a.xtd6 / tot.replace(0, np.nan)
    a['vac_alloc'] = (a.team_vacated_xtd * share).fillna(0.0)
    return a.drop(columns=['key', 'xtd6'])


def _team_open(a, events):
    """Team opening-script scoring: rate of games in which the team scored the game's first TD (and TD on its first two possessions), prior 8 team games."""
    ev = events.copy()
    first = ev[ev.is_first].groupby(['game_id', 'td_team']).size().rename('t_first').reset_index().rename(columns={'td_team': 'team'})
    open_td = ev[(ev.kind.isin(['rush', 'receive']))].copy()
    team_games = a[['game_id', 'team', 'season', 'week']].drop_duplicates().sort_values(['team', 'season', 'week']).reset_index(drop=True)
    team_games = team_games.merge(first, on=['game_id', 'team'], how='left')
    team_games['t_first'] = team_games.t_first.fillna(0).clip(upper=1)
    roll = team_games.groupby('team')['t_first'].apply(lambda s: s.shift(1).rolling(8, min_periods=3).mean()).reset_index(level=0, drop=True)
    team_games['tm_first_td_rate'] = roll
    return a.merge(team_games[['game_id', 'team', 'tm_first_td_rate']], on=['game_id', 'team'], how='left')
