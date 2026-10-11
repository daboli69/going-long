const {test}=require('node:test'),assert=require('node:assert/strict');
const {select}=require('../shared/football-parlays.js');
const now=Date.parse('2026-09-13T12:00:00Z'),settings={sport:'nfl',now,start:'2026-09-08',last:'2026-09-14'};
const leg=(id,event=id,book='fanatics')=>({sport:'nfl',kind:'prop',profileId:id,event,book,kickoff:'2026-09-13T17:00:00Z',updatedAt:new Date(now).toISOString(),market:'rec_yds',n:12,prob:.6,odds:100,dec:2,ev:.2,push:0,flags:[]});
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

test('Custom leg counts and odds ranges apply without silently returning fewer legs',()=>{
 const pool=['a','b','c','d'].map(id=>leg(id));
 const result=select(pool,{...settings,legs:3,minOdds:600,maxOdds:800});
 assert.equal(result.parlay.legs.length,3);assert.equal(result.parlay.decimal,8);
 assert.equal(select(pool,{...settings,legs:5}).parlay,null);
 assert.equal(select(pool,{...settings,legs:3,minOdds:900}).parlay,null);
 assert.equal(select(pool,{...settings,legs:3,maxOdds:500}).parlay,null);
 assert.throws(()=>select(pool,{...settings,minOdds:0}),/valid American/);
 assert.throws(()=>select(pool,{...settings,legs:7}),/2 and 6/);
 assert.equal(select(pool,{...settings,book:'draftkings'}).parlay,null);
 assert.equal(select(pool,{...settings,kind:'game'}).parlay,null);
});
test('SGP respects requested leg count but never claims a target ticket price',()=>{
 const pool=['a','b','c'].map(id=>leg(id,'g'));
 const result=select(pool,{...settings,legs:3,minOdds:2000});
 assert.equal(result.sgp.legs.length,3);assert.equal(result.sgp.decimal,null);
 assert.equal(select(pool,{...settings,legs:4}).sgp,null);
});

test('Game selections constrain both builders and clearing games returns no suggestions',()=>{
 const pool=[leg('a','one'),leg('b','one'),leg('c','two'),leg('d','three')];
 assert.equal(select(pool,{...settings,events:[]}).parlay,null);
 assert.equal(select(pool,{...settings,events:[]}).sgp,null);
 const only=select(pool,{...settings,events:['one']});assert.equal(only.parlay,null);assert.ok(only.sgp.legs.every(r=>r.event==='one'));
 const pair=select(pool,{...settings,events:['two','three']}).parlay;assert.deepEqual(pair.legs.map(r=>r.event),['two','three']);
});

test('Profit boost applies to winnings only and can turn a negative ticket positive',()=>{
 const {profitBoost}=require('../shared/football-parlays.js');
 const b=profitBoost(.3,3,50,10);assert.equal(b.boostedDecimal,4);assert.ok(Math.abs(b.returnPerDollar-.2)<1e-10);assert.equal(b.profitIfWin,30);assert.ok(Math.abs(b.breakEvenBoost-16.6666666667)<1e-6);
 const pool=[{...leg('a'),prob:.5,odds:-100/.9,dec:1.9,ev:-.05},{...leg('b'),prob:.5,odds:-100/.9,dec:1.9,ev:-.05}];
 assert.equal(select(pool,settings).parlay,null);assert.ok(select(pool,{...settings,boostPercent:50}).parlay.boost.returnPerDollar>0);
 assert.throws(()=>profitBoost(.5,2,-1),/boost/);
});

test('Tickets identify their weakest leg and a compatible replacement',()=>{
 const pool=[{...leg('a','one'),prob:.7},{...leg('b','two'),prob:.55},{...leg('c','three'),prob:.5},{...leg('d','four'),prob:.49}];
 const ticket=select(pool,{...settings,legs:2}).parlay;
 assert.equal(ticket.weakestLeg.profileId,'b');
 assert.equal(ticket.replacement.remove.profileId,'b');
 assert.equal(ticket.replacement.add.profileId,'c');
 assert.equal(new Set(ticket.replacement.legs.map(row=>row.event)).size,2);
});

test('Same-game replacement preserves the game and avoids a second outcome for one entity',()=>{
 const pool=[{...leg('a','g'),prob:.7},{...leg('b','g'),prob:.55},{...leg('c','g'),prob:.5},{...leg('a-alt','g'),profileId:'a',prob:.68,market:'receptions'}];
 const ticket=select(pool,{...settings,legs:2}).sgp;
 assert.equal(ticket.weakestLeg.profileId,'b');
 assert.equal(ticket.replacement.add.profileId,'c');
 assert.equal(ticket.replacement.probability,null);
 assert.equal(ticket.replacement.decimal,null);
});

const {manage,alternatives,summarize}=require('../shared/football-parlays.js');
const quote=(id,event=id,book='fanatics')=>({...leg(id,event,book),side:'Over',line:50.5,odds:100});
const gameQuote=(id,event=id)=>({...quote(id,event),kind:'game',profileId:'',market:'total',side:'Over',line:45.5});

test('User edits preserve the other legs and the position of a swapped leg',()=>{
 const a=quote('a'),b=quote('b'),c=quote('c'),d=quote('d'),pool=[a,b,c,d],original=[a,b,c];
 const swapped=manage(original,pool,settings,{type:'swap',index:1,row:d});
 assert.equal(swapped.ok,true);assert.deepEqual(swapped.legs,[a,d,c]);
 assert.equal(swapped.legs[0],a);assert.equal(swapped.legs[2],c);assert.deepEqual(original,[a,b,c]);
 assert.equal(swapped.ticket.probability,.216);assert.equal(swapped.ticket.decimal,8);
 const removed=manage(original,pool,settings,{type:'remove',index:1});
 assert.deepEqual(removed.legs,[a,c]);assert.equal(removed.ticket.ready,true);
 const added=manage(removed.legs,pool,settings,{type:'add',row:d});
 assert.deepEqual(added.legs,[a,c,d]);assert.equal(added.ticket.boost.profitIfWin,70);
});

test('Alternatives are bounded, unique, scoped, and cannot move the ticket to another book',()=>{
 const a=quote('a'),b=quote('b'),candidates=Array.from({length:12},(_,i)=>quote('alt'+i));
 const pool=[a,b,...candidates,{...candidates[0]},quote('wrong-book','other','draftkings'),{...quote('wrong-sport'),sport:'ncaa'},quote('unselected')];
 const options={...settings,events:['a','b',...candidates.map(r=>r.event)]};
 const choices=alternatives([a,b],pool,options,{index:1,limit:99});
 assert.equal(choices.length,6);assert.equal(new Set(choices.map(r=>r.profileId)).size,6);
 assert.ok(choices.every(r=>r.book==='fanatics'&&r.profileId.startsWith('alt')));
 assert.deepEqual(alternatives([a,b],pool,{...options,events:[]},{index:1}),[]);
 const wrong=manage([a,b],pool,settings,{type:'swap',index:0,row:pool.find(r=>r.book==='draftkings')});
 assert.equal(wrong.ok,false);assert.deepEqual(wrong.legs,[a,b]);
});

test('Managed legs need real, matching, fresh unstarted quotes rather than just an identity',()=>{
 const a=quote('a'),b=quote('b');
 const changes=[{odds:undefined},{odds:0},{odds:100,dec:3},{dec:Infinity},{kickoff:undefined},{updatedAt:undefined},{kickoff:new Date(now).toISOString()},{updatedAt:new Date(now-86400001).toISOString()},{updatedAt:new Date(now+1).toISOString()},{manual:true},{dfs:true},{trust:{review:true}},{flags:[{id:'check'}]},{push:.1},{market:'first_td'},{market:'rec_yds_1h'}];
 for(const change of changes){
  const invalid={...b,...change};
  assert.equal(manage([a],[a,invalid],settings,{type:'add',row:invalid}).ok,false,JSON.stringify(change));
  assert.equal(summarize([a,invalid],[a,invalid],settings).valid,false,JSON.stringify(change));
 }
 assert.equal(manage([a],[a,b],settings,{type:'add',row:{...b,prob:.7}}).ok,false);
 assert.equal(manage([a],[a,b],settings,{type:'add',row:{...b,updatedAt:new Date(now-60000).toISOString()}}).ok,false);
 assert.equal(summarize([a,b],[a],settings).valid,false);
 const invalid=summarize([a,b],[a],settings);assert.equal(invalid.probability,null);assert.equal(invalid.decimal,null);assert.equal(invalid.boost,null);
});

test('Managed date filters use Eastern dates and NCAA never offers player props',()=>{
 const a=quote('a'),evening={...quote('evening'),kickoff:'2026-09-14T02:00:00Z'},tomorrow={...quote('tomorrow'),kickoff:'2026-09-14T04:01:00Z'};
 const day={...settings,start:'2026-09-13',last:'2026-09-13'};
 assert.deepEqual(alternatives([a],[a,evening,tomorrow],day).map(r=>r.profileId),['evening']);
 assert.equal(manage([a],[a,tomorrow],day,{type:'add',row:tomorrow}).ok,false);
 const games=['a','b'].map(id=>({...gameQuote(id),sport:'ncaa'})),prop={...quote('prop'),sport:'ncaa'};
 const ncaa={...settings,sport:'ncaa'};
 assert.equal(summarize(games,[...games,prop],ncaa).ready,true);
 assert.deepEqual(alternatives([games[0]],[...games,prop],ncaa).map(r=>r.event),['b']);
 assert.equal(manage([games[0]],[...games,prop],ncaa,{type:'add',row:prop}).ok,false);
 assert.deepEqual(alternatives([],games,{...ncaa,kind:'prop'}),[]);
});

test('Same-game edits keep the game, book, and independent entities without inventing combined prices',()=>{
 const a=quote('a','g'),b=quote('b','g'),c=quote('c','g'),other=quote('other','other'),opposite={...a,side:'Under'},playerAlt={...quote('alt','g'),profileId:'a',market:'receptions'};
 const total=gameQuote('total','g'),under={...total,side:'Under'},spread={...total,market:'spread',side:'Home'},moneyline={...spread,market:'moneyline',line:undefined};
 const pool=[a,b,c,other,opposite,playerAlt,total,under,spread,moneyline],options={...settings,sameGame:true};
 const result=manage([a,b],pool,options,{type:'swap',index:1,row:c});
 assert.equal(result.ok,true);assert.equal(result.ticket.ready,true);
 for(const name of ['probability','decimal','estimatedReturn','boost'])assert.equal(result.ticket[name],null);
 assert.equal(manage([a,b],pool,options,{type:'swap',index:0,row:other}).ok,false);
 for(const row of [opposite,playerAlt])assert.equal(manage([a,b],pool,options,{type:'add',row}).ok,false);
 assert.equal(manage([a,total],pool,options,{type:'add',row:under}).ok,false);
 assert.equal(manage([a,spread],pool,options,{type:'add',row:moneyline}).ok,false);
 const boostedNegative={...c,ev:-.05};assert.equal(manage([a,b],[a,b,boostedNegative],{...options,boostPercent:50},{type:'add',row:boostedNegative}).ok,false);
});

test('An empty draft can restart, six legs cannot grow, and invalid edits preserve the draft',()=>{
 const pool=Array.from({length:7},(_,i)=>quote('q'+i)),first=pool[0];
 const cleared=manage([first],pool,settings,{type:'remove',index:0});
 assert.equal(cleared.ok,true);assert.deepEqual(cleared.legs,[]);assert.equal(cleared.ticket.valid,true);assert.equal(cleared.ticket.ready,false);
 assert.equal(cleared.ticket.probability,null);
 assert.equal(manage([],pool,settings,{type:'add',row:first}).ok,true);
 assert.equal(alternatives([],pool,settings).length,6);
 assert.equal(manage(pool.slice(0,6),pool,settings,{type:'add',row:pool[6]}).ok,false);
 assert.deepEqual(alternatives(pool.slice(0,6),pool,settings),[]);
 for(const action of [{type:'remove',index:-1},{type:'swap',index:1,row:pool[1]},{type:'add',row:first},{type:'unknown'}]){
  const result=manage([first],pool,settings,action);assert.equal(result.ok,false);assert.deepEqual(result.legs,[first]);
 }
 assert.equal(summarize([null],pool,settings).valid,false);
 assert.equal(manage([null],pool,settings,{type:'add',row:first}).ok,false);
 assert.equal(summarize([{}],pool,settings).valid,false);
 assert.equal(summarize([],pool,{...settings,start:'bad'}).valid,false);
});

test('Removing an unavailable leg repairs a draft, and odds constraints remain visible after removal',()=>{
 const a=quote('a'),b=quote('b'),c=quote('c'),pool=[a,b,c],options={...settings,minOdds:700,maxOdds:900};
 assert.equal(summarize([a,b,c],pool,options).ready,true);
 const smaller=manage([a,b,c],pool,options,{type:'remove',index:1});
 assert.equal(smaller.ok,true);assert.equal(smaller.ticket.valid,true);assert.equal(smaller.ticket.ready,false);
 assert.match(smaller.ticket.issues.join(' '),/odds range/);
 assert.deepEqual(alternatives([a],pool,options),[]);
 assert.equal(manage(smaller.legs,pool,options,{type:'add',row:b}).ok,true);
 const stale={...b,updatedAt:new Date(now-86400001).toISOString()};
 assert.equal(manage([a,stale,c],pool,settings,{type:'add',row:b}).ok,false);
 const repair=manage([a,stale,c],pool,settings,{type:'remove',index:1});assert.equal(repair.ok,true);assert.equal(repair.ticket.valid,true);
 assert.equal(manage([a,stale,c],pool,settings,{type:'swap',index:1,row:b}).ok,false,'same contract cannot be silently repriced by swapping');
});

test('Malformed quote metadata and extreme combined estimates never become ticket prices',()=>{
 const a=quote('a'),b=quote('b'),bad={...b,canonicalContract:{invalid:true}};
 assert.equal(summarize([a,bad],[a,bad],settings).valid,false);
 assert.deepEqual(alternatives([a],[a,bad],settings),[]);
 const huge=[a,b].map(r=>({...r,odds:1e308,dec:1e306}));
 const overflow=summarize(huge,huge,settings);assert.equal(overflow.valid,false);assert.equal(overflow.decimal,null);assert.equal(overflow.probability,null);
 const tiny=[a,b].map(r=>({...r,prob:1e-300}));
 const underflow=summarize(tiny,tiny,settings);assert.equal(underflow.valid,false);assert.equal(underflow.decimal,null);assert.equal(underflow.boost,null);
});

test('Same-game legs are explained as complements, conflicts or the same thesis',()=>{
 const I=require('../shared/going-intel.js'),g={event:'e',home:'NO',away:'MIN',kind:'prop',dec:1.9};
 const qb={...g,player:'QB One',team:'MIN',market:'pass_yds',side:'Over',line:240.5},wr={...g,player:'WR One',profileId:'w1',team:'MIN',market:'rec_yds',side:'Over',line:60.5};
 assert.equal(I.legRelations([qb,wr])[0].kind,'complement');
 assert.equal(I.legRelations([qb,{...wr,side:'Under'}])[0].kind,'conflict');
 const under={event:'e',home:'NO',away:'MIN',kind:'game',market:'total',side:'Under',line:44.5},over={...under,side:'Over'};
 assert.equal(I.legRelations([under,wr])[0].kind,'conflict');assert.equal(I.legRelations([over,wr])[0].kind,'complement');
 const fav={event:'e',home:'NO',away:'MIN',kind:'game',market:'moneyline',side:'Away',line:0,dec:1.5},rb={...g,player:'RB One',team:'MIN',market:'rush_yds',side:'Over',line:60.5};
 assert.equal(I.legRelations([fav,rb])[0].kind,'complement');assert.equal(I.legRelations([fav,{...rb,team:'NO'}])[0].kind,'conflict');
 assert.deepEqual(I.legRelations([wr,{...wr,event:'other'}]),[]);// different games are independent
 assert.equal(I.legRelations([wr,{...wr,market:'receptions',line:5.5}])[0].kind,'same-thesis');
});

test('Parlay relations follow football logic: Under+Under fits, Under total fits a run game and conflicts with touchdowns, nested scoring legs are one thesis',()=>{
 const I=require('../shared/going-intel.js'),g={event:'e',home:'NO',away:'MIN',kind:'prop',dec:1.9};
 const qb={...g,player:'Q',profileId:'q',team:'MIN',market:'pass_yds',side:'Under',line:240.5},wr={...g,player:'W',profileId:'w',team:'MIN',market:'rec_yds',side:'Under',line:60.5};
 assert.equal(I.legRelations([qb,wr])[0].kind,'complement');
 const under={event:'e',home:'NO',away:'MIN',kind:'game',market:'total',side:'Under',line:38.5},rb={...g,player:'R',profileId:'r',team:'MIN',market:'rush_yds',side:'Over',line:70.5};
 assert.equal(I.legRelations([under,rb])[0].kind,'complement');
 const td={...g,player:'R',profileId:'r',team:'MIN',market:'atd',side:'Over',line:.5};
 assert.equal(I.legRelations([under,td])[0].kind,'conflict');assert.equal(I.legRelations([{...under,side:'Over'},td])[0].kind,'complement');
 assert.equal(I.legRelations([td,{...td,market:'rush_tds'}])[0].kind,'same-thesis');
 const smallFav={event:'e',home:'NO',away:'MIN',kind:'game',market:'moneyline',side:'Away',dec:1.8};assert.deepEqual(I.legRelations([smallFav,rb]),[]);// a small favourite says nothing about script
});


test('Extreme short favorites cannot enter builds, same-game ideas, alternatives, edits or restored drafts',()=>{
 const a=quote('a','one'),b=quote('b','two'),extreme={...quote('extreme','three'),odds:-40000,dec:1.0025,prob:.999,ev:.0015};
 const pool=[a,b,extreme],built=select(pool,settings);
 assert.deepEqual(built.parlay.legs.map(r=>r.profileId),['a','b']);
 assert.equal(built.diagnostics.shortPrices,1);assert.equal(built.diagnostics.minLegAmerican,-500);
 assert.equal(select([a,extreme],settings).parlay,null);
 assert.equal(select([a,{...extreme,event:'one'}],settings).sgp,null);
 assert.equal(manage([a],pool,settings,{type:'add',row:extreme}).ok,false);
 assert.equal(manage([a,b],pool,settings,{type:'swap',index:1,row:extreme}).ok,false);
 assert.equal(summarize([a,extreme],pool,settings).valid,false);
 assert.deepEqual(alternatives([a],pool,settings).map(r=>r.profileId),['b']);
 const boundary={...quote('boundary'),odds:-500,dec:1.2,prob:.84,ev:.008};
 assert.ok(select([a,boundary],settings).parlay);
 assert.equal(select([a,{...boundary,odds:-501,dec:1+100/501}],settings).parlay,null);
});

test('Automatic builds share exact price, malformed metadata and unresolved availability gates with edits',()=>{
 const a=quote('a'),b=quote('b');
 for(const change of [{odds:undefined},{odds:0},{odds:100,dec:3},{canonicalContract:{}},{injury:{stale:true}},{injury:{blockRecommendation:true}},{availability:{eligible:false}},{flags:{id:'check'}}]){
  const bad={...b,...change};assert.equal(select([a,bad],settings).parlay,null,JSON.stringify(change));
  assert.equal(select([{...a,event:'same'},{...bad,event:'same'}],settings).sgp,null,JSON.stringify(change));
 }
 const empty=select([],settings);assert.equal(empty.diagnostics.eligible,0);assert.match(empty.diagnostics.reason,/No supported current quotes/);
 assert.throws(()=>select([a,b],{...settings,start:'invalid'}),/valid football sport/);
});

test('Supporting football/price evidence ranks ahead of raw modeled chance without boosting probabilities',()=>{
 const high={...quote('high','one'),prob:.8},a=quote('a','two'),b=quote('b','three');
 a.flags=[{id:'pressure',family:'matchup',why:'Observed current pressure matchup.'}];
 b.parlayEvidence={supported:true,reasons:['Current-season team totals support this direction.']};
 const result=select([high,a,b],settings).parlay;
 assert.deepEqual(result.legs.map(r=>r.profileId),['a','b']);assert.equal(result.evidenceLegs,2);
 assert.equal(result.probability,.36);assert.equal(result.decimal,4);
 assert.deepEqual(alternatives([a],[a,high,b],settings).map(r=>r.profileId),['b','high']);
 const modelOnly={...high,flags:[{id:'gap',family:'model',why:'Modeled price gap.'}]};
 assert.equal(select([modelOnly,a,b],settings).parlay.evidenceLegs,2);
 const sgp=select([high,a,b].map(r=>({...r,event:'same'})),settings).sgp;
 assert.deepEqual(sgp.legs.map(r=>r.profileId),['a','b']);assert.equal(sgp.probability,null);
});


test('Small randomized evidence-first searches match exhaustive different-game enumeration',()=>{
 let seed=20261011;const random=()=>((seed=Math.imul(seed,1664525)+1013904223>>>0)/4294967296);
 for(let trial=0;trial<40;trial++){
  const pool=Array.from({length:12},(_,i)=>{const prob=.51+random()*.11;return {...quote('p'+i,'g'+Math.floor(i/2)),prob,ev:prob*2-1,flags:random()<.5?[{id:'pace',family:'role',why:'Observed current pace.'}]:[]};});
  let expected=null;
  for(let i=0;i<pool.length;i++)for(let j=i+1;j<pool.length;j++)for(let k=j+1;k<pool.length;k++){
   const legs=[pool[i],pool[j],pool[k]];if(new Set(legs.map(r=>r.event)).size!==3)continue;
   const support=legs.filter(r=>r.flags.length).length,probability=legs.reduce((p,r)=>p*r.prob,1);
   if(!expected||support>expected.support||support===expected.support&&probability>expected.probability)expected={support,probability};
  }
  const actual=select(pool,{...settings,legs:3,minOdds:600,maxOdds:800}).parlay;
  assert.equal(actual.evidenceLegs,expected.support);assert.ok(Math.abs(actual.probability-expected.probability)<1e-12);
 }
});
