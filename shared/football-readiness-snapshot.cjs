'use strict';
const {createHash}=require('node:crypto');
const {assess,currentPlayerEvidence,currentGameEvidence,resultsIssue}=require('./football-confidence.js');
const VERSION='football-readiness-v2',SCHEMA_VERSION=2;
const validHash=x=>typeof x==='string'&&/^[a-f0-9]{64}$/i.test(x);
const sha=value=>createHash('sha256').update(value).digest('hex');
function candidateIdentity(row){
 const fields=['home','away','opp','position','prob','push','ev','n','profileDate','modelFamily','projMean','projSd','seasonEvidence','gameSeasonEvidence','roleEvidence','workloadEvidence','injury','evidence','flags','manual','dfs'];
 return {contract:row?.canonicalContract||row?.contract||null,sport:row?.sport||null,kind:row?.kind||null,event:row?.event||null,kickoff:row?.kickoff||null,profileId:row?.profileId||null,team:row?.team||null,market:row?.market||null,line:row?.line??null,side:row?.side||null,book:row?.book||null,american:row?.odds??null,decimal:row?.dec??null,quotedAt:row?.updatedAt||null,assessor_inputs:Object.fromEntries(fields.map(k=>[k,row?.[k]??null]))};
}
function candidateFingerprint(row){return sha(Buffer.from(JSON.stringify(candidateIdentity(row))));}
function publishedFinalRows(results){
 return Object.values(results?.games||{}).filter(g=>g&&[g.homeScore,g.awayScore].every(v=>Number.isInteger(v)&&v>=0)).map(g=>({...g,completed:true,season:new Date(g.kickoff).getUTCFullYear()-(new Date(g.kickoff).getUTCMonth()<6?1:0)}));
}
function confidenceMatchup(learning,row){
 const role=row?.market==='rec_yds'?'RECEIVING':row?.market==='rush_yds'?'RUSHING':null;
 return role?(learning?.matchup_signals||[]).find(m=>m.player_id===row.profileId&&m.opponent===(row.team===row.home?row.away:row.home)&&String(m.role||'').endsWith(role)&&Math.abs(Date.parse(m.kickoff)-Date.parse(row.kickoff))<60000)||null:null;
}
function captureReadiness(row,{capturedAt,season,contextAt,learningAt,historyAt,resultsAt,history,results,learning,historyHash,contextHash,learningHash,resultsHash,assessorHash,historyInputAt=historyAt,contextInputAt=contextAt,learningInputAt=learningAt,resultsInputAt=resultsAt}={}){
 const now=Date.parse(capturedAt),kickoff=Date.parse(row?.kickoff);
 if(!Number.isFinite(now)||!Number.isFinite(kickoff)||kickoff<=now||!validHash(historyHash)||!validHash(contextHash)||!validHash(assessorHash))return null;
 if([historyAt,contextAt,learningAt,resultsAt].some(at=>at&&(!Number.isFinite(Date.parse(at))||Date.parse(at)>now)))return null;
 if(learningHash&&!validHash(learningHash)||resultsHash&&!validHash(resultsHash))return null;
 if(learning&&(!Array.isArray(learning.matchup_signals)||!Array.isArray(learning.defensive_weaknesses)))learning=null;
 const matchup=confidenceMatchup(learning,row),weakness=matchup?learning.defensive_weaknesses.find(x=>x.id===matchup.weakness_id):null;
 const finals=publishedFinalRows(results);
 const resultSource=results?.sources?.[row.sport],gameEvidenceIssue=resultsIssue(results,row.sport,now);
 const gameEvidence=results?currentGameEvidence(finals,row,{now,season,resultsAt,source:'Published results.json full-game finals',sourceStatus:resultSource?.status,sourceCheckedAt:resultSource?.checked_at}):null;
 const evidence=assess(row,{now,season,contextAt,learningAt,historyAt,matchup,weakness,currentRoleEvidence:currentPlayerEvidence(history?.profiles?.[row?.profileId],row,{now,season}),currentGameEvidence:gameEvidence,gameEvidenceIssue});
 if(!evidence.eligible||!['support','developing','check'].includes(evidence.group))return null;
 return {schema_version:SCHEMA_VERSION,version:VERSION,captured_at:capturedAt,group:evidence.group,label:evidence.label,why:evidence.why,concern:evidence.concern,supports:evidence.supports,concerns:evidence.concerns,football_checks:evidence.footballChecks,price_checks:evidence.priceChecks,checks:evidence.checks,reason_codes:evidence.reasonCodes,dimensions:evidence.dimensions,current_games:evidence.currentGames,facts:evidence.facts,candidate_sha256:candidateFingerprint(row),assessor_sha256:assessorHash,inputs:{history:{sha256:historyHash,generated_at:historyInputAt||null},context:{sha256:contextHash,generated_at:contextInputAt||null},learning:validHash(learningHash)?{sha256:learningHash,generated_at:learningInputAt||null}:{unavailable:true},results:validHash(resultsHash)?{sha256:resultsHash,generated_at:resultsInputAt||null}:{unavailable:true},config:inputRef(row,'config'),injury:inputRef(row,'injury'),roster:inputRef(row,'roster'),nfl_feed:inputRef(row,'nfl_feed'),ncaa_feed:inputRef(row,'ncaa_feed')}};
}
function inputRef(row,key){return row?.readiness_inputs?.[key]||{unavailable:true};}
function validReadinessReceipt(receipt,row,provenance,observedAt){
 const freezeAt=Date.parse(observedAt),captured=Date.parse(receipt?.captured_at),kickoff=Date.parse(row?.kickoff),labels={support:'Current support',developing:'Developing',check:'Check first'},inputMap={history:'history.json',context:'football_context.json',learning:'season_learning.json',results:'results.json',config:'data.json',injury:'injury_context.json',roster:'players.json',nfl_feed:'nfl_betting.json',ncaa_feed:'ncaa_lines.json'};
 const textArray=x=>Array.isArray(x)&&x.every(v=>typeof v==='string');
 const checks=x=>Array.isArray(x)&&x.every(v=>v&&typeof v.code==='string'&&typeof v.label==='string'&&typeof v.detail==='string');
 const facts=x=>Array.isArray(x)&&x.every(v=>Array.isArray(v)&&v.length===2&&v.every(y=>typeof y==='string'));
 const inputsValid=receipt?.inputs&&Object.entries(inputMap).every(([key,name])=>{
  const saved=receipt.inputs[key],source=provenance?.inputs?.[name];
  if(key==='learning'&&saved?.unavailable===true)return !source;
  if(['results','learning'].includes(key)&&saved?.unavailable===true)return !source;
  return validHash(saved?.sha256)&&saved.sha256===source?.sha256&&saved.generated_at===(source?.generated_at||null)&&(!saved.generated_at||Number.isFinite(Date.parse(saved.generated_at))&&Date.parse(saved.generated_at)<=captured);
 });
 return receipt?.schema_version===SCHEMA_VERSION&&receipt.version===VERSION&&labels[receipt.group]===receipt.label&&typeof receipt.why==='string'&&typeof receipt.concern==='string'&&textArray(receipt.supports)&&textArray(receipt.concerns)&&checks(receipt.football_checks)&&checks(receipt.price_checks)&&textArray(receipt.checks)&&textArray(receipt.reason_codes)&&textArray(receipt.dimensions)&&facts(receipt.facts)&&validHash(receipt.candidate_sha256)&&receipt.candidate_sha256===candidateFingerprint(row)&&validHash(receipt.assessor_sha256)&&receipt.assessor_sha256===provenance?.readiness_assessor_sha256&&validHash(provenance?.model_source_sha256)&&Number.isFinite(freezeAt)&&Number.isFinite(captured)&&Number.isFinite(kickoff)&&captured<=freezeAt&&captured<kickoff&&inputsValid===true;
}
module.exports={VERSION,SCHEMA_VERSION,candidateIdentity,candidateFingerprint,publishedFinalRows,confidenceMatchup,captureReadiness,validReadinessReceipt};
