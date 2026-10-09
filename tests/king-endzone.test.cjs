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
