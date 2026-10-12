import unittest
from scripts.teammate_challenger import forecast


class TeammateChallengerTests(unittest.TestCase):
    def inputs(self):
        return dict(champion_mean=80, all_targets=[4,4,4,12,12,12],
                    with_targets=[4,4,4], without_targets=[12,12,12],
                    teammate_state='playing', pregame_verified=True)

    def test_shrinkage_is_between_champion_and_unpooled_rate(self):
        r=forecast(**self.inputs())
        self.assertEqual(r['status'],'research_only')
        self.assertGreater(r['challenger'],40)
        self.assertLess(r['challenger'],80)
        d=self.inputs();d['teammate_state']='out'
        self.assertGreater(forecast(**d)['challenger'],80)

    def test_missing_pregame_evidence_and_small_samples_block(self):
        for value in [False, 'false', 'true', 1, None]:
            d=self.inputs();d['pregame_verified']=value
            self.assertIsNone(forecast(**d)['challenger'])
        d=self.inputs();d['without_targets']=[12,12]
        self.assertIsNone(forecast(**d)['challenger'])

    def test_missing_and_invalid_counts_never_become_zero(self):
        for value in [None, True, -1, float('nan'), float('inf')]:
            d=self.inputs();d['with_targets'][0]=value
            self.assertIsNone(forecast(**d)['challenger'])

    def test_equal_conditions_do_not_change_forecast(self):
        d=self.inputs();d.update(all_targets=[8]*6,with_targets=[8]*3,without_targets=[8]*3)
        self.assertEqual(forecast(**d)['challenger'],80)
