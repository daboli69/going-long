"""Shared diagnostic inputs. A postgame field is never a pregame roster.

Unknown experience remains unknown. Conditional mechanism checks can use that
field, but cannot become v1 forecasts, selection receipts or prospective grades.
"""
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import math
import numpy as np

from scripts.king_court.common import EASTERN, TEAMS, team, utc
from scripts.king_court.data import eligible_history
from scripts.king_court.history import context_profiles, effective_n, flatten, player_profile, recency_weights

KEYS=('minutes','pts','reb','ast','fgm','fga','tpm','tpa','ftm','fta','oreb','dreb')


def scheduled_fields(snapshot,dates):
    import polars as pl
    fields={day:set() for day in dates}
    for source in snapshot['sources']:
        if source.get('kind')!='schedule' or source['season']!=2026:
            continue
        for r in pl.read_parquet(source['path']).to_dicts():
            day=utc(r['date']).astimezone(EASTERN).date().isoformat()
            if day not in fields or r.get('season_type')!=2 or r.get('status_type_name')!='STATUS_FINAL':
                continue
            if team(r.get('home_abbreviation')) not in TEAMS or team(r.get('away_abbreviation')) not in TEAMS:
                continue
            note=str(r.get('notes_headline') or '').lower()
            if 'championship' in note and ('cup' in note or 'in-season tournament' in note):
                continue
            fields[day].add('espn:'+str(r['game_id']))
    return fields


def collect_slates(snapshot,dates):
    fields=scheduled_fields(snapshot,dates)
    games={g['game_id']:g for g in snapshot['games']}
    slates,exclusions=[],[]
    for day in dates:
        required=fields[day]
        missing=required-set(games)
        if not required or missing:
            exclusions.append(dict(date=day,reason='no_completed_regular_games' if not required else 'incomplete_reconciled_slate',missing_game_ids=sorted(missing)))
            continue
        target=sorted([games[gid] for gid in required],key=lambda g:g['tipoff'])
        origin=min(utc(g['tipoff']) for g in target)-timedelta(hours=12)
        field=[]
        outcomes={}
        for g in target:
            for p in g['players']:
                if p['player_id'] in outcomes:
                    raise ValueError('Duplicate player across completed games')
                field.append(dict(p,game_id=g['game_id']))
                outcomes[p['player_id']]=dict(points=p['pts'],rebounds=p['reb'],assists=p['ast'],minutes=p['minutes'])
        slates.append(dict(date=day,season=2026,origin=origin.isoformat(),games=target,players=field,outcomes=outcomes,
                           evidence_kind='postgame_box_field_conditioning_not_pregame_availability',
                           source_known_time='archived_retrieval_not_historical_publication'))
    return slates,exclusions


def _aggregate(rows,w):
    if not rows:
        return np.zeros(len(KEYS))
    return np.array([[r[k] for k in KEYS] for r in rows],dtype=float).T@w


def profiles(snapshot,slate,parameters):
    origin=utc(slate['origin']);season=slate['season']
    games=eligible_history(snapshot,origin,season,'retrospective')
    if not set(range(season-3,season+1))<={g['season'] for g in games}:
        raise ValueError('Four-season history missing')
    rows=flatten(games)
    by_player=defaultdict(list)
    by_position=defaultdict(list)
    for r in rows:
        by_player[r['player_id']].append(r)
        by_position[r['position']].append(r)
    population={}
    for position,cohort in by_position.items():
        w=recency_weights(cohort,origin,season,parameters)
        total=_aggregate(cohort,w)/w.sum()
        mean=total[0]
        variance=float(np.average([(r['minutes']-mean)**2 for r in cohort],weights=w))
        population[position]=(dict(zip(KEYS,total)),variance,len(cohort))
    debut=snapshot.get('debut_seasons',{})
    result=[]
    for target in slate['players']:
        pid=target['player_id'];own=by_player[pid]
        if pid in debut:
            candidate=dict(target,debut_season=debut[pid],availability='available',selectable=False)
            p=player_profile(candidate,rows,origin,season,parameters,debut)
        else:
            cohort=population.get(target['position'])
            if cohort is None:
                all_w=recency_weights(rows,origin,season,parameters)
                values=dict(zip(KEYS,_aggregate(rows,all_w)/all_w.sum()))
                variance=float(np.average([(r['minutes']-values['minutes'])**2 for r in rows],weights=all_w))
                cohort=(values,variance,len(rows))
            base,variance,cohort_n=cohort
            w=recency_weights(own,origin,season,parameters)
            own_values=dict(zip(KEYS,_aggregate(own,w)))
            combined={k:own_values[k]+parameters['prior_games']*base[k] for k in KEYS}
            role=[r for r in own if r['team']==target['team'] and r['season']==season]
            rw=recency_weights(role,origin,season,parameters)
            strength=parameters['prior_games']
            mean=(sum(r['minutes']*v for r,v in zip(role,rw))+strength*base['minutes'])/(rw.sum()+strength)
            var=(sum(v*(r['minutes']-mean)**2 for r,v in zip(role,rw))+strength*variance)/(rw.sum()+strength)
            rates={k:combined[k]/combined['minutes'] for k in ('fga','fta','oreb','dreb','ast')}
            def fraction(a,b,fallback):
                return combined[a]/combined[b] if combined[b] else fallback
            two_a=combined['fga']-combined['tpa'];two_m=combined['fgm']-combined['tpm']
            probability=dict(three_share=fraction('tpa','fga',.3),p2=two_m/two_a if two_a else .5,
                             p3=fraction('tpm','tpa',.33),pft=fraction('ftm','fta',.75))
            total=float(w.sum())
            share={str(s):sum(v for r,v in zip(own,w) if r['season']==s)/total for s in sorted({r['season'] for r in own})} if total else {}
            p=dict(player_id=pid,name=target['name'],team=target['team'],game_id=target['game_id'],
                   availability='available',selectable=False,experience='unknown',minutes_mean=float(mean),minutes_sd=math.sqrt(max(0,var)),
                   rates=rates,probabilities=probability,
                   exposures=dict(fga=combined['fga'],fta=combined['fta'],three_share=combined['fga'],p2=two_a,p3=combined['tpa'],pft=combined['fta']),
                   evidence=dict(games=len(own),effective_sample_size=effective_n(w),season_weight_shares=share),
                   prior=dict(kind='unknown_experience_position_prior_DIAGNOSTIC_ONLY',pseudo_games=strength,cohort_player_games=cohort_n),
                   role_evidence=dict(games=len(role),effective_sample_size=effective_n(rw)),
                   weighted_pra_per_minute=(combined['pts']+combined['reb']+combined['ast'])/combined['minutes'])
        current=[r for r in own if r['season']==season]
        p['season_average_pra']=float(np.mean([r['pts']+r['reb']+r['ast'] for r in current])) if current else None
        p['point_minutes_rate']=p['minutes_mean']*p['weighted_pra_per_minute']
        role=[r for r in own if r['team']==target['team'] and r['season']==season]
        p['role_change']='new_team_or_no_current_role' if not role else 'insufficient_role_comparison'
        if len(role)>=8:
            recent=np.mean([r['minutes'] for r in role[-3:]])
            earlier=np.mean([r['minutes'] for r in role[-8:-3]])
            p['role_change']='recent_minutes_up' if recent>earlier else 'recent_minutes_flat_or_down'
        p['conditioning']='Allocation permitted in a measured postgame field; NOT evidence of pregame availability'
        result.append(p)
    teams,overtime=context_profiles(games,origin,season,parameters)
    return result,teams,overtime,games
