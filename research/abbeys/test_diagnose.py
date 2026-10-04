import copy
import unittest

from diagnose import read_games, predictions


class ChronologyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games, _, _ = read_games()

    def test_same_week_result_cannot_change_forecast(self):
        original = predictions(self.games, 2024)
        changed = copy.deepcopy(self.games)
        target = next(x for x in changed[2024] if x["week"] == 4)
        target["hs"], target["aws"] = 99, 0
        revised = predictions(changed, 2024)
        for first, second in zip(original, revised):
            if first["week"] == 4:
                self.assertEqual(first.get("B"), second.get("B"))
                self.assertEqual(first.get("C"), second.get("C"))
                self.assertEqual(first.get("R"), second.get("R"))

    def test_other_seasons_cannot_change_2026_forecasts(self):
        original = predictions(self.games, 2026)
        changed = copy.deepcopy(self.games)
        for season in (2024, 2025):
            for game in changed[season]:
                if game["completed"]:
                    game["hs"], game["aws"] = 0, 70
        revised = predictions(changed, 2026)
        self.assertEqual(original, revised)

    def test_current_week_result_cannot_change_2026_forecasts(self):
        original = predictions(self.games, 2026)
        changed = copy.deepcopy(self.games)
        thursday = next(x for x in changed[2026] if x["week"] == 4 and x["completed"])
        thursday["hs"], thursday["aws"] = 100, 0
        revised = predictions(changed, 2026)
        self.assertEqual(original, revised)


if __name__ == "__main__":
    unittest.main()
