/* Lossless daily sharding for the multisport signal journal.
 *
 * data/signal_tracker.json keeps its path and schema but holds only the current window
 * (default 7 days) plus an `archive` index. Older records live, unchanged, in
 * data/signal_archive/<YYYY-MM-DD>.json (one file per observation day, UTC).
 * Writes UNION with what is already stored (id-keyed, incoming wins): a record can be
 * updated (e.g. an outcome attached) but is never dropped, and shard files are never deleted.
 */
import {readFile,writeFile,rename,readdir,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

export const LAYOUT='daily-shards-v1',ARCHIVE_DIR='signal_archive',DEFAULT_WINDOW_DAYS=7;
const day=r=>{const t=Date.parse(r?.observed_at);return Number.isFinite(t)?new Date(t).toISOString().slice(0,10):'undated';};
const sha=text=>createHash('sha256').update(text).digest('hex');

export function partitionRecords(records,{now=Date.now(),windowDays=DEFAULT_WINDOW_DAYS}={}){
 const cutoff=new Date(now-windowDays*86400000).toISOString().slice(0,10),current=[],shards=new Map();
 for(const r of records){
  const d=day(r);
  // Undated records cannot be placed on the timeline; keep them visible in the current file.
  if(d==='undated'||d>=cutoff){current.push(r);continue;}
  if(!shards.has(d))shards.set(d,[]);
  shards.get(d).push(r);
 }
 return {current,shards,cutoff};
}

async function readJson(file){return JSON.parse(await readFile(file,'utf8'));}

/** Every stored record: the current file plus all archive shards, in no meaningful order. */
export async function readSignalRecords(dataDir){
 let meta={},records=[];
 try{meta=await readJson(path.join(dataDir,'signal_tracker.json'));records=[...(meta.records||[])];}catch{}
 let names=[];
 try{names=(await readdir(path.join(dataDir,ARCHIVE_DIR))).filter(n=>/^\d{4}-\d{2}-\d{2}\.json$/.test(n)).sort();}catch{}
 for(const name of names){const shard=await readJson(path.join(dataDir,ARCHIVE_DIR,name));records.push(...(shard.records||[]));}
 return {meta,records};
}

async function saveIfChanged(file,text){
 let existing=null;try{existing=await readFile(file,'utf8');}catch{}
 if(existing===text)return false;
 await writeFile(file+'.tmp',text);await rename(file+'.tmp',file);return true;
}

export async function writeSignalTracker({dataDir,generated_at,sources,records,now=Date.now(),windowDays=DEFAULT_WINDOW_DAYS}){
 const stored=(await readSignalRecords(dataDir)).records,byId=new Map();
 for(const r of stored)byId.set(r.id,r);
 for(const r of records)byId.set(r.id,r); // incoming wins; nothing stored is dropped
 const {current,shards}=partitionRecords([...byId.values()],{now,windowDays});
 await mkdir(path.join(dataDir,ARCHIVE_DIR),{recursive:true});
 const index=[];let rewritten=0;
 for(const [date,rows] of [...shards].sort((a,b)=>a[0]<b[0]?1:-1)){
  const text=JSON.stringify({schema_version:1,date,records:rows});
  if(await saveIfChanged(path.join(dataDir,ARCHIVE_DIR,date+'.json'),text))rewritten++;
  index.push({date,file:`${ARCHIVE_DIR}/${date}.json`,records:rows.length,bytes:Buffer.byteLength(text),sha256:sha(text)});
 }
 const total=current.length+index.reduce((s,x)=>s+x.records,0);
 const body={schema_version:1,generated_at,sources,records:current,
  archive:{layout:LAYOUT,current_window_days:windowDays,current_records:current.length,archived_records:total-current.length,total_records:total,shards:index}};
 await saveIfChanged(path.join(dataDir,'signal_tracker.json'),JSON.stringify(body));
 return {total,current:current.length,archived:total-current.length,shards:index.length,rewritten_shards:rewritten};
}
