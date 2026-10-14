const test=require('node:test'),assert=require('node:assert/strict');
const {gzipSync}=require('node:zlib'),{createHash}=require('node:crypto');
const owner='11111111-1111-1111-1111-111111111111',id='a'.repeat(64);
const sha=x=>createHash('sha256').update(x).digest('hex');
const body=JSON.stringify({actionable:true,note:'Jos\u00e9\t\\\n'}).replaceAll('\\','\\\\');
const line=`${id}\t${owner}\tprediction\t2026-09-12 12:00:00+00\t2026-09-12 12:01:00+00\t${body}\n`;
function fixture({raw=line,patch={},missing=false}={}){
 const bytes=Buffer.from(raw),gzip=gzipSync(bytes),path=`${owner}/shards/prediction-2026-09-00000.copy.gz`;
 const part={path,owner_id:owner,kind:'prediction',rows:1,raw_bytes:bytes.length,gzip_bytes:gzip.length,raw_sha256:sha(bytes),gzip_sha256:sha(gzip),min_observed:Date.parse('2026-09-12T12:00:00Z')/1000,max_observed:Date.parse('2026-09-12T12:00:00Z')/1000,...patch};
 const manifest={schema:'going-journal-copy-v1',columns:['id','owner_id','kind','observed_at','received_at','payload'],rows:1,shards:[part]},calls=[];
 const client={storage:{from(bucket){assert.equal(bucket,'going-journal-private');return {async download(name){calls.push(name);return missing?{error:Error('offline')}:{data:new Blob([name.endsWith('manifest.json')?JSON.stringify(manifest):gzip])};}};}}};
 return {client,calls,manifest};
}
test('Private archive reads exact owner, validates checksums and restores COPY escapes',async()=>{
 const {createArchiveReader,parseCopyRow}=await import('../apps/validation/journal-archive.mjs');const f=fixture();
 const rows=await createArchiveReader(f.client,owner)('prediction','2026-09-01','2026-10-01');
 assert.equal(rows.length,1);assert.deepEqual(rows[0].payload,{actionable:true,note:'Jos\u00e9\t\\\n'});
 assert.equal(rows[0].received_at,'2026-09-12 12:01:00+00');assert.ok(f.calls.every(p=>p.startsWith(owner+'/')));
 assert.equal(parseCopyRow(line.trimEnd().replace('Jos\u00e9','Jos\\303\\251')).payload.note,'Jos\u00e9\t\\\n');
});
test('Unavailable history never becomes an empty successful result',async()=>{
 const {createArchiveReader}=await import('../apps/validation/journal-archive.mjs');await assert.rejects(createArchiveReader(fixture({missing:true}).client,owner)('prediction','2026-09-01','2026-10-01'),/incomplete results/);
});
test('Tampered checksum, path, owner, size, count and clock metadata fail closed',async()=>{
 const {createArchiveReader}=await import('../apps/validation/journal-archive.mjs');
 for(const patch of [{gzip_sha256:'0'.repeat(64)},{raw_sha256:'0'.repeat(64)},{path:'../manifest.json'},{owner_id:'other'},{raw_bytes:99999999},{rows:2},{min_observed:0}]){
  await assert.rejects(createArchiveReader(fixture({patch}).client,owner)('prediction','2026-09-01','2026-10-01'));
 }
});
test('Archive scans only overlapping kinds/intervals and filters followup associations',async()=>{
 const {createArchiveReader}=await import('../apps/validation/journal-archive.mjs');const f=fixture(),read=createArchiveReader(f.client,owner);
 assert.deepEqual(await read('closing','2026-09-01','2026-10-01'),[]);assert.equal(f.calls.length,1);
 assert.deepEqual(await read('prediction','2026-09-01','2026-10-01',{predictionIds:new Set(['other'])}),[]);
 assert.deepEqual(await read('prediction','2026-10-01','2026-11-01'),[]);assert.equal(f.calls.length,2);
});
test('Live/archive overlap deduplicates equivalent rows but rejects altered history',async()=>{
 const {mergeJournalRows}=await import('../apps/validation/journal-archive.mjs');
 const r={id,kind:'prediction',observed_at:'2026-09-12T12:00:00Z',payload:{b:2,a:1}},s={...r,observed_at:'2026-09-12 12:00:00+00',payload:{a:1,b:2}};
 assert.equal(mergeJournalRows([r],[s]).length,1);assert.throws(()=>mergeJournalRows([r],[{...s,payload:{a:9}}]),/conflict/);
});
