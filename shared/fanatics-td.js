/* Fanatics Sunday TD selection engine (pure logic, no DOM). Generates, validates and ranks three-leg anytime-touchdown slips.
 *
 * What it does NOT do: invent prices, substitute another sportsbook's odds, claim promotion eligibility, value the shared prize, or turn a model estimate into a
 * proven hit rate. A leg needs a real Fanatics price (feed quote or a user-entered Fanatics price), a model probability, confirmed availability from TWO independent
 * checks (the roster screen and the GOING eligibility engine) and a game that has not started. Anything unverifiable is excluded and counted, never guessed.
 *
 * Terms: config/fanatics_td_terms.json records which rules are verified and which are user-supplied. This module takes the effective terms as a parameter.
 * Qualification uses full-precision decimal odds: product of the three decimal prices >= decimal(minCombinedAmerican) (+2000 = 21.00).
 * Probability: joint = P(A) x P(B) x P(C), an independence approximation (legs are from three different games). It is a model estimate, not a hit rate.
 */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const EPS=1e-9;
const DEFAULT_TERMS={legs:3,minStake:5,minCombinedAmerican:2000,market:'atd',differentGames:true,quoteMaxAgeMinutes:15,manualMaxAgeMinutes:120,optionCount:5,diversify:false,maxPlayerAppearances:null,minimumLegAmerican:null,maxLegProbability:.85};
const decimal=a=>finite(a)&&Math.abs(a)>=100?(a>0?1+a/100:1+100/-a):null;
const american=d=>!finite(d)||d<=1?null:d>=2?(d-1)*100:-100/(d-1);
const roundAmerican=a=>a==null?null:Math.round(a);
const nameKey=n=>String(n||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const fmtAmerican=a=>a==null?'n/a':(a>0?'+':'')+Math.round(a);

function validateTerms(t){
 const terms={...DEFAULT_TERMS,...(t||{})};
 if(terms.legs!==3)throw Error('This engine builds exactly three-leg slips.');
 if(!decimal(terms.minCombinedAmerican))throw Error('Minimum combined odds must be valid American odds.');
 if(terms.minimumLegAmerican!=null&&!decimal(terms.minimumLegAmerican))throw Error('Individual-leg minimum must be valid American odds.');
 if(!(terms.quoteMaxAgeMinutes>0)||!(terms.manualMaxAgeMinutes>0))throw Error('Price age limits must be positive.');
 terms.optionCount=Math.max(1,Math.min(20,Math.trunc(terms.optionCount)));
 return terms;
}

// leg: {playerId, player, team, opp, event, gameLabel, kickoff, probability, availability ('active'|'expected'|...), eligibility:{actionable,state,label}|null,
//       price:{american, source:'feed'|'manual', book, updatedAt}|null}
function legProblem(leg,now,terms){
 if(!leg||!leg.playerId||!leg.event)return 'Missing player or game identity';
 const kick=Date.parse(leg.kickoff);
 if(!Number.isFinite(kick)||kick<=now)return 'Game started or time unavailable';
 if(!finite(leg.probability)||leg.probability<=0||leg.probability>=1)return 'Missing or invalid model estimate';
 const p=leg.price;
 if(!p||!finite(p.american))return 'No Fanatics price';
 if(String(p.book||'fanatics').toLowerCase()!=='fanatics')return 'Other sportsbook price';
 const dec=decimal(p.american);if(!dec)return 'Invalid price';
 const at=Date.parse(p.updatedAt),limit=(p.source==='manual'?terms.manualMaxAgeMinutes:terms.quoteMaxAgeMinutes)*60000;
 if(!Number.isFinite(at)||at>now+60000||now-at>limit)return p.source==='manual'?'Entered price expired':'Price needs refreshing';
 if(!['active','expected'].includes(leg.availability))return 'Roster screen did not confirm availability';
 // The shared GOING eligibility decision is required as well; missing means unverified, never active.
 if(!leg.eligibility||leg.eligibility.actionable!==true)return leg.eligibility?'Not eligible: '+(leg.eligibility.label||leg.eligibility.state||'unavailable'):'Eligibility not verified';
 if(terms.minimumLegAmerican!=null&&dec<decimal(terms.minimumLegAmerican))return 'Below individual-leg minimum';
 if(terms.maxLegProbability!=null&&leg.probability>terms.maxLegProbability)return 'Model estimate above the reliability ceiling';
 return null;
}
const better=(a,b)=>a.probability!==b.probability?a.probability>b.probability:a.decimal!==b.decimal?a.decimal<b.decimal:a.key<b.key;

function select(input,settings={}){
 const now=settings.now??Date.now(),terms=validateTerms(settings.terms);
 const floor=decimal(terms.minCombinedAmerican),excluded={},reject=w=>{excluded[w]=(excluded[w]||0)+1;};
 const byPlayer=new Map();
 for(const leg of input||[]){
  const why=legProblem(leg,now,terms);
  if(why){reject(why);continue;}
  const key=leg.playerId,old=byPlayer.get(key);
  if(!old||Date.parse(leg.price.updatedAt)>Date.parse(old.price.updatedAt))byPlayer.set(key,{...leg,decimal:decimal(leg.price.american)});
 }
 // Players excluded by the caller (e.g. user removed a player).
 const drop=new Set(settings.excludedPlayers||[]);const legs=[...byPlayer.values()].filter(l=>{if(drop.has(l.playerId)){reject('Excluded by you');return false;}return true;}).sort((a,b)=>b.probability-a.probability||a.playerId.localeCompare(b.playerId));
 const n=legs.length,games=new Set(legs.map(l=>l.event)).size;
 const wanted=terms.diversify?Math.max(terms.optionCount*40,200):terms.optionCount;
 const top=[];let examined=0;
 const kth=()=>top.length>=wanted?top[top.length-1].probability:-1;
 const consider=(i,j,k)=>{
  const a=legs[i],b=legs[j],c=legs[k];
  if(a.event===b.event||a.event===c.event||b.event===c.event)return;
  examined++;
  const dec=a.decimal*b.decimal*c.decimal;
  if(dec+EPS<floor)return;
  const option={key:[a,b,c].map(l=>l.playerId).sort().join('~'),legs:[a,b,c],decimal:dec,american:american(dec),probability:a.probability*b.probability*c.probability};
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
  entries.push({playerId:matches[0].playerId,player:matches[0].player,american,enteredAt:new Date(now).toISOString()});
 }
 return {entries,errors};
}

function describeTerms(config){
 const rows=Object.entries(config?.terms||{}).map(([k,t])=>({key:k,value:t.value,status:t.status,source:t.source||null,note:t.note||null}));
 return {verified:rows.filter(r=>r.status==='verified-secondary'||r.status==='verified'),userSupplied:rows.filter(r=>r.status==='user-supplied'),unverified:rows.filter(r=>r.status==='unverified'||r.status==='conflicting')};
}

const api={DEFAULT_TERMS,decimal,american,roundAmerican,fmtAmerican,nameKey,validateTerms,legProblem,select,parseManualPrices,describeTerms};
root.GoingFanaticsTD=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis==='undefined'?this:globalThis);
