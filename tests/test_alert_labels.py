import unittest
from scripts.topdown.alerts import format_arbitrage

class AlertLabels(unittest.TestCase):
    def test_matchup_and_opposing_stakes(self):
        arb=dict(sport='ncaa',home='Ohio State Buckeyes',away='Texas Longhorns',market='spreads',return_if_executable=.041,selection='6bbd62b6bbb7',legs=[dict(side='Ohio State Buckeyes',line=-3.5,american=110,book='betmgm',stake_per_100=50),dict(side='Texas Longhorns',line=3.5,american=110,book='betrivers',stake_per_100=50)])
        text=format_arbitrage(arb)
        self.assertIn('Texas Longhorns at Ohio State Buckeyes',text)
        self.assertIn('Texas Longhorns +3.5 +110 at betrivers',text)
        self.assertNotIn(arb['selection'],text)
        self.assertIn('Both opposing bets',text)
        self.assertIn('availability not independently verified',text)
