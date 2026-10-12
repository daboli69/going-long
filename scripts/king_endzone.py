"""Monday longest-touchdown research. Shared return events count once.

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
VERSION = 'longest-td-current-season-2'
RULE_SOURCE = 'https://dknetwork.draftkings.com/2026/02/08/draftkings-king-of-the-end-zone-best-bets-for-super-bowl-60/'



def reported_out_ids():
    """Everything the shared eligibility rules refuse (scripts/eligibility.py)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import eligibility
    return eligibility.confirmed_unavailable()


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


def monday_games(schedule, now):
    """Keep the complete Monday slate until its last kickoff + six hours.

    Never drop an already-started early game from the daily competition.
    """
    groups = defaultdict(list)
    for g in schedule:
        if not g.get('gameday') or not g.get('gametime') or g.get('game_type') not in (None, 'REG', 'POST'):
            continue
        kick = datetime.fromisoformat(f"{g['gameday']}T{g['gametime']}").replace(tzinfo=ZoneInfo('America/New_York'))
        if kick.weekday() != 0:
            continue
        groups[str(g['gameday'])].append(dict(id=g['game_id'], home=g['home_team'], away=g['away_team'], date=str(g['gameday']), kickoff=kick.isoformat()))
    for day, games in sorted(groups.items()):
        if max(datetime.fromisoformat(g['kickoff']).timestamp() for g in games) + 6*3600 > now.timestamp():
            return sorted(games, key=lambda g: g['kickoff'])
    return []


def current_games(profile, season, cutoff):
    return [g for g in profile.get('games', []) if g.get('season') == season and str(g.get('date', ''))[:10] < cutoff]


def matchup_evidence(candidate, games, context, season, as_of):
    """Descriptive current-season evidence; no unvalidated probability weights."""
    stamp = context.get('generated_at')
    try:
        age = (datetime.fromisoformat(as_of) - datetime.fromisoformat(stamp.replace('Z', '+00:00'))).total_seconds()
    except (TypeError, ValueError, AttributeError):
        age = -1
    if not 0 <= age <= 36*3600 or context.get('sources', {}).get('pbp_'+str(season), {}).get('status') != 'loaded':
        return ['Current-season matchup context is missing or stale; no matchup adjustment is applied.']
    scope = context.get('scopes', {}).get(str(season), {})
    team = candidate['team']; pos = candidate.get('position')
    game = next(g for g in games if team in (g['home'], g['away']))
    opp = game['away'] if game['home'] == team else game['home']
    lines = []
    for label, key, unit in [('Receiving', 'defense_receiving', 'targets'), ('Rushing', 'defense_rushing', 'carries')]:
        r = scope.get(key, {}).get(opp+'|'+str(pos), {})
        if r.get('games') and r.get('explosive_rate') is not None:
            lines.append(f"{opp} {label.lower()} defense vs {pos}: {100*r['explosive_rate']:.1f}% explosive-play rate across {r.get(unit, 0)} {unit}, {r['games']} current-season games. This describes all plays, not longest-TD win probability.")
    offense = scope.get('teams', {}).get(team, {})
    if offense.get('games') and offense.get('pass_over_expected') is not None:
        lines.append(f"{team} offensive tendency: {100*offense['pass_over_expected']:+.1f} percentage points pass rate above expected, {offense['games']} current-season games.")
    if offense.get('personnel_11_share') is not None:
        lines.append(f"{team} three-WR personnel share: {100*offense['personnel_11_share']:.1f}%.")
    else:
        lines.append('Verified formation/alignment data unavailable; no alignment advantage is claimed.')
    if not scope.get('defense_coverage_receiving'):
        lines.append('Verified man/zone coverage splits unavailable; no coverage-specific advantage is claimed.')
    lines.append('Matchup evidence is descriptive and does not alter the experimental probability until independently backtested.')
    return lines


def build_slate(games, profiles, roster, rows, as_of, context=None):
    import eligibility
    cutoff = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
    availability = eligibility.freshness(cutoff)
    if not availability['ok']:
        raise RuntimeError('King Endzone availability unverified: ' + availability['reason'])
    date = games[0]['date']
    season = int(games[0]['id'].split('_')[0])
    sample_cutoff = min(as_of[:10], date)
    teams = {g[k] for g in games for k in ('home', 'away')}
    historical = [r for r in rows if str(r.get('game_id', '')).startswith(str(season)+'_') and str(r.get('game_date', ''))[:10] < sample_cutoff]
    events = [e for r in historical if (e := td_event(r))]
    pools = {k: [e['distance'] for e in events if e['kind'] == k] for k in ('rush','receive','return','defense')}
    team_games = defaultdict(dict)
    for r in historical:
        for t in (r.get('home_team'), r.get('away_team')):
            if t: team_games[t][r['game_id']] = str(r['game_date'])[:10]
    windows = {t: set(sorted(g, key=g.get)[:]) for t, g in team_games.items()}
    team_exposure = sum(len(g) for g in team_games.values())
    if not team_exposure or not pools['rush'] or not pools['receive']:
        raise RuntimeError('Current-season scoring evidence unavailable')
    out_reported = eligibility.blocked_ids({r['gsis_id']: {'team': r.get('team')}
        for r in roster if r.get('gsis_id')}, now=cutoff)
    active = {r['gsis_id']: r for r in roster if r.get('gsis_id') and r.get('team') in teams and r.get('status') == 'ACT' and r['gsis_id'] not in out_reported}
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
            position=r.get('position'), uncertainty='High - unvalidated current-season scenario', evidence=[], eligible='Availability screened; sportsbook selection and game-day role require confirmation')
    for team in teams:
        dst = 'dst:'+team
        candidates[dst] = dict(id=dst, name=team+' D/ST', team=team, kind='dst', probability=None,
            uncertainty='High - rare scoring events', evidence=[], eligible='D/ST supported by published rules; current offer unverified')
        window = windows.get(team, set())
        for kind, stat in [('rush','rush_tds'),('receive','rec_tds')]:
            proposed = []
            for pid, c in candidates.items():
                if c['team'] != team or c['kind'] != 'player': continue
                p = profiles.get(pid, {})
                observations = current_games(p, season, sample_cutoff)
                if not observations or any(not isinstance(g.get(stat), (int,float)) or not math.isfinite(g[stat]) or g[stat] < 0 for g in observations): continue
                own = [e['distance'] for e in events if e['player'] == pid and e['kind'] == kind]
                rate = sum(g[stat] for g in observations)/len(observations)
                proposed.append(dict(rate=rate, dist=distance_mix(own,pools[kind]), owners=[pid], kind=kind))
                c['evidence'].append(f"{kind.title()}: {rate:.2f} TDs/game over {len(observations)} current-season appearances; {len(own)} current-season scoring distances. Distance estimate blends in five league-average scoring plays.")
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
            if not pools[kind]:
                candidates[dst]['evidence'].append(f'No current-season {kind} scoring-distance sample; this rare channel is unavailable.')
                continue
            if kind == 'return' and return_counts[team]:
                total = sum(return_counts[team].values())
                for pid, count in return_counts[team].items():
                    distances = [e['distance'] for e in events if e['player']==pid and e['kind']=='return']
                    channels.append(dict(rate=rate*count/total,dist=distance_mix(distances,pools[kind]),owners=[pid,dst],kind=kind))
                    candidates[pid]['evidence'].append(f"{count} of {total} recent returns among current roster returners; return scores also credit {team} D/ST. Current return assignment is unconfirmed.")
            elif pools[kind]:
                channels.append(dict(rate=rate,dist=distance_mix(own,pools[kind]),owners=[dst],kind=kind))
    chance, no_td = probabilities(channels)
    for pid,c in candidates.items():
        c['probability'] = chance.get(pid)
        owned = [x for x in channels if pid in x['owners']]
        c['td_probability'] = 1-math.exp(-sum(x['rate'] for x in owned)) if owned else None
        c['evidence'].append('Team scoring rates limit the combined player estimates. No additional opponent, weather or role adjustment is claimed in this initial version.')
        if c['kind'] == 'player': c['evidence'].extend(matchup_evidence(c, games, context or {}, season, as_of))
        if not owned: c['evidence'].append('Not enough published participation history to estimate this player. Unassigned team scoring remains in the competition.')
    ranked = sorted(candidates.values(),key=lambda c: -(c['probability'] if c['probability'] is not None else -1))
    ranked.append(dict(id='no_td',name='No Touchdown Scorer',team='Slate',kind='no_td',probability=no_td,td_probability=None,
        uncertainty='High - unvalidated model',eligible='Supported by supplied offer terms',evidence=['Wins only when neither team scores a touchdown. Field goals, safeties and extra points are not touchdowns.']))
    ranked.sort(key=lambda c: -(c['probability'] if c['probability'] is not None else -1))
    for rank,c in enumerate(ranked,1): c['rank']=rank
    return dict(date=date,games=games,candidates=ranked,no_td_probability=no_td,generated_at=as_of,model_version=VERSION,
        season=season, sample_policy='Current season only; league shrinkage uses this season', eligibility_status='Monday research slate; current promotion game list and selectable field not verified',
        rule_source=RULE_SOURCE,other_scorer_probability={k:v for k,v in chance.items() if k.startswith('other:')})


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT/"data/king-endzone.json")
    parser.add_argument("--archive-dir", type=Path, default=ROOT/"data/jackpot/king-endzone")
    parser.add_argument("--no-archive", action="store_true", help="Isolated validation: no write-once forecast writes")
    args=parser.parse_args()
    import nflreadpy as nfl
    import polars as pl
    from build_pipeline import atomic_json
    now=datetime.now(timezone.utc);as_of=now.isoformat();year=now.year if now.month >= 3 else now.year-1
    history=json.loads((ROOT/'data/history.json').read_text(encoding='utf-8'))['betting']
    try:
        history_age=(now-datetime.fromisoformat(history['generated_at'].replace('Z','+00:00'))).total_seconds()
    except (KeyError, TypeError, ValueError):
        history_age=-1
    if not 0 <= history_age <= 36*3600 or history.get('sources',{}).get('nflreadpy',{}).get(str(year)) != 'loaded':
        raise RuntimeError('King current-season player history is stale, unavailable or unverified')
    schedule=nfl.load_schedules([year]).to_dicts()
    upcoming=monday_games(schedule, now)
    columns=['game_id','game_date','home_team','away_team','posteam','touchdown','play_type','play_deleted','two_point_attempt','td_team','td_player_id','pass_touchdown','kickoff_attempt','punt_attempt','yards_gained','return_yards','return_team','kickoff_returner_player_id','punt_returner_player_id','fumble','fumble_recovery_1_team','fumble_recovery_1_yards','fumble_recovery_2_team','fumble_recovery_2_yards','game_seconds_remaining','qtr']
    frames=[nfl.load_pbp([year]).select(columns)]
    rows=pl.concat(frames,how='diagonal_relaxed').to_dicts()
    roster=nfl.load_rosters([year]).to_dicts()
    offer=json.loads((ROOT/'config/king-endzone.json').read_text())
    date=upcoming[0]['date'] if upcoming else None
    context=json.loads((ROOT/'data/football_context.json').read_text(encoding='utf-8'))
    archive=args.archive_dir
    if not args.no_archive: archive.mkdir(parents=True,exist_ok=True)
    closed=bool(upcoming) and any(datetime.fromisoformat(g['kickoff']) <= now for g in upcoming)
    if closed:
        path=archive/(date+'.json')
        slate=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    else:
        slate=build_slate(upcoming,history['profiles'],roster,rows,as_of,context) if date else None
    if slate and not closed:
        slate['offer']=dict(offer, cutoff=min(g['kickoff'] for g in upcoming))
        slate['history_generated_at']=history.get('generated_at')
    if not args.no_archive and slate and not closed:
        # First published forecast stays immutable; never backfill a past slate.
        path=archive/(date+'.json')
        if not path.exists():
            with path.open('x',encoding='utf-8') as out: json.dump(slate,out,separators=(',',':'),allow_nan=False)
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
    atomic_json(args.output,dict(generated_at=as_of,slate=slate,offer=offer,results=results))


if __name__=='__main__': main()
