const {test}=require('node:test');
const assert=require('node:assert/strict');

test('Worker serves fresh roster and research snapshots through the deployment allowlist',async()=>{
  const {default:worker}=await import('../server/worker.mjs');
  const {isLiveSnapshot}=await import('../server/public-snapshots.mjs');
  const original=global.fetch,calls=[];
  const env={ASSETS:{fetch:async()=>assert.fail('Unexpected packaged fallback')}};
  global.fetch=async url=>{calls.push(url);return Response.json({receipt:'fresh-public-fixture'});};
  try{
    for(const file of ['nfl_roster.json','dfs_team_touchdowns.json','going_score.json','opportunities.json','charts/calibration.json','public_tracker/manifest.json']){
      assert.ok(isLiveSnapshot(file));
      const response=await worker.fetch(new Request('https://worker.test/api/snapshot?file='+encodeURIComponent(file)),env,{});
      assert.equal(response.status,200);assert.equal(response.headers.get('X-Snapshot-Source'),'nightly');
      assert.deepEqual(await response.json(),{receipt:'fresh-public-fixture'});
      assert.ok(calls.at(-1).endsWith('/data/'+file));
    }
    const before=calls.length;
    for(const file of ['../secret.json','private/model.json','charts/../../secret.json','nfl_roster.json/extra','']){
      const response=await worker.fetch(new Request('https://worker.test/api/snapshot?file='+encodeURIComponent(file)),env,{});
      assert.equal(response.status,400);
    }
    assert.equal(calls.length,before);
  }finally{global.fetch=original;}
});
