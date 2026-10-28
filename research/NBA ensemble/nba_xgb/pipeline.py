"""Frozen-model pipeline: train season bundles, one-pass test predictions, strict as-of replay, daily forecasts."""
from __future__ import annotations
import hashlib
import json
import stat
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from . import data, engine, models
from .develop import DOCS, OUT, DEV_FOLDS, engine_params, file_hash, oos_predictions

ART = OUT / 'artifacts'
MODEL_NAMES = ('elo_raw', 'elo_cal', 'logit', 'xgb')


def load_frozen():
    return json.loads((DOCS / 'NBA_XGB_FROZEN.json').read_text(encoding='utf-8'))


def model_version(frozen):
    return hashlib.sha256(json.dumps({k: frozen[k] for k in ('engine_params', 'features', 'xgb', 'logit_C', 'calibration')},
                                     sort_keys=True, default=float).encode()).hexdigest()[:16]


def check_frozen(frozen):
    if file_hash(DOCS / 'NBA_XGB_ENGINE_PARAMS.json') != frozen['engine_params_file_sha256']:
        raise RuntimeError('engine parameters changed after freezing')
    if file_hash(data.CANON / 'MANIFEST.json') != frozen['canonical_manifest_sha256']:
        raise RuntimeError('canonical data changed after freezing; refit under a new version instead of reusing this one')


def elo_raw(df, hca):
    return 1.0 / (1.0 + 10.0 ** (-(df.elo_diff.values + hca * df.home_court.values) / 400.0))


def fit_bundle(F, frozen, season):
    """Everything fitted from seasons < `season` only (labels for earlier seasons are public by then)."""
    feats = frozen['features']
    cfg, rounds = frozen['xgb']['params'], frozen['xgb']['rounds']
    tr = models.training_frame(F, season)
    bundle = {'season': season, 'features': feats, 'train_seasons': sorted(tr.season.unique().tolist()), 'n_train': len(tr),
              'elo_cal': models.Logit(models.ELO_FEATS).fit(tr), 'logit': models.Logit(feats, frozen['logit_C']).fit(tr),
              'xgb': models.XGB(feats, cfg, rounds).fit(tr), 'elo_hca': frozen['engine_params']['elo']['hca'],
              'version': model_version(frozen)}
    folds = tuple(range(DEV_FOLDS[0], season))
    P = oos_predictions(F, feats, cfg, rounds, frozen['logit_C'], folds)
    bundle['calibration_seasons'] = list(folds)
    bundle['cal'] = {m: models.Calibrator(frozen['calibration'][m]).fit(P[m].values, P.home_win.values) for m in ('elo_cal', 'logit', 'xgb')}
    return bundle


def predict_bundle(bundle, df):
    raw = {'elo_raw': elo_raw(df, bundle['elo_hca']), 'elo_cal': bundle['elo_cal'].predict(df),
           'logit': bundle['logit'].predict(df), 'xgb': bundle['xgb'].predict(df)}
    final = {m: (bundle['cal'][m].predict(raw[m]) if m in bundle['cal'] else raw[m]) for m in raw}
    return raw, final


def save_bundle(bundle):
    ART.mkdir(parents=True, exist_ok=True)
    p = ART / f'bundle_{bundle["season"]}.joblib'
    if p.exists():
        p.chmod(stat.S_IWRITE | stat.S_IREAD)
    joblib.dump(bundle, p)
    p.chmod(stat.S_IREAD)
    return p


def long_predictions(df, raw, final, bundle, source_sha):
    rows = []
    for m in MODEL_NAMES:
        rows.append(pd.DataFrame({'game_id': df.game_id.values, 'season': df.season.values, 'game_date': df.game_date.values,
                                  'prediction_cutoff_utc': df.prediction_cutoff_utc.astype(str).values, 'model': m,
                                  'p_home_raw': raw[m], 'p_home': final[m], 'model_version': bundle['version'],
                                  'train_seasons': f"{bundle['train_seasons'][0]}-{bundle['train_seasons'][-1]}",
                                  'source_data_sha': source_sha}))
    return pd.concat(rows, ignore_index=True)


def write_once(path: Path, frame: pd.DataFrame):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f'{path} already exists; frozen prediction files are immutable')
    frame.to_csv(path, index=False)
    path.chmod(stat.S_IREAD)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_final(F, seasons=(2025, 2026), log=print):
    """One pass over the final test seasons with the frozen configuration."""
    frozen = load_frozen()
    check_frozen(frozen)
    if file_hash(OUT / 'features_lag1.parquet') != frozen['feature_file_sha256']:
        raise RuntimeError('feature file differs from the frozen version')
    src = file_hash(data.CANON / 'MANIFEST.json')
    out = {}
    for T in seasons:
        bundle = fit_bundle(F, frozen, T)
        save_bundle(bundle)
        ev = models.eval_frame(F, T)
        raw, final = predict_bundle(bundle, ev)
        out[T] = long_predictions(ev, raw, final, bundle, src)
        log('fit', T, 'train', bundle['train_seasons'][0], '-', bundle['train_seasons'][-1], 'n', bundle['n_train'], 'games', len(ev))
    return pd.concat(out.values(), ignore_index=True)


# ------------------------------------------------------------------ strict as-of replay
def as_of_tables(games, boxes, day):
    """Canonical tables as they stood on game date `day`: no result dated on or after `day` is visible."""
    g = games.copy()
    hide = (g.game_date >= day)
    g.loc[hide, ['completed', 'verified']] = False
    g.loc[hide, ['home_score', 'away_score', 'home_win']] = np.nan
    hidden_ids = set(g.loc[hide, 'game_id'])
    return g, boxes[~boxes.game_id.isin(hidden_ids)]


FEATURE_COLS = ['elo_diff', 'adj_off_diff', 'adj_def_diff', 'recent_net_diff', 'rest_diff', 'b2b_home', 'b2b_away', 'home_court']


def replay(games, boxes, frozen, season, dates=None, log=print):
    """Predict each game date from only the information visible before that date, using the frozen bundle."""
    bundle = joblib.load(ART / f'bundle_{season}.joblib')
    params = frozen['engine_params']
    dates = dates or sorted(games.loc[(games.season == season) & games.completed & games.verified, 'game_date'].unique())
    parts, feat_parts = [], []
    for i, d in enumerate(dates):
        g, b = as_of_tables(games, boxes, d)
        # shrink to the target season and earlier so each replay day stays cheap; later seasons cannot matter
        g = g[g.season <= season]
        b = b[b.game_id.isin(g.game_id)]
        Fd = engine.build_features(g, b, params)
        day_games = Fd[(Fd.game_date == d) & (Fd.season == season)].copy()
        day_games = day_games[day_games.game_id.isin(games.loc[games.completed & games.verified, 'game_id'])]
        raw, final = predict_bundle(bundle, day_games)
        parts.append(long_predictions(day_games, raw, final, bundle, file_hash(data.CANON / 'MANIFEST.json')))
        feat_parts.append(day_games[['game_id', 'game_date', 'prediction_cutoff_utc', *engine_cols()]])
        if i % 20 == 0:
            log('replay', season, d, f'{i + 1}/{len(dates)}')
    return pd.concat(parts, ignore_index=True), pd.concat(feat_parts, ignore_index=True)


def engine_cols():
    return [c for c in FEATURE_COLS if c != 'home_court'] + ['home_court', 'gp_min', 'recent_off_diff', 'recent_def_diff',
                                                           'adj_net_diff', 'ff_efg_diff', 'ff_tov_diff', 'ff_orb_diff', 'ff_ftr_diff']


# ------------------------------------------------------------------ daily forecast
def daily(date: str, out_dir: Path | None = None, season: int | None = None, log=print):
    """Forecast every unfinished game on `date` (YYYY-MM-DD, ET) with the latest frozen bundle. Refuses to overwrite."""
    games, boxes = data.load(verify=False)
    frozen = load_frozen()
    season = season or int(games.loc[games.game_date == date, 'season'].max())
    path = ART / f'bundle_{season}.joblib'
    if not path.exists():
        F = pd.read_parquet(OUT / 'features_lag1.parquet')
        save_bundle(fit_bundle(F, frozen, season))
    bundle = joblib.load(path)
    g, b = as_of_tables(games, boxes, date)
    Fd = engine.build_features(g, b, frozen['engine_params'])
    day = Fd[Fd.game_date == date].copy()
    if day.empty:
        raise ValueError(f'no scheduled games on {date}')
    now = pd.Timestamp.now(tz='UTC')
    if (pd.to_datetime(day.tipoff_utc, utc=True) <= now).all() and date >= now.tz_convert('America/New_York').strftime('%Y-%m-%d'):
        log('warning: every game on this date has already started; this is a retrospective forecast, not a live one')
    raw, final = predict_bundle(bundle, day)
    pred = long_predictions(day, raw, final, bundle, file_hash(data.CANON / 'MANIFEST.json'))
    pred['generated_utc'] = now.isoformat()
    target = (out_dir or OUT / 'daily') / f'forecast_{date}.csv'
    target.parent.mkdir(parents=True, exist_ok=True)
    write_once(target, pred)
    feats = day[['game_id', 'home', 'away', 'prediction_cutoff_utc', *engine_cols()]]
    feats.to_csv(target.with_name(f'features_{date}.csv'), index=False)
    return pred
