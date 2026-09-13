(function(root){
'use strict';
function select(rows,{sport,now=Date.now(),start,last}={}){
 const day=t=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));
 const books=new Map();
 for(const r of rows){
  const kick=Date.parse(r.kickoff),at=Date.parse(r.updatedAt);
  if(r.sport!==sport||!r.event||!r.book||r.manual||r.dfs||!Number.isFinite(kick)||kick<=now||day(kick)<start||day(kick)>last||!Number.isFinite(at)||at>now||now-at>86400000||!(r.n>=5)||!(r.prob>0&&r.prob<1)||!(r.dec>1)||!Number.isFinite(r.ev)||r.ev<0||r.ev>.25||r.push!==0||r.market==='first_td'||/_1[hq]$/.test(r.market)||r.flags?.some(f=>f.id==='check'&&!f.historicalOnly))continue;
  if(r.kind==='prop'&&!r.profileId)continue;
  if(!books.has(r.book))books.set(r.book,[]);books.get(r.book).push(r);
 }
 let parlay=null,sgp=null;
 const entity=r=>r.kind==='prop'?'player:'+r.profileId:'game:'+(['spread','moneyline'].includes(r.market)?'result':r.market);
 for(const [book,pool] of books){
  pool.sort((a,b)=>b.prob-a.prob||b.ev-a.ev);
  const a=pool[0],b=pool.find(r=>r.event!==a.event);
  if(b){const probability=a.prob*b.prob,decimal=a.dec*b.dec;
   if(!parlay||probability>parlay.probability)parlay={book,legs:[a,b],probability,decimal,estimatedReturn:probability*decimal-1};
  }
  const events=new Map();for(const r of pool){if(!events.has(r.event))events.set(r.event,[]);events.get(r.event).push(r);}
  for(const legs of events.values()){
   const first=legs[0],second=legs.find(r=>entity(r)!==entity(first));if(!second)continue;
   const weakest=Math.min(first.prob,second.prob);
   if(!sgp||weakest>sgp.weakest)sgp={book,legs:[first,second],weakest,probability:null,decimal:null};
  }
 }
 return {parlay,sgp};
}
root.GoingFootballParlays={select};if(typeof module!=='undefined')module.exports=root.GoingFootballParlays;
})(globalThis);
