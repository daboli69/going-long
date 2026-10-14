const {test}=require('node:test'),assert=require('node:assert/strict');
const now=Date.parse('2026-10-13T21:00:00Z');
function fixture(){
 const row={'Player Details.Name':'Receiver','Player Details.Team':'BUF','Player Details.POS':'WR','Player Details.G':2};
 const dataset=(table,records)=>({table,season:2026,for_week:6,status:'accepted',scope:'season_to_date',known_at:'2026-10-13T20:00:00Z',exported_at:'2026-10-13T19:00:00Z',sha256:require('node:crypto').createHash('sha256').update(table).digest('hex'),columns:Object.keys(records[0]),records});
 const receiving=dataset('receiving_advanced',[{...row,'Receiving.RTE':60,'Receiving.YDS':120}]);
 const splits=dataset('receiving_man_vs_zone',[{...row,'Overall.RTE':60,'Man.RTE':20,'Zone.RTE':40,'Man.YPRR':4,'Zone.YPRR':1}]);
 const defense=dataset('coverage_matrix',[{'Team Details.Name':'New England Patriots','Man/Zone.MAN %':25,'Man/Zone.ZONE %':75}]);
 const games=[{season:2026,week:6,home:'BUF',away:'NE',kickoff:'2026-10-18T17:00:00Z'}];
 const profile={name:'Receiver',team:'BUF',position:'WR',stats:{rec_yds:{mean:65}},games:[1,2].map(w=>({season:2026,week:w,team:'BUF',completed:true,game_id:'game'+w,kickoff:`2026-09-${w===1?'13':'20'}T17:00:00Z`,rec_yds:60}))};
 return {datasets:[receiving,splits,defense],options:{season:2026,week:6,now,games,profiles:{player:profile}}};
}
test('CSV coverage and route volume actually change a separate numeric forecast',async()=>{
 const {buildFpModel}=await import('../server/fp-model.mjs');const f=fixture();let r=buildFpModel(f.datasets,f.options);assert.equal(r.forecasts.length,1);assert.equal(r.forecasts[0].mean,52.5);assert.equal(r.forecasts[0].baseline,60);assert.equal(r.forecasts[0].champion,65);assert.equal(r.forecasts[0].delta,-7.5);
 f.datasets[2].records[0]['Man/Zone.MAN %']=75;f.datasets[2].records[0]['Man/Zone.ZONE %']=25;r=buildFpModel(f.datasets,f.options);assert.equal(r.forecasts[0].mean,97.5);assert.equal(r.forecasts[0].status,'prospective_research_not_promoted');assert.equal(r.forecasts[0].probability,undefined);
});
test('unclassified coverage retains its mass at the overall player rate',async()=>{
 const {buildFpModel}=await import('../server/fp-model.mjs');const f=fixture();f.datasets[2].records[0]['Man/Zone.ZONE %']=65;
 assert.equal(buildFpModel(f.datasets,f.options).forecasts[0].mean,55.5);
});
test('missing, stale, duplicated or wrong-week inputs cannot produce a model forecast',async()=>{
 const {buildFpModel}=await import('../server/fp-model.mjs');
 for(const mutate of [f=>f.datasets[0].scope='prior_week',f=>f.datasets[0].season=2025,f=>f.datasets[0].for_week=7,f=>f.datasets[1].records[0]['Man.YPRR']=null,f=>f.datasets[1].records[0]['Man.YPRR']=40,f=>f.datasets[1].records[0]['Man.RTE']=0,f=>f.datasets[1].records[0]['Overall.RTE']=59,f=>f.datasets[2].records[0]['Man/Zone.MAN %']=null,f=>f.datasets[2].records[0]['Man/Zone.MAN %']=90,f=>f.datasets[0].exported_at='2026-09-01T00:00:00Z',f=>f.datasets[0].known_at='2026-10-14T00:00:00Z',f=>f.datasets.push(structuredClone(f.datasets[0])),f=>f.datasets[0].records.push(structuredClone(f.datasets[0].records[0])),f=>f.options.games[0].kickoff='2026-10-12T00:00:00Z']){
  const f=fixture();mutate(f);assert.equal(buildFpModel(f.datasets,f.options).forecasts.length,0);
 }
});
test('traded, unmatched and duplicate appearance cohorts are withheld',async()=>{
 const {buildFpModel}=await import('../server/fp-model.mjs');for(const mutate of [p=>p.games[0].team='NE',p=>p.games[0].rec_yds=20,p=>p.games[0].completed=false,p=>p.games[0].game_id=p.games[1].game_id,p=>p.games[0].season=2025,p=>p.games[0].kickoff='2026-10-18T17:00:00Z']){const f=fixture();mutate(f.options.profiles.player);assert.equal(buildFpModel(f.datasets,f.options).forecasts.length,0);}
});
test('receipts are deterministic and outputs never return input metric tables',async()=>{
 const {buildFpModel}=await import('../server/fp-model.mjs');const f=fixture(),a=buildFpModel(f.datasets,f.options),b=buildFpModel(f.datasets,f.options);assert.deepEqual(a,b);assert.match(a.forecasts[0].receipt,/^[a-f0-9]{64}$/);assert.doesNotMatch(JSON.stringify(a),/Receiving\.RTE|Man\.YPRR|records|reference_rows/);
});

test('current remote context replaces stale deployment data; stale fallback is refused',async()=>{
 const {loadFpModelContext}=await import('../server/fp-model-context.mjs');const f=fixture();
 const data=file=>file==='history.json'?{betting:{generated_at:'2026-10-13T20:00:00Z',profiles:f.options.profiles}}:{generated_at:'2026-10-13T20:00:00Z',games:f.options.games};
 let packagedReads=0;const r=await loadFpModelContext({season:2026,week:6,now,fetchImpl:async url=>({ok:true,json:async()=>data(url.split('/').at(-1))}),readImpl:async()=>{packagedReads++;throw Error('stale');}});assert.equal(packagedReads,0);assert.equal(r.sources['history.json'],'current-public-snapshot');
 await assert.rejects(loadFpModelContext({season:2026,week:6,now,fetchImpl:async()=>{throw Error('offline');},readImpl:async file=>JSON.stringify(file==='history.json'?{betting:{generated_at:'2026-09-01T00:00:00Z',profiles:{}}}:{generated_at:'2026-09-01T00:00:00Z',games:[]})}),/Fresh current-period/);
 const fallback=await loadFpModelContext({season:2026,week:6,now,fetchImpl:async()=>{throw Error('offline');},readImpl:async file=>JSON.stringify(data(file))});assert.equal(fallback.sources['nfl_betting.json'],'fresh-packaged-fallback');
});
