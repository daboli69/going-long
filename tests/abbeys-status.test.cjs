'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {currentStatus}=require('../research/abbeys/status.cjs');
const now='2026-10-10T20:00:00Z';
function schedule(){return {season:2026,generated_at:'2026-10-10T03:00:00Z',games:[
  {game_id:'2026_05_ATL_NO',season:2026,week:5,away:'ATL',home:'NO',kickoff:'2026-10-09T00:15:00Z'},
  {game_id:'2026_05_PHI_JAX',season:2026,week:5,away:'PHI',home:'JAX',kickoff:'2026-10-11T13:30:00Z'},
  {game_id:'2026_05_BUF_LA',season:2026,week:5,away:'BUF',home:'LA',kickoff:'2026-10-13T00:15:00Z'},
  {game_id:'2026_06_ATL_NO',season:2026,week:6,away:'ATL',home:'NO',kickoff:'2026-10-18T17:00:00Z'}]};}
test('current week uses Sunday/Monday schedule; missing capture explicitly distinguishes manual opportunity and missed research origin',()=>{
  const s=currentStatus(schedule(),[{season:2026,week:4}],now);
  assert.equal(s.week,5);assert.equal(s.status,'not-frozen');assert.equal(s.registeredOrigin,'2026-10-08T12:15:00.000Z');assert.equal(s.captureDeadline,'2026-10-11T13:30:00Z');assert.match(s.reason,/not been captured or published/);assert.match(s.reason,/no scheduled holdout catch-up/);
});
test('started Sunday week cannot be backfilled; Monday current week persists through game completion window',()=>{
  const source=schedule();source.generated_at='2026-10-12T20:00:00Z';
  const s=currentStatus(source,[],'2026-10-13T02:00:00Z');assert.equal(s.week,5);assert.match(s.reason,/cannot be backfilled/);
  assert.equal(currentStatus(source,[{season:2026,week:5}],'2026-10-13T02:00:00Z').status,'frozen');
});
test('stale, future or missing schedule receipt does not invent current-week status',()=>{
  for(const generated_at of [null,'2026-10-08T00:00:00Z','2026-10-11T00:00:00Z']){
    const s=currentStatus({...schedule(),generated_at},[],now);assert.equal(s.status,'unavailable');assert.equal(s.week,undefined);
  }
});
