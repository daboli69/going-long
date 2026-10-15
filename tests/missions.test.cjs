const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const M=require('../shared/missions.js'),W=require('../config/sharp_weights.json');
const NOW=Date.parse('2026-10-14T15:00:00Z'),iso=ms=>new Date(ms).toISOString().replace('.000Z','Z'),fresh=iso(NOW-60e3);
const T=['Kansas City Chiefs','Buffalo Bills','Denver Broncos','Seattle Seahawks','Green Bay Packers','Dallas Cowboys'];
const bk=(key,h2h,spread,total,last=fresh)=>({key,title:key,last_update:last,markets:[
 ...(h2h?[{key:'h2h',last_update:last,outcomes:[{name:'HOME',price:h2h[0]},{name:'AWAY',price:h2h[1]}]}]:[]),
 ...(spread?[{key:'spreads',last_update:last,outcomes:[{name:'HOME',price:spread[1],point:spread[0]},{name:'AWAY',price:spread[2],point:-spread[0]}]}]:[]),
 ...(total?[{key:'totals',last_update:last,outcomes:[{name:'Over',price:total[1],point:total[0]},{name:'Under',price:total[2],point:total[0]}]}]:[])]});
const fix=(s,home,away)=>JSON.parse(JSON.stringify(s).replaceAll('HOME',home).replaceAll('AWAY',away));
// Five books agree at -150/+130; "sharpbook" hangs +150 on the home moneyline: a real, checkable price edge.
function event(i,{home=T[i*2],away=T[i*2+1],extra=[],edge=true}={}){
 const books=['a','b','c','d','e'].map((k,j)=>bk(k,[-150+j,130-j],[-3.5,-110,-110],[44.5,-110,-110]));
 books.push(bk('shop',[edge?-125:-150,edge?105:130],[-3.5,-110,-110],[44.5,-110,-110]));
 return fix({id:'ev'+i,home_team:'HOME',away_team:'AWAY',commence_time:iso(NOW+4*3600e3+i*60e3),bookmakers:[...books,...extra]},home,away);
}
const run=(events,input={})=>M.runMission(events,{now:NOW,objective:'cash-out',weights:W.game_lines,aliases:W.aliases,oddsGeneratedAt:iso(NOW),mission:{runs:2000,...(input.mission||{})},...input,mission:{runs:2000,...(input.mission||{})}});

test('team table covers all 32 NFL teams with unique codes',()=>{
 assert.equal(Object.keys(M.TEAM_CODES).length,32);assert.equal(new Set(Object.values(M.TEAM_CODES)).size,32);
});
test('a price better than the independent consensus qualifies, with executable odds and stated evidence',()=>{
 const r=run([event(0)]),q=r.qualified.find(o=>o.source==='shop'&&o.market==='moneyline'&&o.side==='A');
 assert.ok(q,'edge offer qualifies');assert.equal(q.american,'-125'); // the posted price, not an invented one
 assert.ok(q.ev>M.POLICY.minEv);assert.ok(q.consensus.sources>=4);assert.equal(q.clv,null);
 assert.ok(r.qualified.every(o=>o.source==='shop'||o.ev>=M.POLICY.minEv));
 assert.ok(Math.abs(q.win+q.loss+q.push-1)<1e-12);
});
test('a book is judged only against other books, never against itself',()=>{
 const {offers}=M.buildOffers([event(0)],{now:NOW,weights:W.game_lines,aliases:W.aliases});
 const o=offers.find(x=>x.source==='shop'&&x.market==='moneyline'&&x.side==='A');
 assert.ok(!o.consensus.used.some(u=>u.source==='shop'));assert.equal(o.consensus.sources,5);
});
test('exchange prices inform consensus but are never certified as executable',()=>{
 const ex=bk('novig',[-125,105],null,null);
 const {offers}=M.buildOffers([event(0,{extra:[fix(ex,'Kansas City Chiefs','Buffalo Bills')],edge:false})],{now:NOW,weights:W.game_lines,aliases:W.aliases});
 const n=offers.filter(o=>o.source==='novig');assert.ok(n.length>0&&n.every(o=>o.exchange&&!o.qualified&&o.reasons.some(r=>/Exchange/.test(r))));
});
test('integer lines need a push probability and are rejected; moneylines carry the existing tie rate',()=>{
 const ev=event(0);for(const b of ev.bookmakers)for(const m of b.markets)if(m.key==='spreads')for(const o of m.outcomes)o.point=o.name===ev.home_team?-3:3;
 const {offers}=M.buildOffers([ev],{now:NOW,weights:W.game_lines,aliases:W.aliases});
 assert.ok(offers.filter(o=>o.market==='spread').every(o=>!o.qualified&&/Integer line/.test(o.reasons[0])));
 assert.equal(offers.find(o=>o.market==='moneyline'&&o.ev!=null).push,M.POLICY.tieRate);
});
test('stale offers, too few sources and wide disagreement do not qualify',()=>{
 const stale=event(0);stale.bookmakers.find(b=>b.key==='shop').markets.forEach(m=>m.last_update=iso(NOW-3600e3));
 assert.ok(!run([stale]).qualified.some(o=>o.source==='shop'));
 const few=event(0);few.bookmakers=few.bookmakers.slice(3);assert.equal(run([few]).qualified.length,0);
 const wide=event(0);wide.bookmakers.forEach((b,i)=>b.markets.forEach(m=>{if(m.key==='h2h'){m.outcomes[0].price=[-300,150,-110,-250,200,-125][i];m.outcomes[1].price=[260,-170,-110,210,-240,105][i];}}));
 const w=M.buildOffers([wide],{now:NOW,weights:W.game_lines,aliases:W.aliases}).offers.filter(o=>o.market==='moneyline'&&o.reasons?.some(r=>/disagree/.test(r)));assert.ok(w.length>0);
});
test('copied prices are clustered once and cannot create an apparent consensus',()=>{
 const evs=Array.from({length:8},(_,i)=>{const e=event(0,{home:'H'+i,away:'A'+i});e.id='c'+i;
  const a=e.bookmakers.find(b=>b.key==='a');for(const m of a.markets)if(m.key==='spreads'){m.outcomes[0].price=-112;m.outcomes[1].price=-108;}
  e.bookmakers.find(b=>b.key==='b').markets=JSON.parse(JSON.stringify(a.markets));return e;});
 const {diagnostics,offers}=M.buildOffers(evs,{now:NOW});
 assert.deepEqual(diagnostics.copyClusters,[['a','b']]);
 const o=offers.find(x=>x.source==='shop'&&x.market==='moneyline'&&x.side==='A'),c=o.consensus.used;
 assert.equal(c.find(u=>u.source==='a').share,c.find(u=>u.source==='b').share);
 // a and b are one cluster: each carries half a vote, so two copies weigh as much as one independent source
 assert.ok(Math.abs(c.find(u=>u.source==='a').share-.5/(3+1))<1e-9);
 const judged=offers.find(x=>x.source==='a'&&x.market==='moneyline');assert.ok(!judged.consensus.used.some(u=>u.source==='b'),'a book is not judged against its own copy');
});
test('GOING model cross-check: anchored spread/total probabilities are labelled as adding no information, stale snapshots are ignored',()=>{
 const model={odds_generated_at:iso(NOW),rows:[{book:'shop',kickoff:event(0).commence_time,home:'KC',away:'BUF',market:'spread',side:'Home',line:-3.5,odds:-110,prob:.5,push:0,n:12,ev:-.045}]};
 const {offers,diagnostics}=M.buildOffers([event(0)],{now:NOW,weights:W.game_lines,aliases:W.aliases,model,oddsGeneratedAt:iso(NOW)});
 const o=offers.find(x=>x.source==='shop'&&x.market==='spread'&&x.side==='A');assert.ok(o.model.anchoredToLine);assert.match(o.warnings[0],/market-anchored/);assert.equal(diagnostics.modelRows,1);
 const old=M.buildOffers([event(0)],{now:NOW,weights:W.game_lines,aliases:W.aliases,model:{...model,odds_generated_at:iso(NOW-24*3600e3)},oddsGeneratedAt:iso(NOW)});
 assert.ok(old.diagnostics.modelNote&&old.offers.every(x=>!x.model));
 const veto={...model,rows:[{...model.rows[0],market:'moneyline',side:'Home',line:0,prob:.3,ev:-.5}]};
 const v=M.buildOffers([event(0)],{now:NOW,weights:W.game_lines,aliases:W.aliases,model:veto,oddsGeneratedAt:iso(NOW)}).offers.find(x=>x.source==='shop'&&x.market==='moneyline'&&x.side==='A');
 assert.equal(v.qualified,false);assert.ok(v.reasons.some(r=>/model probability/.test(r)));
});
test('same-game legs are classified, never given an invented joint probability',()=>{
 const a={eventId:'e',market:'moneyline',side:'A'},b={eventId:'e',market:'spread',side:'A'},c={eventId:'e',market:'spread',side:'B'},d={eventId:'e',market:'total',side:'A'},z={eventId:'z',market:'total',side:'A'};
 assert.equal(M.classifyPair(a,b).relation,'redundant-dependent');assert.equal(M.classifyPair(a,c).relation,'contradictory');
 assert.equal(M.classifyPair(b,d).relation,'dependent-unestimated');assert.equal(M.classifyPair(b,z).relation,'independent-assumed');
 assert.equal(M.classifyPair(b,c).relation,'contradictory');
});
test('parlays combine only qualified legs from different games at one book; EV uses the exact pushes-aware product',()=>{
 const r=run([event(0),event(1),event(2)],{policy:{}});
 const ps=r.parlays;assert.ok(ps.length>0);
 for(const p of ps){assert.equal(new Set(p.legs.map(l=>l.eventId)).size,p.legs.length);assert.equal(new Set(p.legs.map(l=>l.source)).size,1);assert.equal(p.priceVerified,false);
  const dec=p.legs.reduce((m,l)=>m*l.dec,1),ev=p.legs.reduce((m,l)=>m*(l.win*l.dec+l.push),1)-1;assert.ok(Math.abs(p.dec-dec)<1e-9&&Math.abs(p.ev-ev)<1e-9);assert.ok(p.ev>=M.POLICY.minEv);}
 const one=M.buildParlays(run([event(0)]).qualified.filter(o=>o.eventId==='ev0'));assert.equal(one.parlays.length,0);
});
test('simulation compares the no-bet baseline with straight, parlay and mixed strategies and attaches paired results',()=>{
 const r=run([event(0),event(1),event(2)]);
 const ids=r.strategies.map(s=>s.id);assert.deepEqual(ids,['none','straights','parlays','mixed']);
 const none=r.strategies[0].result;assert.equal(none.pReachTarget,0);assert.equal(none.expectedEnding,50);
 for(const s of r.strategies)assert.equal(s.result.runs,2000);
 assert.ok(r.strategies[1].tickets.every(t=>t.stake>0&&t.stake<=50*r.mission.exposure));
 assert.ok(r.diagnostics.assumptions.some(a=>/independence/.test(a)));
});
test('when nothing qualifies the result says so and simulates only labelled negative-return references',()=>{
 const r=run([event(0,{edge:false}),event(1,{edge:false})]);
 assert.equal(r.qualified.length,0);assert.deepEqual(r.strategies.map(s=>s.id).filter(x=>x!=='none').every(x=>x.startsWith('ref-')),true);
 assert.ok(r.strategies.filter(s=>s.reference).every(s=>s.qualified===false));
 const ref=r.strategies.find(s=>s.id==='ref-parlay');assert.ok(ref&&ref.tickets[0].ev<0);
});
test('preferred sportsbooks and bet-type settings constrain the candidate set',()=>{
 assert.equal(run([event(0)],{mission:{books:['a']}}).qualified.length,0);
 const s=run([event(0),event(1)],{mission:{betTypes:'straights'}}).strategies.map(x=>x.id);assert.ok(!s.includes('parlays')&&!s.includes('mixed'));
 const p=run([event(0),event(1),event(2)],{mission:{betTypes:'parlays'}}).strategies.map(x=>x.id);assert.ok(!p.includes('straights'));
});
test('objectives rank differently but use the same qualified set',()=>{
 const evs=[event(0),event(1),event(2)];
 const ids=o=>new Set(run(evs,{objective:o}).qualified.map(x=>x.id));
 const a=ids('survival');for(const o of ['growth','parlay','cash-out'])assert.deepEqual([...ids(o)].sort(),[...a].sort());
 assert.throws(()=>run(evs,{mission:{target:10}}),/Invalid mission settings/);
});
test('real snapshot replay: every offer carries a price that exists in the feed; nothing is fabricated',()=>{
 const raw=JSON.parse(fs.readFileSync('data/nfl_betting.json','utf8')),model=JSON.parse(fs.readFileSync('data/missions_model.json','utf8'));
 const r=M.runMission(raw.games_raw,{now:Date.parse(raw.generated_at),weights:W.game_lines,aliases:W.aliases,model,oddsGeneratedAt:raw.generated_at,mission:{runs:500}});
 const prices=new Set();for(const e of raw.games_raw)for(const b of e.bookmakers)for(const m of b.markets)for(const o of m.outcomes)prices.add(o.price);
 assert.ok(r.diagnostics.offerCount>100);
 for(const s of r.strategies)for(const t of s.tickets)for(const l of t.legs)assert.ok(prices.has(l.odds),'posted odds only');
 for(const o of r.qualified){assert.ok(o.ev>=M.POLICY.minEv);assert.ok(!o.exchange);}
 assert.equal(r.strategies[0].id,'none');
});
test('when nothing qualifies the closest executable prices are listed with their reasons',()=>{
 const r=run([event(0,{edge:false})]);
 assert.equal(r.qualified.length,0);assert.ok(r.nearMisses.length>0&&r.nearMisses.length<=5);
 assert.ok(r.nearMisses.every(n=>n.reasons.length>0&&Number.isFinite(n.ev)&&n.sources>=4));
 assert.ok(r.nearMisses.every((n,i,a)=>i===0||a[i-1].ev>=n.ev));
 assert.equal(new Set(r.nearMisses.map(n=>n.id.split('|').slice(0,4).join('|'))).size>=1,true);
});
