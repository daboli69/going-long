"""Matched free-NFL history windows in both arms; FPDS adds audited features."""
import copy
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from ..fpds_research.common import read,write_once,digest,sha
from ..fpds_research.features import rolling_panel,join_asof
from ..props.ensemble.features import RAW_STATS


def capped_candidates(frame,asof):
    result=frame.copy()
    result['kickoff_utc']=pd.to_datetime(result.kickoff_utc,utc=True).clip(upper=asof)
    return result


def matched_windows(players,games,observations,asof=None):
    players=players.copy();games=games.copy();observations=observations.copy()
    played=observations.snap_share.fillna(0).gt(0)|observations[['targets','carries','dropbacks']].fillna(0).sum(axis=1).gt(0)
    observations=observations[played & observations.season.ge(2021)].drop_duplicates(['game_id','pid'])
    asof=pd.Timestamp.now(tz='UTC') if asof is None else asof
    metrics=[c for c in RAW_STATS if c in observations]
    playerobs=observations[observations.pid.isin(players.pid)]
    raw=playerobs[['season','week','pid']+(['position'] if 'position' in playerobs else [])+metrics].rename(columns={'pid':'entity'})
    panel=rolling_panel(raw,metrics,games)
    columns=[c for c in panel if any(c.endswith('__'+suffix) for suffix in ('last1','last3','last5','last8','std','ewma','change','position_adj'))]
    values,_,_=join_asof(capped_candidates(players,asof),panel,columns,'pid')
    player_cols=['nflw__'+c for c in columns]
    players=pd.concat([players.reset_index(drop=True),pd.DataFrame(values,columns=player_cols)],axis=1)
    volume=[c for c in ('targets','carries','dropbacks','pass_yds','pass_tds','rec','rec_yds','rush_yds','off_td') if c in observations]
    team=observations.groupby(['season','week','team'],as_index=False)[volume].sum().rename(columns={'team':'entity'})
    rolled=rolling_panel(team,volume,games)
    cols=[c for c in rolled if c.endswith(('__last1','__last3','__last5','__last8','__std','__ewma','__change'))]
    added={}
    for side in ('home','away'):
        values,_,_=join_asof(capped_candidates(games,asof),rolled,cols,side+'_team')
        added.update({'nflw_'+side+'__'+c:v for c,v in zip(cols,values.T)})
    games=pd.concat([games.reset_index(drop=True),pd.DataFrame(added)],axis=1)
    return players,games,player_cols,list(added)


def cap_future(original,players,games,observations,asof):
    """Future-week features stop at NOW, not at the later forecast kickoff."""
    from ..fpds_research.features import availability,numeric_panel
    from ..props.ensemble.features import earlier_features
    future=players.kickoff_utc.gt(asof)
    if future.any():
        clock=availability(games)
        known=[clock.get((s,w),pd.Timestamp.max.tz_localize('UTC'))<asof for s,w in zip(observations.season,observations.week)]
        h=observations[known]
        computed=[c for c in players if c.startswith(('hist_','history_last_','opp_position_')) or c in ('opp_adjustment','adot','yac_rate','deep_target_rate','outside_rz_td_rate','explosive_rate','long_td_rate','is_qb','is_rb','is_wr','is_te')]
        candidates=players.loc[future].drop(columns=computed)
        rebuilt=earlier_features(h,candidates)
        for c in computed:
            if c in rebuilt:players.loc[future,c]=rebuilt[c].to_numpy()
    target=capped_candidates(players,asof)
    manifest=read(Path(original['import_manifest_path'])/'MANIFEST.json')
    tables={t['table']:t for t in manifest['working_tables']}
    for table,group in original['groups'].items():
        prefix='fp__'+table+'__';cols=[c.removeprefix(prefix) for c in group['columns']]
        raw=pd.read_parquet(tables[table]['private_path']);raw=raw[raw.entity.notna()].copy();raw['entity']=raw.team
        metrics=group['metrics'];rolled=rolling_panel(numeric_panel(raw,tables[table],metrics),metrics,games)
        panel=pd.read_parquet(Path(original['path'])/(table+'__windows.parquet'))
        if 'cornerback' in table:panel=rolled
        values,_,_=join_asof(target,panel,cols,group['join_key'])
        players.loc[:,group['columns']]=values
        teamcols=[c+'__last3' for c in metrics[:4]]
        for side in ('home','away'):
            vals,_,_=join_asof(capped_candidates(games,asof),rolled,teamcols,side+'_team')
            for c,v in zip(teamcols,vals.T):games['fpg__'+table+'__'+side+'__'+c]=v
    return players,games


def build(original,path):
    original=copy.deepcopy(original)
    players=pd.read_parquet(Path(original['path'])/'players.parquet')
    games=pd.read_parquet(Path(original['path'])/'games.parquet')
    for frame in (players,games):frame['kickoff_utc']=pd.to_datetime(frame.kickoff_utc,utc=True)
    observations_path=Path(original['base_source']).with_name('observations_production.parquet')
    observations=pd.read_parquet(observations_path)
    asof=pd.Timestamp.now(tz='UTC')
    players,games=cap_future(original,players,games,observations,asof)
    players,games,pcols,gcols=matched_windows(players,games,observations,asof)
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    players.to_parquet(path/'players.parquet',index=False);games.to_parquet(path/'games.parquet',index=False)
    original['original_path']=original['path'];original['path']=str(path)
    # Avoid undated QB/injury/script inputs. Future game controls use known
    # schedule context and identically lagged free team statistics in both arms.
    original['base_columns']=[c for c in original['base_columns'] if c.startswith(('hist_','opp_','is_')) or c in ('adot','yac_rate','deep_target_rate','outside_rz_td_rate','explosive_rate','long_td_rate','home','rest','dome')]+pcols
    original['game_base_columns']=[c for c in original['game_base_columns'] if c.startswith('ctx_')]+gcols
    original['fingerprint']=digest({'original':original['fingerprint'],'matched_windows':sha(Path(__file__))})
    original['files']={name:sha(path/name) for name in ('players.parquet','games.parquet')}
    original['fingerprint']=digest({'features':original['fingerprint'],'files':original['files']})
    original['history_windows']='last1/3/5/8 played games, season-to-date, EWMA .3, role change; same in both arms'
    original['feature_creation_cutoff']=asof.isoformat()
    original['source_policy']='full-history-authority-v1'
    hashes={}
    for name,frame,cols in [('players',players,original['base_columns']+[c for g in original['groups'].values() for c in g['columns']]+['pid','pass_yds','pass_tds','rec','rec_yds','rush_yds','anytime_td']),
                            ('games',games,original['game_base_columns']+original['game_fp_columns']+['win','margin','total'])]:
        cols=sorted(set(cols+['game_id','season','week']))
        d=frame.loc[frame.season.le(2024),cols].sort_values(['season','week','game_id']+(['pid'] if name=='players' else []))
        hashes[name]=hashlib.sha256(pd.util.hash_pandas_object(d,index=False).to_numpy().tobytes()).hexdigest()
    original['discovery_fingerprint']=digest(hashes)
    write_once(path/'FEATURES.json',original)
    return original
