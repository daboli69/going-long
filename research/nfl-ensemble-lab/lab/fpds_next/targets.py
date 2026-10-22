"""Local PBP reconstruction; never claims independent official certification."""
import numpy as np
import pandas as pd
from ..ingest import normalize_team

STATS=('pass_yds','pass_tds','rec','rec_yds','rush_yds','anytime_td')
EXTRA=['pass_attempt','rush_attempt','play_deleted','td_player_id','td_team','return_touchdown',
       'lateral_receiver_player_id','lateral_receiving_yards','lateral_rusher_player_id','lateral_rushing_yards']


def team_code(value):
    if pd.isna(value):return None
    try:return normalize_team(value)
    except ValueError:return None  # Unknown team is quarantined, never guessed.


def reconstruct(plays,rosters,snaps):
    p=plays[plays.season_type.eq('REG') & plays.two_point_attempt.fillna(0).eq(0)
            & plays.play_deleted.fillna(0).eq(0) & plays.play_type.ne('no_play')].copy()
    p['team']=p.posteam.map(team_code)
    chunks=[]
    def add(mask,idcol,values):
        d=p.loc[mask & p[idcol].notna(),['game_id','season','week','team',idcol]].rename(columns={idcol:'pid'}).copy()
        for c,v in values.items():d[c]=v.loc[d.index].fillna(0) if isinstance(v,pd.Series) else v
        chunks.append(d)
    passing=p.pass_attempt.fillna(0).eq(1) & p.sack.fillna(0).eq(0)
    rushing=p.rush_attempt.fillna(0).eq(1)|p.qb_kneel.fillna(0).eq(1)
    add(passing,'passer_player_id',{'pass_yds':p.passing_yards,'pass_tds':p.pass_touchdown,'dropbacks':1})
    add(passing,'receiver_player_id',{'targets':1,'rec':p.complete_pass,'rec_yds':p.receiving_yards})
    add(rushing,'rusher_player_id',{'carries':1,'rush_yds':p.rushing_yards})
    for kind in ('receiving','rushing'):
        col='lateral_receiver_player_id' if kind=='receiving' else 'lateral_rusher_player_id'
        add(p[col].notna(),col,{'rec_yds' if kind=='receiving' else 'rush_yds':p['lateral_'+kind+'_yards']})
    td=(p.pass_touchdown.fillna(0).eq(1)|p.rush_touchdown.fillna(0).eq(1)) & p.return_touchdown.fillna(0).eq(0)
    add(td,'td_player_id',{'off_td':1})
    values=['pass_yds','pass_tds','rec','rec_yds','rush_yds','targets','carries','dropbacks','off_td']
    observed=pd.concat(chunks,ignore_index=True)
    for c in values:
        if c not in observed:observed[c]=0.
    observed[values]=observed[values].fillna(0)
    observed=observed.groupby(['game_id','season','week','team','pid'],as_index=False)[values].sum()
    r=rosters.copy();r['team']=r.team.map(team_code);r=r[r.team.notna()]
    mapping=r.dropna(subset=['pfr_id','gsis_id'])[['season','week','team','pfr_id','gsis_id']].drop_duplicates()
    unique=~mapping.duplicated(['season','week','team','pfr_id'],keep=False)
    mapping=mapping[unique]
    sn=snaps[snaps.game_type.eq('REG') & snaps.offense_snaps.gt(0)].copy();sn['team']=sn.team.map(team_code)
    sn=sn.merge(mapping,left_on=['season','week','team','pfr_player_id'],right_on=['season','week','team','pfr_id'],how='left',validate='many_to_one')
    participants=sn.dropna(subset=['gsis_id'])[['game_id','season','week','team','gsis_id']].rename(columns={'gsis_id':'pid'})
    participants=pd.concat([observed[['game_id','season','week','team','pid']],participants],ignore_index=True).drop_duplicates()
    out=participants.merge(observed,on=['game_id','season','week','team','pid'],how='left',validate='one_to_one')
    out[values]=out[values].fillna(0)  # Verified offensive participation only, not roster ACT.
    out['anytime_td']=out.off_td.gt(0).astype(float)
    pos=r[['season','week','team','gsis_id','position']].drop_duplicates()
    pos=pos[~pos.duplicated(['season','week','team','gsis_id'],keep=False)].rename(columns={'gsis_id':'pid'})
    out=out.merge(pos,on=['season','week','team','pid'],how='left',validate='many_to_one')
    lateral_rec=set(p.loc[p.lateral_receiver_player_id.notna(),'game_id'])
    lateral_rush=set(p.loc[p.lateral_rusher_player_id.notna(),'game_id'])
    missing_td=set(p.loc[td & p.td_player_id.isna(),'game_id'])
    missing_pass=set(p.loc[passing & p.passer_player_id.isna(),'game_id'])
    missing_rush=set(p.loc[rushing & p.rusher_player_id.isna(),'game_id'])
    # PBP only identifies the final lateral receiver. Multi-lateral completeness
    # cannot be certified locally, so affected yard targets remain quarantined.
    for stat,bad in [('rec_yds',lateral_rec),('rush_yds',lateral_rush|missing_rush),
                     ('anytime_td',missing_td),('pass_yds',missing_pass),('pass_tds',missing_pass)]:
        out.loc[out.game_id.isin(bad),stat]=np.nan
    out['target_source']='local PBP + verified offensive snaps; not independently box-score certified'
    report={'known_participant_rows':len(out),'offensive_snap_rows':len(sn),
            'unmatched_snap_rows':int(sn.gsis_id.isna().sum()),
            'unknown_team_play_rows':int(p.team.isna().sum()),
            'quarantined_games':{'receiving_laterals':len(lateral_rec),'rushing_laterals_or_missing_id':len(lateral_rush|missing_rush),
                                 'missing_scorer_id':len(missing_td),'missing_passer_id':len(missing_pass)},
            'unknown_labels':{s:int(out[s].isna().sum()) for s in STATS},
            'certification':'reconstructed only; no independent official player-stat file available locally'}
    return out,report


def join_targets(candidates,observed):
    # Do not reassign candidate teams using postgame evidence: wrong-team
    # pregame context must be excluded, not silently corrected after the game.
    d=candidates.drop(columns=list(STATS),errors='ignore').merge(
        observed[['game_id','team','pid']+list(STATS)],on=['game_id','team','pid'],how='left',validate='one_to_one')
    return d
