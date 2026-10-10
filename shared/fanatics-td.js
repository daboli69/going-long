/* Fanatics Sunday TD selection engine (pure logic, no DOM). Generates, validates and ranks three-leg anytime-touchdown slips.
 *
 * What it does NOT do: invent prices, substitute another sportsbook's odds, claim promotion eligibility, value the shared prize, or turn a model estimate into a
 * proven hit rate. A leg needs a real Fanatics price (feed quote or a user-entered Fanatics price), a model probability, confirmed availability from TWO independent
 * checks (the roster screen and the GOING eligibility engine) and a game that has not started. Anything unverifiable is excluded and counted, never guessed.
 *
 * Terms: config/fanatics_td_terms.json records which rules are verified and which are user-supplied. This module takes the effective terms as a parameter.
 * Qualification uses full-precision decimal odds: product of the three decimal prices >= decimal(minCombinedAmerican) (+2000 = 21.00), without a below-floor tolerance.
 * Probability: joint = P(A) x P(B) x P(C), an independence approximation (legs are from three different games). It is a model estimate, not a hit rate.
 */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const DEFAULT_TERMS={legs:3,minStake:5,minCombinedAmerican:2000,market:'atd',differentGames:true,quoteMaxAgeMinutes:15,manualMaxAgeMinutes:120,optionCount:5,diversify:false,maxPlayerAppearances:null,minimumLegAmerican:null,maxLegProbability:null,maxPoolLegs:600};
const decimal=a=>finite(a)&&Math.abs(a)>=100?(a>0?1+a/100:1+100/-a):null;
const american=d=>!finite(d)||d<=1?null:d>=2?(d-1)*100:-100/(d-1);
const roundAmerican=a=>a==null?null:Math.round(a);
const nameKey=n=>String(n||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const fmtAmerican=a=>a==null?'n/a':(a>0?'+':'')+Math.round(a);
// Integer American prices have exact rational decimal odds. Resolve near-floor
// roundoff by cross multiplication, without admitting prices below the floor.
function meetsFloor(prices,minimum,product){
 const floor=decimal(minimum);
 if(Math.abs(product-floor)>1e-9||![...prices,minimum].every(Number.isSafeInteger))return product>=floor;
 const ratio=a=>{const value=BigInt(a);return a>0?[100n+value,100n]:[100n-value,-value];};
 const [fn,fd]=ratio(minimum);let n=1n,d=1n;
 for(const price of prices){const [pn,pd]=ratio(price);n*=pn;d*=pd;}
 return n*fd>=fn*d;
}
// Accept only real calendar timestamps carrying an explicit UTC offset.
function timestamp(t){
 if(typeof t!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(t))return null;
 const y=+t.slice(0,4),m=+t.slice(5,7),d=+t.slice(8,10),leap=y%4===0&&(y%100!==0||y%400===0),days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
 if(!y||m<1||m>12||d<1||d>days[m-1]||+t.slice(11,13)>23||+t.slice(14,16)>59||+t.slice(17,19)>59)return null;
 if(!t.endsWith('Z')&&(+t.slice(-5,-3)>23||+t.slice(-2)>59))return null;
 const ms=Date.parse(t);return Number.isFinite(ms)?ms:null;
}
const DAY_FORMAT=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}),WEEKDAY_FORMAT=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short'});
const slateDay=t=>DAY_FORMAT.format(new Date(t));
const sunday=t=>WEEKDAY_FORMAT.format(new Date(t))==='Sun';
function canonicalTeam(t,resolve){
 if(typeof t!=='string')return null;
 const alias={LAR:'LA',LA:'LA',JAC:'JAX',JAX:'JAX',WSH:'WAS',WAS:'WAS'}[t.trim().toUpperCase()];
 return alias||(resolve?resolve(t):t);
}
function gameIdentity(leg,resolve){
 const kick=timestamp(leg?.kickoff),raw=leg?.eventTeams;
 if(kick==null||!Array.isArray(raw)||raw.length!==2)return null;
 const teams=raw.map(t=>canonicalTeam(t,resolve)).map(t=>typeof t==='string'?nameKey(t):'');
 if(teams.some(t=>!t)||teams[0]===teams[1])return null;
 return teams.sort().join('|')+'|'+kick;
}
const contract=(id,event)=>JSON.stringify([id,event,'atd',.5]);

function validateTerms(t){
 const terms={...DEFAULT_TERMS,...(t||{})};
 if(terms.legs!==3)throw Error('This engine builds exactly three-leg slips.');
 if(!decimal(terms.minCombinedAmerican)||terms.minCombinedAmerican<2000)throw Error('Minimum combined odds must be +2000 or longer.');
 if(terms.minimumLegAmerican!=null&&!decimal(terms.minimumLegAmerican))throw Error('Individual-leg minimum must be valid American odds.');
 if(!finite(terms.quoteMaxAgeMinutes)||!finite(terms.manualMaxAgeMinutes)||!(terms.quoteMaxAgeMinutes>0)||!(terms.manualMaxAgeMinutes>0))throw Error('Price age limits must be finite and positive.');
 if(terms.maxLegProbability!=null&&(!finite(terms.maxLegProbability)||terms.maxLegProbability<=0||terms.maxLegProbability>=1))throw Error('Probability cap must be between zero and one.');
 if(!finite(terms.optionCount)||!finite(terms.maxPoolLegs)||terms.maxPoolLegs<3)throw Error('Pool and option counts must be finite.');
 terms.optionCount=Math.max(1,Math.min(5,Math.trunc(terms.optionCount)));
 return terms;
}

// leg: {playerId, player, team, opp, event, gameLabel, kickoff, probability, availability ('active'|'expected'|...), eligibility:{actionable,state,label}|null,
//       price:{american, source:'feed'|'manual', book, updatedAt}|null}
function legProblem(leg,now,terms,day=null){
 const event=gameIdentity(leg);
 if(!leg||typeof leg.playerId!=='string'||!leg.playerId.trim()||!event)return 'Missing player or game identity';
 const kick=timestamp(leg.kickoff);
 if(!finite(now)||kick<=now)return 'Game started or time unavailable';
 if(!sunday(kick)||(day!=null&&slateDay(kick)!==day))return 'Not on the selected Sunday';
 if(!finite(leg.probability)||leg.probability<=0||leg.probability>=1)return 'Missing or invalid model estimate';
 const p=leg.price;
 if(!p||!finite(p.american))return 'No Fanatics price';
 if(typeof p.book!=='string'||p.book.toLowerCase()!=='fanatics')return 'Other sportsbook price';
 if(!['feed','manual'].includes(p.source))return 'Unverified price source';
 if(p.contract!==contract(leg.playerId,event))return 'Price game identity mismatch';
 const dec=decimal(p.american);if(!dec)return 'Invalid price';
 const at=timestamp(p.updatedAt),limit=(p.source==='manual'?terms.manualMaxAgeMinutes:terms.quoteMaxAgeMinutes)*60000;
 if(at==null||at>now||now-at>limit)return p.source==='manual'?'Entered price expired':'Price needs refreshing';
 if(!['active','expected'].includes(leg.availability))return 'Roster screen did not confirm availability';
 // The shared GOING eligibility decision is required as well; missing means unverified, never active.
 if(!leg.eligibility||leg.eligibility.actionable!==true)return leg.eligibility?'Not eligible: '+(leg.eligibility.label||leg.eligibility.state||'unavailable'):'Eligibility not verified';
 if(terms.minimumLegAmerican!=null&&dec<decimal(terms.minimumLegAmerican))return 'Below individual-leg minimum';
 if(terms.maxLegProbability!=null&&leg.probability>terms.maxLegProbability)return 'Above configured probability cap';
 return null;
}
const better=(a,b)=>a.probability!==b.probability?a.probability>b.probability:a.decimal!==b.decimal?a.decimal<b.decimal:a.key<b.key;

function select(input,settings={}){
 const now=settings.now??Date.now(),terms=validateTerms(settings.terms);
 const excluded={},reject=w=>{excluded[w]=(excluded[w]||0)+1;};
 const byPlayer=new Map();
 for(const leg of input||[]){
  const why=legProblem(leg,now,terms,settings.slateDate);
  if(why){reject(why);continue;}
  const key=leg.playerId,old=byPlayer.get(key);
  if(old&&old.event!==gameIdentity(leg)){reject('Conflicting player game identity');byPlayer.set(key,null);continue;}
  if(byPlayer.has(key)&&old===null){reject('Conflicting player game identity');continue;}
  if(!old||timestamp(leg.price.updatedAt)>timestamp(old.price.updatedAt))byPlayer.set(key,{...leg,event:gameIdentity(leg),slateDate:slateDay(timestamp(leg.kickoff)),decimal:decimal(leg.price.american)});
 }
 // Players excluded by the caller (e.g. user removed a player).
 const drop=new Set(settings.excludedPlayers||[]);let legs=[...byPlayer.values()].filter(Boolean).filter(l=>{if(drop.has(l.playerId)){reject('Excluded by you');return false;}return true;}).sort((a,b)=>b.probability-a.probability||a.playerId.localeCompare(b.playerId));
 let truncated=0;if(legs.length>terms.maxPoolLegs){truncated=legs.length-terms.maxPoolLegs;legs=legs.slice(0,terms.maxPoolLegs);}
 const n=legs.length,games=new Set(legs.map(l=>l.event)).size;
 const wanted=terms.diversify?Math.max(terms.optionCount*40,200):terms.optionCount;
 const top=[];let examined=0;
 const kth=()=>top.length>=wanted?top[top.length-1].probability:-1;
 const consider=(i,j,k)=>{
  const a=legs[i],b=legs[j],c=legs[k];
  if(a.event===b.event||a.event===c.event||b.event===c.event)return;
  if(a.slateDate!==b.slateDate||a.slateDate!==c.slateDate)return;
  examined++;
  const dec=a.decimal*b.decimal*c.decimal;
  const payout=american(dec);
  if(!finite(dec)||!finite(payout)||!meetsFloor([a.price.american,b.price.american,c.price.american],terms.minCombinedAmerican,dec))return;
  const option={key:[a,b,c].map(l=>l.playerId).sort().join('~'),legs:[a,b,c],decimal:dec,american:payout,probability:a.probability*b.probability*c.probability};
  if(top.length>=wanted&&!better(option,top[top.length-1]))return;
  let p=top.length;while(p>0&&better(option,top[p-1]))p--;top.splice(p,0,option);if(top.length>wanted)top.pop();
 };
 // Branch and bound on probability: legs are sorted descending, so for fixed (i,j) no later leg can beat p_i*p_j*p_(j+1).
 for(let i=0;i<n-2;i++){
  if(top.length>=wanted&&legs[i].probability*legs[i+1].probability*legs[i+2].probability<kth())break;
  for(let j=i+1;j<n-1;j++){
   if(top.length>=wanted&&legs[i].probability*legs[j].probability*legs[j+1].probability<kth())break;
   for(let k=j+1;k<n;k++){
    if(top.length>=wanted&&legs[i].probability*legs[j].probability*legs[k].probability<kth())break;
    consider(i,j,k);
   }
  }
 }
 let options=top;
 if(terms.diversify){
  const cap=terms.maxPlayerAppearances??Math.max(1,Math.ceil(terms.optionCount*.6)),exposure=new Map(),picked=[];
  for(const o of top){if(o.legs.some(l=>(exposure.get(l.playerId)||0)>=cap))continue;picked.push(o);for(const l of o.legs)exposure.set(l.playerId,(exposure.get(l.playerId)||0)+1);if(picked.length===terms.optionCount)break;}
  options=picked;
 }else options=top.slice(0,terms.optionCount);
 const exposure={};for(const o of options)for(const l of o.legs)exposure[l.playerId]=(exposure[l.playerId]||0)+1;
 const reasons=[];
 if(!n)reasons.push('No leg has a usable Fanatics price, a model estimate and confirmed availability.');
 else if(n<3)reasons.push(`Only ${n} eligible player${n===1?'':'s'}; three are needed.`);
 else if(games<3)reasons.push(`Eligible players come from ${games} game${games===1?'':'s'}; three different games are needed.`);
 if(n>=3&&games>=3&&options.length<terms.optionCount)reasons.push(`Only ${options.length} distinct slip${options.length===1?'':'s'} reach ${fmtAmerican(terms.minCombinedAmerican)} from three different games; fewer than ${terms.optionCount} are shown rather than padding the list.`);
 if(truncated)reasons.push(`The pool was capped at the ${terms.maxPoolLegs} most likely scorers (${truncated} lower-probability players were not searched).`);
 return {options,eligiblePlayers:n,eligibleGames:games,examinedCombinations:examined,excluded,exposure,terms,reasons,generatedAt:new Date(now).toISOString()};
}

// "Player Name +250" or "Player Name, +250" per line. Names must match exactly one player in the pool; anything else is reported, not guessed.
function parseManualPrices(text,pool,now=Date.now()){
 const entries=[],errors=[],index=new Map();
 for(const p of pool||[]){const k=nameKey(p.player);if(!index.has(k))index.set(k,[]);index.get(k).push(p);}
 for(const raw of String(text||'').split(/\r?\n/)){
  const line=raw.trim();if(!line)continue;
  const m=line.match(/^(.*?)[\s,;:\t]+([+\-−]\d{2,5})\s*$/);
  if(!m){errors.push(`Could not read "${line}". Use: Player Name +250`);continue;}
  const american=Number(m[2].replace('−','-')),matches=index.get(nameKey(m[1]))||[];
  if(!decimal(american)){errors.push(`"${line}": invalid American odds.`);continue;}
  if(matches.length===0){errors.push(`"${m[1].trim()}" does not match a player with an upcoming game.`);continue;}
  if(matches.length>1){errors.push(`"${m[1].trim()}" matches more than one player; include the team in the pool or skip.`);continue;}
  if(!matches[0].contract){errors.push(`"${m[1].trim()}": game identity is unavailable.`);continue;}
  entries.push({playerId:matches[0].playerId,player:matches[0].player,contract:matches[0].contract,american,enteredAt:new Date(now).toISOString()});
 }
 return {entries,errors};
}

function describeTerms(config){
 const rows=Object.entries(config?.terms||{}).map(([k,t])=>({key:k,value:t.value,status:t.status,source:t.source||null,note:t.note||null}));
 return {verified:rows.filter(r=>r.status==='verified-secondary'||r.status==='verified'),userSupplied:rows.filter(r=>r.status==='user-supplied'),unverified:rows.filter(r=>r.status==='unverified'||r.status==='conflicting')};
}

const api={DEFAULT_TERMS,timestamp,timestampMs:timestamp,slateDay,sunday,canonicalTeam,gameIdentity,contract,decimal,american,roundAmerican,fmtAmerican,nameKey,validateTerms,legProblem,select,parseManualPrices,describeTerms};
root.GoingFanaticsTD=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis==='undefined'?this:globalThis);
