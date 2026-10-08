"""Prospective weekly trend capture (2026 onward).

Each Tuesday's live Fantasy Points snapshot is season-to-date. Differencing two CONSECUTIVE live snapshots (through games g-1 and g) recovers
what happened in week g alone for every COUNT metric (routes, targets, receptions, carries, snaps, expected fantasy points). From those this
module stores, once and never rewritten:

  * the week's own usage per player: routes, route share of team routes, targets, targets per route run, target share of team targets,
    carries, snaps, expected fantasy points
  * how that compares with the player's season-to-date baseline BEFORE the week (the "what changed" signal) and, when available, with the
    previous week's own usage

A trend file is a pure function of the two snapshots, carries the later snapshot's known-at time, and is written write-once: a later
revision of a snapshot produces a separate `__revision-<sha12>` file, never an edit. Nothing here uses any game outcome beyond the snapshots.
"""
import hashlib
import json
from pathlib import Path

from .store import GOOD, Manifest, write_json

# table -> {output name: 'Group.COLUMN' count metric}
COUNT_METRICS = {
    'receiving_routes_run': {'routes': 'Overall.RTE', 'targets': 'Overall.TGT', 'wide_routes': 'Wide.RTE', 'slot_routes': 'Slot.RTE',
                             'inline_routes': 'Inline.RTE', 'backfield_routes': 'Backfield.RTE'},
    'receiving_advanced': {'first_read_targets': 'Advanced.1READ', 'designed_targets': 'Advanced.DESIGN', 'air_yards': 'Receiving.AY',
                           'end_zone_targets': 'Advanced.EZTGT', 'xfp': 'FPTS.XFP'},
    'rushing_bell_cow': {'snaps': 'Snaps.Snaps', 'carries': 'Rushing.ATT', 'rb_routes': 'Receiving.RTE', 'rb_targets': 'Receiving.TGT', 'rb_xfp': 'FPTS.XFP'},
    'offense_snaps': {'snaps_total': 'Total.Snaps', 'snaps_inside_5': 'Inside 5.Snaps', 'snaps_inside_10': 'Inside 10.Snaps', 'snaps_inside_20': 'Inside 20.Snaps'},
}
TEAM_TABLES = {'run_pass_report': {'plays': 'Overall.SNAPS', 'pass_plays': 'Overall.PASS', 'rush_plays': 'Overall.RUSH'}}
MIN_ROUTES_FOR_RATE = 10


def _load(root, entry):
    return json.loads((Path(root) / entry['normalized_path']).read_text(encoding='utf-8'))


def _players(doc, columns):
    out = {}
    for row in doc['rows']:
        entity = row['entity']
        pid = entity.get('player_id')
        if not pid or entity.get('split_entity'):
            continue
        out[pid] = {'games': row['context'].get('games'), 'team': entity.get('team'), 'pos': entity.get('position'),
                    **{name: row['metrics'].get(col) for name, col in columns.items()}}
    return out


def live_snapshots(manifest, season, table_id):
    """{through_games: entry}, live captures only, current revision per week."""
    found = {}
    for entry in manifest.entries(season, table_id):
        if entry.get('scope') == 'season_to_date' and entry.get('known_live') and not entry.get('superseded_by'):
            found[entry['through_games']] = entry
    return found


def weekly_usage(root, manifest, season, game):
    """Week-`game` usage for every player in the tables that have BOTH consecutive snapshots (game-1 and game), or None."""
    out = {}
    sources = {}
    for table_id, columns in COUNT_METRICS.items():
        snaps = live_snapshots(manifest, season, table_id)
        if game not in snaps or (game - 1) not in snaps:
            continue
        now, before = _players(_load(root, snaps[game]), columns), _players(_load(root, snaps[game - 1]), columns)
        sources[table_id] = {'now': snaps[game]['sha256'], 'before': snaps[game - 1]['sha256']}
        for pid, current in now.items():
            previous = before.get(pid)
            record = out.setdefault(pid, {'team': current['team'], 'pos': current['pos']})
            if previous is None:
                record.setdefault('new_in_table', []).append(table_id)  # first appearance: no weekly difference can be computed
                continue
            if (current['games'] or 0) <= (previous['games'] or 0):
                record.setdefault('did_not_play', []).append(table_id)  # no new game recorded: bye, inactive or injured (not distinguishable here)
                continue
            for name in columns:
                a, b = current.get(name), previous.get(name)
                if a is not None and b is not None:
                    record.setdefault('week', {})[name] = round(a - b, 4)
                    record.setdefault('before', {})[name] = b
                    record.setdefault('games_before', {})[table_id] = previous['games']
    return out, sources


def derive(usage):
    """Rates from the weekly counts: route share needs the team's routes, which come from teammates' weekly routes (sum over the team)."""
    team_routes, team_targets = {}, {}
    for pid, rec in usage.items():
        w = rec.get('week', {})
        if rec.get('team') and 'routes' in w and rec['team'] is not None:
            # a team's weekly route total is approximated by its busiest pass-catcher's routes (every WR1 runs a route on nearly every dropback)
            team_routes[rec['team']] = max(team_routes.get(rec['team'], 0), w['routes'])
            team_targets[rec['team']] = team_targets.get(rec['team'], 0) + (w.get('targets') or 0)
    for pid, rec in usage.items():
        w = rec.get('week', {})
        if 'routes' in w:
            derived = {'tprr_week': round(w['targets'] / w['routes'], 4) if w['routes'] >= MIN_ROUTES_FOR_RATE and w.get('targets') is not None else None}
            team = rec.get('team')
            if team and team_routes.get(team):
                derived['route_share_week'] = round(w['routes'] / team_routes[team], 4)
            if team and team_targets.get(team):
                derived['target_share_week'] = round((w.get('targets') or 0) / team_targets[team], 4)
            b = rec.get('before', {})
            gb = (rec.get('games_before') or {}).get('receiving_routes_run')
            if gb and b.get('routes') and w['routes'] >= MIN_ROUTES_FOR_RATE:
                derived['routes_vs_season_avg'] = round(w['routes'] - b['routes'] / gb, 2)
                if b.get('targets') is not None and w.get('targets') is not None:
                    derived['targets_vs_season_avg'] = round(w['targets'] - b['targets'] / gb, 2)
                derived['tprr_before'] = round(b['targets'] / b['routes'], 4) if b['routes'] else None
            rec['derived'] = derived
    return usage


def build_trend(root, manifest, season, game):
    usage, sources = weekly_usage(root, manifest, season, game)
    if not usage:
        return None
    usage = derive(usage)
    known = []
    for table_id, shas in sources.items():  # a state is knowable only once BOTH snapshots it was derived from had been imported (a corrected earlier week counts)
        known.append(manifest.files[shas['now']]['first_imported_at'])
        known.append(manifest.files[shas['before']]['first_imported_at'])
    from . import trend_labels  # imported here: trend_labels reads snapshots through this module
    environment, env_sources = trend_labels.team_environment(root, manifest, season, game)
    matchup, matchup_sources = trend_labels.matchup_context(root, manifest, season, game)
    for table_id, shas in env_sources.items():
        sources[table_id] = shas
        known.append(manifest.files[shas['now']]['first_imported_at'])
        known.append(manifest.files[shas['before']]['first_imported_at'])
    for table_id, sha in matchup_sources.items():
        sources[table_id] = {'now': sha}
        known.append(manifest.files[sha]['first_imported_at'])
    for record in usage.values():
        record['labels'] = trend_labels.detect(record)
    return {'schema': 'fp-trend-state-v2', 'season': season, 'through_games': game, 'prev_through_games': game - 1, 'known_at': max(known),
            'sources': sources, 'players': usage, 'team_environment': environment, 'matchup_known_before_game': matchup,
            'labels_note': 'labels are descriptive evidence only: not model inputs, rating bonuses or bet triggers until prospective evidence validates them',
            'note': 'weekly usage = difference of two consecutive live season-to-date snapshots; team environment likewise from the run/pass report; matchup context = what the forward-looking tables said when this snapshot was imported; route share uses the busiest teammate\'s routes as the team total; '
                    'no game outcome beyond the snapshots is used; this file is write-once'}


def capture(root, season, manifest=None):
    """Write every missing trend state for `season`. Returns the list of files written. Existing files are never edited."""
    root = Path(root)
    manifest = manifest or Manifest(root)
    games = sorted({g for t in COUNT_METRICS for g in live_snapshots(manifest, season, t)})
    written = []
    for game in games[1:]:
        state = build_trend(root, manifest, season, game)
        if state is None:
            continue
        digest = hashlib.sha256(json.dumps(state, sort_keys=True).encode('utf-8')).hexdigest()[:12]
        target = root / 'trends' / str(season) / f'through-week-{game:02d}.json'
        if target.exists():
            existing = json.loads(target.read_text(encoding='utf-8'))
            if json.dumps(existing, sort_keys=True) == json.dumps(state, sort_keys=True):
                continue
            target = target.with_name(f'through-week-{game:02d}__revision-{digest}.json')
            if target.exists():
                continue
        write_json(target, state)
        written.append(target.relative_to(root).as_posix())
    return written
