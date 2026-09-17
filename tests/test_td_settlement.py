"""Only published touchdown counts can settle a frozen research record."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from settle_markets import settle
from topdown.journal import Journal
from topdown.model import stamp


class TouchdownSettlementTests(unittest.TestCase):
    def test_counts_missing_results_refunds_and_legacy_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            journal = Journal(root / 'journal.db')
            base = dict(tracking_group='all_projection', sport='nfl', event='game',
                        home='BUF', away='DET', kickoff='2026-09-18T00:15:00Z',
                        observed_at='2026-09-17T20:00:00Z', profile_id='player',
                        player='Test Player', side_index=0, line=0.5)
            cases = [('rush', 'player_rushing_tds', 0.5, 0, 'win'),
                     ('receive', 'player_receiving_tds', 0.5, 0, 'loss'),
                     ('refund', 'rush_tds', 1, 0, 'refund'),
                     ('under', 'rec_tds', 0.5, 1, 'win'),
                     ('missing', 'player_passing_tds', 0.5, 0, None),
                     ('anytime', 'anytime_td', 0.5, 0, None)]
            for ident, market, line, side, _ in cases:
                row = dict(base, id=ident, market=market, line=line, side_index=side)
                journal.append('prediction', ident, row)
            history = {'betting': {'profiles': {'player': {'name': 'Test Player', 'team': 'BUF'}}}}
            results = {'generated_at': '2026-09-18T15:00:00Z', 'games': {'g': {
                'sport': 'nfl', 'home': 'BUF', 'away': 'DET', 'kickoff': base['kickoff'],
                'homeScore': 21, 'awayScore': 14}}, 'players': {}}
            (root / 'data/history.json').write_text(json.dumps(history))
            path = root / 'data/results.json'
            path.write_text(json.dumps(results))
            settle(journal, root, stamp('2026-09-18T16:00:00Z'))
            self.assertEqual(journal.rows('settlement'), [])
            # Eastern date, not the next UTC day. Missing is distinct from zero.
            results['players']['player|2026-09-17'] = {'rush_tds': 1, 'rec_tds': 0}
            path.write_text(json.dumps(results))
            for _ in range(2):
                settle(journal, root, stamp('2026-09-18T16:00:00Z'))
            actual = {s['prediction_id']: s['status'] for s in journal.rows('settlement')}
            self.assertEqual(actual, {i: expected for i, _, _, _, expected in cases if expected})
            journal.db.close()


if __name__ == '__main__':
    unittest.main()
