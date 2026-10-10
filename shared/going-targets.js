/* Players to Target: pure logic (no DOM). Two views built from the same shared facts so GOING never gives conflicting answers about one player:
 *   fantasyTargets: buy-low / emerging opportunity / waiver-stash / sell-high / monitor
 *   bettingTargets: players whose role evidence supports researching a specific market, priced or not
 * Availability comes first: unavailable players are never actionable in either view.
 * Evidence status: the opportunity-vs-production gap did NOT predict future points in our test (research E12), so gaps alone never create a target; they must come with
 * real opportunity (top-40% expected points at the position) and a stable-or-rising role. All thresholds below are fixed design rules, not fitted values.
 */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const intel=()=>root.GoingIntel||(typeof require!=='undefined'?require('./going-intel.js'):null);
const OUT=new Set(['RES','INA','PUP','IR','SUS','RET','EXE']),OFF=new Set(['CUT','DEV','PRA','PS']);
const RULES={marketWeight:.15,minGames:3,buyGap:-2.5,buyGapL3:-1,sellGap:3,expTop:60,expMid:25,emergingScore:40,staleDays:21,extremeProb:.85,reviewEv:.25,returnStashWeeks:4};

// Availability is decided by the shared engine (shared/going-eligibility.js) so Targets agree with every other surface. indexInjury() just captures the inputs.
const elig=()=>root.GoingEligibility||(typeof require!=='undefined'?require('./going-eligibility.js'):null);
function indexInjury(injury,week,roster){return {injury,roster,week,asOf:injury?.generated_at||roster?.generated_at||null,engines:new Map()};}
function engineFor(inj,now){
 const key=Math.floor(now/60000);if(!inj.engines.has(key))inj.engines.set(key,elig().create({injury:inj.injury,roster:inj.roster,week:inj.week,now}));
 return inj.engines.get(key);
}
function availability(id,profile,inj,now=Date.now()){
 const e=engineFor(inj,now),d=e.decide(id,{team:profile?.team,lastGame:profile?.last_game});
 return {...d,asOf:d.asOf||inj.asOf};
}

function percentileMap(rows,key){
 const by={};for(const r of rows)if(r.g>=RULES.minGames&&finite(r[key]))(by[r.pos]??=[]).push(r[key]);
 for(const k in by)by[k].sort((a,b)=>a-b);
 return (pos,v)=>{const a=by[pos];if(!a||!a.length||!finite(v))return null;let n=0;for(const x of a)if(x<=v)n++;return 100*n/a.length;};
}
const fmt1=x=>finite(x)?(Math.round(x*10)/10).toFixed(1):'n/a';

// ctx: {ovp:{players:[...]}, profiles, score:{players:{}}, injury, week, now, window:'season'|'l3'}
function fantasyTargets(ctx){
 const I=intel(),now=ctx.now||Date.now(),inj=indexInjury(ctx.injury,ctx.week,ctx.roster),win=ctx.window==='l3'?'l3':'season';
 const rows=(ctx.ovp?.players||[]).map(r=>{
  const t=r.trend3||{};
  const exp=win==='l3'&&finite(t.exp_pg)?t.exp_pg:r.exp_pg,act=win==='l3'&&finite(t.act_pg)?t.act_pg:r.act_pg;
  return {...r,exp,act,res:finite(exp)&&finite(act)?act-exp:null,gUsed:win==='l3'?Math.min(r.g||0,t.games?.length||3):r.g};
 });
 const pct=percentileMap(rows,'exp'),out={buy_low:[],emerging:[],stash:[],sell_high:[],monitor:[]},unavailable=[];
 for(const r of rows){
  const profile=ctx.profiles?.[r.id],av=availability(r.id,profile,inj,now),sc=ctx.score?.players?.[r.id];
  if(r.g<RULES.minGames||!finite(r.exp))continue;
  const role=I&&profile?I.roleTrend(profile.role_trend,r.pos,r.pos==='RB'?'rush_yds':'rec_yds'):null;
  const ep=pct(r.pos,r.exp),scorePct=sc?.score,why=[],concern=[];
  const base={id:r.id,name:r.name,pos:r.pos,team:r.team,games:r.g,exp:r.exp,act:r.act,res:r.res,expPct:ep,score:sc?.score??null,scoreRank:sc?.rank??null,scoreOf:sc?.of??null,delta3w:sc?.delta_3w??null,
   role:role?{state:role.state,text:role.text}:null,availability:av,series:(r.trend3?.games||[]).map(x=>({week:x[0],exp:x[1],act:x[2]})),scoringRole:profile?.scoring_role?.tier||null};
  const flat=!role||role.state!=='down';
  if(!av.actionable&&!av.caution){ if(ep!=null&&ep>=RULES.expMid||r.pos==='QB')unavailable.push({...base,category:'unavailable'}); continue; }
  if(!av.actionable&&av.caution){ unavailable.push({...base,category:'unavailable'}); continue; }
  const push=(cat,strength,whyArr,concernArr)=>out[cat].push({...base,category:cat,strength,why:whyArr,concern:[...concernArr,...(av.caution?[`${av.label}: ${av.detail}`]:[])]});
  const gapL3=r.trend3?.res_pg;
  if(role?.state==='up'&&scorePct!=null&&scorePct>=RULES.emergingScore&&ep!=null&&ep>=RULES.expTop){
   push('emerging',(Math.max(...role.parts.map(p=>Math.abs(p.change)/({snap_share:8,target_share:.03,carry_share:.05})[p.metric]))||1)*(ep||50)/100,
    [`Role is growing: ${role.text}.`,`Opportunity is ${fmt1(r.exp)} expected points per game (${ep!=null?Math.round(ep)+'th percentile at '+r.pos:'percentile n/a'}).`,`GOING Score ${Math.round(scorePct)}${sc.rank?` (rank ${sc.rank} of ${sc.of})`:''}.`],
    [r.g<5?`Only ${r.g} games of data.`:'Usage can reverse with one injury or game script.','Role expansion was validated for next-game volume, not for fantasy points or prices.']);
  }else if(role?.state==='up'&&ep!=null&&ep>=RULES.expMid&&ep<RULES.expTop){
   push('stash',(ep)/100,[`Role is growing: ${role.text}.`,`Current opportunity is modest (${fmt1(r.exp)} expected points per game), so this is a watch/stash, not a starter.`],['Needs more weeks to confirm; check availability on your waiver wire.']);
  }
  if(finite(r.res)&&r.res<=RULES.buyGap&&ep!=null&&ep>=RULES.expTop&&flat&&(!finite(gapL3)||gapL3<=RULES.buyGapL3||win==='l3')){
   push('buy_low',-r.res*(ep/100),[`Scored ${fmt1(-r.res)} fewer points per game than the opportunity implies (${fmt1(r.act)} vs ${fmt1(r.exp)}).`,`Opportunity is real: ${Math.round(ep)}th percentile at ${r.pos}${role?`; ${role.text}`:''}.`],
    ['Opportunity-vs-production gaps did not predict later points in our test; this is a descriptive case, not a forecast.',...(role?.state==='flat'||!role?[]:[]),...(r.g<5?[`Only ${r.g} games.`]:[])]);
  }
  if(finite(r.res)&&r.res>=RULES.sellGap&&role?.state!=='up'&&(ep==null||ep<RULES.expTop||role?.state==='down')){
   push('sell_high',r.res,[`Scored ${fmt1(r.res)} more points per game than the opportunity implies (${fmt1(r.act)} vs ${fmt1(r.exp)}).`,role?.state==='down'?`Role is shrinking: ${role.text}.`:`Opportunity is only ${ep!=null?Math.round(ep)+'th percentile':'average'} at ${r.pos}.`],
    ['Overperformance is not proven to fade; this is an avoid/sell case, not a prediction of a collapse.']);
  }
  if(av.caution&&ep!=null&&ep>=70&&!out.monitor.some(x=>x.id===r.id)){
   push('monitor',ep/100,[`High opportunity (${Math.round(ep)}th percentile at ${r.pos}).`],[]);
  }
 }
 for(const k in out)out[k].sort((a,b)=>b.strength-a.strength);
 return {categories:out,unavailable:unavailable.sort((a,b)=>(b.expPct||0)-(a.expPct||0)),window:win,injuryAsOf:inj.asOf,rules:RULES};
}

// candidates: priced prop rows from goingPicksCandidates (kind 'prop'): {profileId,player,market,side,line,odds,dec,prob,ev,calibrated,book,updatedAt,position}
const MARKET_LABEL={rec_yds:'Receiving yards',receptions:'Receptions',rush_yds:'Rushing yards',atd:'Anytime TD'};
// What the out-of-sample test (champion_2021_2025, 2021-25, games 4+ of a season, top-15% vs bottom-15% change in share, ratio of actual to the Champion mean) found. It tests
// information beyond GOING's own Champion model. It does NOT test information beyond a sportsbook price, which cannot be tested without historical posted lines.
const EVIDENCE={
 // Receptions on target share is NOT here: the earlier +5.6% finding came from zero-filled did-not-play rows. On participants (books void non-participants) it is +1.6% (90% interval -3.8% to +7.3%), a null.
 rush_yds:{metric:'carry_share',text:'Weak evidence: for running backs, a rising carry share beat the Champion mean by 16% over a falling one on participants (95% interval +1% to +34%; positive in 4 of 5 seasons, concentrated late in the season). Not tested against a price.'},
 atd:{metric:null,text:'Scoring-role tiers beat the Champion anytime-TD rate (2025 holdout log loss -4.2%); touchdown probabilities are still dispersed (calibration slope about 0.7), so treat them as a ranking, not exact odds.'}
};
const CAL_TD=new Set(['atd','rec_tds','rush_tds']);
function thesis(profile,position,market,sr){
 const I=intel();
 if(market==='atd'){
  if(sr&&sr.confidence!=='low'&&['PRIMARY','SECONDARY'].includes(sr.tier))return {side:'Yes',evidence:EVIDENCE.atd.text,strength:sr.tier==='PRIMARY'?1:.6,why:`${sr.tier.toLowerCase()} scoring role: ${fmt1(sr.xtd_pg_l12)} expected TDs per game over the last 12.`};
  return null;
 }
 const role=I&&profile?I.roleTrend(profile.role_trend,position,market==='rush_yds'?'rush_yds':'rec_yds'):null;
 if(!role||role.state==='flat')return null;
 if(market==='rush_yds'&&position!=='RB')return null;
 const parts=role.parts.filter(p=>p.metric===EVIDENCE[market]?.metric);
 if(!parts.length||parts[0].state==='flat')return null;
 const size=Math.max(...parts.map(p=>Math.abs(p.change)/({snap_share:8,target_share:.03,carry_share:.05})[p.metric]));
 return {side:parts[0].state==='up'?'Over':'Under',strength:Math.min(2,size),why:`${parts[0].state==='up'?'Growing':'Shrinking'} ${parts[0].label.toLowerCase()}: ${parts[0].from} → ${parts[0].to} (last 6 → last 3 games).`,evidence:EVIDENCE[market].text};
}
function calStatus(market,calibrated){
 if(CAL_TD.has(market)&&calibrated)return 'TD mean corrected about 20% lower (walk-forward validated); TD probabilities remain uncertain';
 if(calibrated)return 'Probability recalibrated (holdout slope about 1.0)';
 return 'Raw model probability: overconfident in audits, unreliable above about 80%';
}
function bettingTargets(ctx,candidates=[]){
 const I=intel(),now=ctx.now||Date.now(),inj=indexInjury(ctx.injury,ctx.week,ctx.roster),rows=[],seen=new Set(),excluded=[];
 const markets=Object.keys(EVIDENCE),priced=new Map();// receptions and receiving yards are deliberately absent: receptions on target share is a null for participants, and a rising target share predicted FEWER yards than the Champion mean (about -12%, interval -18% to -6%, all five seasons)
 
 for(const c of candidates||[]){
  if(c.kind&&c.kind!=='prop'||!c.profileId||!MARKET_LABEL[c.market])continue;
  const k=[c.profileId,c.market,c.side,c.line].join('|'),prev=priced.get(k);
  if(!prev||(c.dec||0)>(prev.dec||0))priced.set(k,c);
 }
 for(const [id,profile] of Object.entries(ctx.profiles||{})){
  const pos=profile.position;if(!['RB','WR','TE'].includes(pos))continue;
  if(ctx.pos&&ctx.pos!=='ALL'&&pos!==ctx.pos)continue;
  const av=availability(id,profile,inj,now);
  for(const m of markets){
   if(m==='rush_yds'&&pos!=='RB'||m==='receptions'&&pos==='QB')continue;
   const th=thesis(profile,pos,m,profile.scoring_role);if(!th)continue;
   if(!av.actionable){if(th.strength>=1)excluded.push({id,name:profile.name,team:profile.team,pos,market:m,reason:av.label,detail:av.detail});continue;}
   const all=[...priced.values()].filter(c=>c.profileId===id&&c.market===m&&(m==='atd'?c.side==='Yes':c.side===th.side));
   // The main line is the middle of the posted ladder; alternate and extreme lines are not the market a role trend speaks to.
   const lines=[...new Set(all.map(c=>c.line))].filter(finite).sort((a,b)=>a-b),mid=lines.length?lines[Math.floor((lines.length-1)/2)]:null;
   const offers=m==='atd'?all:all.filter(c=>mid==null||Math.abs(c.line-mid)<=Math.max(.5,.25*Math.abs(mid)));
   const best=offers.sort((a,b)=>(m==='atd'?0:Math.abs(a.line-mid)-Math.abs(b.line-mid))||(b.dec||0)-(a.dec||0))[0];
   const key=id+'|'+m;if(seen.has(key))continue;seen.add(key);
   const extreme=best&&(best.prob>=RULES.extremeProb||best.prob<=.15&&best.dec>=4),bigGap=best&&finite(best.ev)&&best.ev>RULES.reviewEv;
   // Live receptions test (4 weeks, 48 games): the book price predicted outcomes with slope ~1.0, the model added nothing detectable beyond it (weight -0.02, upper bound ~0.26).
   // So value is shown against the de-vigged price with only a small model weight; one-sided markets (anytime TD) cannot be de-vigged and show no value.
   const opp=best?priced.get([id,m,th.side==='Over'?'Under':'Over',best.line].join('|')):null;
   let evShrunk=null;
   if(best&&opp&&finite(best.prob)&&finite(opp.prob)&&best.prob+opp.prob>0&&best.dec>1&&opp.dec>1){
    const fair=(1/best.dec)/(1/best.dec+1/opp.dec),pm=best.prob/(best.prob+opp.prob),q=fair+RULES.marketWeight*(pm-fair);
    evShrunk=q*best.dec-1;
   }
   const valueShown=!!best&&finite(evShrunk)&&!extreme&&!bigGap;
   const concerns=[];
   if(av.caution)concerns.push(`${av.label}: ${av.detail}`);
   if(!best)concerns.push('No posted line in our feed, so there is no price to compare: a research target, not a betting edge.');
   if(extreme)concerns.push('The model puts this at an extreme probability. Estimates above 85% have not held up in recorded results.');
   if(bigGap)concerns.push('The model and sportsbook disagree unusually strongly; the estimated value is likely overstated and is withheld.');
   if(best&&!best.calibrated)concerns.push('Probability is the raw model output, not recalibrated.');
   concerns.push('Role trends were validated for next-game volume, not for beating sportsbook prices.');
   rows.push({opportunity:{signal:th.why,evidence:th.evidence,beyondPrice:'Unknown: no historical posted lines exist to test it.'},recommendation:{level:'research',text:best?(extreme||bigGap?'Not a recommendation: the model and price disagree beyond what has held up.':'Research only. No validated edge against sportsbook prices exists for this market; compare the price yourself.'):'Research only. No price to evaluate.'},id,name:profile.name,team:profile.team,pos,market:m,marketLabel:MARKET_LABEL[m],direction:th.side,strength:th.strength+(best?.25:0),why:[th.why],concern:concerns,
    availability:av,priced:!!best,line:best?.line??null,odds:best?.odds??null,book:best?.book||null,updatedAt:best?.updatedAt||null,prob:best?.prob??null,
    calibration:best?calStatus(m,best.calibrated):null,ev:valueShown?evShrunk:null,evModelOnly:best&&finite(best.ev)?best.ev:null,evWithheld:!!best&&!valueShown&&(extreme||bigGap),evUnavailable:!!best&&!finite(evShrunk),
    status:best?(extreme||bigGap?'Priced, needs review':valueShown&&evShrunk<-.02?'Priced, no value at this price':'Priced research target'):'Research target (no price)',
    scoringTier:profile.scoring_role?.tier||null});
  }
 }
 const tier=r=>!r.priced?0:/needs review|no value/.test(r.status)?1:2;
 rows.sort((a,b)=>tier(b)-tier(a)||b.strength-a.strength);
 return {targets:rows,excluded:excluded.slice(0,40),injuryAsOf:inj.asOf,rules:RULES};
}
root.GoingTargets={RULES,availability,indexInjury,fantasyTargets,bettingTargets,MARKET_LABEL};
if(typeof module!=='undefined')module.exports=root.GoingTargets;
})(globalThis);
