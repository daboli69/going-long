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


test('Eastern kickoff slate filters retain linked results and do not filter by capture date',async()=>{
 const {filterTrackerRecords,slateDate,summarize}=await import('../apps/validation/metrics.mjs');
 const nfl={id:'nfl',tracking_group:'best_model',sport:'nfl',event:'e1',selection:'team',side:'Over',market:'totals',line:40.5,odds:2.2,probability:.55,observed_at:'2026-10-02T12:00:00Z',kickoff:'2026-10-05T00:20:00Z'};
 const ncaa={...nfl,id:'ncaa',sport:'ncaa',event:'e2',kickoff:'2026-10-04T02:30:00Z'};
 const rows=[{kind:'prediction',id:'record-nfl',payload:nfl},{kind:'prediction',id:'record-ncaa',payload:ncaa},{kind:'settlement',payload:{prediction_id:'nfl',status:'win',observed_at:'2026-10-05T04:00:00Z'}},{kind:'settlement',payload:{prediction_id:'ncaa',status:'loss',observed_at:'2026-10-04T05:30:00Z'}}];
 assert.equal(slateDate(nfl.kickoff),'2026-10-04');assert.equal(slateDate(ncaa.kickoff),'2026-10-03');
 assert.equal(slateDate('not-a-date'),'');
 const nflRows=filterTrackerRecords(rows,{sport:'nfl',date:'2026-10-04'});
 assert.equal(nflRows.length,2);assert.ok(Math.abs(summarize(nflRows,'best_model').profit-120)<1e-9);
 assert.equal(summarize(filterTrackerRecords(rows,{sport:'ncaa',date:'2026-10-03'}),'best_model').profit,-100);
 assert.equal(filterTrackerRecords(rows,{days:'7',asOf:Date.parse('2026-10-05T12:00:00Z')}).length,4);
});

test('$100 financial denominators include returns and exclude unresolved selections',async()=>{
 const {summarize}=await import('../apps/validation/metrics.mjs');
 const base={tracking_group:'best_model',event:'game',selection:'team',market:'totals',side:'Over',odds:2.5,probability:.6,observed_at:'2026-10-03T12:00:00Z',kickoff:'2026-10-03T16:00:00Z'};
 const statuses=['win','loss','refund','void'];
 const rows=statuses.flatMap((status,i)=>[{kind:'prediction',payload:{...base,id:status,line:40.5+i}},{kind:'settlement',payload:{prediction_id:status,status,observed_at:'2026-10-03T20:00:00Z'}}]);
 rows.push({kind:'prediction',payload:{...base,id:'pending',line:50.5}});
 const result=summarize(rows,'best_model',Date.parse('2026-10-04T12:00:00Z'));
 assert.deepEqual(result.counts,{win:1,loss:1,refund:1,void:1});assert.equal(result.stake,400);assert.equal(result.profit,50);assert.equal(result.roi,.125);assert.equal(result.winRate,.5);assert.equal(result.coverage.awaiting,1);assert.equal(result.series.at(-1).roi,.125);assert.equal(result.selected.length,5);
});


test('Vendor kickoff drift and book changes are one contract while cohorts and lines stay separate',async()=>{
 const {summarize,performanceContractKey,performanceGameKey}=await import('../apps/validation/metrics.mjs');
 const p={id:'first',tracking_group:'best_model',sport:'nfl',home:'DEN',away:'JAX',event:'vendor-1',selection:'contract|rule',canonical_contract:'canonical-1|rule',market:'player_receiving_yards',profile_id:'player-1',player:'Receiver',side_index:0,side:'Over',line:65.5,odds:2,probability:.55,observed_at:'2026-10-04T12:00:00Z',kickoff:'2026-10-04T20:05:00Z',book:'A',model_cohort:'legacy'};
 const drift={...p,id:'later',event:'vendor-2',canonical_contract:'canonical-2|rule',kickoff:'2026-10-04T20:10:00Z',observed_at:'2026-10-04T13:00:00Z',book:'B',odds:3};
 assert.equal(performanceContractKey(p),performanceContractKey(drift));assert.equal(performanceGameKey(p),performanceGameKey(drift));
 assert.notEqual(performanceContractKey(p),performanceContractKey({...drift,line:75.5}));assert.notEqual(performanceContractKey(p),performanceContractKey({...drift,model_cohort:'current-80-20'}));
 const rows=[{kind:'prediction',payload:p},{kind:'prediction',payload:drift},...['first','later'].map(prediction_id=>({kind:'settlement',payload:{prediction_id,status:'win',observed_at:'2026-10-05T00:00:00Z'}}))];
 const result=summarize(rows,'best_model');assert.equal(result.bets,1);assert.equal(result.profit,100);assert.equal(result.games,1);assert.equal(result.selected[0].book,'A');
});

test('Verified official midnight slate correction preserves the original frozen kickoff',async()=>{
 const {filterTrackerRecords,summarize}=await import('../apps/validation/metrics.mjs');
 const p={id:'midnight',tracking_group:'best_model',sport:'ncaa',home:'HOME',away:'AWAY',player:'AWAY @ HOME',market:'h2h',side:'Home',side_index:0,line:0,odds:2,probability:.6,observed_at:'2026-10-03T12:00:00Z',kickoff:'2026-10-04T04:00:00Z'};
 const rows=[{kind:'prediction',payload:p},{kind:'settlement',payload:{prediction_id:p.id,status:'loss',method:'published_full_game_result',official_kickoff:'2026-10-04T03:59:00Z',observed_at:'2026-10-04T08:00:00Z'}}];
 const filtered=filterTrackerRecords(rows,{date:'2026-10-03',sport:'ncaa'});assert.equal(filtered.length,2);assert.equal(summarize(filtered,'best_model').profit,-100);
 assert.equal(p.kickoff,'2026-10-04T04:00:00Z');assert.equal(filtered[0].payload.recorded_kickoff,p.kickoff);
 assert.equal(filterTrackerRecords(rows,{date:'2026-10-04'}).length,0);
});


test('Game filter keeps linked settlements/prices, normalizes vendor drift and separates sports/dates',async()=>{
 const {filterTrackerRecords,performanceGameKey,summarize}=await import('../apps/validation/metrics.mjs');
 const p={id:'a',tracking_group:'best_model',sport:'nfl',home:'BAL',away:'CIN',event:'vendor-a',market:'totals',side:'Over',line:45.5,odds:2,probability:.6,observed_at:'2026-10-01T12:00:00Z',kickoff:'2026-10-04T17:00:00Z'};
 const rows=[{kind:'prediction',payload:p},{kind:'prediction',payload:{...p,id:'b',event:'vendor-b',home:'bal',kickoff:'2026-10-04T17:01:00Z',line:46.5}},{kind:'prediction',payload:{...p,id:'ncaa',sport:'ncaa'}},{kind:'prediction',payload:{...p,id:'other-date',kickoff:'2026-10-11T17:00:00Z'}},{kind:'settlement',payload:{prediction_id:'a',status:'win',observed_at:'2026-10-04T21:00:00Z'}},{kind:'closing',payload:{prediction_id:'a',near_kickoff:true,quoted_at:'2026-10-04T16:59:00Z',probability:.55}}];
 const selected=filterTrackerRecords(rows,{game:performanceGameKey(p)});
 assert.deepEqual(selected.map(r=>r.payload.id||r.payload.prediction_id),['a','b','a','a']);
 const stats=summarize(selected,'best_model');assert.equal(stats.profit,100);assert.equal(stats.stake,100);assert.equal(stats.roi,1);assert.equal(stats.selected.length,2);
 assert.equal(filterTrackerRecords(rows,{game:'unknown'}).length,0);assert.equal(filterTrackerRecords(rows).length,rows.length);assert.equal(rows[1].payload.home,'bal');
});
