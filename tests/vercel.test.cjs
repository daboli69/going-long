const {test}=require('node:test');
const assert=require('node:assert/strict');
function response(){return {statusCode:0,headers:{},setHeader(k,v){this.headers[k]=v;},end(body){this.body=body;}};}
test('Vercel route reads the server secret and caches successful upstream requests',async()=>{
 const {default:handler}=await import('../api/odds.mjs');
 const fetchBefore=global.fetch,keyBefore=process.env.PARLAY_API_KEY;let calls=0;
 try{
  delete process.env.PARLAY_API_KEY;let res=response();await handler({method:'GET',url:'/api/odds?sport=nfl'},res);assert.equal(res.statusCode,503);
  process.env.PARLAY_API_KEY='private-fixture';
  global.fetch=async(url,options)=>{calls++;assert.equal(options.headers['X-API-Key'],'private-fixture');return Response.json([]);};
  for(let i=0;i<2;i++){res=response();await handler({method:'GET',url:'/api/odds?sport=nfl'},res);assert.equal(res.statusCode,200);assert.ok(!res.body.includes('private-fixture'));assert.equal(res.headers['Cache-Control'],'no-store');assert.match(res.headers['Vercel-CDN-Cache-Control'],/s-maxage=/);}
  assert.equal(calls,4);
  res=response();await handler({method:'GET',url:'/api/odds?sport=__proto__'},res);assert.equal(res.statusCode,400);
  res=response();await handler({method:'POST',url:'/api/odds'},res);assert.equal(res.statusCode,405);
 }finally{global.fetch=fetchBefore;if(keyBefore===undefined)delete process.env.PARLAY_API_KEY;else process.env.PARLAY_API_KEY=keyBefore;}
});
test('Large Vercel JSON responses are compressed and decode correctly',async()=>{
 const {sendJson}=await import('../server/vercel-response.mjs');const {gunzipSync}=require('node:zlib');const res=response(),body={data:'a'.repeat(100000)};
 sendJson({headers:{'accept-encoding':'gzip, br'}},res,body,200,120);
 assert.equal(res.headers['Content-Encoding'],'gzip');assert.deepEqual(JSON.parse(gunzipSync(res.body)),body);
});
test('Vercel snapshot endpoint validates file paths and falls back during upstream outages',async()=>{
 const {default:handler}=await import('../api/snapshot.mjs');const before=global.fetch;
 try{global.fetch=async()=>{throw new Error('offline');};let res=response();await handler({method:'GET',url:'/api/snapshot?file=../../secret'},res);assert.equal(res.statusCode,400);
 res=response();await handler({method:'GET',url:'/api/snapshot?file=data.json'},res);assert.equal(res.statusCode,200);assert.equal(res.headers['X-Snapshot-Source'],'packaged');assert.ok(JSON.parse(res.body).betting);
 }finally{global.fetch=before;}
});

test('Every football loader snapshot can retrieve current upstream data without falling back',async()=>{
 const fs=require('node:fs'),path=require('node:path');
 const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
 const loader=html.match(/worker\.postMessage\((\[\[.*?\]\])\.map/);
 assert.ok(loader,'Football worker snapshot manifest must be discoverable');
 const files=[...loader[1].matchAll(/\['[^']+','([^']+)'\]/g)].map(m=>m[1]);
 assert.ok(files.includes('season_learning.json'));
 const {default:handler}=await import('../api/snapshot.mjs'),before=global.fetch;
 const generated_at='2026-10-02T17:00:00Z';let calls=0;
 try{
  global.fetch=async url=>{calls++;const file=String(url).split('/data/')[1];assert.ok(files.includes(file));return Response.json({file,generated_at});};
  for(const file of files){const res=response();await handler({method:'GET',url:'/api/snapshot?file='+encodeURIComponent(file)},res);
   assert.equal(res.statusCode,200,file);assert.equal(res.headers['X-Snapshot-Source'],'nightly',file);assert.deepEqual(JSON.parse(res.body),{file,generated_at});
  }
  assert.equal(calls,files.length);
  for(const file of ['../../secret','season_learning.json/../secret','unknown.json']){const res=response();await handler({method:'GET',url:'/api/snapshot?file='+encodeURIComponent(file)},res);assert.equal(res.statusCode,400,file);}
  assert.equal(calls,files.length,'Rejected paths must never reach upstream');
 }finally{global.fetch=before;}
});

test('Season learning retains its packaged timestamp when upstream is unavailable',async()=>{
 const fs=require('node:fs'),path=require('node:path');
 const packaged=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/season_learning.json'),'utf8'));
 const {default:handler}=await import('../api/snapshot.mjs'),before=global.fetch;
 try{
  global.fetch=async()=>{throw Error('offline');};
  const res=response();await handler({method:'GET',url:'/api/snapshot?file=season_learning.json'},res);
  assert.equal(res.statusCode,200);assert.equal(res.headers['X-Snapshot-Source'],'packaged');
  assert.ok(packaged.generated_at);assert.deepEqual(JSON.parse(res.body),packaged);
 }finally{global.fetch=before;}
});

test('Shared baseball snapshots allow only public assets and coalesce requests',async()=>{
 const {default:handler}=await import('../api/yard-snapshot.mjs');const before=global.fetch;let calls=0;
 try{global.fetch=async url=>{calls++;assert.equal(url,'https://raw.githubusercontent.com/daboli69/hr-board/main/docs/board.json');return Response.json({players:[]});};
  const bad=response();await handler({method:'GET',url:'/api/yard-snapshot?file=../secret'},bad);assert.equal(bad.statusCode,400);assert.equal(calls,0);
  const a=response(),b=response();await Promise.all([handler({method:'GET',url:'/api/yard-snapshot?file=board.json'},a),handler({method:'GET',url:'/api/yard-snapshot?file=board.json'},b)]);assert.equal(calls,1);assert.equal(a.statusCode,200);assert.deepEqual(JSON.parse(b.body),{players:[]});
 }finally{global.fetch=before;}
});

test('Validation config never emits a service-role key mistaken for a public key',async()=>{
 const {default:handler}=await import('../api/validation-config.mjs');const before=process.env.SUPABASE_PUBLISHABLE_KEY;
 try{process.env.SUPABASE_PUBLISHABLE_KEY='sb_secret_private';const res=response();handler({method:'GET'},res);assert.equal(JSON.parse(res.body).publishableKey,null);}finally{if(before===undefined)delete process.env.SUPABASE_PUBLISHABLE_KEY;else process.env.SUPABASE_PUBLISHABLE_KEY=before;}
});


test('Provider outages retain dated cache and suppress repeated credit-consuming failures',async t=>{
 const {default:handler}=await import('../api/odds.mjs');const before=global.fetch,key=process.env.PARLAY_API_KEY;
 const start=Date.now();t.mock.timers.enable({apis:['Date'],now:start});let calls=0;
 try{
  process.env.PARLAY_API_KEY='fixture';global.fetch=async()=>{calls++;return Response.json([]);};
  let res=response();await handler({method:'GET',url:'/api/odds?sport=ncaa'},res);
  const original=JSON.parse(res.body);assert.equal(res.statusCode,200);
  t.mock.timers.setTime(start+600001);global.fetch=async()=>{calls++;throw Error('offline');};
  res=response();await handler({method:'GET',url:'/api/odds?sport=ncaa'},res);
  assert.equal(res.statusCode,200);const saved=JSON.parse(res.body);assert.equal(saved.feed_status,'STALE');assert.equal(saved.refresh_status,'STALE');assert.equal(saved.generated_at,original.generated_at);assert.match(saved.feed_notice,/original timestamps/);
  const failedCalls=calls;res=response();await handler({method:'GET',url:'/api/odds?sport=ncaa'},res);assert.equal(calls,failedCalls);assert.equal(res.statusCode,200);
 }finally{global.fetch=before;if(key===undefined)delete process.env.PARLAY_API_KEY;else process.env.PARLAY_API_KEY=key;}
});
