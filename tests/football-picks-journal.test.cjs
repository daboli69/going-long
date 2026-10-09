'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const P=require('../shared/football-picks.js'),{fingerprint,validPickReceipt}=require('../shared/football-picks-snapshot.cjs');
const captured='2026-10-05T18:00:00Z',frozen='2026-10-05T18:01:00Z';
function play(extra={}){
 const row={kind:'prop',sport:'nfl',home:'NO',away:'ATL',team:'NO',player:'Receiver',profileId:'p',profileDate:'2026-09-27',kickoff:'2026-10-06T00:15:00Z',market:'rec_yds',side:'Over',line:50.5,projMean:65,projSd:20,prob:.6,push:0,n:12,book:'Book',odds:-110,dec:1+100/110,updatedAt:'2026-10-05T17:30:00Z',contract:'nfl-prop-contract',tracking_group:'going_picks_v3',model_cohort:'going-picks-v3',...extra};
 const e=P.assess(row,{now:Date.parse(captured),season:2026,historyAt:captured});
 row.provenance={model_source_sha256:'a'.repeat(64),picks_assessor_sha256:'b'.repeat(64),inputs:{'history.json':{sha256:'c'.repeat(64),generated_at:captured}}};
 row.picks_snapshot={...e,captured_at:captured,rank:1,source_inputs:row.provenance.inputs,candidate_sha256:fingerprint(row)};return row;
}
test('Picks receipt rejects changed line/model, future inputs and future capture',()=>{
 const row=play();assert.equal(validPickReceipt(row.picks_snapshot,row,row.provenance,frozen),true);
 for(const changed of [{...row,line:45.5},{...row,projMean:80}])assert.equal(validPickReceipt(row.picks_snapshot,changed,row.provenance,frozen),false);
 assert.equal(validPickReceipt({...row.picks_snapshot,captured_at:'2026-10-05T19:00:00Z'},row,row.provenance,frozen),false);
 const p=structuredClone(row.provenance);p.inputs['history.json'].generated_at='2026-10-05T19:00:00Z';assert.equal(validPickReceipt(row.picks_snapshot,row,p,frozen),false);
});
test('Picks forecasts retain first rating, use existing settlement and remain a distinct cohort',async()=>{
 const {freezePredictions,settlePredictions,selectTrackedPlays}=await import('../scripts/build_public_tracker.mjs'),records=[],row=play();
 assert.equal(selectTrackedPlays([row]).length,1);
 for(const [odds,dec,expected] of [[-500,1.2,1],[-501,1.1996,0],[-1200,1.083,0],[-110,1.909,1]])assert.equal(selectTrackedPlays([{...row,odds,dec}]).length,expected,`odds ${odds}: Picks follow the same -500 floor as every other tracked group`);assert.equal(freezePredictions(records,[row],frozen).length,1);const original=JSON.stringify(records[0]);
 assert.equal(freezePredictions(records,[play({prob:.9})],'2026-10-05T18:02:00Z').length,0);assert.equal(JSON.stringify(records[0]),original);
 assert.equal(records[0].payload.model_cohort,'going-picks-v3');assert.equal(records[0].payload.picks_snapshot.rating,35);
 const results={games:{g:{sport:'nfl',id:'g',home:'NO',away:'ATL',kickoff:row.kickoff,homeScore:20,awayScore:17}},players:{'p|2026-10-05':{rec_yds:60}},generated_at:'2026-10-06T04:00:00Z'};
 assert.equal(settlePredictions(records,results,'2026-10-06T04:00:00Z')[0].payload.status,'win');assert.equal(JSON.stringify(records[0]),original);
});
test('Unavailable price freezes the research case but never invents a $100 wager',async t=>{
 const {build}=await import('../scripts/build_public_tracker.mjs'),dir=await fs.mkdtemp(path.join(os.tmpdir(),'going-picks-test-')),output=path.join(dir,'tracker.json');
 t.after(()=>fs.rm(dir,{recursive:true,force:true}));const row=play({odds:null,dec:null});const snapshot=await build({output,now:frozen,plays:[row]});
 assert.equal(snapshot.records.filter(r=>r.kind==='prediction').length,0);assert.equal(snapshot.records.filter(r=>r.kind==='pick_research').length,1);
 const original=JSON.stringify(snapshot.records);const again=await build({output,now:'2026-10-05T18:02:00Z',plays:[row]});assert.equal(JSON.stringify(again.records),original);
});
test('Unpriced research receives an official outcome without becoming a wager',async()=>{
 const {settlePickResearch}=await import('../scripts/build_public_tracker.mjs'),row=play({odds:null,dec:null}),records=[{id:'research-1',kind:'pick_research',observed_at:frozen,payload:{contract:row.contract,sport:'nfl',home:'NO',away:'ATL',kickoff:row.kickoff,profile_id:'p',market:'rec_yds',side:'Over',line:50.5,picks_snapshot:row.picks_snapshot}}],before=JSON.stringify(records[0]);
 const results={games:{g:{sport:'nfl',id:'g',home:'NO',away:'ATL',kickoff:row.kickoff,homeScore:20,awayScore:17}},players:{'p|2026-10-05':{rec_yds:60}}};
 assert.equal(settlePickResearch(records,results,'2026-10-06T04:00:00Z')[0].payload.status,'win');assert.equal(settlePickResearch(records,results,'2026-10-06T05:00:00Z').length,0);assert.equal(JSON.stringify(records[0]),before);assert.equal(records.filter(r=>r.kind==='prediction').length,0);
});
test('v3 rating/spread/tier tampering is rejected; original v1 freezes are never converted',async()=>{
 const row=play();for(const patch of [{rating:99},{evidenceTier:5},{ratingDetail:{...row.picks_snapshot.ratingDetail,strength:1}}])assert.equal(validPickReceipt({...row.picks_snapshot,...patch},row,row.provenance,frozen),false);
 assert.equal(validPickReceipt(row.picks_snapshot,{...row,projSd:30},row.provenance,frozen),false);
 const legacy=play({tracking_group:'going_picks_v1',model_cohort:'going-picks-v1'});legacy.picks_snapshot={...legacy.picks_snapshot,version:'football-case-v1',rating:2};delete legacy.picks_snapshot.evidenceTier;delete legacy.picks_snapshot.ratingDetail;
 assert.equal(validPickReceipt(legacy.picks_snapshot,legacy,legacy.provenance,frozen),true);
 const {freezePredictions}=await import('../scripts/build_public_tracker.mjs'),records=[];freezePredictions(records,[legacy],frozen);const before=JSON.stringify(records[0]);freezePredictions(records,[row],frozen);
 assert.equal(records.length,2);assert.equal(JSON.stringify(records[0]),before);assert.equal(records[0].payload.picks_snapshot.rating,2);assert.equal(records[1].payload.picks_snapshot.rating,35);
 const {recordedEvidence}=await import('../apps/validation/evidence.mjs');assert.match(recordedEvidence(records[0].payload).join('\n'),/rating: 2\/5/);assert.match(recordedEvidence(records[1].payload).join('\n'),/rating: 35\/100/);
});

test('a frozen v2 receipt still validates under its own rule and cohort (v2 history is never reinterpreted)',()=>{
 const row=play(),v2={...row,tracking_group:'going_picks_v2',model_cohort:'going-picks-v2'};v2.picks_snapshot={...row.picks_snapshot,version:'football-case-v2'};
 assert.equal(validPickReceipt(v2.picks_snapshot,v2,v2.provenance,frozen),true);
 assert.equal(validPickReceipt({...v2.picks_snapshot,version:'football-case-v2'},{...v2,model_cohort:'going-picks-v3'},v2.provenance,frozen),false);
});
