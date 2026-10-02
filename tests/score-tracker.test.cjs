const test=require('node:test');
const assert=require('node:assert/strict');
const tracker=require('../shared/score-tracker.js');
const now=Date.parse('2026-10-01T12:00:00Z');
const kickoff=Date.parse('2026-10-02T20:00:00Z');
function observation(extra={}){
 return {scoreVersion:'v1',sport:'nfl',profileId:'player-1',player:'Player One',team:'BUF',opp:'NYJ',home:'BUF',away:'NYJ',
  kickoff,market:'rush_yds',side:'Over',line:50.5,score:78,probability:.61,scoreProbability:.5,projection:65,
  modelAt:now-1000,contextAt:now-2000,componentCoverage:.9,confidence:{value:73,label:'Moderate'},
  components:{projection:{value:65,percentile:80,weight:.45,label:'Projection',evidence:'Published projection'}},...extra};
}
function captured(extra={}){return tracker.freeze(tracker.create(),observation(extra),now);}
function result(extra={}){return {status:'win',value:65,source:'published-player-game-result',resultAt:kickoff+3600000,game:'NYJ at BUF',profileId:'player-1',home:'BUF',away:'NYJ',kickoff,...extra};}
test('first observation survives changed score and reload without input mutation',()=>{
 const input=tracker.create(),snap=observation();const original=JSON.stringify(snap);
 const first=tracker.freeze(input,snap,now);assert.equal(first.added,true);assert.deepEqual(input,tracker.create());assert.equal(JSON.stringify(snap),original);
 snap.components.projection.value=99;first.record.components.projection.value=1;
 assert.equal(first.ledger.records[first.record.key].components.projection.value,65);
 const second=tracker.freeze(first.ledger,observation({score:95,projection:99}),now+1000);
 assert.equal(second.added,false);assert.equal(second.record.score,78);assert.equal(second.record.projection,65);
 assert.deepEqual(tracker.restore(JSON.parse(JSON.stringify(first.ledger))),first.ledger);
 assert.equal(second.record.selectionBias,'user-selected');assert.equal(second.record.probability,.61);assert.equal(second.record.scoreProbability,.5);
});
test('identity includes frozen line, version and game, but not bookmaker',()=>{
 const a=captured({quote:{book:'A',line:50.5,odds:-110,updatedAt:now-500}});
 const b=tracker.freeze(a.ledger,observation({quote:{book:'B',line:50.5,odds:105,updatedAt:now}}),now);
 assert.equal(b.added,false);assert.equal(b.record.quote.book,'A');
 const c=tracker.freeze(b.ledger,observation({line:51.5}),now);assert.equal(c.added,true);
 const d=tracker.freeze(c.ledger,observation({scoreVersion:'v2'}),now);assert.equal(d.added,true);
 const e=tracker.freeze(d.ledger,observation({opp:'MIA',away:'MIA'}),now);assert.equal(e.added,true);
 assert.equal(tracker.summary(e.ledger).total,4);assert.equal(tracker.summary(e.ledger).games,2);
});
test('missing prices allowed; nested and top-level private fields discarded',()=>{
 const a=captured({secret:'hidden',confidence:{value:73,label:'Moderate',private:'hidden'},components:{projection:{value:65,evidence:'Public',token:'hidden'}}});
 assert.equal(a.added,true);assert.equal(a.record.quote,undefined);
 assert.equal(JSON.stringify(a.ledger).includes('hidden'),false);
});
test('snapshot preserves cohort inputs and explicitly labels old prices',()=>{
 const a=captured({cohortSize:20,rank:2,sampleGames:12,currentGames:3,pushProbability:.1,quote:{book:'A',line:50.5,odds:-110,updatedAt:now-300001}});
 assert.equal(a.added,true);assert.equal(a.record.quoteFreshAtFreeze,false);assert.equal(a.record.cohortSize,20);assert.equal(a.record.rank,2);assert.equal(a.record.pushProbability,.1);
 assert.equal(captured({quote:{book:'A',line:50.5,odds:-110,updatedAt:now-300000}}).record.quoteFreshAtFreeze,true);
 assert.equal(captured({pushProbability:.5}).added,false);
 assert.equal(captured({cohortSize:1,rank:2}).added,false);
 assert.equal(captured({sampleGames:-1}).added,false);
 const edited=JSON.parse(JSON.stringify(a.ledger));edited.records[a.record.key].quoteFreshAtFreeze=true;
 assert.equal(tracker.restore(edited).records[a.record.key].quoteFreshAtFreeze,false);
});
test('independent evidence timestamps are frozen and cannot use future source updates',()=>{
 const evidenceAt={learning:now-2000,injury:now-1000,roster:now};
 const a=captured({evidenceAt});assert.equal(a.added,true);
 evidenceAt.injury=now+1000;
 assert.equal(a.record.evidenceAt.injury,new Date(now-1000).toISOString());
 assert.deepEqual(tracker.restore(JSON.parse(JSON.stringify(a.ledger))),a.ledger);
 for(const key of ['learning','injury','roster'])assert.equal(captured({evidenceAt:{[key]:now+1}}).added,false);
 assert.equal(captured({evidenceAt:{injury:null}}).added,false);
 const b=tracker.freeze(a.ledger,observation({evidenceAt:{injury:now}}),now);
 assert.equal(b.record.evidenceAt.injury,a.record.evidenceAt.injury);
});
test('American quoted prices exclude magnitudes below 100',()=>{
 for(let odds=1;odds<100;odds++)for(const signed of [odds,-odds]){
  assert.equal(captured({quote:{book:'A',line:50.5,odds:signed,updatedAt:now}}).added,false);
 }
 for(const odds of [-100,100,-110,150])assert.equal(captured({quote:{book:'A',line:50.5,odds,updatedAt:now}}).added,true);
});
test('reject invalid contracts and future or postgame capture',()=>{
 for(const extra of [{kickoff:now},{kickoff:now-1},{modelAt:now+1},{modelAt:null},{contextAt:now+1},{line:NaN},{score:101},{score:-1},{profileId:''},{home:'NYJ'},{probability:1.1},{market:'unknown'},{side:'Under'},
  {quote:{book:'A',line:50.5,odds:-110,updatedAt:now+1}},{quote:{book:'A',line:51,odds:-110,updatedAt:now}}]){
  assert.equal(captured(extra).added,false,JSON.stringify(extra));
 }
 assert.equal(captured({market:'atd',side:'Yes',line:.5}).added,true);
 assert.equal(captured({market:'atd',side:'Yes',line:1.5}).added,false);
});
test('settlements require provenance and chronology and cannot overwrite prediction or result',()=>{
 const a=captured(),before=JSON.stringify(a.ledger);
 for(const [grade,at] of [[result(),now],[result({source:'manual'}),kickoff+7200000],[result({resultAt:kickoff-1}),kickoff+7200000],[result({resultAt:kickoff+8000000}),kickoff+7200000],
  [result({profileId:'different'}),kickoff+7200000],[result({status:'loss'}),kickoff+7200000],[result({value:null}),kickoff+7200000],[result({game:''}),kickoff+7200000]]){
  assert.equal(tracker.attachSettlement(a.ledger,a.record.key,grade,at).added,false);
 }
 const b=tracker.attachSettlement(a.ledger,a.record.key,result(),kickoff+7200000);
 assert.equal(b.added,true);assert.equal(JSON.stringify(a.ledger),before);assert.deepEqual(b.ledger.records,a.ledger.records);
 const c=tracker.attachSettlement(b.ledger,a.record.key,result({status:'void',value:null}),kickoff+8000000);
 assert.equal(c.added,false);assert.equal(c.settlement.status,'win');assert.ok(c.error);
 assert.deepEqual(tracker.restore(JSON.parse(JSON.stringify(b.ledger))),b.ledger);
 assert.deepEqual(tracker.summary(b.ledger),{total:1,settled:1,pending:0,games:1,bands:{'70-79':{count:1,settled:1,pending:0,win:1,loss:0,push:0,void:0}},selectionBias:'user-selected'});
});
test('push and void handling and score 100 band',()=>{
 const a=captured({score:100,line:65});assert.equal(a.record.band,'90+');
 assert.equal(tracker.attachSettlement(a.ledger,a.record.key,result({status:'push'}),kickoff+7200000).added,true);
 assert.equal(tracker.attachSettlement(a.ledger,a.record.key,result({status:'void',value:null}),kickoff+7200000).added,true);
});
test('settlement game identity must match with at most two minutes kickoff drift',()=>{
 const a=captured();
 for(const extra of [{home:'MIA'},{away:'MIA'},{kickoff:kickoff+120001},{kickoff:null},{playerSourceAt:kickoff-1},{sourceCheckedAt:kickoff+7200001}]){
  assert.equal(tracker.attachSettlement(a.ledger,a.record.key,result(extra),kickoff+7200000).added,false);
 }
 const b=tracker.attachSettlement(a.ledger,a.record.key,result({kickoff:kickoff+120000,playerSourceAt:kickoff+3000000,sourceCheckedAt:kickoff+3600000}),kickoff+7200000);
 assert.equal(b.added,true);assert.deepEqual(tracker.restore(b.ledger),b.ledger);
});
test('restore rejects corrupt keys, inconsistent chronology and invalid settlement',()=>{
 const a=captured();const key=a.record.key;
 const variants=[{version:2,records:{},settlements:{}},{version:1,records:[],settlements:{}}];
 for(const mutate of [l=>{l.records.bad=l.records[key];delete l.records[key];},l=>{l.records[key].score=Infinity;},l=>{l.records[key].frozenAt=new Date(kickoff).toISOString();},l=>{l.records[key].modelAt=new Date(now+1).toISOString();},l=>{l.settlements[key]={...result(),settledAt:new Date(now).toISOString()};},l=>{l.settlements.unknown={};}]){
  const ledger=JSON.parse(JSON.stringify(a.ledger));mutate(ledger);variants.push(ledger);
 }
 for(const ledger of variants)assert.equal(tracker.restore(ledger),null);
 assert.equal(tracker.summary(null),null);
});
test('capacity is explicit and never prunes saved records',()=>{
 let ledger=tracker.create();const base=captured().record;
 for(let i=0;i<tracker.CAPACITY;i++){
  const r={...base,profileId:`player-${i}`};
  const key=JSON.stringify([r.sport,r.profileId,r.home,r.away,r.kickoff,r.market,r.side,r.line,r.scoreVersion]);r.key=key;ledger.records[key]=r;
 }
 const response=tracker.freeze(ledger,observation({profileId:'overflow'}),now);
 assert.equal(response.added,false);assert.match(response.error,/capacity/i);assert.equal(Object.keys(response.ledger.records).length,tracker.CAPACITY);
 assert.equal(Object.keys(ledger.records).length,tracker.CAPACITY);
});
