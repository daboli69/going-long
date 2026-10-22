"""Discrete score pairs from earlier verified scoreboard-consistent drives."""
import numpy as np
import pandas as pd
from .targets import team_code

COLS=['game_id','play_id','season','week','season_type','qtr','fixed_drive','posteam','home_team','away_team',
      'total_home_score','total_away_score','home_score','away_score','play_deleted']


def extract(plays):
    p=plays[plays.season_type.eq('REG')&plays.play_deleted.fillna(0).eq(0)].sort_values(['game_id','play_id']).copy()
    for side in ('home','away'):
        score=p.groupby('game_id')['total_'+side+'_score'].ffill().fillna(0)
        before=score.groupby(p.game_id).shift().fillna(0)
        p['delta_'+side]=score-before
    p['period']=np.where(p.qtr.gt(4),'OT','REG')
    for c in ('posteam','home_team','away_team'):p[c]=p[c].map(team_code)
    p=p[p.fixed_drive.notna()|(p.delta_home+p.delta_away).gt(0)].copy()
    # Missing drive labels retain a unique event; unknown offensive teams with
    # points are quarantined rather than assigned to a team by guesswork.
    p['drive_key']=p.fixed_drive.fillna(-p.play_id-1)
    rows=p.groupby(['game_id','period','drive_key'],as_index=False).agg(
        season=('season','first'),week=('week','first'),team=('posteam','first'),home_team=('home_team','first'),away_team=('away_team','first'),
        home_points=('delta_home','sum'),away_points=('delta_away','sum'))
    final=p.groupby('game_id').agg(home=('home_score','max'),away=('away_score','max'))
    sums=rows.groupby('game_id')[['home_points','away_points']].sum()
    check=final.join(sums)
    bad=set(check.index[(check.home-check.home_points).abs().gt(.01)|(check.away-check.away_points).abs().gt(.01)])
    bad.update(rows.loc[(rows.team.isna()&(rows.home_points+rows.away_points).gt(0))|rows.home_points.lt(0)|rows.away_points.lt(0),'game_id'])
    rows=rows[~rows.game_id.isin(bad)&rows.team.notna()].copy()
    rows['opponent']=np.where(rows.team.eq(rows.home_team),rows.away_team,rows.home_team)
    rows['off_points']=np.where(rows.team.eq(rows.home_team),rows.home_points,rows.away_points).astype(int)
    rows['opp_points']=np.where(rows.team.eq(rows.home_team),rows.away_points,rows.home_points).astype(int)
    return rows,{'raw_games':len(final),'quarantined_games':len(bad),'verified_games':int(rows.game_id.nunique()),
                 'rule':'all drive increments sum to final local scoreboard; regulation and OT separated; not an independent official feed'}


def simulate(history,home,away,sims,rng):
    reg=history[history.period.eq('REG')]
    if reg.game_id.nunique()<30:raise ValueError('Insufficient verified earlier drives')
    events=reg.groupby(['off_points','opp_points']).size();pairs=np.array(list(events.index),int)
    freq=events.to_numpy(float);league=freq/freq.sum()
    counts=reg.assign(is_home=reg.team.eq(reg.home_team)).groupby(['game_id','is_home']).size().unstack(fill_value=0)
    counts=counts.reindex(columns=[True,False],fill_value=0).to_numpy(int)
    counts=counts[(counts>0).all(1)];n=counts[rng.integers(0,len(counts),sims)]
    totals=np.zeros((sims,2),float)
    for side,(team,opp) in enumerate(((home,away),(away,home))):
        offense=reg[reg.team.eq(team)].groupby(['off_points','opp_points']).size().reindex(events.index,fill_value=0).to_numpy(float)
        defense=reg[reg.opponent.eq(opp)].groupby(['off_points','opp_points']).size().reindex(events.index,fill_value=0).to_numpy(float)
        a=(offense+80*league)/(offense.sum()+80);b=(defense+80*league)/(defense.sum()+80)
        prob=a*b/np.maximum(league,1e-12);prob/=prob.sum()
        chosen=rng.choice(len(pairs),(sims,int(n[:,side].max())),p=prob)
        valid=np.arange(chosen.shape[1])[None,:]<n[:,side,None]
        result=pairs[chosen]*valid[:,:,None]
        totals[:,side]+=result[:,:,0].sum(1);totals[:,1-side]+=result[:,:,1].sum(1)
    ot=history[history.period.eq('OT')].groupby('game_id')[['home_points','away_points']].sum().to_numpy(float)
    tied=totals[:,0]==totals[:,1]
    if tied.any() and len(ot):totals[tied]+=ot[rng.integers(0,len(ot),tied.sum())]
    return totals,{'earlier_games':int(reg.game_id.nunique()),'earlier_ot_games':len(ot),'simulated_tie_probability':float((totals[:,0]==totals[:,1]).mean())}
