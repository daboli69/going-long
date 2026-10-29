"""Independent reimplementation of NBA_AVAIL_FEATURE_SPEC.md. Run from repo root:
   .venv\\Scripts\\python.exe research_nba_xgb\\second_impl\\second_features.py
"""
import glob, os, time, math
import numpy as np, pandas as pd
import scipy.sparse as sp
from scipy.linalg import cho_factor, cho_solve
from sklearn.linear_model import LogisticRegression

OUT = 'research_nba_xgb/second_impl'
t0 = time.time()


def sid(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NA:
            return None
        return str(int(float(x)))
    except Exception:
        return str(x)


games = pd.read_parquet('research_nba_xgb/canonical/games.parquet')
games = games[games.completed & games.verified].copy()
games['game_id'] = games.game_id.map(sid)
games['home_id'] = games.home_id.map(sid)
games['away_id'] = games.away_id.map(sid)
glab = games.set_index('game_id')
labelled = set(glab.index)

# ---------------------------------------------------------------- stints
def clock_secs(s):
    s = str(s)
    if ':' in s:
        m, x = s.split(':')
        return int(m) * 60 + float(x)
    return float(s)


def elapsed(p, rem):
    if p <= 4:
        return 720 * (p - 1) + (720 - rem)
    return 2880 + 300 * (p - 5) + (300 - rem)


def kind_of(t):
    t = t or ''
    if t.startswith('Free Throw'): return 'FTA'
    if t == 'Offensive Rebound': return 'OREB'
    if 'Turnover' in t: return 'TOV'
    if t == 'Substitution': return 'SUB'
    return 'OTHER'


box = pd.read_parquet('data/cache/player_boxes.parquet',
                      columns=['game_id', 'team_id', 'athlete_id', 'minutes', 'did_not_play', 'starter'])
box['game_id'] = box.game_id.map(sid)
box = box[box.game_id.isin(labelled)].copy()
box['team_id'] = box.team_id.map(sid)
box['athlete_id'] = box.athlete_id.map(sid)
box['played'] = (box.minutes.fillna(0) > 0) & (~box.did_not_play.fillna(False).astype(bool))
box_starters = {}
for (g, t), d in box[box.starter.fillna(False).astype(bool)].groupby(['game_id', 'team_id']):
    box_starters[(g, t)] = set(d.athlete_id)


def process_game(gid, ev, home, away):
    """ev: dict of numpy arrays. Returns list of stint tuples or None."""
    n = len(ev['kind'])
    teams = ev['team']
    a1, a2 = ev['a1'], ev['a2']
    kinds = ev['kind']
    issub = ev['issub']
    starters = {}
    for tm in (home, away):
        seen, st = set(), []
        for i in range(n):
            if teams[i] != tm:
                continue
            if issub[i]:
                if a2[i] is not None and a2[i] not in seen:
                    st.append(a2[i])
                    seen.add(a2[i])
                for a in (a1[i], a2[i]):
                    if a is not None: seen.add(a)
            else:
                actors = [a1[i]]
                if ev['scoring'][i] and kinds[i] == 'OTHER':
                    actors.append(a2[i])
                for a in actors:
                    if a is not None and a not in seen:
                        st.append(a)
                        seen.add(a)
        st = list(dict.fromkeys(st))
        if len(st) != 5:
            bs = box_starters.get((gid, tm))
            if bs is not None and len(bs) == 5:
                st = list(bs)
            else:
                return None
        starters[tm] = set(st)
    court = {home: set(starters[home]), away: set(starters[away])}
    out = []
    start_t = 0.0
    start_h = start_a = 0
    cnt = {home: [0.0, 0.0, 0.0, 0.0], away: [0.0, 0.0, 0.0, 0.0]}  # fga fta oreb tov
    start_court = (frozenset(court[home]), frozenset(court[away]))

    def close(end_t, hs, as_):
        if end_t <= start_t:
            return
        ph = cnt[home][0] + 0.44 * cnt[home][1] - cnt[home][2] + cnt[home][3]
        pa = cnt[away][0] + 0.44 * cnt[away][1] - cnt[away][2] + cnt[away][3]
        out.append((start_t, end_t, start_court[0], start_court[1], hs - start_h, as_ - start_a, ph, pa))

    for i in range(n):
        t = ev['t'][i]
        if issub[i]:
            tm = teams[i]
            if tm not in court:
                continue
            ent, lea = a1[i], a2[i]
            if lea not in court[tm] or ent in court[tm]:
                return None
            if t > start_t:
                close(t, ev['hs'][i], ev['as'][i])
                start_t = t
                start_h, start_a = ev['hs'][i], ev['as'][i]
                cnt = {home: [0.0] * 4, away: [0.0] * 4}
                start_court = (frozenset(court[home]), frozenset(court[away]))
                # lineups unchanged until swap; start_court recorded after swap below
            court[tm].remove(lea)
            court[tm].add(ent)
            start_court = (frozenset(court[home]), frozenset(court[away]))
        else:
            tm = teams[i]
            if tm in cnt:
                k = kinds[i]
                if k == 'FTA': cnt[tm][1] += 1
                elif k == 'OREB': cnt[tm][2] += 1
                elif k == 'TOV': cnt[tm][3] += 1
                elif k == 'OTHER' and ev['shoot'][i]: cnt[tm][0] += 1
    close(ev['t'][n - 1], ev['hs'][n - 1], ev['as'][n - 1])
    return out


stint_rows = []  # per stint
dropped = 0
nproc = 0
for season in range(2021, 2027):
    files = sorted(glob.glob(f'data/raw/archive/pbp_{season}/*.parquet'))
    if not files:
        continue
    p = pd.read_parquet(files[-1], columns=['game_id', 'season_type', 'game_play_number', 'type_text', 'text', 'team_id',
                                            'athlete_id_1', 'athlete_id_2', 'period_number', 'clock_display_value',
                                            'home_score', 'away_score', 'scoring_play', 'shooting_play'])
    p = p[p.season_type == 2]
    p['game_id'] = p.game_id.map(sid)
    p = p[p.game_id.isin(labelled)].sort_values(['game_id', 'game_play_number'])
    for gid, d in p.groupby('game_id', sort=False):
        nproc += 1
        home, away = glab.at[gid, 'home_id'], glab.at[gid, 'away_id']
        kinds = [kind_of(x) for x in d.type_text.tolist()]
        texts = d.text.fillna('').tolist()
        issub = [k == 'SUB' and 'enters the game for' in tx for k, tx in zip(kinds, texts)]
        ev = dict(
            kind=kinds, issub=issub,
            team=[sid(x) for x in d.team_id.tolist()],
            a1=[sid(x) for x in d.athlete_id_1.tolist()],
            a2=[sid(x) for x in d.athlete_id_2.tolist()],
            t=[elapsed(int(pn), clock_secs(c)) for pn, c in zip(d.period_number, d.clock_display_value)],
            hs=d.home_score.tolist(), **{'as': d.away_score.tolist()},
            scoring=d.scoring_play.fillna(False).tolist(), shoot=d.shooting_play.fillna(False).tolist())
        res = process_game(gid, ev, home, away)
        if res is None:
            dropped += 1
            continue
        for r in res:
            stint_rows.append((gid, glab.at[gid, 'game_date'], bool(glab.at[gid, 'neutral'])) + r)
print('pbp games processed', nproc, 'dropped', dropped, 'stints', len(stint_rows), time.time() - t0, flush=True)

st = pd.DataFrame(stint_rows, columns=['game_id', 'game_date', 'neutral', 't0', 't1', 'hp', 'ap', 'dh', 'da', 'ph', 'pa'])
st['poss'] = (st.ph + st.pa) / 2
st = st[(st.poss > 0.5) & (st.t1 > st.t0)].copy()
st['day'] = pd.to_datetime(st.game_date)
st = st.sort_values(['day', 'game_id']).reset_index(drop=True)
# note: columns hp/ap hold home/away on-court frozensets, dh/da points

players = sorted({p for s in st.hp for p in s} | {p for s in st.ap for p in s})
pidx = {p: i for i, p in enumerate(players)}
P = len(players)
S = len(st)
# observation rows: 2 per stint
rows, cols = [], []
y = np.empty(2 * S)
w0 = np.empty(2 * S)
day_of = np.empty(2 * S, dtype='int64')
hc = np.empty(2 * S)
daynum = (st.day - pd.Timestamp('1970-01-01')).dt.days.values
for k in range(S):
    hpl = [pidx[p] for p in st.hp[k]]
    apl = [pidx[p] for p in st.ap[k]]
    poss = st.poss[k]
    for side in (0, 1):  # 0 home offence
        r = 2 * k + side
        off, de = (hpl, apl) if side == 0 else (apl, hpl)
        y[r] = 100.0 * (st.dh[k] if side == 0 else st.da[k]) / poss
        w0[r] = poss
        day_of[r] = daynum[k]
        hc[r] = 0 if st.neutral[k] else (1 if side == 0 else -1)
        rows += [r] * (len(off) + len(de))
        cols += [2 + i for i in off] + [2 + P + i for i in de]
# columns: 0 intercept,1 hc, 2..2+P off, 2+P..2+2P def
D = 2 + 2 * P
data = np.ones(len(rows))
Xp = sp.csr_matrix((data, (rows, cols)), shape=(2 * S, D))
X = sp.hstack([sp.csr_matrix(np.ones((2 * S, 1))), sp.csr_matrix(hc.reshape(-1, 1)), Xp[:, 2:]]).tocsr()
pen = np.full(D, 3000.0)
pen[:2] = 1e-6

g_dates = pd.to_datetime(games.game_date)
last_day = g_dates.max()
first_ref = pd.Timestamp('2021-12-01')
refits = []
R = first_ref
while R <= last_day:
    refits.append(R)
    R = R + pd.Timedelta(days=7)
ratings_by_refit = []
for R in refits:
    rd = (R - pd.Timestamp('1970-01-01')).days
    mask = day_of <= rd - 1
    if mask.sum() == 0:
        ratings_by_refit.append(np.zeros(P))
        continue
    w = w0[mask] * 0.5 ** ((rd - 1 - day_of[mask]) / 730.0)
    Xm = X[mask]
    XtW = Xm.T.multiply(w).tocsr()
    A = (XtW @ Xm).toarray() + np.diag(pen)
    b = XtW @ y[mask]
    c = cho_solve(cho_factor(A), b)
    ratings_by_refit.append(c[2:2 + P] - c[2 + P:])
print('refits', len(refits), time.time() - t0, flush=True)
refit_days = np.array([(r - pd.Timestamp('1970-01-01')).days for r in refits])

# ---------------------------------------------------------------- candidates
inj = pd.read_parquet('data/cache/injury_reports.parquet',
                      columns=['game_id', 'team_id', 'athlete_id', 'status', 'reason', 'not_yet_submitted', 'available_at'])
inj = inj[inj.game_id.notna() & inj.athlete_id.notna()].copy()
inj['game_id'] = inj.game_id.map(sid)
inj['team_id'] = inj.team_id.map(sid)
inj['athlete_id'] = inj.athlete_id.map(sid)
inj = inj[inj.game_id.isin(labelled)]
inj_map = {}
for r in inj.itertuples(index=False):
    inj_map.setdefault((r.game_id, r.team_id), {})[r.athlete_id] = (r.status, bool(r.not_yet_submitted), r.reason)


def reason_cat(r):
    if r is None or (isinstance(r, float) and math.isnan(r)):
        return 'other'
    r = str(r).lower()
    for sub, c in [('g league', 'gleague'), ('two-way', 'gleague'), ('assignment', 'gleague'), ('rest', 'rest'),
                   ('management', 'rest'), ('personal', 'personal'), ('suspension', 'suspension'),
                   ('health and safety', 'health_safety'), ('not with team', 'not_with_team'),
                   ('injury', 'injury'), ('illness', 'injury'), ('soreness', 'injury')]:
        if sub in r:
            return c
    return 'other'


played_box = {}
for (g, t), d in box[box.played].groupby(['game_id', 'team_id']):
    played_box[(g, t)] = dict(zip(d.athlete_id, d.minutes.astype(float)))

order = games[games.season >= 2021].sort_values(['game_date', 'tipoff_utc', 'game_id'])
hist = {}
cand = []  # dict rows
for g in order.itertuples(index=False):
    for tm, side in ((g.home_id, 'h'), (g.away_id, 'a')):
        prev = hist.get(tm, [])
        last10 = prev[-10:]
        n = len(last10)
        ij = inj_map.get((g.game_id, tm), {})
        pl = {}
        for m in last10:
            for a in m: pl[a] = 1
        cset = set(pl) | set(ij)
        own = played_box.get((g.game_id, tm), {})
        for a in cset:
            gp = sum(1 for m in last10 if a in m)
            num = den = 0.0
            for i, m in enumerate(last10):
                if a in m:
                    wt = 0.8 ** (n - 1 - i)
                    num += wt * m[a]
                    den += wt
            avg = num / den if den > 0 else np.nan
            streak = 0
            for m in reversed(last10):
                if a in m: break
                streak += 1
            if a in ij:
                s, nys, rs = ij[a]
                status = 'NotYetSubmitted' if nys else s
                rc = reason_cat(rs)
            else:
                status, rc = 'NotListed', 'other'
            cand.append((g.game_id, g.season, tm, side, a, status, rc, gp, avg, streak, 1 if a in own else 0))
        hist.setdefault(tm, []).append({a: mn for a, mn in played_box.get((g.game_id, tm), {}).items()})
C = pd.DataFrame(cand, columns=['game_id', 'season', 'team', 'side', 'athlete', 'status', 'reason', 'gp', 'avg', 'streak', 'played'])
print('candidates', len(C), time.time() - t0, flush=True)

STAT = ['Out', 'Doubtful', 'Questionable', 'Probable', 'Available', 'NotYetSubmitted']
REAS = ['injury', 'rest', 'gleague', 'personal', 'suspension', 'health_safety', 'not_with_team', 'other']


def design(d):
    cols = [(d.status == s).astype(float).values for s in STAT]
    cols += [(d.reason == r).astype(float).values for r in REAS]
    inj_ = (d.reason == 'injury').values
    cols.append(((d.status == 'Out').values & inj_).astype(float))
    cols.append((d.status.isin(['Questionable', 'Doubtful']).values & inj_).astype(float))
    cols.append(d.gp.values / 10.0)
    avg = d.avg.fillna(12.0).clip(0, 40).values / 40.0
    cols.append(avg)
    cols.append(np.minimum(d.streak.values, 10) / 10.0)
    return np.column_stack(cols)


C = C[C.season >= 2022]  # candidate rows are only needed from 2022 on (games from 2022 on)
C = C.merge(games[['game_id', 'game_date']], on='game_id')
Xall = design(C)
C['p'] = np.nan
for T in range(2023, 2027):
    tr = (C.season >= 2022) & (C.season <= T - 1)
    if tr.sum() <= 500:
        continue
    m = LogisticRegression(C=1.0, penalty='l2', max_iter=2000).fit(Xall[tr.values], C.played[tr].values)
    te = (C.season == T).values
    C.loc[te, 'p'] = m.predict_proba(Xall[te])[:, 1]
print('model done', time.time() - t0, flush=True)

# ---------------------------------------------------------------- team values
gdate_num = {gid: (pd.Timestamp(d) - pd.Timestamp('1970-01-01')).days for gid, d in zip(games.game_id, games.game_date)}
res = []
Cf = C[C.season >= 2023].dropna(subset=['p'])
for (gid, side), d in Cf.groupby(['game_id', 'side']):
    day = gdate_num[gid]
    k = np.searchsorted(refit_days, day, side='right') - 1
    rt = ratings_by_refit[k] if k >= 0 else None
    rating = np.array([rt[pidx[a]] if (rt is not None and a in pidx) else 0.0 for a in d.athlete]) if rt is not None else np.zeros(len(d))
    avg = d['avg'].fillna(12.0).values
    mn = np.clip(avg, 4, 38)
    usual = ((d.gp >= 5) & (d['avg'] >= 10)).values
    p = d.p.values
    def val(pp):
        m = pp * mn
        s = m.sum()
        if s <= 0: return np.nan
        m = m * 240.0 / s
        return float(np.sum(m / 48.0 * rating))
    ev_ = val(p)
    fv = val(np.where(usual, 1.0, p))
    miss = float(np.sum((1 - p[usual]) * mn[usual]))
    res.append((gid, side, ev_, fv, miss))
R_ = pd.DataFrame(res, columns=['game_id', 'side', 'ev', 'fv', 'miss'])
h = R_[R_.side == 'h'].set_index('game_id')
a = R_[R_.side == 'a'].set_index('game_id')
j = h.join(a, lsuffix='_h', rsuffix='_a', how='inner').dropna()
out = pd.DataFrame({
    'game_id': j.index,
    'avail_value_diff': (j.ev_h - j.ev_a).values,
    'full_value_diff': (j.fv_h - j.fv_a).values,
    'avail_effect_diff': ((j.ev_h - j.fv_h) - (j.ev_a - j.fv_a)).values,
    'missing_min_diff': (j.miss_a - j.miss_h).values,
}).reset_index(drop=True)
out = out[out.game_id.isin(labelled)]
out.to_parquet(f'{OUT}/second_features.parquet', index=False)
print('games', len(out), 'seconds', time.time() - t0)
print(out.describe())
