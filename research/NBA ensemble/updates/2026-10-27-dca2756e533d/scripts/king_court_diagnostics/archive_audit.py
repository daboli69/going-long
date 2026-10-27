"""Reconcile available event-level NBA archives; never claim raw vendor JSON.

SportsDataverse has parsed legacy NBA action descriptions and inferred lineups.
Ambiguous names/lineup seeds remain failures, not silently repaired observations.
"""
from collections import Counter, defaultdict
import re
import unicodedata
import numpy as np

from scripts.king_court.common import load_sealed, seal, write_new


def key(value):
    return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower())


def seconds(clock):
    match=re.fullmatch(r'PT(\d+)M([\d.]+)S',str(clock))
    if not match:
        raise ValueError('unknown_clock')
    return 60*int(match[1])+float(match[2])


def box_seconds(value):
    if not value:
        return 0.
    parts=str(value).split(':')
    if len(parts)!=2:
        raise ValueError('unknown_box_minutes')
    return 60*float(parts[0])+float(parts[1])


def audit_game(events,lineups,boxes):
    boxes={int(p['person_id']):p for p in boxes}
    counters={pid:Counter() for pid in boxes}
    names=defaultdict(set)
    for pid,p in boxes.items():
        for name in (p['family_name'],p['name_i'],p['first_name']+' '+p['family_name']):
            names[(int(p['team_id']),key(name))].add(pid)
    for e in events:
        if int(e['person_id'] or 0) in boxes and e.get('player_name'):
            names[(int(e['team_id'] or 0),key(e['player_name']))].add(int(e['person_id']))
    issues=Counter()
    free_throws=Counter()
    seen={}
    for e in sorted(events,key=lambda x:x['order_index']):
        # Producer splits a steal/block into a related row sharing action_number.
        # order_index identifies a record; do not discard the paired event.
        number=int(e['order_index'])
        if number in seen and seen[number]!=e:
            issues['conflicting_order_index']+=1
        elif number in seen:
            continue
        seen[number]=e
        pid=int(e['person_id'] or 0)
        kind=e['action_type']
        if kind in ('Made Shot','Missed Shot'):
            if pid not in boxes:
                issues['unmapped_shooter']+=1
                continue
            counters[pid]['fga']+=1
            if kind=='Made Shot':
                counters[pid]['fgm']+=1
                counters[pid]['pts']+=int(e['shot_value'])
                assist=re.search(r'\(([^()]*) (\d+) AST\)',str(e['description']))
                if assist:
                    ids=names[(int(e['team_id']),key(assist[1]))]
                    if len(ids)==1:
                        aid=next(iter(ids))
                        if aid==pid:
                            issues['self_assist']+=1
                        counters[aid]['ast']+=1
                    else:
                        issues['ambiguous_assist_name']+=1
        elif kind=='Free Throw':
            if pid not in boxes:
                issues['unmapped_free_throw_shooter']+=1
                continue
            counters[pid]['fta']+=1
            missed=str(e['description']).upper().startswith('MISS ')
            if not missed:
                counters[pid]['ftm']+=1
                counters[pid]['pts']+=1
            else:
                text=(str(e['description'])+' '+str(e['sub_type'])).lower()
                sequence=re.search(r'(\d+) of (\d+)',text)
                if 'technical' in text or (sequence and int(sequence[1])<int(sequence[2])):
                    free_throws['missed_nonfinal_or_technical_not_a_live_rebound_chance']+=1
                elif sequence and not any(x in text for x in ('flagrant','clear path','away from play')):
                    free_throws['missed_ordinary_final_potentially_reboundable']+=1
                else:
                    free_throws['missed_ambiguous_sequence_or_retained_possession']+=1
        elif kind=='Rebound' and pid in boxes:
            counters[pid]['reb']+=1
    differences=[]
    fields={'pts':'points','reb':'rebounds_total','ast':'assists','fga':'field_goals_attempted','fgm':'field_goals_made',
            'fta':'free_throws_attempted','ftm':'free_throws_made'}
    for pid,p in boxes.items():
        for metric,col in fields.items():
            actual=int(p[col] or 0)
            if counters[pid][metric]!=actual:
                differences.append(dict(player_id=pid,stat=metric,event=counters[pid][metric],box=actual))
    by_period=defaultdict(list)
    lineup_index={(int(r['period']),int(r['action_number'])):r for r in lineups}
    for e in sorted(events,key=lambda x:x['order_index']):
        by_period[int(e['period'])].append(e)
    time=Counter()
    stint_issues=Counter()
    for period,rows in sorted(by_period.items()):
        seed=lineup_index.get((period,int(rows[0]['action_number'])))
        if not seed:
            stint_issues['missing_period_lineup_seed']+=1
            continue
        floors={side:set(int(seed[f'{side}_player_{i}']) or 0 for i in range(1,6)) for side in ('home','away')}
        if any(len(ids)!=5 or any(pid not in boxes for pid in ids) for ids in floors.values()):
            stint_issues['invalid_period_lineup_seed']+=1
            continue
        side_for_team={int(boxes[next(iter(ids))]['team_id']):side for side,ids in floors.items()}
        remaining=720. if period<=4 else 300.
        for e in rows:
            clock=seconds(e['clock'])
            if clock>remaining+1e-6 or clock<0:
                stint_issues['clock_order_conflict']+=1
                break
            for ids in floors.values():
                for pid in ids:
                    time[pid]+=remaining-clock
            remaining=clock
            if e['action_type']=='Substitution':
                match=re.fullmatch(r'SUB: (.+) FOR (.+)',str(e['description']))
                team=int(e['team_id'] or 0)
                side=side_for_team.get(team)
                leaving=int(e['person_id'] or 0)
                incoming=names[(team,key(match[1]))] if match else set()
                if not side or leaving not in floors[side] or len(incoming)!=1:
                    stint_issues['ambiguous_or_inconsistent_substitution']+=1
                    continue
                entrant=next(iter(incoming))
                if entrant in floors[side]:
                    stint_issues['entrant_already_on_floor']+=1
                    continue
                floors[side].remove(leaving)
                floors[side].add(entrant)
        else:
            for ids in floors.values():
                for pid in ids:
                    time[pid]+=remaining
    minute_errors=[dict(player_id=pid,reconstructed_seconds=time[pid],box_seconds=box_seconds(p['minutes']))
                   for pid,p in boxes.items() if abs(time[pid]-box_seconds(p['minutes']))>2.01]
    return dict(event_agreement=not differences and not issues,stat_differences=differences,event_issues=dict(issues),
                stint_agreement=not minute_errors and not stint_issues,minute_differences=minute_errors,
                stint_issues=dict(stint_issues),free_throw_misses=dict(free_throws),
                lineups_source='producer_inferred_snapshots_seed_raw_substitutions_not_independent_observation')


def run(source_manifest,possessions_manifest,history_path,output):
    import polars as pl
    from pathlib import Path
    from hashlib import sha256
    sources=load_sealed(source_manifest)['sources']+load_sealed(possessions_manifest)['sources']
    data={}
    for s in sources:
        if s.get('status')!=200:
            continue
        if sha256(Path(s['path']).read_bytes()).hexdigest()!=s['sha256']:
            raise ValueError('Raw event source changed')
        data[s['kind']]=pl.read_parquet(s['path'])
    pbp=data['nba_pbp_2026'].filter(pl.col('game_id').str.starts_with('002'))
    boxes=data['nba_boxes_2026'].filter(pl.col('game_id').str.starts_with('002'))
    lineups=data['nba_lineups_2026'].filter(pl.col('game_id').str.starts_with('002'))
    pg=pbp.partition_by('game_id',as_dict=True)
    bg=boxes.partition_by('game_id',as_dict=True)
    lg=lineups.partition_by('game_id',as_dict=True)
    results={}
    for identifier,events in pg.items():
        if identifier not in bg or identifier not in lg:
            continue
        results[identifier[0]]=audit_game(events.to_dicts(),lg[identifier].to_dicts(),bg[identifier].to_dicts())
    counts=Counter()
    ft=Counter()
    for r in results.values():
        counts['games']+=1
        counts['event_agreement']+=r['event_agreement']
        counts['stint_agreement']+=r['stint_agreement']
        counts['event_and_stint_agreement']+=r['event_agreement'] and r['stint_agreement']
        ft.update(r['free_throw_misses'])
    history=load_sealed(history_path)
    canonical={g['game_id']:g for g in history['games']}
    links=[]
    for r in data['schedule_crosswalk_2026'].to_dicts():
        espn='espn:'+str(r['espn_game_id'])
        nba=str(r['nba_game_id'])
        if espn in canonical and nba in results and r['match_confidence']==1:
            links.append((nba,espn))
    identities=defaultdict(set)
    for r in data['player_crosswalk_2026'].to_dicts():
        if r['match_confidence']==1 and r.get('espn_athlete_id') and r.get('nba_player_id'):
            identities['espn:'+str(r['espn_athlete_id'])].add(int(r['nba_player_id']))
    for nba,espn in links:
        official={int(r['person_id']):r for r in bg[(nba,)].to_dicts()}
        differences=[]
        for p in canonical[espn]['players']:
            candidates=identities[p['player_id']]
            if len(candidates)!=1 or next(iter(candidates)) not in official:
                if p['minutes']>0 or p['pts']+p['reb']+p['ast']>0:
                    differences.append(dict(player_id=p['player_id'],reason='unmapped_active_player'))
                continue
            q=official[next(iter(candidates))]
            for key,column in (('pts','points'),('reb','rebounds_total'),('ast','assists'),('fgm','field_goals_made'),('fga','field_goals_attempted'),('ftm','free_throws_made'),('fta','free_throws_attempted')):
                if p[key]!=int(q[column] or 0):
                    differences.append(dict(player_id=p['player_id'],stat=key,canonical=p[key],NBA=int(q[column] or 0)))
            if abs(p['minutes']*60-box_seconds(q['minutes']))>61:
                differences.append(dict(player_id=p['player_id'],reason='canonical_rounded_minutes_mismatch'))
        results[nba]['canonical_espn_box_agreement']=not differences
        results[nba]['canonical_espn_box_differences']=differences
        counts['canonical_espn_box_agreement']+=not differences
    pos=data['nba_possessions_2026'].filter(pl.col('count_as_possession')==True)
    pos_counts=pos.group_by('game_id','offense_team_id').len().partition_by('game_id',as_dict=True)
    box_groups=boxes.group_by('game_id','team_id').agg(pl.col('field_goals_attempted').sum().alias('fga'),pl.col('points').sum().alias('pts')).partition_by('game_id',as_dict=True)
    counter_rows=[]
    for nba,espn in links:
        g=canonical[espn]
        if g['tipoff']>='2025-12-17' or not results[nba]['event_agreement']:
            continue
        p=pos_counts.get((nba,));b=box_groups.get((nba,))
        if p is None or b is None or p.height!=2 or b.height!=2:
            continue
        counts_by_team={r['offense_team_id']:r['len'] for r in p.to_dicts()}
        bs=b.sort('team_id').to_dicts()
        if set(counts_by_team)!=set(r['team_id'] for r in bs):
            continue
        possession=.5*sum(counts_by_team.values())
        counter_rows.append((possession,bs[0]['fga'],bs[1]['fga']))
    component={}
    if counter_rows:
        x=np.array(counter_rows,dtype=float)
        residual=(x[:,1:]/x[:,0,None]-(x[:,1:]/x[:,0,None]).mean(axis=0))*x[:,0,None]
        component=dict(games=len(x),mean_implied_Poisson_variance=x[:,1:].mean(axis=0).tolist(),
                       measured_counted_possession_residual_variance=residual.var(axis=0,ddof=1).tolist(),
                       residual_variance_to_Poisson=(residual.var(axis=0,ddof=1)/x[:,1:].mean(axis=0)).tolist(),
                       limitation='Producer-derived possession grouping, same NBA feed; not an independent provider. Development-only matched games.')
    body=dict(kind='available_event_archive_reconciliation_not_pregame_validation',counts=dict(counts),
              free_throw_miss_classification=dict(ft),explicit_game_crosswalk_matches=len(links),
              development_counted_possession_check=component,sources=sources,games=results,
              unavailable=['native_original_vendor_JSON','independently_observed_period_lineups','pregame_availability_receipts','verified_NBA_debut_metadata','potential_assists_tracking'],
              interpretation='Event/stat and raw-substitution audits concern measurement, not probability calibration. No pregame roster is inferred.')
    write_new(output,seal(body))
    return body
