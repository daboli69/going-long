import json
import math
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nb_shadow as ns  # noqa: E402

KICK = '2026-10-11T13:00:00.000-04:00'
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding='utf8')


def make_root(root, generated='2026-10-09T11:00:00+00:00', completed=False):
    write(root / 'config' / 'nb_shadow.json', {'version': 'v', 'c': 1.5})
    props = []
    for book, line in (('a', 3.5), ('b', 4.5), ('c', 3.5)):
        props.append({'market': 'receptions', 'eventId': 'e1', 'player': 'Pat Receiver', 'line': line, 'bookKey': book, 'kickoff': KICK})
    props.append({'market': 'receptions', 'eventId': 'e1', 'player': 'No Profile', 'line': 2.5, 'bookKey': 'a', 'kickoff': KICK})
    props.append({'market': 'rec_yds', 'eventId': 'e1', 'player': 'Pat Receiver', 'line': 40.5, 'bookKey': 'a', 'kickoff': KICK})
    write(root / 'data' / 'nfl_betting.json', {'generated_at': generated, 'props': props, 'games': [
        {'game_id': '2026_05_AAA_BBB', 'season': 2026, 'week': 5, 'home': 'BBB', 'away': 'AAA', 'kickoff': '2026-10-11T17:00:00+00:00', 'completed': completed}]})
    write(root / 'data' / 'history.json', {'betting': {'generated_at': generated, 'aliases': {'e1|pat receiver': {'player_id': 'p1'}}, 'profiles': {
        'p1': {'name': 'Pat Receiver', 'team': 'AAA', 'position': 'WR', 'stats': {'receptions': {'mean': 4.0, 'policy': 'champion-v2'}}}}}})
    write(root / 'data' / 'results.json', {'generated_at': 'x', 'players': {}})


class Distribution(unittest.TestCase):
    def test_nb1_matches_scipy_reference(self):
        # scipy.stats.nbinom(n=mean/(c-1), p=1/c).cdf(k)
        known = {(2, 3.0, 1.5): 0.46822130772748, (6, 3.0, 1.5): 0.9326, (3, 1.0, 1.53): 0.9467}
        try:
            from scipy.stats import nbinom
        except ImportError:
            self.skipTest('scipy missing')
        for (k, mean, c) in known:
            self.assertAlmostEqual(ns.nb1_cdf(k, mean, c), float(nbinom.cdf(k, mean / (c - 1), 1 / c)), places=12)
        self.assertAlmostEqual(ns.nb1_cdf(2, 3.0, 1.5), known[(2, 3.0, 1.5)], places=3)

    def test_moments_and_limits(self):
        mean, c = 3.2, 1.5317
        pmf = [ns.nb1_cdf(k, mean, c) - ns.nb1_cdf(k - 1, mean, c) for k in range(0, 200)]
        m = sum(k * p for k, p in enumerate(pmf))
        v = sum((k - m) ** 2 * p for k, p in enumerate(pmf))
        self.assertAlmostEqual(m, mean, places=6)
        self.assertAlmostEqual(v, c * mean, places=5)
        self.assertAlmostEqual(ns.nb1_cdf(4, 2.0, 1.0), ns.poisson_cdf(4, 2.0), places=12)  # c = 1 is Poisson
        self.assertEqual(ns.nb1_cdf(-1, 2.0, 1.5), 0.0)
        self.assertEqual(ns.nb1_cdf(3, 0.0, 1.5), 1.0)
        self.assertAlmostEqual(ns.poisson_cdf(4, 3), 0.8152632445237722, places=12)

    def test_p_over_half_and_integer_lines(self):
        self.assertAlmostEqual(ns.p_over(ns.poisson_cdf, 3.5, 3.0), 1 - ns.poisson_cdf(3, 3.0))
        self.assertAlmostEqual(ns.p_over(ns.poisson_cdf, 3.0, 3.0), 1 - ns.poisson_cdf(3, 3.0))  # push excluded from over


class Recording(unittest.TestCase):
    def test_record_rows_and_median_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_root(root)
            result = ns.record(date(2026, 10, 11), NOW, root)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(result['rejected'], {'no_champion_v2_receptions_mean': 1})
            doc = json.loads((root / 'data' / 'nb_shadow' / '2026-week-05.json').read_text(encoding='utf8'))
            row = doc['rows'][0]
            self.assertEqual((row['line'], row['n_books'], row['mean'], row['game_id']), (3.5, 3, 4.0, '2026_05_AAA_BBB'))
            self.assertAlmostEqual(row['p_over_poisson'], 1 - ns.poisson_cdf(3, 4.0))
            self.assertAlmostEqual(row['p_over_nb1'], 1 - ns.nb1_cdf(3, 4.0, 1.5))
            self.assertEqual(doc['data_cutoff'], '2026-10-09T11:00:00+00:00')
            self.assertEqual(doc['nb1_c'], 1.5)

    def test_write_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_root(root)
            ns.record(date(2026, 10, 11), NOW, root)
            path = root / 'data' / 'nb_shadow' / '2026-week-05.json'
            before = path.read_text(encoding='utf8')
            with self.assertRaises(FileExistsError):
                ns.record(date(2026, 10, 11), NOW, root)
            self.assertEqual(path.read_text(encoding='utf8'), before)

    def test_rejects_recording_after_kickoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_root(root)
            late = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)  # after the 13:00 ET kickoff
            result = ns.record(date(2026, 10, 11), late, root)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(result['rejected'], {'kickoff_not_after_recording_time': 2})
            self.assertEqual(list((root / 'data' / 'nb_shadow').glob('*.json')), [])

    def test_rejects_history_cutoff_not_before_kickoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_root(root, generated='2026-10-11T18:00:00+00:00')  # data cut after kickoff
            result = ns.record(date(2026, 10, 11), datetime(2026, 10, 9, tzinfo=timezone.utc), root)
            self.assertEqual(result['rows'], 0)
            self.assertIn('history_cutoff_not_before_kickoff', result['rejected'])

    def test_date_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_root(root)
            self.assertEqual(ns.record(date(2026, 10, 12), NOW, root)['rows'], 0)


class Settling(unittest.TestCase):
    def test_waits_until_final_then_settles_without_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_root(root)
            ns.record(date(2026, 10, 11), NOW, root)
            self.assertIn('waiting', ns.settle(root)[0][1])
            make_root_games_final(root)
            write(root / 'data' / 'results.json', {'generated_at': 'x', 'players': {'p1|2026-10-11': {'receptions': 5}}})
            self.assertIn('settled', ns.settle(root)[0][1])
            out = json.loads((root / 'data' / 'nb_shadow' / '2026-week-05-outcomes.json').read_text(encoding='utf8'))
            self.assertEqual(out['rows'][0]['actual'], 5)
            self.assertIsNone(out['summary'])
            self.assertEqual(ns.settle(root)[0][1], 'already settled')

    def test_summary_requires_thirty_rows_and_is_sane(self):
        rows = [{'line': 3.5, 'actual': 5 if i % 3 == 0 else 2, 'p_over_poisson': 0.3, 'p_over_nb1': 0.32} for i in range(29)]
        self.assertIsNone(ns.summarize(rows))
        rows.append({'line': 3.5, 'actual': 4, 'p_over_poisson': 0.3, 'p_over_nb1': 0.32})
        s = ns.summarize(rows)
        self.assertEqual(s['n'], 30)
        self.assertAlmostEqual(s['actual_over_rate'], 11 / 30)
        self.assertAlmostEqual(s['poisson']['brier'], (11 * 0.49 + 19 * 0.09) / 30)
        self.assertAlmostEqual(s['poisson']['logloss'], -(11 * math.log(.3) + 19 * math.log(.7)) / 30)

    def test_calibration_slope_recovers_known_slope(self):
        import random
        rng = random.Random(1)
        p = [rng.uniform(.05, .95) for _ in range(4000)]
        y = [1.0 if rng.random() < 1 / (1 + math.exp(-(0.2 + 0.8 * math.log(v / (1 - v))))) else 0.0 for v in p]
        fit = ns.calibration_slope(p, y)
        self.assertAlmostEqual(fit['slope'], 0.8, delta=0.12)

    def test_unplayed_rows_excluded(self):
        rows = [{'line': 3.5, 'actual': None, 'p_over_poisson': .3, 'p_over_nb1': .3} for _ in range(40)]
        self.assertIsNone(ns.summarize(rows))


def make_root_games_final(root):
    path = root / 'data' / 'nfl_betting.json'
    doc = json.loads(path.read_text(encoding='utf8'))
    for game in doc['games']:
        game['completed'] = True
    write(path, doc)


if __name__ == '__main__':
    unittest.main()
