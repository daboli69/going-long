const {test}=require('node:test'),assert=require('node:assert/strict');
const MF=require('../shared/market-fair.js'),SC=require('../shared/sharp-consensus.js');
const NOW=Date.parse('2026-10-18T14:00:00Z'),iso=ms=>new Date(ms).toISOString(),fresh=iso(NOW-60e3),KICK=iso(NOW+3*3600e3);
const dec=o=>SC.americanToDecimal(o);
// One game row per book, like BET.games. Prices: five books agree near -110/-110 on the same total; "shop" differs.
const book=(key,over,under,total=44.5,o={})=>({id:'ev1|'+key,source:'parlay',book:key,bookKey:key,home:'Home',away:'Away',kickoff:KICK,updatedAt:fresh,marketTimes:{totals:fresh,spreads:fresh,h2h:fresh},
 total,overOdds:over,underOdds:under,spread:-3.5,homeSpreadOdds:-110,awaySpreadOdds:-110,mlHome:-170,mlAway:150,...o});
const games=[book('a',-110,-110),book('b',-112,-108),book('c',-108,-112),book('d',-110,-110),book('e',-111,-109),book('shop',+105,-125)];
const index=MF.build(games,{now:NOW,eventKey:()=>'EV'});
// An anchored game row exactly as the generator emits it: probability pinned to 50% at the line, ev = 0.5 * price - 1.
const row=(o={})=>({kind:'game',sport:'nfl',event:'EV',market:'total',side:'Over',line:44.5,book:'shop',odds:105,dec:dec(105),prob:.5,push:0,ev:.5*dec(105)-1,updatedAt:fresh,n:12,
 reference:{win:SC.devigPair(dec(105),dec(-125),'proportional').pA,push:0,loss:SC.devigPair(dec(105),dec(-125),'proportional').pB},flags:[{id:'gap',family:'model',why:'Historical model estimates $1.03 returned per $1'},{id:'price',family:'market',why:'x'}],...o});
const close=(a,b,t=1e-9)=>assert.ok(Math.abs(a-b)<=t,`${a} vs ${b}`);

test('expected return is exact for odds, break-even, push and invalid input',()=>{
 close(MF.evFor(.5,2,0),0);close(MF.evFor(1/dec(-110),dec(-110),0),0);close(MF.evFor(.55,dec(-110),0),.55*dec(-110)-1);
 close(MF.evFor(.45,2,.1),.45*1-.45);              // win .45 at 2.0 with a .10 push: +.45 - .45 loss = 0
 assert.equal(MF.evFor(.6,1,0),null);assert.equal(MF.evFor(NaN,2,0),null);assert.equal(MF.evFor(.7,2,.4),null);assert.equal(MF.evFor(-.1,2,0),null);
});
test('a 50% model at the posted line is replaced by the other books\' consensus; the unsupported +EV does not survive',()=>{
 const a=MF.annotate(row(),index);
 assert.equal(a.modelProb,.5);assert.ok(a.modelEv>.02,'generator value preserved for the record');
 assert.equal(a.probSource,'market_consensus');assert.equal(a.independentModel,false);
 assert.ok(a.marketFair.ok&&a.marketFair.sources===5&&a.marketFair.source==='shop'&&a.marketFair.dispersion<.015);
 close(a.ev,MF.evFor(a.prob,dec(105),0));assert.ok(Math.abs(a.prob-.5)<.02);
 assert.ok(!a.flags.some(f=>f.id==='gap'),'the model-gap claim is removed');assert.ok(a.modelFlags.some(f=>f.id==='gap'));
 assert.match(a.flags.find(f=>f.id==='basis').why,/anchored to the line and adds no independent probability/);
 assert.ok(a.flags.some(f=>f.id==='price'),'unrelated market flags survive');
});
test('both sides of one contract use the same consensus (probabilities sum to one)',()=>{
 const o=MF.annotate(row(),index),u=MF.annotate(row({side:'Under',odds:-125,dec:dec(-125),reference:{win:.55,push:0,loss:.45}}),index);
 close(o.marketFair.p+u.marketFair.p,1,1e-9);
});
test('a book is never judged against itself or its copy cluster',()=>{
 const g=games.map(x=>({...x}));
 const idx=MF.build(g,{now:NOW,eventKey:()=>'EV'});
 const a=MF.annotate(row({book:'a'}),idx);
 assert.ok(!a.marketFair.source||a.marketFair.source==='a');
 const withShop=MF.fairFor(idx,row({book:'a'}));close(withShop.sources,5);   // b,c,d,e,shop
});
test('different lines are different contracts; too few books falls back to the book\'s own de-vigged price with no edge claim',()=>{
 const odd=[book('a',-110,-110),book('b',-110,-110,45.5),book('c',-110,-110,46.5),book('d',-110,-110,47.5),book('shop',+105,-125)];
 const idx=MF.build(odd,{now:NOW,eventKey:()=>'EV'});
 const a=MF.annotate(row(),idx);
 assert.equal(a.probSource,'book_implied');assert.equal(a.edgeSupported,false);assert.ok(a.ev<0,'vig makes the own-price estimate negative');
 assert.match(a.flags.find(f=>f.id==='basis').why,/Fewer than 4 independent books/);
 const wide=MF.annotate(row({line:44.5}),MF.build([...games.slice(0,5).map((g,i)=>({...g,overOdds:[-150,+130,-110,-200,+160][i],underOdds:[+130,-150,-110,+170,-190][i]})),games[5]],{now:NOW,eventKey:()=>'EV'}));
 assert.equal(wide.probSource,'book_implied');assert.match(wide.marketFair.reason,/disagree/);
});
test('stale quotes, exchange prices and non-games never produce a supported edge; unsupported rows are dropped',()=>{
 const stale=MF.annotate(row({updatedAt:iso(NOW-3600e3)}),index);assert.equal(stale.edgeSupported,false);assert.match(stale.flags.at(-1).why,/more than 15 minutes old/);
 const ex=MF.annotate(row({book:'novig'}),MF.build([...games,book('novig',+105,-125)],{now:NOW,eventKey:()=>'EV'}));
 assert.equal(ex.edgeSupported,false);assert.match(ex.flags.at(-1).why,/Exchange price/);
 const prop={kind:'prop',market:'rec_yds',prob:.6,ev:.2};assert.equal(MF.annotate(prop,index),prop);
 assert.equal(MF.annotate(row({reference:null,event:'NOPE'}),index),null);
});
test('push probability: win is conditional on no push and expected return keeps the returned stake',()=>{
 const a=MF.annotate(row({line:44,push:.06,ev:.1}),MF.build(games.map(g=>({...g,total:44})),{now:NOW,eventKey:()=>'EV'}));
 close(a.prob,a.marketFair.p*.94,1e-12);close(a.ev,MF.evFor(a.prob,dec(105),.06),1e-12);
});
test('started games, one-sided books and untimed quotes are ignored when building the index',()=>{
 const idx=MF.build([book('x',-110,null),book('y',-110,-110,44.5,{marketTimes:{totals:'nonsense'},updatedAt:'nonsense'}),book('z',-110,-110,44.5,{kickoff:iso(NOW-1)})],{now:NOW,eventKey:()=>'EV'});
 assert.equal(idx.events.size,0+idx.events.size);assert.ok(idx.skipped.oneSided>0&&idx.skipped.noTime>0);
 assert.equal([...idx.events.values()].reduce((n,e)=>n+e.markets.total.length,0),0);
});
