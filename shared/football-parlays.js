(function(root){
'use strict';
function profitBoost(probability,decimal,boostPercent=0,stake=10){
 if(!(probability>0&&probability<1)||!(decimal>1)||!Number.isFinite(decimal)||!Number.isFinite(boostPercent)||boostPercent<0||boostPercent>1000||!Number.isFinite(stake)||stake<=0)throw Error('Enter a boost from 0 to 1000% and a positive stake.');
 const boostedDecimal=1+(decimal-1)*(1+boostPercent/100);
 return {boostedDecimal,returnPerDollar:probability*boostedDecimal-1,baseReturn:probability*decimal-1,breakEvenBoost:Math.max(0,100*((1/probability-1)/(decimal-1)-1)),profitIfWin:stake*(boostedDecimal-1),expectedProfit:stake*(probability*boostedDecimal-1)};
}

const contractKey=r=>r.canonicalContract||r.contract||r.key||[r.event,r.kind,r.profileId||'',r.market,r.line??'',r.side].join('|');
const entity=r=>r.kind==='prop'?'player:'+r.profileId:'game:'+(['spread','moneyline'].includes(r.market)?'result':r.market);
const weakestLeg=legs=>legs.reduce((weak,row)=>!weak||row.prob<weak.prob?row:weak,null);

function bestReplacement(ticket,pool,{sameGame,lower=1,upper=Infinity,boostPercent=0,stake=10}){
 if(!ticket?.legs?.length)return null;
 const weak=weakestLeg(ticket.legs),remaining=ticket.legs.filter(row=>row!==weak),usedContracts=new Set(ticket.legs.map(contractKey)),usedEntities=new Set(remaining.map(entity)),usedEvents=new Set(remaining.map(row=>row.event));
 const candidates=pool.filter(row=>!usedContracts.has(contractKey(row))&&(sameGame?row.event===weak.event&&!usedEntities.has(entity(row)):!usedEvents.has(row.event)));
 let best=null;
 for(const row of candidates){
  const legs=[...remaining,row];
  if(sameGame){if(!best||row.prob>best.add.prob)best={remove:weak,add:row,legs,probability:null,decimal:null};continue;}
  const probability=legs.reduce((value,leg)=>value*leg.prob,1),decimal=legs.reduce((value,leg)=>value*leg.dec,1);
  if(decimal<lower||decimal>upper)continue;
  const boost=profitBoost(probability,decimal,boostPercent,stake);if(boost.returnPerDollar<0)continue;
  if(!best||probability>best.probability)best={remove:weak,add:row,legs,probability,decimal,estimatedReturn:probability*decimal-1,boost};
 }
 return best;
}

function select(rows,{sport,now=Date.now(),start,last,legs=2,minOdds=null,maxOdds=null,book:chosenBook="all",kind="all",events=null,boostPercent=0,stake=10}={}){
 const decimal=o=>o==null?null:Number.isFinite(o)&&Math.abs(o)>=100?(o>0?1+o/100:1+100/-o):NaN;
 profitBoost(.5,2,boostPercent,stake);
 const lower=decimal(minOdds)??1,upper=decimal(maxOdds)??Infinity;
 if(!Number.isInteger(legs)||legs<2||legs>6)throw Error('Choose between 2 and 6 legs.');
 if(!Number.isFinite(lower)||Number.isNaN(upper)||upper<lower)throw Error('Enter valid American odds, with the maximum at least the minimum.');
 const day=t=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));
 const books=new Map();
 for(const r of rows){
  const kick=Date.parse(r.kickoff),at=Date.parse(r.updatedAt);
  if((events!==null&&!events.includes(r.event))||(chosenBook!=='all'&&r.book!==chosenBook)||(kind!=='all'&&r.kind!==kind)||r.sport!==sport||!r.event||!r.book||r.manual||r.dfs||r.trust?.review||!Number.isFinite(kick)||kick<=now||day(kick)<start||day(kick)>last||!Number.isFinite(at)||at>now||now-at>86400000||!(r.n>=5)||!(r.prob>0&&r.prob<1)||!(r.dec>1)||!Number.isFinite(r.ev)||(boostPercent===0&&r.ev<0)||r.ev>.25||r.push!==0||r.market==='first_td'||/_1[hq]$/.test(r.market)||r.flags?.some(f=>f.id==='check'&&!f.historicalOnly))continue;
  if(r.kind==='prop'&&!r.profileId)continue;
  if(!books.has(r.book))books.set(r.book,[]);books.get(r.book).push(r);
 }
 let parlay=null,sgp=null;
 for(const [book,pool] of books){
  pool.sort((a,b)=>b.prob-a.prob||b.ev-a.ev);
  const events=new Map();for(const r of pool){if(!events.has(r.event))events.set(r.event,[]);events.get(r.event).push(r);}
  // Bounded search keeps larger weekly slates responsive. It is not an exhaustive optimum.
  let states=[{legs:[],probability:1,decimal:1}];
  for(const group of events.values()){
   const unique=new Map();for(const r of group){const key=[r.kind,r.profileId,r.market,r.line,r.side].join('|');if(!unique.has(key))unique.set(key,r);}
   const choices=[...unique.values()].slice(0,12),next=[...states];
   for(const state of states){if(state.legs.length>=legs)continue;for(const r of choices){
    const value={legs:[...state.legs,r],probability:state.probability*r.prob,decimal:state.decimal*r.dec};
    if(value.decimal<=upper)next.push(value);
   }}
   states=[];
   for(let n=0;n<=legs;n++){
    const candidates=next.filter(x=>x.legs.length===n).sort((a,b)=>b.probability-a.probability);
    // Retain both high-chance and longer-price branches for target-odds searches.
    const kept=candidates.slice(0,100);if(lower>1)kept.push(...candidates.slice(100).sort((a,b)=>b.decimal-a.decimal).slice(0,60));
    states.push(...kept);
   }
  }
  for(const candidate of states.filter(x=>x.legs.length===legs&&x.decimal>=lower&&x.decimal<=upper)){
   const boost=profitBoost(candidate.probability,candidate.decimal,boostPercent,stake);
   if(boost.returnPerDollar<0)continue;
   if(!parlay||candidate.probability>parlay.probability)parlay={book,...candidate,estimatedReturn:candidate.probability*candidate.decimal-1,boost,pool};
  }
  for(const rawGroup of events.values()){
   const group=rawGroup.filter(r=>r.ev>=0);
   const chosen=[],seen=new Set();for(const r of group){if(seen.has(entity(r)))continue;seen.add(entity(r));chosen.push(r);if(chosen.length===legs)break;}
   if(chosen.length!==legs)continue;
   const weakest=Math.min(...chosen.map(r=>r.prob));
   if(!sgp||weakest>sgp.weakest)sgp={book,legs:chosen,weakest,probability:null,decimal:null,pool};
  }
 }
 if(parlay){parlay.weakestLeg=weakestLeg(parlay.legs);parlay.replacement=bestReplacement(parlay,parlay.pool,{sameGame:false,lower,upper,boostPercent,stake});delete parlay.pool;}
 if(sgp){sgp.weakestLeg=weakestLeg(sgp.legs);sgp.replacement=bestReplacement(sgp,sgp.pool,{sameGame:true});delete sgp.pool;}
 return {parlay,sgp};
}
// User edits share the builder's eligibility policy, without changing its search.
// A retained leg must still match an eligible observed quote in the supplied pool.
const quoteKey=r=>JSON.stringify([contractKey(r),r.event,r.book,r.kind,r.profileId||'',r.market,r.line??'',r.side||'',r.kickoff,r.updatedAt,r.prob,r.dec,r.ev,r.n,r.push,r.odds]);
function editContext(rows,options={}){
 const o={now:Date.now(),book:'all',kind:'all',events:null,boostPercent:0,stake:10,sameGame:false,...options};
 const fail=error=>({o,error,pool:[],quotes:new Set()});
 const date=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d+'T12:00:00Z'))&&new Date(d+'T12:00:00Z').toISOString().slice(0,10)===d;
 if(!['nfl','ncaa'].includes(o.sport)||!Number.isFinite(o.now)||!date(o.start)||!date(o.last)||o.start>o.last)return fail('Choose a valid football sport and date range.');
 if(!['all','game','prop'].includes(o.kind)||(o.events!==null&&(!Array.isArray(o.events)||o.events.some(e=>typeof e!=='string'))))return fail('Choose valid leg and game filters.');
 const decimal=v=>v==null?null:Number.isFinite(v)&&Math.abs(v)>=100?(v>0?1+v/100:1+100/-v):NaN;
 const lower=decimal(o.minOdds)??1,upper=decimal(o.maxOdds)??Infinity;
 if(!Number.isFinite(lower)||Number.isNaN(upper)||upper<lower)return fail('Enter valid American odds, with the maximum at least the minimum.');
 try{profitBoost(.5,2,o.boostPercent,o.stake);}catch(e){return fail(e.message);}
 const formatter=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}),day=t=>formatter.format(new Date(t));
 const eligible=r=>{
  if(!r||typeof r!=='object'||typeof r.event!=='string'||!r.event||typeof r.book!=='string'||!r.book||!['game','prop'].includes(r.kind)||typeof r.market!=='string'||!r.market)return false;
  if([r.canonicalContract,r.contract,r.key,r.line,r.side,r.profileId,r.kickoff,r.updatedAt].some(v=>v!=null&&!['string','number'].includes(typeof v))||![r.n,r.prob,r.dec,r.ev,r.odds].every(Number.isFinite))return false;
  const kick=Date.parse(r.kickoff),at=Date.parse(r.updatedAt),priced=decimal(r.odds);
  if((o.events!==null&&!o.events.includes(r.event))||(o.book!=='all'&&r.book!==o.book)||(o.kind!=='all'&&r.kind!==o.kind)||r.sport!==o.sport||(o.sport==='ncaa'&&r.kind==='prop')||r.manual||r.dfs||r.trust?.review||!Number.isFinite(kick)||kick<=o.now||day(kick)<o.start||day(kick)>o.last||!Number.isFinite(at)||at>o.now||o.now-at>86400000||!(r.n>=5)||!(r.prob>0&&r.prob<1)||!(r.dec>1)||!Number.isFinite(r.dec)||!Number.isFinite(priced)||Math.abs(priced-r.dec)>1e-9||!Number.isFinite(r.ev)||((o.boostPercent===0||o.sameGame)&&r.ev<0)||r.ev>.25||r.push!==0||r.market==='first_td'||/_1[hq]$/.test(r.market)||(!Array.isArray(r.flags)&&r.flags!=null)||r.flags?.some(f=>f?.id==='check'&&!f.historicalOnly))return false;
  return !(r.kind==='prop'&&!r.profileId);
 };
 const pool=(Array.isArray(rows)?rows:[]).filter(eligible);
 return {o,lower,upper,pool,eligible,quotes:new Set(pool.map(quoteKey)),error:null};
}
function summarizeEdit(legs,context){
 const list=Array.isArray(legs)?legs:[],{o}=context;
 const ticket={legs:list,book:list[0]?.book||null,valid:true,ready:false,error:null,issues:[],weakestLeg:weakestLeg(list.filter(r=>r&&typeof r==='object'&&Number.isFinite(r.prob))),probability:null,decimal:null,estimatedReturn:null,boost:null};
 const fail=error=>({...ticket,valid:false,ready:false,error,issues:[error],probability:null,decimal:null,estimatedReturn:null,boost:null});
 if(context.error)return fail(context.error);
 if(!Array.isArray(legs)||list.length>6)return fail('Keep the ticket between zero and six legs.');
 const contracts=new Set(),entities=new Set(),events=new Set();
 for(const r of list){
  if(!context.eligible(r)||!context.quotes.has(quoteKey(r)))return fail('A leg no longer has a supported current quote for these filters. Remove it or rebuild the ticket.');
  if(r.book!==ticket.book)return fail('Keep every leg at the same sportsbook.');
  if(contracts.has(contractKey(r)))return fail('This selection is already on the ticket.');
  if(o.sameGame){
   if(r.event!==list[0].event)return fail('Keep every same-game leg in the original game.');
   if(entities.has(entity(r)))return fail('Use one outcome per player or game market in a same-game ticket.');
  }else if(events.has(r.event))return fail('Choose a different game for each leg.');
  contracts.add(contractKey(r));entities.add(entity(r));events.add(r.event);
 }
 if(list.length<2){ticket.issues.push('Add at least two legs to complete a ticket.');return ticket;}
 if(o.sameGame){ticket.weakest=Math.min(...list.map(r=>r.prob));ticket.ready=true;return ticket;}
 ticket.probability=list.reduce((v,r)=>v*r.prob,1);ticket.decimal=list.reduce((v,r)=>v*r.dec,1);
 // An overflow cannot be presented as a real ticket price.
 if(!Number.isFinite(ticket.decimal))return fail('The combined illustrative price is outside the supported range.');
 ticket.estimatedReturn=ticket.probability*ticket.decimal-1;
 try{ticket.boost=profitBoost(ticket.probability,ticket.decimal,o.boostPercent,o.stake);}catch{return fail('The combined illustrative estimate is outside the supported range.');}
 if(ticket.decimal<context.lower||ticket.decimal>context.upper)ticket.issues.push('This draft is outside the selected combined odds range.');
 if(ticket.boost.returnPerDollar<0)ticket.issues.push('This draft has a negative estimated return after the selected boost.');
 ticket.ready=ticket.issues.length===0;
 return ticket;
}
function summarize(legs,pool,options={}){return summarizeEdit(legs,editContext(pool,options));}
function manageEdit(legs,context,action={}){
 const current=Array.isArray(legs)?legs:[],reject=error=>({ok:false,legs:current,ticket:summarizeEdit(current,context),error});
 if(!Array.isArray(legs))return reject('Choose a valid ticket.');
 const {type,index,row}=action||{};
 if(!['remove','swap','add'].includes(type))return reject('Choose remove, swap or add.');
 if(type!=='add'&&(!Number.isInteger(index)||index<0||index>=current.length))return reject('Choose a leg on the ticket.');
 const next=current.slice();
 if(type==='remove'){
  next.splice(index,1);return {ok:true,legs:next,ticket:summarizeEdit(next,context),error:null};
 }
 if(context.error)return reject(context.error);
 if(type==='add'&&current.length>=6)return reject('Six legs is the maximum.');
 if(!context.eligible(row)||!context.quotes.has(quoteKey(row)))return reject('That selection no longer has a supported current quote.');
 if(current.length&&row.book!==current[0]?.book)return reject('Keep every leg at the current sportsbook.');
 if(context.o.sameGame&&current.length&&row.event!==current[0]?.event)return reject('Keep every same-game leg in the original game.');
 if(current.some(r=>r&&contractKey(r)===contractKey(row)))return reject('This selection is already on the ticket.');
 if(type==='swap')next[index]=row;else next.push(row);
 const ticket=summarizeEdit(next,context);
 if(!ticket.valid)return reject(ticket.error);
 if(next.length>=2&&!ticket.ready)return reject(ticket.issues.join(' '));
 return {ok:true,legs:next,ticket,error:null};
}
function manage(legs,pool,options={},action={}){return manageEdit(legs,editContext(pool,options),action);}
function alternatives(legs,pool,options={},request={}){
 const context=editContext(pool,options),list=Array.isArray(legs)?legs:[],index=request?.index??null;
 if(context.error||!Array.isArray(legs)||(index!==null&&(!Number.isInteger(index)||index<0||index>=list.length))||(index===null&&list.length>=6))return [];
 if(!summarizeEdit(index===null?list:list.filter((_,i)=>i!==index),context).valid)return [];
 const limit=Math.max(0,Math.min(6,Number.isInteger(request?.limit)?request.limit:6));
 const candidates=context.pool.slice().sort((a,b)=>b.prob-a.prob||b.ev-a.ev),found=[],seen=new Set();
 for(const row of candidates){
  if(found.length>=limit)break;
  const key=contractKey(row);if(seen.has(key))continue;
  if(manageEdit(list,context,{type:index===null?'add':'swap',index,row}).ok){seen.add(key);found.push(row);}
 }
 return found;
}
root.GoingFootballParlays={select,profitBoost,summarize,manage,alternatives};if(typeof module!=='undefined')module.exports=root.GoingFootballParlays;
})(globalThis);
