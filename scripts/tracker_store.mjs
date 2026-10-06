/* Write side (and Node reader) of the segmented public tracker store; see shared/tracker-store.mjs.
 *
 * Invariants enforced on every write:
 *  - append-only: every record already stored must be unchanged and in the same position;
 *  - lossless: each segment is expanded again and compared record-for-record with its input;
 *  - segment files are content-addressed (seg-NNNNNN-<sha12>.json) and never rewritten in place; the
 *    manifest is written LAST (atomic rename) and superseded files are removed only afterwards, so a
 *    crash or retry always leaves a manifest whose every referenced file exists with a matching checksum;
 *  - no file may exceed MAX_FILE_BYTES.
 */
import {readFile,writeFile,rename,mkdir,readdir,unlink} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {LAYOUT,expandSegment,rehydrate} from '../shared/tracker-store.mjs';

export {LAYOUT};
export const STORE_DIR='public_tracker',LEGACY_FILE='public_tracker.json';
export const MAX_RAW_SEGMENT_BYTES=5_000_000,WARN_FILE_BYTES=4e6,MAX_FILE_BYTES=30e6,MIN_INTERN_BYTES=96;
const sha=text=>createHash('sha256').update(text).digest('hex');
const isBig=(node,s)=>s.length>=MIN_INTERN_BYTES;

/** Replace exact-duplicate subtrees/long strings inside one segment's records with dictionary refs. */
export function internRecords(records){
 const counts=new Map();
 const key=(node,s)=>(typeof node==='string'?'s:':'o:')+sha(s);
 const visit=(node,fn)=>{
  if(Array.isArray(node)){for(const v of node)consider(v,fn);return;}
  if(node&&typeof node==='object')for(const k of Object.keys(node))consider(node[k],fn);
 };
 const consider=(node,fn)=>{
  if(node===null||typeof node!=='object'&&typeof node!=='string')return;
  const s=JSON.stringify(node);
  if(isBig(node,s)){if(fn(node,s))return;}
  if(typeof node==='object')visit(node,fn);
 };
 for(const r of records)consider(r,(node,s)=>{const k=key(node,s);counts.set(k,(counts.get(k)||0)+1);return false;});
 const dict={},full=new Map();
 const rebuild=node=>{
  if(node===null||typeof node!=='object'&&typeof node!=='string')return node;
  const s=JSON.stringify(node);
  if(isBig(node,s)){
   const k=key(node,s);
   if(counts.get(k)>=2&&node!==undefined){
    const id=k.slice(0,2)+sha(s).slice(0,20);
    if(full.has(id)&&full.get(id)!==s)throw new Error('Dictionary id collision '+id);
    full.set(id,s);dict[id]=node;
    return {$ref:id};
   }
  }
  if(Array.isArray(node))return node.map(rebuild);
  if(typeof node==='object'){const o={};for(const k of Object.keys(node))o[k]=rebuild(node[k]);return o;}
  return node;
 };
 // A literal {"$ref":...} in source data would be indistinguishable from a reference.
 const guard=n=>{if(n&&typeof n==='object'){const ks=Object.keys(n);if(!Array.isArray(n)&&ks.length===1&&ks[0]==='$ref')throw new Error('Source data contains a reserved $ref object');for(const k of ks)guard(n[k]);}};
 for(const r of records)guard(r);
 const out=records.map(rebuild);
 return {dict,records:out};
}

export function planSegments(records,start,maxRaw=MAX_RAW_SEGMENT_BYTES){
 const bounds=[];let from=start,size=0;
 for(let i=start;i<records.length;i++){
  const n=JSON.stringify(records[i]).length+1;
  if(i>from&&size+n>maxRaw){bounds.push([from,i]);from=i;size=0;}
  size+=n;
 }
 if(from<records.length)bounds.push([from,records.length]);
 return bounds;
}

const segmentName=(index,digest)=>`segments/seg-${String(index).padStart(6,'0')}-${digest.slice(0,12)}.json`;
const SEGMENT_FILE=/^seg-\d{6}(-[0-9a-f]{12})?\.json(\.tmp)?$/;

async function saveIfChanged(file,text){
 let existing=null;try{existing=await readFile(file,'utf8');}catch{}
 if(existing===text)return false;
 await mkdir(path.dirname(file),{recursive:true});
 await writeFile(file+'.tmp',text);await rename(file+'.tmp',file);return true;
}

/** Manifest + rehydrated snapshot from disk, or null when no store exists. */
export async function readTrackerStore(dataDir){
 let manifest;
 let manifestText;
 try{manifestText=await readFile(path.join(dataDir,STORE_DIR,'manifest.json'),'utf8');}catch(error){if(error.code==='ENOENT')return null;throw error;}
 manifest=JSON.parse(manifestText); // a truncated or corrupt manifest must raise, never look like a fresh store
 const segments=[];
 for(const s of manifest.segments){
  const text=await readFile(path.join(dataDir,STORE_DIR,s.file),'utf8');
  if(sha(text)!==s.sha256)throw new Error('Tracker segment '+s.file+' does not match its manifest checksum');
  segments.push(JSON.parse(text));
 }
 return {manifest,snapshot:rehydrate(manifest,segments)};
}

/** The tracker snapshot in the legacy single-file shape: segmented store first, else the legacy file. */
export async function loadTrackerSnapshot(dataDir){
 const store=await readTrackerStore(dataDir);
 if(store)return store.snapshot;
 let text;
 try{text=await readFile(path.join(dataDir,LEGACY_FILE),'utf8');}catch(error){
  if(error.code==='ENOENT')return null; // genuinely fresh: nothing was ever stored
  throw error;
 }
 // A present-but-unusable file must never be treated as an empty tracker: that would re-freeze
 // every prediction. Only a valid v1 file or a fresh checkout may start the log.
 const legacy=JSON.parse(text);
 if(legacy.schema_version===1&&Array.isArray(legacy.records))return legacy;
 throw new Error(legacy.schema_version===2?'The public tracker moved to '+STORE_DIR+'/manifest.json but that manifest is missing; refusing to start an empty tracker':'Unrecognized public tracker file; refusing to start an empty tracker');
}

export async function writeTrackerStore({dataDir,snapshot,maxRaw=MAX_RAW_SEGMENT_BYTES}){
 if(snapshot.schema_version!==1||!Array.isArray(snapshot.records))throw new Error('Refusing to store a non-v1 tracker snapshot');
 const existing=await readTrackerStore(dataDir),records=snapshot.records;
 let sealed=0,sealedSegments=[];
 if(existing){
  const old=existing.snapshot.records;
  if(records.length<old.length)throw new Error(`Tracker would shrink from ${old.length} to ${records.length} records; refusing to write`);
  for(let i=0;i<old.length;i++){
   if(JSON.stringify(old[i])!==JSON.stringify(records[i]))throw new Error(`Stored tracker record ${i} (${old[i]?.id}) changed; the store is append-only, refusing to write`);
  }
  sealedSegments=existing.manifest.segments.slice(0,-1);
  sealed=sealedSegments.reduce((n,s)=>n+s.records,0);
 }
 const bounds=planSegments(records,sealed,maxRaw),entries=[...sealedSegments],writes=[];
 bounds.forEach(([from,to],n)=>{
  const index=sealedSegments.length+n+1,slice=records.slice(from,to),{dict,records:encoded}=internRecords(slice);
  const segment={schema_version:1,layout:LAYOUT,index,first_record:from,dict,records:encoded};
  // Lossless proof for this segment, before anything touches disk.
  const back=expandSegment(JSON.parse(JSON.stringify(segment)));
  for(let i=0;i<slice.length;i++)if(JSON.stringify(back[i])!==JSON.stringify(slice[i]))throw new Error(`Segment ${index} record ${from+i} did not round-trip`);
  const text=JSON.stringify(segment),bytes=Buffer.byteLength(text);
  if(bytes>MAX_FILE_BYTES)throw new Error(`Tracker segment ${index} is ${bytes} bytes, over the ${MAX_FILE_BYTES} limit; refusing to write`);
  if(bytes>WARN_FILE_BYTES)console.warn(`Tracker segment ${index} is ${bytes} bytes`);
  const file=segmentName(index,sha(text));
  writes.push([file,text]);
  entries.push({file,index,first_record:from,records:to-from,raw_bytes:slice.reduce((s,r)=>s+JSON.stringify(r).length+1,0),bytes,sha256:sha(text),sealed:false,first_observed_at:slice[0]?.observed_at??null,last_observed_at:slice.at(-1)?.observed_at??null});
 });
 entries.forEach((e,i)=>{e.sealed=i<entries.length-1;});
 const summary={};
 for(const k of Object.keys(snapshot))if(k!=='records')summary[k]=snapshot[k];
 const manifest={schema_version:1,layout:LAYOUT,generated_at:snapshot.generated_at??null,total_records:records.length,
  top_level_keys:Object.keys(snapshot),summary,
  segments:entries.map(({file,index,first_record,records:n,raw_bytes,bytes,sha256,sealed,first_observed_at,last_observed_at})=>({file,index,first_record,records:n,raw_bytes,bytes,sha256,sealed,first_observed_at,last_observed_at}))};
 const manifestText=JSON.stringify(manifest),manifestBytes=Buffer.byteLength(manifestText);
 if(manifestBytes>MAX_FILE_BYTES)throw new Error('Tracker manifest is '+manifestBytes+' bytes, over the limit');
 let rewritten=0;
 for(const [file,text] of writes)if(await saveIfChanged(path.join(dataDir,STORE_DIR,file),text))rewritten++;
 await saveIfChanged(path.join(dataDir,STORE_DIR,'manifest.json'),manifestText); // last: everything it references already exists
 // Only now is it safe to drop superseded open-segment versions and temp debris (never anything the manifest references).
 const keep=new Set(entries.map(e=>path.basename(e.file)));let removed=0;
 try{for(const name of await readdir(path.join(dataDir,STORE_DIR,'segments')))if(SEGMENT_FILE.test(name)&&!keep.has(name)){await unlink(path.join(dataDir,STORE_DIR,'segments',name));removed++;}}catch(error){if(error.code!=='ENOENT')throw error;}
 return {total:records.length,segments:entries.length,rewritten_segments:rewritten,removed_superseded:removed,new_records:records.length-(existing?existing.snapshot.records.length:0),
  largest_segment_bytes:Math.max(...entries.map(e=>e.bytes)),manifest_bytes:manifestBytes};
}

/** Replace the legacy single file with a v2 tombstone so a reader that was missed fails loudly, never silently stale. */
export async function writeLegacyTombstone(dataDir){
 const file=path.join(dataDir,LEGACY_FILE);
 let legacy;try{legacy=JSON.parse(await readFile(file,'utf8'));}catch{return false;}
 if(legacy.schema_version!==1)return false; // already a tombstone
 const body={schema_version:2,moved_to:STORE_DIR+'/manifest.json',layout:LAYOUT,generated_at:legacy.generated_at??null,
  note:'The public tracker is stored as immutable segments. Load it with scripts/tracker_store.mjs (Node), scripts/tracker_store.py (Python) or shared/tracker-store.mjs (browser).'};
 await writeFile(file+'.tmp',JSON.stringify(body));await rename(file+'.tmp',file);return true;
}

// Rollback/export helper: `node scripts/tracker_store.mjs export [dataDir] > data/public_tracker.json`
// writes the byte-identical legacy single file, including every record appended since migration.
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)&&process.argv[2]==='export'){
 const dataDir=path.resolve(process.argv[3]||path.join(path.dirname(fileURLToPath(import.meta.url)),'..','data'));
 const snapshot=await loadTrackerSnapshot(dataDir);
 if(!snapshot)throw new Error('No public tracker found in '+dataDir);
 process.stdout.write(JSON.stringify(snapshot));
}
