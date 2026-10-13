const {test}=require('node:test'),assert=require('node:assert/strict');
const fixture=()=>({schema:'going-private-fp-inputs-v1',licensed:true,season:2026,prediction_week:6,datasets:[{table:'rushing_bell_cow',season:2026,status:'accepted',scope:'prior_week',observed_week:5,known_at:'2026-10-13T20:00:00Z',exported_at:'2026-10-13T19:00:00Z',columns:['XFP'],records:[{XFP:10}]}]});
test('private writer rejects missing/wrong auth and never serves licensed GET data',async()=>{
 const m=await import('../server/fp-input-store.mjs');assert.equal(m.authorized('Bearer x','x'),false);assert.equal(m.authorized('Bearer '+'x'.repeat(32),'x'.repeat(32)),true);assert.equal(m.authorized('Bearer '+'y'.repeat(32),'x'.repeat(32)),false);
 const {default:handler}=await import('../api/fp-ingest.mjs');let value;const res={setHeader(){},end(s){value=JSON.parse(s);}};await handler({method:'GET',headers:{}},res);assert.equal(res.statusCode,405);assert.equal(value.datasets,undefined);
});
test('private upload uses authenticated service storage, returns metadata and withholds wrong-period/late features',async()=>{
 const m=await import('../server/fp-input-store.mjs'),d=fixture(),env={SUPABASE_URL:'https://example.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'fixture-key'};
 let request;const fetchImpl=async(url,options)=>{request={url:String(url),options};return {ok:true,json:async()=>d};};
 const r=await m.writePrivateInputs(d,{env,fetchImpl});assert.deepEqual(r,{season:2026,week:6,datasets:1});assert.match(request.url,/going-fp-private/);assert.equal(request.options.headers.Authorization,'Bearer fixture-key');
 assert.equal((await m.readPrivateInputs({season:2026,week:6,knownBy:'2026-10-13T19:30:00Z'},{env,fetchImpl})).length,0);
 await assert.rejects(m.readPrivateInputs({season:2026,week:7,knownBy:'2026-10-14T00:00:00Z'},{env,fetchImpl}),/period/);
 await assert.rejects(m.writePrivateInputs(d,{env:{},fetchImpl}),/not configured/);
});
test('malformed or mixed period data cannot overwrite private inputs',async()=>{
 const m=await import('../server/fp-input-store.mjs');for(const change of [d=>d.datasets[0].season=2025,d=>d.datasets[0].observed_week=6,d=>d.datasets[0].exported_at='bad',d=>d.licensed=false]){const d=fixture();change(d);assert.throws(()=>m.validateInputs(d));}
});
