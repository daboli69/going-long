(function(root){
'use strict';
function select(rows,{sport,now=Date.now(),start,last,legs=2,minOdds=null,maxOdds=null,book:chosenBook="all",kind="all",events=null}={}){
 const decimal=o=>o==null?null:Number.isFinite(o)&&Math.abs(o)>=100?(o>0?1+o/100:1+100/-o):NaN;
 const lower=decimal(minOdds)??1,upper=decimal(maxOdds)??Infinity;
 if(!Number.isInteger(legs)||legs<2||legs>6)throw Error('Choose between 2 and 6 legs.');
 if(!Number.isFinite(lower)||Number.isNaN(upper)||upper<lower)throw Error('Enter valid American odds, with the maximum at least the minimum.');
 const day=t=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));
 const books=new Map();
 for(const r of rows){
  const kick=Date.parse(r.kickoff),at=Date.parse(r.updatedAt);
  if((events!==null&&!events.includes(r.event))||(chosenBook!=='all'&&r.book!==chosenBook)||(kind!=='all'&&r.kind!==kind)||r.sport!==sport||!r.event||!r.book||r.manual||r.dfs||!Number.isFinite(kick)||kick<=now||day(kick)<start||day(kick)>last||!Number.isFinite(at)||at>now||now-at>86400000||!(r.n>=5)||!(r.prob>0&&r.prob<1)||!(r.dec>1)||!Number.isFinite(r.ev)||r.ev<0||r.ev>.25||r.push!==0||r.market==='first_td'||/_1[hq]$/.test(r.market)||r.flags?.some(f=>f.id==='check'&&!f.historicalOnly))continue;
  if(r.kind==='prop'&&!r.profileId)continue;
  if(!books.has(r.book))books.set(r.book,[]);books.get(r.book).push(r);
 }
 let parlay=null,sgp=null;
 const entity=r=>r.kind==='prop'?'player:'+r.profileId:'game:'+(['spread','moneyline'].includes(r.market)?'result':r.market);
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
   if(!parlay||candidate.probability>parlay.probability)parlay={book,...candidate,estimatedReturn:candidate.probability*candidate.decimal-1};
  }
  for(const group of events.values()){
   const chosen=[],seen=new Set();for(const r of group){if(seen.has(entity(r)))continue;seen.add(entity(r));chosen.push(r);if(chosen.length===legs)break;}
   if(chosen.length!==legs)continue;
   const weakest=Math.min(...chosen.map(r=>r.prob));
   if(!sgp||weakest>sgp.weakest)sgp={book,legs:chosen,weakest,probability:null,decimal:null};
  }
 }
 return {parlay,sgp};
}
root.GoingFootballParlays={select};if(typeof module!=='undefined')module.exports=root.GoingFootballParlays;
})(globalThis);
