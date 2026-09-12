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

test('Shared baseball snapshots allow only public assets and coalesce requests',async()=>{
 const {default:handler}=await import('../api/yard-snapshot.mjs');const before=global.fetch;let calls=0;
 try{global.fetch=async url=>{calls++;assert.equal(url,'https://raw.githubusercontent.com/daboli69/hr-board/main/docs/board.json');return Response.json({players:[]});};
  const bad=response();await handler({method:'GET',url:'/api/yard-snapshot?file=../secret'},bad);assert.equal(bad.statusCode,400);assert.equal(calls,0);
  const a=response(),b=response();await Promise.all([handler({method:'GET',url:'/api/yard-snapshot?file=board.json'},a),handler({method:'GET',url:'/api/yard-snapshot?file=board.json'},b)]);assert.equal(calls,1);assert.equal(a.statusCode,200);assert.deepEqual(JSON.parse(b.body),{players:[]});
 }finally{global.fetch=before;}
});
