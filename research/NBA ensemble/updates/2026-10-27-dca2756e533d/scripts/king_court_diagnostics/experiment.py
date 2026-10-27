"""Reproduce the frozen reused-data diagnostic; never a prospective backtest."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import itertools
import json
from pathlib import Path
import numpy as np

from scripts.king_court.common import digest,load_sealed,seal,utc,write_new
from scripts.king_court.research import parameter_grid
from .challengers import fixed_conversion,fixed_pace,game_block,observed_minutes,observed_pools,shuffle_players
from .dataset import collect_slates,profiles
from .metrics import aggregate,evaluate,paired_intervals
from .pools import PairedFGA,possessions
from .simulation import simulate

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT/'research/king-court/distribution-v2'


def diagnostic_code_hashes():
    return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}


def verify_registration():
    r=load_sealed(RESEARCH/'registration.json')
    if sha256((RESEARCH/'PLAN.md').read_bytes()).hexdigest()!=r['plan_sha256']:
        raise ValueError('Frozen plan changed')
    if sha256((ROOT/'docs/KING_COURT_DISTRIBUTION_AUDIT.md').read_bytes()).hexdigest()!=r['audit_sha256']:
        raise ValueError('Frozen audit changed')
    for name,value in r['baseline_files'].items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=value:
            raise ValueError('Preserved v1/winner source changed: '+name)
    return r


def lock_code(path):
    r=verify_registration()
    write_new(path,seal(dict(kind='diagnostic_code_lock_before_comparison',recorded_at=datetime.now(timezone.utc).isoformat(),
                             registration_sha256=r['sha256'],diagnostic_code_sha256=diagnostic_code_hashes(),
                             baseline_files=r['baseline_files'])))


def _pool_score(sim,slate,teams):
    result=[]
    for g in slate['games']:
        for code,opponent in ((g['home'],g['away']),(g['away'],g['home'])):
            pool=sim['measured_pools'][(g['game_id'],code)]
            mu=np.sqrt(teams[code]['fga_poss']*teams[opponent]['allowed_fga_poss'])
            residual=pool['fga']-pool['possessions']*mu
            result.append(dict(game_id=g['game_id'],team=code,simulated_conditional_residual_variance=float(residual.var(ddof=1)),
                               predicted_mean=float(pool['fga'].mean()),observed=g['teams'][code]['fga'],
                               observed_conditioned_residual=float(g['teams'][code]['fga']-possessions(g)*mu)))
    return result


def _choose(snapshot,slates,registration):
    candidates=[]
    seed=registration['selection_seed']
    for number,parameters in enumerate(parameter_grid()):
        cells=[]
        for slate in slates:
            pp,teams,ot,games=profiles(snapshot,slate,parameters)
            sample=simulate(slate,pp,teams,ot,registration['selection_draws'],seed)
            metrics=evaluate(sample,slate,pp)
            cells.append(dict(date=slate['date'],crps=metrics['crps'],mae=metrics['mae']))
        candidate=dict(parameters=parameters,mean_crps=float(np.mean([c['crps'] for c in cells])),
                       mean_mae=float(np.mean([c['mae'] for c in cells])),slates=cells)
        candidates.append(candidate)
        print(json.dumps({'stage':'diagnostic_development','candidate':number+1,'of':len(parameter_grid()),
                          'complete_slates':len(cells),'crps':candidate['mean_crps']}),flush=True)
    candidates.sort(key=lambda x:(x['mean_crps'],x['mean_mae'],x['parameters']['season_decay'],x['parameters']['game_half_life_days'],x['parameters']['prior_games']))
    score=np.array([[c['crps'] for c in candidate['slates']] for candidate in candidates])
    rng=np.random.default_rng(seed)
    draws=rng.integers(0,len(slates),size=(4000,len(slates)))
    winners=score[:,draws].mean(axis=2).argmin(axis=0)
    return dict(kind='conditional_reused_data_parameter_choice_NOT_v1_selection_receipt',parameters=candidates[0]['parameters'],
                candidates=candidates,complete_development_slates=len(slates),
                insufficient_for_v1_selection=len(slates)<8,
                development_slate_bootstrap_choice_frequencies=[dict(parameters=c['parameters'],fraction=float(np.mean(winners==i))) for i,c in enumerate(candidates)],
                interpretation='Earlier diagnostic choice only; not validated priors, not posterior parameter probabilities. No assessment tuning.')


def run(history_path,code_lock,output,event_audit_path):
    registration=verify_registration()
    lock=load_sealed(code_lock)
    if lock['diagnostic_code_sha256']!=diagnostic_code_hashes() or lock['registration_sha256']!=registration['sha256']:
        raise ValueError('Comparison code/registration differs from frozen lock')
    if Path(output).exists():
        raise FileExistsError(output)
    history=load_sealed(history_path)
    dev,dev_excluded=collect_slates(history,registration['retrospective_development'])
    assessment,excluded=collect_slates(history,registration['retrospective_assessment'])
    if not dev or not assessment:
        raise ValueError('No complete paired diagnostic slates')
    chosen=_choose(history,dev,registration)
    parameters=chosen['parameters']
    evaluations={name:[] for name in ('original','repaired_fga','observed_minutes','fixed_pace','fixed_opportunities','fixed_conversion','independent_player_shuffle','game_block')}
    sensitivity={name:[] for name in ('original','repaired_fga')}
    seed=registration['assessment_seeds'][0]
    second_seed=registration['assessment_seeds'][1]
    draws=registration['assessment_draws']
    pool_records=[];repair_evidence=[];block_support=[];mc=[]
    for index,slate in enumerate(assessment):
        pp,teams,ot,games=profiles(history,slate,parameters)
        original=simulate(slate,pp,teams,ot,draws,seed)
        empirical=PairedFGA(games,utc(slate['origin']),slate['season'],parameters,teams,seed+101)
        repaired=simulate(slate,pp,teams,ot,draws,seed,field_goal_pools=empirical)
        evaluations['original'].append(evaluate(original,slate,pp))
        evaluations['repaired_fga'].append(evaluate(repaired,slate,pp))
        pool_records.append(dict(date=slate['date'],original=_pool_score(original,slate,teams),repaired=_pool_score(repaired,slate,teams)))
        repair_evidence.append(dict(date=slate['date'],**empirical.evidence))
        variants={}
        variants['observed_minutes']=simulate(slate,observed_minutes(pp,slate),teams,ot,draws,seed)
        variants['fixed_pace']=simulate(slate,pp,fixed_pace(teams),ot,draws,seed)
        fg,ft=observed_pools(slate,draws)
        variants['fixed_opportunities']=simulate(slate,pp,teams,ot,draws,seed,field_goal_pools=fg,free_throw_pools=ft)
        variants['fixed_conversion']=simulate(slate,fixed_conversion(pp),teams,ot,draws,seed)
        variants['independent_player_shuffle']=shuffle_players(original,seed+201)
        variants['game_block']=game_block(games,slate,pp,parameters,utc(slate['origin']),draws,seed+301)
        block_support.append(dict(date=slate['date'],support=variants['game_block']['diagnostics'],mapping=variants['game_block']['conditioning']))
        for name,value in variants.items():
            evaluations[name].append(evaluate(value,slate,pp))
        other=simulate(slate,pp,teams,ot,draws,second_seed)
        pool=PairedFGA(games,utc(slate['origin']),slate['season'],parameters,teams,second_seed+101)
        other_repair=simulate(slate,pp,teams,ot,draws,second_seed,field_goal_pools=pool)
        sensitivity['original'].append(evaluate(other,slate,pp))
        sensitivity['repaired_fga'].append(evaluate(other_repair,slate,pp))
        for name in ('original','repaired_fga'):
            first=evaluations[name][-1]['players'];second=sensitivity[name][-1]['players']
            for a,b in zip(first,second):
                den=np.hypot(a['leader_mc_se'],b['leader_mc_se'])
                mc.append(dict(variant=name,date=slate['date'],player_id=a['player_id'],probability_difference=b['inclusive_leader_probability']-a['inclusive_leader_probability'],
                               combined_mc_se=float(den),mean_difference=b['mean']-a['mean'],combined_mean_mc_se=float(np.hypot(a['mean_mc_se'],b['mean_mc_se']))))
        print(json.dumps({'stage':'assessment','slate':index+1,'of':len(assessment),'date':slate['date'],'players':len(pp)}),flush=True)
    # Strict raw-event/stint subset is additional coverage, not a replacement cohort.
    event_audit=load_sealed(event_audit_path)
    links={}
    import polars as pl
    cross=next(s for s in event_audit['sources'] if s['kind']=='schedule_crosswalk_2026')
    for row in pl.read_parquet(cross['path']).to_dicts():
        if row['match_confidence']==1:
            links['espn:'+str(row['espn_game_id'])]=str(row['nba_game_id'])
    verified=[]
    for slate in assessment:
        checks=[event_audit['games'].get(links.get(g['game_id'],''),{}) for g in slate['games']]
        if checks and all(c.get('event_agreement') and c.get('stint_agreement') and c.get('canonical_espn_box_agreement') for c in checks):
            verified.append(slate['date'])
    result=dict(kind='reused_postgame_field_distribution_diagnostic_NOT_predictive_validation',
                registration_sha256=registration['sha256'],code_lock_sha256=lock['sha256'],history_sha256=history['sha256'],event_audit_sha256=event_audit['sha256'],
                parameter_choice=chosen,development_exclusions=dev_excluded,assessment_exclusions=excluded,
                summary={name:aggregate(values) for name,values in evaluations.items()},
                paired_original_repair=paired_intervals(evaluations['original'],evaluations['repaired_fga']),
                seed_sensitivity=dict(summary={name:aggregate(values) for name,values in sensitivity.items()},
                                      paired=paired_intervals(sensitivity['original'],sensitivity['repaired_fga'],second_seed),
                                      finite_simulation_differences=mc),
                strict_event_and_stint_verified_dates=verified,
                strict_verified_summary={name:aggregate([e for e in evaluations[name] if e['date'] in verified]) for name in ('original','repaired_fga')},
                FGA_pool_diagnostics=pool_records,repair_support=repair_evidence,empirical_block_support=block_support,
                per_slate=evaluations,
                overall_predictive_verdict='inconclusive',
                prospective_evaluation=dict(registered_dates=registration['prospective_evaluation'],completed_slates=0,
                                            status='future_unopened_no_prediction_or_outcome_fabricated'),
                limitations=['Historical fields are postgame conditioning, not inferred pregame availability or verified promotion eligibility.',
                             'Unknown debut metadata remains unknown; v1 verified experience priors are preserved, not falsely validated.',
                             'Shared diagnostic position priors for unknown experience are common to both comparators; this is a simulator comparison, not a valid replay of v1 live forecasts.',
                             'All assessment archives were previously inspected; later chronological dates are not an untouched holdout.',
                             'Conditional FGA residuals use a possession proxy. Event-count evidence is producer-derived from the same NBA feed.',
                             'Monte Carlo noise, game uncertainty, parameter-choice instability and model misspecification are distinct.',
                             'The role-transport empirical challenger is not identity-specific and cannot validate rookie ceilings.',
                             'No promotion, popularity estimate, expected payout or betting claim is made.'])
    write_new(output,seal(result))
    return result
