const {test}=require('node:test'),assert=require('node:assert/strict');
const {select}=require('../shared/football-parlays.js');
const now=Date.parse('2026-09-13T12:00:00Z'),settings={sport:'nfl',now,start:'2026-09-08',last:'2026-09-14'};
const leg=(id,event=id,book='fanatics')=>({sport:'nfl',kind:'prop',profileId:id,event,book,kickoff:'2026-09-13T17:00:00Z',updatedAt:new Date(now).toISOString(),market:'rec_yds',n:12,prob:.6,dec:2,ev:.2,push:0,flags:[]});
test('Different-game best parlay uses a single book and actual per-leg prices',()=>{
 const result=select([leg('a'),leg('b'),{...leg('c'),prob:.5}],settings).parlay;
 assert.equal(result.probability,.36);assert.equal(result.decimal,4);
 assert.equal(select([leg('a'),leg('b','b','draftkings')],settings).parlay,null);
});
test('Same-game suggestion has no invented ticket odds or joint probability',()=>{
 const result=select([leg('a','g'),leg('b','g')],settings);
 assert.equal(result.parlay,null);assert.equal(result.sgp.probability,null);assert.equal(result.sgp.decimal,null);
 assert.equal(select([leg('a','g'),{...leg('a','g'),side:'Under'}],settings).sgp,null);
});
test('Reject started, stale, future-week, negative-return and extreme estimates',()=>{
 for(const change of [{kickoff:new Date(now-1).toISOString()},{updatedAt:new Date(now-86400001).toISOString()},{kickoff:'2026-09-21T17:00:00Z'},{ev:-.1},{ev:.8},{push:.1},{n:2}])assert.equal(select([leg('a'),{...leg('b'),...change}],settings).parlay,null);
});
