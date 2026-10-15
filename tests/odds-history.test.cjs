const {test}=require('node:test'),assert=require('node:assert/strict');
const {gzipSync}=require('node:zlib'),{createHash}=require('node:crypto');
const env={SUPABASE_URL:'https://fixture.supabase.co',SUPABASE_SECRET_KEY:'sb_secret_fixture'};
const hex='a'.repeat(64),clock='2025-10-12T16:00:00Z';
const quote=()=>({id:'quote',event_id:'event',snapshot_at:clock,quote_at:'2025-10-12T15:59:00Z',kickoff:'2025-10-12T17:00:00Z',price:-110,book:'pinnacle',market:'spreads',side:'Home',line:-3.5});
const event=()=>({schema:'going-odds-history-event-v1',id:'event',quotes:[quote()]});
const pack=(kind,data)=>{const b=gzipSync(JSON.stringify(data));return {schema:'going-odds-history-upload-v1',kind,sha256:createHash('sha256').update(b).digest('hex'),gzip:b.toString('base64')};};
const stored=p=>Buffer.from(JSON.stringify({schema:'going-odds-history-object-v1',sha256:p.sha256,gzip:p.gzip}));
const index=(digest)=>({schema:'going-odds-history-index-v1',historicalOnly:true,scheduleVerified:true,scheduleSha256:hex,archiveId:hex,generatedAt:'2026-01-01T00:00:00Z',cutoff:'2025-12-31T00:00:00Z',credits:30,quotes:1,receiptsSha256:hex,events:[{id:'event',sha256:digest,home:'Home',away:'Away',kickoff:'2025-10-12T17:00:00Z',quotes:1}]});
test('historical storage refuses corrupt, live, mixed-identity and post-kickoff records',async()=>{
 const {decodeObject}=await import('../server/odds-history-store.mjs');
 assert.equal(decodeObject(pack('event',event())).parsed.quotes.length,1);
 for(const change of [q=>q.snapshot_at=new Date().toISOString(),q=>q.quote_at='2025-10-12T16:01:00Z',q=>q.kickoff=clock,q=>q.event_id='other',q=>q.price=-99,q=>q.quote_at='2025-10-12T16:00:00']){const e=event();change(e.quotes[0]);assert.throws(()=>decodeObject(pack('event',e)));}
 const p=pack('event',event());p.sha256=hex;assert.throws(()=>decodeObject(p),/checksum/);
 assert.throws(()=>decodeObject(pack('index',{...index(hex),quotes:2})),/totals/);
});
test('only historical acquisition receipts can be backed up; keys are refused',async()=>{
 const {decodeObject}=await import('../server/odds-history-store.mjs');
 const receipt={schema:'going-odds-history-receipts-v1',requests:[{id:hex,rawGzipSha256:hex,path:'/v4/historical/sports/americanfootball_nfl/odds',params:{date:clock},charge:30,snapshot_at:clock}]};
 assert.ok(decodeObject(pack('receipts',receipt)));
 receipt.requests[0].params.apiKey='private';assert.throws(()=>decodeObject(pack('receipts',receipt)));
 delete receipt.requests[0].params.apiKey;receipt.requests[0].path='/v4/sports/americanfootball_nfl/odds';assert.throws(()=>decodeObject(pack('receipts',receipt)));
});
test('immutable private storage uses opaque apikey, verifies duplicate content and blocks missing manifest references',async()=>{
 const {writeHistory}=await import('../server/odds-history-store.mjs');const upload=pack('event',event());let writes=0;
 const fetchImpl=async(url,o)=>{assert.match(String(url),/^https:\/\/fixture.supabase.co\/storage\/v1\/object\/going-fp-private\/odds-history\/v1\//);assert.equal(o.headers.apikey,env.SUPABASE_SECRET_KEY);assert.equal(o.headers.Authorization,undefined);if(o.method==='POST'){writes++;assert.equal(o.headers['x-upsert'],'false');assert.equal(o.headers['Content-Type'],'application/json');assert.equal(JSON.parse(o.body).gzip,upload.gzip);return {ok:false,status:409};}return {ok:true,arrayBuffer:async()=>stored(upload)};};
 assert.equal((await writeHistory(upload,{env,fetchImpl})).sha256,upload.sha256);assert.equal(writes,1);
 await assert.rejects(writeHistory(upload,{env,fetchImpl:async()=>({ok:false,status:409})}),/conflict/);
 let didWrite=false;
 await assert.rejects(writeHistory(pack('index',index(upload.sha256)),{env,fetchImpl:async(u,o)=>{if(o.method==='POST')didWrite=true;return {ok:false,status:404,json:async()=>({statusCode:'404'})};}}),/receipts missing/);
 assert.equal(didWrite,false);
});
test('private history reader filters exact market and has no provider calls',async()=>{
 const {readHistory}=await import('../server/odds-history-store.mjs'),e=event();e.quotes.push({...quote(),id:'other',market:'totals',side:'Over',line:45.5});const upload=pack('event',e),idx=index(upload.sha256);idx.quotes=2;idx.events[0].quotes=2;
 const fetchImpl=async(url)=>{assert.match(String(url),/\.supabase\.co\/storage\//);return {ok:true,arrayBuffer:async()=>String(url).endsWith('index.json')?stored(pack('index',idx)):stored(upload)};};
 const result=await readHistory('event','totals',{env,fetchImpl});assert.equal(result.quotes.length,1);assert.equal(result.quotes[0].market,'totals');assert.equal(result.historicalOnly,true);
 await assert.rejects(readHistory('not-present',null,{env,fetchImpl}),/Unknown/);
});
test('index cannot regress and upstream storage errors cannot masquerade as an empty archive',async()=>{
 const {writeHistory}=await import('../server/odds-history-store.mjs'),old=index(hex);old.generatedAt='2026-02-01T00:00:00Z';
 await assert.rejects(writeHistory(pack('index',index(hex)),{env,fetchImpl:async()=>({ok:true,arrayBuffer:async()=>stored(pack('index',old))})}),/regression/);
 await assert.rejects(writeHistory(pack('index',index(hex)),{env,fetchImpl:async()=>({ok:false,status:403,json:async()=>({})})}),/unavailable/);
});
test('API protects all historical reads and writes and has no public caching',async()=>{
 const {default:handler}=await import('../api/odds-history.mjs');
 for(const method of ['GET','POST','DELETE']){let body;const headers={},res={setHeader(k,v){headers[k]=v;},end(s){body=JSON.parse(s);}};await handler({method,headers:{}},res);assert.equal(res.statusCode,method==='DELETE'?405:401);assert.equal(headers['Cache-Control'],'private, no-store');assert.equal(body.quotes,undefined);}
});
test('local historical route cannot fall through to the current-odds provider middleware',async()=>{
 const {default:config}=await import('../vite.config.mjs');let middleware;
 config.plugins.find(p=>p.name==='going-long-local-odds').configureServer({middlewares:{use(f){middleware=f;}}});
 let passed=0;await middleware({url:'/api/odds-history?event=fixture'},null,()=>{passed++;});assert.equal(passed,1);
});
