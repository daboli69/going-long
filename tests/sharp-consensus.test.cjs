const {test}=require('node:test'),assert=require('node:assert/strict');
const S=require('../shared/sharp-consensus.js'),W=require('../config/sharp_weights.json');
const NOW=Date.parse('2026-10-13T18:00:00Z'),iso=ms=>new Date(ms).toISOString().replace('.000Z','Z');
const quote=(source,aOdds,bOdds,over={})=>({source,title:source,aOdds,bOdds,aDec:S.americanToDecimal(aOdds),bDec:S.americanToDecimal(bOdds),line:null,ageSec:60,...over});

test('normal CDF and inverse match reference values and round-trip',()=>{
 assert.ok(Math.abs(S.normalCdf(1.96)-0.9750021048517795)<1e-12);
 assert.ok(Math.abs(S.normalInv(0.975)-1.959963984540054)<1e-8);
 for(const p of [1e-6,.01,.1234,.5,.9,.999])assert.ok(Math.abs(S.normalCdf(S.normalInv(p))-p)<1e-10,String(p));
});
test('vig removal sums to one, is symmetric at even prices and orders methods sensibly',()=>{
 for(const m of ['proportional','power','probit']){
  const d=S.devigPair(1.5,2.8,m);assert.ok(Math.abs(d.pA+d.pB-1)<1e-12);
  assert.ok(Math.abs(S.devigPair(1.909091,1.909091,m).pA-.5)<1e-9);
 }
 const prop=S.devigPair(1.5,2.8,'proportional').pA,pow=S.devigPair(1.5,2.8,'power').pA,pro=S.devigPair(1.5,2.8,'probit').pA;
 assert.ok(Math.abs(prop-.6511628)<1e-6);
 assert.ok(prop<pro&&pro<pow,'favourite keeps more probability under power than proportional');
 assert.equal(S.devigPair(1,2),null);assert.equal(S.devigPair(NaN,2),null);assert.equal(S.devigPair(1.9,1.9,'x'),null);
});
test('exchange fee shortens the winning payout only when configured',()=>{
 assert.equal(S.afterFee(2,0),2);assert.ok(Math.abs(S.afterFee(2,.02)-1.98)<1e-12);
});
test('source names normalize through aliases',()=>{
 const n=S.makeNormalizer(W.aliases);
 assert.equal(n('Hard Rock Bet'),'hardrock');assert.equal(n('hardrock'),'hardrock');assert.equal(n('BetMGM'),'betmgm');assert.equal(n('DK Predictions'),'dkpredictions');
});
test('weights follow the specification and unspecified sources are disabled',()=>{
 assert.equal(W.game_lines.novig,7.5);assert.equal(W.game_lines.betmgm,.1);assert.equal(W.game_lines.fanatics,.1);assert.equal(W.game_lines.caesars,.3);
 assert.equal(W.player_props.novig,7);assert.equal(W.player_props.kalshi,7);assert.equal(W.player_props.hardrock,.1);
 assert.equal(W.game_lines.bet365,undefined);assert.equal(W.default_enabled,false);assert.match(W.status,/UNVALIDATED/);
});

const event=(books,over={})=>({id:'e1',home_team:'Home',away_team:'Away',commence_time:iso(NOW+3600e3),bookmakers:books,...over});
const book=(key,markets,last=iso(NOW-60e3))=>({key,title:key,last_update:last,markets});
const h2h=(h,a,last)=>({key:'h2h',last_update:last,outcomes:[{name:'Home',price:h},{name:'Away',price:a}]});
const spr=(pt,hp,ap,last,apt=-pt)=>({key:'spreads',last_update:last,outcomes:[{name:'Home',price:hp,point:pt},{name:'Away',price:ap,point:apt}]});
test('board drops started games, missing/future timestamps and mismatched points instead of repairing them',()=>{
 const t=iso(NOW-30e3);
 const ev=event([book('a',[h2h(-150,130,t),spr(-3.5,-110,-110,t)]),book('b',[{...h2h(-150,130),last_update:undefined}],null),book('c',[h2h(-150,130,iso(NOW+10*60e3))]),book('d',[spr(-3.5,-110,-110,t,2.5)]),book('e',[h2h(-150,130,t)])]);
 const {board,drop}=S.boardFromRaw([ev,event([],{id:'old',commence_time:iso(NOW-1)})],{now:NOW});
 assert.equal(drop.started,1);assert.equal(drop.noTimestamp,1);assert.equal(drop.futureTimestamp,1);assert.equal(drop.mismatchedPoints,1);
 assert.equal(board.length,1);assert.equal(board[0].markets.moneyline.length,2);assert.equal(board[0].markets.spread[0].line,-3.5);
});
test('different lines are different contracts and are never combined',()=>{
 const q=[quote('a',-110,-110,{line:-3}),quote('b',-110,-110,{line:-3}),quote('c',-110,-110,{line:-3.5})];
 const m=S.mainLine(q);assert.equal(m.line,-3);assert.equal(m.quotes.length,2);
});
test('equal and research consensus renormalize over available sources and ignore unweighted ones',()=>{
 const q=[quote('novig',-120,110),quote('fanduel',-130,110),quote('pinnacle',-125,105),quote('bet365',-160,140)];
 const eq=S.consensus(q,{mode:'equal',minSources:3}),rs=S.consensus(q,{mode:'research',weights:W.game_lines,minSources:3});
 assert.equal(eq.n,4);assert.equal(rs.n,3);assert.ok(rs.dropped.some(d=>d.source==='bet365'&&d.why==='unweighted'));
 assert.ok(Math.abs(rs.used.reduce((s,u)=>s+u.share,0)-1)<1e-12);
 const nov=rs.used.find(u=>u.source==='novig');assert.ok(Math.abs(nov.share-7.5/9.6)<1e-12);
 assert.ok(eq.pA<rs.pA||eq.pA>rs.pA);
 const missing=S.consensus(q.filter(x=>x.source!=='novig'),{mode:'research',weights:W.game_lines,minSources:2});assert.equal(missing.n,2);
});
test('leave-one-out, copy clusters, staleness and minimum sources',()=>{
 const q=[quote('a',-110,-110),quote('b',-120,100),quote('c',-125,105),quote('d',-125,105,{ageSec:7200})];
 assert.equal(S.consensus(q,{minSources:3,excludeSources:['a'],maxAgeSec:3600}).ok,false);
 assert.equal(S.consensus(q,{minSources:3,excludeSources:['a']}).ok,true);
 const c=S.consensus(q,{minSources:2,excludeSources:['a'],maxAgeSec:3600});assert.equal(c.n,2);assert.ok(c.dropped.some(d=>d.why==='stale'));
 const dup=[quote('x',-130,110),quote('y',-130,110),quote('z',-110,-110)];
 const one=S.consensus(dup,{minSources:2,clusters:[['x','y']]}),two=S.consensus(dup,{minSources:2});
 assert.ok(Math.abs(one.used.find(u=>u.source==='x').w-.5)<1e-12);assert.ok(one.pA<two.pA,'copied price counts once');
 const crossed=S.consensus([quote('a',150,150),quote('b',-110,-110),quote('c',-110,-110),quote('d',-110,-110)],{minSources:3});assert.ok(crossed.dropped.some(d=>d.why==='crossed'));
});
test('copy detection links books with identical non-standard prices and ignores standard -110 pairs',()=>{
 const board=[];
 for(let i=0;i<20;i++)board.push({markets:{moneyline:[quote('p',-130-i,110+i),quote('q',-130-i,110+i),quote('r',-128-i,108+i)],spread:[quote('p',-110,-110,{line:-3}),quote('r',-110,-110,{line:-3})],total:[]}});
 const c=S.detectCopies(board);assert.deepEqual(c.clusters,[['p','q']]);
 assert.deepEqual(S.detectCopies(board.map(b=>({markets:{moneyline:[],spread:b.markets.spread,total:[]}}))).clusters,[]);
});
test('real feed snapshot: every combined quote shares the exact line and consensus is a probability',()=>{
 const raw=require('../data/nfl_betting.json'),now=Date.parse(raw.generated_at),n=S.makeNormalizer(W.aliases);
 const {board}=S.boardFromRaw(raw.games_raw,{now,normalize:n});assert.ok(board.length>0);
 for(const ev of board)for(const m of ['spread','total']){const main=S.mainLine(ev.markets[m]);if(!main)continue;assert.ok(main.quotes.every(q=>q.line===main.line));
  const c=S.consensus(main.quotes,{minSources:3,devig:'probit'});if(c.ok)assert.ok(c.pA>0&&c.pA<1&&c.sd>=0);}
});
