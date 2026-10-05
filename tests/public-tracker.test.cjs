const {test}=require('node:test');const assert=require('node:assert/strict');const {execFileSync}=require('node:child_process');const path=require('node:path');
const play=(changes={})=>({kind:'prop',sport:'nfl',home:'BAL',away:'PIT',event:'game',kickoff:'2026-09-20T17:00:00Z',player:'Example Player',profileId:'player-1',market:'rec_yds',side:'Over',line:50.5,odds:-110,dec:1.91,prob:.58,ev:.1078,book:'Fanatics',updatedAt:'2026-09-20T14:00:00Z',canonicalContract:'contract-1',tracking_group:'best_model',...changes});

test('Public tracker collector boots using only repository-local data',()=>{
 const root=path.resolve(__dirname,'..'),stdout=execFileSync(process.execPath,[path.join(root,'scripts/collect_model_plays.cjs')],{cwd:root,encoding:'utf8',maxBuffer:64*1024*1024,env:{...process.env,GOING_TRACKER_LOCAL_DATA:'1',GOING_CAPTURE_QUOTES:'0'}});
 assert.ok(Array.isArray(JSON.parse(stdout)));
});

test('Public tracker freezes only supported prospective selections and never rewrites them',async()=>{
 const {freezePredictions}=await import('../scripts/build_public_tracker.mjs'),records=[],at='2026-09-20T15:00:00Z';
 assert.equal(freezePredictions(records,[play(),play({market:'first_td',canonicalContract:'unsupported'}),play({kickoff:'2026-09-20T14:00:00Z',canonicalContract:'late'})],at).length,1);
 assert.equal(freezePredictions(records,[play({prob:.99,odds:500})],'2026-09-20T15:10:00Z').length,0);
 assert.equal(records[0].payload.probability,.58);assert.equal(records[0].payload.american,-110);assert.ok(Date.parse(records[0].payload.observed_at)<Date.parse(records[0].payload.kickoff));
});

test('Public tracker settles exact games and player outcomes without inventing missing results',async()=>{
 const {freezePredictions,settlePredictions}=await import('../scripts/build_public_tracker.mjs'),records=[];freezePredictions(records,[play(),play({profileId:'missing',canonicalContract:'missing-result'})],'2026-09-20T15:00:00Z');
 const results={generated_at:'2026-09-20T22:00:00Z',games:{one:{sport:'nfl',home:'BAL',away:'PIT',kickoff:'2026-09-20T17:00:00Z',homeScore:20,awayScore:17}},players:{'player-1|2026-09-20':{rec_yds:72}}};
 const added=settlePredictions(records,results,'2026-09-20T22:00:00Z');assert.equal(added.length,1);assert.equal(added[0].payload.status,'win');assert.equal(added[0].payload.actual,72);
 assert.equal(settlePredictions(records,results,'2026-09-20T23:00:00Z').length,0);assert.equal(records.filter(r=>r.kind==='settlement').length,1);
});

test('Public tracker grades home and away game lines consistently',async()=>{
 const {freezePredictions,settlePredictions}=await import('../scripts/build_public_tracker.mjs'),records=[],base={kind:'game',sport:'nfl',home:'BAL',away:'PIT',event:'game',kickoff:'2026-09-20T17:00:00Z',player:'PIT @ BAL',odds:-110,dec:1.91,prob:.55,ev:.05,book:'Fanatics',updatedAt:'2026-09-20T14:00:00Z',tracking_group:'best_model'};
 freezePredictions(records,[{...base,market:'spread',side:'Home',line:-2.5,canonicalContract:'home-spread'},{...base,market:'spread',side:'Away',line:-2.5,canonicalContract:'away-spread'},{...base,market:'moneyline',side:'Home',line:0,canonicalContract:'home-ml'}],'2026-09-20T15:00:00Z');
 const results={generated_at:'2026-09-20T22:00:00Z',games:{one:{sport:'nfl',home:'BAL',away:'PIT',kickoff:'2026-09-20T17:00:00Z',homeScore:24,awayScore:20}},players:{}};settlePredictions(records,results,'2026-09-20T22:00:00Z');
 assert.deepEqual(records.filter(r=>r.kind==='settlement').map(r=>r.payload.status),['win','loss','win']);
});

test('Same-day player stats remain pending until their official final exists',async()=>{
 const {freezePredictions,settlePredictions}=await import('../scripts/build_public_tracker.mjs'),records=[];
 freezePredictions(records,[play()],'2026-09-20T15:00:00Z');
 const results={generated_at:'2026-09-20T19:00:00Z',games:{},players:{'player-1|2026-09-20':{rec_yds:72}}};
 assert.equal(settlePredictions(records,results,'2026-09-20T19:00:00Z').length,0);
 results.games.one={sport:'nfl',home:'BAL',away:'PIT',kickoff:'2026-09-20T17:00:00Z',homeScore:20,awayScore:17};
 assert.equal(settlePredictions(records,results,'2026-09-20T22:00:00Z').length,1);
});

test('Results-only refresh preserves frozen records and capture freshness',async(t)=>{
 const fs=require('node:fs/promises'),os=require('node:os'),{build,freezePredictions}=await import('../scripts/build_public_tracker.mjs');
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'going-results-only-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 const output=path.join(dir,'tracker.json'),records=[];
 freezePredictions(records,[play({kickoff:'2026-12-20T17:00:00Z'})],'2026-09-20T15:00:00Z');
 const original=JSON.stringify(records);
 await fs.writeFile(output,JSON.stringify({schema_version:1,generated_at:'2026-09-20T15:00:00Z',records,sources:{predictions:{status:'FRESH'}}}));
 const snapshot=await build({output,now:'2026-09-20T16:00:00Z',settleOnly:true,plays:[play({canonicalContract:'never-capture'})]});
 assert.equal(JSON.stringify(snapshot.records),original);assert.equal(snapshot.latest_run.captured,0);
 assert.equal(snapshot.latest_run.kind,'settlement_only');assert.equal(snapshot.sources.predictions.status,'RETAINED');
 assert.equal(snapshot.sources.predictions.last_capture_at,'2026-09-20T15:00:00Z');
});

test('Final-game coverage includes untracked finals without manufacturing predictions',async()=>{
 const {resultCoverage,freezePredictions}=await import('../scripts/build_public_tracker.mjs'),records=[];
 freezePredictions(records,[play({kickoff:'2026-09-21T00:20:00Z'})],'2026-09-20T15:00:00Z');
 const games={one:{sport:'nfl',id:'tracked',home:'BAL',away:'PIT',kickoff:'2026-09-21T00:20:00Z',homeScore:20,awayScore:17},two:{sport:'nfl',id:'untracked',home:'A',away:'B',kickoff:'2026-09-20T17:00:00Z',homeScore:10,awayScore:7},three:{sport:'nfl',id:'partial',home:'C',away:'D',kickoff:'2026-09-20T17:00:00Z',homeScore:null,awayScore:7}};
 const before=JSON.stringify(records),coverage=resultCoverage(records,{games},'2026-09-21T04:00:00Z');
 assert.equal(JSON.stringify(records),before);assert.equal(coverage.slates.length,1);assert.equal(coverage.slates[0].date,'2026-09-20');
 assert.equal(coverage.slates[0].finals,2);assert.equal(coverage.slates[0].tracked_finals,1);assert.equal(coverage.slates[0].games.find(g=>g.id==='untracked').tracked,false);
});

test('A unique one-minute midnight clock discrepancy settles against the official Eastern slate',async()=>{
 const {freezePredictions,settlePredictions,settlementReason}=await import('../scripts/build_public_tracker.mjs'),records=[];
 const p=play({sport:'ncaa',home:"Hawai'i",away:'San José State',kickoff:'2026-10-04T04:00:00Z',market:'moneyline',kind:'game',side:'Home',line:0});
 freezePredictions(records,[p],'2026-10-03T12:00:00Z');const before=JSON.stringify(records[0]);
 const game={sport:'ncaa',id:'official',home:"Hawai'i",away:'San José State',kickoff:'2026-10-04T03:59:00Z',homeScore:16,awayScore:20},results={games:{one:game},players:{}};
 const added=settlePredictions(records,results,'2026-10-04T08:00:00Z');assert.equal(added.length,1);assert.equal(added[0].payload.status,'loss');assert.equal(added[0].payload.official_kickoff,game.kickoff);assert.equal(JSON.stringify(records[0]),before);
 assert.equal(settlementReason(records[0].payload,{games:{one:game,two:{...game,id:'other'}}},'2026-10-04T08:00:00Z'),'ambiguous_game');
 assert.equal(settlementReason(records[0].payload,{games:{one:{...game,kickoff:'2026-10-03T03:59:00Z'}}},'2026-10-04T08:00:00Z'),'official_final_missing');
 assert.equal(settlementReason({...records[0].payload,observed_at:'2026-10-04T03:59:30Z'},results,'2026-10-04T08:00:00Z'),'not_before_official_kickoff');
});

test('Public tracker uses declared qualification rules and one primary projection line',async()=>{
 const {selectTrackedPlays}=await import('../scripts/build_public_tracker.mjs'),gap=[{id:'gap'}],check=[{id:'gap'},{id:'check'}],rows=[
  play({tracking_group:'best_model',canonicalContract:'qualified',flags:gap,ev:.04,isAltLine:false}),
  play({tracking_group:'best_model',canonicalContract:'same-game-better-price',flags:gap,ev:.04,isAltLine:false,kickoff:'2026-09-20T17:01:00Z',dec:2.05,odds:105}),
  play({tracking_group:'best_model',canonicalContract:'alt',flags:gap,ev:.2,isAltLine:true}),
  play({tracking_group:'best_model',canonicalContract:'blocked',flags:check,ev:.2,isAltLine:false}),
  play({tracking_group:'all_projection',canonicalContract:'standard',line:50.5,dec:1.91,odds:-110}),
  play({tracking_group:'all_projection',canonicalContract:'alternate',line:20.5,dec:1.2,odds:-500}),
  play({tracking_group:'best_value',canonicalContract:'value',isAltLine:false}),
 ];
 assert.deepEqual(selectTrackedPlays(rows).map(row=>row.canonicalContract),['same-game-better-price','value','standard']);
});
