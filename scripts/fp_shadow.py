#!/usr/bin/env python3
"""Prospective, write-once SHADOW capture of the P5-2 game-total forecasts for unstarted 2026 games (research only; shown to no one).

For every game of 2026 Weeks 6-10 that has NOT started and has a posted total, record BEFORE kickoff: the raw Champion trailing average (CH_RAW), the simple baselines
(B_PTS, B_NFL), the Challenger with Fantasy Points pace (C_FP), and the matched market price, together with source hashes, per-source feature cutoffs, exclusions and the
real capture time. A forecast is never created after kickoff and never overwritten: capture files are created exclusively and chained in an append-only ledger.

    python scripts/fp_shadow.py capture [--root FantasyPoints] [--out DIR] [--weeks 6-10] [--dry-run [--now ISO]]
    python scripts/fp_shadow.py settle  [--out DIR]       append outcomes from final scores (never edits a capture)
    python scripts/fp_shadow.py score   [--out DIR]       aggregate Brier of each model vs the market on settled captures
    python scripts/fp_shadow.py receipt [--out DIR] --to FILE   credential-free hashes/timestamps only (no probabilities, no licensed values)
    python scripts/fp_shadow.py verify  [--out DIR]       check the ledger chain and every capture hash

Capture files hold values derived from licensed Fantasy Points data, so the default directory is private (outside Git) and a path inside the repository is refused.
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[1]
SCHEMA = 'going-fp-shadow-v1'
MIN_LEAD_MINUTES = 30
MAX_MARKET_AGE_HOURS = 6
SEASON = 2026
MODELS = ('CH_RAW', 'B_PTS', 'B_NFL', 'C_FP')


class ShadowError(RuntimeError):
    pass


def default_out():
    return Path(os.environ.get('GOING_FP_SHADOW') or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'GOING' / 'private' / 'fp-shadow')


def check_out_dir(out):
    out = Path(out).resolve()
    if out == REPO or REPO in out.parents:
        raise ShadowError('refusing to write licensed-derived captures inside the Git checkout')
    return out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def parse_time(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def american_to_decimal(price):
    return 1 + price / 100 if price > 0 else 1 + 100 / abs(price)


def devig_over(over_odds, under_odds):
    """Proportional (multiplicative) de-vig of a two-way price. Records the method; not the probit used by the archive comparison."""
    o, u = 1 / american_to_decimal(over_odds), 1 / american_to_decimal(under_odds)
    return o / (o + u), o + u


def _num(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else float(x)


# ------------------------------------------------------------------ pure capture logic (tested without private data)
def screen_games(games, now, *, market_generated_at, weeks=(6, 10), max_market_age_hours=MAX_MARKET_AGE_HOURS):
    """Stdlib-only eligibility screen that needs no historical data. Yields (game, kickoff, reason) in board order; reason is None when the game is eligible.
    Games outside the season/week scope are omitted (never captured, never reported)."""
    market_age_h = (now - parse_time(market_generated_at)).total_seconds() / 3600
    for g in games:
        if g.get('season') != SEASON or not (weeks[0] <= g.get('week', 0) <= weeks[1]):
            continue
        if g.get('completed') or g.get('home_score') is not None or g.get('away_score') is not None:
            yield g, None, 'already_played'
            continue
        kickoff = parse_time(g['kickoff'])
        if kickoff - now < timedelta(minutes=MIN_LEAD_MINUTES):
            yield g, kickoff, 'started_or_less_than_%d_min_to_kickoff' % MIN_LEAD_MINUTES
            continue
        if g.get('total') is None or g.get('over_odds') is None or g.get('under_odds') is None:
            yield g, kickoff, 'no_matched_market_price'
            continue
        if market_age_h > max_market_age_hours:
            yield g, kickoff, 'market_snapshot_older_than_%gh' % max_market_age_hours
            continue
        yield g, kickoff, None


def precheck(games, out, now, *, market_generated_at, weeks=(6, 10), max_market_age_hours=MAX_MARKET_AGE_HOURS):
    """Cheap first stage of a capture run: freshness, eligible unstarted games and existing captures, before any historical data is loaded.
    Returns (needed_game_ids, exclusions, already_captured_ids). Nothing is written."""
    captured_dir = Path(out) / 'captures'
    needed, exclusions, already = [], [], []
    for g, _kickoff, reason in screen_games(games, now, market_generated_at=market_generated_at, weeks=weeks, max_market_age_hours=max_market_age_hours):
        if reason:
            exclusions.append({'game_id': g['game_id'], 'week': g.get('week'), 'reason': reason})
        elif (captured_dir / f"{g['game_id']}.json").exists():
            already.append(g['game_id'])
        else:
            needed.append(g['game_id'])
    return needed, exclusions, already


def plan_captures(games, features, fitted, now, *, market_generated_at, market_sha256, source_hashes, cutoffs, weeks=(6, 10), code_sha=None, spec_sha=None, max_market_age_hours=MAX_MARKET_AGE_HOURS):
    """Returns (records, exclusions). Nothing is written here.

    games: iterable of dicts from data/nfl_betting.json. features: {game_id: {pts6_offset: exp_total, nfl_plays6.., fp_..}} (lagged, same season).
    fitted: {model: (predictor(feature_dict_without_line)->r_hat or None, sigma)}.
    """
    records, exclusions = [], []
    for g, kickoff, reason in screen_games(games, now, market_generated_at=market_generated_at, weeks=weeks, max_market_age_hours=max_market_age_hours):
        gid = g['game_id']
        if reason:
            exclusions.append({'game_id': gid, 'week': g.get('week'), 'reason': reason})
            continue
        f = features.get(gid)
        if not f or _num(f.get('exp_total')) is None:
            exclusions.append({'game_id': gid, 'week': g.get('week'), 'reason': 'fewer_than_3_prior_same_season_games'})
            continue
        line = float(g['total'])
        p_mkt, overround = devig_over(g['over_odds'], g['under_odds'])
        feats = {'pts6': f['exp_total'] - line, **{k: _num(f.get(k)) for k in ('nfl_plays6', 'nfl_pass6', 'fp_snaps6', 'fp_pass6', 'fp_neutral6')}}
        forecasts = {}
        for name in MODELS:
            predictor, sigma = fitted[name]
            r_hat = predictor(feats)
            if r_hat is None or not math.isfinite(r_hat):
                forecasts[name] = None
            else:
                forecasts[name] = {'expected_total': line + float(r_hat), 'p_over': 0.5 * math.erfc(-(r_hat / sigma) / math.sqrt(2)), 'sigma': sigma}
        records.append({
            'schema': SCHEMA, 'game_id': gid, 'season': SEASON, 'week': g['week'], 'away': g['away'], 'home': g['home'], 'kickoff': kickoff.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'captured_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'status': 'pregame_prospective_capture',
            'market': {'line': line, 'over_odds': g['over_odds'], 'under_odds': g['under_odds'], 'p_over_devig_proportional': p_mkt, 'overround': overround,
                       'source_generated_at': market_generated_at, 'source_sha256': market_sha256, 'note': 'single-provider consensus board from data/nfl_betting.json; not the multi-book archive board'},
            'forecasts': forecasts, 'feature_hash': sha256_text(canonical({k: _num(v) for k, v in feats.items()})), 'feature_cutoffs': cutoffs.get(gid, {}),
            'source_hashes': source_hashes, 'code_sha': code_sha, 'protocol_spec_sha256': spec_sha,
            'timestamps': {'market_snapshot': market_generated_at, 'forecast_created': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'bookmaker_update': None,
                           'features_available_through': cutoffs.get(gid, {})}})
    return records, exclusions


def _ledger_entries(out):
    path = out / 'ledger.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def write_once(out, record, clock=lambda: datetime.now(timezone.utc)):
    """Create the capture exclusively and chain it. Returns 'written' or a reason it was not. Never overwrites and never writes after kickoff."""
    out = check_out_dir(out)
    (out / 'captures').mkdir(parents=True, exist_ok=True)
    path = out / 'captures' / f"{record['game_id']}.json"
    if path.exists():
        return 'already_captured'
    now = clock()
    if now >= parse_time(record['kickoff']) - timedelta(minutes=MIN_LEAD_MINUTES):
        return 'refused_too_late'  # time passed between planning and writing: never record a forecast as if it were pregame
    record = {**record, 'captured_at': now.strftime('%Y-%m-%dT%H:%M:%SZ')}
    body = canonical(record)
    try:
        with open(path, 'x', encoding='utf-8') as f:
            f.write(body)
    except FileExistsError:
        return 'already_captured'
    os.chmod(path, 0o444)
    entries = _ledger_entries(out)
    prev = entries[-1]['entry_sha256'] if entries else '0' * 64
    entry = {'seq': len(entries) + 1, 'captured_at': record['captured_at'], 'game_id': record['game_id'], 'file_sha256': sha256_text(body), 'prev_entry_sha256': prev}
    entry['entry_sha256'] = sha256_text(canonical(entry))
    with open(out / 'ledger.jsonl', 'a', encoding='utf-8') as f:
        f.write(canonical(entry) + '\n')
    return 'written'


def verify(out):
    out = Path(out)
    problems, prev = [], '0' * 64
    entries = _ledger_entries(out)
    for e in entries:
        body = {k: v for k, v in e.items() if k != 'entry_sha256'}
        if e['prev_entry_sha256'] != prev or sha256_text(canonical(body)) != e['entry_sha256']:
            problems.append(f"ledger break at seq {e['seq']}")
        prev = e['entry_sha256']
        path = out / 'captures' / f"{e['game_id']}.json"
        if not path.exists() or sha256_text(path.read_text(encoding='utf-8')) != e['file_sha256']:
            problems.append(f"capture {e['game_id']} missing or modified")
    extra = {p.stem for p in (out / 'captures').glob('*.json')} - {e['game_id'] for e in entries} if (out / 'captures').exists() else set()
    problems += [f'capture {g} is not in the ledger' for g in sorted(extra)]
    return {'entries': len(entries), 'problems': problems, 'ok': not problems}


# ------------------------------------------------------------------ loading real inputs (private data required)
FEATURE_COLS = {'CH_RAW': ['pts6'], 'B_PTS': ['pts6'], 'B_NFL': ['pts6', 'nfl_plays6', 'nfl_pass6'], 'C_FP': ['pts6', 'nfl_plays6', 'nfl_pass6', 'fp_snaps6', 'fp_pass6', 'fp_neutral6']}
CACHE_SCHEMA = 'going-fp-shadow-inputs-v1'


def make_predictor(name, params):
    """Pure-Python predictor from frozen ridge parameters (the same arithmetic as stats.Ridge.predict). CH_RAW is the raw trailing-average offset."""
    cols = FEATURE_COLS[name]
    if name == 'CH_RAW':
        def raw(feats):
            v = feats.get('pts6')
            return None if v is None or not math.isfinite(v) else v
        return raw
    mean, scale, coef, intercept = params['mean'], params['scale'], params['coef'], params['intercept']

    def predict(feats):
        vals = [feats.get(c) for c in cols]
        if any(v is None or not math.isfinite(v) for v in vals):
            return None
        total = 0.0
        for v, m, sc, w in zip(vals, mean, scale, coef):
            total += ((v - m) / sc) * w
        return float(intercept + total)
    return predict


def build_inputs(root):
    """Heavy path: rebuilds the historical features and refits the development models (research modules, pandas, scipy). Returns a JSON-serialisable bundle."""
    from trend_research import experiments14 as e14
    games_tbl, tg = e14.team_games(root)
    g = e14.game_features(games_tbl, tg)
    dev = g[g.season.isin([2021, 2022, 2023]) & g.total_line.notna() & g.total.notna()].copy()
    dev['pts6'] = dev.exp_total - dev.total_line
    dev = dev.dropna(subset=e14.FEATS['C_FP'])
    raw = e14._fit_totals(dev)
    models = {}
    for name in MODELS:
        model, sigma = raw[name]
        entry = {'sigma': float(sigma)}
        if model is not None:
            entry.update(mean=[float(x) for x in model.mean_], scale=[float(x) for x in model.scale_], coef=[float(x) for x in model.coef_], intercept=float(model.intercept_))
        models[name] = entry
    cur = g[g.season == SEASON]
    features, cutoffs = {}, {}
    for r in cur.itertuples():
        features[r.game_id] = {'exp_total': None if r.exp_total != r.exp_total else float(r.exp_total),
                               **{c: _num(getattr(r, c)) for c in ('nfl_plays6', 'nfl_pass6', 'fp_snaps6', 'fp_pass6', 'fp_neutral6')}}
        prior = tg[(tg.season == SEASON) & (tg.week < r.week) & tg.team.isin([r.home, r.away])]
        cutoffs[r.game_id] = {'scores_through_week': {t: _last(prior, t, 'pf') for t in (r.home, r.away)}, 'nflverse_weekly_through_week': {t: _last(prior, t, 'nfl_plays') for t in (r.home, r.away)},
                              'fantasy_points_run_pass_through_week': {t: _last(prior, t, 'fp_snaps') for t in (r.home, r.away)}, 'window_games': e14.WINDOW, 'min_prior_games': e14.MIN_PRIOR}
    return {'models': models, 'features': features, 'cutoffs': cutoffs}


def input_hashes(root):
    """Hashes that control cache validity: every data file the features read, the protocol spec, and the code that computes them."""
    root = Path(root)
    cache = root / 'research' / 'cache'
    scripts = Path(__file__).resolve().parent
    code_files = [scripts / 'fp_shadow.py', scripts / 'trend_research' / 'experiments14.py', scripts / 'trend_research' / 'stats.py', scripts / 'trend_research' / 'champion.py',
                  scripts / 'trend_research' / 'weekly.py', scripts / 'fp_ingest' / 'identity.py', scripts / 'fp_ingest' / 'store.py']
    book = json.loads((REPO / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))
    data = {'games_csv_sha256': sha256_file(cache / 'games.csv'), 'fantasy_points_manifest_index_sha256': sha256_file(root / 'manifests' / 'index.json')}
    for season in range(2021, 2027):
        data[f'stats_player_week_{season}_sha256'] = sha256_file(cache / f'stats_player_week_{season}.csv')
    # The FP weekly run/pass files are content-addressed in the manifest index; hash the normalised documents it points to as well.
    index = json.loads((root / 'manifests' / 'index.json').read_text(encoding='utf-8'))
    for entry in sorted((e for e in index.get('files', {}).values() if 'run_pass_report_weekly' in str(e.get('normalized_path'))), key=lambda e: str(e.get('normalized_path'))):
        path = root / entry['normalized_path']
        if path.exists():
            data['run_pass_' + path.stem] = sha256_file(path)
    code = sha256_text(''.join(sha256_file(f) for f in code_files if f.exists()))
    return data, book['experiments']['P5-2']['spec_sha256'], code


def cache_key(data, spec_sha, code):
    return sha256_text(canonical({'schema': CACHE_SCHEMA, 'data': data, 'spec': spec_sha, 'code': code}))


def prepare_inputs(root, out, *, rebuild=False):
    """Returns (features, fitted, cutoffs, source_hashes, spec_sha, cache_status). Rebuilds the historical features and models only when a hash that controls them changed."""
    data, spec_sha, code = input_hashes(root)
    key = cache_key(data, spec_sha, code)
    cache_dir = Path(out) / 'cache'
    path = cache_dir / f'inputs-{key[:24]}.json'
    status = 'rebuilt'
    bundle = None
    if path.exists() and not rebuild:
        try:
            bundle = json.loads(path.read_text(encoding='utf-8'))
            if bundle.get('key') != key or bundle.get('schema') != CACHE_SCHEMA:
                bundle = None
            else:
                status = 'hit'
        except (OSError, ValueError):
            bundle = None
    if bundle is None:
        bundle = build_inputs(root)
        bundle.update(schema=CACHE_SCHEMA, key=key, data_hashes=data, spec_sha=spec_sha, code_sha256=code)
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(bundle, sort_keys=True, allow_nan=False), encoding='utf-8')
        os.replace(tmp, path)
        for old in sorted(cache_dir.glob('inputs-*.json'), key=lambda p: p.stat().st_mtime)[:-2]:
            old.unlink()  # keep the two newest bundles only
    fitted = {name: (make_predictor(name, bundle['models'][name]), bundle['models'][name]['sigma']) for name in MODELS}
    hashes = {'games_csv_sha256': data['games_csv_sha256'], 'stats_player_week_2026_sha256': data['stats_player_week_2026_sha256'],
              'fantasy_points_manifest_index_sha256': data['fantasy_points_manifest_index_sha256'], 'inputs_cache_key': key[:24]}
    return bundle['features'], fitted, bundle['cutoffs'], hashes, spec_sha, status


def _last(frame, team, col):
    sub = frame[(frame.team == team) & frame[col].notna()]
    return None if sub.empty else int(sub.week.max())


def git_sha():
    pinned = REPO / 'RUNTIME_COMMIT'  # written by install_fp_shadow_task.ps1 for a self-contained, version-pinned runtime copy
    if pinned.exists():
        return pinned.read_text(encoding='utf-8').strip() or None
    try:
        return subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=20, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def board_from_git(ref='origin/main', path='data/nfl_betting.json', fetch=True):
    """Latest published game-line board without touching the working tree: fetch (read-only network call to the project's own remote) then read the blob. Returns bytes."""
    if fetch:
        subprocess.run(['git', '-C', str(REPO), 'fetch', '-q', 'origin', ref.split('/', 1)[-1]], check=True, timeout=120)
    return subprocess.run(['git', '-C', str(REPO), 'show', f'{ref}:{path}'], check=True, capture_output=True, timeout=60).stdout


RAW_BASE = 'https://raw.githubusercontent.com/daboli69/going-long/'
BOARD_FILES = ('data/nfl_game_lines.json', 'data/nfl_betting.json')


def board_from_url(ref='main', fetch=None):
    """Newest published game-line board from the project's own PUBLIC repository (HTTPS GET, no credentials, no git, no provider call).
    Reads the independent game-lines snapshot and the full board, and returns the bytes of whichever carries the newer generated_at."""
    import re
    if not re.fullmatch(r'[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*', ref) or '..' in ref:
        raise ShadowError('invalid ref')
    if fetch is None:
        import urllib.request

        def fetch(url):
            req = urllib.request.Request(url, headers={'User-Agent': 'going-fp-shadow/1', 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
    best = None
    for path in BOARD_FILES:
        url = f'{RAW_BASE}{ref}/{path}'
        if not url.startswith(RAW_BASE):
            raise ShadowError('board URL outside the project repository')
        try:
            body = fetch(url)
            stamp = parse_time(json.loads(body)['generated_at'])
        except Exception:  # missing file (404), malformed JSON or no timestamp: that candidate is simply unavailable
            continue
        if best is None or stamp > best[0]:
            best = (stamp, body, path)
    if best is None:
        raise ShadowError('no published game-line board could be read')
    return best[1]


RAW_BASE = 'https://raw.githubusercontent.com/daboli69/going-long/'
BOARD_FILES = ('data/nfl_game_lines.json', 'data/nfl_betting.json')


def board_from_url(ref='main', fetch=None):
    """Newest published game-line board from the project's own PUBLIC repository (HTTPS GET, no credentials, no git, no provider call).
    Reads the independent game-lines snapshot and the full board, and returns the bytes of whichever carries the newer generated_at."""
    if fetch is None:
        import urllib.request

        def fetch(url):
            req = urllib.request.Request(url, headers={'User-Agent': 'going-fp-shadow/1', 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
    best = None
    for path in BOARD_FILES:
        url = f'{RAW_BASE}{ref}/{path}'
        try:
            body = fetch(url)
            stamp = parse_time(json.loads(body)['generated_at'])
        except Exception:  # missing file (404), malformed JSON or no timestamp: that candidate is simply unavailable
            continue
        if best is None or stamp > best[0]:
            best = (stamp, body, path)
    if best is None:
        raise ShadowError('no published game-line board could be read')
    return best[1]


LOCK_STALE_SECONDS = 15 * 60


class Lock:
    """Exclusive run lock so a manual run and the scheduled run can never overlap. A lock older than 15 minutes is treated as left by a crashed run."""

    def __init__(self, out):
        self.path = Path(out) / 'capture.lock'
        self.held = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    continue
                if attempt == 0 and age > LOCK_STALE_SECONDS:
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                return self
            with os.fdopen(fd, 'w') as f:
                f.write(json.dumps({'pid': os.getpid(), 'started': datetime.now(timezone.utc).isoformat()}))
            self.held = True
            return self
        return self

    def __exit__(self, *exc):
        if self.held:
            try:
                self.path.unlink()
            except OSError:
                pass


def capture(root, out, *, weeks=(6, 10), dry_run=False, now=None, results_path=REPO / 'data' / 'nfl_betting.json', max_market_age_hours=MAX_MARKET_AGE_HOURS, market_bytes=None, rebuild=False):
    out = check_out_dir(out)
    if now is not None and not dry_run:
        raise ShadowError('--now is only allowed with --dry-run: a real capture always uses the wall clock')
    if dry_run:
        return _capture(root, out, weeks, True, now, results_path, max_market_age_hours, market_bytes, rebuild)
    with Lock(out) as lock:
        if not lock.held:
            report = {'captured_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'dry_run': False, 'results': {}, 'exclusions': [], 'counts': {}, 'skipped': 'another capture run holds the lock'}
            return report
        return _capture(root, out, weeks, False, now, results_path, max_market_age_hours, market_bytes, rebuild)


def _capture(root, out, weeks, dry_run, now, results_path, max_market_age_hours, market_bytes, rebuild):
    now = now or datetime.now(timezone.utc)
    market_text = market_bytes if market_bytes is not None else Path(results_path).read_bytes()
    market = json.loads(market_text)
    needed, exclusions, already = precheck(market['games'], out, now, market_generated_at=market['generated_at'], weeks=weeks, max_market_age_hours=max_market_age_hours)
    results = {gid: 'already_captured' for gid in already}
    stage = {'precheck_only': True, 'inputs_cache': 'not_needed', 'eligible_needing_capture': len(needed)}
    if needed:
        features, fitted, cutoffs, hashes, spec_sha, cache_status = prepare_inputs(root, out, rebuild=rebuild)
        stage.update(precheck_only=False, inputs_cache=cache_status)
        records, plan_excl = plan_captures([g for g in market['games'] if g['game_id'] in set(needed)], features, fitted, now, market_generated_at=market['generated_at'],
                                           market_sha256=hashlib.sha256(market_text).hexdigest(), source_hashes=hashes, cutoffs=cutoffs, weeks=weeks, code_sha=git_sha(),
                                           spec_sha=spec_sha, max_market_age_hours=max_market_age_hours)
        exclusions += plan_excl
        for rec in records:
            results[rec['game_id']] = 'dry_run' if dry_run else write_once(out, rec)
    report = {'captured_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'dry_run': dry_run, 'results': results, 'exclusions': exclusions, 'stage': stage,
              'counts': {s: sum(1 for v in results.values() if v == s) for s in set(results.values())}}
    if not dry_run:
        (out / 'runs').mkdir(parents=True, exist_ok=True)
        run_path = out / 'runs' / f"{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        if not run_path.exists():
            run_path.write_text(canonical(report), encoding='utf-8')
    return report


# ------------------------------------------------------------------ settlement and scoring (never edits a capture)
def settle(out, results_path=REPO / 'data' / 'nfl_betting.json'):
    out = check_out_dir(out)
    final = {g['game_id']: g for g in json.loads(Path(results_path).read_text(encoding='utf-8'))['games'] if g.get('completed') is True
             and isinstance(g.get('home_score'), (int, float)) and isinstance(g.get('away_score'), (int, float))}
    (out / 'settled').mkdir(parents=True, exist_ok=True)
    done = {}
    for path in sorted((out / 'captures').glob('*.json')):
        rec = json.loads(path.read_text(encoding='utf-8'))
        target = out / 'settled' / path.name
        if rec['game_id'] not in final:
            done[rec['game_id']] = 'not_final'
            continue
        if target.exists():
            done[rec['game_id']] = 'already_settled'
            continue
        g = final[rec['game_id']]
        total = g['home_score'] + g['away_score']
        y = None if total == rec['market']['line'] else int(total > rec['market']['line'])
        with open(target, 'x', encoding='utf-8') as f:
            f.write(canonical({'game_id': rec['game_id'], 'capture_file_sha256': sha256_text(path.read_text(encoding='utf-8')), 'total': total, 'y_over': y,
                               'push': y is None, 'settled_from': 'data/nfl_betting.json final score'}))
        done[rec['game_id']] = 'settled'
    return done


def score(out):
    import numpy as np
    out = Path(out)
    rows = []
    for path in sorted((out / 'settled').glob('*.json')):
        s = json.loads(path.read_text(encoding='utf-8'))
        if s['y_over'] is None:
            continue
        rec = json.loads((out / 'captures' / path.name).read_text(encoding='utf-8'))
        row = {'y': s['y_over'], 'MKT': rec['market']['p_over_devig_proportional']}
        for m in MODELS:
            row[m] = rec['forecasts'][m]['p_over'] if rec['forecasts'].get(m) else None
        rows.append(row)
    result = {'settled_non_push': len(rows), 'models': {}}
    if not rows:
        return result
    from trend_research.experiments5 import _cluster_ci
    for m in MODELS:
        ok = [r for r in rows if r[m] is not None]
        if not ok:
            continue
        y = np.array([r['y'] for r in ok], float)
        pm, pn = np.array([r['MKT'] for r in ok]), np.array([r[m] for r in ok])
        gain = (pm - y) ** 2 - (pn - y) ** 2
        mean, lo, hi = _cluster_ci(gain, np.arange(len(ok)), 0.95) if len(ok) > 2 else (float(gain.mean()), None, None)
        result['models'][m] = {'n': len(ok), 'brier_market': float(((pm - y) ** 2).mean()), 'brier_model': float(((pn - y) ** 2).mean()), 'brier_gain_vs_market': [mean, lo, hi]}
    return result


def receipt(out):
    out = Path(out)
    entries = _ledger_entries(out)
    games = []
    for e in entries:
        rec = json.loads((out / 'captures' / f"{e['game_id']}.json").read_text(encoding='utf-8'))
        games.append({'game_id': e['game_id'], 'week': rec['week'], 'kickoff': rec['kickoff'], 'captured_at': e['captured_at'], 'file_sha256': e['file_sha256'], 'entry_sha256': e['entry_sha256'],
                      'models': sorted(k for k, v in rec['forecasts'].items() if v), 'minutes_before_kickoff': round((parse_time(rec['kickoff']) - parse_time(rec['captured_at'])).total_seconds() / 60, 1),
                      'protocol_spec_sha256': rec['protocol_spec_sha256'], 'code_sha': rec['code_sha'], 'source_hashes': rec['source_hashes']})
    return {'schema': 'going-fp-shadow-receipt-v1', 'note': 'hashes, timestamps and model names only; no probabilities, features or licensed values', 'verification': verify(out), 'captures': games}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('capture')
    c.add_argument('--root', type=Path, default=REPO / 'FantasyPoints')
    c.add_argument('--out', type=Path, default=default_out())
    c.add_argument('--weeks', default='6-10')
    c.add_argument('--market', type=Path, default=REPO / 'data' / 'nfl_betting.json', help='fresh game-line board (default: the checkout copy; use the latest origin/main data refresh)')
    c.add_argument('--market-from-git', metavar='REF', help='read the board from a git ref (for example origin/main) after fetching it, instead of the working-tree file')
    c.add_argument('--market-from-url', metavar='REF', help='read the newest published board from the project public repository at this ref (for example main)')
    c.add_argument('--max-market-age-hours', type=float, default=MAX_MARKET_AGE_HOURS)
    c.add_argument('--dry-run', action='store_true')
    c.add_argument('--rebuild-inputs', action='store_true', help='ignore the cached historical features and models and rebuild them')
    c.add_argument('--now')
    for name in ('settle', 'score', 'verify'):
        s = sub.add_parser(name)
        s.add_argument('--out', type=Path, default=default_out())
    r = sub.add_parser('receipt')
    r.add_argument('--out', type=Path, default=default_out())
    r.add_argument('--to', type=Path, required=True)
    a = p.parse_args()
    if a.cmd == 'capture':
        lo, hi = (int(x) for x in a.weeks.split('-'))
        print(json.dumps(capture(a.root, a.out, weeks=(lo, hi), dry_run=a.dry_run, now=parse_time(a.now) if a.now else None, results_path=a.market, max_market_age_hours=a.max_market_age_hours,
                                 market_bytes=board_from_url(a.market_from_url) if a.market_from_url else (board_from_git(a.market_from_git) if a.market_from_git else None),
                                 rebuild=a.rebuild_inputs), indent=1))
    elif a.cmd == 'settle':
        print(json.dumps(settle(a.out), indent=1))
    elif a.cmd == 'score':
        print(json.dumps(score(a.out), indent=1))
    elif a.cmd == 'verify':
        res = verify(a.out)
        print(json.dumps(res, indent=1))
        sys.exit(0 if res['ok'] else 1)
    else:
        a.to.write_text(json.dumps(receipt(a.out), indent=1), encoding='utf-8')
        print(f'wrote {a.to}')


if __name__ == '__main__':
    main()
