"""Live daily forecasts for 2026-27 with the frozen availability models.

Run after refreshing sources (nba_lab refresh, extra-data, injury_reports collect for the season, and the pbp_2027 download):
    python -m nba_xgb.avail_daily --date 2026-10-29
The forecast is refused when the first tipoff of the day minus 60 minutes has passed, unless --late is given (then it is labelled LATE and
must not be counted as a pregame forecast). Output files are written once, read-only, and listed with their SHA256 in live/MANIFEST.csv.
"""
import argparse
import hashlib
import json
import stat
import numpy as np
import pandas as pd
from nba_lab import sources
from . import availability, data, engine, pbp, rapm, avail_study as S, models

LIVE = S.OUT / 'live'
PBP_URL = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_pbp/play_by_play_{s}.parquet'


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def refresh_pbp(season):
    return sources.fetch(PBP_URL.format(s=season), f'pbp_{season}', 'parquet', ttl_hours=0)


def run(date: str, late=False, refresh=True, log=print):
    LIVE.mkdir(parents=True, exist_ok=True)
    data.CANON = LIVE / 'canonical'                       # never overwrite the frozen study tables
    if refresh:
        refresh_pbp(int(date[:4]) + int(date[5:7] >= '07'))
    data.build(write=True)
    games, boxes = data.load(verify=False)
    season = int(games.loc[games.game_date == date, 'season'].max())
    day_games = games[games.game_date == date]
    if day_games.empty:
        raise ValueError(f'no games on {date}')
    first_tip = pd.to_datetime(day_games.tipoff_utc, utc=True).min()
    cutoff = first_tip - pd.Timedelta(minutes=60)
    now = pd.Timestamp.now(tz='UTC')
    status = 'PREGAME' if now <= cutoff else 'LATE'
    if status == 'LATE' and not late:
        raise RuntimeError(f'cutoff {cutoff} already passed (now {now}); not a pregame forecast. Use --late for a labelled retrospective run.')
    frozen = json.loads((S.DOCS / 'NBA_AVAIL_FROZEN.json').read_text())
    old = json.loads((S.DOCS / 'NBA_XGB_FROZEN.json').read_text())
    # base team-strength features from the refreshed tables
    F = engine.build_features(games, boxes, old['engine_params'])
    F = F[F.game_date == date]
    # availability features
    g_all, pb, inj = availability.load_inputs()
    stints = pd.read_parquet(S.OUT / 'stints.parquet')
    stints = stints[stints.season < season]
    new_stints, why = pbp.build_season(season, g_all, pd.read_parquet(S.ROOT / 'data' / 'cache' / 'player_boxes.parquet'))
    stints = pd.concat([stints, new_stints], ignore_index=True)
    design = rapm.Design(stints[stints.season >= 2021], g_all)
    d = rapm.day_num(date)
    R = rapm.day_num('2021-12-01')
    while R + rapm.REFIT_DAYS <= d:
        R += rapm.REFIT_DAYS
    beta, _ = design.fit(R - 1, 3000, 730)
    P = design.P
    ratings = pd.DataFrame({'refit_day': R, 'athlete_id': design.players, 'net': beta[2:2 + P] - beta[2 + P:]})
    cands = availability.candidate_rows(g_all, pb, inj, labelled=False)
    A = availability.build_game_features(cands, g_all, ratings, log=lambda *a: None, seasons={season})
    keep = ['game_id', 'rapm_refit_day', 'full_value_diff', 'avail_effect_diff', 'missing_min_diff', 'avail_value_diff', 'oracle_value_diff']
    new = F.merge(A[keep], on='game_id', how='left')
    new['has_avail'] = new.full_value_diff.notna().astype(float)
    # report timing: every injury row used must predate the first tipoff
    used = inj[inj.game_id.isin(day_games.game_id)]
    latest_pub = pd.to_datetime(used.available_at, utc=True).max() if len(used) else pd.NaT
    # verification gates: a check that covers nothing must fail, not pass
    assert len(new) == len(day_games) > 0, f'features for {len(new)} of {len(day_games)} games'
    assert new.has_avail.sum() > 0, 'no game received availability features'
    assert len(used) > 0, 'no injury-report rows were found for this day'
    assert pd.isna(latest_pub) is False and latest_pub <= first_tip, 'an injury row was published after the first tipoff'
    # production models: trained on every labelled season before this one, frozen hyperparameters
    T = S.load_table()
    calP = S.oos(T, frozen, tuple(range(2022, season)))
    tr = S.train_rows(T, season)
    rows = []
    for k in S.KINDS:
        m = S.make_model(k, frozen).fit(tr)
        raw = m.predict(new)
        cal = models.Calibrator(frozen['calibration'][k]['method']).fit(calP[k].values, calP.home_win.values)
        rows.append(pd.DataFrame({'game_id': new.game_id.values, 'home': new.home.values, 'away': new.away.values, 'model': k,
                                  'p_home_raw': raw, 'p_home': cal.predict(raw)}))
    out = pd.concat(rows, ignore_index=True)
    assert len(out) == len(S.KINDS) * len(day_games) and out.p_home.between(0, 1).all() and out.p_home.notna().all(), 'incomplete forecast table'
    out['forecast_date'] = date
    out['status'] = status
    out['prediction_cutoff_utc'] = cutoff.isoformat()
    out['generated_utc'] = now.isoformat()
    out['latest_injury_publication_utc'] = str(latest_pub)
    out['data_through_game_date'] = games.loc[games.completed & games.verified, 'game_date'].max()
    out['games_with_availability_features'] = int(new.has_avail.sum())
    out['model_version'] = hashlib.sha256(json.dumps(frozen, sort_keys=True, default=str).encode()).hexdigest()[:16]
    out['train_seasons'] = f'{S.FIRST}-{season - 1}'
    path = LIVE / f'forecast_{date}.csv'
    if path.exists():
        raise FileExistsError(f'{path} already exists; live forecasts are immutable')
    out.to_csv(path, index=False)
    path.chmod(stat.S_IREAD)
    manifest = LIVE / 'MANIFEST.csv'
    line = f'{date},{path.name},{sha(path)},{now.isoformat()},{status}\n'
    if not manifest.exists():
        manifest.write_text('forecast_date,file,sha256,generated_utc,status\n', encoding='utf-8')
    with manifest.open('a', encoding='utf-8') as f:
        f.write(line)
    log(line.strip())
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--late', action='store_true')
    ap.add_argument('--no-refresh', action='store_true')
    a = ap.parse_args()
    o = run(a.date, a.late, not a.no_refresh)
    print(o[o.model == 'logit_avail'][['home', 'away', 'p_home']].to_string(index=False))
