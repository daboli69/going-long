'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const P=require('../shared/football-picks.js');
const now=Date.parse('2026-10-05T17:00:00Z');
const c={kind:'prop',sport:'nfl',home:'NO',away:'ATL',team:'NO',player:'Player',profileId:'p',profileDate:'2026-09-27',kickoff:'2026-10-06T00:15:00Z',market:'rec_yds',side:'Over',line:55.5,projMean:65,projSd:20,prob:.6,push:0,n:12,book:'Book',odds:-110,dec:1+100/110,updatedAt:'2026-10-05T16:00:00Z'};
const o={now,season:2026,historyAt:'2026-10-05T16:00:00Z',currentRoleEvidence:{playerId:'p',team:'NO',season:2026,games:3,latest:'2026-09-27',means:{rec_yds:68,targets:8}}};
test('a separate football-case rating leaves probabilities/prices/Score unchanged',()=>{const input=structuredClone(c),e=P.assess(c,o);assert.equal(e.evidenceTier,3);assert.equal(e.points,3);assert.equal(e.price.fresh,false);assert.equal(e.interesting,true);assert.deepEqual(c,input);assert.equal(P.assess({...c,odds:500,dec:6},o).rating,e.rating);});
test('missing evidence is neutral, disagreement lowers support, model-only remains visible',()=>{const missing=P.assess(c,{...o,currentRoleEvidence:null});assert.equal(missing.points,2);assert.equal(missing.interesting,true);const conflict=P.assess(c,{...o,currentRoleEvidence:{...o.currentRoleEvidence,means:{rec_yds:40,targets:8}}});assert.equal(conflict.points,1);assert.match(conflict.concern,/does not favor/);});
test('no fabricated ATD, First TD or rare-event model-direction credit',()=>{const e=P.assess({...c,market:'atd',side:'Yes',line:.5,prob:.95},o);assert.equal(e.points,0);assert.equal(e.tdResearch,true);assert.equal(e.interesting,false);assert.equal(P.assess({...c,market:'first_td'},o).eligible,false);});
test('official reserve/inactive status, started games and invalid models cannot be picks',()=>{for(const status of ['RES','INA','PUP','IR','SUS'])assert.equal(P.assess(c,{...o,injuryLearning:{current_players:{'NO|player':{roster_status:status}}}}).eligible,false);for(const x of [{prob:null},{n:4},{kickoff:'2026-10-04T17:00:00Z'},{market:'rec_yds_1h'}])assert.equal(P.assess({...c,...x},o).eligible,false);});
test('missing/stale/future/invalid prices do not erase a valid football thesis',()=>{for(const x of [{odds:null,dec:null},{updatedAt:'2026-10-01T12:00:00Z'},{updatedAt:'2026-10-06T12:00:00Z'},{dec:4}]){const e=P.assess({...c,...x},o);assert.equal(e.points,3);assert.equal(e.price.fresh,false);assert.equal(e.price.saveable,false);}});
test('current usage trend requires exact player/team and two observed games in each period',()=>{const player={player_id:'p',team:'NO',season:2026,last_game:'2026-10-04',games:4},rows=[4,5,8,9].map((targets,i)=>({player_id:'p',team:'NO',date:['2026-09-13','2026-09-20','2026-09-27','2026-10-04'][i],targets})),context={generated_at:o.historyAt,scopes:{2026:{players:{p:player},player_game_usage:Object.fromEntries(rows.map((r,i)=>[i,r]))}}};assert.equal(P.assess(c,{...o,context}).points,4);assert.ok(P.assess(c,{...o,context}).badges.includes('TARGETS ↑'));delete context.scopes[2026].player_game_usage[0];assert.equal(P.assess(c,{...o,context}).points,3);context.scopes[2026].players.p.team='ATL';assert.equal(P.assess(c,{...o,context}).points,3);});
test('opportunity does not become a reward for box-score success or invented routes',()=>{const context={generated_at:o.historyAt,scopes:{2026:{players:{p:{player_id:'p',team:'NO',season:2026,last_game:'2026-09-27',games:3,routes:null,expected_catches:21,actual_catches:16,catch_model_targets:30}},player_game_usage:{}}}};const e=P.assess(c,{...o,context});assert.equal(e.points,3);assert.ok(e.facts.some(x=>x[1].includes('not expected yards')));assert.ok(e.facts.some(x=>x[1].includes('routes unavailable')));});
test('NCAA game evidence never needs NFL player-role fields',()=>{const game={...c,kind:'game',sport:'ncaa',profileId:null,market:'total',side:'Under',line:48.5,modelMean:44},currentGameEvidence={sport:'ncaa',home:'NO',away:'ATL',season:2026,totalContext:45,homeGames:4,awayGames:4};const e=P.assess(game,{...o,currentRoleEvidence:null,currentGameEvidence});assert.equal(e.evidenceTier,3);assert.equal(e.eligible,true);});
test('standard line, opposite sides and duplicate minute-shift/book observations are consolidated',()=>{const rows=[c,{...c,book:'Other',updatedAt:'2026-10-05T16:30:00Z',kickoff:'2026-10-06T00:16:00Z'},{...c,side:'Under',projMean:65,projSd:20,prob:.4},{...c,line:15.5,odds:-1000,dec:1.1,prob:.99}];const b=P.board(rows,o);assert.equal(b.picks.length,1);assert.equal(b.picks[0].candidate.line,55.5);assert.equal(b.picks[0].candidate.side,'Over');assert.equal(b.picks[0].candidate.book,'Other');});
test('card leads with bet/rating/why/risk/price, methodology is progressive and escaped',()=>{const e=P.assess({...c,player:'<img>'},o),text=P.card({candidate:{...c,player:'<img>'},evidence:e},{label:'Over 55.5 Receiving yards'});assert.match(text,/GOING <b>50\/100/);assert.match(text,/WHY/);assert.match(text,/CONCERN/);assert.match(text,/PRICE NEEDS REFRESH/);assert.match(text,/&lt;img&gt;/);assert.match(text,/<details/);assert.doesNotMatch(text,/Current support|Developing|Check first|High confidence/);});
test('formerly tied cases separate by directional gap relative to model spread, not probability or price',()=>{
 const close=P.assess({...c,projMean:57.5},o),clear=P.assess({...c,projMean:67.5},o),wide=P.assess({...c,projMean:67.5,projSd:40},o);
 assert.equal(close.evidenceTier,clear.evidenceTier);assert.ok(clear.rating>close.rating);assert.ok(clear.rating>wide.rating);
 assert.equal(P.assess({...c,projMean:67.5,prob:.99,goingScore:99,odds:400,dec:5},o).rating,clear.rating);
 const rows=[{...c,profileId:'z',projMean:57.5},{...c,profileId:'a',projMean:67.5}],options=x=>({...o,currentRoleEvidence:{...o.currentRoleEvidence,playerId:x.profileId}});
 assert.deepEqual(P.board(rows,options).picks.map(x=>x.candidate.profileId),['a','z']);assert.deepEqual(P.board(rows.reverse(),options).picks.map(x=>x.candidate.profileId),['a','z']);
});
test('projection refinement respects direction, market units, evidence caps and unknown spread',()=>{
 const under=P.assess({...c,side:'Under',projMean:43.5}, {...o,currentRoleEvidence:{...o.currentRoleEvidence,means:{rec_yds:40}}});
 assert.equal(under.rating,P.assess({...c,projMean:67.5},o).rating);
 const missing=P.assess({...c,projSd:null},o);assert.equal(missing.evidenceTier,3);assert.equal(missing.rating,41);assert.equal(missing.ratingDetail.strength,null);assert.equal(missing.interesting,true);
 for(const projSd of [0,-1,NaN,Infinity])assert.equal(P.assess({...c,projSd},o).rating,41);
 assert.equal(P.assess({...c,projMean:1000},o).rating,60);assert.ok(P.assess({...c,projMean:1000},{...o,currentRoleEvidence:null}).rating<=40);
 for(const [market,line,mean,sd] of [['spread',-3.5,5.5,4],['total',45.5,47.5,4],['moneyline',0,2,4]]){
  const e=P.assess({...c,kind:'game',market,side:'Home',line,modelMean:mean,modelSd:sd}, {...o,currentRoleEvidence:null});assert.equal(e.ratingDetail.strength,.5);assert.equal(e.rating,31);
 }
 const td=P.assess({...c,market:'atd',side:'Yes',line:.5}, {...o,currentRoleEvidence:{...o.currentRoleEvidence,tdAppearances:2}});assert.equal(td.ratingDetail.strength,null);assert.ok(td.rating<=40);
});
test('role trend and projection-vs-line appear as descriptive facts and add no rating points',()=>{
 const trend={games:8,snap_share:{l1:90,l3:84,l6:70},target_share:{l1:.25,l3:.23,l6:.18},carry_share:{l1:0,l3:0,l6:0}},w={...c,position:'WR'};
 const base=P.assess(w,o),up=P.assess({...w,roleTrend:trend},o);
 assert.equal(up.points,base.points);assert.equal(up.rating,base.rating);
 const fact=up.facts.find(x=>x[0].startsWith('Role trend'));assert.match(fact[1],/Snap share 70% → 84%/);assert.match(fact[1],/Target share 18% → 23%/);assert.match(fact[1],/expanded/);assert.doesNotMatch(fact[1],/Carry/);
 assert.ok(up.badges.includes('ROLE ↑'));assert.match(up.facts.find(x=>x[0]==='Projection vs line')[1],/projects 65\.0 against a line of 55\.5/);
 const shrink={games:8,snap_share:{l1:50,l3:55,l6:70},target_share:{l1:.1,l3:.12,l6:.18}};
 const down=P.assess({...w,roleTrend:shrink},o);assert.ok(down.badges.includes('ROLE ↓'));assert.ok(down.concerns.some(x=>/shrunk/.test(x)));
 assert.equal(P.assess({...w,roleTrend:null},o).facts.some(x=>x[0].startsWith('Role trend')),false);
 // A quarterback has no snap/target/carry-share role in passing markets: never a role badge.
 assert.equal(P.assess({...w,position:'QB',roleTrend:shrink},o).badges.some(x=>x.startsWith('ROLE')),false);
});
test('GoingIntel picks only the role metrics that matter for the market',()=>{
 const I=require('../shared/going-intel.js'),t={snap_share:{l3:60,l6:75},target_share:{l3:.1,l6:.2},carry_share:{l3:.3,l6:.5}};
 assert.deepEqual(I.roleTrend(t,'WR','receptions').parts.map(x=>x.metric),['snap_share','target_share']);
 assert.deepEqual(I.roleTrend(t,'RB','rush_yds').parts.map(x=>x.metric),['snap_share','carry_share']);
 assert.equal(I.roleTrend(t,'QB','pass_yds'),null);assert.equal(I.roleTrend(t,'WR','pass_yds'),null);
 assert.equal(I.roleTrend({snap_share:{l3:80,l6:80},carry_share:{l3:0,l6:0}},'WR','atd').parts.length,1);
});
test('Same-thesis cards collapse into one with the others listed',()=>{
 const I=require('../shared/going-intel.js'),a={kind:'prop',away:'MIN',home:'NO',profileId:'p',market:'rec_yds',side:'Over'};
 assert.equal(I.thesisKey(a),I.thesisKey({...a,market:'receptions'}));assert.notEqual(I.thesisKey(a),I.thesisKey({...a,side:'Under'}));assert.notEqual(I.thesisKey(a),I.thesisKey({...a,market:'atd'}));
 const g={kind:'game',away:'MIN',home:'NO',market:'spread',side:'Away'};assert.equal(I.thesisKey(g),I.thesisKey({...g,market:'moneyline'}));assert.notEqual(I.thesisKey(g),I.thesisKey({...g,market:'total',side:'Over'}));
});

test('Scoring role: tier, goal-line/red-zone badges and TD luck appear on touchdown cards only, from the profile record',()=>{
 const I=require('../shared/going-intel.js'),sr={version:1,n:12,confidence:'ok',tier:'PRIMARY',xtd_pg_l12:.96,xtd_share_l6:.32,snap_pct_l6:.755,gl_carry_pg_l12:.42,rz_tgt_pg_l12:1.2,td_pg_l12:1.25,td_luck_l12:.29};
 const a=I.scoringRole(sr,'RB','atd');assert.equal(a.tier,'PRIMARY');assert.deepEqual(a.badges,['SCORING ROLE','RED ZONE']);assert.equal(a.luck,'above');assert.match(a.text,/32% of his team's expected TDs/);
 assert.deepEqual(I.scoringRole({...sr,gl_carry_pg_l12:.6},'RB','atd').badges,['SCORING ROLE','GOAL LINE','RED ZONE']);
 assert.equal(I.scoringRole({...sr,confidence:'low'},'RB','atd'),null);assert.equal(I.scoringRole(null,'RB','atd'),null);
 const td={...c,market:'atd',side:'Yes',line:.5,position:'RB',scoringRole:sr},e=P.assess(td,o);
 assert.ok(e.badges.includes('SCORING ROLE'));assert.ok(e.facts.some(x=>x[0]==='Scoring role'&&/primary scoring role/.test(x[1])));assert.ok(e.components.some(x=>x.id==='scoring_role'&&x.points===1));
 assert.ok(e.concerns.some(x=>/more than his opportunity predicts/.test(x)));
 assert.equal(P.assess({...c,position:'RB',scoringRole:sr},o).facts.some(x=>x[0]==='Scoring role'),false);// not a touchdown market
});
