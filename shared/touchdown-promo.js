/* Fanatics three-touchdown research. No pool-share valuation or invented joint adjustment. */
(function(root){
'use strict';
const decimal=odds=>Number.isFinite(odds)&&Math.abs(odds)>=100?(odds>0?1+odds/100:1+100/-odds):null;
function optimize(input,settings={}){
 const now=settings.now??Date.now(),floor=decimal(settings.minimumAmerican??2000);
 if(!floor)throw Error('Minimum combined odds must be valid American odds.');
 const date=settings.slateDate;
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||''))throw Error('Choose the Sunday slate date.');
 const day=stamp=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(stamp));
 const seen=new Map(),excluded={};
 const reject=why=>{excluded[why]=(excluded[why]||0)+1;};
 for(const leg of input){
  const kick=Date.parse(leg.kickoff),at=Date.parse(leg.updatedAt),dec=decimal(leg.odds);
  let why=leg.book!=='fanatics'?'Other sportsbook':leg.market!=='atd'||leg.line!==.5?'Wrong touchdown market':!leg.playerId||!leg.event?'Missing player or game identity':!dec?'Invalid price':!Number.isFinite(leg.probability)||leg.probability<=0||leg.probability>=1?'Missing model estimate':!Number.isFinite(kick)||kick<=now?'Game started or time unavailable':day(kick)!==date?'Outside selected slate':!Number.isFinite(at)||at>now||now-at>(settings.maxAgeMinutes??15)*60000?'Price needs refreshing':!['active','expected'].includes(leg.availability)?'Availability not confirmed':null;
  if(!why&&settings.minimumLegAmerican!=null&&dec<decimal(settings.minimumLegAmerican))why='Below individual-leg minimum';
  if(!why&&(settings.excludedPlayers||[]).includes(leg.playerId))why='Excluded player';
  if(!why&&(settings.excludedEvents||[]).includes(leg.event))why='Excluded game';
  if(why){reject(why);continue;}
  const key=leg.event+'|'+leg.playerId,old=seen.get(key);
  if(!old||at>Date.parse(old.updatedAt))seen.set(key,{...leg,decimal:dec});
 }
 const legs=[...seen.values()],top=[],sameGame=[];
 for(let i=0;i<legs.length;i++)for(let j=i+1;j<legs.length;j++)for(let k=j+1;k<legs.length;k++){
  const group=[legs[i],legs[j],legs[k]];
  if(new Set(group.map(l=>l.playerId)).size!==3)continue;
  const repeated=new Set(group.map(l=>l.event)).size<3;
  const price=group.reduce((v,l)=>v*l.decimal,1),probability=group.reduce((v,l)=>v*l.probability,1);
  const key=group.map(l=>l.event+'|'+l.playerId).sort().join('~');
  if(repeated){
   if(!settings.includeSameGame)continue;
   const ticket=decimal(settings.ticketAmerican?.[key]);
   if(!ticket||ticket<floor)continue;
   sameGame.push({key,legs:group,decimal:ticket,american:(ticket-1)*100,probability:null,independenceIllustration:probability,priceSource:'Manual Fanatics ticket',qualification:'Rules require confirmation'});
   continue;
  }
  if(price+1e-12<floor)continue;
  top.push({key,legs:group,decimal:price,american:(price-1)*100,probability,priceSource:'Product of Fanatics single prices',qualification:'Rules and final ticket require confirmation'});
  top.sort((a,b)=>b.probability-a.probability||a.decimal-b.decimal||a.key.localeCompare(b.key));
  if(top.length>5)top.pop();
 }
 return {options:top,sameGame: sameGame.sort((a,b)=>b.independenceIllustration-a.independenceIllustration).slice(0,5),eligiblePlayers:legs.length,excluded,entryMode:'Five alternatives to choose from; entry allowance not verified'};
}
root.GoingTouchdown={decimal,optimize};
if(typeof module!=='undefined')module.exports=root.GoingTouchdown;
})(typeof globalThis==='undefined'?this:globalThis);
