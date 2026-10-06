const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const React=require('react');

test('Results exposes full paginated receipts, Eastern slate filters, and real financial chart controls',async()=>{
 const {JSDOM}=require('jsdom'),{transformWithOxc}=await import('vite'),metrics=await import('../apps/validation/metrics.mjs'),cohort=await import('../shared/model-cohort.mjs'),evidence=await import('../apps/validation/evidence.mjs');
 const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost/results/'}),saved={window:global.window,document:global.document,IS_REACT_ACT_ENVIRONMENT:global.IS_REACT_ACT_ENVIRONMENT};
 global.window=dom.window;global.document=dom.window.document;global.IS_REACT_ACT_ENVIRONMENT=true;
 const {createRoot}=require('react-dom/client');
 const source=fs.readFileSync(require.resolve('../apps/validation/src.jsx'),'utf8').replace(/^import .*;\r?\n/gm,'').replace(/createRoot\(document\.getElementById\('root'\)\)\.render\(<App\/>\);/,'');
 const code=(await transformWithOxc(source,'validation.jsx',{jsx:{runtime:'classic'}})).code;
 const names=['React','useEffect','useMemo','useState','summarize','displayLine','filterTrackerRecords','slateDate','COHORT_LABELS','recordedEvidence','settlementExplanation'];
 const Dashboard=Function(...names,code+';return TrackerDashboard;')(React,React.useEffect,React.useMemo,React.useState,metrics.summarize,metrics.displayLine,metrics.filterTrackerRecords,metrics.slateDate,cohort.COHORT_LABELS,evidence.recordedEvidence,evidence.settlementExplanation);
 const records=[];
 for(let i=0;i<70;i++){
  const p={id:`p${i}`,tracking_group:'best_model',model_cohort:'current-80-20',sport:'nfl',home:'HOME',away:'AWAY',event:'game',player:`Player ${i}`,profile_id:`player-${i}`,market:'player_receiving_yards',side:'Over',side_index:0,line:50.5,odds:2,probability:.6,book:'Test',observed_at:'2026-10-01T12:00:00Z',kickoff:'2026-10-02T00:20:00Z'};
  records.push({kind:'prediction',payload:p},{kind:'settlement',payload:{prediction_id:p.id,status:'win',observed_at:`2026-10-02T04:${String(i%60).padStart(2,'0')}:00Z`}});
 }
 records.push({kind:'prediction',payload:{...records[0].payload,id:'000-missing',profile_id:'missing',player:'Missing Player'}});
 records.push({kind:'prediction',payload:{...records[0].payload,id:'001-rules',profile_id:'rules',player:'Rules Player'}},{kind:'prediction',payload:{...records[0].payload,id:'002-unknown',profile_id:'unknown',player:'Unknown Player'}},{kind:'prediction',payload:{...records[0].payload,id:'003-future',profile_id:'future',player:'Future Player',kickoff:'2099-10-02T00:20:00Z'}});
 const root=createRoot(document.getElementById('root'));
 try{
  await React.act(async()=>root.render(React.createElement(Dashboard,{records,meta:{settlement_audit:{counts:{player_participation_or_result_missing:1},pending:[{prediction_id:'000-missing',reason:'player_participation_or_result_missing'},{prediction_id:'001-rules',reason:'unsupported_settlement_rules'}]},generated_at:'2026-10-02T05:00:00Z',sources:{predictions:{last_capture_at:'2026-10-01T12:00:00Z'}},result_coverage:{slates:[{sport:'nfl',date:'2026-10-01',finals:2,tracked_finals:1,games:[{id:'game',home:'HOME',away:'AWAY',homeScore:28,awayScore:20,tracked:true},{id:'untracked',home:'OTHER',away:'VISITOR',homeScore:21,awayScore:10,tracked:false}]}]}}})));
  const $=selector=>document.querySelector(selector),text=()=>document.body.textContent;
  assert.equal($('.evidence-tabs button[aria-pressed="true"]').textContent,'Results');
  assert.equal(document.querySelectorAll('.result-card').length,24);
  assert.match($('.settlement-reason').textContent,/does not establish a zero, loss or void/);
  assert.match($('.settlement-reason').textContent,/Excluded from settled profit and ROI/);
  assert.match($('.evidence-unresolved').textContent,/entire published ledger/);
  assert.match($('.evidence-receipts .record-pager').textContent,/1–24 of 70/);
  const next=$('.evidence-receipts .record-pager button:last-child');
  await React.act(async()=>next.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true})));
  await React.act(async()=>next.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true})));
  assert.equal(document.querySelectorAll('.result-card').length,22);
  assert.match($('.evidence-receipts .record-pager').textContent,/49–70 of 70/);
  assert.match($('.profit-chart svg').getAttribute('aria-label'),/ending \$7,000/);
  await React.act(async()=>$('.chart-controls button:last-child').dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true})));
  assert.match($('.profit-chart svg').getAttribute('aria-label'),/ROI.*100\.0%/);
  const slate=[...document.querySelectorAll('select')].find(el=>el.parentElement.textContent.startsWith('Kickoff slate'));
  assert.ok([...slate.options].some(o=>o.value==='2026-10-01'));
  await React.act(async()=>{slate.value='2026-10-01';slate.dispatchEvent(new dom.window.Event('change',{bubbles:true}));});
  assert.match($('.evidence-receipts .record-pager').textContent,/1–24 of 70/);
  assert.match(text(),/Last pregame capture/);assert.match($('.finished-games').textContent,/2 final games/);assert.match($('.finished-games').textContent,/No pregame pick · no ROI/);assert.equal(document.querySelectorAll('.finished-games tbody tr').length,2);assert.doesNotMatch(text(),/AWAITING \/ COMPLETE/);
  await React.act(async()=>[...document.querySelectorAll('.evidence-tabs button')].find(b=>b.textContent==='Unresolved results').click());
  assert.equal(document.querySelectorAll('.tracked-cards article').length,3);
  assert.match($('.evidence-current h2').textContent,/Awaiting tracked results/);
  assert.doesNotMatch($('.tracked-cards').textContent,/Player 0|Future Player/);
  const reason=[...document.querySelectorAll('select')].find(el=>el.parentElement.textContent.startsWith('Unresolved reason'));
  assert.ok([...reason.options].some(o=>o.value==='verified_result_unavailable'));
  await React.act(async()=>{reason.value='unsupported_settlement_rules';reason.dispatchEvent(new dom.window.Event('change',{bubbles:true}));});
  assert.equal(document.querySelectorAll('.tracked-cards article').length,1);
  assert.match($('.tracked-cards').textContent,/Rules Player/);
  assert.match($('.settlement-reason').textContent,/does not support yet/);
  assert.match($('.profit-chart svg').getAttribute('aria-label'),/100\.0%/);
  await React.act(async()=>{reason.value='verified_result_unavailable';reason.dispatchEvent(new dom.window.Event('change',{bubbles:true}));});
  assert.match($('.settlement-reason').textContent,/verified result is not available/);
  await React.act(async()=>[...document.querySelectorAll('.evidence-tabs button')].find(b=>b.textContent==='Results').click());
  assert.equal(document.querySelectorAll('.tracked-cards article').length,24);
  assert.match(fs.readFileSync(require.resolve('../apps/validation/style.css'),'utf8'),/evidence-view-unresolved \.evidence-current\{display:block\}/);
 }finally{await React.act(async()=>root.unmount());dom.window.close();Object.assign(global,saved);}
});
