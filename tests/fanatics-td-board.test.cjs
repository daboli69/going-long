const {test}=require('node:test'),assert=require('node:assert/strict');
const UI=require('../shared/fanatics-td-ui.js'),O=require('../shared/td-opportunity.js');
const NOW=Date.parse('2026-10-17T12:00:00Z'),KICK='2026-10-18T17:00:00Z',ctx={now:NOW,slateDate:'2026-10-18'};
const sr=(x,o={})=>({version:1,as_of:'2026-10-11',n:12,confidence:'ok',xtd_pg_l12:x,xtd_pg_l6:x,snap_pct_l3:.7,snap_pct_l6:.7,rz_tgt_pg_l12:1,gl_carry_pg_l12:0,inside5_touch_pg_l12:0,td_pg_l12:x,td_luck_l12:0,tier:'PRIMARY',trend:{d_xtd36:0,d_snap36:0},...o});
const leg=(id,p,x,o={})=>({playerId:id,player:id.toUpperCase(),team:'AAA',opp:'BBB',kickoff:KICK,probability:p,availability:'active',eligibility:{actionable:true,state:'active',label:'Active'},price:null,
 opportunity:O.describe({scoring_role:sr(x),role_trend:{last_game:{season:2026,week:5}}},{now:NOW,kickoff:KICK}),...o});
test('players need both availability checks; confirmed-out players are excluded and unresolved ones are flagged, never treated as active',()=>{
 const legs=[leg('ok',.30,.5),leg('out',.60,.9,{eligibility:{actionable:false,state:'out',label:'Ruled out'}}),leg('doubt',.55,.8,{eligibility:{actionable:false,state:'doubtful',label:'Doubtful'}}),
  leg('unver',.50,.7,{eligibility:null}),leg('roster',.45,.6,{availability:'unavailable'}),leg('unknownstate',.44,.6,{eligibility:{actionable:false,state:'unverified',label:'Availability unverified'}})];
 const d=UI.boardData(legs,ctx);
 assert.deepEqual(d.confirmed.map(l=>l.playerId),['ok']);
 assert.deepEqual(d.unresolved.map(l=>l.playerId).sort(),['roster','unknownstate','unver']);
 assert.equal(Object.entries(d.excluded).filter(([k])=>/confirmed unavailable/.test(k)).reduce((n,[,v])=>n+v,0),2);
 assert.ok(d.byProbability.every(l=>l.playerId==='ok'));
});
test('the probability list and the opportunity list answer different questions and can disagree',()=>{
 const legs=[leg('likely',.40,.2),leg('profile',.25,.9),leg('mid',.30,.5)];
 const d=UI.boardData(legs,ctx);
 assert.deepEqual(d.byProbability.map(l=>l.playerId),['likely','mid','profile']);
 assert.deepEqual(d.byOpportunity.map(l=>l.playerId),['profile','mid','likely']);
});
test('stale, future-dated or missing opportunity data keeps a player out of the opportunity list but not out of the probability list',()=>{
 const stale=leg('stale',.35,2,{opportunity:O.describe({scoring_role:sr(2,{as_of:'2026-08-01'}),role_trend:{last_game:{season:2026,week:1}}},{now:NOW,kickoff:KICK})});
 const future=leg('future',.34,3,{opportunity:O.describe({scoring_role:sr(3,{as_of:'2026-10-25'})},{now:NOW,kickoff:KICK})});
 const none=leg('none',.33,0,{opportunity:O.describe({},{now:NOW,kickoff:KICK})});
 const d=UI.boardData([stale,future,none,leg('good',.20,.4)],ctx);
 assert.equal(d.byProbability.length,4);assert.deepEqual(d.byOpportunity.map(l=>l.playerId),['good']);
});
test('only this Sunday slate, with a valid model estimate and a game that has not started',()=>{
 const d=UI.boardData([leg('mon',.3,.5,{kickoff:'2026-10-20T00:15:00Z'}),leg('started',.3,.5,{kickoff:'2026-10-17T11:00:00Z'}),leg('noprob',null,.5),leg('one',1,.5),leg('fine',.2,.5)],ctx);
 assert.deepEqual(d.confirmed.map(l=>l.playerId),['fine']);assert.equal(d.excluded['no model estimate'],2);
});
test('the board renders without any Fanatics price, labels payout-share ranking unavailable and shows freshness and availability wording',()=>{
 const html=UI.boardMarkup([leg('a',.3,.5),leg('b',.2,.9,{eligibility:null})],ctx);
 assert.match(html,/3\. Best jackpot selection after payout sharing/);assert.match(html,/Unavailable\. The jackpot is shared/);assert.match(html,/No Fanatics price/);
 assert.match(html,/Role data through 2026-10-11 \(6 days old, 12 games\)/);assert.match(html,/1 player with unresolved availability \(not treated as active\)/);
 assert.match(html,/Not official game-day clearance/);assert.doesNotMatch(html,/guarantee|lock\b/i);
});
test('an escaped player name cannot inject markup',()=>{
 const html=UI.boardMarkup([leg('x',.3,.5,{player:'<img src=x onerror=1>'})],ctx);
 assert.doesNotMatch(html,/<img/);assert.match(html,/&lt;img/);
});
