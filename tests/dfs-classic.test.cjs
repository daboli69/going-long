const {test}=require('node:test');
const assert=require('node:assert/strict');
const dfs=require('../shared/dfs-classic.js');
// All names, salaries and projections below are synthetic test fixtures, not real contest recommendations.
const NOW='2026-10-04T16:00:00Z';
const HEADER='Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame';
function csvRow(id,position='RB',salary=5000,game='BUF@MIA 10/04/2026 01:00PM ET',team='BUF',name=`Fixture ${id}`){return [position,`${name} (${id})`,name,id,['QB','DST'].includes(position)?position:`${position}/FLEX`,salary,game,team,'10.2'].join(',');}
function csv(...rows){return [HEADER,...rows].join('\n');}
function fixture(counts={QB:3,RB:8,WR:10,TE:4,DST:4}){
 let id=1;const players=[];
 for(const [position,count] of Object.entries(counts))for(let i=0;i<count;i++){
  const game=i%2?'KC@DEN':'BUF@MIA',teams=game.split('@'),salary=position==='DST'?2500+i*100:position==='QB'?6500+i*100:4000+i*200;
  players.push({id:String(id++),name:`Fixture ${position} ${i}`,position,salary,team:teams[0],opponent:teams[1],gameId:game+'|2026-10-04T17:00:00.000Z',kickoff:'2026-10-04T17:00:00.000Z',sourceSalary:'draftkings-csv',matched:true,projection:position==='DST'?7+i/10:25-i,tdMean:position==='DST'?100:position==='QB'?i*.02:.8-i*.04});
 }
 return players;
}
test('strict official Classic import preserves salary, IDs, game set, ET kickoff and raw average',()=>{
 const parsed=dfs.parseCsv(csv(csvRow(1),csvRow(2,'DST',3000,'KC@DEN 10/04/2026 04:25PM ET','DEN')));
 assert.deepEqual(parsed.errors,[]);assert.equal(parsed.players[0].salary,5000);assert.equal(parsed.players[0].id,'1');assert.equal(parsed.players[0].avgPointsPerGame,10.2);assert.equal(parsed.players[0].kickoff,'2026-10-04T17:00:00.000Z');assert.equal(parsed.players[1].kickoff,'2026-10-04T20:25:00.000Z');assert.equal(parsed.slate.gameIds.length,2);assert.equal(parsed.slate.date,'2026-10-04');
});
test('winter ET conversion uses EST and CSV handles escaped names',()=>{
 const text=csv(csvRow(1,'WR',5000,'BUF@MIA 12/06/2026 01:00PM ET','BUF','Fixture "Quoted"').split(',').map((v,i)=>i===1||i===2?'"'+v.replace(/"/g,'""')+'"':v).join(','),csvRow(2,'DST',3000,'KC@DEN 12/06/2026 04:25PM ET','DEN'));
 const parsed=dfs.parseCsv(text);assert.deepEqual(parsed.errors,[]);assert.equal(parsed.players[0].kickoff,'2026-12-06T18:00:00.000Z');assert.equal(parsed.players[0].name,'Fixture "Quoted"');
});
test('name normalization preserves identifying suffixes',()=>{assert.equal(dfs.matchName('John Smith Jr.'),'johnsmithjr');assert.notEqual(dfs.matchName('John Smith'),dfs.matchName('John Smith Jr.'));});
test('malformed, duplicate, mixed and showdown imports fail closed rather than salvage rows',()=>{
 const other=csvRow(2,'DST',3000,'KC@DEN 10/04/2026 04:25PM ET','DEN');
 const bad=[csv(csvRow(1),csvRow(1),other),csv(csvRow(1,'RB','5000.5'),other),csv(csvRow(1,'RB','-5000'),other),csv(csvRow(1,'RB','5e3'),other),csv(csvRow(1,'RB',5000,'BUF@MIA','BUF'),other),csv(csvRow(1,'RB',5000,'BUF@MIA 02/30/2026 01:00PM ET'),other),csv(csvRow(1,'RB',5000,'BUF@MIA 10/04/2026 13:00PM ET'),other),csv(csvRow(1,'RB',5000,'BUF@MIA 10/04/2026 01:00PM ET','KC'),other),csv(csvRow(1,'CPT'),other),csv(csvRow(1).replace('RB/FLEX','FLEX'),other),csv(csvRow(1),csvRow(2,'DST',3000,'KC@DEN 10/05/2026 04:25PM ET','DEN')),csv(csvRow(1)),csv(csvRow(1),other+'extra'),csv(csvRow(1).replace('Fixture 1 (1)','"Unclosed'),other),HEADER.replace('ID,Roster','Name,Roster')+'\n'+csvRow(1)+'\n'+other];
 for(const text of bad){const result=dfs.parseCsv(text);assert.equal(result.players.length,0,text);assert.ok(result.errors.length,text);}
});
test('same-team conflicting kickoffs and duplicate athlete identity reject import',()=>{
 for(const text of [csv(csvRow(1),csvRow(2,'WR',5000,'BUF@MIA 10/04/2026 04:25PM ET')),csv(csvRow(1),csvRow(2,'RB',5000,'BUF@MIA 10/04/2026 01:00PM ET','BUF','Fixture 1'),csvRow(3,'DST',3000,'KC@DEN 10/04/2026 04:25PM ET','DEN'))])assert.ok(dfs.parseCsv(text).errors.length);
});
test('both modes satisfy every Classic position, salary, uniqueness and two-game rule',()=>{
 const pool=fixture();
 for(const mode of ['best','throne']){
  const result=dfs.optimize(pool,{mode,now:NOW});assert.equal(result.reason,null);assert.deepEqual(result.lineup.map(p=>p.slot),dfs.SLOTS);assert.ok(result.salaryUsed<=50000);assert.equal(result.salaryRemaining,50000-result.salaryUsed);assert.equal(new Set(result.lineup.map(p=>p.id)).size,9);assert.ok(new Set(result.lineup.map(p=>p.gameId)).size>=2);assert.ok(dfs.validateLineup(result.lineup,pool,{mode,now:NOW}).valid);assert.equal(result.tdMean,result.lineup.filter(p=>p.position!=='DST').reduce((sum,p)=>sum+p.tdMean,0));assert.equal(result.heuristic,true);
 }
});
test('TD objective counts multiple qualifying TDs, ignores DST TD input and QB passing fields',()=>{
 const pool=fixture();const qbs=pool.filter(p=>p.position==='QB');qbs.forEach(p=>{p.projection=30;p.tdMean=0;p.passTds=100;});qbs[1].tdMean=1.4;qbs[0].passingTdMean=100;
 const rb=pool.find(p=>p.position==='RB');rb.tdMean=2.4;rb.anytimeTdProbability=.5;
 const result=dfs.optimize(pool,{mode:'throne',now:NOW});assert.equal(result.lineup[0].id,qbs[1].id);assert.ok(result.lineup.some(p=>p.id===rb.id));assert.ok(result.tdMean<20);
});
test('strict eligibility excludes unmatched, unavailable, missing evidence and missing real salary',()=>{
 const pool=fixture();const bad=pool.slice(0,5).map((p,i)=>({...p,id:'bad'+i,name:'bad'+i,projection:1000,tdMean:100,...[{matched:false},{unavailable:true},{projection:NaN},{sourceSalary:undefined},{salary:5000.5}][i]}));
 const result=dfs.optimize([...pool,...bad],{mode:'throne',now:NOW});assert.ok(result.lineup.length===9);assert.ok(result.lineup.every(p=>!p.id.startsWith('bad')));
 const missing=pool.map(p=>({...p,tdMean:undefined}));assert.equal(dfs.optimize(missing,{mode:'throne',now:NOW}).lineup.length,0);assert.equal(dfs.optimize(missing,{mode:'best',now:NOW}).lineup.length,9);
});
test('locks reserve the exact duplicate-position slot and excludes survive rebuild',()=>{
 const pool=fixture(),rb=pool.filter(p=>p.position==='RB').at(-1),wr=pool.filter(p=>p.position==='WR').at(-1),excluded=pool.find(p=>p.position==='QB');
 const options={now:NOW,mode:'throne',lockedSlots:{2:rb.id,5:wr.id},excludedIds:[excluded.id]};const result=dfs.optimize(pool,options);
 assert.equal(result.lineup[2].id,rb.id);assert.equal(result.lineup[5].id,wr.id);assert.ok(result.lineup.every(p=>p.id!==excluded.id));assert.ok(dfs.validateLineup(result.lineup,pool,options).valid);
 assert.equal(dfs.optimize(pool,{...options,excludedIds:[rb.id]}).lineup.length,0);assert.equal(dfs.optimize(pool,{now:NOW,lockedSlots:{1:rb.id,2:rb.id}}).lineup.length,0);assert.equal(dfs.optimize(pool,{now:NOW,lockedSlots:{0:rb.id}}).lineup.length,0);
});
test('swap alternatives retain eight slots, salary and game eligibility; show actual deltas',()=>{
 const pool=fixture(),options={now:NOW,mode:'throne'},base=dfs.optimize(pool,options).lineup,result=dfs.alternatives(base,1,pool,options);
 assert.ok(result.alternatives.length);for(const alt of result.alternatives){base.forEach((p,i)=>{if(i!==1)assert.equal(alt.lineup[i].id,p.id);});assert.ok(dfs.validateLineup(alt.lineup,pool,options).valid);assert.equal(alt.salaryDelta,alt.player.salary-base[1].salary);assert.equal(alt.projectionDelta,alt.player.projection-base[1].projection);assert.ok(Math.abs(alt.tdMeanDelta-(alt.player.tdMean-base[1].tdMean))<1e-10);}
 assert.equal(dfs.alternatives(base,1,pool,{...options,lockedSlots:{1:base[1].id}}).alternatives.length,0);
});
test('independent validator catches forged salary, positions, identity duplicates and two teams from one game',()=>{
 const pool=fixture(),opts={now:NOW},lineup=dfs.optimize(pool,opts).lineup;
 assert.equal(dfs.validateLineup(lineup.map((p,i)=>i===0?{...p,salary:1}:p),pool,opts).valid,false);
 assert.equal(dfs.validateLineup(lineup.map((p,i)=>i===0?{...p,slot:'WR'}:p),pool,opts).valid,false);
 const sameGame=pool.map(p=>({...p,gameId:'BUF@MIA|2026-10-04T17:00:00.000Z',team:p.team==='BUF'?'BUF':'MIA',opponent:p.team==='BUF'?'MIA':'BUF'}));assert.equal(dfs.optimize(sameGame,opts).lineup.length,0);
 const dup=pool.map(p=>({...p,athleteId:'same'}));assert.equal(dfs.optimize(dup,opts).lineup.length,0);
 assert.equal(dfs.optimize([...pool,pool[0]],opts).lineup.length,0);
});
test('started players are unavailable to new generation; explicit incumbents stay in exact slots',()=>{
 const pool=fixture(),initial=dfs.optimize(pool,{now:NOW}).lineup,startedId=initial[1].id;
 const laterPool=pool.map(p=>p.id===startedId?{...p,kickoff:'2026-10-04T15:00:00.000Z',unavailable:true}:p),incumbent=initial.map(p=>p.id===startedId?{...p,kickoff:'2026-10-04T15:00:00.000Z',unavailable:true}:p);
 const fresh=dfs.optimize(laterPool,{now:NOW});assert.ok(fresh.lineup.every(p=>p.id!==startedId));
 const result=dfs.optimize(laterPool,{now:NOW,incumbentLineup:incumbent});assert.equal(result.lineup[1].id,startedId);assert.equal(dfs.alternatives(result.lineup,1,laterPool,{now:NOW,incumbentLineup:incumbent}).alternatives.length,0);
 assert.equal(dfs.optimize(laterPool,{now:NOW,incumbentLineup:incumbent,excludedIds:[startedId]}).lineup.length,0);
});
test('cheap evidence-backed candidates remain available when stars need salary relief',()=>{
 const pool=fixture();pool.forEach(p=>{if(p.position!=='DST')p.salary=9000;});
 for(const pos of ['RB','WR','TE']){const candidates=pool.filter(p=>p.position===pos);candidates.slice(-3).forEach(p=>{p.salary=3000;p.projection=2;p.tdMean=.1;});}
 const result=dfs.optimize(pool,{now:NOW,mode:'throne'});assert.equal(result.lineup.length,9);assert.ok(result.salaryUsed<=50000);assert.ok(result.lineup.some(p=>p.salary===3000));
});
test('representative 300-player pool search is bounded and returns a valid lineup',()=>{
 const pool=fixture({QB:32,RB:70,WR:140,TE:40,DST:18});pool.forEach((p,i)=>{p.projection=8+(i%21);p.tdMean=(i%17)/20;p.salary=2500+(i%46)*100;});
 const start=performance.now(),result=dfs.optimize(pool,{now:NOW,mode:'throne',beamWidth:400});assert.equal(result.lineup.length,9);assert.ok(dfs.validateLineup(result.lineup,pool,{now:NOW,mode:'throne'}).valid);assert.ok(performance.now()-start<15000,'Bounded 300-player search should finish within 15 seconds.');
});


test('tournament objective distinguishes observed upside from median without relaxing any roster rules',()=>{
 const pool=fixture();const first=pool.find(p=>p.position==='QB'),other=pool.filter(p=>p.position==='QB').at(-1);other.upside={value:75,source:'observed-partial-fantasy-residual-v1',n:12,currentGames:4,asOf:NOW};
 const best=dfs.optimize(pool,{mode:'best',now:NOW}),tournament=dfs.optimize(pool,{mode:'tournament',now:NOW});assert.equal(best.lineup[0].id,first.id);assert.equal(tournament.lineup[0].id,other.id);assert.ok(dfs.validateLineup(tournament.lineup,pool,{mode:'tournament',now:NOW}).valid);assert.equal(tournament.tournament.ownership.status,'unknown');assert.equal(tournament.tournament.objective.jointCeiling,'not-estimated');
 other.unavailable=true;assert.notEqual(dfs.optimize(pool,{mode:'tournament',now:NOW}).lineup[0].id,other.id);
});

test('the DraftKings Status column: IR/OUT players are marked unavailable and can never fill a slot; Q and blank are not blocked',()=>{
 const rows=[csvRow(1),csvRow(2),csvRow(3),csvRow(9,'DST',3000,'KC@DEN 10/04/2026 04:25PM ET','DEN')];
 const text=[HEADER+',Status',rows[0]+',OUT',rows[1]+',Q',rows[2]+',',rows[3]+','].join('\n');
 const parsed=dfs.parseCsv(text);assert.deepEqual(parsed.errors,[]);
 const by=Object.fromEntries(parsed.players.map(p=>[p.id,p]));
 assert.equal(by[1].csvOut,true);assert.equal(by[1].unavailable,true);assert.equal(by[2].csvOut,false);assert.equal(by[2].csvStatus,'Q');assert.equal(by[3].csvOut,false);
 const ir=dfs.parseCsv([HEADER+',Status',rows[0]+',IR',rows[3]+','].join('\n'));assert.equal(ir.players[0].csvOut,true);
});

test('measured and tournament builds report whether they differ from Best DFS instead of presenting duplicates',()=>{
 require('../shared/dfs-correlations.js');
 const pool=fixture().map(p=>({...p,distribution:undefined}));
 const best=dfs.optimize(pool,{mode:'best',now:NOW});assert.equal(best.vsBest,undefined,'best is the baseline');
 const flat=dfs.optimize(pool,{mode:'measured',now:NOW});
 assert.ok(flat.vsBest&&typeof flat.vsBest.same==='boolean'&&flat.vsBest.changed>=0);
 assert.equal(flat.vsBest.same,flat.vsBest.changed===0);
 // a wide-spread, slightly lower-mean player must be taken by the measured objective but not by Best DFS
 const wide=pool.map(p=>p.id==='13'?{...p,projection:p.projection-.3,distribution:{mean:p.projection-.3,sd:30,floor:0,median:p.projection,p90:p.projection+40,boom:.2}}:p);
 const m=dfs.optimize(wide,{mode:'measured',now:NOW}),b=dfs.optimize(wide,{mode:'best',now:NOW});
 assert.equal(m.vsBest.same,m.lineup.every(p=>b.lineup.some(q=>q.id===p.id)));
 const t=dfs.optimize(pool,{mode:'tournament',now:NOW});assert.ok(t.vsBest&&t.vsBest.same,'without observed spread the tournament objective falls back to projection and says it matches Best DFS');
});
test('measured objective charges a D/ST for facing the lineup\'s own offence only through the lineup variance',()=>{
 require('../shared/dfs-correlations.js');const sim=require('../shared/dfs-sim.js');
 const mk=(o)=>({sourceSalary:'draftkings-csv',matched:true,...o});
 const base=[mk({position:'QB',team:'B',opponent:'A',projection:20,distribution:{mean:20,sd:7}}),mk({position:'DST',team:'A',opponent:'B',projection:7})];
 sim.assignRoles(base);
 const paired=dfs.measuredMoments(base),apart=dfs.measuredMoments([base[0],{...base[1],team:'C',opponent:'D'}]);
 assert.equal(paired.mean,apart.mean);assert.ok(paired.sd<apart.sd);
});
