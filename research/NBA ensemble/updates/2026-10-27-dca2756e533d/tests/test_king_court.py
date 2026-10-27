import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scripts.king_court.common import code_receipts, digest, load_sealed, protocol, seal, utc, write_new
from scripts.king_court.data import PLAYER_FIELDS, eligible_history, normalize, validate_slate
from scripts.king_court.demo import fixtures
from scripts.king_court.events import reconcile
from scripts.king_court.history import build_profiles, effective_n, flatten, player_profile, recency_weights
from scripts.king_court.research import evaluate_result, forecast, parameter_grid, paired_slate_intervals, validate_experiment
from scripts.king_court.simulation import allocate, capped_minutes, leader_summary, prize_scenario, simulate, summarize


class KingCourtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history,cls.slate=fixtures()
        cls.params=parameter_grid()[0]
        cls.profiles,cls.teams,cls.overtime=build_profiles(cls.slate,cls.history['games'],cls.params,cls.history['debut_seasons'])
        cls.sim=simulate(cls.slate,cls.profiles,cls.teams,cls.overtime,512,42)
        cls.summary=summarize(cls.sim,cls.profiles)

    def test_two_level_decay_and_missing_seasons(self):
        origin=utc(self.slate['origin'])
        rows=[dict(season=s,tipoff=f'{s-1}-10-20T23:00:00Z') for s in (2023,2024,2025,2026,2027)]
        w=recency_weights(rows,origin,2027,self.params)
        self.assertEqual(w[0],0)
        self.assertGreater(w[-1],w[-2])
        self.assertGreater(w[-2],w[-3])
        recent=[dict(season=2027,tipoff=x) for x in ('2026-10-10T23:00:00Z','2026-10-20T23:00:00Z')]
        v=recency_weights(recent,origin,2027,self.params)
        self.assertGreater(v[1],v[0])
        self.assertAlmostEqual(effective_n([1,1,1]),3)
        self.assertEqual(recency_weights(rows,origin,2027,self.params,'current_only').tolist(),[0,0,0,0,1])

    def test_rookie_prior_never_invents_own_history(self):
        p=dict(self.slate['players'][0],player_id='fixture:NEW',debut_season=2027)
        value=player_profile(p,flatten(self.history['games']),utc(self.slate['origin']),2027,self.params,self.history['debut_seasons'])
        self.assertEqual(value['experience'],'rookie')
        self.assertEqual(value['evidence']['games'],0)
        self.assertEqual(value['evidence']['season_weight_shares'],{})
        self.assertEqual(value['prior']['own_rate_evidence_share'],0)
        self.assertGreater(value['rates']['fga'],0)
        self.assertEqual(value['prior']['kind'],'experience_position_stage_matched')
        broad=player_profile(p,flatten(self.history['games']),utc(self.slate['origin']),2027,self.params,{})
        self.assertIn('fallback',broad['prior']['kind'])

    def test_second_year_and_team_change_keep_skill_separate_from_role(self):
        second=next(p for p in self.profiles if p['player_id']=='fixture:BOS:6')
        self.assertEqual(second['experience'],'second_year')
        self.assertEqual(set(second['evidence']['season_weight_shares']),{'2026','2027'})
        player=dict(self.slate['players'][0],team='NYK')
        player.pop('expected_minutes')
        result=player_profile(player,flatten(self.history['games']),utc(self.slate['origin']),2027,self.params,self.history['debut_seasons'])
        self.assertEqual(result['role_evidence']['games'],0)
        self.assertGreater(result['evidence']['games'],0)

    def test_future_results_and_late_source_receipts_are_excluded(self):
        history=copy.deepcopy(self.history)
        origin=utc(self.slate['origin'])
        future=copy.deepcopy(history['games'][-1])
        future['tipoff']=(origin+timedelta(hours=5)).isoformat()
        future['known_at']=origin.isoformat()
        history['games'].append(future)
        self.assertEqual(len(eligible_history(history,origin,2027)),len(self.history['games']))
        history['games'][0]['known_at']=(origin+timedelta(days=1)).isoformat()
        self.assertEqual(len(eligible_history(history,origin,2027)),len(self.history['games'])-1)
        self.assertEqual(len(eligible_history(history,origin,2027,'retrospective')),len(self.history['games']))

    def test_full_field_and_tuesday_eastern_origin(self):
        validate_slate(self.slate)
        late=copy.deepcopy(self.slate)
        late['games'][0]['tipoff']='2026-10-28T02:00:00+00:00'
        validate_slate(late)
        for patch in ({'field_complete':False},{'eligible_player_ids':self.slate['eligible_player_ids'][:-1]},
                      {'date':'2026-10-28'},{'origin':'2026-10-27T23:01:00+00:00'}):
            wrong=dict(self.slate,**patch)
            with self.assertRaises(ValueError):
                validate_slate(wrong)
        unknown=copy.deepcopy(self.slate)
        unknown['players'][0]['availability']='questionable'
        with self.assertRaises(ValueError):
            validate_slate(unknown)

    def test_source_age_and_unknown_rookie_status_fail(self):
        bad=copy.deepcopy(self.slate)
        bad['evidence_kind']='prospective'
        bad['known_at']='2026-10-20T12:00:00Z'
        with self.assertRaisesRegex(ValueError,'stale'):
            validate_slate(bad)
        bad=copy.deepcopy(self.slate)
        bad['players'][0].pop('debut_season')
        with self.assertRaisesRegex(ValueError,'debut'):
            validate_slate(bad)

    def test_missing_historical_season_is_not_silently_ignored(self):
        history=copy.deepcopy(self.history)
        history['games']=[g for g in history['games'] if g['season']!=2024]
        with self.assertRaisesRegex(ValueError,'Missing requested season'):
            forecast(history,self.slate,self.params,100,mode='retrospective')

    def test_integer_pra_pool_and_minutes_accounting(self):
        s=self.sim
        np.testing.assert_array_equal(s['pra'],s['points']+s['rebounds']+s['assists'])
        self.assertTrue(np.issubdtype(s['pra'].dtype,np.integer))
        self.assertTrue(np.all(s['pra']>=0))
        for team in ('BOS','NYK'):
            indexes=[i for i,p in enumerate(self.profiles) if p['team']==team]
            np.testing.assert_allclose(s['minutes'][:,indexes].sum(axis=1),240,atol=1e-7)
            self.assertLessEqual(s['minutes'][:,indexes].max(),48)
        self.assertTrue(s['diagnostics'][0]['rebound_pool_conservation'])
        self.assertTrue(s['diagnostics'][0]['self_assists_excluded'])
        self.assertGreater(np.corrcoef(s['minutes'][:,0],s['points'][:,0])[0,1],0)

    def test_out_player_never_receives_allocated_stats(self):
        profiles=copy.deepcopy(self.profiles)
        profiles[0].update(availability='out',minutes_mean=0,minutes_sd=0)
        result=simulate(self.slate,profiles,self.teams,self.overtime,100,2)
        for key in ('pra','minutes','points','rebounds','assists'):
            self.assertTrue(np.all(result[key][:,0]==0))

    def test_allocation_and_caps_reject_impossible_pools(self):
        rng=np.random.default_rng(3)
        np.testing.assert_array_equal(allocate(np.array([5,7]),np.array([1,0]),rng),[[5,0],[7,0]])
        with self.assertRaises(ValueError):
            allocate(np.array([5]),np.array([0,0]),rng)
        with self.assertRaises(ValueError):
            capped_minutes(np.ones((1,4)),np.array([48]))

    def test_ties_are_overlapping_events_not_normalized_win_odds(self):
        values=np.array([[10,10,9],[9,10,8],[10,9,8]])
        result,leaders=leader_summary(values)
        self.assertAlmostEqual(result[0]['inclusive_leader_probability'],2/3)
        self.assertAlmostEqual(result[0]['sole_leader_probability'],1/3)
        self.assertAlmostEqual(sum(r['fractional_leader_credit'] for r in result),1)
        self.assertGreater(sum(r['inclusive_leader_probability'] for r in result),1)

    def test_prize_pool_is_shared_by_customers_across_tied_players(self):
        _,leaders=leader_summary(np.array([[10,10,9],[9,10,8],[10,9,8]]))
        scenario=dict(name='count fixture',kind='measured_counts',counts={'A':1,'B':3,'C':0},
                      source_scope='promotion_qualifying_selections',source='fixture',known_at='2026-10-27T12:00:00Z')
        result=prize_scenario(leaders,['A','B','C'],scenario,pool=1000)
        self.assertAlmostEqual(result['results'][0]['expected_bonus_bet_face_value'],(200+500)/3)
        self.assertAlmostEqual(result['results'][1]['expected_bonus_bet_face_value'],(200+250)/3)
        scenario=dict(name='hypothetical',kind='hypothetical',other_entrants=0,ownership={'A':.5,'B':.5,'C':0})
        result=prize_scenario(leaders,['A','B','C'],scenario,pool=1000)
        self.assertAlmostEqual(result['results'][0]['expected_bonus_bet_face_value'],1000*2/3)
        scenario['ownership'].pop('C')
        with self.assertRaises(ValueError):
            prize_scenario(leaders,['A','B','C'],scenario)

    def test_simulation_does_not_invent_popularity(self):
        self.assertEqual(self.summary['prize_scenarios'],[])
        self.assertTrue(all(p['observed_ownership_fraction'] is None for p in self.summary['players']))
        self.assertAlmostEqual(self.summary['probability_accounting']['sum_fractional'],1)
        json.dumps(self.summary,allow_nan=False)

    def test_readiness_blocks_unselected_weights_and_missing_evidence(self):
        result,_=forecast(self.history,self.slate,self.params,draws=100,mode='retrospective')
        self.assertEqual(result['recommendation_status'],'blocked_research_only')
        self.assertFalse(result['parameters_selected'])
        self.assertIn('history_lineup_reconciliation_missing',result['blockers'])
        self.assertIn('complete_date_specific_offer_terms_unverified',result['blockers'])

    def test_ownership_cannot_inherit_a_pool_from_another_date(self):
        slate=copy.deepcopy(self.slate)
        slate.pop('offer')
        scenario=dict(name='fixture',kind='hypothetical',other_entrants=10,
                      ownership={p['player_id']:1/len(slate['players']) for p in slate['players']})
        with self.assertRaisesRegex(ValueError,'date-specific'):
            forecast(self.history,slate,self.params,100,[scenario],mode='retrospective')

    def test_prospective_field_needs_independent_preserved_identity(self):
        slate=copy.deepcopy(self.slate)
        slate['evidence_kind']='prospective'
        with self.assertRaisesRegex(ValueError,'Independent'):
            validate_slate(slate)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'field.json'
            payload=dict(date=slate['date'],eligible_game_ids=slate['eligible_game_ids'],eligible_player_ids=slate['eligible_player_ids'])
            path.write_text(json.dumps(payload))
            from hashlib import sha256
            slate['field_source_receipt']=dict(path=str(path),sha256=sha256(path.read_bytes()).hexdigest(),source='fixture',known_at=slate['origin'])
            validate_slate(slate)
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'bytes changed'):
                validate_slate(slate)

    def test_holdout_overlap_and_unregistered_weights_fail(self):
        dates=[(datetime(2026,10,27)+timedelta(weeks=i)).date().isoformat() for i in range(8)]
        experiment=dict(development_dates=dates,holdout_dates=[dates[-1]])
        with self.assertRaisesRegex(ValueError,'Disjoint'):
            validate_experiment(experiment,[])
        experiment['holdout_dates']=['2027-01-05']
        with self.assertRaisesRegex(ValueError,'registration'):
            validate_experiment(experiment,[])

    def test_source_box_accounting_and_unknown_minutes_fail_closed(self):
        g=self.history['games'][-1]
        schedule=[dict(game_id=7,season=2027,season_type=2,date=g['tipoff'],home_abbreviation='BOS',away_abbreviation='NYK',
                       time_valid=True,status_type_name='STATUS_FINAL',status_type_completed=True,
                       home_score=g['teams']['BOS']['pts'],away_score=g['teams']['NYK']['pts'])]
        players=[]
        for i,p in enumerate(g['players']):
            players.append(dict(game_id=7,athlete_id=i,athlete_display_name=p['name'],team_abbreviation=p['team'],
                                minutes=p['minutes'],athlete_position_abbreviation='G',did_not_play=False,
                                **{field:p[key] for key,field in PLAYER_FIELDS.items()}))
        teams=[]
        for code,stats in g['teams'].items():
            values={field:stats[key] for key,field in PLAYER_FIELDS.items()}
            values.pop('points');values.pop('rebounds')
            teams.append(dict(game_id=7,team_abbreviation=code,team_score=stats['pts'],total_rebounds=stats['reb'],total_turnovers=stats['tov'],**values))
        result=normalize(schedule,players,teams,'2026-10-27T12:00:00Z')
        self.assertEqual(len(result['games']),1)
        bad=copy.deepcopy(players)
        bad[0]['minutes']=None
        with self.assertRaisesRegex(ValueError,'No fully reconciled'):
            normalize(schedule,bad,teams,'2026-10-27T12:00:00Z')
        duplicate=dict(players[0],did_not_play=True)
        with self.assertRaisesRegex(ValueError,'played/DNP'):
            normalize(schedule,players+[duplicate],teams,'2026-10-27T12:00:00Z')

    def test_settlement_requires_the_full_outcome_field_and_reports_cohorts(self):
        actual={pid:int(self.sim['pra'][0,j]) for j,pid in enumerate(self.sim['player_ids'])}
        summary=dict(self.summary,slate_date=self.slate['date'])
        value=evaluate_result(summary,self.sim,actual)
        self.assertTrue(0<=value['coverage80']<=1)
        report=paired_slate_intervals([value])
        self.assertEqual(report['evidence_status'],'insufficient_slates')
        self.assertIn('second_year',report['experience_cohorts'])
        actual.pop(next(iter(actual)))
        with self.assertRaises(ValueError):
            evaluate_result(summary,self.sim,actual)

    def test_immutable_receipts_detect_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json'
            body=seal(dict(value=1))
            write_new(path,body)
            self.assertEqual(load_sealed(path),body)
            with self.assertRaises(FileExistsError):
                write_new(path,body)
            path.write_text(json.dumps(dict(body,value=2)))
            with self.assertRaises(ValueError):
                load_sealed(path)


class EventsTest(unittest.TestCase):
    def fixture(self):
        players=[]
        people={}
        for i in range(10):
            pid=f'P{i}';people[str(100+i)]=pid
            players.append(dict(player_id=pid,team='BOS' if i<5 else 'NYK',pts=2 if i==0 else 0,
                                reb=1 if i==2 else 0,ast=1 if i==1 else 0,minutes=48))
        game=dict(game_id='espn:X',home='BOS',away='NYK',game_minutes=48,players=players)
        actions=[dict(actionNumber=1,period=1,clock='PT12M00.00S',actionType='2pt',shotResult='Made',personId=100,teamId=1,assistPersonId=101),
                 dict(actionNumber=2,period=1,clock='PT11M40.00S',actionType='2pt',shotResult='Missed',personId=105,teamId=2),
                 dict(actionNumber=3,period=1,clock='PT11M39.00S',actionType='rebound',personId=102,teamId=1)]
        for period in (2,3,4):
            actions.append(dict(actionNumber=period+2,period=period,clock='PT12M00.00S',actionType='period'))
        raw=dict(game=dict(gameId='NBA:X',actions=actions))
        cross=dict(game_id='espn:X',nba_game_id='NBA:X',persons=people,teams={'1':'BOS','2':'NYK'},
                   period_lineups={str(n):{'BOS':[f'P{i}' for i in range(5)],'NYK':[f'P{i}' for i in range(5,10)]} for n in (1,2,3,4)})
        return raw,game,cross

    def test_raw_events_and_five_player_stints_reconcile(self):
        raw,game,cross=self.fixture()
        result=reconcile(raw,game,cross)
        self.assertTrue(result['event_agreement'])
        self.assertTrue(result['lineup_agreement'])
        self.assertEqual(result['derived_minutes']['P0'],48)

    def test_missing_lineups_are_not_claimed_verified(self):
        raw,game,cross=self.fixture()
        cross.pop('period_lineups')
        result=reconcile(raw,game,cross)
        self.assertTrue(result['event_agreement'])
        self.assertFalse(result['lineup_agreement'])
        raw['game']['actions'][0].pop('assistPersonId')
        self.assertFalse(reconcile(raw,game,cross)['event_agreement'])

    def test_conflicting_events_and_self_assists_fail(self):
        raw,game,cross=self.fixture()
        raw['game']['actions'][0]['assistPersonId']=100
        with self.assertRaisesRegex(ValueError,'Self-assist'):
            reconcile(raw,game,cross)
        raw,game,cross=self.fixture()
        raw['game']['actions'].append(dict(raw['game']['actions'][0],personId=101))
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            reconcile(raw,game,cross)

    def test_substitution_batches_reconstruct_minutes(self):
        raw,game,cross=self.fixture()
        game['players'][4]['minutes']=24
        game['players'].append(dict(player_id='P10',team='BOS',pts=0,reb=0,ast=0,minutes=24))
        cross['persons']['110']='P10'
        for period in ('3','4'):
            cross['period_lineups'][period]['BOS']=['P0','P1','P2','P3','P10']
        actions=raw['game']['actions'][:4]
        actions.extend([dict(actionNumber=5,period=2,clock='PT00M00.00S',actionType='substitution',subType='out',personId=104),
                        dict(actionNumber=6,period=2,clock='PT00M00.00S',actionType='substitution',subType='in',personId=110),
                        dict(actionNumber=7,period=3,clock='PT12M00.00S',actionType='period'),
                        dict(actionNumber=8,period=4,clock='PT12M00.00S',actionType='period')])
        raw['game']['actions']=actions
        report=reconcile(raw,game,cross)
        self.assertTrue(report['lineup_agreement'])
        self.assertEqual(report['derived_minutes']['P4'],24)
        self.assertEqual(report['derived_minutes']['P10'],24)


if __name__=='__main__':
    unittest.main()
