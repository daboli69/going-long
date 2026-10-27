"""Prespecified diagnostic ablations and empirical whole-game block transport."""
import copy
import numpy as np

from scripts.king_court.history import recency_weights


def observed_minutes(profiles,slate):
    result=copy.deepcopy(profiles)
    for p in result:
        p['minutes_mean']=slate['outcomes'][p['player_id']]['minutes']
        p['minutes_sd']=0.
    return result


def fixed_pace(teams):
    result=copy.deepcopy(teams)
    for values in result.values():
        values['pace_sd']=0.
    return result


def fixed_conversion(profiles):
    result=copy.deepcopy(profiles)
    for p in result:
        for name in ('three_share','p2','p3','pft'):
            strength=p['exposures'][name]
            # Keep the original Beta posterior mean, remove its latent variability.
            p['probabilities'][name]=(p['probabilities'][name]*strength+1)/(strength+2)
            p['exposures'][name]=1e12
    return result


def observed_pools(slate,draws):
    fga,fta={},{}
    for g in slate['games']:
        fga[g['game_id']]={code:np.full(draws,g['teams'][code]['fga'],dtype=np.int64) for code in (g['home'],g['away'])}
        fta[g['game_id']]={code:np.full(draws,g['teams'][code]['fta'],dtype=np.int64) for code in (g['home'],g['away'])}
    return fga,fta


def shuffle_players(samples,seed):
    rng=np.random.default_rng(seed)
    result={key:value for key,value in samples.items() if key not in ('measured_pools',)}
    for key in ('points','rebounds','assists','minutes','pra'):
        result[key]=samples[key].copy()
    for j in range(len(samples['player_ids'])):
        order=rng.permutation(len(samples['pra']))
        for key in ('points','rebounds','assists','minutes','pra'):
            result[key][:,j]=samples[key][order,j]
    result['conditioning']='Marginal-preserving dependence destruction; team accounting intentionally broken. Diagnostic only.'
    return result


def game_block(games,slate,profiles,parameters,origin,draws,seed):
    """Transport complete recorded game vectors by precomputed target role rank.

    This is NOT identity-specific resampling. Donor positive-minute roles map to
    target prior-minute ranks, leaving explicit simulated nonparticipation slots.
    No absent source observation is converted into a zero. Unsupported donors
    with more positive roles than target roster slots are rejected.
    """
    rng=np.random.default_rng(seed)
    n=len(profiles)
    result=dict(player_ids=[p['player_id'] for p in profiles],diagnostics=[])
    for k in ('points','rebounds','assists','pra'):
        result[k]=np.zeros((draws,n),dtype=np.int64)
    result['minutes']=np.zeros((draws,n))
    support=[]
    for target in slate['games']:
        slots={code:sorted([j for j,p in enumerate(profiles) if p['game_id']==target['game_id'] and p['team']==code],key=lambda j:(-profiles[j]['minutes_mean'],profiles[j]['player_id'])) for code in (target['home'],target['away'])}
        blocks=[]
        for g in games:
            donor={side:sorted([p for p in g['players'] if p['team']==g[side] and p['minutes']>0],key=lambda p:(-p['minutes'],p['player_id'])) for side in ('home','away')}
            if len(donor['home'])<=len(slots[target['home']]) and len(donor['away'])<=len(slots[target['away']]):
                blocks.append((g,donor))
        if len(blocks)<30:
            raise ValueError('Insufficient complete role-transport game blocks')
        w=recency_weights([g for g,_ in blocks],origin,slate['season'],parameters)
        choices=rng.choice(len(blocks),size=draws,p=w/w.sum())
        for index in np.unique(choices):
            draw_indexes=np.flatnonzero(choices==index)
            g,donor=blocks[index]
            for side,code in (('home',target['home']),('away',target['away'])):
                for rank,p in enumerate(donor[side]):
                    slot=slots[code][rank]
                    for stat,key in (('pts','points'),('reb','rebounds'),('ast','assists'),('minutes','minutes')):
                        result[key][draw_indexes,slot]=p[stat]
        support.append(dict(game_id=target['game_id'],complete_donor_blocks=len(blocks),
                            mapping='target_prior_minute_rank_to_recorded_positive_role_rank',
                            zero_slots='Explicit simulated nonparticipation roles, not missing historical statistics'))
    result['pra']=result['points']+result['rebounds']+result['assists']
    result['diagnostics']=support
    result['conditioning']='Role-exchangeable whole-game empirical challenger, not identity-specific or pregame-availability validated'
    return result
