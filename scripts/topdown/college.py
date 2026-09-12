"""Exact, ambiguity-rejecting aliases from ESPN's public team catalog."""
import json
from pathlib import Path
import re
import unicodedata


def key(name):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',str(name)).encode('ascii','ignore').decode().lower())


CATALOG=json.loads((Path(__file__).resolve().parents[2]/'config/ncaa-teams.json').read_text())['teams']
ALIASES={};TEAMS={t['id']:t for t in CATALOG}
for team in CATALOG:
    for field in ('displayName','shortDisplayName','location','abbreviation'):
        if team.get(field):ALIASES.setdefault(key(team[field]),set()).add(team['id'])


def team_id(name):
    found=ALIASES.get(key(name),set())
    return next(iter(found)) if len(found)==1 else None


def canonical(name):
    found=team_id(name)
    return TEAMS[found]['displayName'] if found else None
