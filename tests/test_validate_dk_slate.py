"""Synthetic official-shaped inputs; no real salaries, private files or network."""
import csv
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_dk_slate as V

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
FRESH = '2026-10-11T10:00:00Z'


def row(i, pos, club='BUF', away='BUF', home='MIA', role=None, salary=5000):
    name = 'Synthetic ' + str(i)
    return {'Position': pos, 'Name + ID': f'{name} ({i})', 'Name': name, 'ID': str(i),
            'Roster Position': role or (pos if pos in ('QB', 'DST') else pos + '/FLEX'),
            'Salary': str(salary), 'Game Info': f'{away}@{home} 10/11/2026 01:00PM ET',
            'TeamAbbrev': club, 'AvgPointsPerGame': '10'}


def text(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=V.HEADERS + ['Status'])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def fixture(showdown=False):
    positions = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'RB', 'DST']
    rows = [row(i + 1, pos) for i, pos in enumerate(positions)]
    rows[-1].update(**row(9, 'DST', 'NYJ', 'NYJ', 'NE'))
    if showdown:
        rows = []
        for i, pos in enumerate(['QB', 'RB', 'WR', 'TE', 'K', 'DST'], 1):
            flex = row(i, pos, 'BUF' if i < 4 else 'MIA', role='FLEX', salary=4000)
            captain = {**flex, 'ID': str(i + 100), 'Name + ID': f"{flex['Name']} ({i + 100})", 'Roster Position': 'CPT', 'Salary': '6000'}
            rows.extend([flex, captain])
    roster = {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH, 'week': 5, 'players': [], 'bye_carry_forward_teams': []}
    for r in rows:
        if r['Position'] == 'DST' or r['Roster Position'] == 'CPT':
            continue
        roster['players'].append({'id': 'gsis-' + r['ID'], 'name': r['Name'], 'team': r['TeamAbbrev'],
                                  'position': r['Position'], 'roster_status': 'ACT'})
    injury = {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH, 'current_players': {}, 'current_reports': {}}
    schedule = {'games': [{'away': 'BUF', 'home': 'MIA', 'kickoff': '2026-10-11T17:00:00Z'},
                          {'away': 'NYJ', 'home': 'NE', 'kickoff': '2026-10-11T17:00:00Z'}]}
    return rows, dict(contest_format='showdown' if showdown else 'classic', slate_date='2026-10-11',
                      roster=roster, injury=injury, schedule=schedule, now=NOW)


class ValidateDraftKingsSlateTests(unittest.TestCase):
    def test_classic_exact_schedule_identity_slots_and_cap(self):
        rows, kwargs = fixture()
        out = V.validate(text(rows), lineup=[str(i) for i in range(1, 10)], **kwargs)
        self.assertTrue(out['ok'])
        self.assertEqual(out['lineup']['salary'], 45000)
        self.assertTrue(out['lineup']['legal'])
        self.assertEqual(out['counts']['eligible_rows'], 9)
        self.assertIn('unverified', out['contest_association'])

    def test_showdown_distinct_ids_captain_salary_not_multiplied_twice(self):
        rows, kwargs = fixture(True)
        out = V.validate(text(rows), lineup=['101', '2', '3', '4', '5', '6'], **kwargs)
        self.assertTrue(out['ok'])
        self.assertEqual(out['lineup']['salary'], 26000)
        self.assertEqual(out['lineup']['scoring_multipliers'], [1.5, 1, 1, 1, 1, 1])

    def test_salary_pair_mismatch_and_same_athlete_twice_reject(self):
        rows, kwargs = fixture(True)
        out = V.validate(text(rows), lineup=['101', '1', '2', '3', '4', '5'], **kwargs)
        self.assertFalse(out['ok'])
        self.assertIn('Same athlete selected more than once', out['lineup']['errors'])
        rows[1]['Salary'] = '8000'
        self.assertFalse(V.validate(text(rows), **kwargs)['ok'])

    def test_stale_missing_or_malformed_availability_excludes_every_row(self):
        for source in (None, [], {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH}, {'generated_at': '2026-10-08T10:00:00Z', 'current_players': {}, 'current_reports': {}}):
            rows, kwargs = fixture()
            kwargs['injury'] = source
            out = V.validate(text(rows), **kwargs)
            self.assertFalse(out['ok'])
            self.assertEqual(out['counts']['eligible_rows'], 0)

    def test_unknown_ambiguous_and_contradictory_player_exclusions(self):
        rows, kwargs = fixture()
        kwargs['roster']['players'][0]['name'] = 'Unknown Name'
        out = V.validate(text(rows), **kwargs)
        self.assertFalse(out['players'][0]['eligible'])
        rows, kwargs = fixture()
        kwargs['roster']['players'].append({**kwargs['roster']['players'][0], 'id': 'duplicate-name'})
        self.assertFalse(V.validate(text(rows), **kwargs)['players'][0]['eligible'])
        rows, kwargs = fixture()
        kwargs['injury']['current_players']['a'] = {'gsis_id': 'gsis-1', 'team': 'NE', 'roster_status': 'ACT'}
        self.assertFalse(V.validate(text(rows), **kwargs)['players'][0]['eligible'])

    def test_out_doubtful_bye_and_csv_out_excluded_without_rejecting_legitimate_pool(self):
        rows, kwargs = fixture()
        kwargs['injury']['current_reports']['a'] = {'gsis_id': 'gsis-1', 'report_status': 'Out', 'week': 5}
        kwargs['injury']['current_reports']['b'] = {'gsis_id': 'gsis-2', 'report_status': 'Doubtful', 'week': 5}
        kwargs['roster']['bye_carry_forward_teams'] = ['NYJ']
        rows[2]['Status'] = 'OUT'
        out = V.validate(text(rows), **kwargs)
        self.assertTrue(out['ok'])
        self.assertTrue(all(not out['players'][i]['eligible'] for i in (0, 1, 2, 8)))
        self.assertFalse(V.validate(text(rows), lineup=[str(i) for i in range(1, 10)], **kwargs)['ok'])

    def test_wrong_date_team_game_kickoff_and_started_rows_fail(self):
        for change in ({'Game Info': 'BUF@MIA 10/12/2026 01:00PM ET'},
                       {'TeamAbbrev': 'NE'}, {'Game Info': 'BUF@MIA 10/11/2026 02:00PM ET'}):
            rows, kwargs = fixture()
            rows[0].update(change)
            self.assertFalse(V.validate(text(rows), **kwargs)['ok'])
        rows, kwargs = fixture()
        kwargs['now'] = datetime(2026, 10, 11, 17, tzinfo=timezone.utc)
        self.assertEqual(V.validate(text(rows), **kwargs)['counts']['eligible_rows'], 0)

    def test_cap_wrong_slots_and_two_game_requirement(self):
        rows, kwargs = fixture()
        rows[0]['Salary'] = '10000'
        rows[1]['Salary'] = '10000'
        self.assertFalse(V.validate(text(rows), lineup=[str(i) for i in range(1, 10)], **kwargs)['ok'])
        rows, kwargs = fixture()
        ids = [str(i) for i in range(1, 10)]
        ids[0], ids[1] = ids[1], ids[0]
        self.assertFalse(V.validate(text(rows), lineup=ids, **kwargs)['ok'])
        rows[-1] = row(9, 'DST')
        self.assertFalse(V.validate(text(rows), **kwargs)['ok'])

    def test_csv_duplicate_headers_ids_and_malformed_rows_reject(self):
        rows, kwargs = fixture()
        self.assertFalse(V.validate(text(rows + [rows[0]]), **kwargs)['ok'])
        self.assertFalse(V.validate(text(rows).replace('Position,', 'ID,', 1), **kwargs)['ok'])
        self.assertFalse(V.validate(text(rows) + 'bad,row\n', **kwargs)['ok'])
        rows[0]['Salary'] = '5000.5'
        self.assertFalse(V.validate(text(rows), **kwargs)['ok'])

    def test_sunday_night_uses_eastern_date(self):
        rows, kwargs = fixture(True)
        for r in rows:
            r['Game Info'] = 'BUF@MIA 10/11/2026 08:20PM ET'
        kwargs['schedule']['games'][0]['kickoff'] = '2026-10-12T00:20:00Z'
        self.assertTrue(V.validate(text(rows), **kwargs)['ok'])

    def test_authoritative_athlete_id_cannot_be_selected_across_positions(self):
        rows, kwargs = fixture()
        rows[3].update(Name=rows[1]['Name'], **{'Name + ID': rows[1]['Name'] + ' (4)'})
        kwargs['roster']['players'][3].update(id='gsis-2', name=rows[1]['Name'])
        self.assertFalse(V.validate(text(rows), lineup=[str(i) for i in range(1, 10)], **kwargs)['ok'])

    def test_team_defense_identity_cannot_be_duplicated_under_another_name(self):
        rows, kwargs = fixture(True)
        flex = row(7, 'DST', 'MIA', role='FLEX', salary=4000)
        captain = {**flex, 'ID': '107', 'Name + ID': 'Synthetic 7 (107)', 'Roster Position': 'CPT', 'Salary': '6000'}
        rows.extend([flex, captain])
        self.assertFalse(V.validate(text(rows), lineup=['101', '2', '3', '4', '6', '7'], **kwargs)['ok'])

    def test_malformed_offsets_dates_and_naive_times_are_rejected(self):
        for value in ('2026-10-11T18:00:00+00:60', '2026-10-11T17:00:00+24:00',
                      '2026-02-30T17:00:00Z', '2026-10-11T17:00:00'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): V.stamp(value)
        rows, kwargs = fixture(True)
        kwargs['schedule']['games'][0]['kickoff'] = '2026-10-11T18:00:00+00:60'
        self.assertFalse(V.validate(text(rows), **kwargs)['ok'])

    def test_csv_unavailable_and_unknown_statuses_cannot_override_active_roster(self):
        for status in ('PS', 'PRA', 'SUSPENDED', 'RESERVE', 'WAIVED', 'REL', 'D', 'BOGUS'):
            rows, kwargs = fixture()
            rows[1]['Status'] = status
            out = V.validate(text(rows), lineup=[str(i) for i in range(1, 10)], **kwargs)
            self.assertFalse(out['ok'], status)
            self.assertFalse(next(p for p in out['players'] if p['id'] == '2')['eligible'], status)


if __name__ == '__main__':
    unittest.main()
