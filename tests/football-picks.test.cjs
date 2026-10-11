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
test('current usage trend needs exact player/team, two games per half, and (v3) six games or role-share agreement',()=>{const player={player_id:'p',team:'NO',season:2026,last_game:'2026-10-15',games:6},dates=['2026-09-30','2026-10-03','2026-10-06','2026-10-09','2026-10-12','2026-10-15'],rows=[4,5,5,8,9,9].map((targets,i)=>({player_id:'p',team:'NO',date:dates[i],targets})),context={generated_at:o.historyAt,scopes:{2026:{players:{p:player},player_game_usage:Object.fromEntries(rows.map((r,i)=>[i,r]))}}},now6={...o,now:Date.parse('2026-10-19T17:00:00Z'),historyAt:'2026-10-19T16:00:00Z'};
 const ctx6={...context,generated_at:now6.historyAt},base6={...c,kickoff:'2026-10-20T00:15:00Z',updatedAt:'2026-10-19T16:00:00Z',profileDate:'2026-10-15'},opts6=extra=>({...now6,currentRoleEvidence:{...o.currentRoleEvidence,latest:'2026-10-15'},context:ctx6,...extra});
 assert.equal(P.assess(base6,opts6()).points,4);assert.ok(P.assess(base6,opts6()).badges.includes('TARGETS ↑'));
 // five games: no longer enough on its own
 const five=structuredClone(ctx6);delete five.scopes[2026].player_game_usage[0];assert.equal(P.assess(base6,opts6({context:five})).points,3);
 // a role-share trend that agrees brings it back; one that disagrees removes it and says so
 const agree={games:8,snap_share:{l3:84,l6:70},target_share:{l3:.23,l6:.18}},disagree={games:8,snap_share:{l3:60,l6:75},target_share:{l3:.1,l6:.2}},wr={...base6,position:'WR'};
 assert.equal(P.assess({...wr,roleTrend:agree},opts6({context:five})).points,4);
 const mixed=P.assess({...wr,roleTrend:disagree},opts6());assert.equal(mixed.points,3);assert.ok(mixed.badges.includes('USAGE MIXED'));assert.ok(!mixed.badges.some(b=>/^(TARGETS|CARRIES|ROLE)/.test(b)));
 const wrong=structuredClone(ctx6);wrong.scopes[2026].players.p.team='ATL';assert.equal(P.assess(base6,opts6({context:wrong})).points,3);});
test('opportunity does not become a reward for box-score success or invented routes',()=>{const context={generated_at:o.historyAt,scopes:{2026:{players:{p:{player_id:'p',team:'NO',season:2026,last_game:'2026-09-27',games:3,routes:null,expected_catches:21,actual_catches:16,catch_model_targets:30}},player_game_usage:{}}}};const e=P.assess(c,{...o,context});assert.equal(e.points,3);assert.ok(e.facts.some(x=>x[1].includes('not expected yards')));assert.ok(e.facts.some(x=>x[1].includes('routes unavailable')));});
test('NCAA game evidence never needs NFL player-role fields',()=>{const game={...c,kind:'game',sport:'ncaa',profileId:null,market:'total',side:'Under',line:48.5,modelMean:44},currentGameEvidence={sport:'ncaa',home:'NO',away:'ATL',season:2026,totalContext:45,homeGames:4,awayGames:4};const e=P.assess(game,{...o,currentRoleEvidence:null,currentGameEvidence});assert.equal(e.evidenceTier,3);assert.equal(e.eligible,true);});
test('standard line, opposite sides and duplicate minute-shift/book observations are consolidated',()=>{const rows=[c,{...c,book:'Other',updatedAt:'2026-10-05T16:30:00Z',kickoff:'2026-10-06T00:16:00Z'},{...c,side:'Under',projMean:65,projSd:20,prob:.4},{...c,line:15.5,odds:-1000,dec:1.1,prob:.99}];const b=P.board(rows,o);assert.equal(b.picks.length,1);assert.equal(b.picks[0].candidate.line,55.5);assert.equal(b.picks[0].candidate.side,'Over');assert.equal(b.picks[0].candidate.book,'Other');});
test('card leads with bet/rating/why/risk/price, methodology is progressive and escaped',()=>{const e=P.assess({...c,player:'<img>'},o),text=P.card({candidate:{...c,player:'<img>'},evidence:e},{label:'Over 55.5 Receiving yards'});assert.match(text,/GOING <b>50\/100/);assert.match(text,/WHY/);assert.match(text,/CONCERN/);assert.match(text,/PRICE NEEDS REFRESH/);assert.match(text,/&lt;img&gt;/);assert.match(text,/<details/);assert.doesNotMatch(text,/Current support|Developing|Check first|High confidence/);});
test('formerly tied cases separate by directional gap relative to model spread, not probability or price',()=>{
 const close=P.assess({...c,projMean:61},o),clear=P.assess({...c,projMean:67.5},o),wide=P.assess({...c,projMean:67.5,projSd:40},o);
 assert.equal(close.evidenceTier,clear.evidenceTier);assert.ok(clear.rating>close.rating);assert.ok(clear.rating>wide.rating);
 assert.equal(P.assess({...c,projMean:67.5,prob:.99,goingScore:99,odds:400,dec:5},o).rating,clear.rating);
 const rows=[{...c,profileId:'z',projMean:61},{...c,profileId:'a',projMean:67.5}],options=x=>({...o,currentRoleEvidence:{...o.currentRoleEvidence,playerId:x.profileId}});
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
 const down=P.assess({...w,roleTrend:shrink},o);assert.ok(down.badges.includes('ROLE ↓ vs Over'));assert.ok(down.concerns.some(x=>/shrunk/.test(x)));
 assert.equal(P.assess({...w,roleTrend:null},o).facts.some(x=>x[0].startsWith('Role trend')),false);
 // A quarterback has no snap/target/carry-share role in passing markets: never a role badge.
 assert.equal(P.assess({...w,position:'QB',roleTrend:shrink},o).badges.some(x=>x.startsWith('ROLE')),false);
});
test('GoingIntel gives one role answer per position (same on every page); QBs and passing markets have none',()=>{
 const I=require('../shared/going-intel.js'),t={snap_share:{l3:60,l6:75},target_share:{l3:.1,l6:.2},carry_share:{l3:.3,l6:.5}};
 assert.deepEqual(I.roleTrend(t,'WR','receptions').parts.map(x=>x.metric),['snap_share','target_share']);
 assert.deepEqual(I.roleTrend(t,'RB','rush_yds').parts.map(x=>x.metric),['snap_share','carry_share','target_share']);
 for(const m of ['rec_yds','rush_yds','atd'])assert.equal(I.roleTrend(t,'RB',m).state,I.roleTrend(t,'RB','rec_yds').state);
 assert.equal(I.roleTrend(t,'QB','pass_yds'),null);assert.equal(I.roleTrend(t,'WR','pass_yds'),null);
 assert.equal(I.roleTrend({snap_share:{l3:80,l6:80},carry_share:{l3:0,l6:0}},'WR','atd').parts.length,1);
 const now=Date.parse('2026-10-09T12:00:00Z');
 assert.equal(I.activeProfile({id:'a',last_game:'2026-10-04'},null,now),true);assert.equal(I.activeProfile({id:'a',last_game:'2025-01-05'},null,now),false);
 assert.equal(I.activeProfile({id:'a',last_game:'2026-10-04'},I.unavailableIds({x:{gsis_id:'a',roster_status:'RES'}}),now),false);
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
 assert.ok(e.badges.includes('SCORING ROLE'));assert.ok(e.facts.some(x=>x[0]==='Scoring role'&&/primary scoring role/i.test(x[1])));assert.equal(e.components.some(x=>x.id==='scoring_role'),false);assert.equal(e.points,P.assess({...td,scoringRole:null},o).points);
 assert.ok(e.concerns.some(x=>/more than his opportunity predicts/.test(x)));
 assert.equal(P.assess({...c,position:'RB',scoringRole:sr},o).facts.some(x=>x[0]==='Scoring role'),false);// not a touchdown market
});

test('collapse() merges same-thesis rows for display and keeps the best-rated first; board() itself does not collapse',()=>{
 const mk=(market,line)=>({candidate:{kind:'prop',away:'MIN',home:'NO',profileId:'p',market,side:'Over',line},evidence:{rating:50}});
 const rows=[mk('rec_yds',42.5),mk('receptions',4.5),{candidate:{kind:'prop',away:'MIN',home:'NO',profileId:'q',market:'rec_yds',side:'Over',line:50.5},evidence:{rating:40}}];
 const out=P.collapse(rows);assert.equal(out.length,2);assert.equal(out[0].related.length,1);assert.equal(out[0].related[0].candidate.market,'receptions');
 assert.match(P.card({...out[0],evidence:{...P.assess(c,o),rating:50,family:'Receiving',badges:[],components:[],ratingDetail:{strength:null},facts:[],unknown:[],concerns:[],why:'w',concern:'c',price:P.quote(c,o.now),key:'k'},offers:[]},{label:'x'}),/SAME THESIS/);
});

test('v3: missed time and an injured higher-depth teammate are surfaced; game lines cap at tier 3; sub-0.25-SD gaps earn nothing',()=>{
 const players={'NO|player':{gsis_id:'p',position:'RB',roster_status:'ACT',depth_rank:2,games:2,roster_week:5,name:'Player'},'NO|starter':{gsis_id:'s',name:'Starter',team:'NO',position:'RB',roster_status:'ACT',depth_rank:1,games:4,roster_week:5}};
 players['NO|player'].team='NO';
 const reports={'NO|starter':{name:'Starter',practice_status:'Did Not Participate In Practice',report_status:null,primary_injury:'Hamstring'}};
 const under={...c,market:'rush_yds',side:'Under',line:70.5,projMean:40,projSd:30,position:'RB'},opts={...o,injuryLearning:{current_players:players,current_reports:reports}};
 const e=P.assess(under,opts);
 assert.ok(e.concerns.some(x=>/Appeared in 2 of his team's 4 games/.test(x)));assert.ok(e.concerns.some(x=>/Starter \(depth 1, same position\) did not practice/.test(x)));assert.ok(e.components.some(x=>x.id==='teammate'&&x.points===-1));
 assert.equal(P.assess({...under,side:'Over',projMean:100},opts).components.some(x=>x.id==='teammate'),false);// context only for an Over
 const flat=P.assess({...c,projMean:56.5},o);assert.equal(flat.components.some(x=>x.id==='model'),false);assert.ok(flat.unknown.some(x=>/quarter of a standard deviation/.test(x)));
 const neg=P.assess({...c,projMean:-0.3,projSd:3.5,line:.5,side:'Under'},o);assert.equal(neg.components.some(x=>x.id==='model'),false);
 const game=P.assess({...c,kind:'game',sport:'nfl',market:'total',side:'Over',line:41.5,modelMean:50,modelSd:8,profileId:null},{...o,currentRoleEvidence:null,currentGameEvidence:{sport:'nfl',home:'NO',away:'ATL',season:2026,totalContext:50,homeGames:4,awayGames:4}});
 assert.ok(game.evidenceTier<=3);assert.match(game.concern,/Game script|moves|line/i);
});


test('presentation never represents ungraded ATD or neutral game score floors as confidence',()=>{
 const td={...c,market:'atd',side:'Yes',line:.5,prob:.95},opts={...o,currentRoleEvidence:{...o.currentRoleEvidence,tdAppearances:2}};
 const e=P.assess(td,opts),before=structuredClone(e),html=P.card({candidate:td,evidence:e},{label:'Anytime TD'});
 assert.equal(e.rating,1);assert.match(html,/TD role research/);assert.doesNotMatch(html,/1\/100|95\/100/);assert.match(html,/95.0% win/);assert.deepEqual(e,before);
 const game={...c,kind:'game',market:'spread',side:'Home',line:-3.5,modelMean:3.5,modelSd:14},gopts={...o,currentGameEvidence:{sport:'nfl',home:'NO',away:'ATL',season:2026,marginContext:5,homeGames:4,awayGames:4}};
 const ge=P.assess(game,gopts);assert.equal(ge.rating,1);assert.equal(P.ratingPresentation(game,ge).label,'Current-season forecast lean');
 assert.doesNotMatch(P.card({candidate:game,evidence:ge},{label:'Home -3.5'}),/1\/100/);
 const unknown=P.assess(game,{...o,currentGameEvidence:null});assert.equal(P.ratingPresentation(game,unknown).label,'No model lean');
 const directional=P.assess({...game,modelMean:8},gopts);assert.equal(P.ratingPresentation(game,directional).numeric,true);assert.match(P.card({candidate:{...game,modelMean:8},evidence:directional},{label:'Home -3.5'}),/GOING <b>\d+\/100/);
});


test('anchored moneyline favorites never acquire a numerical independent-confidence headline',()=>{
 const ml={...c,kind:'game',market:'moneyline',side:'Home',line:0,modelMean:8,modelSd:12.75,gameAnchor:{version:'market-anchor-v1',applicable:true}},e=P.assess(ml,{...o,currentRoleEvidence:null});
 assert.equal(e.components.find(x=>x.id==='model').points,2);assert.equal(P.ratingPresentation(ml,e).numeric,false);assert.equal(P.ratingPresentation(ml,e).label,'Market baseline');
 const html=P.card({candidate:ml,evidence:e},{label:'Home moneyline'});assert.match(html,/market information, not independent model confidence/);assert.doesNotMatch(html,/GOING <b>\d+\/100/);
 assert.equal(P.ratingPresentation({...ml,gameAnchor:{applicable:false}},e).numeric,true);
});


test('all-market display exposes positive spread and total without changing frozen ranks or inventing rows',()=>{
 const mk=(id,market,interesting=true)=>({candidate:{kind:'game',market,contract:id},evidence:{key:id,rating:market==='moneyline'?50:1,interesting}}),rows=[...Array.from({length:7},(_,i)=>mk('ml'+i,'moneyline')),mk('spread','spread'),mk('total','total')],original=structuredClone(rows);
 assert.deepEqual(P.displayMix(rows,{mix:true,limit:6}).map(x=>x.evidence.key),['spread','total','ml0','ml1','ml2','ml3']);assert.deepEqual(rows,original);
 assert.deepEqual(P.displayMix(rows,{mix:false,limit:6}),rows.slice(0,6));
 assert.equal(P.displayMix([...rows,rows[7]],{limit:99}).length,9);assert.deepEqual(P.displayMix(rows,{limit:0}),[]);
 const absent=[...rows.slice(0,7),mk('no-support','total',false)];assert.deepEqual(P.displayMix(absent,{limit:6}),absent.slice(0,6));
 const totalOnly=[...rows.slice(0,7),rows[8]];assert.equal(P.displayMix(totalOnly,{limit:6})[0],rows[8]);
 assert.equal(P.displayMix(rows,{limit:99}).length,rows.length);assert.deepEqual(P.displayMix(null),[]);
});


test('current-season scoring facts show forecast and exact total/spread direction without changing probabilities',()=>{
 const base={...c,kind:'game',modelMean:46,modelSd:13.3,gameAnchor:{applicable:true}},g={sport:'nfl',home:'NO',away:'ATL',season:2026,totalContext:47,marginContext:2,homeGames:4,awayGames:4};
 for(const [market,line,side,expected] of [['total',44.5,'Over','supports'],['total',44.5,'Under','opposes'],['spread',-3.5,'Home','opposes'],['spread',-3.5,'Away','supports']]){
  const candidate={...base,market,line,side},e=P.assess(candidate,{...o,currentGameEvidence:g}),fact=e.facts.find(x=>x[0]==='Forecast lean vs this line');
  assert.match(fact[1],new RegExp(expected+' '+side));const html=P.card({candidate,evidence:e},{label:'test'});assert.ok(html.indexOf('CURRENT-SEASON FORECAST')<html.indexOf('<details'));assert.match(html,new RegExp(expected+' '+side));assert.equal(candidate.prob,.6);assert.ok(e.facts.some(x=>x[0]==='Current-season total estimate'&&x[1].includes('47.0 points')));assert.ok(e.facts.some(x=>x[0]==='Current-season margin estimate'&&x[1].includes('2.0 points')));assert.match(e.facts.find(x=>x[0]==='Scoring estimator')[1],/home team points scored/);
 }
 const missing=P.assess({...base,market:'total',line:44.5,side:'Over'},{...o,currentGameEvidence:null});assert.equal(missing.facts.some(x=>x[0]==='Forecast lean vs this line'),false);
});
