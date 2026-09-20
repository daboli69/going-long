const {test}=require('node:test'),assert=require('node:assert/strict');const {decimal,optimize}=require('../shared/touchdown-promo.js');
const now=Date.parse('2026-09-13T12:00:00Z'),settings={now,slateDate:'2026-09-13'};
const leg=(id,odds=200,p=.4,event=id)=>({playerId:id,event,player:id,book:'fanatics',market:'atd',line:.5,odds,probability:p,kickoff:'2026-09-13T17:00:00Z',updatedAt:'2026-09-13T11:59:00Z',availability:'expected'});
test('Correct American conversion and strict 21.0 decimal floor',()=>{assert.equal(decimal(2000),21);assert.equal(decimal(-200),1.5);assert.equal(optimize([leg('A',200),leg('B',200),leg('C',100)],settings).options.length,0);assert.equal(optimize([leg('A',200),leg('B',250),leg('C',100)],settings).options[0].decimal,21);});
test('Ranks by hit estimate, not highest odds, with five unique options',()=>{const result=optimize([leg('A'),leg('B'),leg('C'),leg('D'),leg('E',1000,.1)],settings);assert.equal(result.options.length,5);assert.ok(result.options[0].legs.every(l=>l.playerId!=='E'));assert.equal(new Set(result.options.map(x=>x.key)).size,5);});
test('Diversifies suggested tickets so the top scorer is not in every option',()=>{const result=optimize([leg('A',200,.75),leg('B',200,.45),leg('C',200,.44),leg('D',200,.43),leg('E',200,.42),leg('F',200,.41),leg('G',200,.4)],settings);assert.equal(result.options.length,5);const exposure={};for(const option of result.options)for(const item of option.legs)exposure[item.playerId]=(exposure[item.playerId]||0)+1;assert.ok(Math.max(...Object.values(exposure))<result.options.length);assert.equal(Math.max(...Object.values(exposure)),result.maxPlayerAppearances);});
test('Stale, injured, other-book and non-anytime lines cannot qualify',()=>{for(const changes of [{availability:'questionable'},{book:'fanduel'},{line:1.5},{updatedAt:'2026-09-12T12:00:00Z'}])assert.equal(optimize([leg('A'),leg('B'),{...leg('C'),...changes}],settings).options.length,0);});
test('Same-game combinations require ticket odds and never claim a modeled joint chance',()=>{const input=[leg('A',200,.4,'game'),leg('B',200,.4,'game'),leg('C')];assert.equal(optimize(input,{...settings,includeSameGame:true}).sameGame.length,0);const key=input.map(x=>x.event+'|'+x.playerId).sort().join('~');const out=optimize(input,{...settings,includeSameGame:true,ticketAmerican:{[key]:2200}});assert.equal(out.sameGame[0].probability,null);assert.equal(out.sameGame[0].decimal,23);});

test('Sunday and optional individual price settings are validated',()=>{
 assert.throws(()=>optimize([],{...settings,slateDate:'2026-09-14'}),/Sunday/);
 assert.throws(()=>optimize([],{...settings,minimumLegAmerican:0}),/Individual/);
});
test('Automatic roster screening excludes injuries, reserves and missing injury data',async()=>{
 const {rosterPlayers}=await import('../server/promo-availability.mjs');
 const body={timestamp:new Date(now).toISOString(),athletes:[{items:[
 {fullName:'Healthy Player',status:{type:'active'},injuries:[]},
 {fullName:'Hurt Player',status:{type:'active'},injuries:[{status:'Questionable'}]},
 {fullName:'Reserve Player',status:{type:'reserve'},injuries:[]},
 {fullName:'Unknown Player',status:{type:'active'}}]}]};
 assert.deepEqual(rosterPlayers(body,now).players.map(p=>p.availability),['expected','unavailable','unavailable','unavailable']);
 assert.throws(()=>rosterPlayers({...body,timestamp:'2025-01-01'},now),/stale/);
 assert.throws(()=>rosterPlayers({...body,athletes:[]},now),/unavailable/);
});
