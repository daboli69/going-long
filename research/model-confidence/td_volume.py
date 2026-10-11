"""Research-only current-season opportunity ATD challenger. Offline public caches only.
No 2026 input/outcome files, private files, production writes or model promotion.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.trend_research import champion
import build_pipeline

POSITIONS = {'RB', 'WR', 'TE'}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()

def finite_count(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

def opportunity_probability(carries, targets, rates):
    if not all(finite_count(v) for v in [carries, targets, *rates.values()]) or set(rates) != {'carry', 'target'}:
        raise ValueError('Complete nonnegative carry/target opportunity and rates required')
    if any(v > 1 for v in rates.values()):
        raise ValueError('Conversion rates must be probabilities')
    lam = carries * rates['carry'] + targets * rates['target']
    return -math.expm1(-lam)

def prior_role(rows, season, week, team, minimum=3):
    # Mean opportunity is genuinely current-season/current-team, never past outcomes.
    current = [r for r in rows if r['season'] == season and r['week'] < week]
    last_other = max((r['week'] for r in current if r['team'] != team), default=-1)
    selected = [r for r in current if r['team'] == team and r['week'] > last_other]
    if len(selected) < minimum:
        return None
    if len({(r['season'], r['week']) for r in selected}) != len(selected):
        raise ValueError('Duplicate appearance receipt')
    if not all(finite_count(r.get(k)) for r in selected for k in ['carries', 'targets']):
        return None
    return {k: sum(r[k] for r in selected)/len(selected) for k in ['carries', 'targets']} | {'n': len(selected)}

def fitted_rates(frame, development):
    d = frame[frame.season.isin(development)]
    rates = {}
    for exposure, outcome, key in [('carries', 'rushing_tds', 'carry'), ('targets', 'receiving_tds', 'target')]:
        x, y = d[exposure].to_numpy(float), d[outcome].to_numpy(float)
        if np.any(~np.isfinite(x)) or np.any(~np.isfinite(y)) or np.any(x < 0) or np.any(y < 0) or x.sum() <= 0:
            raise ValueError('Incomplete development opportunity/outcome data')
        rates[key] = float(y.sum()/x.sum())
    return rates

def clustered_interval(frame, first, other, cluster, metric, rng, replications):
    y = frame.y.to_numpy(float)
    def loss(name):
        p = frame[name].to_numpy(float)
        if metric == 'brier':
            return (p-y)**2
        q = np.clip(p, 1e-6, 1-1e-6)
        return -y*np.log(q)-(1-y)*np.log1p(-q)
    delta = loss(first)-loss(other)
    ids, _ = pd.factorize(frame[cluster])
    sums, ns = np.bincount(ids, weights=delta), np.bincount(ids)
    draws = rng.integers(0, len(ns), size=(replications, len(ns)))
    boot = sums[draws].sum(axis=1)/ns[draws].sum(axis=1)
    return {'delta':float(delta.mean()), 'lower':float(np.quantile(boot,.025)), 'upper':float(np.quantile(boot,.975)), 'clusters':len(ns)}

def metrics(y, p):
    q = np.clip(p,1e-6,1-1e-6)
    z = np.log(q/(1-q))
    def objective(b):
        v = b[0]+b[1]*z
        return float(np.mean(np.logaddexp(0,v)-y*v))
    cal = minimize(objective,[0.,1.],method='BFGS')
    return {'brier':float(np.mean((p-y)**2)), 'log_loss':float(np.mean(-y*np.log(q)-(1-y)*np.log1p(-q))), 'mean_probability':float(p.mean()),
            'calibration':{'intercept':float(cal.x[0]),'slope':float(cal.x[1]),'optimizer_success':bool(cal.success),'diagnostic_only_never_applied':True},
            'reliability':[{'lower':lo,'upper':hi,'n':int(((p>=lo)&(p<hi)).sum()),'mean_probability':float(p[(p>=lo)&(p<hi)].mean()) if ((p>=lo)&(p<hi)).any() else None,'observed_rate':float(y[(p>=lo)&(p<hi)].mean()) if ((p>=lo)&(p<hi)).any() else None} for lo,hi in [(0,.1),(.1,.2),(.2,.4),(.4,.6),(.6,1.000001)]]}

def report(frame, protocol):
    if frame.empty:
        return {'rows':0,'status':'insufficient'}
    y = frame.y.to_numpy(float)
    out = {'rows':len(frame),'games':int(frame.game_id.nunique()),'players':int(frame.player_id.nunique()),'observed_rate':float(y.mean()),
           'models':{k:metrics(y,frame[k].to_numpy(float)) for k in ['opportunity','champion_reconstructed','current_frequency']},'paired':{}}
    rng = np.random.default_rng(protocol['bootstrap']['seed'])
    for other in ['champion_reconstructed','current_frequency']:
        out['paired'][other] = {cluster:{metric:clustered_interval(frame,'opportunity',other,cluster,metric,rng,protocol['bootstrap']['replications']) for metric in ['brier','log_loss']} for cluster in ['game_id','player_id']}
    out['positions'] = {p:{'rows':len(g),'brier':{k:float(np.mean((g[k]-g.y)**2)) for k in ['opportunity','champion_reconstructed','current_frequency']}} for p,g in frame.groupby('position')}
    return out

def run(cache, protocol_path):
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    for name, frozen in protocol['sources_sha256'].items():
        if digest(ROOT/name) != frozen:
            raise ValueError('Preregistered source changed: '+name)
    if protocol['splits']['test'] != [2025] or protocol['splits']['development'] != [2021,2022,2023]:
        raise ValueError('Split changes require a new preregistered protocol')
    files = [cache/f'{prefix}_{s}.csv' for prefix in ['stats_player_week','snap_counts'] for s in range(2019,2026)] + [cache/'players.csv']
    if not all(p.exists() for p in files):
        raise ValueError('Public weekly/snap/identity cache incomplete; this runner never downloads')
    snap_game = snap_games(cache)
    for season in range(2019,2026):
        raw = pd.read_csv(cache/f'stats_player_week_{season}.csv')
        raw = raw[(raw.season_type=='REG') & raw.position.isin(POSITIONS)]
        if raw.duplicated(['player_id','season','week']).any():
            raise ValueError('Ambiguous raw weekly appearances')
        values = raw[['carries','targets','rushing_tds','receiving_tds','special_teams_tds','def_tds','fumble_recovery_tds']].to_numpy(float)
        if np.any(~np.isfinite(values)) or np.any(values<0) or np.any(values!=np.floor(values)):
            raise ValueError('Incomplete or malformed offensive/TD source observations')
    # Reuse existing public appearance reconstruction, replacing its downloader
    # with an offline-only existence check. Missing stat rows need positive snaps.
    old_cache, old_download = champion.cache, champion._download
    champion.cache = lambda _: cache
    def offline(_, destination):
        if not destination.exists():
            raise ValueError('Offline public file missing: '+str(destination))
        return destination
    champion._download = offline
    try:
        apps = champion.appearances(ROOT,range(2019,2026))
    finally:
        champion.cache, champion._download = old_cache, old_download
    apps = apps[apps.position.isin(POSITIONS)].copy()
    if apps.duplicated(['player_id','season','week']).any():
        raise ValueError('Duplicate player-week appearances')
    # Champion supplied extra snap-zero records omit component TD columns.
    # Verified missing stat row is a zero offensive-scoring appearance.
    for col in ['rushing_tds','receiving_tds']:
        apps[col] = apps[col].fillna(0)
    rates = fitted_rates(apps,protocol['splits']['development'])
    rows, rejected = [], Counter()
    for pid, group in apps.groupby('player_id',sort=False):
        previous = []
        for r in group.sort_values(['season','week']).to_dict('records'):
            season, week = int(r['season']), int(r['week'])
            if season in [2024,2025]:
                role = prior_role(previous,season,week,r['team'],protocol['minimum_current_appearances'])
                window = previous[-12:]
                fit = build_pipeline.season_fit(window,'touchdowns','poisson',season,market='atd',position=r['position'])
                if role is None:
                    rejected['insufficient_current_team_role'] += 1
                elif fit.get('status') != 'ready':
                    rejected['champion_incomplete'] += 1
                elif not finite_count(r['touchdowns']):
                    rejected['missing_outcome'] += 1
                else:
                    last_other = max((v['week'] for v in previous if v['season']==season and v['team']!=r['team']), default=-1)
                    own = [v for v in previous if v['season']==season and v['team']==r['team'] and v['week']>last_other]
                    gid = r.get('game_id')
                    if not isinstance(gid,str) or not gid.startswith(str(season)+'_'):
                        # stats-free snap appearance has a game receipt in snaps
                        gid = snap_game.get((pid,season,week))
                    if not gid:
                        rejected['unmapped_game_identity'] += 1
                        previous.append(r)
                        continue
                    rows.append({'season':season,'week':week,'game_id':gid,'player_id':pid,'position':r['position'],'y':int(r['touchdowns']>0),
                                 'opportunity':opportunity_probability(role['carries'],role['targets'],rates),'champion_reconstructed':-math.expm1(-fit['lambda']),
                                 'current_frequency':(sum(v['touchdowns']>0 for v in own)+1)/(len(own)+2),'prior_current_games':role['n']})
            previous.append(r)
    frame = pd.DataFrame(rows)
    reports = {str(season):report(frame[frame.season==season],protocol) for season in [2024,2025]}
    accepted = all(v['rows']>0 and v['models']['champion_reconstructed']['brier']-v['models']['opportunity']['brier']>=.002 and v['models']['opportunity']['log_loss']<=v['models']['champion_reconstructed']['log_loss'] and all(v['paired']['champion_reconstructed'][cluster]['brier']['upper']<0 for cluster in ['game_id','player_id']) for v in reports.values())
    return {'schema':'td-opportunity-volume-research-v1','status':'reused_retrospective_diagnostic_no_promotion','research_gate':'prospective_candidate' if accepted else 'rejected','promotion_eligible':False,'protocol_sha256':digest(protocol_path),'sources':{p.name:digest(p) for p in files},'fitted_conversion_rates':rates,'attrition':dict(rejected),'feature_missingness':{'goal_line_detail':'absent in weeklystats;no fabricated proxy','red_zone_detail':'absent in weeklystats;no fabricated proxy','opportunity_counts':'eligible rows complete; confirmed snap-zero stat absence handled by existing Champion appearance loader'},
            'reports':reports,'market_comparison':{'status':'blocked','reason':'No matched historical sportsbook ATD quotes for2019–2025 supplied; do not substitute synthetic prices'},
            'limitations':['Conditioned on retrospectively confirmed appearances; no historical pregame availability/execution validation.','Historical source receipts are retrospectively loaded public releases, not immutable contemporaneous feed receipts.','2024/2025 already used in prior model research; not an untouched holdout.','Champion reconstructed with current fixed policy on public stats/snap appearance windows, not archived exact historical forecasts.','Zero-touch appearances require positive offensive snap receipts; unmapped PFR identities omitted by inherited appearance builder.','Offensive team/opponent TD forecasts and exact red-zone detail not in this simpler volume challenger.','No2026 outcomes accessed; no betting profit or production accuracy claim.']}

# Missing weekly-stat appearance game identity is recovered from verified snaps.
def snap_games(cache):
    players = pd.read_csv(cache/'players.csv',usecols=['gsis_id','pfr_id']).dropna()
    mapping = dict(zip(players.pfr_id,players.gsis_id))
    out = {}
    for s in range(2019,2026):
        f = pd.read_csv(cache/f'snap_counts_{s}.csv')
        for r in f[(f.game_type=='REG')&(f.offense_snaps>0)].itertuples():
            pid=mapping.get(r.pfr_player_id)
            if pid:
                key=(pid,s,int(r.week))
                if key in out and out[key]!=r.game_id:
                    raise ValueError('Conflicting player-week game identities')
                out[key]=r.game_id
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache/model-confidence-public')
    parser.add_argument('--protocol',type=Path,default=Path(__file__).with_name('td_volume_protocol.json'))
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('td_volume_results.json'))
    args=parser.parse_args();result=run(args.cache,args.protocol)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'rates':result['fitted_conversion_rates'],'reports':{s:{'rows':v['rows'],'models':{k:{m:x[m] for m in ['brier','log_loss']} for k,x in v['models'].items()}} for s,v in result['reports'].items()}},indent=2))
