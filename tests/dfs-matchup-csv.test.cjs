const {test}=require('node:test'),assert=require('node:assert/strict');
const m=require('../shared/dfs-matchup-csv.js'),tournament=require('../shared/dfs-tournament.js');
const now=Date.now(),date=new Date(now),season=date.getUTCFullYear()-(date.getUTCMonth()<2?1:0),stamp=new Date(now-60000).toISOString().slice(0,16).replace('T',' ');
const teams='ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' ');
// Synthetic two-header provider shape; not licensed data or measured predictive results.
function csv(pos='WR',fpg=20){return ['TEAM DETAILS,TEAM DETAILS,TEAM DETAILS,TEAM DETAILS,FP','Rank,Name,POS,G,FP/G',',,,,10',...teams.map((v,i)=>`${i+1},${v},vs. ${pos},4,${v==='MIA'?fpg:10}`),`Exported from Data Suite 2.0 on ${stamp} UTC,,,,`].join('\n');}
function dataset(pos='WR',fpg=20,name='fantasy-points-allowed-wr.csv'){return m.parse(csv(pos,fpg),{name,season,now});}
function player(){return {id:'1',name:'Synthetic WR',position:'WR',team:'BUF',opponent:'MIA',matched:true,unavailable:false,projection:12,projectionSource:'dfs-current-season-empirical-v1',projectionSeason:season,upside:{source:tournament.UPSIDE_SOURCE,n:4,currentGames:4,season,asOf:new Date(now-60000).toISOString(),value:17}};}
test('provider parsing preserves full team coverage, league mean and exact WR split categories',()=>{
 assert.equal(Object.keys(dataset().records).length,32);assert.equal(dataset().records.MIA.metrics['FP/G'],20);
 assert.equal(dataset('WR',20,'fantasy-points-allowed-wr (1).csv').kind,'outside');assert.equal(dataset('WR',20,'fantasy-points-allowed-wr (2).csv').kind,'slot');
 assert.throws(()=>dataset('WR',20,'renamed.csv'),/original WR filenames/);assert.equal(dataset('QB',20,'qb.csv').kind,'qb');
});
test('CSV rejects missing/duplicate teams, absent league average, malformed numbers and quoted input',()=>{
 const s=csv();for(const broken of [s.replace('2,ATL,vs. WR,4,10','2,ARI,vs. WR,4,10'),s.replace('2,ATL,vs. WR,4,10\n',''),s.replace(',,,,10\n',''),s.replace('2,ATL,vs. WR,4,10','2,ATL,vs. WR,4,'),s+'\n"broken'])assert.throws(()=>m.parse(broken,{name:'fantasy-points-allowed-wr.csv',season,now}));
});
test('current season assertion and export time enforce missing/stale/future gates',()=>{
 assert.throws(()=>m.parse(csv(),{name:'fantasy-points-allowed-wr.csv',season:season-1,now}),/current NFL season/);
 assert.throws(()=>m.parse(csv(),{name:'fantasy-points-allowed-wr.csv',season,now:now+37*3600000}),/36 hours/);
 assert.throws(()=>m.parse(csv(),{name:'fantasy-points-allowed-wr.csv',season,now:now-3600000}),/future/);
 assert.throws(()=>m.parse(csv().split('\n').slice(0,-1).join('\n'),{name:'fantasy-points-allowed-wr.csv',season,now}),/timestamp/);
});
test('optional matchup scenario changes tournament rank while preserving baseline, spread and availability',()=>{
 const p=player(),annotated=m.annotate(p,{wr:dataset()},{enabled:true,now});
 assert.equal(annotated.projection,12);assert.deepEqual(annotated.upside,p.upside);assert.equal(annotated.matchupResearch.scenario,24);assert.equal(tournament.objective(annotated),29);assert.equal(tournament.objective(p),17);
 const other=m.annotate({...p,id:'2',opponent:'ATL',projection:15,upside:{...p.upside,value:20}},{wr:dataset()},{enabled:true,now});assert.equal(tournament.objective(other),20);assert.ok(tournament.objective(annotated)>tournament.objective(other));
 assert.equal(m.annotate(p,{wr:dataset()},{enabled:false,now}).matchupResearch,undefined);
 assert.equal(m.annotate({...p,unavailable:true},{wr:dataset()},{enabled:true,now}).matchupResearch,undefined);
 assert.equal(m.annotate({...p,incumbentLocked:true},{wr:dataset()},{enabled:true,now}).matchupResearch,undefined);
 assert.equal(m.annotate({...p,projectionSeason:season-1},{wr:dataset()},{enabled:true,now}).matchupResearch,undefined);
});
test('stale or misbound scenario cannot influence tournament objective',()=>{
 const p=m.annotate(player(),{wr:dataset()},{enabled:true,now});assert.equal(m.adjustment(p,now+37*3600000),0);
 for(const change of [{opponent:'ATL'},{projection:99},{projectionSeason:season-1},{unavailable:true},{matched:false},{incumbentLocked:true}])assert.equal(m.adjustment({...p,...change},now),0);
 assert.equal(m.adjustment({...p,matchupResearch:{...p.matchupResearch,scenario:999}},now),0);
});
test('outside and slot evidence are separate and do not replace overall WR ranking',()=>{
 const p=m.annotate(player(),{outside:dataset('WR',40,'fantasy-points-allowed-wr (1).csv'),slot:dataset('WR',2,'fantasy-points-allowed-wr (2).csv')},{enabled:true,now});
 assert.equal(p.matchupResearch,undefined);assert.equal(tournament.objective(p),17);assert.equal(p.matchupContext.length,2);assert.match(p.matchupContext.join(' '),/Player alignment unknown/);
});
test('evaluation labels experimental scenario and counts valid upside independently',()=>{
 const p=m.annotate(player(),{wr:dataset()},{enabled:true,now}),x=tournament.evaluate([p]);
 assert.equal(x.objective.value,29);assert.equal(x.objective.basis,'sum-of-experimental-opponent-scenarios');assert.equal(x.objective.coverage.provided,1);assert.equal(x.objective.coverage.missing,0);
 const captain={...p,slot:'CPT'};assert.equal(tournament.evaluate([captain],{contest:'showdown'}).objective.value,43.5);
});
