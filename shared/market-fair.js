/* Market-derived fair probability and expected return for NFL game-line rows (Best Plays presentation layer).
 * GOING's spread/total model is market-anchored (shared/game-market.js): at the posted line its probability is the line itself, so
 * "model probability x price - 1" is just price versus that anchor and carries NO independent model edge. This module re-expresses such rows
 * with the leave-one-out consensus of the OTHER books for the identical contract (shared/sharp-consensus.js) and labels where each number
 * comes from. It never changes the generator or any frozen record; callers use it for display and qualification only. */
(function(root){
'use strict';
const SC=root.GoingSharpConsensus||(typeof require!=='undefined'?require('./sharp-consensus.js'):null);
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const EXCHANGES=new Set(['novig','kalshi','polymarket','prophetx','dkpredictions','tailgate']);
// Product constraints, not fitted values (same as Missions): independent sources, agreement, freshness.
const POLICY={minSources:4,maxDispersion:.015,rowMaxAgeSec:900,consensusMaxAgeSec:3600,devig:'probit',edgeHurdle:.01};
const SIDE_A={Home:true,Over:true},SIDE_B={Away:true,Under:true};

function evFor(win,dec,push){
 if(!finite(win)||!finite(dec)||dec<=1||!finite(push)||win<0||push<0||win+push>1+1e-9)return null;
 return win*(dec-1)-(1-win-push);
}
const decimal=o=>finite(o)&&Math.abs(o)>=100?(o>0?1+o/100:1+100/-o):null;

/* games: one row per book per event (index.html BET.games): {id,source,book,bookKey,home,away,kickoff,updatedAt,marketTimes,
 * mlHome,mlAway,spread,homeSpreadOdds,awaySpreadOdds,total,overOdds,underOdds}. eventKey(g) must return the same identity the
 * Best Plays rows carry in `row.event`. Quotes need BOTH sides, a valid aware timestamp that is not in the future, and a game not yet started. */
function build(games,{now=Date.now(),eventKey,aliases={},policy={}}={}){
 const P={...POLICY,...policy},normalize=SC.makeNormalizer(aliases),events=new Map(),skipped={noTime:0,oneSided:0};
 for(const g of Array.isArray(games)?games:[]){
  if(!g||g.source==='manual')continue;
  const kick=Date.parse(g.kickoff);if(!(kick>now))continue;
  const key=eventKey?eventKey(g):null;if(!key)continue;
  const source=normalize(g.bookKey||g.book),ev=events.get(key)||{key,markets:{moneyline:[],spread:[],total:[]}};
  const add=(market,a,b,line,stamp)=>{
   const da=decimal(a),db=decimal(b),ts=Date.parse(stamp);
   if(!da||!db){skipped.oneSided++;return;}
   if(!Number.isFinite(ts)||ts>now+60000){skipped.noTime++;return;}
   ev.markets[market].push({source,title:g.book,aOdds:a,bOdds:b,aDec:da,bDec:db,line,ts,ageSec:Math.max(0,(now-ts)/1000)});
  };
  add('moneyline',g.mlHome,g.mlAway,null,g.marketTimes?.h2h||g.updatedAt);
  if(finite(g.spread))add('spread',g.homeSpreadOdds,g.awaySpreadOdds,g.spread,g.marketTimes?.spreads||g.updatedAt);
  if(finite(g.total))add('total',g.overOdds,g.underOdds,g.total,g.marketTimes?.totals||g.updatedAt);
  events.set(key,ev);
 }
 const board=[...events.values()];
 return {events,clusters:SC.detectCopies(board).clusters,normalize,now,policy:P,skipped};
}

function fairFor(index,row){
 const P=index.policy,ev=index.events.get(row.event);
 if(!ev)return {ok:false,reason:'No matching event in the current odds feed.'};
 const market=row.market==='total'?'total':row.market==='spread'?'spread':row.market==='moneyline'?'moneyline':null;
 if(!market)return {ok:false,reason:'Unsupported market.'};
 const line=market==='moneyline'?null:Number(row.line);
 const quotes=ev.markets[market].filter(q=>q.line===line);
 if(!quotes.length)return {ok:false,reason:'No other book quotes this exact line.'};
 const mine=index.normalize(row.bookKey||row.book),mates=index.clusters.find(c=>c.includes(mine))||[mine];
 const c=SC.consensus(quotes,{mode:'equal',minSources:P.minSources,devig:P.devig,excludeSources:mates,clusters:index.clusters,maxAgeSec:P.consensusMaxAgeSec});
 if(!c.ok)return {ok:false,reason:c.reason||'Too few independent sources.',source:mine};
 if(c.sd>P.maxDispersion)return {ok:false,reason:`Books disagree (dispersion ${(c.sd*100).toFixed(1)} pp).`,source:mine,sources:c.n};
 const a=Object.hasOwn(SIDE_A,row.side)?true:Object.hasOwn(SIDE_B,row.side)?false:null;
 if(a===null)return {ok:false,reason:'Unrecognised side.'};
 return {ok:true,p:a?c.pA:c.pB,sources:c.n,dispersion:c.sd,range:a?c.range:[1-c.range[1],1-c.range[0]],source:mine,exchange:EXCHANGES.has(mine),newestAgeSec:c.newestAgeSec};
}

/* Returns a COPY of the row. Non-game rows are returned unchanged. Original fields survive as modelProb/modelEv/modelFlags.
 * Never invents a probability: with neither a consensus nor the book's own two-way price the row is dropped (returns null). */
function annotate(row,index){
 if(!row||row.kind!=='game')return row;
 const P=index.policy,fair=fairFor(index,row),dec=row.dec,push=finite(row.push)?row.push:0;
 const own=row.reference&&finite(row.reference.win)?row.reference:null;
 const rowAge=(index.now-Date.parse(row.updatedAt))/1000,stale=!(rowAge>=0)||rowAge>P.rowMaxAgeSec;
 const out={...row,modelProb:row.prob,modelEv:row.ev,independentModel:false,marketFair:fair};
 let win=null,source=null;
 if(fair.ok){win=fair.p*(1-push);source='market_consensus';}
 else if(own){win=own.win;source='book_implied';}
 const ev=win==null?null:evFor(win,dec,push);
 if(ev==null)return null;
 out.prob=win;out.ev=ev;out.probSource=source;out.evSource=source;
 const flags=(row.flags||[]).filter(f=>f.id!=='gap');   // the model-gap claim presumes an independent model
 out.modelFlags=(row.flags||[]).filter(f=>f.id==='gap');
 const why=[];
 if(source==='market_consensus'){
  const verified=!fair.exchange&&!stale;
  out.edgeSupported=verified&&ev>=P.edgeHurdle;
  why.push(`Fair probability ${(100*fair.p).toFixed(1)}% from ${fair.sources} other books quoting this exact line (probit vig removal, dispersion ${(100*fair.dispersion).toFixed(1)} pp). GOING's own model is anchored to the line and adds no independent probability.`);
  if(fair.exchange)why.push('Exchange price: fee, spread and size are not in the feed, so it is not treated as executable.');
  if(stale)why.push(`This quote is more than ${P.rowMaxAgeSec/60} minutes old; confirm the live price.`);
 }else{
  out.edgeSupported=false;
  why.push(`Fewer than ${P.minSources} independent books agree on this contract (${fair.reason||'no consensus'}), so the only available estimate is this book's own de-vigged price. Expected return here shows the cost of the vig, not an edge.`);
 }
 flags.push({id:'basis',family:'market',why:why.join(' ')});
 out.flags=flags;
 return out;
}

const api={POLICY,EXCHANGES,build,fairFor,annotate,evFor};
root.GoingMarketFair=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
