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
