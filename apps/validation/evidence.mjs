export function recordedEvidence(p){
 const evidence=p.model_evidence||{},source=p.provenance;
 const lines=[];
 if(Number.isFinite(evidence.n))lines.push(`${evidence.n} recorded games supported this estimate.`);
 if(evidence.profileDate)lines.push(`Player history through ${evidence.profileDate}.`);
 const picks=p.picks_snapshot;if(['football-case-v1','football-case-v2'].includes(picks?.version)){lines.push('Frozen GOING rating: '+picks.rating+(picks.version==='football-case-v2'?'/100':'/5')+' — research strength, not probability or value.');lines.push('Why: '+picks.why,'Concern: '+picks.concern,'Badges: '+picks.badges.join(', '));for(const [name,value] of picks.facts||[])lines.push(name+': '+value);}
 const readiness=p.readiness_snapshot;
 if(readiness?.schema_version===2&&readiness.version==='football-readiness-v2'&&readiness.captured_at&&readiness.assessor_sha256){
  lines.push(`Saved GOING Confidence at capture: ${readiness.label} (${readiness.captured_at}).`);
  lines.push(`Why: ${readiness.why}`);
  if(readiness.concern)lines.push(`Main concern: ${readiness.concern}`);
  for(const check of readiness.football_checks||[])lines.push(`Football check — ${check.label}: ${check.detail}`);
  for(const check of readiness.price_checks||[])lines.push(`Price check — ${check.label}: ${check.detail}`);
  for(const [name,value] of readiness.facts||[])lines.push(`Capture-time ${name}: ${value}.`);
  lines.push(`Readiness assessor fingerprint: ${readiness.assessor_sha256}; candidate fingerprint: ${readiness.candidate_sha256}.`);
 }else lines.push('GOING Confidence readiness was not saved at capture; older records are not reconstructed from current context.');
 if(!source?.model_source_sha256)return [...lines,'This older record has no saved model/input fingerprints. They cannot be reconstructed reliably after the fact.'];
 lines.push(`Model fingerprint: ${source.model_source_sha256}.`);
 for(const [name,input] of Object.entries(source.inputs||{}))lines.push(`${name}: published ${input.generated_at||'at an unrecorded time'}; fingerprint ${input.sha256}.`);
 lines.push('Fingerprints identify the exact inputs used; they do not prove accuracy or that every input was available historically.');
 return lines;
}
export const isHistoricalModel=p=>['all_projection','best_model'].includes(p.tracking_group)||p.model_version?.startsWith('board-tracking-');

export function settlementExplanation(reason){
 const explanations={
  player_participation_or_result_missing:'The player appearance or result log is missing. This does not establish a zero, loss or void.',
  player_market_result_missing:'The player log is present, but the statistic needed for this market is missing.',
  official_final_missing:'No matching official final is published yet. The game may still be in progress or its result unavailable.',
  partial_final:'The official result is incomplete; both final team scores are required.',
  ambiguous_game:'More than one official game matches this record. A unique match is required before grading.',
  not_before_official_kickoff:'The recorded capture was not before the official kickoff. It cannot be graded as a pregame selection.',
  unsupported_settlement_rules:'This market needs settlement rules or period-specific results that the tracker does not support yet.'
 };
 return explanations[reason]||'A verified result is not available for this saved selection yet.';
}
