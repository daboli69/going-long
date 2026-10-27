"""Integer, correlated game pools; complete-field leader and customer tie math."""
import math
import numpy as np


def allocate(total, weights, rng):
    """Vectorized multinomials; zero-weight players receive no opportunity."""
    total = np.asarray(total, dtype=np.int64)
    weights = np.maximum(0, np.asarray(weights, dtype=float))
    if weights.ndim == 1:
        weights = np.broadcast_to(weights, (len(total), len(weights)))
    sums = weights.sum(axis=1)
    if np.any((total > 0) & (sums <= 0)):
        raise ValueError('Positive opportunity pool has no eligible recipient')
    result = np.zeros(weights.shape, dtype=np.int64)
    left, remaining = total.copy(), sums.copy()
    for j in range(weights.shape[1]):
        probability = np.divide(weights[:,j], remaining, out=np.zeros(len(total)), where=remaining > 1e-12)
        draw = rng.binomial(left, np.clip(probability, 0, 1))
        result[:,j] = draw
        left -= draw
        remaining = np.maximum(0, remaining - weights[:,j])
    if np.any(left):
        raise ValueError('Allocation lost integer opportunities')
    return result


def capped_minutes(draws, game_length):
    """Each team gets five players of time, each individual <= game length."""
    values = np.maximum(0, np.array(draws,dtype=float))
    cap = np.asarray(game_length,dtype=float)
    target = cap * 5
    for _ in range(values.shape[1] + 1):
        over = values >= cap[:,None] - 1e-10
        fixed = (over * cap[:,None]).sum(axis=1)
        free = np.where(over,0,values)
        needed = np.maximum(0,target - fixed)
        sums = free.sum(axis=1)
        if np.any((needed > 1e-7) & (sums <= 0)):
            raise ValueError('Rotation cannot fill five-player game time')
        scaled = free * np.divide(needed,sums,out=np.zeros(len(cap)),where=sums>0)[:,None]
        values = np.where(over,cap[:,None],np.minimum(scaled,cap[:,None]))
        if np.allclose(values.sum(axis=1), target, atol=1e-7):
            return values
    raise ValueError('Minutes projection did not converge')


def _logit(p):
    p = np.clip(p,.001,.999)
    return np.log(p/(1-p))


def _shift(p, offset):
    return 1/(1+np.exp(-(_logit(p)+offset)))


def _beta(mean, exposure, n, rng):
    # Two weak pseudo-trials prevent degenerate 0/1 shooting on tiny samples.
    # This numerical prior is disclosed and is not claimed as a fitted effect.
    return rng.beta(mean*exposure+1,(1-mean)*exposure+1,size=n)


def simulate(slate, profiles, teams, overtime, draws=20000, seed=271026):
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
    for game in slate['games']:
        home, away = game['home'], game['away']
        th, ta = teams[home], teams[away]
        lengths = 48 + 5*rng.choice(list(overtime),size=draws,p=list(overtime.values()))
        pace_mean = .5*(th['pace48']+ta['pace48'])
        pace_sd = .5*(th['pace_sd']+ta['pace_sd'])
        log_sd = math.sqrt(math.log1p((pace_sd/max(1,pace_mean))**2))
        possessions = rng.lognormal(math.log(pace_mean)-.5*log_sd**2,log_sd,size=draws)*lengths/48
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
                pra=points+rebounds+assists,diagnostics=diagnostics)


def leader_summary(pra):
    pra=np.asarray(pra)
    if pra.ndim!=2 or not len(pra) or pra.shape[1]==0 or not np.issubdtype(pra.dtype,np.integer):
        raise ValueError('Integer complete-field PRA simulations required')
    leaders=pra==pra.max(axis=1,keepdims=True)
    counts=leaders.sum(axis=1)
    result=[]
    for j in range(pra.shape[1]):
        sole=leaders[:,j]&(counts==1)
        tied=leaders[:,j]&(counts>1)
        inclusive=leaders[:,j]
        entry=dict(sole_leader_probability=float(sole.mean()),tied_leader_probability=float(tied.mean()),
                   inclusive_leader_probability=float(inclusive.mean()),fractional_leader_credit=float((inclusive/counts).mean()))
        entry['monte_carlo_se']={name:math.sqrt(entry[name]*(1-entry[name])/len(pra)) for name in ('sole_leader_probability','tied_leader_probability','inclusive_leader_probability')}
        result.append(entry)
    return result,leaders


def prize_scenario(leaders,player_ids,scenario,pool=1000000,seed=271027,selectable=None):
    """N is OTHER valid customers; one separate hypothetical entry per candidate."""
    if scenario.get('kind') not in ('hypothetical','measured_counts'):
        raise ValueError('Explicit ownership scenario kind required')
    rng=np.random.default_rng(seed)
    if scenario['kind']=='measured_counts':
        if scenario.get('source_scope')!='promotion_qualifying_selections' or not scenario.get('source') or not scenario.get('known_at'):
            raise ValueError('Promo-specific count provenance required')
        counts=scenario['counts']
        if set(counts)!=set(player_ids) or any(type(v)is not int or v<0 for v in counts.values()):
            raise ValueError('Complete valid other-customer counts required')
        entrants=np.broadcast_to([counts[p] for p in player_ids],leaders.shape)
        ownership={p:counts[p]/sum(counts.values()) if sum(counts.values()) else None for p in player_ids}
    else:
        q=scenario['ownership']
        n=scenario['other_entrants']
        if set(q)!=set(player_ids) or type(n)is not int or n<0 or any(not math.isfinite(v) or v<0 for v in q.values()) or not math.isclose(sum(q.values()),1,abs_tol=1e-9):
            raise ValueError('Complete ownership vector summing to one and nonnegative entrant count required')
        entrants=rng.multinomial(n,[q[p] for p in player_ids],size=len(leaders))
        ownership=q
    denominators=1+(entrants*leaders).sum(axis=1)
    payouts=pool*leaders/denominators[:,None]
    result=[]
    for j,pid in enumerate(player_ids):
        winning=payouts[leaders[:,j],j]
        allowed=selectable is None or selectable[j]
        result.append(dict(player_id=pid,ownership_fraction=ownership[pid],ownership_kind=scenario['kind'],
                           expected_bonus_bet_face_value=float(payouts[:,j].mean()) if allowed else None,
                           bonus_bet_face_value_when_leader=float(winning.mean()) if len(winning) and allowed else None,
                           monte_carlo_se=float(payouts[:,j].std(ddof=1)/math.sqrt(len(payouts))) if allowed else None,
                           conditional_on='Supplied crowd scenario, one valid qualifying entry, and screenshot prize-split interpretation. Not cash EV.'))
    return dict(name=scenario['name'],kind=scenario['kind'],results=result)


def summarize(simulation,profiles,scenarios=None,pool=1000000):
    leaders,mask=leader_summary(simulation['pra'])
    rows=[]
    for j,p in enumerate(profiles):
        pra=simulation['pra'][:,j]
        row=dict(p,expected_pra=float(pra.mean()),pra_quantiles=dict(zip(('p10','p50','p90'),np.quantile(pra,[.1,.5,.9]).tolist())),
                 expected_minutes=float(simulation['minutes'][:,j].mean()),minutes_10_90=np.quantile(simulation['minutes'][:,j],[.1,.9]).tolist(),
                 expected_components={k:float(simulation[k][:,j].mean()) for k in ('points','rebounds','assists')},
                 pra_mean_monte_carlo_se=float(pra.std(ddof=1)/math.sqrt(len(pra))),
                 observed_ownership_fraction=None,**leaders[j])
        rows.append(row)
    return dict(players=rows,game_diagnostics=simulation['diagnostics'],
                probability_accounting=dict(sum_inclusive=float(sum(r['inclusive_leader_probability'] for r in rows)),
                                            sum_fractional=float(sum(r['fractional_leader_credit'] for r in rows))),
                prize_scenarios=[prize_scenario(mask,simulation['player_ids'],s,pool,selectable=[p['selectable'] for p in profiles]) for s in (scenarios or [])],
                uncertainty_note='Monte Carlo errors measure finite simulation noise only. Predictive intervals mix fitted-history and game uncertainty, but are unvalidated until held-out coverage checks pass.')
