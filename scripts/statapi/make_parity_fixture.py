"""Writes tests/fixtures/dfs-field-parity.json: a SYNTHETIC (non-licensed) Showdown pool, lineups and toy model, with the expected ownership/features/duplication computed by the
Python training code (showdown_models.py). tests/dfs-field.test.cjs then requires shared/dfs-field.js to reproduce every number. Regenerate: python scripts/statapi/make_parity_fixture.py"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from statapi import showdown_models as sm  # noqa: E402

rng = np.random.default_rng(2024)
POS = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'WR', 'TE', 'TE', 'K', 'DST']
rows = []
for team in ('AAA', 'BBB'):
    for i, pos in enumerate(POS):
        base = int(np.clip(11800 - i * 900 - (400 if team == 'BBB' else 0), 200, None) // 200 * 200)
        if i in (4, 5):
            base = 6000  # deliberate salary ties across both teams
        rows.append((f'{team}{i}', team, pos, base))
cid = 1
pool = []
for key, team, pos, base in rows:
    for slot, mult in (('CPT', 1.5), ('FLEX', 1.0)):
        pool.append(dict(contest_id=cid, slot=slot, player_key=key, position=pos, team=team, salary=base * mult, entries=30000))
pool = pd.DataFrame(pool)
pool = sm.pool_features(pool)
bins = sm.BINS
ramp = [float(max(.2, 30 * np.exp(-i / 5))) for i in range(bins)]
tables = {r: {'QB': ramp, 'SKILL': [x * .9 for x in ramp], 'DK': [x / 3 for x in ramp]} for r in ('CPT', 'FLEX')}
pool['own_pred'] = np.nan
for role in ('CPT', 'FLEX'):
    m = sm.TableOwnership(role)
    m.table = tables[role]
    idx = pool.role == role
    pool.loc[idx, 'own_pred'] = m.predict(pool[idx])
cpt_keys = [k for k, *_ in rows]
lineups = []
while len(lineups) < 40:
    c = cpt_keys[rng.integers(len(cpt_keys))]
    f = list(rng.choice([k for k in cpt_keys if k != c], 5, replace=False))
    lineups.append([c] + f)
tmp = Path(tempfile.mkdtemp())
(tmp / 'normalized' / f'contest_{cid}').mkdir(parents=True)
pd.DataFrame(lineups, columns=[f'seat{i}' for i in range(6)]).to_parquet(tmp / 'normalized' / f'contest_{cid}' / 'lineups.parquet')
pool['date'] = '2025-02-01'
feat = sm.lineup_rows(tmp, pool, per_contest=4000)
order = np.random.default_rng(7).choice(len(lineups), size=len(lineups), replace=False)
sub = [lineups[i] for i in order]
assert len(feat) == len(sub)
F = sm.DUP_FEATURES
spec = {'features': F, 'mean': [5, 40, 2, -18, 800, .3, 4, 1.5, .2, 10], 'sd': [5, 20, 2, 4, 900, .25, 1, 1, .4, 1], 'intercept': 1.4, 'coef': [.3, .2, .1, .15, -.1, -.1, .05, .1, .05, .2], 'resid_sd': 1.1,
        'decile_edges': [4, 6, 8, 10, 13, 17, 22, 30, 45], 'decile_median_copies': [1, 2, 3, 4, 5, 6, 8, 10, 14, 25], 'decile_unique_share': [.6, .5, .4, .3, .2, .15, .1, .07, .04, .02]}
dm = sm.DupModel()
dm.mu, dm.sd, dm.b0, dm.w, dm.resid_sd = np.array(spec['mean']), np.array(spec['sd']), spec['intercept'], np.array(spec['coef']), spec['resid_sd']
X = feat[F].to_numpy(float).copy()
X[:, F.index('log_entries')] = np.log(11000)  # entries 40 would be clamped to the trained minimum by the JS
logd = dm.predict_log(X)
cop = np.exp(logd + .5 * spec['resid_sd'] ** 2)
decile = [1 + int(sum(e < c for e in spec['decile_edges'])) for c in cop]
out = {'schema': 'going-private-showdown-models-v2', 'model': {'schema': 'going-private-showdown-models-v2',
       'ownership': {r: {'kind': 'rank_table', 'bins': bins, 'table': tables[r], 'total': sm.TOTAL[r]} for r in tables}, 'duplication': spec},
       'players': [dict(id=r.player_key, role=r.role, position=r.position, team=r.team, salary=float(r.salary)) for r in pool.itertuples()],
       'expectedOwnership': [dict(id=r.player_key, role=r.role, ownership=float(r.own_pred), rank=int(r.salary_rank), rankPct=float(r.rank_pct)) for r in pool.itertuples()],
       'lineups': sub, 'entries': 40, 'expectedFeatures': {c: feat[c].tolist() for c in F}, 'expectedLogDup': logd.tolist(), 'expectedCopies': cop.tolist(), 'expectedDecile': decile}
dest = Path(__file__).resolve().parent.parent.parent / 'tests' / 'fixtures' / 'dfs-field-parity.json'
dest.write_text(json.dumps(out), encoding='utf-8')
print('wrote', dest, 'deciles', sorted(set(decile)))
