// Authenticated Storage SDK reads only. No public URLs, service key or browser persistence.
const BUCKET='going-journal-private',MAX=8*1024*1024;
const hex=bytes=>[...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');
const digest=async bytes=>hex(await crypto.subtle.digest('SHA-256',bytes));
const stamp=value=>typeof value==='string'?Date.parse(value.length>10?value.replace(' ','T').replace(/([+-]\d\d)$/,'$1:00'):value):NaN;
function field(value){
 if(value==='\\N')throw Error('Archive contains unexpected NULL');
 if(!value.includes('\\'))return value;
 const input=new TextEncoder().encode(value),out=[];
 for(let i=0;i<input.length;i++){
  let b=input[i];
  if(b===92){
   b=input[++i];if(b===undefined)throw Error('Invalid archive escape');
   if(b>=48&&b<=55){let oct=String.fromCharCode(b);while(oct.length<3&&input[i+1]>=48&&input[i+1]<=55)oct+=String.fromCharCode(input[++i]);b=parseInt(oct,8);}
   else if(b===120&&/[\da-f]/i.test(String.fromCharCode(input[i+1]||0))){let h=String.fromCharCode(input[++i]);if(/[\da-f]/i.test(String.fromCharCode(input[i+1]||0)))h+=String.fromCharCode(input[++i]);b=parseInt(h,16);}
   else b=({98:8,102:12,110:10,114:13,116:9,118:11})[b]??b;
  }
  out.push(b);
 }
 return new TextDecoder('utf-8',{fatal:true}).decode(new Uint8Array(out));
}
export function parseCopyRow(line){
 const fields=line.replace(/\r$/,'').split('\t');if(fields.length!==6)throw Error('Invalid archive row');
 const [id,owner_id,kind,observed_at,received_at,body]=fields.map(field);
 const payload=JSON.parse(body);
 if(!/^[a-f\d]{64}$/.test(id)||!Number.isFinite(stamp(observed_at))||!Number.isFinite(stamp(received_at))||!payload||Array.isArray(payload)||typeof payload!=='object')throw Error('Invalid archive record');
 return {id,owner_id,kind,observed_at,received_at,payload};
}
export function createArchiveReader(client,owner){
 if(!/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/.test(owner))throw Error('Invalid archive owner');
 let manifestPromise;
 const download=async path=>{
  const {data,error}=await client.storage.from(BUCKET).download(path);
  if(error||!data)throw Error('Private history archive unavailable; incomplete results will not be scored.');
  return data;
 };
 async function manifest(){
  if(!manifestPromise)manifestPromise=(async()=>{
   const blob=await download(`${owner}/manifest.json`);if(blob.size>2*1024*1024)throw Error('Archive manifest too large');
   const m=JSON.parse(await blob.text());
   if(m.schema!=='going-journal-copy-v1'||JSON.stringify(m.columns)!==JSON.stringify(['id','owner_id','kind','observed_at','received_at','payload'])||!Array.isArray(m.shards)||m.shards.length>10000)throw Error('Invalid archive manifest');
   const paths=new Set();let count=0;
   for(const p of m.shards){
    if(p.owner_id!==owner||!['quote','prediction','settlement','closing','reference','run','notification','arbitrage','inactive_report'].includes(p.kind)||!new RegExp(`^${owner}/shards/${p.kind}-\\d{4}-\\d{2}-\\d{5}\\.copy\\.gz$`).test(p.path)||paths.has(p.path)||!Number.isSafeInteger(p.rows)||p.rows<1||!Number.isSafeInteger(p.raw_bytes)||p.raw_bytes<1||p.raw_bytes>MAX||!Number.isSafeInteger(p.gzip_bytes)||p.gzip_bytes<1||p.gzip_bytes>MAX+65536||![p.raw_sha256,p.gzip_sha256].every(x=>/^[a-f\d]{64}$/.test(x))||!Number.isFinite(p.min_observed)||!Number.isFinite(p.max_observed)||p.min_observed>p.max_observed)throw Error('Invalid archive shard manifest');
    paths.add(p.path);count+=p.rows;
   }
   if(count!==m.rows)throw Error('Archive manifest row count mismatch');return m;
  })();
  return manifestPromise;
 }
 return async(kind,since,until,{predictionIds,eligiblePreview=false}={})=>{
  const start=stamp(since),end=stamp(until);if(!Number.isFinite(start)||!Number.isFinite(end)||start>end)throw Error('Invalid archive interval');
  const m=await manifest(),rows=[],seen=new Set(),preview=[];
  for(const p of m.shards.filter(p=>p.kind===kind&&p.max_observed*1000>=start&&p.min_observed*1000<=end)){
   const blob=await download(p.path);if(blob.size!==p.gzip_bytes)throw Error('Archive compressed size mismatch');
   const compressed=await blob.arrayBuffer();if(await digest(compressed)!==p.gzip_sha256)throw Error('Archive compressed checksum mismatch');
   const reader=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip')).getReader();const chunks=[];let length=0;
   try{while(true){const {done,value}=await reader.read();if(done)break;length+=value.byteLength;if(length>p.raw_bytes||length>MAX)throw Error('Archive expansion exceeds manifest');chunks.push(value);}}finally{await reader.cancel();}
   const raw=new Uint8Array(length);let offset=0;for(const chunk of chunks){raw.set(chunk,offset);offset+=chunk.length;}
   if(length!==p.raw_bytes||await digest(raw)!==p.raw_sha256)throw Error('Archive raw checksum mismatch');
   const text=new TextDecoder('utf-8',{fatal:true}).decode(raw);if(!text.endsWith('\n'))throw Error('Incomplete archive shard');
   const lines=text.slice(0,-1).split('\n');if(lines.length!==p.rows)throw Error('Archive row count mismatch');
   let min=Infinity,max=-Infinity;
   for(const line of lines){
    const r=parseCopyRow(line),time=stamp(r.observed_at);if(r.owner_id!==owner||r.kind!==kind)throw Error('Archive ownership/kind mismatch');
    min=Math.min(min,time/1000);max=Math.max(max,time/1000);
    if(time<start||time>end||predictionIds&&!predictionIds.has(r.payload.prediction_id))continue;
    if(seen.has(r.id))throw Error('Duplicate archived record');seen.add(r.id);
    if(kind==='prediction'&&eligiblePreview&&!r.payload.actionable&&!['all_model','all_projection','best_model','best_value'].includes(r.payload.tracking_group)){
     preview.push(r);preview.sort((a,b)=>stamp(b.observed_at)-stamp(a.observed_at)||a.id.localeCompare(b.id));if(preview.length>100)preview.pop();
    }else rows.push(r);
    if(rows.length>100000)throw Error('Too many historical records; choose a shorter review window.');
   }
   if(Math.abs(min-p.min_observed)>0.001||Math.abs(max-p.max_observed)>0.001)throw Error('Archive time bounds mismatch');
  }
  return [...rows,...preview];
 };
}

const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;
export function mergeJournalRows(...sources){
 const rows=new Map();
 for(const r of sources.flat()){
  const old=rows.get(r.id);
  if(old&&(old.kind!==r.kind||stamp(old.observed_at)!==stamp(r.observed_at)||JSON.stringify(canonical(old.payload))!==JSON.stringify(canonical(r.payload))))throw Error('Live/archive record conflict; incomplete results will not be scored.');
  rows.set(r.id,r);
 }
 return [...rows.values()].sort((a,b)=>stamp(b.observed_at)-stamp(a.observed_at)||a.id.localeCompare(b.id));
}
