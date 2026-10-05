'use strict';
const {createHash}=require('node:crypto');
const {candidateFingerprint}=require('./football-readiness-snapshot.cjs');
const {quote}=require('./football-picks.js');
const hash=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const fingerprint=row=>hash([candidateFingerprint(row),row.modelMean??null,row.modelSd??null]);
function validPickReceipt(receipt,row,provenance,observedAt){
 const captured=Date.parse(receipt?.captured_at),frozen=Date.parse(observedAt),kickoff=Date.parse(row?.kickoff);
 const textArray=x=>Array.isArray(x)&&x.every(v=>typeof v==='string');
 return receipt?.version==='football-case-v1'&&row?.model_cohort==='going-picks-v1'&&Number.isInteger(receipt.rating)&&receipt.rating>=1&&receipt.rating<=5&&Number.isFinite(receipt.points)&&receipt.points>0&&Number.isInteger(receipt.rank)&&receipt.rank>0&&typeof receipt.why==='string'&&typeof receipt.concern==='string'&&textArray(receipt.badges)&&textArray(receipt.unknown)&&Array.isArray(receipt.components)&&receipt.components.reduce((sum,x)=>sum+x.points,0)===receipt.points&&Array.isArray(receipt.facts)&&receipt.price?.saveable===quote(row,captured).saveable&&receipt.candidate_sha256===fingerprint(row)&&/^[a-f0-9]{64}$/.test(provenance?.picks_assessor_sha256||'')&&Number.isFinite(captured)&&captured<=frozen&&captured<kickoff&&Object.entries(provenance?.inputs||{}).every(([name,source])=>/^[a-f0-9]{64}$/.test(source.sha256||'')&&receipt.source_inputs?.[name]?.sha256===source.sha256&&(!source.generated_at||Date.parse(source.generated_at)<=captured));
}
module.exports={fingerprint,validPickReceipt};
