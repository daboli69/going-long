import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import opportunity_shadow as shadow


def fixture():
    now = datetime(2026, 10, 14, 16, tzinfo=timezone.utc)
    ts = now.isoformat()
    config = json.loads((shadow.ROOT/'config/opportunity_shadow.json').read_text())
    games = [{'game_id':f'game{w}', 'season':2026, 'week':w, 'home':'BUF', 'away':'LA', 'kickoff':(now+timedelta(days=1+7*(w-6))).isoformat()} for w in range(6,11)]
    prior = [{'season':2026, 'week':w, 'game_id':f'prior{w}', 'team':'BUF', 'completed':True, 'kickoff':(now-timedelta(days=7*(6-w))).isoformat(), 'offense_snap_share':50, 'carries':10, 'targets':2, 'atd':int(w==3)} for w in range(1,6)]
    games += [{'game_id':r['game_id'],'season':2026,'week':r['week'],'home':'BUF','away':'LA','kickoff':r['kickoff'],'completed':True} for r in prior]
    policy=json.loads((shadow.ROOT/'config/calibration_policy.json').read_text()); spec=policy['markets']['atd']
    p = {'id':'p', 'name':'Player', 'team':'BUF', 'position':'RB', 'games':prior, 'stats':{'atd':{'family':'poisson','status':'ready','lambda':.5,'lambda_raw':.5/spec['params']['factor'],'calibration':{'method':spec['method'],'params':spec['params'],'version':policy['version']}}}}
    history = {'generated_at':ts, 'betting':{'generated_at':ts,'sources':{'nflreadpy':{'2026':'loaded'}},'profiles':{'p':p},'games':{'nfl':[{**g,'id':g['game_id']} for g in games]}}}
    roster = {'generated_at':ts, 'source_roster_at':ts,'source_injury_at':ts,'season':2026,'week':6,'injury_week':6,'players':[{'id':'p','team':'BUF','position':'RB','roster_status':'ACT'}]}
    injury = {'generated_at':ts,'source_content_at':ts,'source_roster_at':ts,'current_players':{'p':{'gsis_id':'p','team':'BUF','roster_status':'ACT','roster_week':6}},'current_reports':{}}
    return [history, {'generated_at':ts,'games':games}, injury, roster, config, now]


class CaptureTests(unittest.TestCase):
    def test_exact_probability_and_complete_exclusions(self):
        args=fixture(); args[3]['players'].append({'id':'new','team':'BUF','position':'WR','roster_status':'ACT'})
        out=shadow.build(*args); p=out['rows'][0]['probabilities']
        self.assertAlmostEqual(p['production'],1-shadow.math.exp(-.5))
        self.assertAlmostEqual(p['opportunity'],1-shadow.math.exp(-(.0310903241504231*10+.04425638973068786*2)))
        self.assertAlmostEqual(p['frequency_beta11'],2/7)
        self.assertEqual(out['exclusions'][0]['player_id'],'new')

    def test_stale_availability_never_clears(self):
        args=fixture(); args[2]['source_content_at']=(args[-1]-timedelta(hours=40)).isoformat()
        with self.assertRaises(ValueError): shadow.build(*args)

    def test_out_unknown_and_conflicting_team_block(self):
        for status in ['OUT','PS','']:
            args=fixture(); args[3]['players'][0]['roster_status']=status
            with self.assertRaises(ValueError): shadow.build(*args)
        args=fixture(); args[2]['current_players']['p']['team']='LA'
        with self.assertRaises(ValueError): shadow.build(*args)

    def test_prior_season_mutation_does_not_change_challenger(self):
        args=fixture(); original=shadow.build(*args)['rows'][0]['probabilities']['opportunity']
        args[0]['betting']['profiles']['p']['games'].append({'season':2025,'carries':999999})
        self.assertEqual(shadow.build(*args)['rows'][0]['probabilities']['opportunity'],original)

    def test_traded_stint_and_too_few_games(self):
        args=fixture(); rows=args[0]['betting']['profiles']['p']['games']; rows[2]['team']='LA'
        with self.assertRaises(ValueError): shadow.build(*args)

    def test_receipt_missing_duplicate_or_in_game_blocks(self):
        for field,value in [('team',None),('kickoff','bad'),('completed',False),('offense_snap_share',None),('carries',True),('atd',None),('week',6)]:
            args=fixture(); args[0]['betting']['profiles']['p']['games'][0][field]=value
            with self.assertRaises(ValueError): shadow.build(*args)
        args=fixture(); args[0]['betting']['profiles']['p']['games'][0]['kickoff']=(args[-1]-timedelta(hours=1)).isoformat()
        with self.assertRaises(ValueError): shadow.build(*args)
        args=fixture(); rows=args[0]['betting']['profiles']['p']['games']; rows.append(copy.deepcopy(rows[0]))
        with self.assertRaises(ValueError): shadow.build(*args)

    def test_complete_week_cannot_be_reduced_to_unstarted_games(self):
        args=fixture(); args[1]['games'].append({'game_id':'early','season':2026,'week':6,'home':'PIT','away':'KC','kickoff':(args[-1]-timedelta(hours=1)).isoformat()})
        # Entire week6 is skipped; week7 cannot borrow week6 availability.
        with self.assertRaises(ValueError): shadow.build(*args)

    def test_missing_week_duplicate_game_and_team_rejected(self):
        args=fixture(); args[1]['games']=[g for g in args[1]['games'] if g['week']!=10]
        with self.assertRaises(ValueError): shadow.build(*args)
        args=fixture(); args[1]['games'].append(copy.deepcopy(args[1]['games'][0]))
        with self.assertRaises(ValueError): shadow.build(*args)
        args=fixture(); args[1]['games'].append({**args[1]['games'][0],'game_id':'different'})
        with self.assertRaises(ValueError): shadow.build(*args)

    def test_capture_immutable_and_reject_definition_change(self):
        args=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'data').mkdir(); output=root/'captures'
            for name,doc in zip(['history.json','nfl_betting.json','injury_context.json','nfl_roster.json'],args): (root/'data'/name).write_text(json.dumps(doc))
            path,created=shadow.capture(root,output,args[-1]); self.assertTrue(created); old=path.read_bytes()
            self.assertFalse(shadow.capture(root,output,args[-1]+timedelta(minutes=1))[1]); self.assertEqual(path.read_bytes(),old)
            manifest=shadow.sealed(output/'experiment.json'); manifest['config']['version']='changed'; (output/'experiment.json').unlink(); shadow.write_once(output/'experiment.json',manifest)
            with self.assertRaises(ValueError): shadow.capture(root,output,args[-1])

    def test_initial_late_capture_refused(self):
        args=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'data').mkdir()
            for name,doc in zip(['history.json','nfl_betting.json','injury_context.json','nfl_roster.json'],args): (root/'data'/name).write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'missed'): shadow.capture(root,root/'captures',args[-1]+timedelta(days=2))
            self.assertFalse((root/'captures').exists())

    def test_write_once_is_exclusive_and_tamper_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'receipt.json'; shadow.write_once(path,{'a':1})
            with self.assertRaises(FileExistsError): shadow.write_once(path,{'a':2})
            data=json.loads(path.read_text()); data['payload']['a']=2; path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): shadow.sealed(path)

    def test_unrostered_id_cannot_bypass_shared_gate(self):
        args=fixture(); args[0]['betting']['profiles']['p']['id']='unrostered'
        with self.assertRaisesRegex(ValueError,'identities'): shadow.build(*args)

    def test_exact_historical_schedule_receipt(self):
        for field,value in [('game_id','wrong'),('team','KC'),('kickoff','2026-09-01T00:00:00Z')]:
            args=fixture(); args[0]['betting']['profiles']['p']['games'][0][field]=value
            with self.assertRaises(ValueError): shadow.build(*args)

    def test_calibration_not_applied_twice_and_unknown_method_rejected(self):
        args=fixture(); out=shadow.build(*args)
        self.assertAlmostEqual(out['rows'][0]['probabilities']['production'],1-shadow.math.exp(-.5))
        args[0]['betting']['profiles']['p']['stats']['atd']['calibration']['method']='platt'
        with self.assertRaises(ValueError): shadow.build(*args)

    def test_missing_opener_in_odds_schedule_cannot_allow_late_capture(self):
        args=fixture()
        args[0]['betting']['games']['nfl'].append({'id':'missing-opener','season':2026,'week':6,'home':'PIT','away':'KC','kickoff':(args[-1]-timedelta(hours=1)).isoformat()})
        with self.assertRaisesRegex(ValueError,'snapshots disagree'): shadow.build(*args)

    def test_reference_kickoff_conflict_blocks_capture(self):
        args=fixture(); args[0]['betting']['games']['nfl'][0]['kickoff']=(args[-1]+timedelta(hours=4)).isoformat()
        with self.assertRaisesRegex(ValueError,'receipts disagree'): shadow.build(*args)


if __name__=='__main__': unittest.main()
