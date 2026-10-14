const test=require('node:test'),assert=require('node:assert/strict');
const {gzipSync}=require('node:zlib'),{createHash}=require('node:crypto');
const hash=x=>createHash('sha256').update(x).digest('hex');
const pack=x=>{const raw=Buffer.from(JSON.stringify(x));return {encoding:'gzip-base64-v1',sha256:hash(raw),data:gzipSync(raw).toString('base64')};};
test('Large private inputs cross the wire compressed with exact original content hash',async()=>{
 const {decodePrivateUpload}=await import('../server/fp-upload.mjs'),data={note:'x'.repeat(7_500_000)},envelope=pack(data);
 assert.ok(Buffer.byteLength(JSON.stringify(envelope))<4_000_000);const decoded=decodePrivateUpload(envelope);
 assert.deepEqual(decoded.data,data);assert.equal(decoded.inputSha256,hash(Buffer.from(JSON.stringify(data))));
 assert.deepEqual(decodePrivateUpload('{"legacy":true}').data,{legacy:true});
});
test('Malformed, corrupted, oversized and expansion-bomb uploads fail closed',async()=>{
 const {decodePrivateUpload}=await import('../server/fp-upload.mjs');
 for(const body of [{...pack({a:1}),sha256:'0'.repeat(64)},{...pack({a:1}),data:'bad%base64'},{...pack({a:1}),encoding:'zip'},{...pack({a:1}),extra:true},'{invalid'])assert.throws(()=>decodePrivateUpload(body),e=>e.status===400);
 assert.throws(()=>decodePrivateUpload('x'.repeat(4_000_001)),e=>e.status===413);
 assert.throws(()=>decodePrivateUpload(pack({note:'x'.repeat(8_000_001)})),e=>e.status===413);
});
test('Ingest authenticates before expansion and acknowledges the exact uploaded bytes',async()=>{
 const {default:handler}=await import('../api/fp-ingest.mjs');
 const keys=['GOING_FP_INGEST_TOKEN','SUPABASE_URL','SUPABASE_SECRET_KEY'],old=Object.fromEntries(keys.map(k=>[k,process.env[k]])),fetchBefore=global.fetch;
 const token='a'.repeat(32);process.env.GOING_FP_INGEST_TOKEN=token;process.env.SUPABASE_URL='https://example.supabase.co';process.env.SUPABASE_SECRET_KEY='sb_secret_fixture_only';
 let calls=0;global.fetch=async()=>{calls++;return {ok:true};};
 const run=async(body,authorization)=>{let result;const res={setHeader(){},end(s){result=JSON.parse(s);}};await handler({method:'POST',headers:{authorization},body},res);return {status:res.statusCode,result};};
 try{
  assert.equal((await run(pack({note:'x'.repeat(8_000_001)}),'Bearer wrong')).status,401);assert.equal(calls,0);
  const data={schema:'going-private-fp-inputs-v1',licensed:true,season:2026,prediction_week:6,datasets:[{table:'test',season:2026,status:'accepted',scope:'prior_week',observed_week:5,known_at:'2026-10-14T00:00:00Z',exported_at:'2026-10-14T00:00:00Z',columns:['NOTE'],records:[{NOTE:'x'.repeat(7_000_000)}]}]};
  const envelope=pack(data),r=await run(envelope,'Bearer '+token);assert.equal(r.status,200);assert.equal(r.result.inputSha256,envelope.sha256);assert.equal(r.result.datasets,1);assert.equal(calls,1);
  assert.equal((await run({...envelope,sha256:'0'.repeat(64)},'Bearer '+token)).status,400);assert.equal(calls,1);
 }finally{global.fetch=fetchBefore;for(const k of keys){if(old[k]===undefined)delete process.env[k];else process.env[k]=old[k];}}
});
