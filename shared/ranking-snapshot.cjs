'use strict';
// Lossless columnar chunks keep complete pools affordable in the existing Git journal.
const {canonicalJSON,hashPayload,appendRecord,readRecords}=require('./ranking-journal.cjs');
const COLUMNS=['id','kind','sport','event','kickoff','home','away','profileId','player','team','opp','market','side','line','book','odds','dec','prob','push','ev','n','profileDate','updatedAt','canonicalContract','modelFamily','projMean','projSd','flags','evidence','slateDate','family','eligibility'];
const DERIVED=new Set(['frozenAt','quoteAgeSeconds','quoteFresh5m']);
function checkSnapshot(snapshot){
 if(!snapshot||typeof snapshot!=='object'||!Array.isArray(snapshot.rows)||!Array.isArray(snapshot.preCandidateExclusions)||!Array.isArray(snapshot.gameExclusions))throw Error('Invalid complete snapshot pool');
 if(!Number.isFinite(Date.parse(snapshot.decisionTime)))throw Error('Invalid snapshot decision time');
 for(const field of ['storageVersion','rowColumns','counts','chunks'])if(Object.hasOwn(snapshot,field))throw Error('Snapshot contains reserved storage field: '+field);
 canonicalJSON(snapshot); // Reject non-JSON before writing any reusable chunks.
 const ids=new Set();
 for(const row of snapshot.rows){
  if(!row||typeof row!=='object'||Array.isArray(row)||COLUMNS.some(k=>!Object.hasOwn(row,k)||row[k]===undefined)||Object.keys(row).some(k=>!COLUMNS.includes(k)&&!DERIVED.has(k)))throw Error('Snapshot row differs from frozen storage schema');
  if(ids.has(row.id))throw Error('Duplicate snapshot row ID');ids.add(row.id);
  const age=Number.isFinite(Date.parse(row.updatedAt))?(Date.parse(snapshot.decisionTime)-Date.parse(row.updatedAt))/1000:null;
  if(row.frozenAt!==snapshot.decisionTime||row.quoteAgeSeconds!==age||row.quoteFresh5m!==(age!==null&&age>=0&&age<=300))throw Error('Snapshot derived time fields disagree with frozen row');
 }
}
function storeSnapshot(directory,snapshot,key){checkSnapshot(snapshot);const records=readRecords(directory),known=new Map(records.map(r=>[r.key,r])),refs=[];const {rows,preCandidateExclusions,gameExclusions,...metadata}=snapshot;const evidence=[],evidenceIndex=new Map();const tuples=rows.map(row=>COLUMNS.map(k=>{if(k!=='evidence')return row[k];const body=row.evidence,h=hashPayload(body);if(!evidenceIndex.has(h)){evidenceIndex.set(h,evidence.length);evidence.push(body);}return evidenceIndex.get(h);}));
 for(const [field,data] of [['rows',tuples],['evidence',evidence],['preCandidateExclusions',preCandidateExclusions],['gameExclusions',gameExclusions]]){let group=[],bytes=0;const flush=()=>{if(!group.length)return;const payload={type:'snapshot_chunk_v1',field,items:group},chunkKey='pool|'+hashPayload(payload);let r=known.get(chunkKey);if(r&&(r.kind!=='status'||canonicalJSON(r.payload)!==canonicalJSON(payload)))throw Error('Conflicting immutable pool chunk');if(!r){r=appendRecord(directory,{kind:'status',key:chunkKey,observedAt:snapshot.decisionTime,payload});known.set(chunkKey,r);}refs.push({field,hash:r.hash,count:group.length});group=[];bytes=0;};for(const item of data){const size=Buffer.byteLength(canonicalJSON(item));if(size>500000)throw Error('Single pool item exceeds safe chunk budget');if(bytes+size>500000||group.length>=1000)flush();group.push(item);bytes+=size;}flush();}
 return appendRecord(directory,{kind:'snapshot',key,observedAt:snapshot.decisionTime,payload:{...metadata,storageVersion:1,rowColumns:COLUMNS,counts:{rows:rows.length,evidence:evidence.length,preCandidateExclusions:preCandidateExclusions.length,gameExclusions:gameExclusions.length},chunks:refs}});
}
function materialize(record,records){const meta=record?.payload;if(record?.kind!=='snapshot'||meta?.storageVersion!==1||JSON.stringify(meta.rowColumns)!==JSON.stringify(COLUMNS)||!Array.isArray(meta.chunks)||!meta.counts)throw Error('Unknown frozen storage schema');const byHash=new Map(records.map(r=>[r.hash,r])),parts={rows:[],evidence:[],preCandidateExclusions:[],gameExclusions:[]};for(const ref of meta.chunks){const r=byHash.get(ref.hash);if(!r||r.seq>=record.seq||Date.parse(r.observedAt)>Date.parse(record.observedAt)||r.key!=='pool|'+hashPayload(r.payload)||r.kind!=='status'||r.payload.type!=='snapshot_chunk_v1'||r.payload.field!==ref.field||!parts[ref.field]||!Array.isArray(r.payload.items)||r.payload.items.length!==ref.count)throw Error('Missing or invalid immutable pool chunk');parts[ref.field].push(...r.payload.items);}for(const f of Object.keys(parts))if(parts[f].length!==meta.counts[f])throw Error('Incomplete candidate pool: '+f);const rows=parts.rows.map(tuple=>{if(!Array.isArray(tuple)||tuple.length!==COLUMNS.length)throw Error('Corrupt columnar row');const row=Object.fromEntries(COLUMNS.map((k,i)=>[k,tuple[i]]));if(!Number.isSafeInteger(row.evidence)||row.evidence<0||row.evidence>=parts.evidence.length)throw Error('Invalid frozen evidence index');row.evidence=parts.evidence[row.evidence];row.frozenAt=meta.decisionTime;row.quoteAgeSeconds=Number.isFinite(Date.parse(row.updatedAt))?(Date.parse(meta.decisionTime)-Date.parse(row.updatedAt))/1000:null;row.quoteFresh5m=row.quoteAgeSeconds!==null&&row.quoteAgeSeconds>=0&&row.quoteAgeSeconds<=300;return row;});const {storageVersion,rowColumns,counts,chunks,...snapshot}=meta;return {...snapshot,rows,preCandidateExclusions:parts.preCandidateExclusions,gameExclusions:parts.gameExclusions};}
function verifyCompletePools(records){
 if(!Array.isArray(records))throw new TypeError('Journal records must be an array');
 const referenced=new Set();
 let snapshots=0;
 for(const record of records){
  if(record.kind!=='snapshot')continue;
  materialize(record,records); // Validate each complete manifest and all of its references.
  snapshots++;
  for(const ref of record.payload.chunks)referenced.add(ref.hash);
 }
 let chunks=0;
 for(const record of records){
  if(record.kind!=='status'||record.payload?.type!=='snapshot_chunk_v1')continue;
  chunks++;
  if(!referenced.has(record.hash))throw Error('Orphan immutable pool chunk: '+record.hash);
 }
 return {snapshots,chunks};
}
module.exports={storeSnapshot,materialize,verifyCompletePools,COLUMNS};
