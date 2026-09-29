const {test}=require('node:test'),assert=require('node:assert/strict');
function history(){const out=[];for(let i=0;i<24;i++){const kick=new Date(Date.UTC(2025,8,1+i*7)).toISOString(),at=new Date(Date.parse(kick)-86400000).toISOString(),settled=new Date(Date.parse(kick)+6*3600000).toISOString(),id='p'+i;out.push({id,kind:'prediction',payload:{id,tracking_group:'best_model',canonical_contract:id,sport:'nfl',home:'A',away:'B',market:'player_rushing_yards',kickoff:kick,observed_at:at,probability:.8,model_evidence:{push:0}}},{kind:'settlement',payload:{prediction_id:id,status:i%2?'win':'loss',observed_at:settled,method:'published_full_game_result'}});}return out;}
test('calibration is chronological, game-balanced and never trains on another cohort',async()=>{
 const {calibrationRows,shadowPrediction,calibrationAudit}=await import('../scripts/calibration_audit.mjs');
 const records=history(),rows=calibrationRows(records),p=rows[15].p,before=shadowPrediction(p,rows);
 assert.ok(before.conditional_probability<.8);assert.ok(Date.parse(before.trained_through)<Date.parse(p.observed_at));
 const altered=rows.map(r=>r.available>=Date.parse(p.observed_at)?{...r,y:1-r.y}:r);
 assert.deepEqual(shadowPrediction(p,altered),before);
 assert.equal(shadowPrediction({...p,model_cohort:'current-80-20'},rows),null);
 assert.equal(calibrationAudit(records,'2026-09-29T12:00:00Z').live_adjustment,false);
});
test('80/20 classification uses explicit policy, not coincidental 100% current samples',async()=>{
 const {modelCohort}=await import('../shared/model-cohort.mjs');
 assert.equal(modelCohort({model_evidence:{seasonEvidence:{current_weight:1,method:'equal appearance baseline'}}}),'role-aware-equal-weight');
 assert.equal(modelCohort({model_evidence:{seasonEvidence:{current_weight:0,method:'80% current / 20% historical policy'}}}),'current-80-20');
});
test('grading tolerates a unique same-day clock drift but rejects ambiguity and late capture',async()=>{
 const {settlementReason,settlePredictions}=await import('../scripts/build_public_tracker.mjs');
 const p={id:'p',sport:'nfl',home:'A',away:'B',market:'totals',line:40.5,side_index:0,kickoff:'2026-09-20T17:07:00Z',observed_at:'2026-09-20T16:00:00Z'},game={sport:'nfl',home:'A',away:'B',kickoff:'2026-09-20T17:00:00Z',homeScore:24,awayScore:20},results={games:{a:game}};
 assert.equal(settlementReason(p,results,'2026-09-21T12:00:00Z'),null);
 assert.equal(settlePredictions([{kind:'prediction',payload:p}],results,'2026-09-21T12:00:00Z')[0].payload.status,'win');
 assert.equal(settlementReason({...p,observed_at:'2026-09-20T17:03:00Z'},results,'2026-09-21T12:00:00Z'),'not_before_official_kickoff');
 assert.equal(settlementReason(p,{games:{a:game,b:{...game,kickoff:'2026-09-20T20:00:00Z'}}},'2026-09-21T12:00:00Z'),'ambiguous_game');
 assert.equal(settlementReason({...p,market:'atd',profile_id:'missing'},results,'2026-09-21T12:00:00Z'),'player_participation_or_result_missing');
});
test('price observations must match book and line and cannot be backfilled after kickoff',async()=>{
 const {captureClosingPrices}=await import('../scripts/build_public_tracker.mjs');
 const p={id:'p',sport:'nfl',home:'A',away:'B',profile_id:'q',market:'player_passing_yards',side:'Over',line:200.5,book:'Book',kickoff:'2026-09-20T17:00:00Z',observed_at:'2026-09-20T15:00:00Z'};
 const q={...p,profileId:'q',market:'pass_yds',dec:1.9,updatedAt:'2026-09-20T16:54:00Z',reference:{win:.52,loss:.48}},records=[{kind:'prediction',payload:p}];
 assert.equal(captureClosingPrices(records,[{...q,line:201.5},{...q,book:'Other'}],'2026-09-20T16:55:00Z').length,0);
 const found=captureClosingPrices(records,[q],'2026-09-20T16:55:00Z');assert.equal(found.length,1);assert.equal(found[0].payload.near_kickoff,true);
 assert.equal(captureClosingPrices(records,[q],'2026-09-20T16:56:00Z').length,0);
 assert.equal(captureClosingPrices([{kind:'prediction',payload:p}],[q],'2026-09-20T17:01:00Z').length,0);
});
test('model versions retain separate frozen forecasts without overwriting old contracts',async()=>{
 const {freezePredictions}=await import('../scripts/build_public_tracker.mjs'),{cohortRecords}=await import('../apps/validation/metrics.mjs');
 const base={sport:'nfl',home:'A',away:'B',kind:'prop',profileId:'q',market:'pass_yds',side:'Over',line:200.5,book:'Book',kickoff:'2026-09-20T17:00:00Z',updatedAt:'2026-09-20T14:00:00Z',canonicalContract:'same',dec:1.9,prob:.6,tracking_group:'best_model'},rows=[];
 freezePredictions(rows,[base],'2026-09-20T15:00:00Z');freezePredictions(rows,[{...base,prob:.55,seasonEvidence:{method:'80% current / 20% historical policy'}}],'2026-09-20T15:10:00Z');
 assert.equal(rows.length,2);assert.equal(rows[0].payload.probability,.6);assert.equal(cohortRecords(rows,'current-80-20').length,1);
});
test('workload diagnostics require frozen inputs and reconcile volume plus efficiency errors',async()=>{
 const {workloadAudit}=await import('../scripts/calibration_audit.mjs');const rows=history().slice(0,2);rows[0].payload.model_evidence={projection_mean:50,workload:{carries:{mean:10}}};rows[1].payload.actual=24;rows[1].payload.actual_workload={carries:8};
 const row=workloadAudit(rows).families[0];assert.equal(row.volume_error,10);assert.equal(row.efficiency_error,16);assert.equal(row.projection_error,26);
 delete rows[0].payload.model_evidence.workload;assert.equal(workloadAudit(rows).families.length,0);
});
