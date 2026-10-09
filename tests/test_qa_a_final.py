"""QA-A final pass: pins confirmed defects (these FAIL until fixed)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class FirstTdGate(unittest.TestCase):
    def test_first_td_outcomes_only_for_active_roster_players(self):
        """Week-5 First TD gives probability to practice-squad (DEV), cut (CUT) and not-on-roster players (e.g. Tyreek Hill MIA, last game 2025-09-29, 3.8%)."""
        history = json.loads((ROOT / 'data/history.json').read_text(encoding='utf-8'))['betting']
        roster = {v['gsis_id']: str(v.get('roster_status')).upper() for v in json.loads((ROOT / 'data/injury_context.json').read_text(encoding='utf-8'))['current_players'].values() if v.get('gsis_id')}
        teams_with_roster = {v['team'] for v in json.loads((ROOT / 'data/injury_context.json').read_text(encoding='utf-8'))['current_players'].values()}
        bad = []
        for gid, game in history['derivatives']['first_td'].items():
            if not gid.startswith('2026_05'):
                continue
            for pid, o in game['outcomes'].items():
                if pid.startswith('00-') and o['probability'] > 0.01 and o['team'] in teams_with_roster and roster.get(pid) != 'ACT':
                    bad.append((gid, o['name'], roster.get(pid), round(o['probability'], 3)))
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
