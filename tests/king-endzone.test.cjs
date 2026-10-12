const {test}=require('node:test'),assert=require('node:assert/strict');
const {markup}=require('../shared/king-endzone.js');
test('Jackpot renders complete ranked field, missing probabilities and shared-winner explanation',()=>{
 const candidates=Array.from({length:24},(_,i)=>({name:i===23?'<unsafe>':'Player '+i,team:'BUF',kind:'player',probability:i===23?null:.1,uncertainty:'High',evidence:['Real history'],eligible:'Check selection'}));
 const html=markup({slate:{date:'2026-09-17',games:[{away:'DET',home:'BUF',kickoff:'2026-09-18T00:15:00Z'}],offer:{cutoff:'2026-09-18T00:20:00Z',note:'Terms'},candidates,generated_at:'2026-09-16T12:00:00Z'},results:[]},Date.parse('2026-09-16T12:00:00Z'));
 assert.equal((html.match(/<li>/g)||[]).length,24);assert.match(html,/Not enough data/);assert.match(html,/need not total 100/);assert.match(html,/&lt;unsafe&gt;/);assert.doesNotMatch(html,/Entries closed/);
});

test('A played slate is never shown as a current recommendation',()=>{
 const K=require('../shared/king-endzone.js'),S=require('../shared/slate-breaker.js');
 const games=[{id:'g',away:'DET',home:'BUF',kickoff:'2026-09-17T23:20:00+00:00'}],now=Date.parse('2026-10-09T12:00:00Z');
 const king=K.markup({slate:{date:'2026-09-17',games,candidates:[{name:'X',kind:'player',team:'BUF',probability:.2,evidence:[]}],offer:{cutoff:'2026-09-18T00:20:00Z'}},results:[]},now);
 assert.match(king,/No current King of the Endzone offer/);assert.doesNotMatch(king,/king-list/);
 assert.match(S.markup({slate:{games,selections:[]}},now),/No current Slate Breaker slate/);
});

const K=require('../shared/king-endzone.js');
const now=Date.parse('2026-10-12T15:00:00Z');
const game={home:'LA',away:'BUF',kickoff:'2026-10-13T00:15:00Z'};
const candidates=[.2,.18,.16,.1].map((p,i)=>({id:'p'+i,name:'P'+i,team:'BUF',kind:'player',probability:p,td_probability:.5,evidence:[]}));
const slate={date:'2026-10-12',games:[game],candidates,generated_at:'2026-10-12T14:00:00Z',offer:{note:'Verify terms'}};
const quote=(id,odds)=>({profileId:id,market:'atd',bookKey:'draftkings',overOdds:odds,kickoff:game.kickoff,eventTeams:['BUF','LA'],updatedAt:'2026-10-12T14:00:00Z'});
const context={eligibility:()=>({actionable:true}),quoteState:()=>null,props:[quote('p0',150),quote('p1',400),quote('p2',300),quote('p3',1000)]};
test('Highlights separate longest chance from highest actual price among top five',()=>{
 const x=K.highlights(slate,context,now);assert.equal(x.top.id,'p0');assert.equal(x.alternative.c.id,'p3');
 assert.match(K.markup({slate},now,context),/Higher-paying alternative/);
});
test('Quotes fail closed for other books, games, identities, clocks and invalid odds',()=>{
 for(const mutation of [{bookKey:'fanatics'},{kickoff:'invalid'},{kickoff:'2026-10-12T00:15:00Z'},{eventTeams:['BUF','ATL']},{profileId:'other'},{updatedAt:'2026-10-12T16:00:00Z'},{updatedAt:'2026-10-12T10:00:00Z'},{overOdds:99}]){
  assert.equal(K.priceFor(candidates[0],slate,{...context,props:[{...quote('p0',150),...mutation}]},now),null);
 }
 assert.equal(K.priceFor(candidates[0],slate,{...context,quoteState:()=> 'stale'},now),null);
});
test('Latest quote wins rather than cherry-picking old higher price',()=>{
 const q=quote('p0',120);q.updatedAt='2026-10-12T14:30:00Z';
 assert.equal(K.priceFor(candidates[0],slate,{...context,props:[quote('p0',500),q]},now).overOdds,120);
});
test('Unavailable and unknown athletes never become highlighted selections',()=>{
 assert.equal(K.highlights(slate,{...context,eligibility:id=>({actionable:id!=='p0'})},now).top.id,'p1');
 assert.equal(K.highlights(slate,{},now).top,undefined);
 assert.match(K.markup({slate},now,{}),/availability is unverified/);
});
test('Started or stale slate has no current highlight cards',()=>{
 assert.doesNotMatch(K.markup({slate},Date.parse(game.kickoff),context),/class="king-highlights"/);
 assert.match(K.markup({slate:{...slate,generated_at:'2026-10-09T00:00:00Z'}},now,context),/selections paused/);
});
test('The 60-second render refetches rather than pinning the first response',async()=>{
 const priorFetch=global.fetch,priorDocument=global.document,priorNow=Date.now;
 let clock=now,requests=0;const target={innerHTML:''};
 global.document={getElementById:()=>target};Date.now=()=>clock;
 global.fetch=async()=>{requests++;return {ok:true,json:async()=>({slate:{...slate,date:requests===1?'2026-10-12':'2026-10-19'}})};};
 try{await K.render(context);assert.equal(requests,1);clock+=60000;await K.render(context);assert.equal(requests,2);assert.match(target.innerHTML,/2026-10-19/);}finally{global.fetch=priorFetch;global.document=priorDocument;Date.now=priorNow;}
});

test('A lower single payout can never be advertised as higher-paying',()=>{
 const x=K.highlights(slate,{...context,props:[quote('p0',900),quote('p1',150),quote('p2',200)]},now);
 assert.equal(x.alternative,null);
 assert.equal(K.highlights(slate,{...context,props:[quote('p1',400)]},now).alternative,null);
});
