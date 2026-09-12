const {test}=require('node:test');
const assert=require('node:assert/strict');
const future=new Date(Date.now()+86400000).toISOString();
const quote={player:'Josh Allen',bookmaker:'draftkings',bookmaker_title:'DraftKings',market_key:'player_passing_yards',line:249.5,over_price:-110,under_price:105,canonical_event_id:'event',commence_time:future,last_update:new Date().toISOString()};

test('Parlay flat quotes preserve alternative TD thresholds, identities and missing prices',async()=>{
  const {normalizeProps}=await import('../server/parlay.mjs');
  const rows=normalizeProps([quote,{...quote,market_key:'player_anytime_td',line:1.5,over_price:600,under_price:null},
    {...quote,market_key:'player_anytime_td',line:0}, {...quote,market_key:'player_last_touchdown'},
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
  assert.equal(result.props.length,1);assert.equal(calls.length,4);
  for(const c of calls){assert.equal(c.url.origin,'https://parlay-api.com');assert.equal(c.options.headers['X-API-Key'],'fixture-key');assert.ok(!c.url.href.includes('fixture-key'));}
  assert.ok(calls.every(c=>c.url.pathname.includes('/americanfootball_nfl/')));
  await assert.rejects(fetchParlay('ncaa','fixture-key',async()=>Response.json({error:'bad'})),/Unexpected/);
});

test('NCAA ingestion requests only game spreads, totals and moneylines',async()=>{
  const {fetchParlay}=await import('../server/parlay.mjs');const urls=[];
  const result=await fetchParlay('ncaa','fixture-key',async url=>{urls.push(url);return Response.json([]);});
  assert.equal(urls.length,2);assert.ok(urls[0].pathname.endsWith('/americanfootball_ncaaf/odds'));
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
    assert.equal(calls,4);
    for(const r of responses){assert.equal(r.status,200);assert.ok(!(await r.text()).includes('fixture-key'));}
    assert.equal((await oddsResponse(req,{PARLAY_API_KEY:'fixture-key'})).status,200);assert.equal(calls,4);
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

test('Derivative identities separate first TD, anytime, periods, books and alternative lines',async()=>{
  const {normalizeProps,normalizePeriods,periodsFromGames}=await import('../server/parlay.mjs');
  const props=normalizeProps(['player_first_td','player_anytime_td','pass_yds_1h','player_pass_yds'].map(market_key=>({...quote,market_key,line:market_key.includes('td')?null:100})));
  assert.equal(props.length,4);assert.equal(new Set(props.map(p=>p.quoteKey)).size,4);
  const q={match_id:'g',source:'book',period_key:'1H',market:'total',side:'over',line:20.5,price:-110,age_seconds:4};
  const rows=normalizePeriods([q,{...q,price:110,age_seconds:1},{...q,period_key:'Q1'},{...q,line:21.5},{...q,source:'other'}]);
  assert.equal(rows.length,4);assert.equal(rows[0].price,110);assert.equal(rows[0].inPlay,true);
  assert.equal(normalizePeriods([{...q,market:'team_total'}]).length,0);
  const parsed=periodsFromGames([{id:'g',home_team:'A',away_team:'B',commence_time:'2099-01-01',bookmakers:[{key:'book',markets:[{key:'1h_spread',outcomes:[{name:'A',point:-3,price:-110},{name:'B',point:3,price:-110}]}]}]}]);
  assert.equal(parsed.length,2);assert.equal(parsed[0].period_key,'1H');assert.equal(parsed[0].inPlay,false);
});

test('Optional period endpoint failure cannot erase working main odds',async()=>{
  const {fetchParlay}=await import('../server/parlay.mjs');
  const out=await fetchParlay('nfl','fixture',async url=>url.pathname.endsWith('/period_markets')?new Response('',{status:503}):Response.json(url.pathname.endsWith('/props')?[quote]:[]));
  assert.equal(out.props.length,1);assert.equal(out.period_status,'unavailable');
});

test('Observed period feeds retain upcoming kickoffs and identify three-way moneylines',async()=>{
  const {normalizePeriods,MARKET_MAP}=await import('../server/parlay.mjs');
  const base={match_id:'g',source:'book',period_key:'1H',market:'h2h',commence_time:future,last_observed_ms:Date.now(),price:120};
  const rows=normalizePeriods(['home','away','draw'].map(side=>({...base,side})));
  assert.equal(rows.length,3);assert.ok(rows.every(r=>r.inPlay===false&&r.threeWay&&r.updatedAt&&r.kickoff===future));
  assert.equal(MARKET_MAP.player_1h_pass_yards,'pass_yds_1h');assert.equal(MARKET_MAP.player_1q_rec_yards,'rec_yds_1q');assert.equal(MARKET_MAP.player_1st_td,'first_td');
});

test('MLB separates market requests to avoid a shared row cap and retains partial successes',async()=>{
 const {fetchParlay}=await import('../server/parlay.mjs');const seen=[];
 const result=await fetchParlay('mlb','fixture-key',async(url,options)=>{
  assert.equal(options.headers['X-API-Key'],'fixture-key');assert.ok(url.pathname.startsWith('/v1/sports/baseball_mlb/'));
  const market=url.searchParams.get('markets');seen.push(market);
  if(market==='player_total_bases')throw Error('temporary outage');
  return Response.json(url.pathname.endsWith('/props')?[{market_key:market}]:[]);
 });
 assert.equal(seen.length,6);assert.ok(seen.includes('player_home_runs'));assert.equal(result.props.length,4);
 assert.equal(result.coverage.markets.player_home_runs.status,'loaded');assert.equal(result.coverage.markets.player_total_bases.status,'unavailable');
});

