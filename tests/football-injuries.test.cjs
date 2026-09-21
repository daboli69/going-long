const {test}=require('node:test');
const assert=require('node:assert/strict');
const injuries=require('../shared/football-injuries.js');

const generatedAt='2026-09-20T12:00:00Z';
const now=Date.parse('2026-09-20T18:00:00Z');
const model=(mean=100)=>({family:'lognormal',status:'ready',mean,sd:mean/5,mu_log:4.5,sigma_log:.2,nonpositive:[],n:12});
const context=(players,profiles={})=>injuries.createContext({generated_at:generatedAt,players},profiles,now);

test('questionable designation lowers the mean and widens relative uncertainty',()=>{
 const ctx=context([{name:'Ladd Example',team:'LAC',pos:'WR',injury_status:'Questionable',injury_body_part:'Chest',depth_chart_order:1}]);
 const result=injuries.adjustModel({model:model(),name:'Ladd Example',team:'LAC',position:'WR',market:'rec_yds',context:ctx});
 assert.equal(result.model.mean,88);
 assert.ok(result.model.sd>20);
 assert.equal(result.injury.state,'questionable');
 assert.equal(result.injury.bodyPart,'Chest');
 assert.equal(result.injury.projectionScale,.88);
 assert.match(result.injury.reason,/Questionable availability adjustment -12%/);
});

test('confirmed out player is unavailable rather than presented as a fresh projection',()=>{
 const ctx=context([{name:'Starting Back',team:'A',pos:'RB',injury_status:'Out',depth_chart_order:1}]);
 const result=injuries.adjustModel({model:model(70),name:'Starting Back',team:'A',position:'RB',market:'rush_yds',context:ctx});
 assert.equal(result.model.status,'unavailable');
 assert.equal(result.model.mean,null);
 assert.equal(result.injury.blockRecommendation,true);
 assert.match(result.injury.reason,/removed/);
});

test('only the verified next healthy depth-chart player receives a capped role boost',()=>{
 const players=[
  {name:'Starting Back',team:'A',pos:'RB',injury_status:'Out',depth_chart_order:1},
  {name:'Next Back',team:'A',pos:'RB',injury_status:null,depth_chart_order:2},
  {name:'Third Back',team:'A',pos:'RB',injury_status:null,depth_chart_order:3},
 ];
 const profiles={starter:{name:'Starting Back',team:'A',stats:{rush_yds:model(100)}}};
 const ctx=context(players,profiles);
 const next=injuries.adjustModel({model:model(40),name:'Next Back',team:'A',position:'RB',market:'rush_yds',context:ctx});
 const third=injuries.adjustModel({model:model(20),name:'Third Back',team:'A',position:'RB',market:'rush_yds',context:ctx});
 assert.equal(next.model.mean,52);
 assert.equal(next.injury.roleBoost.players[0],'Starting Back');
 assert.equal(next.injury.projectionScale,1.3);
 assert.equal(third.model.mean,20);
 assert.equal(third.injury,null);
});

test('stale roster data is disclosed and never changes a projection',()=>{
 const stale=injuries.createContext({generated_at:'2026-09-17T00:00:00Z',players:[{name:'Injured Player',team:'A',pos:'WR',injury_status:'Questionable'}]}, {}, now);
 const result=injuries.adjustModel({model:model(80),name:'Injured Player',team:'A',position:'WR',market:'rec_yds',context:stale});
 assert.equal(result.model.mean,80);
 assert.equal(result.injury.stale,true);
 assert.equal(result.injury.applied,false);
});

test('questionable replacement is not treated as a healthy workload recipient',()=>{
 const players=[
  {name:'Starting Back',team:'A',pos:'RB',injury_status:'Out',depth_chart_order:1},
  {name:'Next Back',team:'A',pos:'RB',injury_status:'Questionable',depth_chart_order:2},
 ];
 const profiles={starter:{name:'Starting Back',team:'A',stats:{rush_yds:model(100)}}};
 const result=injuries.adjustModel({model:model(40),name:'Next Back',team:'A',position:'RB',market:'rush_yds',context:context(players,profiles)});
 assert.equal(result.model.mean,35.2);
 assert.equal(result.injury.roleBoost,null);
});

test('only the first available quarterback is starter-eligible',()=>{
 const players=[{name:'QB One',team:'A',pos:'QB',depth_chart_order:1},{name:'QB Two',team:'A',pos:'QB',depth_chart_order:2}];let ctx=context(players);
 assert.equal(injuries.starterEligibility({name:'QB One',team:'A',position:'QB',context:ctx}).eligible,true);
 const backup=injuries.starterEligibility({name:'QB Two',team:'A',position:'QB',context:ctx});assert.equal(backup.known,true);assert.equal(backup.eligible,false);assert.match(backup.reason,/behind QB One/);
 players[0].injury_status='Out';ctx=context(players);assert.equal(injuries.starterEligibility({name:'QB Two',team:'A',position:'QB',context:ctx}).eligible,true);
});

test('stale depth data does not guess which quarterback starts',()=>{
 const ctx=injuries.createContext({generated_at:'2026-09-17T00:00:00Z',players:[{name:'QB Two',team:'A',pos:'QB',depth_chart_order:2}]},{},now),result=injuries.starterEligibility({name:'QB Two',team:'A',position:'QB',context:ctx});
 assert.equal(result.known,false);assert.equal(result.eligible,true);assert.match(result.reason,/not inferred/);
});

test('official no-auth injury evidence applies a body-part cohort instead of a fixed status guess',()=>{
 const evidence={
  current_reports:{'LAC|laddexample':{name:'Ladd Example',team:'LAC',position:'WR',body_part:'hip',primary_injury:'Hip',report_status:'Questionable',practice_status:'Limited Participation in Practice'}},
  effects:{'WR|hip|questionable|rec_yds':{position:'WR',body_part:'hip',status:'questionable',market:'rec_yds',sample:31,scale:.82,confidence:'moderate'}},
 };
 const ctx=injuries.createContext({generated_at:generatedAt,players:[{name:'Ladd Example',team:'LAC',pos:'WR',depth_chart_order:1}]},{},now,evidence);
 const result=injuries.adjustModel({model:model(),name:'Ladd Example',team:'LAC',position:'WR',market:'rec_yds',context:ctx});
 assert.equal(result.model.mean,82);assert.equal(result.injury.bodyPart,'Hip');assert.equal(result.injury.historicalEffect.sample,31);assert.match(result.injury.reason,/Historical hip\/questionable cohort -18% \(n=31, moderate\)/);
});

test('vacated WR work is distributed by current target and snap role with QB tendency evidence',()=>{
 const players=[{name:'Starting Wideout',team:'A',pos:'WR',injury_status:'Out',depth_chart_order:1},{name:'Usage Leader',team:'A',pos:'WR',depth_chart_order:2},{name:'Depth Only',team:'A',pos:'WR',depth_chart_order:3}];
 const profiles={starter:{name:'Starting Wideout',team:'A',stats:{rec_yds:model(30)}}},evidence={current_players:{
  'A|startingwideout':{role_order:1,snap_share:.8,target_share:.25},'A|usageleader':{role_order:2,snap_share:.8,target_share:.20},'A|depthonly':{role_order:3,snap_share:.4,target_share:.05},
 },qb_tendencies:{A:{qb_name:'QB One',targets:60,target_rate_by_position:{WR:.62}}}};
 const ctx=injuries.createContext({generated_at:generatedAt,players},profiles,now,evidence),leader=injuries.adjustModel({model:model(40),name:'Usage Leader',team:'A',position:'WR',market:'rec_yds',context:ctx}),depth=injuries.adjustModel({model:model(40),name:'Depth Only',team:'A',position:'WR',market:'rec_yds',context:ctx});
 assert.ok(leader.model.mean>depth.model.mean);assert.match(leader.injury.reason,/20% current target share/);assert.match(leader.injury.reason,/QB One targets WRs on 62%/);
});

test('supported current blitz and QB target splits can bound replacement receiving work',()=>{
 const players=[{name:'Starting Wideout',team:'A',pos:'WR',injury_status:'Out',depth_chart_order:1},{name:'Replacement',team:'A',pos:'WR',depth_chart_order:2}],profiles={starter:{name:'Starting Wideout',team:'A',stats:{rec_yds:model(40)}}},evidence={current_players:{'A|startingwideout':{role_order:1,snap_share:.9,target_share:.3},'A|replacement':{role_order:2,snap_share:.7,target_share:.15}},qb_tendencies:{A:{qb_name:'QB One',targets:70,supported_for_model:true,target_rate_by_position:{WR:.6},targets_per_dropback_by_position:{WR:.5},blitz_splits:{blitz:{dropbacks:30,target_rate_by_position:{WR:.8}},non_blitz:{dropbacks:70,target_rate_by_position:{WR:.4}}}}},defense_scheme:{B:{charted_dropbacks:80,blitz_rate:.5,supported_for_model:true}}};
 const ctx=injuries.createContext({generated_at:generatedAt,players},profiles,now,evidence),result=injuries.adjustModel({model:model(100),name:'Replacement',team:'A',position:'WR',market:'rec_yds',opponent:'B',context:ctx});
 assert.equal(result.injury.roleBoost.schemeFactor,1.1);assert.ok(Math.abs(result.model.mean-111)<1e-9);assert.match(result.injury.reason,/B blitz mix changes the supported WR target tendency by 10%/);
});
