"""Availability-aware, games-played rolling features and private NFL joins."""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
import pandas as pd
from ..fpds_ingest import number, slug
from ..config import LAB_ROOT
from ..data_pipeline import FEATURE_STORE
from ..props.ensemble.features import FEATURES, eligible, earlier_features
from ..props.independent import FEATURES as GAME_FEATURES
from .common import ROOT, VERSION, now, read, atomic, write_once, digest, sha
from .audit import latest

BASE=LAB_ROOT/'artifacts/props/phase10/weekly/2026_w07_r03_20261020T204312344118Z/features_production.parquet'
WINDOWS=(1,3,5,8)
PRIORITY=('xtd','i5','i20','ez','share','rte_pct','tgt_pct','att_pct','snap_pct','adot','yprr','yac','exp','pres','epa','pace','man_pct','zone_pct','rte','tprr','pass','snap','tgt','att','yds','rec','td','pct')


def selected_metrics(table):
    if table.get('valid_rows_games_gt_one',0)>0:
        # No verified cumulative-unit definitions: do not pretend these are per-game rows.
        return []
    values=[c for c in table['columns'] if c['laggable_numeric']]
    def order(c):
        text=c['column']
        return (next((i for i,x in enumerate(PRIORITY) if x in text),len(PRIORITY)),text)
    return [c['column'] for c in sorted(values,key=order)[:12]]


def schedule():
    g=pd.read_parquet(FEATURE_STORE)
    g=g[g.game_type.eq('REG') & g.season.between(2021,2026)].copy()
    g['kickoff_utc']=pd.to_datetime(g.kickoff_utc,utc=True)
    return g


def availability(games):
    return games.groupby(['season','week']).kickoff_utc.max()+pd.Timedelta(hours=24)


def rolling_panel(frame,columns,games):
    """One entity observation per played game; no fabricated bye observations."""
    d=frame.sort_values(['entity','season','week']).copy()
    clock=availability(games)
    d['available_at']=[clock.get((s,w),pd.NaT) for s,w in zip(d.season,d.week)]
    d['available_at']=pd.to_datetime(d.available_at,utc=True)
    d=d.dropna(subset=['available_at','entity'])
    pieces=[]
    for entity,z in d.groupby('entity',sort=False):
        values=z[columns].astype(float)
        features={}
        for w in WINDOWS:
            avg=values.rolling(w,min_periods=1).mean()
            for c in columns:features[c+f'__last{w}']=avg[c].to_numpy(np.float32)
        std=values.groupby(z.season.to_numpy()).expanding().mean().reset_index(level=0,drop=True).reindex(values.index)
        ewma=values.ewm(alpha=.3,adjust=False).mean()
        for c in columns:
            features[c+'__std']=std[c].to_numpy(np.float32)
            features[c+'__ewma']=ewma[c].to_numpy(np.float32)
            features[c+'__change']=features[c+'__last1']-features[c+'__last3']
        a=z[['season','week','entity','available_at']].reset_index(drop=True)
        if 'position' in z:a['position']=z.position.to_numpy()
        a=pd.concat([a,pd.DataFrame(features)],axis=1)
        a['observed_games']=np.arange(1,len(a)+1)
        pieces.append(a)
    if not pieces:return pd.DataFrame()
    result=pd.concat(pieces,ignore_index=True)
    keys=['season','week']+(['position'] if 'position' in result else [])
    for c in columns:
        # Same completed source week cohort, never target-week outcomes.
        result[c+'__position_adj']=result[c+'__last3']-result.groupby(keys,dropna=False)[c+'__last3'].transform('mean')
    return result


def join_asof(candidates,panel,columns,entity_column,prospective=False,observed_at=None):
    """Never match equal/later source weeks, even if a calendar timestamp is bad."""
    result=np.full((len(candidates),len(columns)),np.nan,dtype=np.float32)
    used_week=np.full(len(candidates),np.nan);used_season=np.full(len(candidates),np.nan)
    if panel.empty:return result,used_season,used_week
    target=candidates.reset_index(drop=True)
    grouped={k:v.sort_values('available_at') for k,v in panel.groupby('entity',sort=False)}
    times=pd.to_datetime(target.kickoff_utc,utc=True).astype('int64').to_numpy()
    current=pd.Timestamp.now(tz='UTC').value
    for entity,indices in target.groupby(entity_column,sort=False).indices.items():
        p=grouped.get(entity)
        if p is None:continue
        pt=p.available_at.astype('int64').to_numpy()
        cut=np.minimum(times[indices],current) if prospective else times[indices]
        loc=np.searchsorted(pt,cut,side='left')-1
        ok=loc>=0
        if not ok.any():continue
        ix=np.asarray(indices)[ok];chosen=p.iloc[loc[ok]]
        strict=(chosen.season.to_numpy()*100+chosen.week.to_numpy()) < (target.iloc[ix].season.to_numpy()*100+target.iloc[ix].week.to_numpy())
        if prospective and observed_at is not None:strict &= pd.Timestamp(observed_at).value < cut[ok]
        ix=ix[strict];chosen=chosen[strict]
        result[ix]=chosen[columns].to_numpy(np.float32)
        used_week[ix]=chosen.week;used_season[ix]=chosen.season
    return result,used_season,used_week


def numeric_panel(raw,table,columns):
    d=raw[['season','week','entity','team','pid']].copy()
    for c in columns:
        percent='pct' in c
        d[c]=raw[c].map(lambda x:number(x,percent=percent)).astype(np.float32)
    # Split rows / combinations are overlapping units: mean, never a fabricated sum.
    d=d.dropna(subset=['entity'])
    out=d.groupby(['season','week','entity'],as_index=False)[columns].mean()
    pos='position_asof' if 'position_asof' in raw else '_position'
    if pos in raw:
        positions=raw.dropna(subset=['entity']).groupby(['season','week','entity'])[pos].agg(lambda x:next(iter(set(x.dropna()))) if x.dropna().nunique()==1 else 'UNKNOWN').reset_index(name='position')
        out=out.merge(positions,on=['season','week','entity'],how='left',validate='one_to_one')
    return out


def run(base=BASE):
    manifest=latest();g=schedule()
    observed_path=Path(base).with_name('observations_production.parquet')
    fingerprint=digest({'schema':VERSION,'import':manifest['fingerprint'],'base':sha(base),
                        'observations':sha(observed_path) if observed_path.exists() else None,
                        'games':sha(FEATURE_STORE),'implementation':sha(Path(__file__))})
    directory=ROOT/'features'/fingerprint[:20]
    if (directory/'FEATURES.json').exists():
        atomic(ROOT/'LATEST_FEATURES.json',{'path':str(directory),'fingerprint':fingerprint})
        return read(directory/'FEATURES.json')
    directory.mkdir(parents=True,exist_ok=True)
    frame=pd.read_parquet(base,filters=[('season','>=',2021)])
    frame=frame.reset_index(drop=True)
    frame['kickoff_utc']=pd.to_datetime(frame.kickoff_utc,utc=True)
    # Ignore retrospective target-week decision_time=min(kickoff,old preparation time).
    frame['decision_time']=frame.kickoff_utc
    observed_path=Path(base).with_name('observations_production.parquet')
    if observed_path.exists():
        targets=('rec','rec_yds','rush_yds','pass_yds','pass_tds')
        observations=pd.read_parquet(observed_path)
        played=observations.snap_share.fillna(0).gt(0)|observations[['targets','carries','dropbacks']].fillna(0).sum(axis=1).gt(0)
        observations=observations[played].sort_values(['pid','season','week'])
        nflgames=pd.read_parquet(FEATURE_STORE,columns=['season','week','game_type','kickoff_utc'])
        nflgames=nflgames[nflgames.game_type.eq('REG')].copy();nflgames['kickoff_utc']=pd.to_datetime(nflgames.kickoff_utc,utc=True)
        nflclock=availability(nflgames)
        observations['source_available_at']=pd.to_datetime([nflclock.get((s,w),pd.NaT) for s,w in zip(observations.season,observations.week)],utc=True)
        chunks=[]
        clock=nflclock
        for pid,z in observations.groupby('pid',sort=False):
            a=z[['season','week']].copy();a['entity']=pid
            a['available_at']=[clock.get((s,w),pd.NaT) for s,w in zip(z.season,z.week)]
            for stat in targets:a['pseudo_'+stat]=np.round(z[stat].rolling(8,min_periods=1).median()*2)/2
            chunks.append(a)
        if chunks:
            p=pd.concat(chunks,ignore_index=True).dropna(subset=['available_at'])
            p['available_at']=pd.to_datetime(p.available_at,utc=True)
            cols=['pseudo_'+s for s in targets]
            values,_,_=join_asof(frame,p,cols,'pid')
            for c,v in zip(cols,values.T):frame[c]=v
        # Reuse the lab's formulas, but exclude DNP rows and observations whose
        # whole source week is not yet available. Original frozen artifacts stay untouched.
        computed=[c for c in frame if c.startswith('hist_') or c.startswith('history_last_') or c.startswith('opp_position_') or c=='opp_adjustment' or c in ('adot','yac_rate','deep_target_rate','outside_rz_td_rate','explosive_rate','long_td_rate','is_qb','is_rb','is_wr','is_te')]
        candidates=frame.drop(columns=computed)
        rebuilt=[]
        for _,target in candidates.groupby(['season','week'],sort=True):
            h=observations[observations.source_available_at.lt(target.kickoff_utc.min())]
            rebuilt.append(earlier_features(h,target))
        frame=pd.concat(rebuilt,ignore_index=True)
    union=np.zeros(len(frame),bool)
    for stat in ('rec','rec_yds','rush_yds','anytime_td','pass_yds','pass_tds'):union |= eligible(frame,stat)
    frame=frame[union].reset_index(drop=True)
    clock=availability(g)
    cutoff=pd.to_datetime([clock.get((s,w),pd.NaT) for s,w in zip(frame.history_last_season,frame.history_last_week)],utc=True)
    invalid=pd.Series(cutoff,index=frame.index).ge(frame.kickoff_utc)
    history_columns=[c for c in FEATURES if c.startswith('hist_') or c.startswith('opp_') or c in ('adot','yac_rate','deep_target_rate','outside_rz_td_rate','explosive_rate','long_td_rate','ind_team_margin','ind_total')]
    frame.loc[invalid,history_columns]=np.nan
    games=g.copy();games['total']=games.home_score+games.away_score;games['win']=games.home_win
    previous_week=pd.to_datetime([clock.get((s,w-1),pd.NaT) for s,w in zip(games.season,games.week)],utc=True)
    unsafe=pd.Series(previous_week,index=games.index).ge(games.kickoff_utc)
    games.loc[unsafe,[c for c in GAME_FEATURES if c in games and not c.startswith('ctx_')]]=np.nan
    groups={};added={};game_added={};timing=[];coverage=[]
    model_count=0
    for table in sorted(manifest['working_tables'],key=lambda t:t['table']):
        name=table['table'];metrics=selected_metrics(table)
        if not metrics:
            coverage.append({'table':name,'status':'blocked: no unambiguous numeric weekly metrics','matched_rows':0})
            continue
        raw=pd.read_parquet(table['private_path'])
        panel=numeric_panel(raw,table,metrics)
        rolled=rolling_panel(panel,metrics,g)
        if rolled.empty:
            coverage.append({'table':name,'status':'blocked: no verified entity/week history','matched_rows':0})
            continue
        rolled.to_parquet(directory/(name+'__windows.parquet'),index=False)
        # Fixed columns used by models; other windows stay in the private per-table cache.
        role=[c for c in metrics if any(k in c for k in ('share','rte','snap','tgt','att'))]
        cols=([c+'__last3' for c in metrics]+[c+'__last8' for c in metrics[:4]]+
              [c+'__change' for c in (role or metrics)[:2]]+[c+'__position_adj' for c in metrics[:2]])
        # Reserve a fixed equal share of the ceiling for every source table.
        # Alphabetical tables must not consume the allowance of later tables.
        remaining=max(0,768-model_count)
        cols=cols[:min(remaining,768//max(1,len(manifest['working_tables']))) ]
        qb_context=name.startswith('passing_')
        player=table['entity_kind']=='player' and 'cornerback' not in name and not qb_context
        defensive=any(x in name for x in ('defense','allowed','coverage','cornerback')) or name in ('lineup_combos_db','lineup_combos_front')
        if 'cornerback' in name:
            # Defensive-player histories attach to the opponent as a team mean.
            cb=raw[raw.entity.notna()].copy();cb['entity']=cb.team
            rolled=rolling_panel(numeric_panel(cb,table,metrics),metrics,g)
        key='projected_qb' if qb_context else 'pid' if player else 'opponent' if defensive else 'team'
        values,sy,sw=join_asof(frame,rolled,cols,key)
        prefix='fp__'+name+'__';names=[prefix+c for c in cols]
        for c,v in zip(names,values.T):added[c]=v
        groups[name]={'family':table['family'],'columns':names,'metrics':metrics,'entity_kind':'player' if player else 'team',
                      'source_entity_kind':table['entity_kind'],
                      'join_key':key,
                      'aggregation':'source entity/week arithmetic mean for overlapping splits; no fabricated totals'}
        model_count+=len(cols)
        timing.append(pd.DataFrame({'game_id':frame.game_id,'pid':frame.pid,'table':name,'source_season':sy,'source_week':sw}))
        matched=np.isfinite(values).any(axis=1)
        coverage.append({'table':name,'status':'usable' if matched.any() else 'no matched eligible history',
                         'matched_rows':int(matched.sum()),'eligible_rows':len(frame),
                         'by_season':{str(s):{'n':int(len(ix)),'matched':int(matched[ix].sum())} for s,ix in frame.groupby('season').indices.items()}})
        # Team aggregates include defensive players / units. Means are role/unit averages, not team totals.
        teamraw=raw[raw.entity.notna()].copy();teamraw['entity']=teamraw.team
        team_panel=numeric_panel(teamraw,table,metrics)
        teamroll=rolling_panel(team_panel,metrics,g)
        teamcols=[c+'__last3' for c in metrics[:4]]
        for side in ('home','away'):
            candidate=games.rename(columns={side+'_team':'team'})
            vals,_,_=join_asof(candidate,teamroll,teamcols,'team')
            for c,v in zip(teamcols,vals.T):game_added['fpg__'+name+'__'+side+'__'+c]=v
    frame=pd.concat([frame,pd.DataFrame(added)],axis=1)
    games=pd.concat([games.reset_index(drop=True),pd.DataFrame(game_added)],axis=1)
    frame.to_parquet(directory/'players.parquet',index=False)
    games.to_parquet(directory/'games.parquet',index=False)
    if timing:pd.concat(timing,ignore_index=True).to_parquet(directory/'TIMING.parquet',index=False)
    fpcols=list(added);own=[c for g in groups.values() if g['entity_kind']=='player' for c in g['columns']]
    any_history=frame[fpcols].notna().any(axis=1);own_history=frame[own].notna().any(axis=1)
    metadata={'created_at':now(),'fingerprint':fingerprint,'path':str(directory),'rows':len(frame),
              'import_fingerprint':manifest['fingerprint'],'import_manifest_path':manifest['path'],
              'base_sha256':sha(base),'observations_sha256':sha(observed_path) if observed_path.exists() else None,
              'rows_without_any_fpds_history':int((~any_history).sum()),'rows_without_player_fpds_history':int((~own_history).sum()),
              'history_by_season':{str(s):{'rows':len(ix),'no_any_history':int((~any_history.iloc[ix]).sum()),'no_player_history':int((~own_history.iloc[ix]).sum())} for s,ix in frame.groupby('season').indices.items()},
              'base_source':str(base),'groups':groups,'coverage':coverage,'base_columns':[c for c in FEATURES if c in frame],
              'game_base_columns':[c for c in GAME_FEATURES if c in games],
              'game_fp_columns':list(game_added),'source_observed_at':max(t.get('first_observed_at',t['imported_at']) for t in manifest['working_tables']),
              'historical_publication':'event-time reconstruction only; original vendor publication/revisions unverified'}
    write_once(directory/'FEATURES.json',metadata)
    atomic(LAB_ROOT/'docs'/'FPDS_FEATURE_COVERAGE.json',{k:metadata[k] for k in ('created_at','fingerprint','rows','rows_without_any_fpds_history','rows_without_player_fpds_history','history_by_season','coverage')})
    atomic(ROOT/'LATEST_FEATURES.json',{'path':str(directory),'fingerprint':fingerprint})
    return metadata


def latest_features():
    return read(read(ROOT/'LATEST_FEATURES.json')['path']+'/FEATURES.json')
