"""Reconstruct champion-style information with the stricter source-week clock."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from .. import features as F
from ..fpds_research.features import availability


def strong_games(targets, source_games, team_stats, qb_stats, injury_rows, before_fit=lambda _:None):
    source=source_games[source_games.game_type.eq('REG') & source_games.season.between(2020,2024)].copy()
    source['kickoff_utc']=pd.to_datetime(source.kickoff_utc,utc=True)
    clock=availability(source)
    long=F._team_game_long(source,team_stats.drop(columns=['season'],errors='ignore'))
    long['kickoff_utc']=[clock.loc[(s,w)] for s,w in zip(long.season,long.week)]
    states=F.team_pregame_states(targets,long)
    keep=[c for c in states if c.startswith(('blend_','l3_','l5_'))]
    result=targets.copy();new={}
    for side in ('home','away'):
        part=states.rename(columns={'team':side+'_team',**{c:'s8_'+side+'_'+c for c in keep}})
        result=result.merge(part[['game_id',side+'_team']+['s8_'+side+'_'+c for c in keep]],on=['game_id',side+'_team'],validate='one_to_one')
    for c in keep:
        new['s8_diff_'+c]=result['s8_home_'+c]-result['s8_away_'+c]
        if c.startswith('blend_'):
            new['s8_sum_'+c]=result['s8_home_'+c]+result['s8_away_'+c]
    q=qb_stats[qb_stats.game_id.isin(source.game_id)].copy()
    q=q.merge(source[['game_id','week','kickoff_utc']],on='game_id',validate='many_to_one')
    q['kickoff_utc']=[clock.loc[(s,w)] for s,w in zip(q.season,q.week)]
    qstates=F._qb_states(q)
    starters=q.sort_values('qb_dropbacks').groupby(['game_id','team']).tail(1)
    teams=sorted(set(source.home_team)|set(source.away_team));index={t:i for i,t in enumerate(teams)}
    ratings=[];context=[]
    for (season,week),group in targets.groupby(['season','week']):
        decision=group.kickoff_utc.min()
        available=source.completed & source.season.between(season-1,season)
        available &= np.array([clock.loc[(s,w)]<decision for s,w in zip(source.season,source.week)])
        hist=source[available]
        strength={t:np.zeros(4) for t in teams}
        if len(hist)>=16:
            X=np.zeros((len(hist),len(teams)+1))
            X[np.arange(len(hist)),hist.home_team.map(index)]=1
            X[np.arange(len(hist)),hist.away_team.map(index)]=-1
            X[:,-1]=1-hist.neutral_site.to_numpy(float)
            weights=np.where(hist.season.eq(season),1,F.RATING_PREV_WEIGHT)
            before_fit('margin_rating')
            rating=Ridge(alpha=F.RATING_RIDGE).fit(X,hist.margin,sample_weight=weights).coef_
            for t in teams:strength[t][0]=rating[index[t]]
            hl=long[long.game_id.isin(hist.game_id)].dropna(subset=['epa_pp'])
            if len(hl)>=32:
                Z=np.zeros((len(hl),2*len(teams)+1))
                Z[np.arange(len(hl)),hl.team.map(index)]=1
                Z[np.arange(len(hl)),len(teams)+hl.opp.map(index)]=1
                Z[:,-1]=(hl.team.to_numpy()==hl.game_id.map(hist.set_index('game_id').home_team).to_numpy())
                before_fit('offense_defense_EPA_rating')
                coefficient=Ridge(alpha=F.RATING_RIDGE).fit(Z,hl.epa_pp,sample_weight=np.where(hl.season.eq(season),1,F.RATING_PREV_WEIGHT)).coef_
                for t in teams:
                    strength[t][1]=coefficient[index[t]]
                    strength[t][2]=coefficient[len(teams)+index[t]]
                    strength[t][3]=strength[t][1]-strength[t][2]
        prior=starters[starters.kickoff_utc.lt(decision)].sort_values('kickoff_utc').groupby('team').tail(1).set_index('team')
        priorq=qstates[qstates.kickoff_utc.lt(decision)].sort_values('kickoff_utc').groupby('qb_id').tail(1).set_index('qb_id')
        for g in group.itertuples():
            h,a=strength[g.home_team],strength[g.away_team]
            ratings.append({'game_id':g.game_id,**{'s8_rating_diff_'+str(i):h[i]-a[i] for i in range(4)},
                            's8_home_matchup':h[1]+a[2],'s8_away_matchup':a[1]+h[2],
                            's8_rating_history':len(hist),'s8_source_available_max':str(max((clock.loc[(s,w)] for s,w in zip(hist.season,hist.week)),default=pd.NaT))})
            row={'game_id':g.game_id}
            for side in ('home','away'):
                team=getattr(g,side+'_team');qb=prior.loc[team,'qb_id'] if team in prior.index else None
                known=qb in priorq.index if qb is not None else False
                row['s8_'+side+'_qb_eff']=float(priorq.loc[qb,'qb_eff']) if known else F.QB_PRIOR_MEAN
                row['s8_'+side+'_qb_known']=int(known)
                row['s8_'+side+'_qb_log_exp']=np.log1p(float(priorq.loc[qb,'qb_career_db'])) if known else 0
                inj=injury_rows[injury_rows.game_id.eq(g.game_id)&injury_rows.team.eq(team)&injury_rows.available_at.lt(decision)]
                inj=inj.sort_values('available_at').drop_duplicates('gsis_id',keep='last')
                out=inj.report_status.isin(['Out','Doubtful'])
                row['s8_'+side+'_inj_known']=int(len(inj)>0)
                for label,positions in [('qb',['QB']),('skill',['RB','WR','TE']),('ol',['C','G','T','OL'])]:
                    row['s8_'+side+'_inj_out_'+label]=int((out&inj.position.isin(positions)).sum())
            context.append(row)
    result=pd.concat([result,pd.DataFrame(new,index=result.index)],axis=1)
    result=result.merge(pd.DataFrame(ratings),on='game_id',validate='one_to_one').merge(pd.DataFrame(context),on='game_id',validate='one_to_one')
    for c in ('qb_eff','qb_known','qb_log_exp','inj_known','inj_out_qb','inj_out_skill','inj_out_ol'):
        result['s8_diff_'+c]=result['s8_home_'+c]-result['s8_away_'+c]
    columns=[c for c in result if c.startswith('s8_') and c!='s8_source_available_max']
    return result,columns


def reconcile(raw,other,team_total):
    """No target outcomes: explicit remainder participates in proportional scaling."""
    raw=np.maximum(np.asarray(raw,float),0);other=max(float(other),0);total=max(float(team_total),0)
    denominator=raw.sum()+other
    if denominator<=0:return np.zeros_like(raw),total
    return raw*total/denominator,other*total/denominator


def scorer_probabilities(player_lambdas,other_lambda):
    """Distinct-scorer expectation differs from TD-event expectation."""
    return -np.expm1(-np.maximum(player_lambdas,0)),-np.expm1(-max(other_lambda,0))
