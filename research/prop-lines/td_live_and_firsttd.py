#!/usr/bin/env python3
"""Task 3 (part 2): live-tracker anytime-TD calibration, first/last-TD outcome availability, and tests of the assumptions inside first_td_game.
usage: td_live_and_firsttd.py QUOTES_PARQUET      (QUOTES_PARQUET from build_quotes.py). Network: public nflreadpy 2026 pbp, in memory only. Aggregates only."""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import calibration_audit_a as A  # noqa: E402
CACHE = ROOT.parent / 'GOING' / 'FantasyPoints' / 'research' / 'cache'
rng = np.random.default_rng(1)

# ---------------- 1. live tracker, anytime TD
df, _ = A.load_frame()
d = A.settled_universe(df[(df.sport == 'nfl') & (df.market == 'atd')])
U = d.drop_duplicates('contract')
print('LIVE tracker atd: predictions', int((df.market == 'atd').sum()), '| settled win/loss pregame unique contracts', len(U), '| games', U.game.nunique(), '| weeks', sorted(U.ko_t.dt.strftime('%m-%d').unique())[:3], '..')
print('  cohorts', U.cohort.value_counts().to_dict(), '| sides', U.side.value_counts().to_dict())
for coh, g in [('all', U)] + list(U.groupby('cohort')):
    if len(g) < 30:
        continue
    y, p = g.y.to_numpy(), g.p.to_numpy()
    a, b = A.fit_cal(A.logit(p), y, np.ones(len(g)))
    cl, k = pd.factorize(g.game); bs = []
    for _ in range(600):
        w = rng.multinomial(k.size, np.full(k.size, 1 / k.size))[cl].astype(float)
        bs.append(A.fit_cal(A.logit(p), y, w)[1])
    print(f'  {coh:24s} n={len(g):4d} meanP {p.mean():.3f} obs {y.mean():.3f} Brier {np.mean((p - y) ** 2):.4f} baseBrier {y.mean() * (1 - y.mean()):.4f} slope {b:.2f} [{np.nanpercentile(bs, 2.5):.2f},{np.nanpercentile(bs, 97.5):.2f}] int {a:+.2f}')

# ---------------- 2. pbp: assumptions in first_td_game
cols = ['game_id', 'play_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'td_team', 'td_player_id', 'td_player_name', 'touchdown', 'two_point_attempt', 'play_deleted', 'play_type',
        'kickoff_attempt', 'punt_attempt', 'game_seconds_remaining', 'qtr', 'rush_attempt', 'pass_attempt', 'home_team', 'away_team']
parts = []
for y in range(2021, 2026):
    p = pd.read_parquet(CACHE / f'pbp_{y}.parquet', columns=cols)
    parts.append(p[p.season_type == 'REG'])
import nflreadpy as nfl
p26 = nfl.load_pbp([2026]).to_pandas()
p26 = p26[p26.season_type == 'REG'][cols]
pbp = pd.concat(parts + [p26])
td = pbp[(pbp.touchdown == 1) & (pbp.two_point_attempt != 1) & (pbp.play_deleted != 1) & (pbp.play_type != 'no_play') & pbp.td_team.notna()].copy()
td['offense'] = (td.td_team == td.posteam) & (td.kickoff_attempt != 1) & (td.punt_attempt != 1)
td = td.sort_values(['game_id', 'play_id'])
sched = pd.read_csv(CACHE / 'games.csv'); sched = sched[(sched.season >= 2021) & (sched.game_type == 'REG')]
sched26 = sched[sched.season == 2026]
print('\nFIRST/LAST-TD outcome availability (public nflverse pbp, regular season)')
for yr, g in td.groupby(td.game_id.str[:4]):
    n_games = pbp[pbp.game_id.str[:4] == yr].game_id.nunique()
    print(f'  {yr}: games {n_games}, games with >=1 TD {g.game_id.nunique()}, first-TD scorer by non-offense (def/ST) {((g.groupby("game_id").offense.first() == False).mean()):.3f}')
tot = td.groupby('game_id').agg(first_off=('offense', 'first'), last_off=('offense', 'last'), n_td=('play_id', 'size'))
hist = tot[~tot.index.str.startswith('2026')]
print(f'  2021-25: games {len(hist)}, first TD by def/ST {(~hist.first_off).mean():.3f} (assumed dst_hazard_share .06/.94 of offense mass = {.06:.3f} of first-TD mass), last TD by def/ST {(~hist.last_off).mean():.3f}')

# offense TD scale: expected_td = ((total +/- margin)/2) * .75 / 7 vs actual offensive TDs per team-game, using closing lines in games.csv
off = td[td.offense].groupby(['game_id', 'td_team']).size().rename('off_td').reset_index()
rows = []
for r in sched.itertuples():
    if not np.isfinite(r.total_line) or not np.isfinite(r.spread_line) or not np.isfinite(r.home_score):
        continue
    for team, pts, margin in ((r.home_team, r.home_score, r.spread_line), (r.away_team, r.away_score, -r.spread_line)):
        exp_pts = (r.total_line + margin) / 2
        n = off[(off.game_id == r.game_id) & (off.td_team == team)].off_td.sum() if False else None
        rows.append((r.game_id, team, pts, exp_pts))
T = pd.DataFrame(rows, columns=['game_id', 'team', 'pts', 'exp_pts'])
T = T.merge(off.rename(columns={'td_team': 'team'}), on=['game_id', 'team'], how='left').fillna({'off_td': 0})
T['exp_td_model'] = T.exp_pts * .75 / 7
print(f'\nTEAM OFFENSIVE-TD SCALE (2021-25 + 2026 played, {len(T)} team-games, closing lines):')
print(f'  mean points {T.pts.mean():.2f} (closing-line implied {T.exp_pts.mean():.2f}) | mean offensive TDs {T.off_td.mean():.3f} | model expected_td {T.exp_td_model.mean():.3f} | ratio actual/model {T.off_td.mean() / T.exp_td_model.mean():.3f}')
print(f'  points from offensive TDs (7 each) / points = {7 * T.off_td.sum() / T.pts.sum():.3f}  (code assumes .75)')
cl, k = pd.factorize(T.game_id); bs = []
for _ in range(500):
    w = rng.multinomial(k.size, np.full(k.size, 1 / k.size))[cl]
    bs.append(np.sum(w * T.off_td.to_numpy()) / np.sum(w * T.exp_td_model.to_numpy()))
print(f'  ratio actual/model CI [{np.percentile(bs, 2.5):.3f}, {np.percentile(bs, 97.5):.3f}]')
by = T.assign(bin=pd.qcut(T.exp_pts, 5)).groupby('bin', observed=True).agg(exp_pts=('exp_pts', 'mean'), off_td=('off_td', 'mean'), model=('exp_td_model', 'mean'))
print('  by expected-points quintile: actual vs model TDs', [(round(a, 1), round(b, 2), round(c, 2)) for a, b, c in zip(by.exp_pts, by.off_td, by.model)])
print('  slope of actual offensive TDs on closing-line expected points:', round(np.polyfit(T.exp_pts, T.off_td, 1)[0], 4), ' (code: .75/7 = %.4f)' % (.75 / 7))

# ---------------- 3. 2026 first-TD quotes vs outcomes (market only; the model's first-TD probabilities for past weeks were never archived)
q = pd.read_parquet(sys.argv[1])
q = q[(q.market == 'first_td') & (q.gameday <= '2026-10-08') & q.over.notna() & q.pid.notna()].copy()
first = td[td.game_id.str.startswith('2026')].groupby('game_id').first().reset_index()
gm = sched26[['game_id', 'gameday']]
first = first.merge(gm, on='game_id')
fid = {(r.gameday, r.td_player_id) for r in first.itertuples()}
q['hit'] = [(g, p) in fid for g, p in zip(q.gameday, q.pid)]
dec = lambda a: 1 + a / 100 if a > 0 else 1 + 100 / -a
q['imp'] = 1 / q.over.map(dec)
c = q.groupby(['gameday', 'pid', 'book']).last().reset_index()
cons = c.groupby(['gameday', 'pid']).agg(imp=('imp', 'mean'), hit=('hit', 'max'), nb=('book', 'nunique')).reset_index()
print('\n2026 FIRST-TD priced quotes (pre-kickoff), played games with outcomes: player-games', len(cons), 'games', cons.gameday.nunique(), 'hits', int(cons.hit.sum()), '(games with a first TD:', len(first), ')')
cons['band'] = pd.cut(cons.imp, [0, .02, .04, .06, .1, .2, 1])
t = cons.groupby('band', observed=True).agg(n=('hit', 'size'), implied=('imp', 'mean'), hit_rate=('hit', 'mean'))
print(t.round(4).to_string())
print('  sum implied per game (overround across posted candidates) median:', round(cons.groupby('gameday').imp.sum().median(), 2), '| hits per priced-candidate set: share of games whose first scorer had a price:', round(cons[cons.hit].gameday.nunique() / max(1, len(first)), 3))
