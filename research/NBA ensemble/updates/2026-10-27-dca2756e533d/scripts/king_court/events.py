"""Reconcile raw NBA live play-by-play against canonical official boxes.

Crosswalks are explicit. PBP-derived lineups require supplied period-start fives;
missing initial lineups cannot silently become verified rotation evidence.
"""
from collections import defaultdict
from hashlib import sha256
import json
import re


def reconcile(raw, game, crosswalk):
    feed=raw['game']
    if str(feed['gameId']) != str(crosswalk['nba_game_id']) or crosswalk['game_id'] != game['game_id']:
        raise ValueError('Exact game crosswalk mismatch')
    persons,teams=crosswalk['persons'],crosswalk['teams']
    boxes={p['player_id']:p for p in game['players']}
    stats={pid:dict(pts=0,reb=0,ast=0) for pid in boxes}
    by_number={}
    for action in feed['actions']:
        number=action['actionNumber']
        if number in by_number and by_number[number]!=action:
            raise ValueError('Conflicting PBP action number')
        by_number[number]=action
    actions=[by_number[n] for n in sorted(by_number)]

    def person(value):
        result=persons.get(str(value))
        if result not in boxes:
            raise ValueError(f'Unmapped player ID in raw PBP: {value}')
        return result

    for a in actions:
        kind=str(a.get('actionType','')).lower()
        if kind in ('2pt','3pt','freethrow') and a.get('shotResult')=='Made':
            pid=person(a.get('personId'))
            if teams.get(str(a.get('teamId'))) != boxes[pid]['team']:
                raise ValueError('Shot team/player conflict')
            stats[pid]['pts'] += {'2pt':2,'3pt':3,'freethrow':1}[kind]
            assister=a.get('assistPersonId')
            if kind!='freethrow' and assister:
                aid=person(assister)
                if aid==pid or boxes[aid]['team']!=boxes[pid]['team']:
                    raise ValueError('Self-assist or opponent assist in PBP')
                stats[aid]['ast']+=1
        if kind=='rebound' and a.get('personId'):
            stats[person(a['personId'])]['reb']+=1
    differences=[dict(player_id=pid,stat=k,event_value=stats[pid][k],box_value=p[k])
                 for pid,p in boxes.items() for k in ('pts','reb','ast') if stats[pid][k]!=p[k]]
    result=dict(game_id=game['game_id'],nba_game_id=str(feed['gameId']),
                raw_sha256=sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest(),
                event_agreement=not differences,differences=differences,
                lineup_agreement=False,lineup_status='missing_period_start_lineups',
                substitutions=sum(a.get('actionType')=='substitution' for a in actions))
    if not crosswalk.get('period_lineups'):
        return result

    def seconds(clock):
        match=re.fullmatch(r'PT(\d+)M([\d.]+)S',clock)
        if not match:
            raise ValueError('Unknown PBP clock format')
        return 60*int(match[1])+float(match[2])

    periods=defaultdict(list)
    for a in actions:
        periods[int(a['period'])].append(a)
    expected_periods=4+(game['game_minutes']-48)//5
    if set(periods)!=set(range(1,expected_periods+1)):
        raise ValueError('Incomplete period field')
    time=defaultdict(float)
    for period,events in sorted(periods.items()):
        starts=crosswalk['period_lineups'].get(str(period))
        if not starts or set(starts)!={game['home'],game['away']}:
            raise ValueError('Missing exact period-start lineups')
        on_floor={code:set(pids) for code,pids in starts.items()}
        for code,pids in on_floor.items():
            if len(pids)!=5 or any(pid not in boxes or boxes[pid]['team']!=code for pid in pids):
                raise ValueError('Invalid starting five')
        remaining=720 if period<=4 else 300
        index=0
        while index<len(events):
            a=events[index]
            clock=seconds(a['clock'])
            if clock>remaining+.001 or clock<0:
                raise ValueError('PBP clock order conflict')
            for pids in on_floor.values():
                for pid in pids:
                    time[pid]+=remaining-clock
            remaining=clock
            if a.get('actionType')=='substitution':
                batch=[]
                while index<len(events) and events[index].get('actionType')=='substitution' and events[index]['clock']==a['clock']:
                    batch.append(events[index]);index+=1
                if any(str(sub.get('subType','')).lower() not in ('in','out') for sub in batch):
                    raise ValueError('Unknown substitution direction')
                for change in ('out','in'):
                    for sub in batch:
                        if str(sub.get('subType','')).lower()!=change:
                            continue
                        pid=person(sub['personId']);code=boxes[pid]['team']
                        if change=='out':
                            if pid not in on_floor[code]:
                                raise ValueError('Substitution removes absent player')
                            on_floor[code].remove(pid)
                        else:
                            if pid in on_floor[code]:
                                raise ValueError('Substitution adds present player')
                            on_floor[code].add(pid)
                if any(len(pids)!=5 for pids in on_floor.values()):
                    raise ValueError('Substitution batch does not preserve five players')
            else:
                if a.get('actionType') in ('2pt','3pt','freethrow','rebound') and a.get('personId'):
                    pid=person(a['personId'])
                    if pid not in on_floor[boxes[pid]['team']]:
                        raise ValueError('Credited event participant is off the floor')
                if a.get('assistPersonId'):
                    aid=person(a['assistPersonId'])
                    if aid not in on_floor[boxes[aid]['team']]:
                        raise ValueError('Credited assister is off the floor')
                index+=1
        for pids in on_floor.values():
            for pid in pids:
                time[pid]+=remaining
    minute_differences=[dict(player_id=pid,event_minutes=time[pid]/60,box_minutes=p['minutes'])
                        for pid,p in boxes.items() if abs(time[pid]/60-p['minutes'])>1.01]
    result.update(lineup_agreement=not minute_differences,lineup_status='reconciled' if not minute_differences else 'minutes_mismatch',
                  minute_differences=minute_differences,derived_minutes={pid:v/60 for pid,v in time.items()})
    return result
