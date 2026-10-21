"""New coherent output only: opportunities -> shares -> efficiency -> remainder."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, PoissonRegressor

from .core import predict_model
from .features import reconcile,scorer_probabilities


def team_frame(games, observations, columns):
    records=[]
    for side in ('home','away'):
        d=games[['game_id','season','week','kickoff_utc']+columns].copy()
        d['team']=games[side+'_team'].to_numpy();d['is_home']=int(side=='home')
        for c in columns:
            if c.startswith('s8_diff_') or 'rating_diff_' in c:d[c]=d[c]*(1 if side=='home' else -1)
            counterpart=c.replace('_home_','_away_')
            if side=='away' and '_home_' in c and counterpart in games:d[c]=games[counterpart].to_numpy()
            counterpart=c.replace('_away_','_home_')
            if side=='away' and '_away_' in c and counterpart in games:d[c]=games[counterpart].to_numpy()
        records.append(d)
    result=pd.concat(records,ignore_index=True)
    obs=observations.copy()
    if 'team' not in obs:obs=obs.rename(columns={'posteam':'team'})
    obs=obs.drop_duplicates(['game_id','team','pid'])
    totals=obs.groupby(['game_id','team'])[['targets','carries','dropbacks','pass_yds','pass_tds','rec','rec_yds','rush_yds','off_td']].sum().add_prefix('actual_team_').reset_index()
    distinct=obs.assign(distinct=obs.off_td.gt(0).astype(float)).groupby(['game_id','team']).distinct.sum().rename('actual_team_distinct_scorers').reset_index()
    totals=totals.merge(distinct,on=['game_id','team'],validate='one_to_one')
    result=result.merge(totals,on=['game_id','team'],how='left',validate='one_to_one')
    return result,obs


def predict(train,target,team_train,team_target,stat,player_cols,team_cols,weights,team_weights,before_fit):
    usage={'pass_yds':'dropbacks','pass_tds':'dropbacks','rec':'targets','rec_yds':'targets','rush_yds':'carries','anytime_td':'opportunities'}[stat]
    train=train.copy();target=target.copy()
    for d in (train,team_train,team_target):
        if 'actual_opportunities' not in d and 'actual_targets' in d:d['actual_opportunities']=d.actual_targets+d.actual_carries
        if 'actual_team_opportunities' not in d and 'actual_team_targets' in d:d['actual_team_opportunities']=d.actual_team_targets+d.actual_team_carries
    outcome='off_td' if stat=='anytime_td' else 'pass_yds' if stat=='rec_yds' else stat
    # Both passing and receiving reconcile to the same independently fitted team passing-yard total.
    team_y=team_train['actual_team_'+outcome].clip(lower=0).to_numpy(float)
    team_u=team_train['actual_team_'+usage].clip(lower=0).to_numpy(float)
    Xcols=team_cols+['is_home']

    def fit(name,model,rows,targets,cols,y,w,binary=False):
        before_fit(name)
        if len(np.unique(y))<2:return np.full(len(targets),float(np.mean(y))),None
        return predict_model(model,rows,targets,cols,y,w,binary)

    u_pred,_=fit('team_usage',PoissonRegressor(alpha=1,max_iter=500),team_train,team_target,Xcols,team_u,team_weights)
    u_pred=np.maximum(u_pred,0)
    if stat in ('pass_yds','rec_yds','rush_yds'):
        yard_usage=team_u;yard_u_pred=u_pred
        if stat=='rec_yds':
            yard_usage=team_train.actual_team_dropbacks.clip(lower=0).to_numpy(float)
            yard_u_pred,_=fit('shared_team_passing_opportunities',PoissonRegressor(alpha=1,max_iter=500),team_train,team_target,Xcols,yard_usage,team_weights)
        good=yard_usage>0
        rate,_=fit('team_efficiency',Ridge(alpha=100),team_train[good],team_target,Xcols,team_y[good]/yard_usage[good],team_weights[good])
        totals=np.maximum(yard_u_pred,0)*np.maximum(rate,0)
    else:
        totals,_=fit('team_count',PoissonRegressor(alpha=1,max_iter=500),team_train,team_target,Xcols,team_y,team_weights)
        totals=np.maximum(totals,0)
    denominator=train['actual_team_'+usage].clip(lower=1).to_numpy(float)
    usage_y=train['actual_'+usage].clip(lower=0).to_numpy(float)
    share=np.clip(usage_y/denominator,0,1)
    share_pred,_=fit('player_usage_share',Ridge(alpha=100),train,target,player_cols,share,weights)
    share_pred=np.clip(share_pred,0,1)
    y=train['actual_off_td' if stat=='anytime_td' else stat].clip(lower=0).to_numpy(float)
    good=usage_y>0
    rate,_=fit('player_efficiency',Ridge(alpha=100),train[good],target,player_cols,y[good]/usage_y[good],weights[good])
    rate=np.maximum(rate,0)
    if stat=='rec':rate=np.minimum(rate,1)
    # Earlier eligible cohorts determine other-player usage mass, never target eligibility/outcomes.
    used=train.groupby(['game_id','team'])['actual_'+usage].sum()
    team_den=team_train.set_index(['game_id','team'])['actual_team_'+usage].clip(lower=1)
    other_share=float((1-used.reindex(team_den.index,fill_value=0)/team_den).clip(0,1).mean())
    other_share=max(other_share,0)
    other_distinct_ratio=1.
    if stat=='anytime_td' and 'actual_team_distinct_scorers' in team_train:
        index=team_train.set_index(['game_id','team'])
        eligible_events=train.groupby(['game_id','team']).actual_off_td.sum()
        eligible_scorers=train.assign(scorer=train.actual_off_td.gt(0).astype(float)).groupby(['game_id','team']).scorer.sum()
        other_events=(index.actual_team_off_td-eligible_events.reindex(index.index,fill_value=0)).clip(lower=0).sum()
        other_scorers=(index.actual_team_distinct_scorers-eligible_scorers.reindex(index.index,fill_value=0)).clip(lower=0).sum()
        other_distinct_ratio=float(np.clip(other_scorers/max(other_events,1e-9),0,1)) if other_events else 1.
    prediction=np.zeros(len(target));raw_values=np.zeros(len(target));diagnostics=[]
    indices=target.reset_index(drop=True).groupby(['game_id','team']).indices
    team_lookup=team_target.reset_index(drop=True).set_index(['game_id','team'])
    for key,ix in indices.items():
        t=team_lookup.index.get_loc(key)
        raw=u_pred[t]*share_pred[ix]*rate[ix];raw_values[ix]=raw
        total=totals[t]
        team_rate=total/max(u_pred[t],1e-9)
        other=u_pred[t]*other_share*team_rate
        scaled,remainder=reconcile(raw,other,total)
        if stat=='anytime_td':
            probabilities,p_other=scorer_probabilities(scaled,remainder)
            prediction[ix]=probabilities
            other_distinct=float(np.clip(remainder*other_distinct_ratio,p_other,remainder))
            distinct=float(probabilities.sum()+other_distinct)
        else:
            prediction[ix]=scaled;distinct=None
        diagnostics.append({'game_id':key[0],'team':key[1],'stat':stat,'team_projection':float(total),
                            'team_opportunities':float(u_pred[t]),'player_sum':float(scaled.sum()),'other_players':float(remainder),
                            'coherence_error':float(scaled.sum()+remainder-total),'expected_distinct_scorers_approx':distinct,
                            'other_expected_distinct_scorers_approx':other_distinct if stat=='anytime_td' else None,
                            'distinct_scorer_method':'known Poisson scorer probabilities + earlier other-scorer/TD ratio approximation' if stat=='anytime_td' else None,
                            'anytime_probability_sum':float(prediction[ix].sum()) if stat=='anytime_td' else None,
                            'other_anytime_probability':float(p_other) if stat=='anytime_td' else None})
    return prediction,raw_values,pd.DataFrame(diagnostics)
