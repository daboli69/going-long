/* GOING Missions: turns the sharp-consensus service and the existing GOING model rows into a small set of qualified
 * opportunities, cross-game parlays priced at posted leg odds, and simulated mission strategies.
 * It never creates probabilities of its own: the probability behind every opportunity is the leave-one-out market
 * consensus; the GOING model is shown as a cross-check and can only veto. The production model is untouched. */
(function(root){
'use strict';
const SC=root.GoingSharpConsensus||(typeof require!=='undefined'?require('./sharp-consensus.js'):null);
const SIM=root.GoingMissionSim||(typeof require!=='undefined'?require('./mission-sim.js'):null);
const finite=x=>typeof x==='number'&&Number.isFinite(x);

const TEAM_CODES={'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Las Vegas Raiders':'LV','Los Angeles Chargers':'LAC','Los Angeles Rams':'LA','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','San Francisco 49ers':'SF','Seattle Seahawks':'SEA','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS'};
// Venues that are exchanges or prediction markets: the feed carries no fee, spread, depth or size, so these prices are
// used as information but are never certified as executable offers.
const EXCHANGES=new Set(['novig','kalshi','polymarket','prophetx','dkpredictions','tailgate']);

// Policy parameters. They are product constraints, not fitted values, and are echoed in every result.
const POLICY={minEv:.01,minSources:4,maxDispersion:.015,offerMaxAgeSec:900,consensusMaxAgeSec:3600,tieRate:.004,
 devig:'probit',maxLegs:3,minLegAmerican:-500,maxStraights:3,maxParlays:2,candidateLegs:12};

const sideLabel=(row,market,side,line)=>market==='moneyline'?`${side==='A'?row.home:row.away} ML`:market==='spread'?`${side==='A'?row.home:row.away} ${fmtLine(side==='A'?line:-line)}`:`${side==='A'?'Over':'Under'} ${line}`;
const fmtLine=l=>l>0?'+'+l:String(l);
const american=o=>o>0?'+'+o:String(o);

// ---- GOING model cross-check ------------------------------------------------------------------------------------
function modelIndex(snapshot,{oddsGeneratedAt,maxLagMs=6*3600000,normalize=SC.compact}={}){
 const rows=Array.isArray(snapshot?.rows)?snapshot.rows:[],idx=new Map();
 const lag=Date.parse(oddsGeneratedAt)-Date.parse(snapshot?.odds_generated_at);
 const stale=!Number.isFinite(lag)||Math.abs(lag)>maxLagMs;
 if(stale)return {idx,stale:true,reason:snapshot?`Model snapshot (built from odds ${snapshot.odds_generated_at}) is not within ${maxLagMs/3600000}h of the odds snapshot; model cross-check disabled.`:'No model snapshot supplied.',count:0};
 for(const r of rows)idx.set([normalize(r.book),r.kickoff,r.home,r.market,String(r.side).toLowerCase(),r.line].join('|'),r);
 return {idx,stale:false,reason:null,count:idx.size};
}
function modelFor(index,row,source,market,side,line){
 const home=TEAM_CODES[row.home],kick=row.kickoff;if(!home||index.stale)return null;
 const name=market==='total'?(side==='A'?'over':'under'):(side==='A'?'home':'away');
 // Model rows carry the line from the selection's own perspective.
 const l=market==='moneyline'?0:market==='total'?line:(side==='A'?line:-line);
 return index.idx.get([source,kick,home,market,name,l].join('|'))||null;
}

// ---- offers ----------------------------------------------------------------------------------------------------
function buildOffers(raw,{now=Date.now(),weights={},aliases={},model=null,oddsGeneratedAt=null,flags={},policy={}}={}){
 const P={...POLICY,...policy},normalize=SC.makeNormalizer(aliases),{board,drop}=SC.boardFromRaw(raw,{now,normalize});
 const copies=SC.detectCopies(board),mi=modelIndex(model,{oddsGeneratedAt,normalize}),mode=flags.researchWeights?'research':'equal';
 const fees=Object.fromEntries(Object.entries(flags.exchangeFees||{}).map(([k,v])=>[k,v]));
 const offers=[],reject={};const bump=k=>{reject[k]=(reject[k]||0)+1;};
 for(const ev of board)for(const market of ['moneyline','spread','total']){
  const main=SC.mainLine(ev.markets[market]);if(!main)continue;
  for(const q of main.quotes){
   if(q.ageSec>P.offerMaxAgeSec){bump('offer older than '+P.offerMaxAgeSec/60+' min');continue;}
   const mates=copies.clusters.find(c=>c.includes(q.source))||[q.source];
   const common={excludeSources:mates,clusters:copies.clusters,minSources:P.minSources,devig:P.devig,feeRates:fees,maxAgeSec:P.consensusMaxAgeSec};
   const eq=SC.consensus(main.quotes,{...common,mode:'equal'}),rs=flags.researchWeights?SC.consensus(main.quotes,{...common,mode:'research',weights}):null;
   const used=mode==='research'?rs:eq;
   if(!used?.ok){bump('fewer than '+P.minSources+' independent sources');continue;}
   for(const side of ['A','B']){
    const dec=side==='A'?q.aDec:q.bDec,odds=side==='A'?q.aOdds:q.bOdds,p=side==='A'?used.pA:used.pB;
    const integerLine=market!=='moneyline'&&Number.isInteger(main.line);
    const push=market==='moneyline'?P.tieRate:integerLine?null:0;
    const base={id:[ev.eventId,market,main.line,side,q.source].join('|'),eventId:ev.eventId,home:ev.home,away:ev.away,kickoff:ev.kickoff,
     market,side,line:main.line,selection:sideLabel(ev,market,side,main.line),book:q.title,source:q.source,odds,american:american(odds),dec,ageSec:q.ageSec,exchange:EXCHANGES.has(q.source)};
    if(push==null){offers.push({...base,qualified:false,reasons:['Integer line: push probability is not estimated for this contract.']});continue;}
    const win=p*(1-push),loss=(1-p)*(1-push),evv=win*(dec-1)-loss;
    const eqP=side==='A'?eq.pA:eq.pB,rsP=rs?(side==='A'?rs.pA:rs.pB):null;
    const m=modelFor(mi,ev,q.source,market,side,main.line);
    const anchored=m&&market!=='moneyline'&&Math.abs(m.prob-.5)<.002;
    const breakeven=1/dec;
    const reasons=[],warn=[];
    if(base.exchange)reasons.push('Exchange/prediction-market price: fee, spread and size are not in the feed, so executability is unverified.');
    if(odds<P.minLegAmerican)reasons.push(`Price shorter than ${P.minLegAmerican}.`);
    if(evv<P.minEv)reasons.push(`Estimated return ${(evv*100).toFixed(1)}% is below the ${(P.minEv*100).toFixed(1)}% hurdle.`);
    if(used.sd>P.maxDispersion)reasons.push(`Sources disagree (dispersion ${(used.sd*100).toFixed(1)} pp).`);
    if(m&&!anchored&&m.prob<breakeven-.02)reasons.push('GOING model probability is more than 2 pp below the break-even for this price.');
    if(anchored)warn.push('GOING model probability equals the posted line by construction (market-anchored), so it adds no independent confirmation.');
    offers.push({...base,qualified:reasons.length===0,reasons,warnings:warn,
     p,pEqual:eqP,pResearch:rsP,push,win,loss,ev:evv,edgePts:p-breakeven,breakeven,
     consensus:{mode:used.mode,devig:P.devig,sources:used.n,dispersion:used.sd,range:used.range,effectiveSources:used.effectiveSources,topShare:used.topShare,newestAgeSec:used.newestAgeSec,oldestAgeSec:used.oldestAgeSec,
      used:used.used.map(u=>({source:u.title,p:side==='A'?u.p:1-u.p,share:u.share})),copyClusters:copies.clusters},
     model:m?{prob:m.prob,ev:m.ev,n:m.n,anchoredToLine:Boolean(anchored)}:null,
     clv:null,clvNote:'No closing-price history is stored yet; CLV is not reported.'});
   }
  }
 }
 return {offers,diagnostics:{events:board.length,drop,reject,copyClusters:copies.clusters,copyPairs:copies.pairs,mode,modelNote:mi.reason,modelRows:mi.count,policy:P}};
}

// ---- same-game relations (evidence only: no joint probability is invented) -----------------------------------------
function classifyPair(a,b){
 if(a.eventId!==b.eventId)return {relation:'independent-assumed',note:'Different games: independence is assumed, not measured.'};
 if(a.market===b.market&&a.side!==b.side)return {relation:'contradictory',note:'Opposite sides of one market cannot both be backed.'};
 if(a.market==='moneyline'&&b.market==='spread'||a.market==='spread'&&b.market==='moneyline'){
  const same=(a.side===b.side);return same?{relation:'redundant-dependent',note:'Moneyline and spread on the same team are strongly dependent; books price this correlation.'}:{relation:'contradictory',note:'Moneyline and spread favour opposite teams.'};
 }
 return {relation:'dependent-unestimated',note:'Same-game legs are dependent; no validated correlation estimate exists, and the feed carries no same-game parlay price.'};
}

// ---- parlays ---------------------------------------------------------------------------------------------------
function buildParlays(offers,{maxLegs=POLICY.maxLegs,minEv=POLICY.minEv,candidateLegs=POLICY.candidateLegs}={}){
 const pool=offers.filter(o=>o.qualified).sort((a,b)=>b.ev-a.ev).slice(0,candidateLegs),out=[],rejected={sameGame:0,mixedBooks:0};
 const byBook=new Map();for(const o of pool)byBook.set(o.source,[...(byBook.get(o.source)||[]),o]);
 const pairs=[];for(let i=0;i<pool.length;i++)for(let j=i+1;j<pool.length;j++){if(pool[i].eventId===pool[j].eventId)rejected.sameGame++;else if(pool[i].source!==pool[j].source)rejected.mixedBooks++;}
 for(const list of byBook.values()){
  const n=list.length;
  const rec=(start,chosen)=>{
   if(chosen.length>=2){
    const events=new Set(chosen.map(l=>l.eventId));
    if(events.size===chosen.length){
     const mult=chosen.reduce((m,l)=>m*(l.win*l.dec+l.push),1),dec=chosen.reduce((m,l)=>m*l.dec,1);
     const pAll=chosen.reduce((m,l)=>m*l.p,1);
     const evv=mult-1;
     if(evv>=minEv)out.push({id:chosen.map(l=>l.id).join(' + '),legs:chosen,book:chosen[0].book,source:chosen[0].source,dec,american:american(SC.decimalToAmerican(dec)),
      pAllWin:pAll,ev:evv,jointMethod:'product of leg consensus probabilities (different games; independence assumed)',priceMethod:'product of posted leg prices at one book; the live ticket price must be confirmed in the book',priceVerified:false});
    }
   }
   if(chosen.length===maxLegs)return;
   for(let i=start;i<n;i++)rec(i+1,[...chosen,list[i]]);
  };
  rec(0,[]);
 }
 return {parlays:out.sort((a,b)=>b.ev-a.ev),rejected};
}

// ---- objectives -----------------------------------------------------------------------------------------------------
const probLow=(o,margin)=>Math.max(.001,o.p-margin-(o.consensus?.dispersion||0));
function kellyGrowth(p,dec,cap=.25){ // fractional (quarter) Kelly growth rate on a lower-bound probability
 const f=Math.min(cap,Math.max(0,(p*dec-1)/(dec-1))*.25);
 return f>0?p*Math.log(1+f*(dec-1))+(1-p)*Math.log(1-f):0;
}
function scoreFor(objective,item,cfg,margin=.01){
 const isParlay=Array.isArray(item.legs),p=isParlay?item.pAllWin:item.p,dec=item.dec;
 const low=isParlay?item.legs.reduce((m,l)=>m*probLow(l,margin),1):probLow(item,margin);
 if(objective==='survival')return low*(item.ev>0?1:0)+item.ev*.1;
 if(objective==='growth')return kellyGrowth(low,dec);
 const stake=cfg.bankroll*cfg.exposure,needed=(cfg.target-(cfg.bankroll-stake))/stake;
 if(objective==='parlay')return (dec>=needed?p:p*dec/needed*.5)*(item.ev>0?1:0)+item.ev*.1;
 // cash-out: progress per stake toward the withdrawal target, penalized by variance of the single ticket
 const gain=Math.min(cfg.withdrawTarget,stake*(dec-1));return (gain/Math.max(1,cfg.withdrawTarget))*low;
}

// ---- strategies -----------------------------------------------------------------------------------------------------
function chooseStraights(straights,objective,cfg){
 const taken=new Set(),chosen=[];
 for(const o of [...straights].sort((a,b)=>scoreFor(objective,b,cfg)-scoreFor(objective,a,cfg))){
  if(taken.has(o.eventId))continue;taken.add(o.eventId);chosen.push(o);if(chosen.length>=POLICY.maxStraights)break;
 }
 return chosen;
}
function chooseParlays(parlays,objective,cfg){
 const used=new Set(),chosen=[];
 for(const p of [...parlays].sort((a,b)=>scoreFor(objective,b,cfg)-scoreFor(objective,a,cfg))){
  if(p.legs.some(l=>used.has(l.eventId)))continue;p.legs.forEach(l=>used.add(l.eventId));chosen.push(p);if(chosen.length>=POLICY.maxParlays)break;
 }
 return chosen;
}
const straightTicket=o=>({id:o.id,legIds:[o.id],decs:[o.dec],weight:1,kind:'straight',offer:o});
const parlayTicket=p=>({id:p.id,legIds:p.legs.map(l=>l.id),decs:p.legs.map(l=>l.dec),weight:1,kind:'parlay',parlay:p});

function planStrategies({offers,parlays,objective,cfg,betTypes}){
 const q=offers.filter(o=>o.qualified),canStraight=betTypes!=='parlays',canParlay=betTypes!=='straights';
 const straights=canStraight?chooseStraights(q,objective,cfg):[],parl=canParlay?chooseParlays(parlays,objective,cfg):[];
 const out=[{id:'none',name:'No bet (baseline)',tickets:[],qualified:true}];
 if(straights.length)out.push({id:'straights',name:'Straight bets',tickets:straights.map(straightTicket),qualified:true});
 if(parl.length)out.push({id:'parlays',name:'Parlays',tickets:parl.map(parlayTicket),qualified:true});
 if(straights.length&&parl.length)out.push({id:'mixed',name:'Mixed (straights + parlay)',tickets:[...straights.slice(0,2).map(t=>({...straightTicket(t),weight:.5/Math.min(2,straights.length)})),...parl.slice(0,1).map(p=>({...parlayTicket(p),weight:.5}))],qualified:true});
 return out;
}
/* When nothing qualifies, a transparent REFERENCE is simulated so the user can see what chasing the target would cost:
 * the least-negative-return executable sportsbook prices, one per game. It is labelled negative-EV and never recommended. */
function referenceStrategies({offers,cfg,betTypes}){
 const exec=offers.filter(o=>!o.exchange&&finite(o.ev)&&o.odds>=POLICY.minLegAmerican).sort((a,b)=>b.ev-a.ev),seen=new Set(),legs=[];
 for(const o of exec){if(seen.has(o.eventId))continue;seen.add(o.eventId);legs.push(o);if(legs.length>=3)break;}
 const out=[];
 if(legs.length&&betTypes!=='parlays')out.push({id:'ref-straights',name:'Reference: best-priced straights',tickets:legs.map(straightTicket),qualified:false});
 const sameBook=legs.length>=2?legs.filter(l=>l.source===legs[0].source):[];
 if(betTypes!=='straights'){
  const book=new Map();for(const o of exec){if(!book.has(o.source))book.set(o.source,[]);const l=book.get(o.source);if(!l.some(x=>x.eventId===o.eventId)&&l.length<3)l.push(o);}
  const best=[...book.values()].filter(l=>l.length>=2).sort((a,b)=>b.reduce((m,l)=>m*(l.win*l.dec+l.push),1)-a.reduce((m,l)=>m*(l.win*l.dec+l.push),1))[0];
  if(best){const dec=best.reduce((m,l)=>m*l.dec,1);const p={id:best.map(l=>l.id).join(' + '),legs:best,book:best[0].book,source:best[0].source,dec,american:american(SC.decimalToAmerican(dec)),pAllWin:best.reduce((m,l)=>m*l.p,1),ev:best.reduce((m,l)=>m*(l.win*l.dec+l.push),1)-1,priceVerified:false,jointMethod:'product of leg consensus probabilities (different games; independence assumed)'};out.push({id:'ref-parlay',name:'Reference: best-priced parlay',tickets:[parlayTicket(p)],qualified:false});}
 }
 void sameBook;
 return out;
}

// ---- mission orchestration ------------------------------------------------------------------------------------------
const OBJECTIVES={survival:'Survival',growth:'Growth',parlay:'Parlay','cash-out':'Cash-Out'};
function runMission(raw,input={}){
 const objective=OBJECTIVES[input.objective]?input.objective:'cash-out';
 const cfg={bankroll:50,target:150,withdrawTarget:100,reserve:50,weeks:1,maxExposure:.5,acceptableDownside:.6,books:[],betTypes:'both',runs:20000,seed:20261014,probShift:0,...input.mission};
 const exposure=Math.min(cfg.maxExposure,cfg.acceptableDownside);
 const built=buildOffers(raw,{now:input.now??Date.now(),weights:input.weights,aliases:input.aliases,model:input.model,oddsGeneratedAt:input.oddsGeneratedAt,flags:input.flags||{},policy:input.policy});
 let offers=built.offers;
 if(cfg.books.length)offers=offers.map(o=>cfg.books.includes(o.source)?o:o.qualified?{...o,qualified:false,reasons:['Not at a preferred sportsbook.']}:o);
 const {parlays,rejected}=buildParlays(offers,{minEv:(input.policy?.minEv)??POLICY.minEv});
 const sc={...cfg,exposure};
 let strategies=planStrategies({offers,parlays,objective,cfg:sc,betTypes:cfg.betTypes});
 const hasQualified=strategies.some(s=>s.tickets.length>0);
 if(!hasQualified)strategies=[...strategies,...referenceStrategies({offers,cfg:sc,betTypes:cfg.betTypes})];
 const legMap=new Map();
 for(const s of strategies)for(const t of s.tickets)for(const l of (t.kind==='parlay'?t.parlay.legs:[t.offer]))legMap.set(l.id,{id:l.id,eventId:l.eventId,p:l.p,push:l.push,loading:0,dec:l.dec});
 const simConfig={bankroll:cfg.bankroll,target:cfg.target,withdrawTarget:cfg.withdrawTarget,reserve:cfg.reserve,weeks:cfg.weeks,maxExposure:exposure,runs:cfg.runs,seed:cfg.seed,probShift:cfg.probShift,acceptableDownside:cfg.acceptableDownside,sigmaLeg:input.sigmaLeg,sigmaSystematic:input.sigmaSystematic};
 for(const k of Object.keys(simConfig))if(simConfig[k]===undefined)delete simConfig[k];
 const results=SIM.simulate({pool:[...legMap.values()],strategies:strategies.map(s=>({id:s.id,name:s.name,tickets:s.tickets.map(t=>({id:t.id,legIds:t.legIds,decs:t.decs,weight:t.weight}))})),config:simConfig});
 const budget=cfg.bankroll*exposure;
 const strategiesOut=strategies.map((s,i)=>{
  const wsum=s.tickets.reduce((a,t)=>a+t.weight,0);
  const tickets=s.tickets.map(t=>{const stake=Math.round(budget*t.weight/wsum*100)/100;const lg=t.kind==='parlay'?t.parlay.legs:[t.offer];const dec=t.kind==='parlay'?t.parlay.dec:t.offer.dec,evv=t.kind==='parlay'?t.parlay.ev:t.offer.ev,pw=t.kind==='parlay'?t.parlay.pAllWin:t.offer.win;
   return {id:t.id,kind:t.kind,stake,toWin:Math.round(stake*(dec-1)*100)/100,dec,american:american(SC.decimalToAmerican(dec)),ev:evv,expectedProfit:Math.round(stake*evv*100)/100,pWin:pw,targetContribution:Math.min(1,stake*(dec-1)/Math.max(1,cfg.target-cfg.bankroll)),book:lg[0].book,legs:lg};});
  return {id:s.id,name:s.name,qualified:s.qualified,reference:!s.qualified&&s.id!=='none',negativeEv:tickets.some(t=>t.ev<0),tickets,result:results[i]};
 });
 return {objective,objectiveLabel:OBJECTIVES[objective],mission:{...cfg,exposure},qualified:offers.filter(o=>o.qualified).sort((a,b)=>scoreFor(objective,b,sc)-scoreFor(objective,a,sc)),parlays:chooseParlays(parlays,objective,sc),
  strategies:strategiesOut,diagnostics:{...built.diagnostics,offerCount:offers.length,qualifiedCount:offers.filter(o=>o.qualified).length,parlayCandidates:parlays.length,parlayRejected:rejected,
   assumptions:['Each simulated weekend reuses this slate as its opportunity template; future edges are not forecast.','Cross-game parlays assume independence; same-game parlays are rejected because no executable same-game price exists in the feed.','Parlay ticket price is the product of posted leg prices and must be confirmed in the book.',`Probability uncertainty: logit sd ${simConfig.sigmaLeg??SIM.DEFAULTS.sigmaLeg} per leg-weekend plus ${simConfig.sigmaSystematic??SIM.DEFAULTS.sigmaSystematic} systematic.`,'Market consensus is not proof of profitability; no validated edge is claimed.']}};
}

const api={runMission,buildOffers,buildParlays,classifyPair,modelIndex,planStrategies,referenceStrategies,scoreFor,TEAM_CODES,EXCHANGES,POLICY,OBJECTIVES};
root.GoingMissions=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
