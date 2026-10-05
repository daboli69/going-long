import unittest
from scripts.pick_evidence import build_pick_evidence, source_sha256


class PickEvidenceTests(unittest.TestCase):
    def inputs(self):
        games=[]; pbp=[]; snaps=[]; reports=[]
        for week in range(1,5):
            gid=f'2026_{week:02d}_ATL_NO'; games.append(dict(game_id=gid,season=2026,game_type='REG',week=week,kickoff=f'2026-09-{week*6:02d}T17:00:00Z',home_team='NO',away_team='ATL',home_score=20,away_score=10))
            snaps.append(dict(game_id=gid,season=2026,game_type='REG',team='NO',pfr_player_id='f',offense_snaps=30,offense_pct=.5))
            if week<=2: snaps.append(dict(game_id=gid,season=2026,game_type='REG',team='NO',pfr_player_id='t',offense_snaps=20,offense_pct=.3))
            else: reports.append(dict(season=2026,season_type='REG',team='NO',week=week,gsis_id='teammate',report_status='Out'))
            for i in range(week): pbp.append(dict(game_id=gid,season=2026,season_type='REG',posteam='NO',play_type='pass',receiver_player_id='focal',receiving_yards=10))
            pbp.append(dict(game_id=gid,season=2026,season_type='REG',play_type='game_end',game_seconds_remaining=0))
        return dict(season=2026,games=games,pbp_rows=pbp,snap_rows=snaps,roster_rows=[dict(season=2026,gsis_id='focal',pfr_id='f',position='WR',full_name='Receiver'),dict(season=2026,gsis_id='teammate',pfr_id='t',position='RB',full_name='Runner')],injury_rows=reports,as_of='2026-10-05',generated_at='2026-10-05T18:00:00Z')

    def test_cross_position_with_without_is_descriptive_and_not_causal(self):
        e=build_pick_evidence(**self.inputs()); p=e['teammate_out_splits']['NO|focal|teammate']
        self.assertEqual((p['with_n'],p['without_n']),(2,2)); self.assertEqual(p['with']['targets_per_game'],1.5); self.assertEqual(p['without']['targets_per_game'],3.5)
        self.assertIn('not causal',p['interpretation']); self.assertIn('lack publication',p['report_timing']); self.assertEqual(e['report_time_audit']['eligible_dated_rows'],0)

    def test_missing_absence_or_contradictory_snaps_never_prove_out(self):
        d=self.inputs();d['injury_rows']=[];self.assertEqual(build_pick_evidence(**d)['teammate_out_splits'],{})
        d=self.inputs();d['snap_rows'].append(dict(d['snap_rows'][1],game_id=d['games'][2]['game_id']));p=build_pick_evidence(**d)['teammate_out_splits']['NO|focal|teammate'];self.assertEqual(p['without_n'],1);self.assertEqual(p['status'],'insufficient_games')

    def test_zero_usage_requires_positive_snaps_and_complete_pbp(self):
        d=self.inputs(); d['pbp_rows']=[r for r in d['pbp_rows'] if r.get('game_id')!=d['games'][0]['game_id']];e=build_pick_evidence(**d)
        self.assertEqual(e['recent_player_games']['NO|focal']['games'],3)
        d=self.inputs();d['pbp_rows']=[r for r in d['pbp_rows'] if r.get('receiver_player_id')!='focal'];e=build_pick_evidence(**d);self.assertEqual(e['recent_player_games']['NO|focal']['games_log'][0]['targets'],0)

    def test_future_or_incomplete_finals_and_failed_sources_are_excluded(self):
        d=self.inputs();d['games'][0]['home_score']=None;d['games'][1]['kickoff']='2026-10-06T17:00:00Z';self.assertEqual(build_pick_evidence(**d)['recent_player_games']['NO|focal']['games'],2)
        d=self.inputs();d['source_meta']={'pbp':{'status':'unavailable'}};e=build_pick_evidence(**d);self.assertEqual(e['recent_player_games'],{});self.assertEqual(e['teammate_out_splits'],{})

    def test_future_dated_reports_do_not_establish_absence(self):
        d=self.inputs()
        for r in d['injury_rows']:r['date_modified']='2026-10-06T00:00:00Z'
        self.assertEqual(build_pick_evidence(**d)['teammate_out_splits'],{})
        self.assertEqual(source_sha256([{'b':2},{'a':1}]),source_sha256([{'a':1},{'b':2}]))
