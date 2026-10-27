"""Instrumented v1 simulator, with ONLY explicit team-attempt-pool hooks.

The source-equivalence test strips these hooks and requires the original AST.
With no override, all v1 sample arrays must match exactly for the same seed.
FTA override is an oracle diagnostic only; the repair uses the FGA hook alone.
"""
import math
import numpy as np
from scripts.king_court.simulation import allocate, capped_minutes, _beta, _logit, _shift


def simulate(slate, profiles, teams, overtime, draws=20000, seed=271026, field_goal_pools=None, free_throw_pools=None):
    if draws < 100:
        raise ValueError('At least 100 simulation draws required')
    rng = np.random.default_rng(seed)
    ids = [p['player_id'] for p in profiles]
    count = len(profiles)
    points = np.zeros((draws,count),dtype=np.int64)
    rebounds = np.zeros_like(points)
    assists = np.zeros_like(points)
    minutes = np.zeros((draws,count))
    diagnostics = []
    measured_pools = {}
    for game in slate['games']:
        home, away = game['home'], game['away']
        th, ta = teams[home], teams[away]
        lengths = 48 + 5*rng.choice(list(overtime),size=draws,p=list(overtime.values()))
        pace_mean = .5*(th['pace48']+ta['pace48'])
        pace_sd = .5*(th['pace_sd']+ta['pace_sd'])
        log_sd = math.sqrt(math.log1p((pace_sd/max(1,pace_mean))**2))
        possessions = rng.lognormal(math.log(pace_mean)-.5*log_sd**2,log_sd,size=draws)*lengths/48
        fga_override = field_goal_pools(game, possessions) if callable(field_goal_pools) else (field_goal_pools or {}).get(game['game_id'], {})
        fta_override = (free_throw_pools or {}).get(game['game_id'], {})
        game_results = {}
        for code, opp in ((home,away),(away,home)):
            indexes = [i for i,p in enumerate(profiles) if p['team']==code and p['game_id']==game['game_id']]
            selected = [profiles[i] for i in indexes]
            if len(indexes) < 5:
                raise ValueError('Incomplete team field')
            # Lognormal minutes preserve active positive exposure; OUT is exactly zero.
            raw = np.zeros((draws,len(indexes)))
            for j,p in enumerate(selected):
                if p['availability']=='out' or p['minutes_mean']<=0:
                    continue
                sd=math.sqrt(math.log1p((p['minutes_sd']/p['minutes_mean'])**2))
                raw[:,j]=rng.lognormal(math.log(p['minutes_mean'])-.5*sd**2,sd,size=draws)
            m=capped_minutes(raw,lengths)
            minutes[:,indexes]=m
            own, defense=teams[code],teams[opp]
            fga_total=rng.poisson(possessions*math.sqrt(own['fga_poss']*defense['allowed_fga_poss']))
            fta_total=rng.poisson(possessions*math.sqrt(own['fta_poss']*defense['allowed_fta_poss']))
            if code in fga_override:
                fga_total=np.asarray(fga_override[code],dtype=np.int64)
            if code in fta_override:
                fta_total=np.asarray(fta_override[code],dtype=np.int64)
            measured_pools[(game['game_id'],code)]={'fga':fga_total,'fta':fta_total,'possessions':possessions}
            opportunity={}
            for kind in ('fga','fta','oreb','dreb','ast'):
                weights=[]
                for j,p in enumerate(selected):
                    mean=p['rates'][kind]
                    if kind in ('fga','fta') and mean>0:
                        exposure=max(1,p['exposures'][kind])
                        rates=rng.gamma(exposure,mean/exposure,size=draws)
                    else:
                        rates=np.full(draws,mean)
                    weights.append(m[:,j]*rates)
                opportunity[kind]=np.array(weights).T
                zero=opportunity[kind].sum(axis=1)<=0
                opportunity[kind][zero]=m[zero]
            fga=allocate(fga_total,opportunity['fga'],rng)
            fta=allocate(fta_total,opportunity['fta'],rng)
            made=np.zeros_like(fga)
            scored=np.zeros_like(fga)
            ft_made_total=np.zeros(draws,dtype=np.int64)
            for j,p in enumerate(selected):
                probs, exposure=p['probabilities'],p['exposures']
                share=_beta(probs['three_share'],exposure['three_share'],draws,rng)
                threes=rng.binomial(fga[:,j],share)
                twos=fga[:,j]-threes
                p2=_shift(_beta(probs['p2'],exposure['p2'],draws,rng), .5*(_logit(defense['allowed_p2'])-_logit(own['p2'])))
                p3=_shift(_beta(probs['p3'],exposure['p3'],draws,rng), .5*(_logit(defense['allowed_p3'])-_logit(own['p3'])))
                pft=_shift(_beta(probs['pft'],exposure['pft'],draws,rng), .5*(_logit(defense['allowed_pft'])-_logit(own['pft'])))
                m2,m3,mft=rng.binomial(twos,p2),rng.binomial(threes,p3),rng.binomial(fta[:,j],pft)
                made[:,j]=m2+m3
                scored[:,j]=2*m2+3*m3+mft
                ft_made_total+=mft
                points[:,indexes[j]]=scored[:,j]
            game_results[code]=dict(indexes=indexes,made=made,scored=scored,
                                    fga_total=fga_total,fta_total=fta_total,
                                    opportunity=opportunity,minutes=m,
                                    fg_misses=fga.sum(axis=1)-made.sum(axis=1))
            game_results[code]['ft_misses']=fta.sum(axis=1)-ft_made_total
        for code,opp in ((home,away),(away,home)):
            own,other=game_results[code],game_results[opp]
            pool=own['fg_misses']+own['ft_misses']
            p_or,p_dr=teams[code]['oreb_miss'],teams[opp]['dreb_oppmiss']
            normalization=max(1.,p_or+p_dr)
            capture=allocate(pool,np.array([p_or/normalization,p_dr/normalization,max(0,1-(p_or+p_dr)/normalization)]),rng)
            offensive=allocate(capture[:,0],own['opportunity']['oreb'],rng)
            defensive=allocate(capture[:,1],other['opportunity']['dreb'],rng)
            rebounds[:,own['indexes']]+=offensive
            rebounds[:,other['indexes']]+=defensive
        for code,opp in ((home,away),(away,home)):
            own=game_results[code]
            q=float(_shift(teams[code]['ast_fgm'],.5*(_logit(teams[opp]['allowed_ast_fgm'])-_logit(teams[code]['ast_fgm']))))
            total_assists=np.zeros(draws,dtype=int)
            for shooter in range(len(own['indexes'])):
                pool=rng.binomial(own['made'][:,shooter],q)
                weights=own['opportunity']['ast'].copy()
                weights[:,shooter]=0
                zero=weights.sum(axis=1)<=0
                fallback=own['minutes'].copy()
                fallback[:,shooter]=0
                weights[zero]=fallback[zero]
                allocated=allocate(pool,weights,rng)
                if np.any(allocated[:,shooter]):
                    raise AssertionError('Self-assist')
                assists[:,own['indexes']]+=allocated
                total_assists+=pool
            if np.any(total_assists>own['made'].sum(axis=1)):
                raise AssertionError('More assists than made baskets')
        game_indexes=game_results[home]['indexes']+game_results[away]['indexes']
        miss_total=sum(game_results[c]['fg_misses']+game_results[c]['ft_misses'] for c in (home,away))
        if np.any(rebounds[:,game_indexes].sum(axis=1)>miss_total):
            raise AssertionError('More player rebounds than missed-shot pool')
        diagnostics.append(dict(game_id=game['game_id'],shared_pace_mean=float(possessions.mean()),
                                overtime_probability=float(np.mean(lengths>48)),
                                minutes_conservation_max_error=float(max(abs(minutes[:,game_results[c]['indexes']].sum(axis=1)-5*lengths).max() for c in (home,away))),
                                rebound_pool_conservation=True,self_assists_excluded=True,
                                rebound_pool='missed_FG_and_FT_proxy_with_empirical_uncredited_fraction',
                                context={home:th,away:ta}))
    return dict(player_ids=ids,points=points,rebounds=rebounds,assists=assists,minutes=minutes,
                pra=points+rebounds+assists,diagnostics=diagnostics,measured_pools=measured_pools)
