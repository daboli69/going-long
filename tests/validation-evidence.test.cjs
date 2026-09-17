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
