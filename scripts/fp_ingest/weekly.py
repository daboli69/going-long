"""Private weekly model inputs. Folder N prepares week N; weekly rows describe N-1.

No licensed value is written outside FantasyPoints. This is feature ingestion,
not model promotion. Content and known-at receipts remain independently auditable.
"""
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path

from .parse import parse_export, to_number
from .registry import classify
from .store import find_inbox, inbox_files, write_json, atomic_write

WEEKLY = {'receiving_advanced', 'receiving_routes_run', 'rushing_bell_cow',
          'rushing_advanced', 'efficiency', 'run_pass_report', 'team_offense', 'separation_routes', 'receiving_separation_by_routes'}


def kind_of(parsed, registry):
    known = classify(registry, '', parsed).get('table_id')
    if known:
        return known
    h = set(parsed['headers'])
    g = set(parsed['groups'] or [])
    # Signatures, not download suffixes, identify each new 2.0 feature family.
    signatures = [
        ('rushing_bell_cow', {'BACKFIELD XFP %', 'TM RB XFP'}),
        ('efficiency', {'XFP/G', 'XFP %', 'RuXFP', 'ReXFP'}),
        ('receiving_advanced', {'1READ %', 'RTE %', 'RecXFP'}),
        ('rushing_advanced', {'RYOE', 'ZONE SUCC %', 'YACO/ATT'}),
        ('separation_routes', {'SEP SCORE', 'ADOR', 'RTE %'}),
        ('separation_coverage', {'SEP SCORE', 'ADOR', '+3 Rate'}),
        ('passing_advanced', {'QBSK', 'TTT', 'P2S %'}),
        ('passing_depth', {'HERO', 'TWT', 'ACC %'}),
        ('passing_situation', {'EPA/DB', 'FP/DB', 'YPA'}),
        ('coverage_matrix', {'COVER 6 %', 'DISGUISE %'}),
        ('pace', {'PACE LEAD', 'PACE NEU', 'PL/DR'}),
        ('offensive_line_units', {'Unit', 'MEN', 'YBC/A'}),
        ('coach_records', {'COACH', 'ROLE', 'WIN %'}),
    ]
    for name, required in signatures:
        if required <= h:
            return name
    if 'PLAYCALLER' in h or ('Coach' in g and 'PROE' in h):
        return 'playcaller'
    if {'EPA/DR', 'PASS SUCC %', 'RUSH SUCC %'} <= h:
        return 'team_defense' if 'Coverage' in g else 'team_offense'
    if {'OUTER', 'SLOT'} <= g:
        return 'receiving_alignment_allowed'
    if 'TEAM DETAILS' in g and 'POS' in h and 'FP/G' in h:
        return 'position_points_allowed'
    return None


def receipt_time(parsed):
    for note in parsed['notes']:
        m = re.search(r'on (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC', note)
        if m:
            return dt.datetime.strptime(m[1], '%Y-%m-%d %H:%M').replace(tzinfo=dt.timezone.utc)
    return None


def inspect_file(path, inbox, registry, season, week, now, first_seen):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rel = str(path.relative_to(inbox))
    info = {'path': rel, 'sha256': digest, 'known_at': first_seen.get(digest, now.isoformat()), 'status': 'held'}
    parsed = parse_export(data)
    kind = kind_of(parsed, registry)
    if not kind:
        return {**info, 'problem': 'Unsupported column signature'}, None
    headers, columns = parsed['headers'], parsed['columns']
    season_ix = next((i for i, x in enumerate(headers) if x.lower() == 'season'), None)
    name_ix = next((i for i, x in enumerate(headers) if x.lower() in {'name', 'coach', 'unit', 'team'}), None)
    rank_ix = next((i for i, x in enumerate(headers) if x.lower() == 'rank'), None)
    summary_rows, detail_rows = [], []
    for row in parsed['rows']:
        label = row[name_ix].strip().lower() if name_ix is not None else ''
        aggregate = (not label or label in {'league avg', 'league average'}) and rank_ix is not None and not row[rank_ix]
        (summary_rows if aggregate else detail_rows).append(row)
    years = set()
    if season_ix is not None:
        values = [to_number(row[season_ix]) for row in detail_rows]
        if not values or any(x is None or not math.isfinite(x) or x != int(x) for x in values):
            return {**info, 'problem': 'Invalid explicit season'}, None
        years = {int(x) for x in values}
    folder = next((re.fullmatch(r'week\s+(\d+)', part, re.I) for part in path.relative_to(inbox).parts[:-1]
                   if re.fullmatch(r'week\s+(\d+)', part, re.I)), None)
    target = int(folder[1]) if folder else None
    info.update(table=kind, season=next(iter(years)) if len(years) == 1 else None, for_week=target)
    if len(years) > 1:
        return {**info, 'problem': 'Mixed seasons'}, None
    exported = receipt_time(parsed)
    if season_ix is None and folder and exported and exported.year == season:
        info['season'] = season  # User declared new weekly-folder exports current-season.
        info['season_source'] = 'operator_folder_and_export_receipt'
    if info['season'] != season:
        return {**info, 'problem': 'Not current-season evidence'}, None
    if target is not None and (target != week or not 1 <= target <= 18):
        return {**info, 'problem': 'Folder is not the current prediction week'}, None
    if not exported or exported > now or now - exported > dt.timedelta(days=8):
        return {**info, 'problem': 'Missing, future or old export receipt'}, None
    games_ix = next((i for i, x in enumerate(headers) if x.upper() == 'G'), None)
    games = [to_number(row[games_ix]) for row in detail_rows] if games_ix is not None else []
    if not games or any(x is None or x < 1 or x != int(x) or x > week - 1 for x in games):
        return {**info, 'problem': 'Invalid or future completed-game count'}, None
    max_games = max(games)
    # Initial Week 6 batch already had browser collision suffixes on cumulative
    # files. Its G=1 (1) file is weekly; future folders follow the user's strict rule.
    legacy_batch = target == 6 and season == 2026
    weekly_suffix = bool(target and (not legacy_batch or max_games == 1) and re.search(r'\(1\)\.csv$', path.name, re.I))
    weekly = weekly_suffix or bool(legacy_batch and kind in WEEKLY and max_games == 1)
    if weekly_suffix and max_games != 1:
        return {**info, 'problem': '(1) declares prior-week data but G exceeds one'}, None
    if max_games == 1 and not weekly:
        return {**info, 'problem': 'Single-game filter conflicts with season-long declaration'}, None
    if not target and max_games == 1:
        return {**info, 'problem': 'Single-week data needs a Week N folder'}, None
    scope = 'prior_week' if weekly else 'season_to_date'
    if not weekly and week <= 14 and max_games < week - 1:
        return {**info, 'problem': 'Season totals trail the most recently completed week'}, None
    rows = []
    for raw in detail_rows:
        metrics = {key: None if value == '' else to_number(value) if to_number(value) is not None else value
                   for key, value in zip(columns, raw)}
        rows.append(metrics)
    info.update(status='accepted', scope=scope, observed_week=target - 1 if weekly else None,
                exported_at=exported.isoformat(), rows=len(rows), games_max=int(max_games))
    summaries = [{key: value for key, value in zip(columns, raw)} for raw in summary_rows]
    return info, {**info, 'columns': columns, 'headers': headers, 'groups': parsed['groups'], 'records': rows, 'reference_rows': summaries}


def sync(root, registry, season, week, now=None):
    root = Path(root).resolve()
    inbox = find_inbox(root)
    now = now or dt.datetime.now(dt.timezone.utc)
    if not 1 <= week <= 18:
        raise ValueError('A verified current NFL week 1..18 is required')
    base = root / 'model_inputs'
    known_path = base / 'known_at.json'
    first_seen = json.loads(known_path.read_text()) if known_path.exists() else {}
    scope_path = base / 'content_periods.json'
    periods = json.loads(scope_path.read_text()) if scope_path.exists() else {}
    outcomes, documents = [], []
    for path in inbox_files(inbox):
        try:
            info, document = inspect_file(path, inbox, registry, season, week, now, first_seen)
            if document:
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != info['sha256']:
                    outcomes.append({**info,'status':'held','problem':'File changed during scan; retry next cycle'})
                    continue
                raw_path = root / 'raw/inbox-autoload' / (info['sha256'] + '.csv')
                if raw_path.exists() and hashlib.sha256(raw_path.read_bytes()).hexdigest() != info['sha256']:
                    raise ValueError('Private raw archive checksum mismatch')
                if not raw_path.exists():atomic_write(raw_path,raw)
                period = [document['season'], document['scope'], document['observed_week']]
                if document['scope'] == 'prior_week' and document['sha256'] in periods and periods[document['sha256']] != period:
                    outcomes.append({**info, 'status':'held', 'problem':'Identical weekly bytes were previously assigned another observation week'})
                    continue
                first_seen.setdefault(info['sha256'], info['known_at'])
                periods.setdefault(info['sha256'], period)
                documents.append(document)
        except Exception as error:
            info = {'path': str(path.relative_to(inbox)), 'status': 'held', 'problem': str(error)}
        outcomes.append(info)
    # Repeated bytes cannot inflate samples. Weekly and season totals stay separate.
    unique = {(d['table'], d['scope'], d['sha256']): d for d in documents}
    documents = sorted(unique.values(), key=lambda d: (d['exported_at'], d['path']))
    bundle = {'schema': 'going-private-fp-inputs-v1', 'licensed': True, 'season': season, 'prediction_week': week,
              'generated_at': now.isoformat(), 'model_status': 'feature_inputs_only_not_promoted', 'datasets': documents}
    report = {'season': season, 'prediction_week': week, 'files_scanned': len(outcomes),
              'accepted': len(documents), 'outcomes': outcomes, 'sync': 'local_only_backend_not_configured'}
    write_json(known_path, first_seen)
    write_json(scope_path, periods)
    fingerprint = hashlib.sha256(json.dumps([(d['sha256'], d['scope']) for d in documents]).encode()).hexdigest()
    archive = base / str(season) / f'week-{week:02d}' / (fingerprint + '.json')
    if not archive.exists():
        write_json(archive, bundle)
    write_json(base / 'current.json', bundle)
    write_json(base / 'status.json', report)
    return report


def model_inputs(root, season, week, known_by):
    """Typed adapter for a GOING model/research caller. Never merges weekly counts into totals."""
    data = json.loads((Path(root) / 'model_inputs/current.json').read_text(encoding='utf-8'))
    if data.get('schema') != 'going-private-fp-inputs-v1' or data['season'] != season or data['prediction_week'] != week:
        raise ValueError('Private features do not match model season/week')
    return [d for d in data['datasets'] if dt.datetime.fromisoformat(d['known_at']) <= known_by
            and dt.datetime.fromisoformat(d['exported_at']) <= known_by]
