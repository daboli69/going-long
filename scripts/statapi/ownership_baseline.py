"""First ownership benchmarks from the private archive (Phase F). Chronological: train on contests before 2025-01-01, test on 2025-01-01 and later.

Targets: Classic field ownership; Showdown Captain ownership (CPT rows) and FLEX ownership (FLEX rows), modelled separately. Models:
  provider  = the provider's archived projected ownership (a benchmark; possibly backfilled, so not proof of what was knowable before lock)
  salary    = gradient boosting on salary structure only (salary, salary rank and share inside the slate/position, position, slate size, field size)
  salary+proj = the above plus the provider's projected fantasy points/ceiling (not the provider's ownership)
Results are written next to the archive (private). Nothing here is published.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import HistGradientBoostingRegressor
except ImportError:  # pragma: no cover
    HistGradientBoostingRegressor = None


def features(df, with_proj):
    out = pd.DataFrame(index=df.index)
    out['salary'] = df.salary
    g = df.groupby(['contest_id', 'slot_group'])
    out['salary_rank'] = g.salary.rank(ascending=False, method='first')
    out['salary_share'] = df.salary / g.salary.transform('sum')
    out['pos_rank_in_slate'] = df.groupby(['contest_id', 'position']).salary.rank(ascending=False, method='first')
    out['n_pool'] = g.salary.transform('size')
    out['log_entries'] = np.log(df.entries)
    for p in ('QB', 'RB', 'WR', 'TE', 'DST', 'K'):
        out['pos_' + p] = (df.position == p).astype(float)
    if with_proj:
        out['proj_pts'] = df.proj_pts
        out['proj_ceiling'] = df.proj_ceiling
        out['value'] = df.proj_pts / df.salary * 1000
        out['proj_rank'] = df.groupby(['contest_id', 'slot_group']).proj_pts.rank(ascending=False, method='first')
    return out


def evaluate(df, target, provider_col, label):
    train, test = df[df.date < '2025-01-01'], df[df.date >= '2025-01-01']
    res = {'label': label, 'train_rows': int(len(train)), 'test_rows': int(len(test)), 'test_contests': int(test.contest_id.nunique())}
    tt = test.dropna(subset=[target])
    res['mean_actual'] = float(tt[target].mean())
    if provider_col in tt and tt[provider_col].notna().any():
        t = tt.dropna(subset=[provider_col])
        res['provider'] = {'n': int(len(t)), 'mae': float((t[target] - t[provider_col]).abs().mean()), 'corr': float(t[target].corr(t[provider_col])), 'bias': float((t[provider_col] - t[target]).mean())}
    for name, with_proj in (('salary', False), ('salary+proj', True)):
        if HistGradientBoostingRegressor is None:
            break
        tr = train.dropna(subset=[target] + (['proj_pts'] if with_proj else []))
        te = tt.dropna(subset=(['proj_pts'] if with_proj else []))
        if len(tr) < 500 or len(te) < 200:
            continue
        model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0).fit(features(tr, with_proj), tr[target])
        pred = np.clip(model.predict(features(te, with_proj)), 0, 100)
        res[name] = {'n': int(len(te)), 'mae': float((te[target] - pred).abs().mean()), 'corr': float(np.corrcoef(te[target], pred)[0, 1]), 'bias': float((pred - te[target]).mean())}
        if 'provider' in res:
            common = te.dropna(subset=[provider_col])
            res[name]['mae_on_provider_rows'] = float((common[target] - np.clip(model.predict(features(common, with_proj)), 0, 100)).abs().mean())
    return res


def main(root):
    df = pd.read_parquet(Path(root) / 'ownership_frame.parquet')
    df['slot_group'] = np.where(df.game_type == 'showdown', df.slot, 'ALL')
    out = {}
    cl = df[df.game_type == 'classic']
    out['classic_field'] = evaluate(cl, 'field_pct', 'proj_own_pct', 'Classic field ownership (%)')
    sd = df[df.game_type == 'showdown']
    out['showdown_cpt'] = evaluate(sd[sd.slot.isin(['CPT', 'MVP'])], 'cpt_field_pct', 'proj_cpt_own', 'Showdown Captain ownership (%)')
    out['showdown_flex'] = evaluate(sd[sd.slot.isin(['FLEX', 'UTIL'])], 'flex_field_pct', 'proj_flex_own', 'Showdown FLEX ownership (%)')
    (Path(root) / 'ownership_baseline_results.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    print(json.dumps(main(sys.argv[1]), indent=1))
