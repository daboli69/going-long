'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('../shared/dfs-current-season.js'),E=require('../shared/dfs-evidence.js'),D=require('../shared/football-dfs.js'),S=require('../shared/dfs-sim.js');
const now=Date.parse('2026-10-11T20:00:00Z'),kickoff='2026-10-12T00:20:00Z';
const game=(year,week,date)=>({season:year,week,date,verified_start:true,attempts:20,pass_yds:200,pass_tds:1,rush_yds:-2,rush_tds:0,rec_yds:0,rec_tds:0,receptions:0});
function profile(){return {id:'fixture',name:'Fixture QB',position:'QB',team:'BAL',last_game:'2025-12-27',games:[game(2025,8,'2025-10-26'),game(2025,17,'2025-12-27'),{...game(2026,4,'2026-10-04'),attempts:9,verified_start:false,pass_yds:63}]};}
function row(){return {id:'dk1',name:'Fixture QB',position:'QB',team:'BAL',opponent:'ATL',kickoff,game:'BAL@ATL',showdownRole:'FLEX',salary:8800};}
function options(){return {profiles:{fixture:profile()},now,generatedAt:'2026-10-11T19:00:00Z',context:{season:2026,generated_at:'2026-10-11T19:00:00Z'},injuryContext:{fresh:true,generatedAt:'2026-10-11T19:00:00Z',byIdentity:new Map()},injuries:{normalize:x=>x,starterEligibility:()=>({known:true,eligible:true}),availability:()=>({block:false,state:'available'})},allowPriorSeasonQB:true,makeModel:(p,k,s)=>{const model=C.model(p,k,{now,kickoff:s.kickoff,allowPriorSeasonQB:s.allowPriorSeasonQB});return {model,projMean:model.mean};},bonusProbability:C.bonusProbability,points:D.projectedPoints};}
test('negative yards retain real current-season starts and scoring deduction',()=>{
 const p=profile();p.games=[game(2026,3,'2026-09-24'),game(2026,4,'2026-10-05')];
 const m=C.model(p,'rush_yds',{now,kickoff,allowPriorSeasonQB:true});assert.equal(m.source,C.SOURCE);assert.equal(m.n,2);assert.equal(m.mean,-2);
 const d=C.distribution(p,{now,kickoff,points:D.projectedPoints});assert.equal(d.mean,11.8);
 const o=options();o.profiles.fixture=p;p.last_game='2026-10-05';const result=E.buildPool([row()],o)[0];assert.equal(result.unavailable,false);assert.equal(result.stats.rush_yds,-2);assert.equal(result.projection,11.8);
});
test('current-season samples always take priority; no mixed-year average',()=>{
 const p=profile();p.games.push(game(2026,3,'2026-09-24'),game(2026,2,'2026-09-20'));
 p.games[0].pass_yds=9999;
 const m=C.model(p,'pass_yds',{now,kickoff,allowPriorSeasonQB:true});assert.equal(m.source,C.SOURCE);assert.equal(m.mean,200);assert.equal(m.season_evidence.historical_games,0);
});
test('fallback uses only immediate previous-season verified starts with honest source and bonus',()=>{
 const p=profile();p.games.push({...game(2025,6,'2025-10-12'),verified_start:false,pass_yds:9999},game(2024,18,'2025-01-05'));
 const m=C.model(p,'pass_yds',{now,kickoff,allowPriorSeasonQB:true});assert.equal(m.source,C.QB_FALLBACK_SOURCE);assert.equal(m.sampleSeason,2025);assert.equal(m.n,2);assert.equal(m.mean,200);assert.equal(m.season_evidence.current_games,0);assert.equal(m.season_evidence.historical_games,2);assert.equal(C.bonusProbability({model:m},299.5),0);
 const d=C.distribution(p,{now,kickoff,allowPriorSeasonQB:true,points:D.projectedPoints});assert.equal(d.n,2);assert.equal(d.source,m.source);assert.match(d.definitions.floor,/prior-season 2025/);
});
test('default Classic and skill positions never enable historical fallback',()=>{
 assert.equal(C.model(profile(),'pass_yds',{now}).status,'unavailable');
 assert.equal(C.model({...profile(),position:'RB'},'rush_yds',{now,allowPriorSeasonQB:true}).status,'unavailable');
 const o=options();delete o.allowPriorSeasonQB;assert.equal(E.buildPool([row()],o)[0].unavailable,true);
 const r=row();delete r.showdownRole;assert.equal(E.buildPool([r],options())[0].unavailable,true);
});
test('confirmed starter fallback can clear old-last-start gate but not OUT, unknown or backup gates',()=>{
 const valid=E.buildPool([row()],options())[0];assert.equal(valid.unavailable,false);assert.equal(valid.projectionSource,C.QB_FALLBACK_SOURCE);assert.equal(valid.upside,null);assert.match(valid.evidence.join(' '),/2 verified 2025 starts/);
 for(const starter of [{known:false,eligible:false},{known:true,eligible:false}]){const o=options();o.injuries.starterEligibility=()=>starter;assert.equal(E.buildPool([row()],o)[0].unavailable,true);}
 for(const patch of [{csvOut:true},{injury:'OUT'}]){const o=options();o.injuries.availability=r=>({block:r.injury_status==='OUT',state:r.injury_status==='OUT'?'out':'available'});assert.equal(E.buildPool([{...row(),...patch}],o)[0].unavailable,true);}
 const stale=options();stale.generatedAt='2026-10-01T00:00:00Z';assert.equal(E.buildPool([row()],stale)[0].unavailable,true);
});
test('duplicate, invalid counts and one prior start cannot manufacture fallback',()=>{
 const p=profile();p.games.push({...p.games[0]});assert.equal(C.model(p,'pass_yds',{now,allowPriorSeasonQB:true}).status,'unavailable');
 for(const change of [{pass_tds:-1},{receptions:1.2},{pass_yds:NaN}]){const q=profile();Object.assign(q.games[0],change);assert.equal(C.model(q,'pass_yds',{now,allowPriorSeasonQB:true}).status,'unavailable');}
});
test('fallback does not revive archived cross-player covariance',()=>{
 const a={projectionSource:C.QB_FALLBACK_SOURCE,position:'QB',dfsRole:'QB',team:'BAL',opponent:'ATL'},b={projectionSource:C.QB_FALLBACK_SOURCE,position:'QB',dfsRole:'QB',team:'ATL',opponent:'BAL'};
 assert.equal(S.pairCorrelation(a,b,{cross_player:{'QB~QB':{r:.99}}}),0);
});
