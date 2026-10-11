const {test}=require('node:test');
const assert=require('node:assert/strict');
const dfs=require('../shared/dfs-classic.js');
const research=require('../shared/dfs-tournament.js');
// Synthetic construction evidence only: these are not backtest returns.
const now='2026-10-11T16:00:00Z';
function pool(){
 let id=0;return ['QB','RB','RB','WR','WR','WR','TE','RB','DST','WR','WR'].map((position,i)=>({id:String(++id),name:'Fixture '+id,position,salary:4000,team:i===8?'KC':'BUF',opponent:i===8?'DEN':'MIA',gameId:i===8?'KC@DEN':'BUF@MIA',kickoff:'2026-10-11T17:00:00Z',sourceSalary:'draftkings-csv',matched:true,unavailable:false,projection:i>=9?19:20,tdMean:.2,ownership:i>=9?1:25,ownershipSource:'classic-salary-model'}));
}
const options={mode:'tournament',now,beamWidth:3000,_compare:true};
const score=ps=>ps.reduce((s,p)=>s+research.objective(p),0);
test('historical ownership changes generated roster only within explicit score budget; projection inputs unchanged',()=>{
 const players=pool(),before=JSON.stringify(players),baseline=dfs.optimize(players,options);
 const result=dfs.optimize(players,{...options,tournamentPolicy:{ownership:true,lossPct:2}});
 assert.equal(result.lineup.length,9);assert.ok(dfs.validateLineup(result.lineup,players,{...options,tournamentPolicy:{ownership:true,lossPct:2}}).valid);
 assert.ok(result.historicalSelection.selectedOwnership<research.ownershipSum(baseline.lineup));
 assert.ok(score(result.lineup)>=score(baseline.lineup)*.98-1e-9);
 assert.equal(JSON.stringify(players),before);
 const zero=dfs.optimize(players,{...options,tournamentPolicy:{ownership:true,lossPct:0}});
 assert.equal(score(zero.lineup),score(baseline.lineup));
 assert.equal(zero.historicalSelection.selectedOwnership,research.ownershipSum(baseline.lineup));
});
test('small candidate search matches exhaustive legal enumeration and handles worker serialization',()=>{
 const players=pool(),reference=dfs.optimize(players,options),floor=score(reference.lineup)*.98;
 const all=[];for(let a=0;a<players.length;a++)for(let b=a+1;b<players.length;b++){
  const group=players.filter((_,i)=>i!==a&&i!==b),remaining=[...group],lineup=[];
  for(const slot of dfs.SLOTS){const i=remaining.findIndex(p=>p.position===slot||(slot==='FLEX'&&['RB','WR','TE'].includes(p.position)));if(i<0)break;lineup.push(remaining.splice(i,1)[0]);}
  if(dfs.validateLineup(lineup,players,options).valid&&score(lineup)>=floor)all.push(lineup);
 }
 const result=dfs.optimize(structuredClone(players),structuredClone({...options,tournamentPolicy:{ownership:true,lossPct:2}}));
 assert.equal(result.historicalSelection.selectedOwnership,Math.min(...all.map(research.ownershipSum)));
});
test('missing, invalid or wrong-source ownership fails closed instead of inventing zero',()=>{
 for(const change of [{ownership:null},{ownership:NaN},{ownership:-1},{ownership:101},{ownershipSource:'observed'},{ownership:undefined}]){
  const players=pool();Object.assign(players[9],change);
  assert.equal(dfs.optimize(players,{...options,tournamentPolicy:{ownership:true,lossPct:2}}).lineup.length,0);
  assert.equal(dfs.optimize(players,options).lineup.length,9);
 }
});
test('user construction rules enforce exact-game stack, bringback and D/ST exclusions',()=>{
 const players=pool();players[7].team='MIA';players[7].opponent='BUF';
 const policy={ownership:true,lossPct:5,stack:2,bringback:true,avoidDst:true};
 const result=dfs.optimize(players,{...options,tournamentPolicy:policy});
 assert.equal(result.lineup.length,9);assert.deepEqual(research.constructionErrors(result.lineup,policy),[]);
 const mismatch=result.lineup.map(p=>p.team==='MIA'?{...p,gameId:'wrong'}:p);
 assert.match(research.constructionErrors(mismatch,policy).join(' '),/return player/);
 players[7].unavailable=true;
 assert.equal(dfs.optimize(players,{...options,tournamentPolicy:policy}).lineup.length,0);
});
test('locks, exclusions, unavailable athletes and started games remain authoritative with history enabled',()=>{
 const players=pool();players[9].unavailable=true;
 const opts={...options,tournamentPolicy:{ownership:true,lossPct:5},lockedSlots:{3:'4'},excludedIds:['11']};
 const result=dfs.optimize(players,opts);assert.equal(result.lineup.length,9);assert.equal(result.lineup[3].id,'4');assert.ok(!result.lineup.some(p=>['10','11'].includes(p.id)));
 players[10].kickoff=now;const another=dfs.optimize(players,{...options,tournamentPolicy:{ownership:true,lossPct:5}});assert.ok(!another.lineup.some(p=>p.id==='11'));
});
test('history settings cannot change Best, Measured or Throne objectives and malformed policies reject',()=>{
 const players=pool();for(const mode of ['best','measured','throne']){
  const baseline=dfs.optimize(players,{...options,mode}),result=dfs.optimize(players,{...options,mode,tournamentPolicy:{ownership:true,lossPct:5,stack:2}});
  assert.deepEqual(result.lineup,baseline.lineup);assert.equal(result.historicalSelection,null);
 }
 for(const policy of [null,{}])assert.equal(research.policyErrors(policy).length,0);
 assert.equal(dfs.optimize(players,{...options,tournamentPolicy:null}).lineup.length,9);
 for(const policy of [{lossPct:-1},{lossPct:6},{lossPct:NaN},{stack:3},{ownership:'true'},[]])assert.ok(research.policyErrors(policy).length);
});
test('seeded small randomized slates match exhaustive ownership optimum under score and salary constraints',()=>{
 let seed=47;const rnd=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
 for(let trial=0;trial<20;trial++){
  const players=pool().map(p=>({...p,projection:12+Math.round(rnd()*15),ownership:Math.round(rnd()*50),salary:3500+Math.round(rnd()*25)*100}));
  const all=[];for(let a=0;a<players.length;a++)for(let b=a+1;b<players.length;b++){
   const remaining=players.filter((_,i)=>i!==a&&i!==b),lineup=[];
   for(const slot of dfs.SLOTS){const i=remaining.findIndex(p=>p.position===slot||(slot==='FLEX'&&['RB','WR','TE'].includes(p.position)));if(i<0)break;lineup.push(remaining.splice(i,1)[0]);}
   if(dfs.validateLineup(lineup,players,options).valid)all.push(lineup);
  }
  const max=Math.max(...all.map(score)),floor=max*.95,eligible=all.filter(p=>score(p)>=floor-1e-9);
  const result=dfs.optimize(players,{...options,tournamentPolicy:{ownership:true,lossPct:5}});
  assert.equal(result.historicalSelection.referenceScore,max,'trial '+trial);
  assert.equal(result.historicalSelection.selectedOwnership,Math.min(...eligible.map(research.ownershipSum)),'trial '+trial);
 }
});
test('swap candidates honor ownership preference, score budget and construction rules',()=>{
 const players=pool(),opts={...options,tournamentPolicy:{ownership:true,lossPct:2,stack:2}},result=dfs.optimize(players,opts);
 const swaps=dfs.alternatives(result.lineup,3,players,opts);assert.deepEqual(swaps.errors,[]);
 for(const row of swaps.alternatives){assert.ok(score(row.lineup)>=result.historicalSelection.scoreFloor-1e-9);assert.ok(dfs.validateLineup(row.lineup,players,opts).valid);}
 for(let i=1;i<swaps.alternatives.length;i++)assert.ok(research.ownershipSum(swaps.alternatives[i-1].lineup)<=research.ownershipSum(swaps.alternatives[i].lineup));
});
