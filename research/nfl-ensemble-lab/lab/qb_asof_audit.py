"""Offline fixed-time QB evidence audit. No fit, fetch, model load or original writes.

Run: .venv/Scripts/python.exe -m lab.qb_asof_audit
Specification: docs/QB_ASOF_PREREGISTRATION.md. Outputs are unique evidence packets.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v20261016_212540"
TEAM = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX", "LVR": "LV"}


@lru_cache(maxsize=200000)
def timestamp(value):
    t = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(t) else t


def implied(odds):
    try:
        v = float(odds)
        if not np.isfinite(v) or abs(v) < 100:
            return None
        return -v / (100 - v) if v < 0 else 100 / (100 + v)
    except (ValueError, TypeError):
        return None


def novig(home, away):
    h, a = implied(home), implied(away)
    return h / (h + a) if h is not None and a is not None else None


def select_snapshot(records, decision):
    eligible = [r for r in records if r.get("model_version") == VERSION
                and timestamp(r.get("predicted_at")) is not None
                and timestamp(r["predicted_at"]) <= decision]
    return max(eligible, key=lambda r: (timestamp(r["predicted_at"]), r["path"])) if eligible else None


def select_quote(quotes, home, away, kickoff, decision, max_age=60):
    eligible = []
    for q in quotes:
        at = timestamp(q.get("observed_at"))
        kt = timestamp(q.get("kickoff"))
        pub = timestamp(q.get("quote_time"))
        if q["home"] != home or q["away"] != away or kt != kickoff:
            continue
        if at is None or at > decision or q.get("p_home") is None or q.get("in_play"):
            continue
        if pub is not None and pub > at:
            continue
        age = (decision - at).total_seconds() / 60
        if max_age is not None and (age > max_age or (pub is not None and (decision-pub).total_seconds()/60 > max_age)):
            continue
        eligible.append(q)
    return max(eligible, key=lambda q: (timestamp(q["observed_at"]), q["path"])) if eligible else None


def losses(y, p):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-6, 1-1e-6)
    return -(y*np.log(p)+(1-y)*np.log1p(-p))


def compare(rows):
    """One paired unit per game, never repeated forecasts as independent observations."""
    if not rows:
        return {"n": 0, "status": "no common scored games"}
    if len({r['game_id'] for r in rows}) != len(rows):
        raise ValueError("duplicate games")
    y = np.array([r['home_win'] for r in rows], float)
    c = np.array([r['p_champion'] for r in rows], float)
    m = np.array([r['p_market'] for r in rows], float)
    if not np.isin(y,[0,1]).all():
        raise ValueError("binary completed outcomes required")
    delta = losses(y,c)-losses(y,m)
    rng = np.random.default_rng(20261026)
    boot = delta[rng.integers(0,len(rows),size=(2000,len(rows)))].mean(axis=1)
    out = {"n":len(rows),"champion_minus_market_log_loss":float(delta.mean()),
           "paired_game_ci95":np.quantile(boot,[.025,.975]).tolist(),"descriptive_only":True}
    for name,p in [('champion',c),('market',m)]:
        bins=[]
        for lo,hi in zip(np.arange(0,1,.2),np.arange(.2,1.01,.2)):
            mask=(p>=lo)&((p<hi) if hi<.999 else (p<=1))
            bins.append({'low':float(lo),'high':float(hi),'n':int(mask.sum()),
                         'mean_probability':float(p[mask].mean()) if mask.any() else None,
                         'observed_rate':float(y[mask].mean()) if mask.any() else None})
        out[name]={'log_loss':float(losses(y,p).mean()),'brier':float(np.mean((p-y)**2)),
                   'accuracy':float(np.mean((p>.5)==y)), 'mean_probability_minus_outcome':float(np.mean(p-y)),
                   'reliability':bins}
    weeks=sorted({r['week'] for r in rows})
    out['week_block_sensitivity']='not estimated: fewer than 10 weeks' if len(weeks)<10 else 'available'
    if len(weeks)>=10:
        groups=[np.array([i for i,r in enumerate(rows) if r['week']==w]) for w in weeks]
        draws=[delta[np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))])].mean() for _ in range(2000)]
        out['week_block_ci95']=np.quantile(draws,[.025,.975]).tolist()
    return out


def power(n):
    factor=1.959964+0.841621
    return [{'assumed_paired_sd':sd,'required_n_for_0_010':math.ceil((factor*sd/.01)**2),
             'detectable_delta_at_n':factor*sd/math.sqrt(n) if n else None} for sd in [.1,.2,.4]]


def qb_evidence(team, champion_id, week, decision, source_tables):
    """Audit structured observations; injury clearance/depth order do not confirm a starter."""
    eligible=[s for s in source_tables if timestamp(s['observed_at'])<=decision]
    latest={}
    for s in eligible:
        if s['kind'] not in latest or s['observed_at']>latest[s['kind']]['observed_at']:
            latest[s['kind']]=s
    reports=[]; projections=[]
    for s in latest.values():
        for r in s['qb_rows']:
            if TEAM.get(r.get('team'),r.get('team'))!=team: continue
            if r.get('week') is not None and r['week']!=week: continue
            if s['kind']=='sleeper_players':
                if r.get('depth_chart_order')==1:
                    projections.append({'gsis_id':r.get('gsis_id'),'status':r.get('status'),'injury_status':r.get('injury_status'),
                                        'path':s['path'],'observed_at':s['observed_at'],'news_updated':r.get('news_updated'),
                                        'confirmed_starter':False})
            elif champion_id and r.get('gsis_id')==champion_id:
                reports.append({'report_status':r.get('report_status'),'path':s['path'],
                                'observed_at':s['observed_at'],'published_at':None})
    statuses={r['report_status'] for r in reports if r['report_status']}
    return {'champion_qb_id':champion_id,'champion_identity_recorded':bool(champion_id),
            'matched_injury_reports':reports,'report_status_conflict':len(statuses)>1,
            'projected_depth_one':projections,'confirmed_starter_evidence':None,
            'limitation':'Structured reports record injury status and depth projections, not affirmative starting confirmation. Narrative reports require independently verified extraction; not established here.'}


def audit(root=ROOT):
    root=Path(root)
    started=pd.Timestamp.now(tz='UTC')
    out=root/'artifacts'/'qb_asof_audit'/started.strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True,exist_ok=False)
    manifest={}; failures=[]

    def read(path):
        path=Path(path); b=path.read_bytes(); key=path.relative_to(root).as_posix()
        digest=hashlib.sha256(b).hexdigest()
        if key in manifest and manifest[key]['sha256']!=digest:
            raise ValueError('source changed during audit: '+key)
        manifest[key]={'sha256':digest,'bytes':len(b)}
        return b

    def js(path): return json.loads(read(path))
    def write(name,value):
        with (out/name).open('x',encoding='utf-8') as f:
            json.dump(value,f,indent=2,default=str,allow_nan=False)

    # Capture file lists once. External scheduler continues independently.
    arch=root/'data/raw/archive'
    injury_files=sorted(arch.glob('espn_injuries_*.json'))
    official_files=sorted(arch.glob('nflverse_injuries_*.parquet'))
    phase7_files=sorted((arch/'phase7').glob('*.parquet'))
    market_files=sorted((arch/'market').glob('espn_odds_*.json'))+sorted((arch/'market').glob('going_*.json'))
    ledger=[json.loads(s) for s in read(root/'snapshots/prospective/ledger.jsonl').decode().splitlines() if s.strip()]
    for p in [root/'models'/VERSION/'manifest.json',root/'models'/VERSION/'bundle.joblib',
              root/'releases/CURRENT.json',root/'docs/QB_ASOF_PREREGISTRATION.md',root/'lab/qb_asof_audit.py']:
        read(p)
    games_bytes=read(root/'data/cache/games.parquet')
    games=pd.read_parquet(io.BytesIO(games_bytes))
    # Preserve outcome source used, separate from historical pregame availability.
    (out/'games_at_audit.parquet').write_bytes(games_bytes)
    depth=pd.read_parquet(io.BytesIO(read(root/'data/raw/depth_charts_2026.parquet')))
    inventory={'ledger_records':len(ledger),'games_in_ledger':len({r['game_id'] for r in ledger}),
               'espn_injury_versions':len(injury_files),'official_injury_versions':len(official_files),
               'phase7_versions':len(phase7_files),'market_versions':len(market_files),
               'depth_rows':len(depth),'depth_fields':list(depth.columns),
               'depth_original_version_archive_count':len(list(arch.rglob('*depth*')))}
    injuries=[]
    for p in injury_files:
        try:
            d=js(p); at=timestamp(d.get('timestamp'))
            # Keep both publication and observation times; no inferred stable ID from names.
            qb=[]
            for team in d.get('injuries',[]):
                for r in team.get('injuries',[]):
                    athlete=r.get('athlete') or {}
                    if (athlete.get('position') or {}).get('abbreviation')=='QB':
                        qb.append({'team_source_id':team.get('id'),'status':r.get('status'),
                                   'source_player_id':athlete.get('id'),'published_at':r.get('date'),
                                   'published_after_retrieval':timestamp(r.get('date')) is not None and at is not None and timestamp(r['date'])>at})
            if at is not None: injuries.append({'observed_at':at.isoformat(),'path':p.relative_to(root).as_posix(),'qb_reports':qb})
        except Exception as exc: failures.append({'path':str(p.relative_to(root)),'error':str(exc)})
    source_tables=[]
    for p in official_files+phase7_files:
        try:
            table=pd.read_parquet(io.BytesIO(read(p)))
            stamp=re.search(r'(\d{8}T\d{6}Z)',p.name)
            if not stamp: raise ValueError('missing observation timestamp in original archive name')
            kind='sleeper_players' if p.name.startswith('sleeper_') else 'nflcom_injuries' if p.name.startswith('nflcom_') else 'nflverse_injuries'
            selected=table[table['position'].eq('QB')]
            # JSON conversion preserves nulls without NaN and limits fields to evidence needed.
            fields=[c for c in ['team','week','gsis_id','report_status','status','injury_status','depth_chart_order','news_updated'] if c in table]
            source_tables.append({'kind':kind,'path':p.relative_to(root).as_posix(),
                                  'observed_at':pd.to_datetime(stamp[1],format='%Y%m%dT%H%M%SZ',utc=True).isoformat(),
                                  'schema':list(table.columns),'qb_rows':json.loads(selected[fields].to_json(orient='records'))})
        except Exception as exc: failures.append({'path':str(p.relative_to(root)),'error':str(exc)})
    quotes=[]
    for p in market_files:
        try:
            d=js(p); rel=p.relative_to(root).as_posix()
            if p.name.startswith('espn_'):
                for r in d.get('rows',[]):
                    if str(r.get('provider','')).lower()!='draftkings': continue
                    quotes.append({'home':TEAM.get(r.get('home'),r.get('home')),'away':TEAM.get(r.get('away'),r.get('away')),
                        'kickoff':r.get('kickoff'),'observed_at':d.get('retrieved_at'),'quote_time':None,
                        'p_home':novig(r.get('home_ml_close'),r.get('away_ml_close')),
                        'home_odds':r.get('home_ml_close'),'away_odds':r.get('away_ml_close'),
                        'book':'draftkings','event_id':r.get('event_id'),'path':rel,'clock':'retrieval_proxy'})
            else:
                content=d.get('content',[])
                # Verify normalized source content hash, not just present-day file identity.
                canonical=json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False,default=str).encode()
                if hashlib.sha256(canonical).hexdigest()!=d.get('content_sha256'):
                    raise ValueError('content hash mismatch')
                at=timestamp(d.get('archived_at')); av=timestamp(d.get('available_at'))
                if at is None or av is None: continue
                at=max(at,av); groups={}
                for r in content:
                    if r.get('book')!='draftkings' or r.get('market')!='h2h' or r.get('period')!='FULL' or r.get('in_play'): continue
                    key=(r.get('event_id'),r.get('home'),r.get('away'),r.get('kickoff'),r.get('quote_time'))
                    groups.setdefault(key,{}).setdefault(r.get('side'),[]).append(r.get('price'))
                for key,sides in groups.items():
                    if len(sides.get('home',[]))!=1 or len(sides.get('away',[]))!=1 or timestamp(key[4]) is None: continue
                    h,a=sides['home'][0],sides['away'][0]
                    quotes.append({'event_id':key[0],'home':key[1],'away':key[2],'kickoff':key[3],'quote_time':key[4],
                        'observed_at':at.isoformat(),'p_home':novig(h,a),'home_odds':h,'away_odds':a,
                        'book':'draftkings','path':rel,'clock':'source_and_local_archive'})
        except Exception as exc: failures.append({'path':str(p.relative_to(root)),'error':str(exc)})
    rows=[]; payloads={}
    # Use kickoff recorded in the earliest original forecast. Changes are excluded rather than resolved with hindsight.
    for game_id in sorted({r['game_id'] for r in ledger}):
        group=[r for r in ledger if r['game_id']==game_id]
        kicks={timestamp(r['kickoff_utc']) for r in group}
        kickoff=timestamp(min(group,key=lambda r:r['predicted_at'])['kickoff_utc'])
        decision=kickoff-pd.Timedelta(minutes=90)
        r=select_snapshot(group,decision)
        row={'game_id':game_id,'week':int(group[0]['week']),'kickoff':kickoff.isoformat(),'decision':decision.isoformat(),
             'schedule_conflict':len(kicks)!=1,'exclusions':[],'qb_evidence_status':'unverified',
             'p_challenger':None,'fit_eligible':False}
        if r is None:
            row['exclusions'].append('no champion snapshot before decision'); rows.append(row);continue
        p=root/'snapshots'/r['path']; d=js(p); rel=p.relative_to(root).as_posix();payloads[rel]=d
        row.update({'snapshot_path':rel,'snapshot_sha256':manifest[rel]['sha256'],
                    'snapshot_at':d['predicted_at'],'snapshot_age_minutes':(decision-timestamp(d['predicted_at'])).total_seconds()/60,
                    'p_champion':d.get('p_champion'),'home':d['home_team'],'away':d['away_team'],
                    'data_cutoff':d.get('data_cutoff'),'source_provenance':d.get('provenance'),
                    'champion_input_qb_fields':{k:v for k,v in d.get('champion_inputs',{}).items() if 'qb' in k.lower()},
                    'live_qb_monitoring_only':d.get('live_qb_monitoring_only')})
        if d.get('p_champion')!=r.get('p_champion') or d.get('model_version')!=VERSION or timestamp(d.get('predicted_at'))!=timestamp(r['predicted_at']):
            row['exclusions'].append('snapshot ledger mismatch')
        if row['schedule_conflict']: row['exclusions'].append('conflicting archived kickoff')
        input_times=[timestamp(v.get('downloaded_at')) for v in (d.get('provenance') or {}).values() if isinstance(v,dict)]
        row['source_after_snapshot_count']=sum(t is not None and t>timestamp(d['predicted_at']) for t in input_times)
        if row['source_after_snapshot_count']: row['exclusions'].append('source recorded after prediction')
        before=[i for i in injuries if timestamp(i['observed_at'])<=decision]
        latest=max(before,key=lambda i:i['observed_at']) if before else None
        row['injury_snapshot']=latest
        # Existing snapshot fields are projections, not source-linked confirmed starting identities.
        ci=d.get('champion_inputs') or {}
        row['qb_evidence']={side:qb_evidence(d[f'{side}_team'],ci.get(f'{side}_qb_id'),row['week'],decision,source_tables) for side in ['home','away']}
        row['champion_qb_identity_both']=all(e['champion_identity_recorded'] for e in row['qb_evidence'].values())
        row['exclusions'].append('affirmative starting availability not established for both teams; injury/depth projections insufficient')
        for age in [30,60,120]:
            row[f'market_{age}']=select_quote(quotes,d['home_team'],d['away_team'],kickoff,decision,age)
        row['later_archived_market']=select_quote(quotes,d['home_team'],d['away_team'],kickoff,kickoff-pd.Timedelta(nanoseconds=1),None)
        matches=games[games['game_id']==game_id]
        row['home_win']=None;row['outcome_status']='unfinished or missing'
        if len(matches)==1:
            g=matches.iloc[0]
            if bool(g.get('completed',False)) and not bool(g.get('tie',False)) and pd.notna(g.get('home_win')):
                row['home_win']=int(g['home_win']);row['outcome_status']='completed binary'
            elif bool(g.get('tie',False)): row['outcome_status']='tie excluded'
            row['retrospective_closing_p_home']=float(g['market_p_home_novig']) if pd.notna(g.get('market_p_home_novig')) else None
        rows.append(row)
    descriptions={}
    for age in [30,60,120]:
        common=[dict(r,p_market=r[f'market_{age}']['p_home']) for r in rows if r.get(f'market_{age}') and r.get('home_win') is not None
                and not r.get('schedule_conflict') and not r.get('source_after_snapshot_count') and len(r['exclusions'])==1]
        descriptions[str(age)]=compare(common)
    common=[r for r in rows if r.get('market_60') and r.get('later_archived_market') and r.get('home_win') is not None
            and len(r['exclusions'])==1]
    accounting={ 'n':len(common),'causal_attribution':'not identifiable: timestamps and simultaneous news incomplete'}
    if common:
        y=[r['home_win'] for r in common];c=[r['p_champion'] for r in common]
        m=[r['market_60']['p_home'] for r in common];later=[r['later_archived_market']['p_home'] for r in common]
        accounting.update({'champion_minus_same_time':float(np.mean(losses(y,c)-losses(y,m))),
                           'same_time_minus_later_archived':float(np.mean(losses(y,m)-losses(y,later))),
                           'champion_minus_later_archived':float(np.mean(losses(y,c)-losses(y,later)))})
    result={'started_at':started.isoformat(),'decision':'INCONCLUSIVE: provenance and training cohort unavailable',
            'configurations_preregistered':1,'configurations_fitted':0,'challenger_forecasts_created':0,
            'inventory':inventory,'champion_snapshot_games':sum('snapshot_path' in r for r in rows),
            'champion_qb_identity_both_games':sum(r.get('champion_qb_identity_both',False) for r in rows),
            'fully_verified_qb_games_established':0,'descriptive_market_comparisons':descriptions,'error_accounting':accounting,
            'power_scenarios':power(descriptions['60']['n']),
            'simulation_noise':'Winner inference uses fixed fitted classifiers; neural network eval mode disables dropout. No same-input seed replicates archived; numerical variance not estimated. This is not a props Monte Carlo study.',
            'failures':failures,'original_archives_changed_by_audit':False}
    write('RESULT.json',result);write('SAMPLE.json',rows);write('SELECTED_SNAPSHOTS.json',payloads)
    write('QUOTES.json',quotes);write('INJURY_TIMELINE.json',injuries);write('STRUCTURED_QB_SOURCES.json',source_tables);write('SOURCE_MANIFEST.json',manifest)
    return out,result


if __name__=='__main__':
    import psutil
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
    directory,result=audit()
    print(json.dumps({'packet':str(directory),'result':result},indent=2))
