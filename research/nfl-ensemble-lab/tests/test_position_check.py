import json, tempfile, unittest
from pathlib import Path
import pandas as pd
from lab.fpds_research import position_check as P


def frame(spec, table='receiving_basic'):
    # spec: {position: {week: rows}} for season 2026
    rows = [(table, 2026, w, p, n) for p, weeks in spec.items() for w, n in weeks.items()]
    return pd.DataFrame(rows, columns=['table', 'season', 'week', 'position', 'rows'])


STEADY = {'WR': {w: 120 for w in range(1, 10)}, 'TE': {w: 80 for w in range(1, 10)}}


class PositionCheck(unittest.TestCase):
    def test_steady_table_is_clean(self):
        self.assertEqual(P.shifts(frame(STEADY)), [])

    def test_late_position_is_flagged(self):
        found = P.shifts(frame({**STEADY, 'RB': {9: 60}}))
        self.assertEqual([(f['position'], f['kind'], f['week'], f['weeks_without'], f['rows']) for f in found],
                         [('RB', 'appeared', 9, 8, 60)])

    def test_season_boundary_orders_weeks(self):
        d = pd.concat([frame(STEADY).assign(season=2025), frame({**STEADY, 'RB': {1: 60}})])
        found = [f for f in P.shifts(d) if f['kind'] == 'appeared']
        self.assertEqual((found[0]['season'], found[0]['week'], found[0]['weeks_without']), (2026, 1, 9))

    def test_old_season_shift_is_not_reported(self):
        d = pd.concat([frame({**STEADY, 'RB': {w: 60 for w in range(8, 10)}}).assign(season=2025),
                       frame({**STEADY, 'RB': {w: 60 for w in range(1, 10)}})])
        self.assertEqual(P.shifts(d), [])

    def test_early_weeks_and_stray_rows_are_ignored(self):
        self.assertEqual(P.shifts(frame({**STEADY, 'RB': {w: 60 for w in range(3, 10)}})), [])
        self.assertEqual(P.shifts(frame({**STEADY, 'FB': {9: 3}})), [])
        self.assertEqual(P.shifts(frame({'WR': {1: 100, 2: 100}, 'RB': {2: 50}})), [])

    def test_vanished_position_is_flagged(self):
        found = P.shifts(frame({**STEADY, 'RB': {w: 60 for w in range(1, 9)}}))
        self.assertEqual([(f['position'], f['kind'], f['week']) for f in found], [('RB', 'vanished', 9)])

    def test_check_raises_until_acknowledged(self):
        d = frame({**STEADY, 'RB': {9: 60}})
        original = P.counts
        P.counts = lambda manifest: d
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ack = Path(tmp) / 'ack.json'
                with self.assertRaises(P.PositionShift) as raised:
                    P.check({}, ack)
                self.assertIn('receiving_basic: RB appeared in 2026 Week 9', str(raised.exception))
                ack.write_text(json.dumps({'acknowledged': [
                    {'table': 'receiving_basic', 'position': 'RB', 'kind': 'appeared', 'season': 2026, 'week': 9}]}))
                self.assertEqual(len(P.check({}, ack)), 1)
                # a later, different shift is not covered by the old acknowledgement
                P.counts = lambda manifest: frame({**STEADY, 'RB': {9: 60}, 'QB': {9: 40}})
                with self.assertRaises(P.PositionShift):
                    P.check({}, ack)
        finally:
            P.counts = original


if __name__ == '__main__':
    unittest.main()
