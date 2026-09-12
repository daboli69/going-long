const {test}=require('node:test');const assert=require('node:assert/strict');
test('React performance uses only prospective eligible contracts and leaves empty results empty',async()=>{
 const {summarize}=await import('../apps/validation/metrics.mjs');assert.equal(summarize([]).bets,0);
 const p={id:'p',event:'e',selection:'s',side:'Over',observed_at:'2026-09-10T12:00:00Z',kickoff:'2026-09-10T17:00:00Z',odds:2.2,probability:.5,ev:.1,odds_band:'2.01–3.00',actionable:true};
 const rows=[{kind:'prediction',payload:p},{kind:'prediction',payload:{...p,id:'duplicate'}},{kind:'settlement',payload:{prediction_id:'p',status:'win',observed_at:'2026-09-11T12:00:00Z'}}];const s=summarize(rows);assert.equal(s.bets,1);assert.ok(Math.abs(s.profit-120)<1e-9);assert.equal(s.games,1);
 assert.equal(summarize([{kind:'prediction',payload:{...p,observed_at:'2026-09-11T12:00:00Z'}},rows[2]]).bets,0);
});

test('Blocked research results are visible only in their tracked group',async()=>{
 const {summarize}=await import('../apps/validation/metrics.mjs');const p={id:'research',tracking_group:'all_model',event:'e',selection:'s',side:'Over',observed_at:'2026-09-12T12:00:00Z',kickoff:'2026-09-12T16:00:00Z',odds:2,probability:.6,actionable:false,odds_band:'1.67–2.00'};
 const rows=[{kind:'prediction',payload:p},{kind:'settlement',payload:{prediction_id:'research',status:'loss',observed_at:'2026-09-12T19:00:00Z'}}];assert.equal(summarize(rows).bets,0);assert.equal(summarize(rows,'all_model').profit,-100);assert.equal(summarize(rows,'best_model').bets,0);
});

test('Away spreads display the opposite sign and graded records retain the pregame timestamp',async()=>{
 const {displayLine,summarize}=await import('../apps/validation/metrics.mjs');assert.equal(displayLine({market:'spreads',side_index:1,line:-40.5}),40.5);assert.equal(displayLine({market:'h2h',line:0}),'');
 const p={id:'p',tracking_group:'all_model',event:'e',selection:'s',side:'Away',observed_at:'2026-09-12T12:00:00Z',kickoff:'2026-09-12T16:00:00Z',odds:2,probability:.4,actionable:false,odds_band:'1.67–2.00'};
 const result=summarize([{kind:'prediction',payload:p},{kind:'settlement',payload:{prediction_id:'p',status:'loss',observed_at:'2026-09-12T19:00:00Z'}}],'all_model');assert.equal(result.graded[0].prediction_observed_at,p.observed_at);
});
