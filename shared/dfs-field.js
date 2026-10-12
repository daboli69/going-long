(function(root){
'use strict';
// Showdown field model: projected Captain / FLEX ownership and lineup duplication risk.
// The code is public; the COEFFICIENTS are not. They come from a private file (showdown_models.json) derived from licensed stat-api contest history, which the user loads
// from their own disk in the browser. Nothing here fetches, stores or embeds that data. Without the file every function returns null and the DFS page works as before.
// Validation: see showdown_models_report.json (models fitted on contests before 2025, scored on 2025-26 contests).
const ENTRIES_RANGE=[11000,90000]; // field sizes seen in training; the entries feature is clamped to this range
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const state={models:null,loadedAt:null};
function validModel(data){
 const vector=(x,n,check=finite)=>Array.isArray(x)&&x.length===n&&x.every(check);
 if(data?.schema!=='going-private-showdown-models-v2')return false;
 for(const [role,total] of [['CPT',100],['FLEX',500]]){
  const m=data.ownership?.[role];
  if(!m||!Number.isInteger(m.bins)||m.bins<1||m.bins>1000||m.total!==total)return false;
  for(const g of ['QB','SKILL','DK'])if(!vector(m.table?.[g],m.bins,x=>finite(x)&&x>=0))return false;
 }
 const d=data.duplication,n=d?.features?.length,allowed=['cpt_own','sum_flex_own','min_flex_own','log_prod_own','unused','cpt_salary_rank_pct','max_team','n_stars','cpt_pos_QB','log_entries'];
 return !!d&&Array.isArray(d.features)&&n>0&&n<=allowed.length&&new Set(d.features).size===n&&d.features.every(x=>allowed.includes(x))&&vector(d.coef,n)&&vector(d.mean,n)&&vector(d.sd,n,x=>finite(x)&&x>0)&&finite(d.intercept)&&finite(d.resid_sd)&&d.resid_sd>=0&&vector(d.decile_edges,9,x=>finite(x)&&x>=0)&&d.decile_edges.every((x,i,a)=>!i||x>=a[i-1])&&vector(d.decile_median_copies,10,x=>finite(x)&&x>=0)&&vector(d.decile_unique_share,10,x=>finite(x)&&x>=0&&x<=1);
}

function load(json){
 let data=json;if(typeof json==='string'){try{data=JSON.parse(json);}catch{return {ok:false,reason:'The file is not valid JSON.'};}}
 if(!validModel(data))return {ok:false,reason:'Invalid GOING Showdown model: check ownership tables and finite, matching duplication coefficients. Previous model retained.'};
 state.models=data;state.loadedAt=Date.now();return {ok:true};
}
function clear(){state.models=null;state.loadedAt=null;}
function ready(){return Boolean(state.models);}

const group=position=>position==='QB'?'QB':(position==='DST'||position==='K')?'DK':'SKILL';
// Adds ownership (% of the field) to every Showdown pool row. Exactly as in training: ALL pool rows with a salary are ranked (injured/unavailable players included), the rank is
// 1 + number of same-role players with strictly higher salary (ties share the best rank, so row order never matters), then a table lookup normalised so Captain sums to 100% and FLEX to 500%.
function annotate(players){
 if(!state.models)return players;
 for(const role of ['CPT','FLEX']){
  const model=state.models.ownership[role],rows=players.filter(p=>p.showdownRole===role&&finite(p.salary));
  if(!rows.length)continue;
  const salaries=rows.map(p=>p.salary),raw=new Map();let total=0;
  for(const p of rows){const rank=1+salaries.filter(s=>s>p.salary).length,value=model.table[group(p.position)][Math.min(rank-1,model.bins-1)];p.fieldRank=rank;p.fieldRankPct=rank/rows.length;raw.set(p,value);total+=value;}
  for(const p of rows){p.ownership=total>0?Math.min(100,raw.get(p)*model.total/total):null;p.ownershipRole=role;}
 }
 return players;
}

function zscore(features,spec){return features.map((v,i)=>(v-spec.mean[i])/spec.sd[i]);}
// Features exactly as the training code builds them (scripts/statapi/showdown_models.py lineup_rows). `lineup` = [captain, flex x5] pool rows after annotate().
function lineupFeatures(lineup,entries){
 const captain=lineup.find(p=>p.slot==='CPT'||p.slot==='MVP')||lineup[0],flex=lineup.filter(p=>p!==captain);
 if(!captain||flex.length!==5||[captain,...flex].some(p=>!finite(p.ownership)||!finite(p.fieldRankPct)))return null;
 const salary=lineup.reduce((s,p)=>s+(finite(p.salary)?p.salary:0),0),flexOwn=flex.map(p=>p.ownership);
 const sameTeam=flex.filter(p=>p.team===captain.team).length+1,maxTeam=Math.max(sameTeam,6-sameTeam);
 return {cpt_own:captain.ownership,sum_flex_own:flexOwn.reduce((a,b)=>a+b,0),min_flex_own:Math.min(...flexOwn),
  log_prod_own:Math.log(Math.max(captain.ownership,.05)/100)+flexOwn.reduce((s,o)=>s+Math.log(Math.min(100,Math.max(o,.05))/100),0),
  unused:50000-salary,cpt_salary_rank_pct:captain.fieldRankPct,max_team:maxTeam,
  n_stars:flex.filter(p=>p.fieldRankPct<=.1).length+(captain.fieldRankPct<=.1?1:0),cpt_pos_QB:captain.position==='QB'?1:0,log_entries:Math.log(Math.min(ENTRIES_RANGE[1],Math.max(ENTRIES_RANGE[0],entries)))};
}
// Expected number of identical lineups (including this one) and where the lineup sits among archived field lineups. The decile tables come from held-out archived contests
// scored by a model fitted on earlier contests only. The model ranks lineups; it is not an exact count (expectedCopies is a mean and the real counts are heavy-tailed).
function duplication(lineup,entries=30000){
 if(!state.models)return null;const spec=state.models.duplication,f=lineupFeatures(lineup,entries);if(!f)return null;
 const x=spec.features.map(name=>f[name]),z=zscore(x,spec),logDup=spec.intercept+z.reduce((s,v,i)=>s+v*spec.coef[i],0),copies=Math.exp(logDup+.5*spec.resid_sd**2);
 const decile=1+spec.decile_edges.filter(e=>e<copies).length,band=decile<=3?'lower':decile<=7?'typical':'higher';
 return {logDup,expectedCopies:copies,decile,band,medianCopies:spec.decile_median_copies[decile-1],uniqueShare:spec.decile_unique_share[decile-1],entries:Math.min(ENTRIES_RANGE[1],Math.max(ENTRIES_RANGE[0],entries)),
  note:'Ranks lineups by predicted duplication. In archived 2025-26 contests, field lineups in this decile had the median copies and unique share shown (group statistics, not a prediction for this lineup). Field size is clamped to 11,000-90,000 entries.'};
}
// First-order, additive stand-in for one player's contribution to the lineup's log expected duplicates (beam search only; finalists are scored by duplication() exactly). Uses the three
// features that are sums over players: captain ownership, sum of FLEX ownership and the log product of ownership. Other features (min FLEX ownership, salary left, team split) are ignored here.
function dupMarginal(player,captain){
 const spec=state.models?.duplication;if(!spec||!finite(player?.ownership))return 0;
 const w=name=>{const i=spec.features.indexOf(name);return i<0?0:spec.coef[i]/spec.sd[i];},own=player.ownership;
 return (captain?w('cpt_own')*own:w('sum_flex_own')*own)+w('log_prod_own')*Math.log(Math.min(100,Math.max(own,.05))/100);
}
function lineupOwnership(lineup){
 const captain=lineup.find(p=>p.slot==='CPT'||p.slot==='MVP'),flex=lineup.filter(p=>p!==captain);
 if(!captain||!lineup.every(p=>finite(p.ownership)))return null;
 return {productIndex:lineup.reduce((product,p)=>product*p.ownership/100,1),captain:captain.ownership,flexTotal:flex.reduce((s,p)=>s+p.ownership,0),flexAverage:flex.reduce((s,p)=>s+p.ownership,0)/flex.length};
}
// Objectives used by the Showdown lineup types. Weights were chosen on contests before 2025 (lambda .5, gamma .05); the 2025-26 holdout then showed no reliable ROI difference between types.
const WEIGHTS={lambda:.5,gamma:.05};
function objective(kind,moments,lineup,entries){
 const dup=duplication(lineup,entries),own=lineupOwnership(lineup),ceiling=moments.mean+1.2816*moments.sd;
 if(kind==='lowdup')return dup?moments.mean-WEIGHTS.lambda*dup.logDup:moments.mean;
 if(kind==='leverage')return own?moments.mean-WEIGHTS.gamma*(own.captain+own.flexTotal):moments.mean;
 if(kind==='best')return dup?ceiling-WEIGHTS.lambda*dup.logDup:ceiling;
 return ceiling;
}
root.GoingDfsField={SCHEMA:'going-private-showdown-models-v2',WEIGHTS,load,clear,ready,annotate,lineupFeatures,duplication,dupMarginal,lineupOwnership,objective,state};
if(typeof module!=='undefined')module.exports=root.GoingDfsField;
})(globalThis);
