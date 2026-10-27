"""Experiment-bound decay selection, holdout evaluation and immutable freezes."""
from datetime import datetime, timezone
from itertools import product
import math
import numpy as np

from .common import EASTERN, code_receipts, digest, protocol, seal, utc
from .data import eligible_history, validate_slate
from .history import build_profiles
from .simulation import simulate, summarize


def parameter_grid():
    grid=protocol()['candidate_grid']
    keys=list(grid)
    return [dict(zip(keys,values)) for values in product(*(grid[k] for k in keys))]


def validate_parameters(parameters):
    if parameters not in parameter_grid():
        raise ValueError('Parameters outside preregistered grid')


def forecast(snapshot,slate,parameters,draws=None,scenarios=None,mode='prospective',selection=None,variant='recency'):
    origin=validate_slate(slate)
    validate_parameters(parameters)
    config=protocol()
    covered={g['season'] for g in snapshot['games']}|{g['season'] for g in snapshot.get('scheduled',[])}
    covered|={s['season'] for s in snapshot.get('sources',[]) if s.get('kind')=='player'}
    required=set(range(slate['season']-3,slate['season']+1))
    if not required<=covered:
        raise ValueError(f'Missing requested season coverage: {sorted(required-covered)}')
    if mode=='prospective' and slate['evidence_kind']=='prospective':
        scheduled={g['game_id']:g for g in snapshot.get('scheduled',[]) if utc(g['tipoff']).astimezone(EASTERN).date().isoformat()==slate['date']}
        if set(scheduled)!=set(slate['eligible_game_ids']):
            raise ValueError('Declared full slate differs from preserved regular-season schedule')
        for g in slate['games']:
            source=scheduled[g['game_id']]
            if (source['home']!=g['home'] or source['away']!=g['away'] or utc(source['tipoff'])!=utc(g['tipoff'])
                    or utc(source['known_at'])>origin or source['season']!=slate['season']):
                raise ValueError('Schedule identity/time/source receipt mismatch')
    history=eligible_history(snapshot,origin,slate['season'],mode)
    if not history:
        raise ValueError('No eligible three-prior-plus-current-season history')
    if mode=='prospective' and snapshot.get('debut_metadata') and utc(snapshot['debut_metadata']['known_at'])>origin:
        raise ValueError('Experience metadata was unavailable at decision time')
    profiles,teams,overtime=build_profiles(slate,history,parameters,snapshot.get('debut_seasons'),variant)
    if scenarios:
        offer=slate.get('offer',{})
        if offer.get('date')!=slate['date'] or not offer.get('source') or not isinstance(offer.get('pool_bonus_bet_face_value'),(int,float)) or offer['pool_bonus_bet_face_value']<=0:
            raise ValueError('Prize scenarios require an explicit date-specific offer and bonus-bet face-value pool')
        if offer.get('requires_prop_win') is True:
            raise ValueError('A win-required qualifying prop needs a separate joint qualification model')
        for scenario in scenarios:
            if scenario['kind']=='measured_counts' and utc(scenario['known_at'])>origin:
                raise ValueError('Crowd counts were unavailable at decision time')
            if scenario['kind']=='measured_counts' and (scenario.get('offer_date')!=slate['date'] or not slate.get('offer_id')
                    or scenario.get('offer_id')!=slate['offer_id'] or scenario.get('counts_are_other_customers') is not True):
                raise ValueError('Measured crowd counts must match the exact offer and exclude the hypothetical entry')
    count=draws or config['simulations']
    result=simulate(slate,profiles,teams,overtime,count,config['seed'])
    output=summarize(result,profiles,scenarios,slate.get('offer',{}).get('pool_bonus_bet_face_value',1000000))
    blockers=['research_model_not_validated_or_promoted','aggregate_box_opportunity_proxies_not_exact_possessions']
    if any(g.get('event_reconciliation')!='reconciled' for g in history):
        blockers.append('history_event_reconciliation_missing')
    if any(g.get('lineup_reconciliation')!='reconciled' for g in history):
        blockers.append('history_lineup_reconciliation_missing')
    if not slate.get('full_terms_verified'):
        blockers.append('complete_date_specific_offer_terms_unverified')
    if mode=='retrospective' or slate['evidence_kind']!='prospective':
        blockers.append('not_a_prospective_pregame_prediction')
    selected=False
    if selection:
        selected=(selection.get('kind')=='earlier_fold_parameter_selection' and selection['parameters']==parameters and utc(selection['trained_through'])<origin
                  and selection['model_code_sha256']==code_receipts() and selection['protocol_sha256']==digest(config))
        if not selected:
            raise ValueError('Selection receipt code/protocol/parameters/origin mismatch')
    if not selected:
        blockers.append('recency_parameters_are_experimental_not_selected_on_earlier_folds')
    for player in profiles:
        if 'fallback' in player['prior']['kind']:
            blockers.append('some_experience_priors_use_disclosed_league_fallback')
    output.update(version=config['version'],origin=slate['origin'],slate_date=slate['date'],
                  evidence_kind=slate['evidence_kind'],history_mode=mode,history_variant=variant,history_games=len(history),
                  parameters=parameters,parameters_selected=selected,draws=count,
                  recommendation_status='blocked_research_only',blockers=sorted(set(blockers)),
                  receipts=dict(history_sha256=snapshot['sha256'],slate_sha256=digest(slate),
                                protocol_sha256=digest(config),model_code_sha256=code_receipts(),
                                selection_sha256=selection.get('sha256') if selection else None))
    return output,result


def forecast_comparison(snapshot,slate,parameters,draws=None,scenarios=None,mode='prospective',selection=None):
    primary,simulation=forecast(snapshot,slate,parameters,draws,scenarios,mode,selection)
    primary['history_comparators']={}
    simulations={'recency':simulation}
    for variant in ('current_only','equal_history'):
        try:
            value,samples=forecast(snapshot,slate,parameters,draws,None,mode,selection,variant)
            primary['history_comparators'][variant]=value
            simulations[variant]=samples
        except ValueError as exc:
            primary['history_comparators'][variant]={'status':'unavailable','reason':str(exc)}
    return primary,simulations


def _crps(samples,y):
    ordered=np.sort(samples)
    n=len(ordered)
    pair=np.sum((2*np.arange(1,n+1)-n-1)*ordered)/(n*n)
    return float(np.mean(abs(samples-y))-pair)


def evaluate_result(output,simulation,outcomes):
    ids=simulation['player_ids']
    if set(outcomes)!=set(ids):
        raise ValueError('Full-slate outcomes required, including genuine DNP zeros')
    y=np.array([outcomes[p] for p in ids])
    if any(type(v)is not int or v<0 for v in outcomes.values()):
        raise ValueError('Nonnegative integer official PRA outcomes required')
    if not y.max():
        raise ValueError('All-zero outcomes cannot establish a completed NBA slate')
    actual_leaders=y==y.max()
    actual_solo=actual_leaders & (actual_leaders.sum()==1)
    rows=[]
    for j,p in enumerate(output['players']):
        samples=simulation['pra'][:,j]
        baseline=p['season_average_pra']
        simple=p['minutes_mean']*p['weighted_pra_per_minute']
        probability=float(np.clip(p['inclusive_leader_probability'],.5/len(samples),1-.5/len(samples)))
        truth=int(actual_leaders[j])
        rows.append(dict(player_id=ids[j],experience=p['experience'],actual=int(y[j]),
                         pra_absolute_error=abs(p['expected_pra']-y[j]),crps=_crps(samples,y[j]),
                         coverage80=bool(p['pra_quantiles']['p10']<=y[j]<=p['pra_quantiles']['p90']),
                         season_average_error=abs(baseline-y[j]) if baseline is not None else None,
                         minutes_rate_error=abs(simple-y[j]),leader_brier=(p['inclusive_leader_probability']-truth)**2,
                         sole_leader_brier=(p['sole_leader_probability']-int(actual_solo[j]))**2,
                         leader_log_loss=-truth*math.log(probability)-(1-truth)*math.log(1-probability),
                         predicted_leader_probability=p['inclusive_leader_probability'],actual_leader=truth))
    return dict(slate_date=output['slate_date'],players=rows,
                pra_mae=float(np.mean([r['pra_absolute_error'] for r in rows])),
                crps=float(np.mean([r['crps'] for r in rows])),
                coverage80=float(np.mean([r['coverage80'] for r in rows])),
                leader_brier=float(np.mean([r['leader_brier'] for r in rows])),
                leader_log_loss=float(np.mean([r['leader_log_loss'] for r in rows])))


def validate_experiment(experiment,slates):
    dev,hold=experiment['development_dates'],experiment['holdout_dates']
    if not dev or not hold or len(set(dev+hold))!=len(dev+hold) or max(dev)>=min(hold):
        raise ValueError('Disjoint development and strictly later holdout dates required')
    if len(dev)<protocol()['minimum_selection_slates']:
        raise ValueError('Insufficient registered development slates')
    if (experiment.get('kind')!='experiment_registration' or experiment.get('model_code_sha256')!=code_receipts()
            or experiment.get('protocol_sha256')!=digest(protocol())):
        raise ValueError('Actual-time experiment registration must match frozen model/protocol')
    known={s['date']:s for s in slates}
    if len(known)!=len(slates) or set(known)!=set(dev):
        raise ValueError('Selection accepts exactly the preregistered development slates, no holdout')
    for s in slates:
        validate_slate(s)
        if utc(experiment['registered_at'])>=min(utc(g['tipoff']) for g in s['games']):
            raise ValueError('Experiment registration must precede all development games')
        if s['evidence_kind']!='prospective':
            raise ValueError('Selection requires archived pregame manifests, not reconstructed participants')


def select_parameters(snapshot,experiment,slates,outcomes,draws=2000):
    validate_experiment(experiment,slates)
    if set(outcomes)!=set(experiment['development_dates']):
        raise ValueError('Only registered development outcomes may enter selection')
    for slate in slates:
        outcome=outcomes[slate['date']]
        if not outcome.get('source') or utc(outcome['known_at'])<=max(utc(g['tipoff']) for g in slate['games']):
            raise ValueError('Official after-game outcome receipt required')
        if utc(outcome['known_at'])>datetime.now(timezone.utc):
            raise ValueError('Future outcome receipt cannot enter selection')
    trials=[]
    for parameters in parameter_grid():
        errors=[]
        for slate in sorted(slates,key=lambda s:s['origin']):
            result,simulation=forecast(snapshot,slate,parameters,draws=draws,mode='prospective')
            value=evaluate_result(result,simulation,outcomes[slate['date']]['values'])
            errors.append(value['pra_mae'])
        trials.append(dict(parameters=parameters,mean_slate_pra_mae=float(np.mean(errors)),slate_errors=errors))
    trials.sort(key=lambda t:(t['mean_slate_pra_mae'],t['parameters']['season_decay'],t['parameters']['game_half_life_days'],t['parameters']['prior_games']))
    return seal(dict(kind='earlier_fold_parameter_selection',parameters=trials[0]['parameters'],trials=trials,
                     trained_through=max(utc(o['known_at']) for o in outcomes.values()).isoformat(),experiment_sha256=digest(experiment),
                     history_sha256=snapshot['sha256'],protocol_sha256=digest(protocol()),
                     model_code_sha256=code_receipts(),development_dates=experiment['development_dates'],
                     holdout_dates=experiment['holdout_dates'],draws_per_fold=draws,
                     limitations='Development selection only; code/source-frozen later holdout still required.'))


def paired_slate_intervals(evaluations):
    if not evaluations:
        raise ValueError('No settled slates')
    rng=np.random.default_rng(protocol()['seed'])
    n=len(evaluations)
    draws=rng.integers(0,n,size=(2000,n))
    result={}
    for baseline in ('season_average_error','minutes_rate_error'):
        diffs=[]
        for evaluation in evaluations:
            paired=[r for r in evaluation['players'] if r[baseline] is not None]
            if paired:
                diffs.append(float(np.mean([r['pra_absolute_error']-r[baseline] for r in paired])))
        if len(diffs)!=n:
            result[baseline]={'status':'some_slates_have_no_paired_baseline'}
            continue
        values=np.array(diffs)
        samples=values[draws].mean(axis=1)
        result[baseline]=dict(mean_delta=float(values.mean()),whole_slate_95_interval=np.quantile(samples,[.025,.975]).tolist())
    cohorts={}
    for group in ('rookie','second_year','established'):
        rows=[r for e in evaluations for r in e['players'] if r['experience']==group]
        cohorts[group]=dict(n=len(rows),pra_mae=float(np.mean([r['pra_absolute_error'] for r in rows])) if rows else None)
    bins=[]
    for lower,upper in ((0,.01),(.01,.05),(.05,.1),(.1,.25),(.25,.5),(.5,1.000001)):
        rows=[r for e in evaluations for r in e['players'] if lower<=r['predicted_leader_probability']<upper]
        if rows:
            bins.append(dict(lower=lower,upper=min(upper,1),n=len(rows),
                             mean_probability=float(np.mean([r['predicted_leader_probability'] for r in rows])),
                             actual_rate=float(np.mean([r['actual_leader'] for r in rows]))))
    history_comparison={}
    for variant in ('current_only','equal_history'):
        paired=[e for e in evaluations if variant in e.get('history_comparators',{})]
        if not paired:
            history_comparison[variant]={'status':'unavailable'}
            continue
        values=np.array([e['pra_mae']-e['history_comparators'][variant]['pra_mae'] for e in paired])
        sample=rng.integers(0,len(values),size=(2000,len(values)))
        history_comparison[variant]=dict(paired_slates=len(values),mean_mae_delta=float(values.mean()),
                                         whole_slate_95_interval=np.quantile(values[sample].mean(axis=1),[.025,.975]).tolist(),
                                         baseline_crps=float(np.mean([e['history_comparators'][variant]['crps'] for e in paired])),
                                         baseline_coverage80=float(np.mean([e['history_comparators'][variant]['coverage80'] for e in paired])))
    return dict(slates=n,paired_mae=result,experience_cohorts=cohorts,leader_reliability_bins=bins,history_comparison=history_comparison,
                evidence_status='insufficient_slates' if n<protocol()['minimum_evaluation_slates'] else 'diagnostic_only_no_automatic_promotion',
                limits='Intervals resample complete slates; longer serial dependence may remain. Popularity unvalidated without real token counts.')
