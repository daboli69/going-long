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

test('Performance history is chronological, reconciles to total profit and measures drawdown',async()=>{
 const {performanceSeries}=await import('../apps/validation/metrics.mjs');
 const result=performanceSeries([
  {prediction_id:'loss',observed_at:'2026-09-14T20:00:00Z',profit:-100},
  {prediction_id:'win',observed_at:'2026-09-13T20:00:00Z',profit:150},
  {prediction_id:'refund',observed_at:'2026-09-15T20:00:00Z',profit:0},
  {prediction_id:'loss-two',observed_at:'2026-09-16T20:00:00Z',profit:-100}
 ]);
 assert.deepEqual(result.series.map(p=>p.cumulative),[0,150,50,50,-50]);
 assert.equal(result.endingProfit,-50);
 assert.equal(result.maxDrawdown,200);
});

test('Different markets and lines for one player remain separate contracts',async()=>{
 const {summarize}=await import('../apps/validation/metrics.mjs');
 const base={tracking_group:'all_projection',event:'game',selection:'Player',side:'Over',side_index:0,observed_at:'2026-09-12T12:00:00Z',kickoff:'2026-09-12T16:00:00Z',odds:2,probability:.6,actionable:false,odds_band:'1.67–2.00'};
 const predictions=[{...base,id:'receiving',market:'player_receiving_yards',line:65.5},{...base,id:'receptions',market:'player_receptions',line:5.5},{...base,id:'alternate',market:'player_receiving_yards',line:75.5}];
 const rows=[...predictions.map(payload=>({kind:'prediction',payload})),...predictions.map((p,index)=>({kind:'settlement',payload:{prediction_id:p.id,status:index===1?'loss':'win',observed_at:'2026-09-12T20:00:00Z'}}))];
 const result=summarize(rows,'all_projection');
 assert.equal(result.bets,3);
 assert.equal(result.markets.find(row=>row.label==='player_receiving_yards').bets,2);
 assert.equal(result.reliability[0].decisive,3);
 assert.equal(result.reliability[0].winRate,2/3);
});

test('Tracking coverage separates upcoming and missing results without grading either',async()=>{
 const {summarize}=await import('../apps/validation/metrics.mjs');
 const base={tracking_group:'all_model',event:'game',selection:'team',market:'totals',side:'Over',line:45.5,odds:2,probability:.52,actionable:false,odds_band:'1.67–2.00',observed_at:'2026-09-10T12:00:00Z'};
 const rows=[
  {kind:'prediction',payload:{...base,id:'settled',kickoff:'2026-09-10T16:00:00Z'}},
  {kind:'settlement',payload:{prediction_id:'settled',status:'win',observed_at:'2026-09-10T20:00:00Z'}},
  {kind:'prediction',payload:{...base,id:'missing',line:46.5,kickoff:'2026-09-11T16:00:00Z'}},
  {kind:'prediction',payload:{...base,id:'upcoming',line:47.5,kickoff:'2026-09-13T16:00:00Z'}}
 ];
 const result=summarize(rows,'all_model',Date.parse('2026-09-12T12:00:00Z'));
 assert.deepEqual(result.coverage,{selected:3,upcoming:1,completed:2,settled:1,awaiting:1,settledShare:.5});
 assert.equal(result.bets,1);
});
