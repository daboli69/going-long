const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../shared/live-snapshot.js'),'utf8');
function loader(fetch){const context=vm.createContext({fetch,AbortSignal});vm.runInContext(source,context);return context.GoingLiveSnapshot.load;}

test('consumer pages read data refreshes independently of their packaged deployment',async()=>{
 const calls=[],load=loader(async(url,options)=>{calls.push(url);assert.equal(options.cache,'no-cache');return Response.json({generated_at:'new'});});
 assert.equal((await load('signal_archive/2026-10-18.json')).generated_at,'new');
 assert.deepEqual(calls,['/api/snapshot?file=signal_archive%2F2026-10-18.json']);
 for(const page of ['players','results']){
  const html=fs.readFileSync(path.join(__dirname,`../apps/${page}/index.html`),'utf8');
  assert.ok(html.indexOf('live-snapshot.js')<html.indexOf(page+'.js'));
 }
});

test('snapshot transport/JSON failures try the packaged copy and exhaust failures explicitly',async()=>{
 for(const failure of [()=>{throw Error('offline');},()=>new Response('',{status:503}),()=>new Response('{bad')]){
  const calls=[],load=loader(async url=>{calls.push(url);return calls.length===1?failure():Response.json({saved:true});});
  assert.equal((await load('nfl_roster.json')).saved,true);
  assert.deepEqual(calls,['/api/snapshot?file=nfl_roster.json','/data/nfl_roster.json']);
 }
 await assert.rejects(loader(async()=>new Response('',{status:503}))('history.json'),/unavailable/);
});
