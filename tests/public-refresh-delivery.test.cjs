const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
test('publication verification detects a successful push that still serves deployment-time data',async t=>{
 const {checkPublicRefresh}=await import('../scripts/check_public_refresh.mjs');
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'public-refresh-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 await fs.mkdir(path.join(root,'data'));await fs.writeFile(path.join(root,'data/nfl_roster.json'),JSON.stringify({observed:'new'}));
 const report={publication_paths:['data/nfl_roster.json','data/unknown.json','data/../private/key.json']};
 let calls=0;
 let result=await checkPublicRefresh({root,report,attempts:4,fetcher:async url=>{calls++;assert.match(url,/file=nfl_roster.json$/);return Response.json({observed:'old'});},sleep:async()=>{}});
 assert.equal(result.healthy,false);assert.equal(calls,4);assert.match(result.checks[0].error,/differs/);
 calls=0;result=await checkPublicRefresh({root,report,fetcher:async()=>Response.json({observed:++calls===1?'old':'new'},{headers:{'X-Snapshot-Source':'nightly'}}),sleep:async()=>{}});
 assert.equal(result.healthy,true);assert.equal(calls,2);assert.equal(result.checks[0].source,'nightly');
 assert.equal((await checkPublicRefresh({root,report:{publication_paths:[]},fetcher:()=>assert.fail('No changed snapshots')})).healthy,true);
});
