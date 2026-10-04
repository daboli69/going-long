'use strict';
// $0, offline public-Git collector. No provider requests, browser-local cohort or
// retroactive official predictions. Run from the source checkout under its cycle
// mutex. Frozen observations and appended result evidence are separate records.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const cp=require('node:child_process');
const core=require('../../shared/abbeys-core.cjs');
const {appendRecord,readRecords,hashPayload,canonicalJSON}=require('../../shared/ranking-journal.cjs');
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const textHash=file=>sha(fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n'));
const JOURNAL='data/abbeys/journal';
const BOARD='data/abbeys-board.json';
function readSource(root,name) {
  const bytes=fs.readFileSync(path.join(root,name));
  const data=JSON.parse(bytes);
  return {data,receipt:{file:name,sha256:hashPayload(data),hashEncoding:'canonical-json-v1',generatedAt:data.generated_at}};
}
function sources(root,now) {
  const schedule=readSource(root,'data/nfl_betting.json'),results=readSource(root,'data/results.json');
  const season=schedule.data.season;
  if (season!==Number(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric'}).format(new Date(now))) && !(new Date(now).getUTCMonth()<=2 && season===new Date(now).getUTCFullYear()-1)) throw new Error('Source is not the active NFL season');
  return {input:core.projectSources(schedule.data,results.data,season,now),receipts:[schedule.receipt,results.receipt],schedule:schedule.data};
}
function modelHash(root) {return textHash(path.join(root,'shared/abbeys-core.cjs'));}
function git(root,args) {return cp.execFileSync('git',args,{cwd:root,encoding:'utf8'}).trim();}
function sourceCommit(root) {
  if (git(root,['status','--porcelain','--','data/nfl_betting.json','data/results.json','data/injury_context.json'])) throw new Error('Public input files have uncommitted modifications');
  return git(root,['rev-parse','HEAD']);
}
function capture(root,week,mode='manual') {
  const now=new Date().toISOString(),commit=sourceCommit(root),s=sources(root,now);
  if (!['manual','scheduled'].includes(mode)) throw new Error('Capture mode must be manual or scheduled');
  const prediction=core.predictWeek(s.input,week);
  const records=readRecords(path.join(root,JOURNAL));
  const key=`abbeys|${s.input.season}|${week}|${core.MODEL_VERSION}`;
  if (records.some(r=>r.key===key)) throw new Error('This official week is already frozen; do not replace or backdate it');
  const allWeek=s.input.schedule.filter(g=>g.week===week);
  const origin=new Date(Math.min(...allWeek.map(g=>Date.parse(g.kickoff)))-12*3600000).toISOString();
  const parts=core.easternParts(origin),actual=core.easternParts(now);
  let cohort='manual-official';
  if (mode==='scheduled') {
    if (week<5 || parts.hour!=='08' || actual.year!==parts.year || actual.month!==parts.month || actual.day!==parts.day || actual.hour!=='08' || +actual.minute>14 || Date.parse(now)>Date.parse(origin)) throw new Error('Outside preregistered primary weekly origin; no missed-slot catchup');
    cohort='prospective-holdout-b-only';
  }
  const payload={schemaVersion:1,key,frozenAt:now,modelVersion:core.MODEL_VERSION,modelSHA256:modelHash(root),protocolSHA256:textHash(path.join(root,'research/abbeys/PROTOCOL.md')),sourceCommit:commit,sourceReceipts:s.receipts,input:s.input,inputHash:hashPayload(s.input),prediction,cohort,registeredOrigin:origin};
  const frozen=appendRecord(path.join(root,JOURNAL),{kind:'snapshot',key,observedAt:now,payload});
  // Current news is frozen as a separate, non-predictive context record AFTER
  // the official prediction exists. Historical injury effects are never read.
  let injury;
  try {injury=readSource(root,'data/injury_context.json');}
  catch {injury={data:{},receipt:null};}
  const fresh=Number.isFinite(Date.parse(injury.data.generated_at)) && Date.parse(injury.data.generated_at)<=Date.parse(now) && Date.parse(now)-Date.parse(injury.data.generated_at)<=36*3600000;
  const availability={};
  for (const p of prediction.picks) {
    availability[p.gameId]=fresh && injury.data.season===s.input.season ? Object.values(injury.data.current_reports||{}).filter(r=>r.week===week && [p.away,p.home].includes(r.team) && /out|doubtful|questionable|limited|did not participate/i.test(`${r.report_status||''} ${r.practice_status||''}`)).map(r=>({team:r.team,name:r.name,status:r.report_status||r.practice_status,injury:r.primary_injury||null})).slice(0,20) : [];
  }
  appendRecord(path.join(root,JOURNAL),{kind:'status',key:`context|${frozen.hash}`,observedAt:new Date().toISOString(),payload:{type:'post-freeze-context',snapshotHash:frozen.hash,availability,injuryReceipt:injury.receipt,fresh,historicalContext:null,marketContext:null,limitation:'No verified book-level quote timestamp or historical trend attached. Injury reports are not confirmed game-day inactives and do not numerically adjust this score benchmark.'}});
  verify(root);materialize(root);
  return {snapshotHash:frozen.hash,key,cohort,picks:prediction.picks.length,frozenAt:now};
}
function verify(root) {
  const records=readRecords(path.join(root,JOURNAL));
  const snapshots=new Map(records.filter(r=>r.kind==='snapshot').map(r=>[r.hash,r]));
  for (const r of records) {
    const p=r.payload;
    if (r.kind==='snapshot') {
      if (p.schemaVersion!==1 || p.frozenAt!==r.observedAt || p.input.cutoff!==p.frozenAt || p.inputHash!==hashPayload(p.input) || p.modelVersion!==core.MODEL_VERSION || p.modelSHA256!==modelHash(root) || p.protocolSHA256!==textHash(path.join(root,'research/abbeys/PROTOCOL.md'))) throw new Error('Snapshot version/input integrity failure');
      for (const receipt of p.sourceReceipts) {
        if (!['data/nfl_betting.json','data/results.json'].includes(receipt.file) || receipt.hashEncoding!=='canonical-json-v1') throw new Error('Unknown predictive source');
        const publicData=JSON.parse(cp.execFileSync('git',['show',`${p.sourceCommit}:${receipt.file}`],{cwd:root,encoding:'utf8'}));
        if (receipt.sha256!==hashPayload(publicData)) throw new Error('Predictive source differs from recorded Git revision');
      }
      if (canonicalJSON(core.predictWeek(p.input,p.prediction.week))!==canonicalJSON(p.prediction)) throw new Error('Frozen prediction is not reproducible');
      if (p.sourceReceipts.some(s=>Date.parse(s.generatedAt)>Date.parse(p.frozenAt))) throw new Error('Source receipt is after freeze');
    } else {
      const frozen=snapshots.get(p.snapshotHash);
      if (!frozen || Date.parse(r.observedAt)<Date.parse(frozen.observedAt)) throw new Error('Orphan or pre-freeze append');
      if (r.kind==='settlement') {
        const pick=frozen.payload.prediction.picks.find(g=>g.gameId===p.gameId);
        if (!pick || canonicalJSON(core.settlementFor(pick,p.result,p.source,r.observedAt))!==canonicalJSON(p.settlement) || p.settlement.state!=='settled') throw new Error('Invalid settlement evidence');
        if (!p.sourceSHA256 || !Number.isFinite(Date.parse(p.resultReceiptAt)) || Date.parse(p.resultReceiptAt)>Date.parse(r.observedAt) || Date.parse(p.resultReceiptAt)<=Date.parse(pick.kickoff)) throw new Error('Settlement source chronology failure');
        const schedule=JSON.parse(cp.execFileSync('git',['show',`${p.sourceCommit}:data/nfl_betting.json`],{cwd:root,encoding:'utf8'}));
        const results=JSON.parse(cp.execFileSync('git',['show',`${p.sourceCommit}:data/results.json`],{cwd:root,encoding:'utf8'}));
        const publicInput=core.projectSources(schedule,results,frozen.payload.input.season,r.observedAt);
        if (hashPayload(results)!==p.sourceSHA256 || !publicInput.results.some(g=>canonicalJSON(g)===canonicalJSON(p.result))) throw new Error('Settlement differs from public Git result evidence');
        if (frozen.payload.cohort!=='manual-official' && !holdoutReleased(publicInput,r.observedAt)) throw new Error('Holdout scoring is still locked');
      }
      if (r.kind==='invalidation' && (!p.reason || !p.evidence)) throw new Error('Invalidation requires reason and evidence');
    }
  }
  // Journal scans detect corruption/gaps; Git anchors additionally detect removal
  // of a valid chain tail or rewriting any already-published observation blob.
  const committed=git(root,['ls-tree','-r','--name-only','HEAD','--',JOURNAL]).split('\n').filter(Boolean);
  for (const file of committed) {
    const original=cp.execFileSync('git',['show',`HEAD:${file}`],{cwd:root});
    if (!fs.existsSync(path.join(root,file)) || !original.equals(fs.readFileSync(path.join(root,file)))) throw new Error(`Published journal changed/deleted: ${file}`);
  }
  return {records:records.length,snapshots:snapshots.size};
}
function settle(root) {
  const now=new Date().toISOString(),s=sources(root,now),records=readRecords(path.join(root,JOURNAL));
  let appended=0,conflicts=0;
  for (const frozen of records.filter(r=>r.kind==='snapshot')) for (const pick of frozen.payload.prediction.picks) {
    const result=s.input.results.find(g=>g.gameId===pick.gameId);
    if (!result) continue;
    if (Date.parse(s.receipts[1].generatedAt)<=Date.parse(pick.kickoff)) continue;
    const evidenceKey=`result-evidence|${frozen.hash}|${pick.gameId}|${hashPayload(result)}`;
    if (!records.some(r=>r.key===evidenceKey)) appendRecord(path.join(root,JOURNAL),{kind:'status',key:evidenceKey,observedAt:now,payload:{type:'result-evidence',snapshotHash:frozen.hash,gameId:pick.gameId,result,sourceSHA256:s.receipts[1].sha256,resultReceiptAt:s.receipts[1].generatedAt,sourceCommit:sourceCommit(root)}});
    if (frozen.payload.cohort!=='manual-official' && !holdoutReleased(s.input,now)) continue;
    const settlement=core.settlementFor(pick,result,'Public nflreadpy schedule/results snapshot',now);
    if (settlement.state!=='settled') continue;
    const prior=records.find(r=>r.kind==='settlement' && r.payload.snapshotHash===frozen.hash && r.payload.gameId===pick.gameId);
    if (prior) {
      if (canonicalJSON(prior.payload.result)!==canonicalJSON(result)) {
        const key=`result-conflict|${frozen.hash}|${pick.gameId}|${hashPayload(result)}`;
        if (!records.some(r=>r.key===key)) {appendRecord(path.join(root,JOURNAL),{kind:'status',key,observedAt:now,payload:{type:'result-conflict',snapshotHash:frozen.hash,gameId:pick.gameId,result,sourceSHA256:s.receipts[1].sha256,priorSettlementHash:prior.hash}});conflicts++;}
      }
      continue;
    }
    appendRecord(path.join(root,JOURNAL),{kind:'settlement',key:`settlement|${frozen.hash}|${pick.gameId}`,observedAt:now,payload:{snapshotHash:frozen.hash,gameId:pick.gameId,result,settlement,source:settlement.source,sourceSHA256:s.receipts[1].sha256,resultReceiptAt:s.receipts[1].generatedAt,sourceCommit:sourceCommit(root)}});appended++;
  }
  verify(root);materialize(root);return {appended,conflicts};
}
function holdoutReleased(input,now) {
  const finalWeek=input.schedule.filter(g=>g.week===18);
  if (!finalWeek.length) return false;
  const last=core.easternParts(new Date(Math.max(...finalWeek.map(g=>Date.parse(g.kickoff)))).toISOString());
  const release=new Date(Date.UTC(+last.year,+last.month-1,+last.day,17));
  do {release.setUTCDate(release.getUTCDate()+1);} while (release.getUTCDay()!==6);
  return Date.parse(now)>=Math.max(Date.parse('2027-01-16T17:00:00Z'),release.getTime()) && finalWeek.every(g=>input.results.some(r=>r.gameId===g.gameId)) && finalWeek.every(g=>Date.parse(g.kickoff)<Date.parse(now));
}
function invalidate(root,snapshotHash,reason,evidence) {
  if (!reason?.trim() || !evidence?.trim()) throw new Error('Reason and evidence required');
  const records=readRecords(path.join(root,JOURNAL));
  if (!records.some(r=>r.hash===snapshotHash && r.kind==='snapshot')) throw new Error('Unknown snapshot');
  appendRecord(path.join(root,JOURNAL),{kind:'invalidation',key:`invalidation|${snapshotHash}|${hashPayload({reason,evidence})}`,observedAt:new Date().toISOString(),payload:{snapshotHash,reason,evidence}});
  verify(root);materialize(root);
}
function materialize(root) {
  const records=readRecords(path.join(root,JOURNAL)),weeks=[];
  const record={wins:0,losses:0,ties:0,pending:0};
  for (const frozen of records.filter(r=>r.kind==='snapshot')) {
    const p=frozen.payload,context=records.find(r=>r.payload.type==='post-freeze-context' && r.payload.snapshotHash===frozen.hash)?.payload;
    const invalidations=records.filter(r=>r.kind==='invalidation' && r.payload.snapshotHash===frozen.hash).map(r=>({reason:r.payload.reason,evidence:r.payload.evidence,observedAt:r.observedAt}));
    const picks=p.prediction.picks.map(pick=>{
      const settled=records.find(r=>r.kind==='settlement' && r.payload.snapshotHash===frozen.hash && r.payload.gameId===pick.gameId)?.payload.settlement;
      const conflicts=records.filter(r=>r.payload.type==='result-conflict' && r.payload.snapshotHash===frozen.hash && r.payload.gameId===pick.gameId);
      const settlement=invalidations.length || conflicts.length ? null : settled||null;
      const reports=context?.availability?.[pick.gameId]||[];
      const concerns=[...pick.concerns,...reports.map(r=>`${r.team} ${r.name}: ${r.status}${r.injury?` (${r.injury})`:''}. Current injury report; participation and numerical impact are uncertain.`)];
      concerns.push(context?.fresh?'Availability snapshot is current; confirm game-day inactives. News does not rewrite this frozen score forecast.':'Availability evidence is missing/stale; confirm game-day inactives.');
      if (conflicts.length) concerns.push('Conflicting later result evidence: unresolved pending inspection. Original result evidence is preserved.');
      return {...pick,concerns,settlement};
    });
    // Holdout aggregate diagnostics stay locked. Manual Week 4 remains a separate
    // official record; never blend the retrospective checks into this count.
    if (p.cohort==='manual-official' && !invalidations.length) for (const pick of picks) record[pick.settlement?pick.settlement.outcome==='win'?'wins':pick.settlement.outcome==='loss'?'losses':'ties':'pending']++;
    const monday={...p.prediction.monday};
    const final=picks.find(g=>g.gameId===monday.gameId)?.settlement;
    if (final && monday.predictedAway!==null && monday.predictedHome!==null) monday.settlement={...final,awayAbsoluteError:Math.abs(final.actualAway-monday.predictedAway),homeAbsoluteError:Math.abs(final.actualHome-monday.predictedHome),combinedAbsoluteError:Math.abs(final.actualAway-monday.predictedAway)+Math.abs(final.actualHome-monday.predictedHome),exact:final.actualAway===monday.predictedAway && final.actualHome===monday.predictedHome};
    weeks.push({...p.prediction,training:undefined,picks,monday:p.prediction.monday?monday:null,frozenAt:p.frozenAt,observationHash:frozen.hash,cohort:p.cohort,invalidations,source:{generatedAt:p.sourceReceipts[1].generatedAt,sourceSHA:p.inputHash,cutoff:p.frozenAt,season:p.input.season},marketContext:context?.marketContext||null});
  }
  const board={schemaVersion:1,modelVersion:core.MODEL_VERSION,generatedAt:new Date().toISOString(),weeks,record,recordScope:'Manual official boards only. Prospective holdout aggregate evaluation is locked until the registered release; no reconstructed historical picks.'};
  const target=path.join(root,BOARD),pending=`${target}.pending-${process.pid}`;
  fs.writeFileSync(pending,JSON.stringify(board,null,2)+'\n',{flag:'wx'});fs.renameSync(pending,target);
  return board;
}
if (require.main===module) {
  const [command,rootArg,weekArg,modeArg]=process.argv.slice(2),root=path.resolve(rootArg||'.');
  const output=command==='capture'?capture(root,Number(weekArg),modeArg||'manual'):command==='settle'?settle(root):command==='verify'?verify(root):command==='materialize'?(verify(root),{weeks:materialize(root).weeks.length}):null;
  if (!output) throw new Error('Usage: collect.cjs capture SOURCE WEEK manual|scheduled; settle|verify|materialize SOURCE');
  process.stdout.write(JSON.stringify(output)+'\n');
}
module.exports={capture,verify,settle,invalidate,materialize,holdoutReleased,JOURNAL,BOARD};
