"""Thursday longest-touchdown research. Shared return events count once.

Marked Poisson scoring channels + empirical distance distributions. This is an
unvalidated baseline, not an estimate of the promotion's monetary value.
"""
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'longest-td-1'
RULE_SOURCE = 'https://dknetwork.draftkings.com/2026/02/08/draftkings-king-of-the-end-zone-best-bets-for-super-bowl-60/'


def probabilities(channels):
    """Probability of sharing the longest score, including exact-distance ties.

    Owners can overlap: one return channel belongs to its returner AND D/ST.
    Do not normalize selection probabilities: they are not mutually exclusive.
    """
    owners = set(o for c in channels for o in c['owners'])
    tails = []
    for c in channels:
        dist = c['dist']
        assert c['rate'] >= 0 and abs(sum(dist.values()) - 1) < 1e-8
        tails.append([c['rate'] * sum(p for x, p in dist.items() if int(x) > d) for d in range(-1, 110)])
    total = [sum(t[d] for t in tails) for d in range(111)]
    result = {}
    for owner in owners:
        own = [sum(t[d] for c, t in zip(channels, tails) if owner in c['owners']) for d in range(111)]
        result[owner] = sum((math.exp(-own[d+1]) - math.exp(-own[d])) * math.exp(-(total[d+1]-own[d+1])) for d in range(110))
    return result, math.exp(-total[0])


def td_event(r):
    if r.get('touchdown') != 1 or (r.get('no_play') == 1 or r.get('play_type') == 'no_play' or r.get('play_deleted') == 1) or r.get('two_point_attempt') == 1:
        return None
    team, player = r.get('td_team'), r.get('td_player_id')
    if not team:
        return None
    if r.get('kickoff_attempt') == 1 or r.get('punt_attempt') == 1:
        kind, distance = 'return', r.get('return_yards')
    elif team != r.get('posteam'):
        kind, distance = 'defense', r.get('return_yards')
        if r.get('fumble') == 1:
            distance = next((r.get(f'fumble_recovery_{i}_yards') for i in (1, 2) if r.get(f'fumble_recovery_{i}_team') == team), distance)
    else:
        kind = 'receive' if r.get('pass_touchdown') == 1 else 'rush'
        distance = r.get('yards_gained')
    if not isinstance(distance, (int, float)) or not math.isfinite(distance) or not 0 <= distance <= 109:
        return None
    return dict(team=team, player=player, kind=kind, distance=int(distance), game=r['game_id'], date=str(r['game_date'])[:10])


def distance_mix(own, pool, prior=5):
    if not pool:
        raise ValueError('Historical touchdown-distance pool is unavailable')
    counts = Counter(own)
    league = Counter(pool)
    return {d: (counts[d] + prior*n/len(pool))/(len(own)+prior) for d, n in league.items()} | {
        d: n/(len(own)+prior) for d, n in counts.items() if d not in league}


def build_slate(games, profiles, roster, rows, as_of):
    date = games[0]['date']
    teams = {g[k] for g in games for k in ('home', 'away')}
    historical = [r for r in rows if str(r.get('game_date', ''))[:10] < as_of[:10]]
    events = [e for r in historical if (e := td_event(r))]
    pools = {k: [e['distance'] for e in events if e['kind'] == k] for k in ('rush','receive','return','defense')}
    team_games = defaultdict(dict)
    for r in historical:
        for t in (r.get('home_team'), r.get('away_team')):
            if t: team_games[t][r['game_id']] = str(r['game_date'])[:10]
    windows = {t: set(sorted(g, key=g.get)[-12:]) for t, g in team_games.items()}
    team_exposure = sum(len(g) for g in team_games.values())
    active = {r['gsis_id']: r for r in roster if r.get('gsis_id') and r.get('team') in teams and r.get('status') == 'ACT'}
    return_counts = defaultdict(Counter)
    for r in historical:
        team = r.get('return_team')
        if team not in teams or r['game_id'] not in windows.get(team, set()): continue
        pid = r.get('kickoff_returner_player_id') or r.get('punt_returner_player_id')
        if pid in active and active[pid]['team'] == team: return_counts[team][pid] += 1
    candidates, channels = {}, []
    for pid, r in active.items():
        if r.get('position') not in ('QB','RB','FB','WR','TE') and not return_counts[r['team']][pid]: continue
        candidates[pid] = dict(id=pid, name=r['full_name'], team=r['team'], kind='player', probability=None,
            uncertainty='High — unvalidated model', evidence=[], eligible='Thursday roster; offer selection not verified')
    for team in teams:
        dst = 'dst:'+team
        candidates[dst] = dict(id=dst, name=team+' D/ST', team=team, kind='dst', probability=None,
            uncertainty='High — rare scoring events', evidence=[], eligible='D/ST supported by published rules; current offer unverified')
        window = windows.get(team, set())
        for kind, stat in [('rush','rush_tds'),('receive','rec_tds')]:
            proposed = []
            for pid, c in candidates.items():
                if c['team'] != team or c['kind'] != 'player': continue
                p = profiles.get(pid, {})
                fit = p.get('stats', {}).get(stat, {})
                if fit.get('status') != 'ready' or fit.get('mean') is None: continue
                own = [e['distance'] for e in events if e['player'] == pid and e['kind'] == kind]
                rate = max(0, fit['mean'])
                proposed.append(dict(rate=rate, dist=distance_mix(own,pools[kind]), owners=[pid], kind=kind))
                c['evidence'].append(f"{kind.title()}: {rate:.2f} TDs/game over {fit['n']} recorded games; {len(own)} historical scoring distances. Distance estimate blends in five league-average scoring plays.")
            observed = sum(e['team']==team and e['kind']==kind and e['game'] in window for e in events)
            league = sum(e['kind']==kind for e in events)/team_exposure
            team_rate = (observed + 8*league)/(len(window)+8)
            raw = sum(c['rate'] for c in proposed)
            for c in proposed: c['rate'] *= min(1, team_rate/raw) if raw else 1
            channels.extend(proposed)
            remaining = max(0, team_rate-sum(c['rate'] for c in proposed))
            if remaining: channels.append(dict(rate=remaining,dist=distance_mix([],pools[kind]),owners=['other:'+team],kind=kind))
        for kind in ('return','defense'):
            own = [e['distance'] for e in events if e['team']==team and e['kind']==kind and e['game'] in window]
            league = sum(e['kind']==kind for e in events)/team_exposure
            rate = (len(own)+8*league)/(len(window)+8)
            candidates[dst]['evidence'].append(f"{kind.title()}: {len(own)} TDs in {len(window)} team games; scoring rate blended with eight league-average team games.")
            if kind == 'return' and return_counts[team]:
                total = sum(return_counts[team].values())
                for pid, count in return_counts[team].items():
                    distances = [e['distance'] for e in events if e['player']==pid and e['kind']=='return']
                    channels.append(dict(rate=rate*count/total,dist=distance_mix(distances,pools[kind]),owners=[pid,dst],kind=kind))
                    candidates[pid]['evidence'].append(f"{count} of {total} recent returns among current roster returners; return scores also credit {team} D/ST. Current return assignment is unconfirmed.")
            else:
                channels.append(dict(rate=rate,dist=distance_mix(own,pools[kind]),owners=[dst],kind=kind))
    chance, no_td = probabilities(channels)
    for pid,c in candidates.items():
        c['probability'] = chance.get(pid)
        owned = [x for x in channels if pid in x['owners']]
        c['td_probability'] = 1-math.exp(-sum(x['rate'] for x in owned)) if owned else None
        c['evidence'].append('Team scoring rates limit the combined player estimates. No additional opponent, weather or role adjustment is claimed in this initial version.')
        if not owned: c['evidence'].append('Not enough published participation history to estimate this player. Unassigned team scoring remains in the competition.')
    ranked = sorted(candidates.values(),key=lambda c: -(c['probability'] if c['probability'] is not None else -1))
    ranked.append(dict(id='no_td',name='No Touchdown Scorer',team='Slate',kind='no_td',probability=no_td,td_probability=None,
        uncertainty='High — unvalidated model',eligible='Supported by supplied offer terms',evidence=['Wins only when neither team scores a touchdown. Field goals, safeties and extra points are not touchdowns.']))
    ranked.sort(key=lambda c: -(c['probability'] if c['probability'] is not None else -1))
    for rank,c in enumerate(ranked,1): c['rank']=rank
    return dict(date=date,games=games,candidates=ranked,no_td_probability=no_td,generated_at=as_of,model_version=VERSION,
        eligibility_status='Thursday research slate; current promotion game list and selectable field not verified',
        rule_source=RULE_SOURCE,other_scorer_probability={k:v for k,v in chance.items() if k.startswith('other:')})


def main():
    import nflreadpy as nfl
    import polars as pl
    from build_pipeline import atomic_json
    now=datetime.now(timezone.utc);as_of=now.isoformat();year=now.year
    history=json.loads((ROOT/'data/history.json').read_text(encoding='utf-8'))['betting']
    schedule=nfl.load_schedules([year]).to_dicts()
    upcoming=[]
    for g in schedule:
        if not g.get('gameday') or not g.get('gametime'): continue
        kick=datetime.fromisoformat(f"{g['gameday']}T{g['gametime']}").replace(tzinfo=ZoneInfo('America/New_York'))
        if kick.weekday()==3 and kick>now:
            upcoming.append(dict(id=g['game_id'],home=g['home_team'],away=g['away_team'],date=str(g['gameday']),kickoff=kick.isoformat()))
    columns=['game_id','game_date','home_team','away_team','posteam','touchdown','play_type','play_deleted','two_point_attempt','td_team','td_player_id','pass_touchdown','kickoff_attempt','punt_attempt','yards_gained','return_yards','return_team','kickoff_returner_player_id','punt_returner_player_id','fumble','fumble_recovery_1_team','fumble_recovery_1_yards','fumble_recovery_2_team','fumble_recovery_2_yards','game_seconds_remaining','qtr']
    frames=[nfl.load_pbp([y]).select(columns) for y in range(year-2,year+1)]
    rows=pl.concat(frames,how='diagonal_relaxed').to_dicts()
    roster=nfl.load_rosters([year]).to_dicts()
    offer=json.loads((ROOT/'config/king-endzone.json').read_text())
    upcoming=[g for g in upcoming if g['date']==offer['date'] and {g['home'],g['away']}==set(offer['teams'])]
    date=min((g['date'] for g in upcoming),default=None)
    slate=build_slate([g for g in upcoming if g['date']==date],history['profiles'],roster,rows,as_of) if date else None
    if slate:
        slate['offer']=offer
        slate['history_generated_at']=history.get('generated_at')
        slate['eligibility_status']='Game and scoring rules confirmed from supplied offer terms; individual sportsbook selections and game-day roles require confirmation.'
    archive=ROOT/'data/jackpot/king-endzone';archive.mkdir(parents=True,exist_ok=True)
    if slate:
        # First published forecast stays immutable; never backfill a past slate.
        path=archive/(date+'.json')
        if not path.exists():
            with path.open('x',encoding='utf-8') as out: json.dump(slate,out,separators=(',',':'),allow_nan=False)
    if not slate and (archive/(offer['date']+'.json')).exists():
        slate=json.loads((archive/(offer['date']+'.json')).read_text())
    results=[]
    for path in archive.glob('*.json'):
        frozen=json.loads(path.read_text());ids={g['id'] for g in frozen['games']}
        matches=[g for g in schedule if g.get('game_id') in ids]
        if len(matches)!=len(ids) or any(g.get('home_score') is None or g.get('away_score') is None for g in matches): continue
        if any(datetime.fromisoformat(g['kickoff']).timestamp()+12*3600>now.timestamp() for g in frozen['games']): continue
        game_rows=[r for r in rows if r.get('game_id') in ids]
        if any(not any(r['game_id']==gid and r.get('game_seconds_remaining')==0 and (r.get('qtr') or 0)>=4 for r in game_rows) for gid in ids): continue
        scores=[e for r in game_rows if (e:=td_event(r))]
        raw_tds=[r for r in game_rows if r.get('touchdown')==1 and r.get('play_type')!='no_play' and r.get('play_deleted')!=1 and r.get('two_point_attempt')!=1]
        if len(scores)!=len(raw_tds): continue
        longest=max((e['distance'] for e in scores),default=None);winners=set() if scores else {'no_td'}
        for e in scores:
            if e['distance']!=longest: continue
            if e['player']: winners.add(e['player'])
            if e['kind'] in ('return','defense'): winners.add('dst:'+e['team'])
        results.append(dict(date=frozen['date'],longest_yards=longest,winners=sorted(winners),model_version=frozen['model_version'],
            predictions=[dict(id=c['id'],probability=c['probability'],won=c['id'] in winners) for c in frozen['candidates']],
            status='Research outcome; promotion settlement not verified'))
    atomic_json(ROOT/'data/king-endzone.json',dict(generated_at=as_of,slate=slate,offer=offer,results=results))


if __name__=='__main__': main()
