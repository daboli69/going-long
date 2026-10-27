import ast
import copy
import inspect
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scripts.king_court.common import load_sealed,utc
from scripts.king_court.demo import fixtures
from scripts.king_court.history import build_profiles
from scripts.king_court.research import parameter_grid
from scripts.king_court.simulation import simulate as original_simulate
from scripts.king_court_diagnostics.challengers import game_block,shuffle_players
from scripts.king_court_diagnostics.archive_audit import audit_game
from scripts.king_court_diagnostics.dataset import profiles
from scripts.king_court_diagnostics.experiment import lock_code,verify_registration
from scripts.king_court_diagnostics.metrics import aggregate,evaluate,paired_intervals
from scripts.king_court_diagnostics.pools import PairedFGA
from scripts.king_court_diagnostics.simulation import simulate


class HookStripper(ast.NodeTransformer):
    def visit_FunctionDef(self,node):
        if node.name=='simulate':
            node.args.args=node.args.args[:-2]
            node.args.defaults=node.args.defaults[:-2]
        return self.generic_visit(node)

    def visit_Assign(self,node):
        for target in node.targets:
            if isinstance(target,ast.Name) and target.id in ('measured_pools','fga_override','fta_override'):
                return None
            if isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name) and target.value.id=='measured_pools':
                return None
        return self.generic_visit(node)

    def visit_If(self,node):
        if isinstance(node.test,ast.Compare) and any(isinstance(v,ast.Name) and v.id in ('fga_override','fta_override') for v in node.test.comparators):
            return None
        return self.generic_visit(node)

    def visit_Call(self,node):
        node.keywords=[k for k in node.keywords if k.arg!='measured_pools']
        return self.generic_visit(node)


class DistributionDiagnosticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history,cls.slate=fixtures()
        cls.params=parameter_grid()[0]
        cls.pp,cls.teams,cls.ot=build_profiles(cls.slate,cls.history['games'],cls.params,cls.history['debut_seasons'])
        cls.slate=copy.deepcopy(cls.slate)
        latest={p['player_id']:p for p in cls.history['games'][-1]['players']}
        cls.slate['outcomes']={pid:dict(points=p['pts'],rebounds=p['reb'],assists=p['ast'],minutes=p['minutes']) for pid,p in latest.items()}
        cls.slate['date']='2026-10-27'
        cls.history_large=cls.history['games']*2

    def test_only_declared_pool_hooks_differ_from_original_source(self):
        baseline=ast.parse(inspect.getsource(original_simulate))
        candidate=HookStripper().visit(ast.parse(inspect.getsource(simulate)))
        self.assertEqual(ast.dump(baseline,include_attributes=False),ast.dump(candidate,include_attributes=False))

    def test_disabled_repair_reproduces_all_original_samples_exactly(self):
        a=original_simulate(self.slate,self.pp,self.teams,self.ot,200,42)
        b=simulate(self.slate,self.pp,self.teams,self.ot,200,42)
        for name in ('points','rebounds','assists','minutes','pra'):
            np.testing.assert_array_equal(a[name],b[name])
        self.assertEqual(a['diagnostics'],b['diagnostics'])

    def test_paired_pool_center_and_integer_nonnegative_means(self):
        pool=PairedFGA(self.history_large,utc(self.slate['origin']),2027,self.params,self.teams,22)
        np.testing.assert_allclose(pool.evidence['centered_weighted_residual_mean'],[0,0],atol=1e-12)
        game=self.slate['games'][0]
        out=pool(game,np.full(50000,100.))
        for code,opponent in (('BOS','NYK'),('NYK','BOS')):
            expected=100*np.sqrt(self.teams[code]['fga_poss']*self.teams[opponent]['allowed_fga_poss'])
            self.assertAlmostEqual(out[code].mean(),expected,delta=.1)
            self.assertTrue(np.issubdtype(out[code].dtype,np.integer))
            self.assertTrue(np.all(out[code]>=0))
        self.assertEqual(pool.evidence['clipping_draws'],0)

    def test_future_outcomes_cannot_change_fitted_opportunity_pool(self):
        a=PairedFGA(self.history_large,utc(self.slate['origin']),2027,self.params,self.teams,22)
        games=copy.deepcopy(self.history_large)
        future=copy.deepcopy(games[-1]);future['tipoff']='2026-10-28T23:00:00Z'
        future['teams']['BOS']['fga']=1000
        games.append(future)
        b=PairedFGA(games,utc(self.slate['origin']),2027,self.params,self.teams,22)
        np.testing.assert_array_equal(a.residuals,b.residuals)
        np.testing.assert_array_equal(a.probability,b.probability)

    def test_repaired_simulation_preserves_integer_component_accounting(self):
        pool=PairedFGA(self.history_large,utc(self.slate['origin']),2027,self.params,self.teams,22)
        sample=simulate(self.slate,self.pp,self.teams,self.ot,200,42,field_goal_pools=pool)
        np.testing.assert_array_equal(sample['pra'],sample['points']+sample['rebounds']+sample['assists'])
        for code in ('BOS','NYK'):
            indexes=[i for i,p in enumerate(self.pp) if p['team']==code]
            np.testing.assert_allclose(sample['minutes'][:,indexes].sum(axis=1),240,atol=1e-7)
        self.assertTrue(sample['diagnostics'][0]['rebound_pool_conservation'])
        self.assertTrue(sample['diagnostics'][0]['self_assists_excluded'])

    def test_shuffling_preserves_player_joint_components_and_all_marginals(self):
        source=simulate(self.slate,self.pp,self.teams,self.ot,200,42)
        mixed=shuffle_players(source,17)
        np.testing.assert_array_equal(mixed['pra'],mixed['points']+mixed['rebounds']+mixed['assists'])
        for name in ('points','rebounds','assists','pra','minutes'):
            np.testing.assert_array_equal(np.sort(source[name],axis=0),np.sort(mixed[name],axis=0))

    def test_unknown_experience_is_not_fabricated(self):
        history=copy.deepcopy(self.history);history['debut_seasons']={}
        pp,_,_,_=profiles(history,self.slate,self.params)
        self.assertTrue(all(p['experience']=='unknown' for p in pp))
        self.assertTrue(all('unknown_experience' in p['prior']['kind'] for p in pp))
        self.assertTrue(all(p['evidence']['effective_sample_size']>0 for p in pp))

    def test_whole_game_block_challenger_keeps_recorded_stats_joint(self):
        sample=game_block(self.history_large,self.slate,self.pp,self.params,utc(self.slate['origin']),200,42)
        np.testing.assert_array_equal(sample['pra'],sample['points']+sample['rebounds']+sample['assists'])
        np.testing.assert_allclose(sample['minutes'].sum(axis=1),480)
        self.assertIn('not identity-specific',sample['conditioning'])

    def test_metric_comparison_requires_identical_dates_and_field(self):
        sample=simulate(self.slate,self.pp,self.teams,self.ot,200,42)
        value=evaluate(sample,self.slate,self.pp)
        result=paired_intervals([value],[value])
        self.assertEqual(result['paired']['crps']['repair_minus_original'],0)
        changed=dict(value,date='2026-11-03')
        with self.assertRaises(ValueError):paired_intervals([value],[changed])
        slate=copy.deepcopy(self.slate);slate['outcomes'].pop(sample['player_ids'][0])
        with self.assertRaises(ValueError):evaluate(sample,slate,self.pp)
        self.assertEqual(aggregate([value])['slates'],1)

    def test_original_sources_and_actual_time_registration_preserved(self):
        registration=verify_registration()
        self.assertFalse(registration['future_outcomes_accessed'])
        self.assertFalse(registration['scheduled_task_created'])
        self.assertGreater(min(registration['prospective_evaluation']),max(registration['prospective_development']))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'code.json'
            lock_code(path)
            self.assertEqual(load_sealed(path)['registration_sha256'],registration['sha256'])


class AvailableArchiveTest(unittest.TestCase):
    def fixture(self):
        boxes=[]
        for pid,name,team in ((1,'A',10),(2,'B',10),(3,'C',20)):
            boxes.append(dict(person_id=pid,first_name=name,family_name=name,name_i=name,team_id=team,minutes='0:00',
                              points=2 if pid==1 else 0,rebounds_total=1 if pid==1 else 0,assists=1 if pid==2 else 0,
                              field_goals_attempted=1 if pid in (1,3) else 0,field_goals_made=1 if pid==1 else 0,
                              free_throws_attempted=1 if pid in (1,3) else 0,free_throws_made=0))
        specifications=[('Made Shot',1,10,'A Layup (2 PTS) (B 1 AST)',2),
                        ('',3,20,'C BLOCK (1 BLK)',0),
                        ('Missed Shot',3,20,'MISS C Layup',2),
                        ('Rebound',1,10,'A REBOUND (Off:0 Def:1)',0),
                        ('Free Throw',1,10,'MISS A Free Throw 1 of 2',0),
                        ('Free Throw',3,20,'MISS C Free Throw 2 of 2',0)]
        events=[dict(order_index=i,action_number=5 if i<2 else i+5,period=1,clock='PT11M00.00S',
                     action_type=kind,person_id=pid,team_id=team,player_name=str(pid),description=text,shot_value=value,sub_type='')
                for i,(kind,pid,team,text,value) in enumerate(specifications)]
        return events,boxes

    def test_related_action_rows_are_not_false_conflicts_or_lost_credit(self):
        events,boxes=self.fixture()
        result=audit_game(events,[],boxes)
        self.assertTrue(result['event_agreement'])
        self.assertEqual(result['free_throw_misses']['missed_nonfinal_or_technical_not_a_live_rebound_chance'],1)
        self.assertEqual(result['free_throw_misses']['missed_ordinary_final_potentially_reboundable'],1)
        self.assertFalse(result['stint_agreement'])

    def test_ambiguous_assist_name_is_not_resolved_by_guessing(self):
        events,boxes=self.fixture()
        another=dict(boxes[1],person_id=4,assists=0)
        result=audit_game(events,[],boxes+[another])
        self.assertFalse(result['event_agreement'])
        self.assertEqual(result['event_issues']['ambiguous_assist_name'],1)

    def test_conflicting_unique_record_id_fails(self):
        events,boxes=self.fixture()
        events.append(dict(events[0],person_id=3))
        self.assertGreater(audit_game(events,[],boxes)['event_issues']['conflicting_order_index'],0)


if __name__=='__main__':
    unittest.main()
