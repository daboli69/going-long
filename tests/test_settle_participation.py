import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from settle_markets import no_participation


class ParticipationTests(unittest.TestCase):
    def test_all_zero_rows_are_not_graded(self):
        self.assertTrue(no_participation({'pass_yds': 0, 'rush_yds': 0, 'rec_yds': 0, 'receptions': 0, 'atd': 0, 'attempts': 0, 'carries': 0, 'targets': 0}))
        self.assertTrue(no_participation({'rec_yds': 0, 'receptions': 0, 'rush_yds': 0}))

    def test_any_touch_counts_as_participation(self):
        self.assertFalse(no_participation({'rec_yds': 0, 'receptions': 0, 'targets': 1, 'carries': 0}))
        self.assertFalse(no_participation({'rec_yds': 12, 'receptions': 2}))

    def test_missing_stat_row_is_not_participation_evidence(self):
        self.assertFalse(no_participation({}))


if __name__ == '__main__':
    unittest.main()
