'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const P=require('../shared/football-picks.js');
const now=Date.parse('2026-10-05T17:00:00Z');
const c={kind:'prop',sport:'nfl',home:'NO',away:'ATL',team:'NO',player:'Player',profileId:'p',profileDate:'2026-09-27',kickoff:'2026-10-06T00:15:00Z',market:'rec_yds',side:'Over',line:55.5,projMean:65,projSd:20,prob:.6,push:0,n:12,book:'Book',odds:-110,dec:1+100/110,updatedAt:'2026-10-05T16:00:00Z'};
const base={now,season:2026,historyAt:'2026-10-05T16:00:00Z',currentRoleEvidence:{playerId:'p',team:'NO',season:2026,games:3,latest:'2026-09-27',means:{rec_yds:68,targets:8}}};
const totals=(expected,actual,tdDelta=0)=>({fantasy_points:{expected,actual,delta:actual-expected},rec_tds:{expected:0,actual:0,delta:tdDelta/6},rush_tds:{expected:0,actual:0,delta:0}});
const usage={team:'NO',player_id:'p',position:'WR',games:4,red_zone:{targets:5,carries:0,team_targets:10,team_carries:12,target_share:.5,carry_share:0},inside_5:{targets:2,carries:0,team_targets:3,team_carries:9,target_share:2/3,carry_share:0},third_down:{targets:6,carries:0,team_targets:20,team_carries:5,target_share:.3,carry_share:0},inside_10:{targets:3,carries:0,team_targets:5,team_carries:10,target_share:.6,carry_share:0}};
const ctx=(t,extra={})=>({generated_at:base.historyAt,picks_evidence:{season:2026,generated_at:base.historyAt,opportunity_process:{season:2026,generated_at:base.historyAt,provenance:{expected_points:{status:'loaded'}},situational_usage:{'NO|p':usage},expected_vs_actual:{'NO|p':{player_id:'p',team:'NO',position:'WR',games:4,totals:t,...extra}}}}});
const withCtx=(t,extra,o={})=>P.assess(c,{...base,context:ctx(t,extra),...o});
const none=P.assess(c,base);

test('underperformance is display-only: badge and numbers, zero rating points, no recommendation change',()=>{
 const e=withCtx(totals(60,36));
 assert.ok(e.badges.includes('UNDERPERFORMED OPPORTUNITY'));
 assert.equal(e.rating,none.rating);assert.equal(e.points,none.points);assert.equal(e.evidenceTier,none.evidenceTier);assert.deepEqual(e.components,none.components);
 const fact=e.facts.find(f=>f[0]==='Opportunity vs production')[1];
 assert.match(fact,/-24\.0 fantasy points vs expected over 4 games/);assert.match(fact,/not a bounce-back or regression forecast/);
 assert.doesNotMatch(JSON.stringify(e),/due for|buy low|bounce back to/i);
});
test('overperformance and an Under bet get the same neutral label, never a concern or support',()=>{
 const over=withCtx(totals(60,84)),under=P.assess({...c,side:'Under',projMean:40},{...base,context:ctx(totals(60,84))});
 assert.ok(over.badges.includes('OVERPERFORMED OPPORTUNITY'));assert.ok(under.badges.includes('OVERPERFORMED OPPORTUNITY'));
 assert.deepEqual(under.concerns,P.assess({...c,side:'Under',projMean:40},base).concerns);
});
test('touchdown-driven gaps use separate wording',()=>{
 const e=withCtx(totals(60,84,24));assert.ok(e.badges.includes('TD ABOVE EXPECTED'));assert.ok(!e.badges.includes('OVERPERFORMED OPPORTUNITY'));
 assert.match(e.facts.find(f=>f[0]==='Opportunity vs production')[1],/touchdowns above\/below expectation/);
 assert.ok(withCtx(totals(60,36,-24)).badges.includes('TD BELOW EXPECTED'));
});
test('sample, size, relative and z floors all must pass',()=>{
 const none2=e=>!e.badges.some(b=>/OPPORTUNITY|EXPECTED/.test(b));
 assert.ok(none2(withCtx(totals(60,36),{games:3})));            // too few games
 assert.ok(none2(withCtx(totals(16,6))));                          // <5 expected points per game
 assert.ok(none2(withCtx(totals(60,54))));                         // |delta| < 6
 assert.ok(none2(withCtx(totals(200,170))));                       // under 25% relative
 assert.ok(none2(withCtx(totals(60,52))));                         // z below 1.28
 assert.ok(none2(withCtx(totals(60,36),{position:'QB'})));         // QB excluded
});
test('stale, unavailable, other-season, wrong identity or non-skill markets add nothing',()=>{
 const stale=ctx(totals(60,36));stale.picks_evidence.opportunity_process.generated_at='2026-09-01T00:00:00Z';
 const down=ctx(totals(60,36));down.picks_evidence.opportunity_process.provenance.expected_points.status='unavailable';
 const season=ctx(totals(60,36));season.picks_evidence.opportunity_process.season=2025;
 for(const context of [stale,down,season]){const e=P.assess(c,{...base,context});assert.ok(!e.badges.some(b=>/OPPORTUNITY|EXPECTED/.test(b)));assert.equal(e.facts.find(f=>f[0]==='Opportunity vs production'),undefined);}
 assert.ok(!P.assess({...c,profileId:'other'},{...base,context:ctx(totals(60,36))}).badges.includes('UNDERPERFORMED OPPORTUNITY'));
 assert.ok(!P.assess({...c,market:'pass_yds',side:'Over'},{...base,context:ctx(totals(60,36))}).badges.includes('UNDERPERFORMED OPPORTUNITY'));
 assert.equal(P.opportunityProcess({...c,kind:'game'},{...base,context:ctx(totals(60,36))}),null);
});
test('situational usage is shown for the market family only, from completed-game counts',()=>{
 const rec=P.assess(c,{...base,context:ctx(totals(60,60))}).facts.find(f=>f[0].startsWith('Situational usage'))[1];
 assert.match(rec,/Red zone targets: 5 of team 10 \(50%\)/);assert.match(rec,/Inside 5 targets: 2 of team 3 \(67%\)/);assert.match(rec,/Third down targets: 6 of team 20 \(30%\)/);assert.doesNotMatch(rec,/carries/);
 const rush=P.assess({...c,market:'rush_yds'},{...base,context:ctx(totals(60,60))}).facts.find(f=>f[0].startsWith('Situational usage'))[1];
 assert.match(rush,/Red zone carries: 0 of team 12 \(0%\)/);assert.doesNotMatch(rush,/targets/);
});
test('the rule constants are the model-research thresholds',()=>{
 assert.deepEqual(P.OPPORTUNITY_RULE,{version:'opportunity-process-v1',sd:{RB:4.93,WR:4.91,TE:3.72},minGames:4,minExpectedPerGame:5,z:1.28,minAbsDelta:6,minRelDelta:.25,tdShare:.6});
});
