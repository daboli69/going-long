#!/usr/bin/env python3
"""Publish the NFL game-line board (moneyline, spread, total) as its own snapshot, independent of player-prop coverage.

Why: one truncated props scope (provider read-window limit) marks all of data/nfl_betting.json FALLBACK, and the publication guard then withholds the whole file,
including game lines that the same run fetched successfully. This script adds NO provider request. It reads the file the nfl step just wrote and publishes
data/nfl_game_lines.json only when the ODDS source itself is FRESH and was observed within MAX_AGE_HOURS. Otherwise it writes nothing and exits 1 (fail closed).
The strict health checks on nfl_betting.json are unchanged: a degraded props scope still makes the refresh unhealthy and keeps nfl_betting.json out of publication.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'nfl_betting.json'
TARGET = ROOT / 'data' / 'nfl_game_lines.json'
MAX_AGE_HOURS = 6
SCHEMA = 'going-game-lines-v1'
GAME_FIELDS = ('game_id', 'season', 'week', 'away', 'home', 'kickoff', 'gametime', 'spread', 'total', 'away_ml', 'home_ml', 'over_odds', 'under_odds',
               'away_spread_odds', 'home_spread_odds', 'away_score', 'home_score', 'completed')


class Refused(RuntimeError):
    pass


def parse(value):
    try:
        moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment if moment.tzinfo else None


def build(doc, now, max_age_hours=MAX_AGE_HOURS):
    """Returns the payload, or raises Refused with the exact reason. Pure function (no I/O)."""
    if not isinstance(doc, dict) or doc.get('sport') != 'nfl':
        raise Refused('source is not the NFL board')
    states = doc.get('source_states') if isinstance(doc.get('source_states'), dict) else {}
    if states.get('odds') != 'FRESH':
        raise Refused(f"odds source is {states.get('odds', 'UNKNOWN')}, not FRESH")
    observed = parse((doc.get('source_observed_at') or {}).get('odds'))
    if observed is None:
        raise Refused('odds observation time missing or without a timezone')
    age = (now - observed).total_seconds() / 3600
    if age < -0.5:
        raise Refused('odds observation time is in the future')
    if age > max_age_hours:
        raise Refused(f'odds observation is {age:.1f} h old (limit {max_age_hours} h)')
    games = doc.get('games')
    if not isinstance(games, list) or not games:
        raise Refused('no games in the source board')
    rows = [{k: g.get(k) for k in GAME_FIELDS} for g in games if isinstance(g, dict) and g.get('game_id')]
    return {'schema': SCHEMA, 'provider': doc.get('provider'), 'sport': 'nfl', 'generated_at': observed.isoformat(), 'source': 'data/nfl_betting.json',
            'odds_state': 'FRESH', 'props_state': states.get('props'), 'derivatives_state': states.get('derivatives'),
            'note': 'game lines only; fresh when odds is FRESH even if player-prop coverage is degraded (see nfl_betting.json for the full-board status)',
            'games': rows}


def publish(source=SOURCE, target=TARGET, now=None):
    now = now or datetime.now(timezone.utc)
    payload = build(json.loads(Path(source).read_text(encoding='utf-8')), now)
    target = Path(target)
    if target.exists():
        try:
            if json.loads(target.read_text(encoding='utf-8')) == payload:
                return 'unchanged'
        except ValueError:
            pass
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=1, sort_keys=True)
        f.write('\n')
    os.replace(tmp, target)
    return 'written'


def main():
    try:
        print(publish())
    except (Refused, OSError, ValueError) as exc:
        print(f'game lines not published: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
