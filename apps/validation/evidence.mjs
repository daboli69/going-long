export function recordedEvidence(p){
 const evidence=p.model_evidence||{},source=p.provenance;
 const lines=[];
 if(Number.isFinite(evidence.n))lines.push(`${evidence.n} recorded games supported this estimate.`);
 if(evidence.profileDate)lines.push(`Player history through ${evidence.profileDate}.`);
 if(!source?.model_source_sha256)return [...lines,'This older record has no saved model/input fingerprints. They cannot be reconstructed reliably after the fact.'];
 lines.push(`Model fingerprint: ${source.model_source_sha256}.`);
 for(const [name,input] of Object.entries(source.inputs||{}))lines.push(`${name}: published ${input.generated_at||'at an unrecorded time'}; fingerprint ${input.sha256}.`);
 lines.push('Fingerprints identify the exact inputs used; they do not prove accuracy or that every input was available historically.');
 return lines;
}
export const isHistoricalModel=p=>['all_projection','best_model'].includes(p.tracking_group)||p.model_version?.startsWith('board-tracking-');
