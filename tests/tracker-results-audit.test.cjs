const {test}=require('node:test');
const assert=require('node:assert/strict');
const {audit,day}=require('../research/tracker-results/audit.cjs');
const asOf='2026-10-05T02:00:00Z';
const prediction=(id,extra={})=>({id,kind:'prediction',payload:{id,sport:'nfl',home:'DEN',away:'JAX',market:'totals',line:40.5,side_index:0,tracking_group:'best_model',model_cohort:'current-80-20',book:'A',odds:2,probability:.6,observed_at:'2026-10-04T14:00:00Z',quoted_at:'2026-10-04T13:55:00Z',kickoff:'2026-10-04T17:00:00Z',model_evidence:{push:0,reference:{win:.5,loss:.5}},provenance:{model_source_sha256:'fixture',inputs:{data:{generated_at:'2026-10-04T13:00:00Z'}}},...extra}});
const settlement=(id,status='win',actual=45)=>({id:`settle-${id}`,kind:'settlement',payload:{prediction_id:id,status,actual,observed_at:'2026-10-04T22:00:00Z',method:'published_full_game_result'}});
const results={games:{game:{sport:'nfl',home:'DEN',away:'JAX',kickoff:'2026-10-04T17:00:00Z',homeScore:25,awayScore:20}},players:{}};
const run=records=>audit({generated_at:asOf,records},results);
test('diagnostic uses Eastern game day across UTC midnight',()=>assert.equal(day('2026-10-04T00:30:00Z'),'2026-10-03'));

test('a unique official midnight correction includes the original selection in its actual slate',()=>{
 const p=prediction('night',{sport:'ncaa',kickoff:'2026-10-04T04:00:00Z',observed_at:'2026-10-03T14:00:00Z',quoted_at:'2026-10-03T13:55:00Z',provenance:{}}),s=settlement('night');
 const final={games:{g:{...results.games.game,sport:'ncaa',kickoff:'2026-10-04T03:59:00Z'}},players:{}};
 const a=audit({generated_at:asOf,records:[p,s]},final);assert.equal(a.target.ncaa.groups[0].settled,1);assert.equal(a.target.ncaa.published_finals_without_prediction.length,0);assert.equal(p.payload.kickoff,'2026-10-04T04:00:00Z');
});
test('vendor kickoff and book drift count once, preserving earliest frozen price',()=>{
 const a=run([prediction('first'),settlement('first'),prediction('second',{book:'B',odds:3,kickoff:'2026-10-04T17:01:00Z',observed_at:'2026-10-04T14:30:00Z'}),settlement('second')]);
 assert.equal(a.predictions,2);assert.equal(a.duplicate_equivalent_contracts,1);assert.equal(a.duplicate_books_changed,1);assert.equal(a.groups[0].profit,100);assert.equal(a.groups[0].settled,1);
});

test('simultaneous captures preserve original ledger order rather than a hash sort',()=>{
 const a=run([prediction('z-first'),settlement('z-first'),prediction('a-second',{book:'B',odds:3}),settlement('a-second')]);
 assert.equal(a.groups[0].profit,100);assert.equal(a.groups[0].settled,1);
});
test('a published final cannot fabricate a missing prospective selection or settlement',()=>{
 const empty=run([]);assert.equal(empty.target.nfl.published_finals_without_prediction.length,1);assert.equal(empty.groups.length,0);
 const missing=run([prediction('a')]);assert.equal(missing.exclusions.settlement_missing_despite_available_result.count,1);assert.equal(missing.groups.length,0);
});
test('refunds return stake and remain in turnover; conditional scoring excludes pushes',()=>{
 const a=run([prediction('push',{line:45,model_evidence:{push:.1}}),settlement('push','refund',45),prediction('win',{line:44.5,model_evidence:{push:.1}}),settlement('win')]).groups[0];
 assert.equal(a.turnover,200);assert.equal(a.profit,100);assert.equal(a.roi,.5);assert.equal(a.decisive,1);assert.ok(Math.abs(a.brier-(2/3-1)**2)<1e-12);assert.equal(a.game_balanced_brier.lower,null);
});
test('prediction captured after actual kickoff is excluded despite vendor clock',()=>{
 const a=run([prediction('late',{observed_at:'2026-10-04T17:00:30Z',kickoff:'2026-10-04T17:01:00Z'}),settlement('late')]);
 assert.equal(a.exclusions.capture_not_before_official_kickoff.count,1);assert.equal(a.groups.length,0);
});
test('future inputs and contradictory grades fail diagnostics rather than silently scoring',()=>{
 const a=run([prediction('future',{provenance:{inputs:{data:{generated_at:'2026-10-04T15:00:00Z'}}}}),settlement('future'),prediction('bad',{line:39.5}),settlement('bad','loss')]);
 assert.equal(a.exclusions.future_input_timestamp.count,1);assert.equal(a.exclusions.settlement_disagrees_with_public_result.count,1);assert.equal(a.groups.length,0);
});
test('duplicate settlements block grading and missing participation is never a loss',()=>{
 const a=run([prediction('dup'),settlement('dup'),{...settlement('dup'),id:'other'},prediction('player',{market:'player_rushing_yards',profile_id:'missing',line:20.5}),settlement('player','loss',0)]);
 assert.equal(a.exclusions.duplicate_settlement.count,1);assert.equal(a.exclusions.player_result_or_line_missing.count,1);assert.equal(a.groups.length,0);
});
