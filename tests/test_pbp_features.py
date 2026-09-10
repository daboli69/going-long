import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pbp_features import aggregate, pressure_matchup


def play(i, **changes):
    return dict(game_id='g', play_id=i, game_date='2025-09-01', posteam='A', defteam='B',
                qtr=1, drive=1, quarter_seconds_remaining=900-i*20, qb_dropback=1,
                rush_attempt=0, receiver_player_id='p', wp=.5, xpass=.6, air_yards=10,
                receiving_yards=12, yardline_100=5, **changes)


class PublicFeaturesTests(unittest.TestCase):
    def test_neutral_boundaries_future_dedup_and_original_opening(self):
        rows=[]
        for i in range(1, 18):
            r=play(i);r['wp']=.9 if i<=15 else .2 if i==16 else .8;rows.append(r)
        rows += [rows[-1], dict(play(18), wp=None), dict(play(19), game_date='2027-01-01')]
        out=aggregate(rows, as_of='2026-01-01')
        self.assertEqual(out['neutral_snaps'],2)
        self.assertEqual(out['teams']['A']['opening_snaps'],0)
        self.assertAlmostEqual(out['teams']['A']['proe'],.4)

    def test_charting_missing_is_not_zero_and_on_field_not_route(self):
        rows=[play(1),play(2),play(3)]
        charts=[dict(nflverse_game_id='g',play_id=1,offense_players='p;q',was_pressure=True),
                dict(nflverse_game_id='g',play_id=2,offense_players=['q'],was_pressure=False)]
        out=aggregate(rows,charting=charts)
        p=out['players']['A|p'];q=out['players']['A|q'];t=out['teams']['A']
        self.assertEqual(p['pass_snap_participation_proxy'],.5)
        self.assertEqual(p['targets_per_pass_snap_proxy'],1)
        self.assertEqual(q['targets_per_pass_snap_proxy'],0)
        self.assertIsNone(p['routes_run']);self.assertIsNone(p['tprr'])
        self.assertEqual(t['pressure_rate_allowed'],.5)
        self.assertEqual(t['participation_coverage'],2/3)
        self.assertEqual(out['defenses']['B']['pressure_rate_generated'],.5)

    def test_pace_does_not_cross_quarter_and_endzone_is_geometric(self):
        rows=[play(1), dict(play(2),qtr=2),dict(play(3),qtr=2,air_yards=2)]
        out=aggregate(rows)
        self.assertEqual(out['teams']['A']['pace_pairs'],1)
        self.assertEqual(out['players']['A|p']['end_zone_targets'],2)
        self.assertAlmostEqual(out['teams']['A']['periods']['Q1']['snap_fraction'],1/3)

    def test_pressure_sensitivity_direction_limits_and_missing(self):
        self.assertEqual(pressure_matchup({}, {})['status'],'insufficient')
        off=dict(pressure_rate_allowed=.2,pressure_dropbacks=500,pressured_dropbacks=100,
                 clean_dropbacks=400,pressured_pass_yards=200,clean_pass_yards=3200,
                 pressured_scramble_yards=200,clean_scramble_yards=40,dropbacks=500,games=12)
        result=pressure_matchup(off,dict(pressure_rate_generated=.5,pressure_dropbacks=500))
        self.assertGreaterEqual(result['pass_scale'],.85)
        self.assertLess(result['pass_scale'],1)
        self.assertGreater(result['scramble_yards_delta'],0)
        self.assertEqual(pressure_matchup(off,dict(pressure_rate_generated=.1,pressure_dropbacks=500))['pass_scale'],1)

    def test_coverage_labels_and_nCAA_has_no_player_profiles(self):
        c=[dict(nflverse_game_id='g',play_id=1,defense_man_zone_type='MAN_COVERAGE',defense_coverage_type='COVER_1')]
        result=aggregate([play(1)],charting=c)
        self.assertEqual(result['players']['A|p']['coverage']['MAN_COVERAGE']['yards_per_target'],12)
        self.assertEqual(result['defense_coverage']['B']['single_high']['dropbacks'],1)
        cfb=[dict(game_id=1,game_play_number=1,start_date='2025-01-01',pos_team='A',def_pos_team='B',period=1,clock_minutes=14,clock_seconds=0,wp_before=.5,**{'pass':1})]
        self.assertEqual(aggregate(cfb,'ncaa')['players'],{})
