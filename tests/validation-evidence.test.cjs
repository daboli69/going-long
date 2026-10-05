const test=require('node:test'),assert=require('node:assert/strict');
test('Recorded evidence distinguishes absent provenance from saved inputs',async()=>{
 const {recordedEvidence,isHistoricalModel}=await import('../apps/validation/evidence.mjs');
 assert.match(recordedEvidence({}).join(' '),/cannot be reconstructed/);
 const p={tracking_group:'all_projection',model_evidence:{n:12,profileDate:'2026-09-10'},provenance:{model_source_sha256:'abc',inputs:{'history.json':{generated_at:'2026-09-11',sha256:'def'}}}};
 const text=recordedEvidence(p).join(' ');
 assert.match(text,/12 recorded games/);assert.match(text,/fingerprint def/);
 assert.match(text,/do not prove accuracy/);assert.equal(isHistoricalModel(p),true);
 assert.equal(Boolean(isHistoricalModel({tracking_group:'all_model'})),false);
});

test('Unresolved reasons explain the exact missing evidence without inventing a grade',async()=>{
 const {settlementExplanation}=await import('../apps/validation/evidence.mjs');
 assert.match(settlementExplanation('player_participation_or_result_missing'),/does not establish a zero, loss or void/);
 assert.match(settlementExplanation('player_market_result_missing'),/statistic/);
 assert.match(settlementExplanation('official_final_missing'),/still be in progress/);
 assert.match(settlementExplanation('unsupported_settlement_rules'),/does not support/);
 assert.match(settlementExplanation('not_before_official_kickoff'),/cannot be graded/);
 assert.match(settlementExplanation('future_unknown_reason'),/not available/);
});
