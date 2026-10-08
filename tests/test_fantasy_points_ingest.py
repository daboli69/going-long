import copy
import csv
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fp_ingest import identity as idmod  # noqa: E402
from fp_ingest.history import COUNT_BASES  # noqa: E402
from fp_ingest import pipeline as pl  # noqa: E402
from fp_ingest import registry as regmod  # noqa: E402
from fp_ingest import store  # noqa: E402
from fp_ingest.parse import ParseError, parse_export, sha256  # noqa: E402

REGISTRY = regmod.load()
TEAMS = sorted(idmod.TEAMS)
FP_CODE = {'ARI': 'ARZ', 'BAL': 'BLT', 'CLE': 'CLV', 'HOU': 'HST'}
NOW = datetime.datetime(2026, 10, 7, 14, 0, tzinfo=datetime.timezone.utc)
FUTURE = '2999-01-01T00:00:00Z'
FULL_NAMES = {code: name.title() for name, code in idmod.TEAM_NAMES.items()}


def players_for(team, count=3):
    return [(f'Player{index} {team.title()}son', 'WR' if index else 'RB') for index in range(count)]


def roster_rows(extra=()):
    rows = []
    for team in TEAMS:
        for name, position in players_for(team):
            rows.append({'gsis_id': f'00-{team}-{name[:7]}', 'full_name': name, 'team': team, 'position': position})
    return rows + list(extra)


def make_csv(table_id, season=2026, games=4, teams=TEAMS, mutate=None, blanks=(), rows_per_team=3, drop_columns=(), add_columns=(), rename=None, truncate=False):
    table = REGISTRY['tables'][table_id]
    keys = [c['key'] for c in table['columns']]
    keys = [k for k in keys if k not in drop_columns]
    if rename:
        keys = [rename.get(k, k) for k in keys]
    keys = keys + list(add_columns)
    groups, headers, last = [], [], None
    for key in keys:
        group, _, base = key.partition('.')
        groups.append('' if group == last else group)
        last = group
        headers.append(base.split('#')[0])
    body = []
    for team in teams:
        for index in range(rows_per_team if table['level'] == 'player' else 1):
            row = []
            for key in keys:
                group, _, base = key.partition('.')
                base = base.split('#')[0]
                if group in ('Player Details', 'Team Details'):
                    name, position = players_for(team, rows_per_team)[index] if table['level'] == 'player' else (FULL_NAMES[team], '')
                    value = {'Rank': str(len(body) + 1), 'Name': name, 'Team': FP_CODE.get(team, team), 'POS': position, 'G': str(games), 'Season': str(season),
                             'OPP': FP_CODE.get('SF' if team != 'SF' else 'KC', 'SF'), 'Location': FULL_NAMES[team].rsplit(' ', 1)[0],
                             'Team Name': FULL_NAMES[team].rsplit(' ', 1)[1]}.get(base, '')
                elif key == 'Defense Stats.Name':
                    value = FULL_NAMES['SF' if team != 'SF' else 'KC']
                elif key == 'Offense Stats.Team':
                    value = FP_CODE.get(team, team)
                else:
                    rate_like = base not in COUNT_BASES
                    value = '' if (len(body), key) in blanks else ('1.5' if rate_like else str(round(1.5 * games, 1)))  # counts grow with games played
                row.append(value)
            body.append(row)
    if mutate:
        mutate(body, keys)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(groups)
    writer.writerow(headers)
    writer.writerows(body)
    writer.writerow([])
    writer.writerow(['RTE', 'Routes Run'])
    text = '﻿' + out.getvalue()
    if truncate:
        text = text[: len(text) // 2]
    return text.encode('utf-8')


class Workspace:
    def __init__(self, test, **options):
        self.dir = Path(tempfile.mkdtemp(prefix='fp_test_'))
        test.addCleanup(shutil.rmtree, self.dir, True)
        self.inbox = self.dir / 'Inbox'
        self.inbox.mkdir()
        self.options = options
        self.extra_roster = options.pop('extra_roster', ())

    def put(self, name, data):
        (self.inbox / name).write_bytes(data)

    def importer(self, now=NOW, **overrides):
        options = {'now': now, 'current_season': 2026, 'max_possible_games': 5, 'expected_games': 4,
                   'rosters': lambda season: idmod.RosterIndex(roster_rows(self.extra_roster)), **self.options, **overrides}
        return pl.Importer(self.dir, REGISTRY, **options)

    def run(self, **kw):
        return self.importer(**kw).run()

    def manifest(self):
        return store.Manifest(self.dir)

    def outcomes(self, report):
        return {r['file']: r['outcome'] for r in report['results']}


def table_cases():
    return {'receiving_routes_run': 'rr.csv', 'rushing_bell_cow': 'bc.csv', 'passing_depth': 'pd.csv'}


class ParsingTests(unittest.TestCase):
    def test_two_row_header_bom_glossary_and_blanks_stay_missing(self):
        data = make_csv('rushing_bell_cow', blanks={(0, 'Snaps.Snap %')})
        parsed = parse_export(data)
        self.assertIn('Snaps.Snap %', parsed['columns'])
        self.assertEqual(parsed['glossary'], {'RTE': 'Routes Run'})
        index = parsed['columns'].index('Snaps.Snap %')
        self.assertEqual(parsed['rows'][0][index], '')
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow', blanks={(0, 'Snaps.Snap %')}))
        workspace.run()
        document = json.loads(next((workspace.dir / 'normalized').rglob('*.json')).read_text(encoding='utf-8'))
        self.assertIsNone(document['rows'][0]['metrics']['Snaps.Snap %'])  # blank is None, never 0
        self.assertEqual(document['rows'][1]['metrics']['Snaps.Snap %'], 1.5)

    def test_malformed_inputs_raise_stable_codes(self):
        for data, code in ((b'', 'empty'), (b'a,b\n1,2\n', 'too_short'), (b'\xff\xfe\x00', 'not_utf8'), (b'x\n' * 4, 'no_header')):
            with self.assertRaises(ParseError) as caught:
                parse_export(data)
            self.assertEqual(caught.exception.code, code, data)


class ImportTests(unittest.TestCase):
    def test_all_tables_import_with_games_detected_and_layout(self):
        workspace = Workspace(self)
        for table_id in REGISTRY['tables']:
            workspace.put(f'{table_id}.csv', make_csv(table_id))
        report = workspace.run()
        self.assertEqual(set(report['outcomes']), {'imported'}, report['outcomes'])
        self.assertEqual(len(report['results']), len(REGISTRY['tables']))
        raws = sorted(p.parent.name for p in (workspace.dir / 'raw' / '2026').rglob('*.csv'))
        self.assertEqual(set(raws), {'through-week-04'})
        self.assertTrue(all(line.endswith('✓') for line in report['freshness']), report['freshness'])

    def test_filename_is_only_a_hint(self):
        workspace = Workspace(self)
        workspace.put('Totally Unrelated Name (3).csv', make_csv('rushing_bell_cow'))
        report = workspace.run()
        self.assertEqual(report['results'][0]['table_id'], 'rushing_bell_cow')

    def test_duplicate_import_is_idempotent_and_inbox_is_untouched(self):
        workspace = Workspace(self)
        data = make_csv('rushing_bell_cow')
        workspace.put('a.csv', data)
        workspace.run()
        before = {p: p.read_bytes() for p in workspace.dir.rglob('*') if p.is_file() and 'last_run' not in p.name and 'freshness' not in p.name}
        workspace.put('Copy of a (1).csv', data)  # same bytes, different filename
        report = workspace.run(now=NOW + datetime.timedelta(days=1))
        self.assertEqual(set(workspace.outcomes(report).values()), {'duplicate'})
        after = {p: p.read_bytes() for p in workspace.dir.rglob('*') if p.is_file() and p not in before and 'last_run' not in p.name and 'freshness' not in p.name}
        self.assertEqual(after.keys() - {workspace.inbox / 'Copy of a (1).csv'}, set(), 'a duplicate must not create new files')
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, f'{path.name} changed on re-import')
        self.assertEqual(len(workspace.manifest().files), 1)
        self.assertEqual((workspace.inbox / 'a.csv').read_bytes(), data)

    def test_raw_copy_is_byte_identical_and_verify_detects_tampering(self):
        workspace = Workspace(self)
        data = make_csv('rushing_bell_cow')
        workspace.put('a.csv', data)
        workspace.run()
        raw = next((workspace.dir / 'raw').rglob('*.csv'))
        self.assertEqual(raw.read_bytes(), data)
        raw.write_bytes(data + b'tamper')
        entry = next(iter(workspace.manifest().files.values()))
        self.assertNotEqual(sha256(raw.read_bytes()), entry['sha256'])
        report = workspace.run()  # a damaged archive copy is repaired from the Inbox bytes, never trusted
        self.assertEqual(raw.read_bytes(), data)
        self.assertEqual(workspace.outcomes(report)['a.csv'], 'repaired')

    def test_corrected_export_is_an_explicit_revision(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        workspace.put('a.csv', make_csv('rushing_bell_cow', mutate=lambda body, keys: body[0].__setitem__(keys.index('Rushing.ATT'), '99')))
        report = workspace.run(now=NOW + datetime.timedelta(hours=5))
        self.assertEqual(workspace.outcomes(report)['a.csv'], 'revision')
        manifest = workspace.manifest()
        old, new = sorted(manifest.files.values(), key=lambda e: e['first_imported_at'])
        self.assertEqual(old['superseded_by'], new['sha256'])
        self.assertEqual(new['revision_of'], old['sha256'])
        self.assertEqual(store.current_entry(manifest, 2026, 'rushing_bell_cow')['sha256'], new['sha256'])
        self.assertEqual(len(list((workspace.dir / 'raw').rglob('*.csv'))), 2, 'both versions stay archived')

    def test_partial_correction_does_not_replace_a_complete_snapshot(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        workspace.put('b.csv', make_csv('rushing_bell_cow', teams=TEAMS[:5]))
        report = workspace.run(now=NOW + datetime.timedelta(hours=5))
        self.assertEqual(workspace.outcomes(report)['b.csv'], 'partial_revision_kept_old_current')
        current = store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')
        self.assertEqual(current['status'], 'imported')

    def test_new_week_is_a_new_snapshot_not_a_revision(self):
        workspace = Workspace(self)
        workspace.put('w4.csv', make_csv('rushing_bell_cow', games=4))
        workspace.run()
        workspace.put('w5.csv', make_csv('rushing_bell_cow', games=5, mutate=lambda body, keys: body[0].__setitem__(keys.index('Rushing.ATT'), '77')))
        report = workspace.run(now=NOW + datetime.timedelta(days=7), expected_games=5, max_possible_games=6)
        self.assertEqual(workspace.outcomes(report)['w5.csv'], 'imported')
        manifest = workspace.manifest()
        self.assertEqual(store.current_entry(manifest, 2026, 'rushing_bell_cow')['through_games'], 5)
        self.assertFalse(any(e.get('superseded_by') for e in manifest.files.values()))
        self.assertEqual(len(list((workspace.dir / 'normalized').rglob('*.json'))), 2)

    def test_individual_week_export_cannot_masquerade_as_current(self):
        workspace = Workspace(self)  # a Week-5-only export shows G=1 for everyone
        workspace.put('week5only.csv', make_csv('rushing_bell_cow', games=1))
        report = workspace.run()
        line = [l for l in report['freshness'] if l.startswith('Bell cow')][0]
        self.assertIn('STALE', line)
        other = Workspace(self)  # the operator can state the truth explicitly, for a file not imported yet
        other.put('week5only.csv', make_csv('rushing_bell_cow', games=1))
        other.run(through_override=5)
        entry = store.current_entry(other.manifest(), 2026, 'rushing_bell_cow')
        self.assertEqual((entry['scope_source'], entry['through_games']), ('operator', 5))

    def test_future_games_and_future_season_are_rejected(self):
        workspace = Workspace(self)
        workspace.put('future.csv', make_csv('rushing_bell_cow', games=9))
        workspace.put('season.csv', make_csv('passing_depth', season=2027))
        report = workspace.run()
        self.assertEqual(workspace.outcomes(report), {'future.csv': 'rejected', 'season.csv': 'rejected'})
        codes = {r['reason']['code'] for r in report['results']}
        self.assertEqual(codes, {'future_games', 'future_season'})

    def test_historical_files_are_archived_by_their_own_season(self):
        workspace = Workspace(self)
        for year in (2021, 2023, 2025):
            workspace.put(f'h{year}.csv', make_csv('rushing_bell_cow', season=year, games=17))
        report = workspace.run()
        self.assertEqual(set(workspace.outcomes(report).values()), {'imported'})
        for year in (2021, 2023, 2025):
            self.assertTrue(list((workspace.dir / 'raw' / str(year) / 'full-season').glob('*.csv')), year)
        entry = store.current_entry(workspace.manifest(), 2023, 'rushing_bell_cow')
        self.assertEqual((entry['scope'], entry['known_live']), ('full_season', False))

    def test_partial_season_of_a_past_year_is_held_not_guessed(self):
        workspace = Workspace(self)
        workspace.put('h.csv', make_csv('rushing_bell_cow', season=2024, games=9))
        report = workspace.run()
        self.assertEqual(workspace.outcomes(report)['h.csv'], 'held_scope')
        self.assertIsNone(store.current_entry(workspace.manifest(), 2024, 'rushing_bell_cow'))
        self.assertEqual(list((workspace.dir / 'normalized').rglob('*.json')), [])

    def test_unknown_table_is_preserved_and_reported(self):
        workspace = Workspace(self)
        unknown = b'Player Details,,\nRank,Name,Wizardry\n1,A B,3\n\nRank,Whatever\n'
        workspace.put('mystery.csv', unknown)
        workspace.put('ok.csv', make_csv('rushing_bell_cow'))
        report = workspace.run()
        self.assertEqual(workspace.outcomes(report), {'mystery.csv': 'unrecognized', 'ok.csv': 'imported'})
        self.assertEqual(next((workspace.dir / 'raw' / '_unrecognized').glob('*')).read_bytes(), unknown)

    def test_one_bad_file_never_stops_the_rest_and_previous_data_survives(self):
        workspace = Workspace(self)
        workspace.put('ok.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        good = store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')
        workspace.put('broken.csv', make_csv('rushing_bell_cow', games=5, truncate=True))
        workspace.put('other.csv', make_csv('passing_depth'))
        report = workspace.run(now=NOW + datetime.timedelta(days=1))
        self.assertEqual(workspace.outcomes(report)['broken.csv'], 'rejected')
        self.assertEqual(workspace.outcomes(report)['other.csv'], 'imported')
        self.assertEqual(store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')['sha256'], good['sha256'])
        self.assertTrue(list((workspace.dir / 'raw' / '_rejected').glob('*broken.csv')))

    def test_truncated_download_is_rejected(self):
        workspace = Workspace(self)
        data = make_csv('rushing_bell_cow')
        workspace.put('cut.csv', data[: data.rindex(b'\n', 0, len(data) - 40) - 7])  # cut inside a data row
        report = workspace.run()
        self.assertEqual(workspace.outcomes(report)['cut.csv'], 'rejected')
        self.assertEqual(report['results'][0]['reason']['code'], 'ragged_row')

    def test_filtered_download_with_few_teams_is_partial_and_flagged_in_freshness(self):
        workspace = Workspace(self)
        workspace.put('few.csv', make_csv('receiving_advanced', teams=TEAMS[:4]))
        report = workspace.run()
        self.assertEqual(workspace.outcomes(report)['few.csv'], 'partial')
        self.assertIn('PARTIAL', [l for l in report['freshness'] if l.startswith('Receiving:')][0])

    def test_missing_and_stale_tables_are_never_current(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow', games=3))
        report = workspace.run()
        lines = {l.split(':')[0]: l for l in report['freshness']}
        self.assertIn('STALE', lines['Bell cow'])
        self.assertIn('MISSING', lines['Routes'])
        self.assertEqual(len(report['freshness']), sum(1 for t in REGISTRY['tables'].values() if t.get('weekly_expected', True)))
        fresh = json.loads((workspace.dir / 'manifests' / 'freshness.json').read_text(encoding='utf-8'))
        self.assertEqual({t['state'] for t in fresh['tables']}, {'stale', 'missing'})

    def test_public_status_contains_no_licensed_values(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow', mutate=lambda body, keys: body[0].__setitem__(keys.index('Rushing.ATT'), '31415')))
        workspace.run()
        fresh = json.loads((workspace.dir / 'manifests' / 'freshness.json').read_text(encoding='utf-8'))
        text = json.dumps(store.public_status(fresh))
        self.assertNotIn('31415', text)
        self.assertEqual(set(store.public_status(fresh)['tables'][0]), {'table', 'label', 'state', 'through_games'})

    def test_interrupted_import_resumes_cleanly(self):
        clean = Workspace(self)
        clean.put('a.csv', make_csv('rushing_bell_cow'))
        clean.put('b.csv', make_csv('passing_depth'))
        clean.run()
        crashed = Workspace(self)
        crashed.put('a.csv', make_csv('rushing_bell_cow'))
        crashed.put('b.csv', make_csv('passing_depth'))

        calls = []

        def boom():
            calls.append(1)
            if len(calls) == 2:
                raise KeyboardInterrupt('power loss')
        with self.assertRaises(KeyboardInterrupt):
            crashed.run(hooks={'after_normalized': boom})
        self.assertFalse((crashed.dir / 'manifests' / 'index.json').exists(), 'manifest is written last')
        (crashed.dir / 'normalized' / 'junk.json.tmp').write_bytes(b'{')
        report = crashed.run()
        self.assertEqual(report['temporary_files_removed'], 1)
        self.assertEqual(set(crashed.outcomes(report).values()), {'imported'})

        def snapshot(workspace):
            return {str(p.relative_to(workspace.dir)): p.read_bytes() for p in workspace.dir.rglob('*')
                    if p.is_file() and 'Inbox' not in p.parts and p.parent.name not in ('manifests',)}
        self.assertEqual(snapshot(crashed), snapshot(clean), 'a resumed import must equal an uninterrupted one')


class SchemaTests(unittest.TestCase):
    def prime(self):
        workspace = Workspace(self)
        workspace.put('ok.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        return workspace

    def test_missing_column_quarantines_and_keeps_previous_valid_snapshot(self):
        workspace = self.prime()
        good = store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')['sha256']
        workspace.put('ok.csv', make_csv('rushing_bell_cow', games=5, drop_columns={'Rushing.ATT'}))
        report = workspace.run(now=NOW + datetime.timedelta(days=7), expected_games=5, max_possible_games=6)
        self.assertEqual(workspace.outcomes(report)['ok.csv'], 'quarantined_schema')
        self.assertIn('Rushing.ATT', report['results'][0]['reason']['message'])
        self.assertEqual(store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')['sha256'], good)
        self.assertTrue(list((workspace.dir / 'raw' / '_quarantine').glob('*')))
        line = [l for l in report['freshness'] if l.startswith('Bell cow')][0]
        self.assertIn('STALE', line)

    def test_renamed_column_is_reported_as_possible_rename_and_blocked(self):
        workspace = self.prime()
        workspace.put('ok.csv', make_csv('rushing_bell_cow', games=5, rename={'Rushing.TM ATT': 'Rushing.TEAM ATT'}))
        report = workspace.run(now=NOW + datetime.timedelta(days=7), expected_games=5, max_possible_games=6)
        self.assertEqual(workspace.outcomes(report)['ok.csv'], 'quarantined_schema')
        self.assertIn('TEAM ATT', report['results'][0]['reason']['message'])

    def test_added_column_is_imported_but_surfaced_for_review(self):
        workspace = self.prime()
        workspace.put('ok.csv', make_csv('rushing_bell_cow', games=5, add_columns=['FPTS.NEW SHINY']))
        report = workspace.run(now=NOW + datetime.timedelta(days=7), expected_games=5, max_possible_games=6)
        result = report['results'][0]
        self.assertEqual(result['outcome'], 'imported')
        self.assertEqual(result['status'], 'imported_review')
        self.assertTrue(any('FPTS.NEW SHINY' in w for w in result['warnings']))
        document = json.loads(next((workspace.dir / 'normalized').rglob('through-week-05*.json')).read_text(encoding='utf-8'))
        classes = {c['key']: c['class'] for c in document['columns']}
        self.assertEqual(classes['FPTS.NEW SHINY'], 'UNREVIEWED')

    def test_changed_column_type_is_blocked(self):
        workspace = self.prime()
        workspace.put('ok.csv', make_csv('rushing_bell_cow', games=5, mutate=lambda body, keys: [row.__setitem__(keys.index('Rushing.ATT'), 'n/a') for row in body]))
        report = workspace.run(now=NOW + datetime.timedelta(days=7), expected_games=5, max_possible_games=6)
        self.assertEqual(workspace.outcomes(report)['ok.csv'], 'quarantined_schema')

    def test_every_registered_column_has_a_use_class(self):
        from fp_ingest import fields
        unreviewed = [(t['id'], c['key']) for t in REGISTRY['tables'].values() for c in t['columns']
                      if fields.classify_column(c['key'])['class'] == 'UNREVIEWED']
        self.assertEqual(unreviewed, [])


class IdentityTests(unittest.TestCase):
    def index(self, rows):
        return idmod.RosterIndex(rows)

    def test_teams_map_to_canonical_codes_and_unknown_is_an_error(self):
        self.assertEqual([idmod.canonical_team(c) for c in ('ARZ', 'BLT', 'CLV', 'HST', 'LA', 'Los Angeles Rams')], ['ARI', 'BAL', 'CLE', 'HOU', 'LA', 'LA'])
        with self.assertRaises(idmod.TeamError):
            idmod.canonical_team('XYZ')

    def test_suffix_nickname_accents_and_initials(self):
        roster = self.index([
            {'gsis_id': 'A', 'full_name': 'Kenneth Walker III', 'team': 'KC', 'position': 'RB'},
            {'gsis_id': 'B', 'full_name': 'J. Michael Sturdivant', 'team': 'GB', 'position': 'WR'},
            {'gsis_id': 'C', 'full_name': 'Amon-Ra St. Brown', 'team': 'DET', 'position': 'WR'},
            {'gsis_id': 'D', 'full_name': "Ja'Marr Chase", 'team': 'CIN', 'position': 'WR'},
            {'gsis_id': 'E', 'full_name': 'Donté Thornton Jr.', 'team': 'LV', 'position': 'WR'},
        ])
        self.assertEqual(roster.resolve('Kenneth Walker', 'KC', 'RB')['player_id'], 'A')
        self.assertEqual(roster.resolve('J. Sturdivant', 'GB', 'WR')['player_id'], 'B')
        self.assertEqual(roster.resolve('Amon-Ra St. Brown', 'DET', 'WR')['player_id'], 'C')
        self.assertEqual(roster.resolve('Ja’Marr Chase', 'CIN', 'WR')['player_id'], 'D')
        self.assertEqual(roster.resolve('Donte Thornton', 'LV', 'WR')['player_id'], 'E')

    def test_ambiguous_players_are_reported_not_guessed(self):
        roster = self.index([
            {'gsis_id': 'A', 'full_name': 'Mike Williams', 'team': 'NYJ', 'position': 'WR'},
            {'gsis_id': 'B', 'full_name': 'Mike Williams', 'team': 'NYJ', 'position': 'WR'},
            {'gsis_id': 'C', 'full_name': 'Josh Allen', 'team': 'BUF', 'position': 'QB'},
            {'gsis_id': 'D', 'full_name': 'Josh Allen', 'team': 'JAX', 'position': 'QB'},
        ])
        same_team = roster.resolve('Mike Williams', 'NYJ', 'WR')
        self.assertEqual((same_team['status'], same_team['player_id'], same_team['candidates']), ('ambiguous', None, ['A', 'B']))
        elsewhere = roster.resolve('Josh Allen', 'DAL', 'QB')  # right name, no team match, two league-wide candidates
        self.assertEqual((elsewhere['status'], elsewhere['player_id']), ('ambiguous', None))
        self.assertEqual(roster.resolve('Josh Allen', 'BUF', 'QB')['player_id'], 'C')
        self.assertEqual(roster.resolve('Nobody Real', 'BUF', 'QB')['status'], 'unmatched')
        self.assertEqual(roster.resolve('Josh Allen', 'ZZZ', 'QB')['status'], 'team_unknown')

    def test_roster_nicknames_match_on_the_legal_first_name_but_stay_flagged(self):
        roster = self.index([
            {'gsis_id': 'W', 'full_name': 'Ced Wilson', 'first_name': 'Cedrick', 'last_name': 'Wilson', 'team': 'MIA', 'position': 'WR'},
            {'gsis_id': 'K', 'full_name': 'Bam Knight', 'first_name': 'Zonovan', 'last_name': 'Knight', 'team': 'DET', 'position': 'RB'},
            {'gsis_id': 'T', 'full_name': 'Deven Thompkins', 'first_name': 'Deven', 'last_name': 'Thompkins', 'team': 'CAR', 'position': 'WR'},
        ])
        for name, team, position, pid in (('Cedrick Wilson', 'MIA', 'WR', 'W'), ('Zonovan Knight', 'DET', 'RB', 'K')):
            result = roster.resolve(name, team, position)
            self.assertEqual((result['status'], result['player_id'], result['method']), ('matched', pid, 'legal_name_team_position'))
        self.assertEqual(roster.resolve('Devin Thompkins', 'CAR', 'WR')['status'], 'unmatched', 'a different spelling is not guessed')
        self.assertEqual(roster.resolve('Zonovan Knight', 'MIA', 'RB')['status'], 'unmatched', 'the team must agree')

    def test_committed_aliases_resolve_only_their_exact_name_and_team(self):
        committed = json.loads((ROOT / 'config' / 'fantasy_points_aliases.json').read_text(encoding='utf-8'))
        self.assertEqual(set(committed['aliases']), set(committed['evidence']), 'every alias carries its evidence')
        roster = idmod.RosterIndex([{'gsis_id': '00-0037091', 'full_name': 'Bo Melton', 'team': 'GB', 'position': 'DB'}], committed['aliases'])
        found = roster.resolve('Bo Melton', 'GB', 'WR')
        self.assertEqual((found['status'], found['player_id'], found['method']), ('matched', '00-0037091', 'alias'))
        self.assertNotEqual(roster.resolve('Bo Melton', 'DAL', 'WR')['method'], 'alias')

    def test_traded_player_matches_by_name_and_position_but_is_flagged_for_review(self):
        roster = self.index([{'gsis_id': 'T', 'full_name': 'Traded Guy', 'team': 'MIA', 'position': 'WR'}])
        result = roster.resolve('Traded Guy', 'DEN', 'WR')
        self.assertEqual((result['status'], result['player_id'], result['method']), ('matched', 'T', 'name_position'))

        def rename(body, keys):
            body[0][keys.index('Player Details.Name')] = 'Traded Guy'
            body[0][keys.index('Player Details.POS')] = 'WR'
        workspace = Workspace(self, rosters=lambda season: idmod.RosterIndex(roster_rows([{'gsis_id': 'T', 'full_name': 'Traded Guy', 'team': 'MIA', 'position': 'WR'}])))
        workspace.put('a.csv', make_csv('rushing_bell_cow', mutate=rename))
        report = workspace.run()
        document = json.loads(next((workspace.dir / 'normalized').rglob('*.json')).read_text(encoding='utf-8'))
        traded = document['rows'][0]['entity']
        self.assertEqual((traded['player_id'], traded['match']['method'], traded['match']['review']), ('T', 'name_position', True))
        self.assertEqual([r['name'] for r in report['identity_review']], ['Traded Guy'])

    def test_unmatched_rows_are_kept_with_null_id_and_listed(self):
        workspace = Workspace(self, rosters=lambda season: idmod.RosterIndex(roster_rows()[:-3]))
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        report = workspace.run()
        unresolved = report['identity_unresolved']
        self.assertEqual(len(unresolved), 3)
        document = json.loads(next((workspace.dir / 'normalized').rglob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual(len(document['rows']), len(TEAMS) * 3, 'unresolved players are kept, not dropped')
        self.assertEqual(sum(1 for r in document['rows'] if r['entity']['player_id'] is None), 3)

    def test_missing_roster_never_invents_ids(self):
        workspace = Workspace(self, rosters=lambda season: None)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        document = json.loads(next((workspace.dir / 'normalized').rglob('*.json')).read_text(encoding='utf-8'))
        self.assertTrue(all(r['entity']['player_id'] is None and r['entity']['match']['status'] == 'no_roster' for r in document['rows']))

    def test_team_tables_resolve_through_full_names_and_opponent(self):
        workspace = Workspace(self)
        workspace.put('t.csv', make_csv('line_matchups'))
        workspace.run()
        document = json.loads(next((workspace.dir / 'normalized').rglob('*.json')).read_text(encoding='utf-8'))
        row = next(r for r in document['rows'] if r['entity']['team'] == 'BAL')
        self.assertEqual((row['entity']['team'], row['context']['opponent']), ('BAL', 'SF'))
        self.assertTrue(document['forward_looking'])
        self.assertEqual(document['target_game_hint'], 5)


def pit(manifest, season, table_id, for_season, for_week, known_by=FUTURE):
    return store.point_in_time(manifest, season, table_id, for_season, for_week, known_by=known_by)


class LeakageTests(unittest.TestCase):
    def build(self):
        workspace = Workspace(self)
        for games in (2, 3, 4):
            workspace.put(f'w{games}.csv', make_csv('rushing_bell_cow', games=games, mutate=lambda body, keys, g=games: body[0].__setitem__(keys.index('Rushing.ATT'), str(g * 10))))
            workspace.run(now=NOW + datetime.timedelta(days=games), expected_games=games, max_possible_games=games + 1)
        return workspace

    def test_current_season_prediction_sees_only_earlier_games(self):
        manifest = self.build().manifest()
        pick = lambda week: pit(manifest, 2026, 'rushing_bell_cow', 2026, week)
        self.assertIsNone(pick(2), 'week 2 may only use data through week 1; none was captured')
        self.assertEqual(pick(3)['through_games'], 2)
        self.assertEqual(pick(4)['through_games'], 3)
        self.assertEqual(pick(9)['through_games'], 4)

    def test_correction_imported_after_the_cutoff_is_invisible_before_it(self):
        workspace = self.build()
        workspace.put('fix.csv', make_csv('rushing_bell_cow', games=3, mutate=lambda body, keys: body[0].__setitem__(keys.index('Rushing.ATT'), '31')))
        workspace.run(now=NOW + datetime.timedelta(days=30), expected_games=4, max_possible_games=5)
        manifest = workspace.manifest()
        early = pit(manifest, 2026, 'rushing_bell_cow', 2026, 4, known_by=iso(NOW + datetime.timedelta(days=5)))
        late = pit(manifest, 2026, 'rushing_bell_cow', 2026, 4)
        self.assertNotEqual(early['sha256'], late['sha256'])
        self.assertEqual(early['through_games'], 3)
        self.assertTrue(late.get('revision_of') == early['sha256'])

    def test_retrospective_same_season_export_is_never_usable_inside_that_season(self):
        workspace = Workspace(self)
        workspace.put('old.csv', make_csv('rushing_bell_cow', season=2025, games=17))
        workspace.run()
        manifest = workspace.manifest()
        self.assertIsNone(pit(manifest, 2025, 'rushing_bell_cow', 2025, 10), 'full-season totals contain weeks 10-17')
        self.assertIsNone(pit(manifest, 2025, 'rushing_bell_cow', 2025, 18))
        self.assertIsNotNone(pit(manifest, 2025, 'rushing_bell_cow', 2026, 1), 'a finished season is fair game for next season')
        self.assertIsNone(pit(manifest, 2025, 'rushing_bell_cow', 2024, 1), 'and never for an earlier one')

    def test_forward_looking_tables_apply_only_to_the_week_they_were_made_for(self):
        workspace = Workspace(self)
        workspace.put('m.csv', make_csv('wr_coverage_matchup', games=4))
        workspace.run()
        manifest = workspace.manifest()
        self.assertIsNotNone(pit(manifest, 2026, 'wr_coverage_matchup', 2026, 5))
        self.assertIsNone(pit(manifest, 2026, 'wr_coverage_matchup', 2026, 6), 'its OPP column is the week-5 opponent')
        self.assertIsNone(pit(manifest, 2026, 'wr_coverage_matchup', 2026, 4))

    def test_missing_snapshot_is_none_not_zero(self):
        manifest = Workspace(self).manifest()
        self.assertIsNone(pit(manifest, 2026, 'rushing_bell_cow', 2026, 5))


def iso(moment):
    return pl.iso(moment)


def set_mtime(path, moment):
    stamp = moment.timestamp()
    os.utime(path, (stamp, stamp))


class QaRegressionTests(unittest.TestCase):
    """Defects found by the independent QA review; each of these failed before the fix."""

    def corrected(self, value='99'):
        return make_csv('rushing_bell_cow', mutate=lambda body, keys: body[0].__setitem__(keys.index('Rushing.ATT'), value))

    def test_revision_order_follows_download_time_not_filename(self):
        workspace = Workspace(self)
        workspace.put('rush.csv', make_csv('rushing_bell_cow'))
        workspace.put('rush (1).csv', self.corrected())  # ' (1)' sorts before '.csv'
        set_mtime(workspace.inbox / 'rush.csv', NOW - datetime.timedelta(hours=5))
        set_mtime(workspace.inbox / 'rush (1).csv', NOW - datetime.timedelta(hours=1))
        workspace.run()
        current = store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')
        self.assertEqual(current['original_filename'], 'rush (1).csv')

    def test_an_older_download_arriving_later_does_not_replace_a_newer_one(self):
        workspace = Workspace(self)
        workspace.put('new.csv', self.corrected())
        set_mtime(workspace.inbox / 'new.csv', NOW)
        workspace.run()
        workspace.put('old.csv', make_csv('rushing_bell_cow'))
        set_mtime(workspace.inbox / 'old.csv', NOW - datetime.timedelta(days=2))
        report = workspace.run(now=NOW + datetime.timedelta(days=1))
        self.assertEqual(workspace.outcomes(report)['old.csv'], 'older_revision_ignored')
        self.assertEqual(store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')['original_filename'], 'new.csv')

    def test_repairing_a_file_does_not_flip_the_revision_chain(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        workspace.put('b.csv', self.corrected())
        set_mtime(workspace.inbox / 'a.csv', NOW - datetime.timedelta(hours=3))
        set_mtime(workspace.inbox / 'b.csv', NOW - datetime.timedelta(hours=1))
        workspace.run()
        before = store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')['sha256']
        old = next(e for e in workspace.manifest().files.values() if e['original_filename'] == 'a.csv')
        (workspace.dir / old['normalized_path']).unlink()
        workspace.run(now=NOW + datetime.timedelta(days=1))
        manifest = workspace.manifest()
        self.assertEqual(store.current_entry(manifest, 2026, 'rushing_bell_cow')['sha256'], before)
        self.assertEqual(manifest.files[old['sha256']]['superseded_by'], before)

    def test_operator_override_is_bounded_and_never_restates_existing_files(self):
        workspace = Workspace(self)
        workspace.put('w4.csv', make_csv('rushing_bell_cow', games=4))
        workspace.run()
        workspace.put('w5.csv', make_csv('passing_depth', games=1))
        workspace.run(through_override=5)
        manifest = workspace.manifest()
        self.assertEqual(sorted(e['through_games'] for e in manifest.files.values()), [4, 5])
        self.assertEqual(len(list((workspace.dir / 'normalized').rglob('*.json'))), 2, 'no orphan restated copy')
        high = Workspace(self)
        high.put('x.csv', make_csv('rushing_bell_cow', games=1))
        report = high.run(through_override=17)
        self.assertEqual(report['results'][0]['reason']['code'], 'override_invalid')
        past = Workspace(self)
        past.put('p.csv', make_csv('rushing_bell_cow', season=2025, games=17))
        past.run(through_override=5)
        self.assertEqual(store.current_entry(past.manifest(), 2025, 'rushing_bell_cow')['scope'], 'full_season')

    def test_known_at_starts_when_data_is_accepted_not_when_first_seen(self):
        workspace = Workspace(self)
        workspace.put('late.csv', make_csv('rushing_bell_cow', games=5))
        first = workspace.run(max_possible_games=4)
        self.assertEqual(workspace.outcomes(first)['late.csv'], 'rejected')
        later = NOW + datetime.timedelta(days=30)
        workspace.run(now=later, max_possible_games=6, expected_games=5)
        entry = store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow')
        self.assertEqual(entry['first_imported_at'], pl.iso(later))
        self.assertEqual(entry['first_seen_at'], pl.iso(NOW))
        self.assertIsNone(pit(workspace.manifest(), 2026, 'rushing_bell_cow', 2026, 7, known_by=pl.iso(NOW + datetime.timedelta(days=1))))

    def test_same_season_lookup_requires_a_cutoff(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        with self.assertRaises(ValueError):
            store.point_in_time(workspace.manifest(), 2026, 'rushing_bell_cow', 2026, 6)

    def test_week_labels_after_every_bye_hold_back_one_more_week(self):
        workspace = Workspace(self)
        workspace.put('g14.csv', make_csv('rushing_bell_cow', games=14))
        workspace.run(max_possible_games=15, expected_games=14)
        manifest = workspace.manifest()
        self.assertIsNone(pit(manifest, 2026, 'rushing_bell_cow', 2026, 15), 'a 14-game total may already include week 15 results')
        self.assertIsNotNone(pit(manifest, 2026, 'rushing_bell_cow', 2026, 16))

    def test_a_later_partial_reexport_never_hides_the_complete_snapshot_as_of_a_cutoff(self):
        workspace = Workspace(self)
        workspace.put('full.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        workspace.put('few.csv', make_csv('rushing_bell_cow', teams=TEAMS[:5]))
        workspace.run(now=NOW + datetime.timedelta(days=1))
        found = pit(workspace.manifest(), 2026, 'rushing_bell_cow', 2026, 6)
        self.assertEqual(found['status'], 'imported')

    def test_offseason_exports_of_the_just_finished_season_are_not_live(self):
        workspace = Workspace(self)
        workspace.put('mid.csv', make_csv('rushing_bell_cow', games=9))
        report = workspace.run(now=datetime.datetime(2027, 3, 1, tzinfo=datetime.timezone.utc), max_possible_games=None)
        self.assertEqual(workspace.outcomes(report)['mid.csv'], 'held_scope')
        workspace.put('full.csv', make_csv('passing_depth', games=17))
        workspace.run(now=datetime.datetime(2027, 3, 1, tzinfo=datetime.timezone.utc), max_possible_games=None)
        entry = store.current_entry(workspace.manifest(), 2026, 'passing_depth')
        self.assertEqual((entry['scope'], entry['known_live']), ('full_season', False))

    def test_surprising_cells_reject_the_file_and_preserve_it(self):
        workspace = Workspace(self)
        workspace.put('na.csv', make_csv('rushing_bell_cow', mutate=lambda body, keys: body[0].__setitem__(keys.index('Player Details.G'), 'N/A')))
        workspace.put('lead.csv', b'\n' + make_csv('passing_depth'))
        workspace.put('ok.csv', make_csv('rushing_advanced'))
        report = workspace.run()
        outcomes = workspace.outcomes(report)
        self.assertEqual((outcomes['na.csv'], outcomes['lead.csv'], outcomes['ok.csv']), ('rejected', 'rejected', 'imported'))
        self.assertEqual(len(list((workspace.dir / 'raw' / '_rejected').glob('*'))), 2)
        info, _ = pl.inspect_bytes('x.csv', b'Rank,Name\n', REGISTRY)  # inspect never raises
        self.assertIn('error', info)

    def test_a_blank_line_inside_the_data_is_an_error_not_silent_row_loss(self):
        data = make_csv('rushing_bell_cow')
        lines = data.split(b'\n')
        lines.insert(40, b'')
        with self.assertRaises(ParseError) as caught:
            parse_export(b'\n'.join(lines))
        self.assertEqual(caught.exception.code, 'blank_in_data')

    def test_non_skill_roster_positions_do_not_match_skill_rows(self):
        roster = idmod.RosterIndex([
            {'gsis_id': 'OL1', 'full_name': 'Chris Moore', 'team': 'HOU', 'position': 'OL'},
            {'gsis_id': 'WR1', 'full_name': 'Justin Jefferson', 'team': 'MIN', 'position': 'WR'},
            {'gsis_id': 'LB1', 'full_name': 'Justin Jefferson', 'team': 'CLE', 'position': 'LB'},
            {'gsis_id': 'NP', 'full_name': 'Unknown Position', 'team': 'DEN', 'position': None},
        ])
        self.assertEqual(roster.resolve('Chris Moore', 'HOU', 'WR')['status'], 'unmatched')
        moved = roster.resolve('Justin Jefferson', 'DAL', 'WR')
        self.assertEqual((moved['status'], moved['player_id']), ('matched', 'WR1'))
        self.assertEqual(roster.resolve('Unknown Position', 'DEN', 'WR')['player_id'], 'NP')

    def test_locked_temp_file_and_bad_manifest_do_not_abort_the_run(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        junk = workspace.dir / 'normalized' / 'x.json.tmp'
        junk.parent.mkdir(parents=True)
        junk.write_bytes(b'{')
        real_unlink = Path.unlink

        def locked(self_path, *args, **kwargs):
            if self_path.name.endswith('.tmp'):
                raise PermissionError('in use')
            return real_unlink(self_path, *args, **kwargs)
        with patch.object(Path, 'unlink', locked):
            report = workspace.run()
        self.assertEqual(workspace.outcomes(report)['a.csv'], 'imported')
        self.assertEqual(len(report['temporary_files_failed']), 1)
        (workspace.dir / 'manifests' / 'index.json').write_text('{"version": 1}', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            workspace.importer()

    def test_a_second_import_cannot_run_at_the_same_time(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        lock = workspace.dir / 'manifests' / '.import.lock'
        lock.parent.mkdir(parents=True)
        lock.write_text('999', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            workspace.run()
        set_mtime(lock, NOW - datetime.timedelta(days=1))  # a stale lock from a crash is cleared
        os.utime(lock, (1, 1))
        workspace.run()
        self.assertFalse(lock.exists())

    def test_verify_command_reports_a_tampered_archive(self):
        import fantasy_points
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        self.assertEqual(fantasy_points.main(['--root', str(workspace.dir), 'verify']), 0)
        next((workspace.dir / 'raw').rglob('*.csv')).write_bytes(b'tampered')
        self.assertEqual(fantasy_points.main(['--root', str(workspace.dir), 'verify']), 1)

    def test_committed_registry_carries_no_vendor_glossary_text(self):
        self.assertTrue(all('glossary' not in table for table in REGISTRY['tables'].values()))


class HistoricalSnapshotTests(unittest.TestCase):
    """Past seasons: only an operator-declared cumulative (weeks 1-N) export is a point-in-time snapshot; nothing is inferred."""

    def cumulative_series(self, workspace, games_list=(3, 6, 9), season=2023):
        for games in games_list:
            workspace.put(f'h{games}.csv', make_csv('rushing_bell_cow', season=season, games=games,
                                                    mutate=lambda body, keys, g=games: body[0].__setitem__(keys.index('Rushing.ATT'), str(g))))
        for path in workspace.inbox.glob('h*.csv'):
            set_mtime(path, NOW - datetime.timedelta(days=1))
        return workspace.run(declare='cumulative', only=['*'], max_possible_games=None)

    def test_undeclared_partial_past_season_is_held_with_instructions(self):
        workspace = Workspace(self)
        workspace.put('h.csv', make_csv('rushing_bell_cow', season=2023, games=9))
        report = workspace.run(max_possible_games=None)
        self.assertEqual(workspace.outcomes(report)['h.csv'], 'held_scope')
        self.assertIn('--declare cumulative', report['results'][0]['reason']['message'])

    def test_declared_cumulative_exports_are_true_point_in_time_snapshots(self):
        workspace = Workspace(self)
        report = self.cumulative_series(workspace)
        self.assertEqual(set(workspace.outcomes(report).values()), {'imported'})
        self.assertEqual(sorted(p.parent.name for p in (workspace.dir / 'raw' / '2023').rglob('*.csv')),
                         ['cumulative-through-game-03', 'cumulative-through-game-06', 'cumulative-through-game-09'])
        manifest = workspace.manifest()
        known_by = '2023-12-01T00:00:00Z'  # long before they were downloaded: the content, not the download date, is what counts
        seen = {week: pit(manifest, 2023, 'rushing_bell_cow', 2023, week, known_by=known_by) for week in (2, 4, 7, 10, 18)}
        self.assertIsNone(seen[2], 'nothing known before game 3')
        self.assertEqual([seen[w]['through_games'] for w in (4, 7, 10, 18)], [3, 6, 9, 9])
        self.assertTrue(all(e['known_live'] is False and e['declared_by'] == 'operator' for e in manifest.files.values()))

    def test_cumulative_snapshot_never_leaks_the_target_week(self):
        workspace = Workspace(self)
        self.cumulative_series(workspace)
        manifest = workspace.manifest()
        self.assertIsNone(pit(manifest, 2023, 'rushing_bell_cow', 2023, 3), 'week 3 prediction cannot use a 3-game total')
        self.assertEqual(pit(manifest, 2023, 'rushing_bell_cow', 2023, 4)['through_games'], 3)

    def test_declaration_does_not_apply_to_full_seasons_or_live_files(self):
        workspace = Workspace(self)
        workspace.put('full.csv', make_csv('rushing_bell_cow', season=2022, games=17))
        workspace.put('live.csv', make_csv('passing_depth', games=4))
        workspace.run(declare='cumulative', only=['*'])
        manifest = workspace.manifest()
        self.assertEqual(store.current_entry(manifest, 2022, 'rushing_bell_cow')['scope'], 'full_season')
        live = store.current_entry(manifest, 2026, 'passing_depth')
        self.assertEqual((live['scope'], live['known_live']), ('season_to_date', True))

    def test_declared_single_weeks_are_stored_separately_and_never_served_as_cumulative(self):
        workspace = Workspace(self)
        workspace.put('w5.csv', make_csv('rushing_bell_cow', season=2023, games=1))
        workspace.run(declare='week:5', only=['*'], max_possible_games=None)
        manifest = workspace.manifest()
        self.assertEqual([e['week'] for e in store.weekly_entries(manifest, 2023, 'rushing_bell_cow')], [5])
        self.assertTrue(list((workspace.dir / 'raw' / '2023' / 'week-05').glob('*.csv')))
        for week in (2, 6, 10, 18):
            self.assertIsNone(pit(manifest, 2023, 'rushing_bell_cow', 2023, week))
        self.assertIsNone(store.current_entry(manifest, 2023, 'rushing_bell_cow'))
        bad = Workspace(self)
        bad.put('c.csv', make_csv('rushing_bell_cow', season=2023, games=9))
        report = bad.run(declare='week:5', only=['*'], max_possible_games=None)
        self.assertEqual(report['results'][0]['reason']['code'], 'declared_week_but_cumulative')

    def test_corrected_historical_snapshot_is_a_revision_of_the_same_games(self):
        workspace = Workspace(self)
        self.cumulative_series(workspace, games_list=(6,))
        workspace.put('fix.csv', make_csv('rushing_bell_cow', season=2023, games=6, mutate=lambda body, keys: body[0].__setitem__(keys.index('Rushing.ATT'), '77')))
        set_mtime(workspace.inbox / 'fix.csv', NOW + datetime.timedelta(hours=1))
        report = workspace.run(declare='cumulative', only=['*'], max_possible_games=None, now=NOW + datetime.timedelta(days=1))
        self.assertEqual(workspace.outcomes(report)['fix.csv'], 'revision')
        self.assertEqual(pit(workspace.manifest(), 2023, 'rushing_bell_cow', 2023, 8)['original_filename'], 'fix.csv')

    def test_rerunning_without_the_declaration_is_a_no_op(self):
        workspace = Workspace(self)
        self.cumulative_series(workspace)
        report = workspace.run(max_possible_games=None, now=NOW + datetime.timedelta(days=1))
        self.assertEqual(set(workspace.outcomes(report).values()), {'duplicate'})

    def test_one_game_cumulative_declaration_is_refused_as_a_single_week(self):
        workspace = Workspace(self)
        workspace.put('w5.csv', make_csv('rushing_bell_cow', season=2023, games=1))
        report = workspace.run(declare='cumulative', only=['*'], max_possible_games=None)
        self.assertEqual(workspace.outcomes(report)['w5.csv'], 'held_scope')
        self.assertEqual(report['results'][0]['reason']['code'], 'cumulative_ambiguous')
        self.assertEqual(list((workspace.dir / 'normalized').rglob('*.json')), [])

    def test_a_declaration_must_name_its_files_and_only_touches_them(self):
        workspace = Workspace(self)
        with self.assertRaises(ValueError):
            workspace.importer(declare='cumulative')
        workspace.put('cum_a.csv', make_csv('rushing_bell_cow', season=2023, games=6))
        workspace.put('single.csv', make_csv('passing_depth', season=2023, games=1))
        report = workspace.run(declare='cumulative', only=['cum_*'], max_possible_games=None)
        self.assertEqual(workspace.outcomes(report), {'cum_a.csv': 'imported'})
        report = workspace.run(declare='week:7', only=['single.csv'], max_possible_games=None)
        self.assertEqual(workspace.outcomes(report), {'single.csv': 'imported'})
        manifest = workspace.manifest()
        self.assertIsNone(store.current_entry(manifest, 2023, 'rushing_bell_cow'), 'a historical cumulative snapshot is not a live current one')
        self.assertEqual([e['week'] for e in store.weekly_entries(manifest, 2023, 'passing_depth')], [7])
        self.assertEqual(pit(manifest, 2023, 'rushing_bell_cow', 2023, 9)['through_games'], 6)
        self.assertIsNone(pit(manifest, 2023, 'passing_depth', 2023, 9))

    def test_bad_declarations_are_refused(self):
        for text in ('week:0', 'week:x', 'weekly', 'week:30'):
            with self.assertRaises(ValueError):
                pl.parse_declare(text)


class FullSeasonHistoryTests(unittest.TestCase):
    """The 2025 pilot: completed seasons with traded players, mixed filenames and tables the provider does not offer for every year."""

    def full(self, table_id='rushing_bell_cow', season=2025, **kw):
        return make_csv(table_id, season=season, games=17, **kw)

    def traded(self, order='DAL, ARZ'):
        def mutate(body, keys):
            body[0][keys.index('Player Details.Team')] = order
        return mutate

    def test_traded_players_with_several_teams_are_matched_not_rejected(self):
        for order in ('DAL, ARZ', 'ARZ, DAL'):  # the order of teams in the export carries no meaning
            workspace = Workspace(self)
            workspace.put('a.csv', self.full(mutate=self.traded(order)))
            report = workspace.run()
            self.assertEqual(workspace.outcomes(report)['a.csv'], 'imported', order)
            document = json.loads(next((workspace.dir / 'normalized').rglob('*.json')).read_text(encoding='utf-8'))
            entity = document['rows'][0]['entity']
            self.assertEqual((entity['multi_team'], entity['team'], sorted(entity['teams'])), (True, None, ['ARI', 'DAL']))
            self.assertEqual(entity['match']['status'], 'matched')
            self.assertTrue(entity['player_id'])

    def test_an_unknown_team_inside_a_multi_team_cell_rejects_the_file(self):
        workspace = Workspace(self)
        workspace.put('a.csv', self.full(mutate=self.traded('ARZ, XYZ')))
        self.assertEqual(workspace.outcomes(workspace.run())['a.csv'], 'rejected')

    def test_repeated_players_in_one_export_are_rejected(self):
        def twice(body, keys):
            body.append(list(body[0]))
        workspace = Workspace(self)
        workspace.put('a.csv', self.full(mutate=twice))
        report = workspace.run()
        self.assertEqual(report['results'][0]['reason']['code'], 'duplicate_rows')

    def test_filenames_and_copy_suffixes_never_decide_the_season(self):
        workspace = Workspace(self)
        workspace.put('rushingBellCowExport (1).csv', make_csv('rushing_bell_cow', season=2026, games=4))  # the 2026 file got the (1)
        workspace.put('rushingBellCowExport.csv', self.full())  # and the 2025 file kept the plain name
        report = workspace.run()
        self.assertEqual(set(workspace.outcomes(report).values()), {'imported'})
        manifest = workspace.manifest()
        a, b = store.current_entry(manifest, 2025, 'rushing_bell_cow'), store.current_entry(manifest, 2026, 'rushing_bell_cow')
        self.assertEqual((a['original_filename'], a['scope'], a['through_games']), ('rushingBellCowExport.csv', 'full_season', 17))
        self.assertEqual((b['original_filename'], b['scope'], b['through_games']), ('rushingBellCowExport (1).csv', 'season_to_date', 4))
        self.assertNotEqual(a['sha256'], b['sha256'])

    def test_importing_another_season_never_touches_existing_entries_or_files(self):
        workspace = Workspace(self)
        workspace.put('now.csv', make_csv('rushing_bell_cow', season=2026, games=4))
        workspace.run()
        before = {str(p): p.read_bytes() for p in workspace.dir.rglob('*') if p.is_file() and 'manifests' not in p.parts}
        entry_before = dict(store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow'))
        workspace.put('old.csv', self.full())
        workspace.run(now=NOW + datetime.timedelta(days=1))
        for path, content in before.items():
            self.assertEqual(Path(path).read_bytes(), content)
        self.assertEqual(store.current_entry(workspace.manifest(), 2026, 'rushing_bell_cow'), entry_before)
        self.assertFalse(any(e.get('superseded_by') for e in workspace.manifest().files.values()), 'seasons never supersede each other')

    def test_full_season_is_flagged_as_retrospective_in_metadata(self):
        workspace = Workspace(self)
        workspace.put('old.csv', self.full())
        workspace.put('now.csv', make_csv('passing_depth', season=2026, games=4))
        workspace.run()
        docs = {d['season']: d for d in (json.loads(p.read_text(encoding='utf-8')) for p in (workspace.dir / 'normalized').rglob('*.json'))}
        self.assertFalse(docs[2025]['research_boundary']['same_season_point_in_time'])
        self.assertIn('input to any prediction or backtest for a week of the same season', docs[2025]['research_boundary']['forbidden_uses'])
        self.assertTrue(docs[2026]['research_boundary']['same_season_point_in_time'])
        self.assertFalse(store.current_entry(workspace.manifest(), 2025, 'rushing_bell_cow')['same_season_point_in_time'])

    def test_availability_separates_provider_gaps_from_failures_and_unknowns(self):
        from fp_ingest import history
        workspace = Workspace(self)
        workspace.put('a.csv', self.full('rushing_bell_cow'))
        workspace.put('b.csv', self.full('passing_depth', mutate=lambda body, keys: body.append(list(body[0]))))  # a bad file: duplicate rows
        workspace.run()
        declarations = {'2025': {'line_matchups': {'evidence': 'test'}}}
        matrix = history.availability(REGISTRY, workspace.manifest(), declarations)['tables']
        self.assertEqual(matrix['rushing_bell_cow']['2025']['status'], 'AVAILABLE')
        self.assertEqual(matrix['passing_depth']['2025']['status'], 'IMPORT_PROBLEM')
        self.assertEqual(matrix['line_matchups']['2025']['status'], 'NOT_OBTAINED')
        self.assertEqual(matrix['qb_coverage_matchup']['2025']['status'], 'AVAILABILITY_UNCONFIRMED')
        self.assertEqual(matrix['rushing_bell_cow']['2024']['status'], 'AVAILABILITY_UNCONFIRMED')
        self.assertEqual(sorted(matrix['rushing_bell_cow']), ['2021', '2022', '2023', '2024', '2025', '2026'])

    def test_availability_never_calls_a_gap_confirmed_unless_confirmed(self):
        from fp_ingest import history
        workspace = Workspace(self)
        workspace.put('a.csv', self.full('rushing_bell_cow'))
        workspace.run()
        declarations = {'2025': {'line_matchups': {'evidence': 'no file'},
                                 'qb_coverage_matchup': {'status': 'not_obtained', 'evidence': 'no file'},
                                 'wr_coverage_matchup': {'status': 'provider_unavailable', 'evidence': 'confirmed in the Fantasy Points UI'}}}
        matrix = history.availability(REGISTRY, workspace.manifest(), declarations)['tables']
        self.assertEqual(matrix['line_matchups']['2025']['status'], 'NOT_OBTAINED')
        self.assertEqual(matrix['qb_coverage_matchup']['2025']['status'], 'NOT_OBTAINED')
        self.assertEqual(matrix['wr_coverage_matchup']['2025']['status'], 'PROVIDER_UNAVAILABLE_CONFIRMED')
        committed = json.loads((ROOT / 'config' / 'fantasy_points_availability.json').read_text(encoding='utf-8'))['declarations']
        self.assertTrue(all(item.get('status') != 'provider_unavailable' for season in committed.values() for item in season.values()),
                        'nothing may be committed as confirmed-unavailable until it is confirmed')

    def test_every_command_runs_against_a_real_looking_archive(self):
        """The CLI printers must handle every status the library can produce (a missing label once crashed `availability`)."""
        import contextlib
        import fantasy_points
        from fp_ingest import history
        workspace = Workspace(self)
        workspace.put('a.csv', self.full('rushing_bell_cow'))
        workspace.put('b.csv', self.full('passing_depth', mutate=lambda body, keys: body.append(list(body[0]))))
        workspace.run()
        with patch.object(history, 'load_config', lambda *a: {'downloaded_seasons': [2025], 'declarations': {'2025': {'line_matchups': {'evidence': 'x'}, 'qb_coverage_matchup': {'status': 'provider_unavailable'}}}}):
            for command in (['status'], ['verify'], ['availability'], ['compat'], ['inventory'], ['fields']):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = fantasy_points.main(['--root', str(workspace.dir), '--current-season', '2026', *command])
                self.assertIn(code, (0, 1), command)
        matrix = json.loads((workspace.dir / 'manifests' / 'availability.json').read_text(encoding='utf-8'))['tables']
        self.assertEqual({matrix['line_matchups']['2025']['status'], matrix['qb_coverage_matchup']['2025']['status'], matrix['passing_depth']['2025']['status']},
                         {'NOT_OBTAINED', 'PROVIDER_UNAVAILABLE_CONFIRMED', 'IMPORT_PROBLEM'})

    def test_every_import_is_tagged_regular_season_and_full_seasons_are_retrospective(self):
        workspace = Workspace(self)
        workspace.put('old.csv', self.full())
        workspace.put('now.csv', make_csv('passing_depth', games=4))
        workspace.run()
        for entry in workspace.manifest().files.values():
            self.assertEqual((entry['season_scope'], entry['season_scope_source']), ('regular_season', 'operator_statement'))
        docs = {d['season']: d for d in (json.loads(p.read_text(encoding='utf-8')) for p in (workspace.dir / 'normalized').rglob('*.json'))}
        self.assertEqual(docs[2025]['research_boundary']['season_scope'], 'regular_season')
        self.assertFalse(docs[2025]['research_boundary']['same_season_point_in_time'])
        from fp_ingest import history
        cell = history.availability(REGISTRY, workspace.manifest(), {})['tables']['rushing_bell_cow']['2025']
        self.assertEqual(cell['season_scope'], 'regular_season')

    def test_games_above_17_are_explained_for_traded_players_and_flagged_otherwise(self):
        def traded(body, keys):
            body[0][keys.index('Player Details.G')] = '18'
            body[0][keys.index('Player Details.Team')] = 'DAL, ARZ'
        workspace = Workspace(self)
        workspace.put('a.csv', self.full(mutate=traded))
        report = workspace.run()
        self.assertTrue(any('traded player' in w and 'not an error' in w for w in report['results'][0]['warnings']))
        single = Workspace(self)
        single.put('a.csv', self.full(mutate=lambda body, keys: body[0].__setitem__(keys.index('Player Details.G'), '18')))
        self.assertTrue(any('suspicious' in w for w in single.run()['results'][0]['warnings']))

    def test_two_rows_for_one_name_with_different_numbers_are_kept_unresolved_never_merged(self):
        def split(body, keys):
            twin = list(body[0])
            twin[keys.index('Rushing.ATT')] = '7'
            twin[keys.index('Player Details.Rank')] = '999'
            body.append(twin)
        workspace = Workspace(self)
        workspace.put('a.csv', self.full(mutate=split))
        report = workspace.run()
        self.assertEqual(workspace.outcomes(report)['a.csv'], 'imported')
        document = json.loads(next((workspace.dir / 'normalized').rglob('*.json')).read_text(encoding='utf-8'))
        twins = [r for r in document['rows'] if r['entity']['split_entity']]
        self.assertEqual(len(twins), 2)
        self.assertTrue(all(r['entity']['player_id'] is None and r['entity']['match']['status'] == 'ambiguous' for r in twins))
        self.assertTrue(any('never merged' in w for w in report['results'][0]['warnings']))

    def test_franchise_names_from_earlier_seasons_resolve(self):
        self.assertEqual(idmod.canonical_team('Washington Football Team'), 'WAS')
        self.assertEqual(idmod.canonical_teams('WFT, ARZ'), ['WAS', 'ARI'])

    def test_older_importer_output_is_rederived_from_raw_without_changing_history(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        workspace.run()
        manifest = workspace.manifest()
        entry = next(iter(manifest.files.values()))
        entry['importer_version'] = 1
        entry.pop('same_season_point_in_time', None)
        first_seen = entry['first_imported_at']
        manifest.save()
        report = workspace.run(now=NOW + datetime.timedelta(days=3))
        self.assertEqual(workspace.outcomes(report)['a.csv'], 'repaired')
        refreshed = next(iter(workspace.manifest().files.values()))
        self.assertEqual((refreshed['first_imported_at'], refreshed['importer_version']), (first_seen, pl.IMPORTER_VERSION))
        self.assertEqual(workspace.outcomes(workspace.run(now=NOW + datetime.timedelta(days=4)))['a.csv'], 'duplicate')

    def test_optional_tables_are_not_reported_missing_but_show_when_present(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        lines = workspace.run()['freshness']
        self.assertFalse(any(l.startswith('Passing basic') for l in lines))
        workspace.put('b.csv', make_csv('passing_basic'))
        lines = workspace.run(now=NOW + datetime.timedelta(days=1))['freshness']
        self.assertTrue(any(l.startswith('Passing basic') for l in lines))

    def test_schema_comparison_classifies_every_kind_of_change(self):
        from fp_ingest import history
        old = make_csv('rushing_bell_cow', season=2025, games=17)
        new = make_csv('rushing_bell_cow', season=2026, games=4, add_columns=['FPTS.NEW'], drop_columns={'Rushing.TM ATT'},
                       mutate=lambda body, keys: [row.__setitem__(keys.index('Rushing.ATT'), 'n/a') for row in body]).replace(b'Routes Run', b'Routes Run (new rule)')
        result = history.compare_exports(old, new)
        self.assertEqual((result['FPTS.NEW']['class'], result['FPTS.NEW']['side']), ('SEASON_LIMITED', 'newer_only'))
        self.assertEqual((result['Rushing.TM ATT']['class'], result['Rushing.TM ATT']['side']), ('SEASON_LIMITED', 'older_only'))
        self.assertEqual(result['Rushing.ATT']['class'], 'SCHEMA_CHANGED')
        self.assertIn('type', result['Rushing.ATT']['why'])
        self.assertEqual(result['Snaps.Snaps']['class'], 'CONSISTENT') if 'Snaps.Snaps' in result else None
        unchanged = history.compare_exports(old, old)
        self.assertEqual({v['class'] for v in unchanged.values()}, {'CONSISTENT'})

    def test_scale_changes_are_surfaced_for_review(self):
        from fp_ingest import history
        old = make_csv('rushing_bell_cow', season=2025, games=17, mutate=lambda body, keys: [row.__setitem__(keys.index('Snaps.Snap %'), '80') for row in body])
        new = make_csv('rushing_bell_cow', season=2026, games=4, mutate=lambda body, keys: [row.__setitem__(keys.index('Snaps.Snap %'), '0.8') for row in body])
        self.assertEqual(history.compare_exports(old, new)['Snaps.Snap %']['class'], 'UNIT_CHANGED')


class MultiSeasonAuditTests(unittest.TestCase):
    """Cross-season artifacts: compatibility matrix, data quality, readiness. Built from synthetic multi-season archives."""

    def archive(self, seasons=(2021, 2022, 2023, 2024, 2025), tables=('rushing_bell_cow',), live=True, **kw):
        workspace = Workspace(self)
        for season in seasons:
            for table in tables:
                workspace.put(f'{table}_{season}.csv', make_csv(table, season=season, games=17, **kw))
        if live:
            for table in tables:
                workspace.put(f'{table}_now.csv', make_csv(table, season=2026, games=4))
        workspace.run()
        return workspace

    def test_consistent_history_gives_a_long_run_and_ready_label(self):
        from fp_ingest import history
        workspace = self.archive(tables=('receiving_routes_run',))
        manifest = workspace.manifest()
        compat = history.multi_season(workspace.dir, REGISTRY, manifest)['tables']['receiving_routes_run']
        self.assertEqual((compat['first_season'], compat['last_season']), (2021, 2026))
        self.assertEqual(compat['table_consistent_run'], [2021, 2026])
        self.assertEqual(compat['column_counts'].get('CONSISTENT'), len(REGISTRY['tables']['receiving_routes_run']['columns']))
        matrix = history.availability(REGISTRY, manifest, {}, downloaded=[2021, 2022, 2023, 2024, 2025, 2026])
        ready = history.readiness(REGISTRY, matrix, history.multi_season(workspace.dir, REGISTRY, manifest))
        self.assertEqual(ready['families']['routes / route participation']['label'], 'READY_FOR_MULTI_SEASON_RESEARCH')
        self.assertEqual(ready['families']['OL / DL']['label'], 'NO_DATA')

    def test_a_schema_change_breaks_the_run_and_blocks_the_ready_label(self):
        from fp_ingest import history
        workspace = Workspace(self)
        for season in (2021, 2022, 2023, 2024):
            workspace.put(f'r{season}.csv', make_csv('rushing_bell_cow', season=season, games=17))
        workspace.put('r2025.csv', make_csv('rushing_bell_cow', season=2025, games=17,
                                            mutate=lambda body, keys: [row.__setitem__(keys.index('Snaps.Snap %'), 'n/a') for row in body]))
        workspace.run()
        manifest = workspace.manifest()
        # the retyped 2025 file is quarantined, so the matrix must say so instead of calling it unavailable
        matrix = history.availability(REGISTRY, manifest, {}, downloaded=[2021, 2022, 2023, 2024, 2025])['tables']['rushing_bell_cow']
        self.assertEqual(matrix['2025']['status'], 'SCHEMA_UNSUPPORTED')
        self.assertEqual(matrix['2024']['status'], 'AVAILABLE')

    def test_unit_and_definition_changes_are_named_and_end_the_consistent_run(self):
        from fp_ingest import history
        workspace = Workspace(self)
        workspace.put('a2022.csv', make_csv('rushing_bell_cow', season=2022, games=17, mutate=lambda body, keys: [row.__setitem__(keys.index('Snaps.Snap %'), '80') for row in body]))
        workspace.put('a2023.csv', make_csv('rushing_bell_cow', season=2023, games=17, mutate=lambda body, keys: [row.__setitem__(keys.index('Snaps.Snap %'), '80') for row in body]))
        workspace.put('a2024.csv', make_csv('rushing_bell_cow', season=2024, games=17, mutate=lambda body, keys: [row.__setitem__(keys.index('Snaps.Snap %'), '0.8') for row in body]))
        workspace.run()
        compat = history.multi_season(workspace.dir, REGISTRY, workspace.manifest())['tables']['rushing_bell_cow']
        self.assertEqual(compat['columns']['Snaps.Snap %']['class'], 'UNIT_CHANGED')
        self.assertEqual(compat['columns']['Snaps.Snap %']['consistent_run'], [2022, 2023])
        self.assertEqual(compat['table_consistent_run'], [2022, 2023])

    def test_a_missing_season_does_not_bridge_a_consistent_run(self):
        from fp_ingest import history
        workspace = self.archive(seasons=(2021, 2022, 2024, 2025), live=False)
        compat = history.multi_season(workspace.dir, REGISTRY, workspace.manifest())['tables']['rushing_bell_cow']
        self.assertEqual(compat['seasons'], [2021, 2022, 2024, 2025])
        self.assertIn(compat['table_consistent_run'], ([2021, 2022], [2024, 2025]))

    def test_quality_report_flags_partial_siblings_and_scores_identity_per_season(self):
        from fp_ingest import history
        workspace = Workspace(self)
        workspace.put('adv.csv', make_csv('receiving_routes_run', season=2024, games=17))
        workspace.put('sep.csv', make_csv('receiving_separation_by_alignment', season=2024, games=17, teams=TEAMS[:28]))
        workspace.run()
        report = history.quality(workspace.dir, REGISTRY, workspace.manifest())
        season = report['seasons']['2024']
        self.assertEqual(season['match_rate'], 100.0)
        sibling = next(item for item in report['sibling_populations'] if item['group'] == 'routes_and_separation')
        self.assertGreater(sibling['in_some_only'], 0)

    def test_quality_report_counts_impossible_percentages_and_split_players(self):
        from fp_ingest import history
        def corrupt(body, keys):
            body[0][keys.index('Snaps.Snap %')] = '140'
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow', season=2024, games=17, mutate=corrupt))
        workspace.run()
        report = history.quality(workspace.dir, REGISTRY, workspace.manifest())
        self.assertEqual(report['tables']['rushing_bell_cow']['2024']['impossible_values'], 1)

    def test_historical_full_seasons_are_never_inputs_to_their_own_season_across_all_years(self):
        workspace = self.archive(tables=('receiving_routes_run', 'rushing_bell_cow'))
        manifest = workspace.manifest()
        for table in ('receiving_routes_run', 'rushing_bell_cow'):
            for season in (2021, 2022, 2023, 2024, 2025):
                for week in range(1, 19):
                    self.assertIsNone(pit(manifest, season, table, season, week), f'{table} {season} week {week}')
                self.assertIsNotNone(pit(manifest, season, table, season + 1, 1), 'next season may use it')
                self.assertIsNone(pit(manifest, season, table, season - 1, 18), 'an earlier season may never use it')
            self.assertEqual(pit(manifest, 2026, table, 2026, 5)['through_games'], 4)
            self.assertIsNone(pit(manifest, 2026, table, 2026, 4), 'game 4 data is not known before week 4 is played')


class QaMultiSeasonRegressionTests(unittest.TestCase):
    """Defects found by the independent QA of the 2021-2026 foundation; each failed before its fix."""

    def seasons(self, workspace, years, table='receiving_man_vs_zone', **kw):
        for year in years:
            workspace.put(f'{table}_{year}.csv', make_csv(table, season=year, games=17, **kw(year) if callable(kw.get('mutate_for')) else {}))

    def test_count_columns_that_collapse_between_seasons_are_flagged(self):
        from fp_ingest import history
        old = make_csv('receiving_man_vs_zone', season=2021, games=17, mutate=lambda body, keys: [row.__setitem__(keys.index('Man.RTE'), '3') for row in body])
        new = make_csv('receiving_man_vs_zone', season=2022, games=17)
        result = history.compare_exports(old, new)
        self.assertEqual(result['Man.RTE']['class'], 'UNIT_CHANGED')
        self.assertIn('per game', result['Man.RTE']['why'])
        self.assertEqual(result['Zone.RTE']['class'], 'CONSISTENT')

    def test_counts_are_compared_per_game_so_a_short_season_is_not_a_unit_change(self):
        from fp_ingest import history
        result = history.compare_exports(make_csv('receiving_man_vs_zone', season=2025, games=17), make_csv('receiving_man_vs_zone', season=2026, games=4))
        self.assertEqual({v['class'] for v in result.values()}, {'CONSISTENT'})

    def test_a_changed_vendor_definition_is_reported(self):
        from fp_ingest import history
        old = make_csv('rushing_bell_cow', season=2023, games=17)
        new = make_csv('rushing_bell_cow', season=2024, games=17).replace(b'Routes Run', b'Routes Run (redefined)')
        result = history.compare_exports(old, new)
        self.assertEqual(result['Receiving.RTE']['class'], 'DEFINITION_CHANGED')

    def test_a_gap_year_never_bridges_a_column_run(self):
        from fp_ingest import history
        workspace = Workspace(self)
        for year in (2021, 2022, 2024, 2025):
            workspace.put(f'r{year}.csv', make_csv('rushing_bell_cow', season=year, games=17,
                                                   mutate=(lambda body, keys: [row.__setitem__(keys.index('Snaps.Snap %'), '90') for row in body]) if year == 2025 else None))
        workspace.run()
        compat = history.multi_season(workspace.dir, REGISTRY, workspace.manifest())['tables']['rushing_bell_cow']
        column = compat['columns']['Snaps.Snap %']
        self.assertIn(column['consistent_run'], ([2021, 2022], [2024, 2024]))
        self.assertNotEqual(column['consistent_run'], [2021, 2024])

    def readiness_inputs(self, table_info, seasons, statuses=None):
        cells = {str(y): {'status': (statuses or {}).get(y, 'AVAILABLE')} for y in seasons}
        return {'tables': {'rushing_advanced': cells}}, {'tables': {'rushing_advanced': table_info}}

    def info(self, seasons, changed=None, consistent=40):
        return {'seasons': seasons, 'first_season': seasons[0], 'last_season': seasons[-1], 'consistent_columns': consistent, 'columns': changed or {},
                'table_consistent_run': [seasons[0], seasons[-1]]}

    def label(self, matrix, compat, family='advanced rushing'):
        from fp_ingest import history
        return history.readiness(REGISTRY, matrix, compat)['families'][family]['label']

    def test_the_live_season_never_counts_as_a_completed_season(self):
        matrix, compat = self.readiness_inputs(self.info([2023, 2024, 2025, 2026]), [2023, 2024, 2025, 2026])
        self.assertEqual(self.label(matrix, compat), 'LIMITED_HISTORY')
        matrix, compat = self.readiness_inputs(self.info([2022, 2023, 2024, 2025, 2026]), [2022, 2023, 2024, 2025, 2026])
        self.assertEqual(self.label(matrix, compat), 'READY_FOR_MULTI_SEASON_RESEARCH')

    def test_one_weak_core_table_holds_the_whole_family_back(self):
        from fp_ingest import history
        good = {s: {'status': 'AVAILABLE'} for s in map(str, range(2021, 2027))}
        thin = {'2025': {'status': 'AVAILABLE'}, '2026': {'status': 'AVAILABLE'}}
        matrix = {'tables': {t: good for t in history.FAMILIES['separation']['core']}}
        matrix['tables']['receiving_separation_by_routes'] = thin
        compat = {'tables': {t: self.info(list(range(2021, 2027))) for t in history.FAMILIES['separation']['core']}}
        compat['tables']['receiving_separation_by_routes'] = self.info([2025, 2026])
        ready = history.readiness(REGISTRY, matrix, compat)['families']['separation']
        self.assertEqual(ready['label'], 'LIMITED_HISTORY')
        self.assertEqual(ready['weakest_core_tables'], ['receiving_separation_by_routes'])

    def test_changed_columns_and_partial_seasons_lower_the_label(self):
        changed = {f'Col{i}': {'class': 'UNIT_CHANGED', 'consistent_run': [2024, 2026], 'seasons': [2021, 2026], 'notes': []} for i in range(30)}
        matrix, compat = self.readiness_inputs(self.info([2021, 2022, 2023, 2024, 2025, 2026], changed=changed, consistent=5), range(2021, 2027))
        self.assertEqual(self.label(matrix, compat), 'NEEDS_SCHEMA_REVIEW')
        matrix, compat = self.readiness_inputs(self.info([2021, 2022, 2023, 2024, 2025]), range(2021, 2026), statuses={2023: 'PARTIAL'})
        self.assertEqual(self.label(matrix, compat), 'LIMITED_HISTORY')
        matrix, compat = self.readiness_inputs(self.info([2026]), [2026])
        self.assertEqual(self.label(matrix, compat), '2026_PROSPECTIVE_ONLY')

    def test_descriptive_only_tables_are_labelled_so(self):
        from fp_ingest import history
        cells = {str(y): {'status': 'AVAILABLE'} for y in range(2021, 2026)}
        matrix = {'tables': {'offense_snaps': {}, 'rushing_basic': cells, 'receiving_basic': cells}}
        compat = {'tables': {'rushing_basic': self.info(list(range(2021, 2026))), 'receiving_basic': self.info(list(range(2021, 2026)))}}
        family = history.readiness(REGISTRY, matrix, compat)['families']['red zone / goal line']
        self.assertEqual(family['tables']['rushing_basic']['label'], 'DESCRIPTIVE_ONLY_FOR_NOW')
        self.assertEqual(family['label'], 'NO_DATA', 'the core table (offense snaps) has no data at all')

    def test_operator_override_cannot_claim_fewer_games_than_the_file_shows(self):
        workspace = Workspace(self)
        workspace.put('nine.csv', make_csv('rushing_bell_cow', games=9))
        report = workspace.run(through_override=3, max_possible_games=12)
        self.assertEqual(report['results'][0]['reason']['code'], 'override_invalid')
        self.assertEqual(list((workspace.dir / 'normalized').rglob('*.json')), [])

    def test_a_finished_season_beats_an_earlier_in_season_capture_of_the_same_season(self):
        workspace = Workspace(self)
        workspace.put('live.csv', make_csv('rushing_bell_cow', season=2026, games=4))
        workspace.put('full.csv', make_csv('rushing_bell_cow', season=2026, games=17))
        workspace.run(now=datetime.datetime(2027, 2, 1, tzinfo=datetime.timezone.utc), max_possible_games=None, current_season=2027)
        entries = workspace.manifest().entries(2026, 'rushing_bell_cow')
        self.assertEqual(sorted((e['scope'], e['through_games']) for e in entries), [('full_season', 17)])
        manifest = workspace.manifest()
        live = dict(entries[0], scope='season_to_date', through_games=4, sha256='x' * 64, first_imported_at='2026-10-01T00:00:00Z', superseded_by=None, status='imported')
        manifest.files['x' * 64] = live
        self.assertEqual(store.current_entry(manifest, 2026, 'rushing_bell_cow')['scope'], 'full_season')

    def test_team_level_tables_get_the_same_seventeen_game_check(self):
        workspace = Workspace(self)
        workspace.put('t.csv', make_csv('coverage_matrix', season=2025, games=17, mutate=lambda body, keys: body[0].__setitem__(keys.index('Team Details.G'), '18')))
        report = workspace.run()
        self.assertTrue(any('suspicious' in w for w in report['results'][0]['warnings']))

    def test_archived_entries_missing_from_the_inbox_are_rederived_and_keep_their_capture_time(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow', season=2025, games=17))
        set_mtime(workspace.inbox / 'a.csv', NOW - datetime.timedelta(days=2))
        workspace.run()
        manifest = workspace.manifest()
        entry = next(iter(manifest.files.values()))
        captured = entry['captured_at']
        entry['importer_version'] = 1
        entry.pop('season_scope', None)
        manifest.save()
        (workspace.inbox / 'a.csv').unlink()  # the file left the Inbox; only the archive remains
        report = workspace.run(now=NOW + datetime.timedelta(days=5))
        self.assertEqual(report['outcomes'], {'repaired': 1})
        refreshed = next(iter(workspace.manifest().files.values()))
        self.assertEqual((refreshed['importer_version'], refreshed['season_scope'], refreshed['captured_at']), (pl.IMPORTER_VERSION, 'regular_season', captured))
        self.assertEqual(refreshed['first_imported_at'], entry['first_imported_at'])

    def test_rederiving_does_not_move_capture_time_when_the_inbox_file_is_touched(self):
        workspace = Workspace(self)
        workspace.put('a.csv', make_csv('rushing_bell_cow'))
        set_mtime(workspace.inbox / 'a.csv', NOW - datetime.timedelta(days=2))
        workspace.run()
        manifest = workspace.manifest()
        entry = next(iter(manifest.files.values()))
        captured = entry['captured_at']
        entry['importer_version'] = 1
        manifest.save()
        set_mtime(workspace.inbox / 'a.csv', NOW + datetime.timedelta(days=9))
        workspace.run(now=NOW + datetime.timedelta(days=10))
        self.assertEqual(next(iter(workspace.manifest().files.values()))['captured_at'], captured)


class ProtectionRemovalTests(unittest.TestCase):
    """Each protection is switched off in turn; the scenario that guards it must then fail (the tests are not vacuous)."""

    def assert_guarded(self, scenario, patcher):
        scenario()  # passes with the protection in place
        with patcher:
            with self.assertRaises(AssertionError):
                scenario()

    def test_schema_block_is_load_bearing(self):
        self.assert_guarded(lambda: self._run('test_missing_column_quarantines_and_keeps_previous_valid_snapshot', SchemaTests),
                            patch.object(regmod, 'blocking', lambda drift: False))

    def _run(self, name, cls):
        case = cls(name)
        result = unittest.TestResult()
        case.run(result)
        if result.failures or result.errors:
            raise AssertionError((result.failures or result.errors)[0][1])

    def test_duplicate_short_circuit_is_load_bearing(self):
        original = pl.Importer.import_file

        def no_dedupe(self, name, data, mtime=None):
            self.manifest.files.pop(sha256(data), None)
            return original(self, name, data, mtime)
        self.assert_guarded(lambda: self._run('test_duplicate_import_is_idempotent_and_inbox_is_untouched', ImportTests),
                            patch.object(pl.Importer, 'import_file', no_dedupe))

    def test_ragged_row_rejection_is_load_bearing(self):
        import fp_ingest.parse as parse_module
        source = parse_module.parse_export

        def padded(data):  # what a parser without the row-length check would do: accept short rows
            try:
                return source(data)
            except ParseError as error:
                if error.code != 'ragged_row':
                    raise
                lines = data.decode('utf-8-sig').splitlines()
                width = len(next(csv.reader([lines[1]])))
                fixed = []
                for line in lines:
                    cells = next(csv.reader([line])) if line else []
                    fixed.append(','.join(cells + [''] * (width - len(cells))) if 2 < len(cells) < width else line)
                return source('\n'.join(fixed).encode('utf-8'))
        self.assert_guarded(lambda: self._run('test_truncated_download_is_rejected', ImportTests), patch.object(pl, 'parse_export', padded))

    def test_ambiguity_check_is_load_bearing(self):
        original = idmod.RosterIndex.resolve

        def first_wins(self, name, team, position):
            result = original(self, name, team, position)
            if result['status'] == 'ambiguous':
                result = {**result, 'status': 'matched', 'player_id': result['candidates'][0]}
            return result
        self.assert_guarded(lambda: self._run('test_ambiguous_players_are_reported_not_guessed', IdentityTests),
                            patch.object(idmod.RosterIndex, 'resolve', first_wins))

    def test_retrospective_guard_is_load_bearing(self):
        def leaky(manifest, season, table_id, for_season, for_week, known_by=None):
            for entry in manifest.entries(season, table_id):
                return entry
            return None
        self.assert_guarded(lambda: self._run('test_retrospective_same_season_export_is_never_usable_inside_that_season', LeakageTests),
                            patch.object(store, 'point_in_time', leaky))

    def test_future_season_guard_is_load_bearing(self):
        original = pl.decide_scope

        def permissive(info, current_season, max_possible_games, override=None, in_season=True, declare=None):
            return original(info, 9999, None, override, in_season, declare)
        self.assert_guarded(lambda: self._run('test_future_games_and_future_season_are_rejected', ImportTests),
                            patch.object(pl, 'decide_scope', permissive))

    def test_manifest_last_ordering_is_load_bearing(self):
        real_import = pl.Importer.import_file

        def save_each(self, name, data, mtime=None):  # saving the manifest per file would survive a crash half-way through the run
            result = real_import(self, name, data, mtime)
            self.manifest.save()
            return result
        self.assert_guarded(lambda: self._run('test_interrupted_import_resumes_cleanly', ImportTests),
                            patch.object(pl.Importer, 'import_file', save_each))


    def test_capture_time_ordering_is_load_bearing(self):
        real = pl.Importer.import_file
        self.assert_guarded(lambda: self._run('test_an_older_download_arriving_later_does_not_replace_a_newer_one', QaRegressionTests),
                            patch.object(pl.Importer, 'import_file', lambda self, name, data, mtime=None: real(self, name, data, None)))

    def test_repair_keeps_revision_chain_is_load_bearing(self):
        real = pl.Importer.import_file

        def forget(self, name, data, mtime=None):
            entry = self.manifest.files.get(sha256(data))
            if entry and not (self.root / entry['normalized_path']).exists():
                self.manifest.files.pop(sha256(data))  # as if the previous entry were not consulted
                mtime = '9999-01-01T00:00:00Z'  # and the file looked freshly touched (OneDrive sync, copy)
            return real(self, name, data, mtime)
        self.assert_guarded(lambda: self._run('test_repairing_a_file_does_not_flip_the_revision_chain', QaRegressionTests),
                            patch.object(pl.Importer, 'import_file', forget))

    def test_skill_position_rule_is_load_bearing(self):
        def wildcard(self, pids, group):
            return sorted(pids)
        self.assert_guarded(lambda: self._run('test_non_skill_roster_positions_do_not_match_skill_rows', QaRegressionTests),
                            patch.object(idmod.RosterIndex, '_compatible', wildcard))

    def test_required_cutoff_is_load_bearing(self):
        real = store.point_in_time
        self.assert_guarded(lambda: self._run('test_same_season_lookup_requires_a_cutoff', QaRegressionTests),
                            patch.object(store, 'point_in_time', lambda *a, known_by=None, **k: real(*a, known_by=known_by or FUTURE, **k)))


    def test_declaration_requirement_is_load_bearing(self):
        original = pl._decide_scope

        def infers(info, current_season, max_possible_games, override, in_season, declare):
            return original(info, current_season, max_possible_games, override, in_season, ('cumulative', None))  # guess instead of asking
        self.assert_guarded(lambda: self._run('test_undeclared_partial_past_season_is_held_with_instructions', HistoricalSnapshotTests),
                            patch.object(pl, '_decide_scope', infers))

    def test_content_based_time_for_historical_snapshots_is_load_bearing(self):
        real = store.point_in_time

        def by_download_date(manifest, season, table_id, for_season, for_week, known_by=None):
            class View:
                def entries(self, *a, **k):
                    return [dict(e, scope='season_to_date') if e.get('scope') == 'historical_cumulative' else e for e in manifest.entries(*a, **k)]
            return real(View(), season, table_id, for_season, for_week, known_by)
        self.assert_guarded(lambda: self._run('test_declared_cumulative_exports_are_true_point_in_time_snapshots', HistoricalSnapshotTests),
                            patch.object(store, 'point_in_time', by_download_date))

    def test_single_week_isolation_is_load_bearing(self):
        real = store.point_in_time

        def serves_weeks(manifest, season, table_id, for_season, for_week, known_by=None):
            class View:
                def entries(self, *a, **k):
                    return [dict(e, scope='historical_cumulative', through_games=e['week'], declared_by='operator') if e.get('scope') == 'single_week' else e
                            for e in manifest.entries(*a, **k)]
            return real(View(), season, table_id, for_season, for_week, known_by)
        self.assert_guarded(lambda: self._run('test_declared_single_weeks_are_stored_separately_and_never_served_as_cumulative', HistoricalSnapshotTests),
                            patch.object(store, 'point_in_time', serves_weeks))

    def test_single_week_guard_on_cumulative_declarations_is_load_bearing(self):
        original = pl._decide_scope

        def lenient(info, current_season, max_possible_games, override, in_season, declare):
            patched = dict(info, games_max=max(2, info.get('games_max') or 0))  # pretend the file was not a one-game file
            return original(patched, current_season, max_possible_games, override, in_season, declare)
        self.assert_guarded(lambda: self._run('test_one_game_cumulative_declaration_is_refused_as_a_single_week', HistoricalSnapshotTests),
                            patch.object(pl, '_decide_scope', lenient))

    def test_file_selection_for_declarations_is_load_bearing(self):
        real = pl.Importer._run

        def everything(self, inbox):
            self.only = []
            return real(self, inbox)
        self.assert_guarded(lambda: self._run('test_a_declaration_must_name_its_files_and_only_touches_them', HistoricalSnapshotTests),
                            patch.object(pl.Importer, '_run', everything))

    def test_multi_team_support_is_load_bearing(self):
        def single_only(value):
            return [idmod.canonical_team(value)]
        self.assert_guarded(lambda: self._run('test_traded_players_with_several_teams_are_matched_not_rejected', FullSeasonHistoryTests),
                            patch.object(idmod, 'canonical_teams', single_only))

    def test_duplicate_row_guard_is_load_bearing(self):
        real = pl._inspect

        def blind(name, data, registry, mtime):
            info, ctx = real(name, data, registry, mtime)
            info['duplicate_entities'] = []
            return info, ctx
        self.assert_guarded(lambda: self._run('test_repeated_players_in_one_export_are_rejected', FullSeasonHistoryTests),
                            patch.object(pl, '_inspect', blind))

    def test_research_boundary_flag_is_load_bearing(self):
        self.assert_guarded(lambda: self._run('test_full_season_is_flagged_as_retrospective_in_metadata', FullSeasonHistoryTests),
                            patch.dict(pl.RESEARCH_BOUNDARY, {'full_season': {'same_season_point_in_time': True, 'season_scope': 'regular_season'}}))

    def test_unconfirmed_availability_label_is_load_bearing(self):
        from fp_ingest import history
        real = history.availability

        def overclaim(registry, manifest, declarations=None, seasons=history.SEASONS):
            declarations = {season: {t: dict(item, status='provider_unavailable') for t, item in tables.items()} for season, tables in (declarations or {}).items()}
            return real(registry, manifest, declarations, seasons)
        self.assert_guarded(lambda: self._run('test_availability_never_calls_a_gap_confirmed_unless_confirmed', FullSeasonHistoryTests),
                            patch.object(history, 'availability', overclaim))

    def test_multi_season_leakage_guard_is_load_bearing(self):
        def leaky(manifest, season, table_id, for_season, for_week, known_by=None):
            return next(iter(manifest.entries(season, table_id)), None)
        self.assert_guarded(lambda: self._run('test_historical_full_seasons_are_never_inputs_to_their_own_season_across_all_years', MultiSeasonAuditTests),
                            patch.object(store, 'point_in_time', leaky))

    def test_unit_change_detection_is_load_bearing(self):
        from fp_ingest import history
        real = history._scale
        self.assert_guarded(lambda: self._run('test_unit_and_definition_changes_are_named_and_end_the_consistent_run', MultiSeasonAuditTests),
                            patch.object(history, '_scale', lambda values: 1.0))

    def test_per_game_count_scaling_is_load_bearing(self):
        from fp_ingest import history
        self.assert_guarded(lambda: self._run('test_counts_are_compared_per_game_so_a_short_season_is_not_a_unit_change', QaMultiSeasonRegressionTests),
                            patch.object(history, 'COUNT_BASES', set()))

    def test_completed_seasons_only_rule_is_load_bearing(self):
        from fp_ingest import history
        self.assert_guarded(lambda: self._run('test_the_live_season_never_counts_as_a_completed_season', QaMultiSeasonRegressionTests),
                            patch.object(history, 'CURRENT_SEASON', 2099))

    def test_archive_rederivation_is_load_bearing(self):
        real = pl.Importer._run

        def inbox_only(self, inbox):
            self.manifest_orig = self.manifest
            for entry in self.manifest.files.values():
                if entry.get('importer_version') != pl.IMPORTER_VERSION:
                    entry['importer_version'] = pl.IMPORTER_VERSION  # pretend nothing is stale: the archive-only pass finds nothing
            return real(self, inbox)
        self.assert_guarded(lambda: self._run('test_archived_entries_missing_from_the_inbox_are_rederived_and_keep_their_capture_time', QaMultiSeasonRegressionTests),
                            patch.object(pl.Importer, '_run', inbox_only))

@unittest.skipUnless(os.environ.get('GOING_FP_ROOT'), 'set GOING_FP_ROOT to run against the real Inbox')
class RealInboxTests(unittest.TestCase):
    def test_every_real_export_is_recognised_with_current_schema(self):
        inbox = store.find_inbox(Path(os.environ['GOING_FP_ROOT']))
        files = sorted(inbox.glob('*.csv'))
        self.assertTrue(files)
        for path in files:
            info, _ = pl.inspect_bytes(path.name, path.read_bytes(), REGISTRY)
            self.assertNotIn('error', info, path.name)
            self.assertEqual(info['schema_status'], 'known', path.name)
            self.assertEqual(len(info['seasons']), 1, path.name)
            self.assertIn(info['seasons'][0], ('2025', '2026'), path.name)


if __name__ == '__main__':
    unittest.main()
