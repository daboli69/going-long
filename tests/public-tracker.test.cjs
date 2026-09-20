const {test}=require('node:test');const assert=require('node:assert/strict');
const play=(changes={})=>({kind:'prop',sport:'nfl',home:'BAL',away:'PIT',event:'game',kickoff:'2026-09-20T17:00:00Z',player:'Example Player',profileId:'player-1',market:'rec_yds',side:'Over',line:50.5,odds:-110,dec:1.91,prob:.58,ev:.1078,book:'Fanatics',updatedAt:'2026-09-20T14:00:00Z',canonicalContract:'contract-1',tracking_group:'best_model',...changes});

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
