(function(root){
'use strict';
// Showdown field model: projected Captain / FLEX ownership and lineup duplication risk.
// The code is public; the COEFFICIENTS are not. They come from a private file (showdown_models.json) derived from licensed stat-api contest history, which the user loads
// from their own disk in the browser. Nothing here fetches, stores or embeds that data. Without the file every function returns null and the DFS page works as before.
// Validation (archived contests of 2025-26, models fitted on earlier contests): Captain ownership MAE 1.0 percentage point (naive 2.8), FLEX 4.1 (naive 11.7);
// the duplication model orders lineups (lowest predicted decile: median 2 copies, 45% unique; highest: median 23 copies, 3% unique).
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const state={models:null,loadedAt:null};

function load(json){
 let data=json;if(typeof json==='string'){try{data=JSON.parse(json);}catch{return {ok:false,reason:'The file is not valid JSON.'};}}
 if(!data||data.schema!=='going-private-showdown-models-v1'||!data.ownership?.CPT?.table||!data.ownership?.FLEX?.table||!data.duplication?.coef)return {ok:false,reason:'This is not a GOING private Showdown model file.'};
 state.models=data;state.loadedAt=Date.now();return {ok:true};
}
function clear(){state.models=null;state.loadedAt=null;}
function ready(){return Boolean(state.models);}

const group=position=>position==='QB'?'QB':(position==='DST'||position==='K')?'DK':'SKILL';
// Adds ownership (% of the field) to every Showdown pool row: rank inside the role by salary, table lookup, normalised so Captain sums to 100% and FLEX to 500%.
function annotate(players){
 if(!state.models)return players;
 for(const role of ['CPT','FLEX']){
  const model=state.models.ownership[role],rows=players.filter(p=>p.showdownRole===role&&finite(p.salary)&&!p.unavailable);
  if(!rows.length)continue;
  const ranked=rows.slice().sort((a,b)=>b.salary-a.salary||String(a.id).localeCompare(String(b.id)));
  const raw=new Map();let total=0;
  ranked.forEach((p,i)=>{const bin=Math.min(i,model.bins-1),value=model.table[group(p.position)][bin];raw.set(p,value);total+=value;});
  ranked.forEach((p,i)=>{p.fieldRank=i+1;p.fieldRankPct=(i+1)/ranked.length;p.ownership=total>0?Math.min(100,raw.get(p)*model.total/total):null;p.ownershipRole=role;});
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
  n_stars:flex.filter(p=>p.fieldRankPct<=.1).length+(captain.fieldRankPct<=.1?1:0),cpt_pos_QB:captain.position==='QB'?1:0,log_entries:Math.log(entries)};
}
// Expected number of identical lineups in the field (including this one) and a coarse band taken from the validation deciles.
function duplication(lineup,entries=30000){
 if(!state.models)return null;const spec=state.models.duplication,f=lineupFeatures(lineup,entries);if(!f)return null;
 const x=spec.features.map(name=>f[name]),z=zscore(x,spec),logDup=spec.intercept+z.reduce((s,v,i)=>s+v*spec.coef[i],0),copies=Math.exp(logDup+.5*spec.resid_sd**2);
 return {logDup,expectedCopies:copies,band:copies<3?'low':copies<8?'moderate':'high',entries,
  note:'Expected identical lineups in a field of this size, from salary structure and projected ownership. Validated as a ranking of lineups, not as an exact count.'};
}
function lineupOwnership(lineup){
 const captain=lineup.find(p=>p.slot==='CPT'||p.slot==='MVP'),flex=lineup.filter(p=>p!==captain);
 if(!captain||!lineup.every(p=>finite(p.ownership)))return null;
 return {captain:captain.ownership,flexTotal:flex.reduce((s,p)=>s+p.ownership,0),flexAverage:flex.reduce((s,p)=>s+p.ownership,0)/flex.length};
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
root.GoingDfsField={SCHEMA:'going-private-showdown-models-v1',WEIGHTS,load,clear,ready,annotate,lineupFeatures,duplication,lineupOwnership,objective,state};
if(typeof module!=='undefined')module.exports=root.GoingDfsField;
})(globalThis);
