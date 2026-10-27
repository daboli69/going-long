"""Learned pregame minutes: P(plays) x minutes-if-plays, from box scores, starters and the official injury report.

Every feature uses only games released before the decision time (first tipoff of the Eastern day minus one
hour; a result is released LAG hours after its tipoff), the same rule as the King of the Court backtest.
Fixed before scoring (docs/KOTC.md, "Learned minutes study").
"""
from collections import defaultdict
import heapq
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier,HistGradientBoostingRegressor
from .config import CACHE,REPORTS,SEED,now
from . import kotc as K

LAG=36;OUT_STATUSES=('Out','Doubtful')
FEATURES=['team_games','m1','m3','m10','started1','starts5','played10','own15','own_n','prev_mpg','days_since',
          'questionable','probable','vacated','team_m10_available','share_m10','rank_m10','back_to_back','rookie']
TRAIN=(2022,2023,2024,2025);TEST=2026


class State:
    """Released team games and player histories, updated one released game at a time."""
    def __init__(self):
        self.team=defaultdict(list);self.played=defaultdict(list);self.last_team={};self.schedule=defaultdict(list)

    def release(self,season,tipoff,team,rows):
        self.team[team].append({'season':season,'tipoff':tipoff,'minutes':{p:m for p,m,_ in rows},'starters':{p for p,_,s in rows if s}})
        for p,m,_ in rows:
            if m>0:self.played[p].append((tipoff,m,season));self.last_team[p]=(team,tipoff)

    def pool(self,team):
        recent={p for g in self.team[team][-82:] for p,m in g['minutes'].items() if m>0}
        return {p for p in recent if self.last_team.get(p,(None,))[0]==team}

    def features(self,p,team,season,tipoff,status,vacated,available_m10):
        current=[g for g in self.team[team] if g['season']==season][-10:]
        minutes=[g['minutes'].get(p,0.) for g in current]
        played=self.played[p];recent=[m for _,m,_ in played[-15:]]
        w=0.5**(np.arange(len(recent))[::-1]/5.) if recent else None
        prev=[m for _,m,s in played if s==season-1]
        m10=float(np.mean(minutes)) if minutes else np.nan
        last_game=max((t for t in self.schedule[team] if t<tipoff),default=None)
        return {'team_games':len(current),'m1':minutes[-1] if minutes else np.nan,'m3':float(np.mean(minutes[-3:])) if minutes else np.nan,
                'm10':m10,'started1':float(p in current[-1]['starters']) if current else np.nan,
                'starts5':float(np.mean([p in g['starters'] for g in current[-5:]])) if current else np.nan,
                'played10':float(np.mean([m>0 for m in minutes])) if minutes else np.nan,
                'own15':float(np.average(recent,weights=w)) if recent else np.nan,'own_n':min(len(played),82),
                'prev_mpg':float(np.mean(prev)) if prev else np.nan,
                'days_since':min((tipoff-played[-1][0]).total_seconds()/86400,365.) if played else 365.,
                'questionable':float(status=='Questionable'),'probable':float(status in ('Probable','Available')),
                'vacated':vacated,'team_m10_available':available_m10,'share_m10':m10/available_m10 if available_m10 and m10==m10 else np.nan,
                'back_to_back':float(last_game is not None and (tipoff-last_game).total_seconds()<36*3600),'rookie':float(not played)}


def rows_for(state,team,season,tipoff,listed):
    """Feature rows for one team in one game. listed: {athlete: status} from that day's official report."""
    pool=state.pool(team)|set(listed)
    current=[g for g in state.team[team] if g['season']==season][-10:]
    m10={p:float(np.mean([g['minutes'].get(p,0.) for g in current])) if current else 0. for p in pool}
    out={p for p,s in listed.items() if s in OUT_STATUSES}
    available=[p for p in pool if p not in out]
    vacated=sum(m10[p] for p in out);total=sum(m10[p] for p in available)
    ranked={p:i+1 for i,p in enumerate(sorted(available,key=lambda p:-m10[p]))}
    rows=[]
    for p in available:
        f=state.features(p,team,season,tipoff,listed.get(p),vacated,total);f['rank_m10']=ranked[p]
        rows.append((p,f))
    return rows,out


def boxes_by_game(boxes):
    out=defaultdict(lambda:defaultdict(list))
    for r in boxes.itertuples(index=False):
        out[str(r.game_id)][str(r.team_id)].append((str(r.athlete_id),float(r.minutes) if r.minutes==r.minutes and not r.did_not_play else 0.,bool(r.starter)))
    return out


def dataset(seasons=(2021,2022,2023,2024,2025,2026)):
    """One row per available pool player per team-game, with the rotation-rule baseline and the actual minutes."""
    games=pd.read_parquet(CACHE/'games.parquet');boxes=pd.read_parquet(CACHE/'player_boxes.parquet')
    reports=pd.read_parquet(CACHE/'injury_reports.parquet').dropna(subset=['game_id','team_id','athlete_id'])
    listed=defaultdict(dict)
    for r in reports.itertuples():listed[(str(r.game_id),str(r.team_id))][str(r.athlete_id)]=r.status
    games=games[games.season.isin(seasons)&games.completed].copy();games['tipoff']=pd.to_datetime(games.tipoff,utc=True)
    games['day']=games.tipoff.dt.tz_convert('America/New_York').dt.date
    box=boxes_by_game(boxes[boxes.season.isin(seasons)]);state=State();queue=[];rows=[]
    for day,today in games.sort_values('tipoff').groupby('day',sort=True):
        decision=today.tipoff.min()-pd.Timedelta(hours=1)
        while queue and queue[0][0]<decision:
            _,gid,season,tip,team=heapq.heappop(queue);state.release(season,tip,team,box[gid][team])
        for g in today.itertuples():
            for team in (str(g.home_id),str(g.away_id)):
                if not box[str(g.game_id)][team]:continue
                status=listed.get((str(g.game_id),team),{})
                built,_=rows_for(state,team,g.season,g.tipoff,status)
                actual={p:m for p,m,_ in box[str(g.game_id)][team]}
                history={'own':{p:[m for _,m,_ in state.played[p]] for p,_ in built},
                         'team':{team:[x['minutes'] for x in state.team[team] if x['season']==g.season]}}
                for p,f in built:
                    rule=K.expected_minutes(p,team,history,decision.isoformat())
                    rows.append({'game_id':str(g.game_id),'season':g.season,'day':str(day),'team':team,'athlete_id':p,**f,
                                 'rotation_minutes':rule['mean'] if rule else np.nan,'actual':actual.get(p,0.)})
        for g in today.itertuples():
            for team in (str(g.home_id),str(g.away_id)):
                state.schedule[team].append(g.tipoff)
                if box[str(g.game_id)][team]:heapq.heappush(queue,(g.tipoff+pd.Timedelta(hours=LAG),str(g.game_id),g.season,g.tipoff,team))
    return pd.DataFrame(rows)


def fit(train):
    x=train[FEATURES].to_numpy(float);played=train.actual.gt(0).to_numpy()
    classifier=HistGradientBoostingClassifier(max_iter=300,learning_rate=.05,max_leaf_nodes=31,l2_regularization=1.,random_state=SEED).fit(x,played)
    regressor=HistGradientBoostingRegressor(max_iter=300,learning_rate=.05,max_leaf_nodes=31,l2_regularization=1.,random_state=SEED).fit(x[played],train.actual[played])
    return classifier,regressor


def predict(model,frame,residual_sd):
    classifier,regressor=model;x=frame[FEATURES].to_numpy(float)
    p=classifier.predict_proba(x)[:,1];m=np.clip(regressor.predict(x),1.,48.)
    s=np.interp(m,residual_sd['minutes'],residual_sd['sd'])
    expected=p*m;sd=np.sqrt(np.maximum(p*(s**2+m**2)-expected**2,0.))
    return pd.DataFrame({'p_play':p,'minutes_if_play':m,'expected':expected,'sd':sd},index=frame.index)


def residual_profile(model,frame):
    """Residual SD of minutes-if-plays by predicted level, from games the model did not train on."""
    played=frame[frame.actual.gt(0)];m=np.clip(model[1].predict(played[FEATURES].to_numpy(float)),1.,48.)
    bins=pd.qcut(m,8,duplicates='drop');resid=played.actual.to_numpy()-m
    table=pd.DataFrame({'m':m,'r':resid,'b':bins}).groupby('b',observed=True).agg(minutes=('m','mean'),sd=('r','std'))
    return {'minutes':table.minutes.tolist(),'sd':table.sd.clip(lower=2.).tolist()}


def study():
    """Train 2022-2024 -> residual SD on 2025; train 2022-2025 -> score 2026. Saves predictions for the KOTC backtest."""
    out=REPORTS/'minutes_v1';out.mkdir(parents=True,exist_ok=True)
    data=dataset();data.to_parquet(out/'dataset.parquet',index=False)
    early=fit(data[data.season.isin(TRAIN[:-1])]);residual=residual_profile(early,data[data.season.eq(TRAIN[-1])])
    model=fit(data[data.season.isin(TRAIN)]);test=data[data.season.eq(TEST)].copy()
    test=test.join(predict(model,test,residual))
    test.to_parquet(out/'predictions_2026.parquet',index=False)
    both=test.dropna(subset=['rotation_minutes'])
    bands=pd.cut(both.actual,[-1,.5,15,25,32,60],labels=['did not play','<15','15-25','25-32','32+'])
    by_band=both.groupby(bands,observed=True).apply(lambda x:pd.Series({'n':len(x),'learned_bias':(x.expected-x.actual).mean(),
              'rotation_bias':(x.rotation_minutes-x.actual).mean()}),include_groups=False)
    summary={'created_at':now(),'train':list(TRAIN),'test':TEST,'rows':len(test),'rows_with_rotation_rule':len(both),
             'learned_mae':float((both.expected-both.actual).abs().mean()),'rotation_mae':float((both.rotation_minutes-both.actual).abs().mean()),
             'learned_mae_all_rows':float((test.expected-test.actual).abs().mean()),
             'played_brier':float(((test.p_play-test.actual.gt(0))**2).mean()),'residual_sd':residual,
             'by_actual_band':{str(k):v for k,v in by_band.round(2).to_dict('index').items()}}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=1,default=float),encoding='utf-8')
    return summary
