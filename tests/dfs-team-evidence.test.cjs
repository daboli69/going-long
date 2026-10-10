'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {buildScenario}=require('../shared/dfs-team-evidence.js');
const injuries=require('../shared/football-injuries.js');
const stamp='2026-10-03T18:00:00Z',now=Date.parse('2026-10-03T19:00:00Z'),sourceURL='https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_2026.csv';
const games=[{gameId:'BUF@MIA|2026-10-04T17:00:00Z',home:'MIA',away:'BUF',kickoff:'2026-10-04T17:00:00Z'}];
const clone=x=>JSON.parse(JSON.stringify(x));
function fixture(){
 const profiles={},players={},teams={};
 for(const t of ['BUF','MIA']){
  teams[t]=[0,2,4].map((n,i)=>({team:t,gameId:`2026_0${i+1}_${t}_${t==='BUF'?'TEN':'IND'}`,opponent:t==='BUF'?'TEN':'IND',kickoff:`2026-09-${13+7*i}T17:00:00Z`,rushTDs:n,recTDs:0,qualifyingTDs:n}));
  for(let i=0;i<2;i++){const id=t+i;profiles[id]={id,name:'Fixture '+id,team:t,position:'RB',last_game:'2026-09-27',stats:{rush_tds:{status:'ready',mean:i?.5:1},rec_tds:{status:'ready',mean:0},pass_tds:{status:'ready',mean:99}}};players[id]={player_id:id,team:t,position:'RB',season:2026,games:3,last_game:'2026-09-27',rush_attempts:10,targets:0};}
 }
 return {teamSnapshot:{schemaVersion:1,season:2026,generatedAt:stamp,retrievedAt:stamp,releaseUpdatedAt:stamp,sourceURL,sourceSha256:'a'.repeat(64),teams},profiles,context:{season:2026,generated_at:stamp,scopes:{2026:{players}}},injuryContext:{fresh:true,generatedAt:stamp,byIdentity:new Map()},generatedAt:stamp,now,makeModel:(p,key)=>({model:p.stats[key],projMean:p.stats[key]?.mean}),injuries,slateGames:games};
}
test('team budgets use every independently verified teammate with an other-scorer reserve',()=>{
 const f=fixture(),s=buildScenario(f),b=s.teams.BUF;
 assert.equal(s.version,'team-budget-v1');assert.deepEqual(b.counts,[0,2,4]);assert.equal(b.n,3);assert.equal(b.mean,2);assert.equal(b.denominator,2);assert.equal(b.allVerifiedPlayerMean,1.5);assert.equal(b.playerShares.BUF0,.5);assert.equal(b.playerShares.BUF1,.25);assert.equal(b.otherShare,.25);
 assert.match(s.limitations.join(' '),/independent/);assert.match(s.limitations.join(' '),/not calibrated/);assert.equal(s.provenance.sourceSha256,'a'.repeat(64));
});
test('selected/imported/excluded subsets cannot change the all-team denominator',()=>{
 const f=fixture(),p=f.profiles.BUF0,row={...p,profileId:p.id,matched:true,unavailable:false,tdMean:1,gameId:games[0].gameId,opponent:'MIA',kickoff:games[0].kickoff};
 const all=buildScenario(f),subset=buildScenario({...f,pool:[row],excludedIds:['BUF1']});
 assert.deepEqual(subset.teams.BUF.playerMeans,all.teams.BUF.playerMeans);assert.equal(subset.teams.BUF.denominator,all.teams.BUF.denominator);
 assert.throws(()=>buildScenario({...f,pool:[{...row,tdMean:3}]}),/independently verified/);
 assert.throws(()=>buildScenario({...f,pool:[{...row,opponent:'TEN'}]}),/independently verified/);
 assert.throws(()=>buildScenario({...f,pool:[row,row]}),/independently verified/);
});
test('modelled player totals above the team mean scale shares without fabricated tail mass',()=>{
 const f=fixture();f.profiles.BUF1.stats.rush_tds.mean=3;const b=buildScenario(f).teams.BUF;
 assert.equal(b.denominator,4);assert.equal(b.playerShares.BUF0,.25);assert.equal(b.otherShare,0);assert.deepEqual(b.counts,[0,2,4]);
});
test('QB passing touchdowns never enter the denominator; rushing and receiving do',()=>{
 const f=fixture();f.profiles.BUF0.position='QB';f.context.scopes[2026].players.BUF0.position='QB';f.profiles.BUF0.stats.rec_tds.mean=.2;
 const fakeInjuries={...injuries,starterEligibility:()=>({known:true,eligible:true})};const b=buildScenario({...f,injuries:fakeInjuries}).teams.BUF;
 assert.equal(b.playerMeans.BUF0,1.2);assert.equal(b.allVerifiedPlayerMean,1.7);
 delete f.profiles.BUF0.stats.rec_tds;const missing=buildScenario({...f,injuries:fakeInjuries}).teams.BUF;assert.equal(missing.playerMeans.BUF0,1);assert.deepEqual(missing.missingQBReceiving,['BUF0']);
 const backup=buildScenario({...f,injuries:{...fakeInjuries,starterEligibility:()=>({known:false,eligible:true})}});assert.equal(backup.teams.BUF.playerMeans.BUF0,undefined);
});
test('missing/ambiguous current identities and non-ready counts never receive guessed TD shares',()=>{
 for(const mutate of [f=>{delete f.context.scopes[2026].players.BUF0;},f=>{f.context.scopes[2026].players.BUF0.team='TEN';},f=>{f.profiles.BUF0.stats.rec_tds.status='insufficient';},f=>{f.profiles.BUF0.last_game='2026-08-01';}]){
  const f=fixture();mutate(f);const row={...f.profiles.BUF0,profileId:'BUF0',matched:true,tdMean:1};assert.throws(()=>buildScenario({...f,pool:[row]}),/independently verified/);
 }
 const f=fixture();f.profiles.duplicate={...f.profiles.BUF0,id:'duplicate'};assert.throws(()=>buildScenario(f),/ambiguous/);
 const missing=fixture();for(const p of Object.values(missing.profiles))p.stats.rec_tds.status='missing';assert.throws(()=>buildScenario(missing),/no uniquely verified/);
});
test('confirmed unavailable teammates are excluded by the existing availability adapter',()=>{
 const f=fixture();f.injuryContext.byIdentity.set('BUF|'+injuries.normalize(f.profiles.BUF0.name),{status:'IR'});const b=buildScenario(f).teams.BUF;
 assert.equal(b.playerMeans.BUF0,undefined);assert.equal(b.allVerifiedPlayerMean,.5);assert.equal(b.otherShare,.75);
});
test('verified starting QB remains eligible with zero carries/targets or missing usage, without loosening other positions',()=>{
 for(const missingUsage of [false,true]){
  const f=fixture();f.profiles.BUF0.position='QB';f.profiles.BUF0.stats.rush_tds.mean=0;
  if(missingUsage)delete f.context.scopes[2026].players.BUF0;
  else Object.assign(f.context.scopes[2026].players.BUF0,{position:'QB',rush_attempts:0,targets:0});
  const verified={...injuries,starterEligibility:()=>({known:true,eligible:true})};
  const p=f.profiles.BUF0,row={...p,profileId:p.id,matched:true,unavailable:false,tdMean:0,gameId:games[0].gameId,opponent:'MIA',kickoff:games[0].kickoff};
  const b=buildScenario({...f,injuries:verified,pool:[row]}).teams.BUF;
  assert.equal(b.playerMeans.BUF0,0);assert.match(b.playerRoleSources.BUF0,/verified starting quarterback/);
  assert.throws(()=>buildScenario({...f,injuries:{...verified,starterEligibility:()=>({known:false,eligible:true})},pool:[row]}),/independently verified/);
 }
 const invalid=fixture();invalid.profiles.BUF0.position='QB';invalid.context.scopes[2026].players.BUF0.position='QB';invalid.context.scopes[2026].players.BUF0.team='TEN';
 const blocked=buildScenario({...invalid,injuries:{...injuries,starterEligibility:()=>({known:true,eligible:true})}});assert.equal(blocked.teams.BUF.playerMeans.BUF0,undefined);
 const rb=fixture();Object.assign(rb.context.scopes[2026].players.BUF0,{rush_attempts:0,targets:0});assert.equal(buildScenario(rb).teams.BUF.playerMeans.BUF0,undefined);
});
test('all-zero evidence uses a zero-share division guard without inventing team touchdowns',()=>{
 const f=fixture();for(const rows of Object.values(f.teamSnapshot.teams))for(const r of rows){r.rushTDs=0;r.qualifyingTDs=0;}for(const p of Object.values(f.profiles))p.stats.rush_tds.mean=0;
 const b=buildScenario(f).teams.BUF;assert.equal(b.mean,0);assert.equal(b.allVerifiedPlayerMean,0);assert.equal(b.denominator,1);assert.equal(b.zeroMeanGuard,true);assert.deepEqual(b.counts,[0,0,0]);assert.equal(b.playerShares.BUF0,0);
});
test('stale/future receipt/model/role/injury data, wrong source and insufficient samples fail closed',()=>{
 const mutations=[f=>{f.teamSnapshot.generatedAt='2026-10-04T00:00:00Z';},f=>{f.teamSnapshot.releaseUpdatedAt='2026-09-01T00:00:00Z';},f=>{f.teamSnapshot.retrievedAt='2026-10-03T17:00:00Z';},f=>{f.teamSnapshot.sourceURL='https://example.com/stats.csv';},f=>{f.teamSnapshot.sourceSha256='bad';},f=>{f.teamSnapshot.schemaVersion=2;},f=>{f.teamSnapshot.season=2025;},f=>{f.generatedAt='2026-10-04T00:00:00Z';},f=>{f.context.generated_at='2026-10-01T00:00:00Z';},f=>{f.injuryContext.fresh=false;},f=>{f.injuryContext.generatedAt='2026-10-04T00:00:00Z';},f=>{f.teamSnapshot.teams.BUF.pop();}];
 for(const mutate of mutations){const f=fixture();mutate(f);assert.throws(()=>buildScenario(f),/team evidence/);}
});
test('duplicate/conflicting source games, invalid teams/counts and uncompleted chronology are rejected',()=>{
 for(const mutate of [r=>{r.gameId='2026_01_TEN_IND';},r=>{r.opponent='BUF';},r=>{r.qualifyingTDs=10;},r=>{r.rushTDs=-1;},r=>{r.kickoff='2026-10-04T17:00:00Z';},r=>{r.kickoff='bad';}]){const f=fixture();mutate(f.teamSnapshot.teams.BUF[0]);assert.throws(()=>buildScenario(f),/team evidence/);}
 const f=fixture();f.teamSnapshot.teams.BUF[1]=clone(f.teamSnapshot.teams.BUF[0]);assert.throws(()=>buildScenario(f),/duplicate/);
 assert.throws(()=>buildScenario({...fixture(),slateGames:[...games,...games]}),/duplicate/);
});
test('actual official artifact and inline attachProjection match the primary evidence pool across the main slate',t=>{
 // Unmodified public pregame blobs from the recorded production commit.
 // Rolling postgame updates cannot supply historical decision-time inputs.
 const frozen=JSON.parse(require('node:zlib').gunzipSync(require('node:fs').readFileSync(require('node:path').join(__dirname,'fixtures/dfs-pregame-20261004.json.gz'))));
 assert.equal(frozen.sourceCommit,'3def63b3ba9381b356632ceeaf14dd9b869841ca');
 const values={};for(const [name,entry] of Object.entries(frozen.files)){assert.equal(require('node:crypto').createHash('sha256').update(entry.raw).digest('hex'),entry.sha256);values[name]=JSON.parse(entry.raw);}
 const snapshot=values.dfs_team_touchdowns,h=values.history.betting,c=values.football_context,roster=values.nfl_roster,inj=values.injury_context;
 // Decision clock follows all frozen input times; original freshness and
 // pregame assertions remain mandatory. No timestamps are backdated.
 const inputTimes=[snapshot.generatedAt,h.generated_at,c.generated_at,roster.generated_at,inj.generated_at].map(Date.parse);
 assert.ok(inputTimes.every(Number.isFinite),'each public input needs a valid timestamp');
 const liveNow=Math.max(...inputTimes)+60000,injuryContext=injuries.createContext(roster,h.profiles,liveNow,inj);
 const slate=h.games.nfl.filter(g=>g.kickoff.startsWith('2026-10-04')&&Date.parse(g.kickoff)>=Date.parse('2026-10-04T17:00:00Z')&&Date.parse(g.kickoff)<Date.parse('2026-10-04T23:00:00Z')).map(g=>({...g,gameId:g.id}));
 assert.ok(slate.length&&slate.every(g=>Date.parse(g.kickoff)>liveNow),'the parity check must remain pregame');
 const vm=require('node:vm'),path=require('node:path'),source=require('../research/today-ranking/collect.cjs').openSource(path.resolve(__dirname,'..'),new Date(liveNow).toISOString());t.after(()=>source.dom.window.close());
 source.w.dfsFixture={history:h,context:c,injuryContext};
 vm.runInContext("BET.history=dfsFixture.history;BET.context=dfsFixture.context;BET.injuryContext=dfsFixture.injuryContext;globalThis.dfsInlineModel=(profile,market,salary)=>attachProjection({player:profile.name,team:profile.team,market,kickoff:salary.kickoff,eventTeams:[salary.team,salary.opponent],source:'projection'},buildProfileIndex(BET.history));",source.context);
 const makeModel=source.w.dfsInlineModel;
 // Salary-free model rows verify parity with the existing evidence adapter;
 // these are not a fabricated DraftKings pool or a contest-valid lineup.
 const modelRows=Object.values(h.profiles).flatMap(p=>{const g=slate.find(g=>g.home===p.team||g.away===p.team);return g?[{...p,gameId:g.gameId,kickoff:g.kickoff,opponent:g.home===p.team?g.away:g.home}]:[];});
 const pool=require('../shared/dfs-evidence.js').buildPool(modelRows,{profiles:h.profiles,context:c,injuryContext,generatedAt:h.generated_at,now:liveNow,injuries,makeModel,bonusProbability:()=>0,points:require('../shared/football-dfs.js').projectedPoints});
 const s=buildScenario({teamSnapshot:snapshot,profiles:h.profiles,context:c,injuryContext,generatedAt:h.generated_at,now:liveNow,injuries,slateGames:slate,makeModel,pool});
 assert.equal(Object.keys(s.teams).length,slate.length*2);for(const t of Object.values(s.teams)){assert.ok(t.n>=3);assert.ok(t.denominator>=t.allVerifiedPlayerMean);assert.ok(t.otherShare>=0&&t.otherShare<=1);assert.ok(Object.values(t.playerShares).reduce((sum,p)=>sum+p,0)<=1+1e-12);}
 assert.ok(pool.some(p=>p.matched&&!p.unavailable));
});
