'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const P=require('../shared/football-picks.js'),T=require('../shared/tonight-board.js');
const now=Date.parse('2026-10-12T19:00:00Z'),kickoff='2026-10-13T00:15:00Z';
const candidate={kind:'prop',sport:'nfl',home:'LA',away:'BUF',team:'LA',player:'Player',profileId:'p',kickoff,market:'rec_yds',side:'Over',line:55.5,projMean:65,projSd:20,prob:.6,book:'Book A',odds:-110,dec:1+100/110,updatedAt:new Date(now-60000).toISOString(),n:12};
function row(patch={},key='p') {const c={...candidate,...patch};return {candidate:c,evidence:{key,gameKey:P.gameKey(c),eligible:true,interesting:true,rating:50,components:[{id:'model',points:2}],facts:[['Current-season usage','4 current-season games']],family:'Receiving',why:'Targets support the direction',concern:'Opponent may reduce volume',price:P.quote(c,now),ratingDetail:{strength:.5}},offers:[]};}
test('tonight uses Eastern calendar date across UTC midnight and removes started/tomorrow games',()=>{
 const schedule=[candidate,{...candidate,kickoff:'2026-10-12T18:59:00Z'},{...candidate,home:'NYG',kickoff:'2026-10-14T00:15:00Z'}];
 assert.equal(T.todayGames(schedule,[],now).length,1);assert.equal(T.dateKey(kickoff),'2026-10-12');assert.equal(T.todayGames(schedule,[],Date.parse(kickoff)).length,0);
});
test('best same-line payout wins while newest quote per book supersedes earlier better odds',()=>{
 const r=row();r.offers=[{book:'Book A',odds:150,updatedAt:new Date(now-120000).toISOString()},{book:'Book B',odds:105,updatedAt:new Date(now-60000).toISOString()}];
 assert.deepEqual(T.offersFor(r,now).map(x=>[x.candidate.book,x.candidate.odds]),[['Book B',105],['Book A',-110]]);
 assert.equal(T.selectRows([r],{game:r.evidence.gameKey,book:'Book A',now})[0].candidate.odds,-110);
 assert.equal(r.candidate.odds,-110);
});
test('fresh offer outranks better stale price and extreme/future/expired quotes are excluded',()=>{
 const r=row();r.offers=[{book:'Saved',odds:200,updatedAt:new Date(now-3600000).toISOString()},{book:'Extreme',odds:-40000,updatedAt:candidate.updatedAt},{book:'Future',odds:200,updatedAt:new Date(now+1).toISOString()},{book:'Expired',odds:200,updatedAt:new Date(now-86400001).toISOString()}];
 assert.deepEqual(T.offersFor(r,now).map(x=>x.candidate.book),['Book A','Saved']);
});
test('unsupported, unavailable and opposite directions do not become recommendations',()=>{
 const a=row(),unsupported=row({side:'Under'},'under');unsupported.evidence.interesting=false;
 const out=row({injury:{blockRecommendation:true}},'out'),invalid=row({},'invalid');invalid.evidence.eligible=false;
 assert.equal(T.selectRows([a,unsupported,out,invalid],{game:a.evidence.gameKey,now}).length,1);
 assert.equal(T.selectRows([a],{game:a.evidence.gameKey,market:'total',now}).length,0);
});
test('saved prices remain visible for research, have explicit labels and cannot be saved as fresh',()=>{
 const dom=new JSDOM('<div id="host"></div>'),host=dom.window.document.getElementById('host'),r=row({updatedAt:new Date(now-3600000).toISOString()});
 T.render(host,{board:{picks:[r]},schedule:[candidate],now,onSave:()=>{throw Error('must not save');}});
 assert.match(host.textContent,/SAVED PRICE/);assert.match(host.textContent,/0 recent prices/);assert.equal(host.querySelector('[data-tonight-save]').disabled,true);
});
test('filters, research-open state and keyboard focus survive a subsequent refresh without duplicate handlers',()=>{
 const dom=new JSDOM('<div id="host"></div>'),host=dom.window.document.getElementById('host'),r=row(),options={board:{picks:[r]},schedule:[candidate],now};
 T.render(host,options);const select=host.querySelector('[data-tonight-control="market"]');select.value='props';select.focus();select.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
 const detail=host.querySelector('details[data-tonight-detail]');detail.open=true;detail.ontoggle();T.render(host,options);
 assert.equal(host.querySelector('[data-tonight-control="market"]').value,'props');assert.equal(host.querySelector('details[data-tonight-detail]').open,true);assert.equal(dom.window.document.activeElement.dataset.tonightControl,'market');
});
test('saved shortlist diagnoses exact price changes, lost quotes and common-game exposure without joint odds',()=>{
 const a=row(),saved={...candidate,label:'Saved over',odds:105};assert.match(T.savedRows([saved],[a],now)[0].status,/Price changed/);
 assert.match(T.savedRows([saved],[row({updatedAt:new Date(now-3600000).toISOString()})],now)[0].status,/unavailable/);
 const dom=new JSDOM('<div id="host"></div>'),host=dom.window.document.getElementById('host');T.render(host,{board:{picks:[a]},schedule:[candidate],saved:[saved,{...saved,profileId:'other'}],now});
 assert.match(host.textContent,/same game/);assert.match(host.textContent,/No combined hit rate/);
});
test('card markup escapes imported names and prices never contaminate the model direction',()=>{
 const dom=new JSDOM('<div id="host"></div>'),host=dom.window.document.getElementById('host'),r=row({player:'<img src=x onerror=alert(1)>',book:'<script>Book</script>'});
 T.render(host,{board:{picks:[r]},schedule:[candidate],now});assert.equal(host.querySelector('img'),null);assert.equal(host.querySelector('script'),null);assert.match(host.textContent,/Targets support/);
});

test('a newer extreme or malformed price cannot resurrect an older attractive quote at the same book',()=>{
 for(const odds of [-40000,-85,NaN]){const r=row();r.offers=[{book:'Book A',odds,updatedAt:new Date(now-30000).toISOString()}];assert.equal(T.offersFor(r,now).length,0);}
});
