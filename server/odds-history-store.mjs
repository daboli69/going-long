// Private saved history only. This module has no sportsbook API client or key.
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {awareTime} from './fp-input-store.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const bad=message=>{throw Error(message);};
const hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const eventId=x=>typeof x==='string'&&/^[a-zA-Z0-9_-]{1,80}$/.test(x);
function connection(env){
 const url=new URL(env.SUPABASE_URL||'https://invalid.invalid'),key=env.SUPABASE_SECRET_KEY||env.SUPABASE_SERVICE_ROLE_KEY;
 if(url.protocol!=='https:'||!url.hostname.endsWith('.supabase.co')||!key||key.startsWith('sb_publishable_'))bad('Private storage unavailable');
 return {base:new URL('/storage/v1/object/going-fp-private/odds-history/v1/',url),headers:{apikey:key,...(key.startsWith('sb_secret_')?{}:{Authorization:'Bearer '+key})}};
}
function validateIndex(data){
 if(data?.schema!=='going-odds-history-index-v1'||data.historicalOnly!==true||!hex(data.archiveId)||!Number.isFinite(awareTime(data.generatedAt))||!Number.isFinite(awareTime(data.cutoff))||awareTime(data.cutoff)>Date.now()-86400000||!Number.isInteger(data.credits)||data.credits<0||data.credits>20000||!Array.isArray(data.events)||data.events.length>5000)bad('Invalid historical index');
 const seen=new Set();
 for(const e of data.events){
  if(!eventId(e.id)||seen.has(e.id)||!hex(e.sha256)||!Number.isFinite(awareTime(e.kickoff))||awareTime(e.kickoff)>awareTime(data.cutoff)||!Number.isInteger(e.quotes)||e.quotes<1||typeof e.home!=='string'||typeof e.away!=='string')bad('Invalid archived event');
  seen.add(e.id);
 }
 if(!hex(data.receiptsSha256)||!Number.isInteger(data.quotes)||data.quotes!==data.events.reduce((n,e)=>n+e.quotes,0))bad('Invalid historical totals or receipts');
 return data;
}
function validateReceipts(data){
 if(data?.schema!=='going-odds-history-receipts-v1'||!Array.isArray(data.requests)||data.requests.length>5000)bad('Invalid acquisition receipts');
 for(const r of data.requests){
  if(!hex(r.id)||!hex(r.rawGzipSha256)||!/^\/v4\/historical\/sports\/americanfootball_(nfl|ncaaf)\/(odds|events|events\/[a-zA-Z0-9_-]{1,80}\/odds)$/.test(r.path)||!r.params||Object.keys(r.params).some(k=>/key|token|secret/i.test(k))||!Number.isInteger(r.charge)||r.charge<0||r.charge>300||!Number.isFinite(awareTime(r.snapshot_at)))bad('Invalid acquisition receipt');
 }
 return data;
}
function validateEvent(data){
 if(data?.schema!=='going-odds-history-event-v1'||!eventId(data.id)||!Array.isArray(data.quotes)||data.quotes.length>50000)bad('Invalid historical event');
 for(const q of data.quotes){
  if(q.event_id!==data.id||!Number.isFinite(awareTime(q.snapshot_at))||!Number.isFinite(awareTime(q.quote_at))||!Number.isFinite(awareTime(q.kickoff))||awareTime(q.snapshot_at)>=Date.now()-86400000||awareTime(q.quote_at)>awareTime(q.snapshot_at)||awareTime(q.snapshot_at)>=awareTime(q.kickoff)||!Number.isFinite(q.price)||Math.abs(q.price)<100||typeof q.market!=='string'||typeof q.book!=='string'||typeof q.side!=='string')bad('Invalid historical quote');
 }
 return data;
}
export function decodeObject(data){
 if(data?.schema!=='going-odds-history-upload-v1'||!['raw','event','index','receipts'].includes(data.kind)||!hex(data.sha256)||typeof data.gzip!=='string'||data.gzip.length>3_800_000||!/^[A-Za-z0-9+/]+={0,2}$/.test(data.gzip))bad('Invalid history upload');
 const bytes=Buffer.from(data.gzip,'base64');
 if(bytes.toString('base64')!==data.gzip||sha(bytes)!==data.sha256)bad('Historical checksum mismatch');
 let parsed;try{parsed=JSON.parse(gunzipSync(bytes,{maxOutputLength:8_000_000}));}catch{bad('Invalid compressed history');}
 if(data.kind==='index')validateIndex(parsed);
 if(data.kind==='event')validateEvent(parsed);
 if(data.kind==='receipts')validateReceipts(parsed);
 if(data.kind==='raw'&&(!Number.isFinite(awareTime(parsed.timestamp))||awareTime(parsed.timestamp)>=Date.now()-86400000||!parsed.data))bad('Invalid raw historical snapshot');
 return {bytes,parsed,path:data.kind==='index'?'index.json':`${data.kind}/${data.sha256}.json`};
}
function storedBytes(wire,path){
 if(wire.length>4_000_000)bad('Historical object too large');
 let value;try{value=JSON.parse(wire.toString());}catch{bad('Invalid historical storage envelope');}
 if(value?.schema!=='going-odds-history-object-v1'||!hex(value.sha256)||typeof value.gzip!=='string'||value.gzip.length>3_800_000)bad('Invalid historical storage envelope');
 const bytes=Buffer.from(value.gzip,'base64');
 if(bytes.toString('base64')!==value.gzip||sha(bytes)!==value.sha256||(path!=='index.json'&&value.sha256!==path.split('/')[1].split('.')[0]))bad('Historical object checksum mismatch');
 return bytes;
}
async function read(path,{env=process.env,fetchImpl=fetch}={}){
 const c=connection(env),response=await fetchImpl(new URL(path,c.base),{headers:c.headers,signal:AbortSignal.timeout(15000)});
 if(!response.ok){let detail;try{detail=await response.json();}catch{}const e=Error('Historical archive unavailable');e.notFound=response.status===404||String(detail?.statusCode)==='404';throw e;}
 const bytes=storedBytes(Buffer.from(await response.arrayBuffer()),path);
 return JSON.parse(gunzipSync(bytes,{maxOutputLength:8_000_000}));
}
export async function writeHistory(data,options={}){
 const object=decodeObject(data),c=connection(options.env||process.env),fetchImpl=options.fetchImpl||fetch;
 if(data.kind==='index'){
  let previous;try{previous=await read('index.json',options);}catch(error){if(!error.notFound)throw error;}
  if(previous&&previous.archiveId===object.parsed.archiveId&&(previous.quotes>object.parsed.quotes||awareTime(previous.generatedAt)>awareTime(object.parsed.generatedAt)))bad('Historical index regression refused');
  // Verify every referenced event exists before publishing the manifest pointer.
  const receipts=await fetchImpl(new URL(`receipts/${object.parsed.receiptsSha256}.json`,c.base),{method:'HEAD',headers:c.headers,signal:AbortSignal.timeout(10000)});
  if(!receipts.ok)bad('Historical acquisition receipts missing');
  for(let offset=0;offset<object.parsed.events.length;offset+=16){
   await Promise.all(object.parsed.events.slice(offset,offset+16).map(async event=>{
    const r=await fetchImpl(new URL(`event/${event.sha256}.json`,c.base),{method:'HEAD',headers:c.headers,signal:AbortSignal.timeout(10000)});
    if(!r.ok)bad('Historical manifest references missing events');
   }));
  }
 }
 // Existing owner-protected bucket deliberately allows application/json only.
 // Preserve the exact gzip bytes in base64 instead of loosening bucket policy.
 const wire=JSON.stringify({schema:'going-odds-history-object-v1',sha256:data.sha256,gzip:data.gzip});
 const r=await fetchImpl(new URL(object.path,c.base),{method:'POST',headers:{...c.headers,'Content-Type':'application/json','x-upsert':data.kind==='index'?'true':'false'},body:wire,signal:AbortSignal.timeout(15000)});
 if(!r.ok){
  if(r.status!==400&&r.status!==409)bad('Historical storage write failed');
  // Immutable objects may already exist; verify content instead of trusting409.
  if(data.kind==='index')bad('Historical index write failed');
  const existing=await fetchImpl(new URL(object.path,c.base),{headers:c.headers,signal:AbortSignal.timeout(15000)});
  if(!existing.ok||sha(storedBytes(Buffer.from(await existing.arrayBuffer()),object.path))!==data.sha256)bad('Historical object conflict');
 }
 return {ok:true,sha256:data.sha256,bytes:object.bytes.length};
}
export async function readHistory(event,market,options={}){
 const index=validateIndex(await read('index.json',options));
 if(!event)return index;
 const entry=index.events.find(e=>e.id===event);if(!entry)bad('Unknown archived event');
 const data=validateEvent(await read(`event/${entry.sha256}.json`,options));
 if(data.id!==event||data.quotes.length!==entry.quotes)bad('Historical manifest/event mismatch');
 const book=options.book,offset=Number(options.offset||0);
 if(!Number.isInteger(offset)||offset<0||offset>50000)bad('Invalid historical page');
 const rows=data.quotes.filter(q=>(!market||q.market===market)&&(!book||q.book===book));
 return {historicalOnly:true,event:entry,markets:[...new Set(data.quotes.map(q=>q.market))],books:[...new Set(data.quotes.map(q=>q.book))],quotes:rows.slice(offset,offset+500),offset,total:rows.length};
}
