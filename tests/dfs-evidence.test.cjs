'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {buildPool,observedCounts}=require('../shared/dfs-evidence.js');
const dfs=require('../shared/football-dfs.js');
// Synthetic identity/projection fixtures only; no real DraftKings prices inferred.
const now=Date.parse('2026-10-03T17:00:00Z'),stamp='2026-10-03T15:00:00Z';
const player={id:'p',name:'Fixture Player Jr.',team:'BUF',position:'RB',last_game:'2026-09-27',games:[{season:2026,date:'2026-09-20',rush_tds:2,rec_tds:1},{season:2026,date:'2026-09-27',rush_tds:0,rec_tds:1}]};
const salary={id:'1',name:player.name,team:'BUF',opponent:'MIA',position:'RB',salary:5000,kickoff:'2026-10-04T17:00:00Z'};
const stats={pass_yds:0,pass_tds:0,rush_yds:80,rush_tds:1.2,rec_yds:20,rec_tds:.3,receptions:3};
function opts(patch={}){return {profiles:{p:player},generatedAt:stamp,now,context:{season:2026,generated_at:stamp,scopes:{2026:{players:{p:{player_id:'p',team:'BUF',season:2026,games:3,last_game:'2026-09-27',targets:8,rush_attempts:25,target_share:.2,rush_share:.7}}}}},injuryContext:{fresh:true,byIdentity:new Map()},injuries:{normalize:x=>x,starterEligibility:()=>({known:true,eligible:true}),availability:()=>({block:false})},makeModel:(p,key,s)=>({projMean:stats[key],model:{status:'ready',mean:stats[key]}}),bonusProbability:()=>0,points:dfs.projectedPoints,...patch};}
test('partial DraftKings scoring and qualifying TD count remain distinct from passing TDs/ATD/Score',()=>{
 const [p]=buildPool([salary],opts());assert.equal(p.unavailable,false);assert.equal(p.tdMean,1.5);assert.equal(p.projection,22);assert.equal(p.value,4.4);assert.match(p.evidence.join(' '),/current-season/);assert.deepEqual(p.counts.bins,[0,1,0,1]);
 const [q]=buildPool([{...salary,position:'QB'}],opts({profiles:{p:{...player,position:'QB'}},makeModel:(p,key)=>({projMean:{...stats,pass_tds:5,pass_yds:300}[key],model:{status:'ready'}})}));assert.equal(q.tdMean,1.5);assert.ok(q.projection>p.projection);assert.ok(!('goingScore' in q));
});
test('unmatched, ambiguous, suffix-different, wrong-team and wrong-position identities are never guessed',()=>{
 for(const [row,o] of [[{...salary,name:'Fixture Player'},opts()],[{...salary,team:'MIA'},opts()],[{...salary,position:'WR'},opts()],[salary,opts({profiles:{p:player,q:{...player,id:'q'}}})]]){const [p]=buildPool([row],o);assert.equal(p.matched,false);assert.equal(p.unavailable,true);assert.equal(p.projection,null);}
});
test('stale/future model data, old profile, missing current opportunity and incomplete models fail closed',()=>{
 for(const patch of [{generatedAt:'2026-10-01T00:00:00Z'},{generatedAt:'2026-10-04T00:00:00Z'},{profiles:{p:{...player,last_game:'2026-08-01'}}},{profiles:{p:{...player,last_game:null}}},{context:null},{makeModel:()=>({projMean:2,model:{status:'insufficient'}})}])assert.equal(buildPool([salary],opts(patch))[0].unavailable,true);
});
test('confirmed out and unknown/backup QB cannot become salary relief',()=>{
 assert.equal(buildPool([salary],opts({injuryContext:{fresh:true,byIdentity:new Map([['BUF|'+player.name,{}]])},injuries:{normalize:x=>x,availability:()=>({block:true,state:'out'})}}))[0].unavailable,true);
 for(const starter of [{known:false,eligible:true},{known:true,eligible:false}])assert.equal(buildPool([{...salary,position:'QB'}],opts({profiles:{p:{...player,position:'QB'}},injuries:{starterEligibility:()=>starter}}))[0].unavailable,true);
});
test('DST preserves explicit imported average, contributes zero qualifying TDs and invents no fallback',()=>{
 const [p]=buildPool([{...salary,position:'DST',avgPointsPerGame:7.5}],opts());assert.equal(p.projection,7.5);assert.equal(p.tdMean,0);assert.match(p.concerns[0],/no current DST matchup/);
 assert.equal(buildPool([{...salary,position:'DST',avgPointsPerGame:null}],opts())[0].unavailable,true);
});
test('observed multi-TD bins exclude future results and passing/defensive/return TDs, January preserves season',()=>{
 const p={games:[...player.games,{season:2026,date:'2026-10-04',rush_tds:5,rec_tds:5},{season:2025,date:'2025-12-28',rush_tds:2,rec_tds:0},{season:2026,date:'2026-09-13',rush_tds:0,rec_tds:0,pass_tds:8,atd:7}]};
 assert.deepEqual(observedCounts(p,now).bins,[1,1,0,1]);assert.equal(observedCounts(p,now).n,3);assert.equal(observedCounts(p,Date.parse('2027-01-01')).season,2026);
});

test('QB projections carry the measured turnover allowance; RB/WR/TE and DST are unchanged; the switch rolls it back',()=>{
 const E=require('../shared/dfs-evidence.js'),qbOpts=o=>opts({profiles:{p:{...player,position:'QB'}},...o}),qb={...salary,position:'QB'};
 const on=buildPool([qb],qbOpts())[0],off=buildPool([qb],qbOpts({adjustments:false}))[0],disabled=buildPool([qb],qbOpts({adjustments:{qbTurnovers:{...E.ADJUSTMENTS.qbTurnovers,enabled:false}}}))[0];
 assert.equal(E.ADJUSTMENTS.qbTurnovers.points,-.52);
 assert.ok(Math.abs(on.projection-(off.projection-.52))<1e-9&&on.projectionAdjustment===-.52&&on.projectionRaw===off.projection);
 assert.equal(off.projection,disabled.projection);assert.equal(off.projectionAdjustment,0);
 assert.match(on.concerns.join(' '),/interceptions and lost fumbles/);
 assert.equal(buildPool([salary],opts())[0].projection,22,'RB unchanged');
 assert.equal(buildPool([{...salary,position:'DST',avgPointsPerGame:7.5}],opts())[0].projection,7.5,'DST unchanged');
});
test('shiftDistribution moves every summary and the hidden sorted draws together and leaves the input intact',()=>{
 const E=require('../shared/dfs-evidence.js'),d={mean:10,sd:5,floor:3,p25:6,median:9,p75:13,p90:17,p95:20,boom:.1};Object.defineProperty(d,'sorted',{value:Float64Array.from([1,2,3]),enumerable:false});
 const s=E.shiftDistribution(d,-.5);assert.equal(s.mean,9.5);assert.equal(s.p90,16.5);assert.equal(s.sd,5);assert.equal(s.boom,.1);assert.deepEqual([...s.sorted],[.5,1.5,2.5]);assert.equal(d.mean,10);assert.equal(E.shiftDistribution(d,0),d);assert.equal(E.shiftDistribution(null,-1),null);
});
