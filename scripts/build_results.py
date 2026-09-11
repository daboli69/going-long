"""Public settlement observations, kept separate from pregame model inputs.

Never infer a zero for a player absent from the appearance-aware profile logs.
Periods, first scorer and participation/void rules require manual settlement.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from build_pipeline import atomic_json, normalize_games, finite

ROOT = Path(__file__).resolve().parents[1]


def assemble(games, profiles, previous=None, now=None):
    now = now or datetime.now(timezone.utc)
    output = dict((previous or {}).get('games', {}))
    for g in games:
        kickoff = datetime.fromisoformat(g['kickoff'].replace('Z', '+00:00'))
        if not g['completed'] or (now - kickoff).total_seconds() < 12 * 3600:
            continue
        key = f"{g['sport']}|{g['id']}"
        output[key] = {k: g[k] for k in ('sport', 'id', 'home', 'away', 'kickoff', 'homeScore', 'awayScore')}
    players = dict((previous or {}).get('players', {}))
    for pid, profile in profiles.items():
        for row in profile.get('games', []):
            if row['date'] >= now.date().isoformat():
                continue
            stats = {k: v for k, v in row.items() if k not in ('season', 'week', 'date') and finite(v)}
            if stats:
                players[pid + '|' + row['date']] = stats
    return {'schema_version': 1, 'generated_at': now.isoformat(), 'games': output, 'players': players,
            'limitations': 'Full-game only. Player values require published appearance-aware logs. Book void rules and First TD/period settlements require manual confirmation.'}


def build():
    import nflreadpy as nfl
    import sportsdataverse.cfb as cfb
    path = ROOT / 'data/results.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    season = int(os.getenv('SEASON', datetime.now().year))
    games, sources = [], {}
    for sport, loader in [('nfl', nfl.load_schedules), ('ncaa', cfb.load_cfb_schedule)]:
        try:
            games.extend(normalize_games(loader([season]).to_dicts(), sport))
            sources[sport] = {'status': 'loaded', 'checked_at': datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            sources[sport] = {'status': 'unavailable', 'reason': type(exc).__name__, 'retained_previous': True}
    history = json.loads((ROOT / 'data/history.json').read_text())['betting']
    result = assemble(games, history['profiles'], previous)
    result['sources'] = sources
    result['player_source_at'] = history['generated_at']
    atomic_json(path, result)
    print(f"Results: {len(result['games'])} finals, {len(result['players'])} player appearances; {sources}")


if __name__ == '__main__':
    build()
