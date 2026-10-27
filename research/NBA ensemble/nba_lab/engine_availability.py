"""Engine stage 1: P(plays) for every pool player, from every official injury-report version before the decision.

Decision: first tipoff of the Eastern day minus one hour. A game's result is usable 12 hours after its tipoff.
Plan: docs/ENGINE_PLAN.md (stage 1) and docs/ENGINE_STAGE1.md.
"""
from collections import defaultdict
import bisect
import heapq
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from .config import CACHE,REPORTS,SEED,now
from .minutes_model import State,boxes_by_game

LAG=12;OUT=REPORTS/'engine_stage1'
STATUSES=('Out','Doubtful','Questionable','Probable','Available')
CATEGORIES=('not_listed','not_yet_submitted')+STATUSES
REASONS=('injury','g_league','rest','personal','protocol','suspension','other')
TESTS={2024:(2022,2023),2025:(2022,2023,2024),2026:(2022,2023,2024,2025)}


def reason_kind(text):
    t=str(text or '').lower()
    if t.startswith('g league') or 'two-way' in t:return 'g_league'
    if t.startswith('injury') or 'illness' in t or 'reconditioning' in t:return 'injury'
    if t.startswith('rest'):return 'rest'
    if 'personal' in t or 'not with team' in t:return 'personal'
    if 'protocol' in t:return 'protocol'
    if 'suspension' in t or 'ineligible' in t:return 'suspension'
    return 'other'


def version_index(versions):
    """(game, team) -> sorted publish times with per-player status; plus each team's not-submitted flags."""
    v=versions.dropna(subset=['game_id','team_id']).copy();v['published_at']=pd.to_datetime(v.published_at,utc=True)
    index=defaultdict(dict)
    for (gid,team,url),rows in v.groupby(['game_id','team_id','report_url'],sort=False):
        stamp=rows.published_at.iloc[0]
        entry={'nys':bool(rows.not_yet_submitted.any()),
               'players':{str(r.athlete_id):(r.status,reason_kind(r.reason)) for r in rows.itertuples() if r.athlete_id and not r.not_yet_submitted}}
        index[(str(gid),str(team))][stamp]=entry
    return {k:sorted(d.items()) for k,d in index.items()}


def at_decision(entries,decision):
    """Versions published strictly before the decision, oldest first."""
    stamps=[t for t,_ in entries];i=bisect.bisect_left(stamps,decision)
    return entries[:i]


def dataset(seasons=(2022,2023,2024,2025,2026)):
    games=pd.read_parquet(CACHE/'games.parquet');boxes=pd.read_parquet(CACHE/'player_boxes.parquet')
    versions=version_index(pd.read_parquet(CACHE/'injury_report_versions.parquet'))
    games=games[games.season.isin(seasons)&games.completed].copy();games['tipoff']=pd.to_datetime(games.tipoff,utc=True)
    games['day']=games.tipoff.dt.tz_convert('America/New_York').dt.date
    box=boxes_by_game(boxes[boxes.season.isin(seasons)]);state=State();queue=[];rows=[]
    out_history=defaultdict(list)  # (team, player) -> statuses in the team's earlier games (latest pre-decision version)
    for day,today in games.sort_values('tipoff').groupby('day',sort=True):
        decision=today.tipoff.min()-pd.Timedelta(hours=1)
        while queue and queue[0][0]<decision:
            _,gid,season,tip,team=heapq.heappop(queue);state.release(season,tip,team,box[gid][team])
        for g in today.itertuples():
            for team in (str(g.home_id),str(g.away_id)):
                if not box[str(g.game_id)][team]:continue
                seen=at_decision(versions.get((str(g.game_id),team),[]),decision)
                latest=seen[-1][1] if seen else None
                listed=set().union(*(e['players'] for _,e in seen)) if seen else set()
                pool=state.pool(team)|listed
                played={p for p,m,_ in box[str(g.game_id)][team] if m>0}
                current=[x for x in state.team[team] if x['season']==g.season]
                for p in pool:
                    status,reason=(latest['players'].get(p,('not_listed',None)) if latest else ('not_listed',None))
                    if latest and latest['nys'] and status=='not_listed':status='not_yet_submitted'
                    history=[e['players'][p][0] for _,e in seen if p in e['players']]
                    previous=out_history[(team,p)][-5:]
                    minutes=[x['minutes'].get(p,0.) for x in current[-10:]]
                    streak=0
                    for x in reversed(current):
                        if x['minutes'].get(p,0.)>0:break
                        streak+=1
                    last=state.played[p][-1][0] if state.played[p] else None
                    last_game=max((t for t in state.schedule[team] if t<g.tipoff),default=None)
                    rows.append({'game_id':str(g.game_id),'season':g.season,'day':str(day),'team':team,'athlete_id':p,
                        'status':status,'reason':reason or 'none','first_status':history[0] if history else 'not_listed',
                        'status_changes':sum(a!=b for a,b in zip(history,history[1:])),'versions_seen':len(seen),
                        'listed_out_prev1':float(bool(previous) and previous[-1] in ('Out','Doubtful')),
                        'listed_out_prev5':float(sum(s in ('Out','Doubtful') for s in previous)),
                        'missed_streak':float(min(streak,82)),'played10':float(np.mean([m>0 for m in minutes])) if minutes else np.nan,
                        'm10':float(np.mean(minutes)) if minutes else np.nan,
                        'started_last':float(p in current[-1]['starters']) if current else np.nan,
                        'days_since_played':min((g.tipoff-last).total_seconds()/86400,365.) if last is not None else 365.,
                        'own_n':float(min(len(state.played[p]),82)),'team_games':float(len(current)),
                        'back_to_back':float(last_game is not None and (g.tipoff-last_game).total_seconds()<36*3600),
                        'played':float(p in played)})
                    out_history[(team,p)].append(status)
        for g in today.itertuples():
            for team in (str(g.home_id),str(g.away_id)):
                state.schedule[team].append(g.tipoff)
                if box[str(g.game_id)][team]:heapq.heappush(queue,(g.tipoff+pd.Timedelta(hours=LAG),str(g.game_id),g.season,g.tipoff,team))
    return pd.DataFrame(rows)


def matrix(frame):
    x=frame[['status_changes','versions_seen','listed_out_prev1','listed_out_prev5','missed_streak','played10','m10',
             'started_last','days_since_played','own_n','team_games','back_to_back']].copy()
    for c in CATEGORIES:x['status_'+c]=frame.status.eq(c).astype(float);x['first_'+c]=frame.first_status.eq(c).astype(float)
    for r in REASONS:x['reason_'+r]=frame.reason.eq(r).astype(float)
    return x.to_numpy(float)


def baseline(train,test):
    """Status-only lookup: each status category's play rate in the training seasons."""
    rates=train.groupby('status').played.mean();overall=train.played.mean()
    return test.status.map(rates).fillna(overall).clip(1e-4,1-1e-4).to_numpy()


def model(train,test):
    clf=HistGradientBoostingClassifier(max_iter=300,learning_rate=.05,max_leaf_nodes=31,l2_regularization=1.,random_state=SEED)
    clf.fit(matrix(train),train.played.astype(int))
    return np.clip(clf.predict_proba(matrix(test))[:,1],1e-4,1-1e-4)


def losses(y,p):
    return -(y*np.log(p)+(1-y)*np.log(1-p)),(p-y)**2


def score():
    OUT.mkdir(parents=True,exist_ok=True)
    data=dataset();data.to_parquet(OUT/'dataset.parquet',index=False)
    parts=[]
    for test_season,train_seasons in TESTS.items():
        train=data[data.season.isin(train_seasons)];test=data[data.season.eq(test_season)].copy()
        test['p_baseline']=baseline(train,test);test['p_model']=model(train,test);parts.append(test)
    scored=pd.concat(parts);scored.to_parquet(OUT/'predictions.parquet',index=False)
    y=scored.played.to_numpy()
    scored['ll_base'],scored['brier_base']=losses(y,scored.p_baseline.to_numpy())
    scored['ll_model'],scored['brier_model']=losses(y,scored.p_model.to_numpy())
    nightly=scored.groupby('day')[['ll_base','ll_model','brier_base','brier_model']].sum().join(scored.groupby('day').size().rename('n'))
    rng=np.random.default_rng(20261027);days=nightly.index.to_numpy();boot=[]
    for _ in range(2000):
        pick=nightly.loc[rng.choice(days,len(days))]
        boot.append((pick.ll_model.sum()-pick.ll_base.sum())/pick.n.sum())
    by_season={int(s):{'n':len(x),'ll_base':float(x.ll_base.mean()),'ll_model':float(x.ll_model.mean()),
                       'brier_base':float(x.brier_base.mean()),'brier_model':float(x.brier_model.mean())} for s,x in scored.groupby('season')}
    by_status={s:{'n':len(x),'play_rate':float(x.played.mean()),'ll_base':float(x.ll_base.mean()),'ll_model':float(x.ll_model.mean())}
               for s,x in scored.groupby('status')}
    delta=float(scored.ll_model.mean()-scored.ll_base.mean())
    brier_change=float(scored.brier_model.mean()/scored.brier_base.mean()-1)
    seasons_better=sum(v['ll_model']<v['ll_base'] for v in by_season.values())
    ci=[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))]
    result={'created_at':now(),'rows':len(scored),'nights':len(days),'log_loss_base':float(scored.ll_base.mean()),
            'log_loss_model':float(scored.ll_model.mean()),'delta':delta,'ci95':ci,'seasons_better':seasons_better,
            'brier_base':float(scored.brier_base.mean()),'brier_model':float(scored.brier_model.mean()),'brier_relative_change':brier_change,
            'passed':bool(ci[1]<0 and seasons_better>=2 and brier_change<=.01),'by_season':by_season,'by_status':by_status}
    (OUT/'RESULTS.json').write_text(json.dumps(result,indent=1),encoding='utf-8')
    return result
