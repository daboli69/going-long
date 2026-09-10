const {test}=require('node:test');
const assert=require('node:assert/strict');
const future=new Date(Date.now()+86400000).toISOString();
const quote={player:'Josh Allen',bookmaker:'draftkings',bookmaker_title:'DraftKings',market_key:'player_passing_yards',line:249.5,over_price:-110,under_price:105,canonical_event_id:'event',commence_time:future,last_update:new Date().toISOString()};

test('Parlay flat quotes preserve alternative TD thresholds, identities and missing prices',async()=>{
  const {normalizeProps}=await import('../server/parlay.mjs');
  const rows=normalizeProps([quote,{...quote,market_key:'player_anytime_td',line:1.5,over_price:600,under_price:null},
    {...quote,market_key:'player_anytime_td',line:0}, {...quote,market_key:'player_first_touchdown'},
    {...quote,bookmaker:'prizepicks',dfs_normalized:true}, {...quote,commence_time:'invalid'},
    {...quote,bookmaker:'other',commence_time:null}]);
  assert.equal(rows.length,5);
  assert.equal(rows[0].market,'pass_yds');assert.equal(rows[0].underOdds,105);
  assert.equal(rows[1].line,1.5);assert.equal(rows[1].underOdds,null);assert.equal(rows[2].line,.5);
  assert.equal(rows[3].overOdds,null);assert.equal(rows[3].dfs,true);assert.equal(rows[4].kickoff,null);
  assert.equal(new Set(rows.map(r=>r.quoteKey)).size,5);
});
test('Parlay authenticates by header and rejects malformed upstream data',async()=>{
  const {fetchParlay}=await import('../server/parlay.mjs');const calls=[];
  const result=await fetchParlay('nfl','fixture-key',async(url,options)=>{
    calls.push({url,options});return Response.json(url.pathname.endsWith('/props')?[quote]:[]);
  });
  assert.equal(result.props.length,1);assert.equal(calls.length,2);
  for(const c of calls){assert.equal(c.url.origin,'https://parlay-api.com');assert.equal(c.options.headers['X-API-Key'],'fixture-key');assert.ok(!c.url.href.includes('fixture-key'));}
  assert.ok(calls.every(c=>c.url.pathname.includes('/americanfootball_nfl/')));
  await assert.rejects(fetchParlay('ncaa','fixture-key',async()=>Response.json({error:'bad'})),/Unexpected/);
});

test('NCAA ingestion requests only game spreads, totals and moneylines',async()=>{
  const {fetchParlay}=await import('../server/parlay.mjs');const urls=[];
  const result=await fetchParlay('ncaa','fixture-key',async url=>{urls.push(url);return Response.json([]);});
  assert.equal(urls.length,1);assert.ok(urls[0].pathname.endsWith('/americanfootball_ncaaf/odds'));
  assert.equal(urls[0].searchParams.get('markets'),'h2h,spreads,totals');assert.equal(result.props.length,0);
});
test('Server proxy validates requests, coalesces refreshes and never exposes the key',async()=>{
  const {oddsResponse}=await import('../server/worker.mjs');
  assert.equal((await oddsResponse(new Request('https://test/api/odds?sport=bad'),{})).status,400);
  assert.equal((await oddsResponse(new Request('https://test/api/odds',{method:'POST'}),{})).status,405);
  assert.equal((await oddsResponse(new Request('https://test/api/odds'),{})).status,503);
  const original=global.fetch;let calls=0;
  const oldCaches=global.caches;global.caches={open:async()=>{throw new Error('Cache unavailable');}};
  global.fetch=async(url,options)=>{calls++;assert.equal(options.headers['X-API-Key'],'fixture-key');return Response.json(url.pathname.endsWith('/props')?[quote]:[]);};
  try{
    const req=new Request('https://test/api/odds?sport=nfl');
    const responses=await Promise.all([oddsResponse(req,{PARLAY_API_KEY:'fixture-key'}),oddsResponse(req,{PARLAY_API_KEY:'fixture-key'})]);
    assert.equal(calls,2);
    for(const r of responses){assert.equal(r.status,200);assert.ok(!(await r.text()).includes('fixture-key'));}
    assert.equal((await oddsResponse(req,{PARLAY_API_KEY:'fixture-key'})).status,200);assert.equal(calls,2);
  }finally{global.fetch=original;global.caches=oldCaches;}
});

test('Hosted snapshots use an API route with allowlisted files and packaged fallback',async()=>{
  const {default:worker}=await import('../server/worker.mjs');const old=global.fetch;let calls=0;
  const env={ASSETS:{fetch:async(req)=>{assert.equal(new URL(req.url).pathname,'/data/ncaa_lines.json');return Response.json({saved:true});}}};
  try{
    global.fetch=async()=>{calls++;return Response.json({betting:{schema_version:1,profiles:{p:{}}}});};
    const result=await worker.fetch(new Request('https://test/api/snapshot?file=history.json'),env,{});
    assert.equal(result.headers.get('X-Snapshot-Source'),'nightly');assert.equal(calls,1);
    assert.equal((await worker.fetch(new Request('https://test/api/snapshot?file=../../secret'),env,{})).status,400);
    assert.equal(calls,1);
    global.fetch=async()=>{throw new Error('offline');};
    assert.deepEqual(await (await worker.fetch(new Request('https://test/api/snapshot?file=ncaa_lines.json'),env,{})).json(),{saved:true});
  }finally{global.fetch=old;}
});
