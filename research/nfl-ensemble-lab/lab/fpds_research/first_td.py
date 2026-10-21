"""Exploratory first offensive scorer, explicit other-player/no-TD classes."""
import numpy as np
import pandas as pd
from ..config import RAW_DIR
from .common import STATS, ROOT, write_once, now,sha


def labels(seasons):
    chunks=[]
    for season in seasons:
        source=RAW_DIR/f'play_by_play_{season}.parquet'
        path=ROOT/'labels'/f'first_td_{season}_{sha(source)[:16]}.parquet'
        if path.exists():chunks.append(pd.read_parquet(path));continue
        p=pd.read_parquet(source,columns=['game_id','play_id','season_type','qtr',
            'pass_touchdown','rush_touchdown','receiver_player_id','rusher_player_id','two_point_attempt'])
        games=p[p.season_type.eq('REG')][['game_id']].drop_duplicates()
        p=p[p.season_type.eq('REG')&p.qtr.le(4)&p.two_point_attempt.fillna(0).eq(0)&(p.pass_touchdown.eq(1)|p.rush_touchdown.eq(1))].copy()
        p['scorer']=p.receiver_player_id.where(p.pass_touchdown.eq(1),p.rusher_player_id)
        first=p.sort_values(['game_id','play_id']).drop_duplicates('game_id')[['game_id','scorer']]
        d=games.merge(first,on='game_id',how='left');d['scorer']=d.scorer.fillna('NO_OFFENSIVE_TD')
        path.parent.mkdir(parents=True,exist_ok=True);d.to_parquet(path,index=False);chunks.append(d)
    return pd.concat(chunks,ignore_index=True)


def probabilities(player_ids,atd,no_td,other):
    h=-np.log1p(-np.clip(np.asarray(atd,float),0,1-1e-6))
    if not len(h):return ['OTHER_PLAYERS','NO_OFFENSIVE_TD'],np.array([1-no_td,no_td])
    share=h/h.sum() if h.sum()>0 else np.full(len(h),1/max(1,len(h)))
    values=(1-no_td)*(1-other)*share
    return list(player_ids)+['OTHER_PLAYERS','NO_OFFENSIVE_TD'],np.r_[values,(1-no_td)*other,no_td]


def run_config(directory,spec,frame,games,seasons,deadline):
    from .walkforward import completed_blocks
    from ..props.ensemble.features import eligible
    arm=spec['arm'];source={'id':f'anytime_td__{arm}__all__linear'}
    predicted=completed_blocks(directory,source)
    if predicted.empty:raise ValueError('ATD precursor unavailable')
    actual=labels(range(2021,max(seasons)+1));g=games.merge(actual,on='game_id')
    candidates=frame[eligible(frame,'anytime_td')][['game_id','pid']]
    scope=set(map(tuple,candidates.to_numpy()))
    for season in seasons:
        for week in (1,5,9,13,17):
            if season==2026 and week>6:continue
            if (deadline-pd.Timestamp.now(tz='UTC')).total_seconds()<180:raise TimeoutError('First-TD deadline')
            path=directory/'blocks'/spec['id']/f'{season}_w{week:02d}.parquet'
            if path.exists():continue
            prior=g[(g.season<season)|((g.season==season)&(g.week<week))]
            from .features import availability
            clock=availability(games)
            first=games[games.season.eq(season)&games.week.between(week,min(week+3,18))].kickoff_utc.min()
            prior=prior[[clock.get((r.season,r.week),pd.Timestamp.max.tz_localize('UTC'))<first for r in prior.itertuples()]]
            td=prior[prior.scorer.ne('NO_OFFENSIVE_TD')]
            no_td=(len(prior)-len(td)+1)/(len(prior)+2)
            other=(sum((r.game_id,r.scorer) not in scope for r in td.itertuples())+1)/(len(td)+2)
            target=g[g.season.eq(season)&g.week.between(week,min(week+3,18))]
            rows=[]
            for r in target.itertuples():
                p=predicted[predicted.game_id.eq(r.game_id)]
                if p.empty:continue
                ids,values=probabilities(p.pid,p.pred,no_td,other)
                label=r.scorer if r.scorer in ids else 'OTHER_PLAYERS'
                truth=np.array([i==label for i in ids],float)
                index=ids.index(label)
                rows.append({'game_id':r.game_id,'season':season,'week':r.week,'actual':label,
                             'pred':float(values[index]),'raw':float(values[index]),'loss':float(-np.log(max(values[index],1e-9))),
                             'brier':float(np.sum((values-truth)**2)),'classes':len(ids),'sum_probability':float(values.sum())})
            path.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_parquet(path,index=False)
            write_once(path.with_suffix('.json'),{'created_at':now(),'prior_games':len(prior),'no_offensive_td_probability':no_td,
                       'other_player_share':other,'definition':'first regulation offensive rushing/receiving TD; passing/defensive/special-teams excluded'})
