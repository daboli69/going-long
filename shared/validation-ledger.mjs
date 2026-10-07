/* Derived "light ledger" for the Validation dashboard (browser- and Node-safe).
 *
 * THE LEDGER IS A PROJECTION, NOT A SOURCE OF TRUTH. The segmented public tracker store
 * (shared/tracker-store.mjs, docs/TRACKER_STORE.md) stays the only canonical history. A ledger shard is a
 * pure function of exactly one sealed store segment: it keeps only the fields apps/validation/metrics.mjs and
 * the dashboard lists read, in the same {id,kind,observed_at,payload} shape, so the dashboard's own code runs
 * on it unchanged and produces identical numbers. Heavy evidence (provenance, readiness/picks snapshots, full
 * model_evidence) is NOT copied; it is fetched on demand from the canonical segment, checksum-verified.
 *
 * It must never be read by the tracker writer, calibration, settlement or any audit (see
 * tests/validation-ledger.test.cjs, which fails if any of them mention it).
 */
import {modelCohort} from './model-cohort.mjs';
import {expandSegment,LAYOUT as STORE_LAYOUT} from './tracker-store.mjs';

export const LEDGER_LAYOUT='validation-ledger-v1',PROJECTION_VERSION='validation-light-v3',LEDGER_PATH='derived/validation_ledger';
export const INDEX_PATH=LEDGER_PATH+'/index.json';
const HEAVY_PARTS=['model_evidence','provenance','picks_snapshot','readiness_snapshot'];
const KEPT_KINDS=new Set(['prediction','settlement','closing']);

const copy=(from,keys,to={})=>{for(const k of keys)if(from[k]!==undefined)to[k]=from[k];return to;};
const slate=at=>Number.isFinite(Date.parse(at));

/** NFL season year of a kickoff: Jul-Dec belong to that year, Jan-Jun to the previous one. */
export function seasonOf(kickoff){
 const t=Date.parse(kickoff);
 if(!Number.isFinite(t))return null;
 const d=new Date(t);
 return d.getUTCMonth()>=6?d.getUTCFullYear():d.getUTCFullYear()-1;
}

/** Pure projection of one canonical record to its light form; null for kinds the dashboard never reads. */
export function projectRecord(record){
 if(!KEPT_KINDS.has(record.kind))return null;
 const p=record.payload||{};
 let payload;
 if(record.kind==='prediction'){
  payload=copy(p,['id','tracking_group','sport','home','away','kickoff','recorded_kickoff','player','profile_id','market','line','side','side_index','book','odds','american','probability','observed_at','actionable','period','period_label','odds_band']);
  // Derived values that the dashboard would otherwise compute from heavy fields; exact by construction.
  payload.model_cohort=modelCohort(p);
  payload.rules=p.rules||((p.canonical_contract||p.selection||'').split('|').at(-1));
  if(p.model_evidence?.push!==undefined)payload.model_evidence={push:p.model_evidence.push};
  // The contract key falls back to these only when a record lacks teams or a valid kickoff; carry them then.
  if(!p.home||!p.away||!slate(p.kickoff))copy(p,['event','selection','canonical_contract'],payload);
 }else if(record.kind==='settlement'){
  payload=copy(p,['prediction_id','status','observed_at','actual','method','official_kickoff','sport','event']);
 }else{
  payload=copy(p,['prediction_id','near_kickoff','quoted_at','probability']);
 }
 return {id:record.id,kind:record.kind,observed_at:record.observed_at,payload};
}

export function projectSegment(records){return records.map(projectRecord).filter(Boolean);}

function recordSeasons(rows){
 return [...new Set(rows.filter(r=>r.kind==='prediction').map(r=>seasonOf(r.payload.kickoff)).filter(s=>s!==null))].sort((a,b)=>a-b);
}
export {recordSeasons};

/** Share one copy of every repeated string (teams, books, markets, timestamps, ids). Values are unchanged; it halves the parsed heap. */
export function internRows(rows,pool=new Map()){
 const share=v=>{let h=pool.get(v);if(h===undefined){pool.set(v,v);h=v;}return h;};
 const walk=o=>{for(const k of Object.keys(o)){const v=o[k];if(typeof v==='string')o[k]=share(v);else if(v&&typeof v==='object')walk(v);}};
 for(const r of rows){r.id=share(r.id);r.kind=share(r.kind);r.observed_at=share(r.observed_at);walk(r.payload);}
 return rows;
}

async function sha256Hex(text){
 const digest=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
 return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
}

/** Throws unless the ledger index was derived from exactly the store segments in `manifest`. */
export function assertLedgerMatchesStore(index,manifest){
 if(index?.layout!==LEDGER_LAYOUT||index.derived!==true||index.not_for_evaluation!==true)throw new Error('Not a validation ledger index');
 if(index.projection_version!==PROJECTION_VERSION)throw new Error('Validation ledger was built with a different projection version');
 const src=index.source?.segments||[];
 if(src.length!==manifest.segments.length||index.source.total_records!==manifest.total_records)throw new Error('Validation ledger is out of sync with the tracker store');
 manifest.segments.forEach((s,i)=>{if(src[i].sha256!==s.sha256||src[i].file!==s.file)throw new Error('Validation ledger is out of sync with tracker segment '+s.file);});
}

/** Pick which shards to load: shards that intersect `seasons`; `'all'` loads everything. */
export function selectShards(index,seasons='latest'){
 const all=index.shards;
 if(seasons==='all')return all.map((s,i)=>i);
 const latest=Math.max(...all.flatMap(s=>s.seasons||[]),-Infinity);
 const wanted=new Set(seasons==='latest'?(Number.isFinite(latest)?[latest]:[]):seasons);
 // A shard with no season (only non-prediction rows) rides with its neighbors, so include it when any neighbor loads.
 return all.map((s,i)=>i).filter(i=>(all[i].seasons||[]).some(x=>wanted.has(x))||(all[i].seasons||[]).length===0&&wanted.size>0);
}

/**
 * Load the light ledger for the dashboard. `getText(rel)` fetches a file under the data directory as text and
 * `manifest` is the (already loaded) tracker store manifest. Every shard is verified against the index checksum
 * and the index against the store manifest; any mismatch throws so the caller can fall back to the full store.
 */
export async function loadLedgerVerified(getText,manifest,{seasons='latest'}={}){
 const index=JSON.parse(await getText(INDEX_PATH));
 assertLedgerMatchesStore(index,manifest);
 const shardRows=new Map(),idToShard=new Map(),sharedStrings=new Map();
 const wanted=selectShards(index,seasons);
 async function loadShard(i){
  if(shardRows.has(i))return;
  const s=index.shards[i],text=await getText(LEDGER_PATH+'/'+s.file);
  if(await sha256Hex(text)!==s.sha256)throw new Error('Validation ledger shard '+s.file+' does not match its checksum');
  const shard=JSON.parse(text);
  if(shard.layout!==LEDGER_LAYOUT||shard.source?.segment_sha256!==s.source_segment_sha256||shard.rows.length!==s.rows)throw new Error('Validation ledger shard '+s.file+' is inconsistent');
  internRows(shard.rows,sharedStrings);
  shardRows.set(i,shard.rows);
  for(const r of shard.rows)idToShard.set(r.id,s.source_index);
 }
 await Promise.all(wanted.map(loadShard));
 const state={
  index,idToShard,
  loaded:()=>[...shardRows.keys()].sort((a,b)=>a-b),
  // Rows in canonical order: shards by index, each shard in its original order.
  rows:()=>[...shardRows.keys()].sort((a,b)=>a-b).flatMap(i=>shardRows.get(i)),
  skipped:()=>index.shards.map((s,i)=>({i,s})).filter(({i})=>!shardRows.has(i)).map(({s})=>({file:s.file,seasons:s.seasons,rows:s.rows})),
  async loadMore(which='all'){await Promise.all(selectShards(index,which).map(loadShard));return state.rows();},
 };
 return state;
}

/**
 * On-demand heavy evidence for one record id. Fetches the canonical store segment that holds the record (the
 * ledger shard and its source segment share an index), verifies its checksum against the store manifest, and
 * returns only the heavy parts the evidence panel reads. A small number of expanded segments are kept.
 */
export function makeEvidenceLoader(getText,manifest,idToShard,{keepSegments=2}={}){
 const cache=new Map();
 async function segmentParts(index){
  if(cache.has(index)){const hit=cache.get(index);cache.delete(index);cache.set(index,hit);return hit;}
  const entry=manifest.segments[index];
  if(!entry)throw new Error('No tracker segment for evidence');
  const pending=(async()=>{
   const text=await getText('public_tracker/'+entry.file);
   if(await sha256Hex(text)!==entry.sha256)throw new Error('Tracker segment '+entry.file+' is out of sync with the manifest');
   const rows=expandSegment(JSON.parse(text),{share:true}),byId=new Map();
   for(const r of rows){
    if(r.kind!=='prediction')continue;
    const parts={};for(const k of HEAVY_PARTS)if(r.payload[k]!==undefined)parts[k]=r.payload[k];
    byId.set(r.payload.id||r.id,parts);
   }
   return byId;
  })();
  cache.set(index,pending); // the in-flight promise is cached, so simultaneous requests share one download
  pending.catch(()=>{if(cache.get(index)===pending)cache.delete(index);});
  while(cache.size>keepSegments)cache.delete(cache.keys().next().value);
  return pending;
 }
 return async function loadEvidence(id){
  const index=idToShard.get(id);
  if(index===undefined)throw new Error('Unknown record');
  const parts=(await segmentParts(index)).get(id);
  if(!parts)throw new Error('Saved evidence for this record was not found in its segment');
  return parts;
 };
}

export {STORE_LAYOUT};
