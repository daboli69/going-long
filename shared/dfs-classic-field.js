(function(root){
'use strict';
// Classic (full-slate) ownership model. The code is public; the COEFFICIENTS are private (derived from the licensed stat-api contest archive) and are loaded by the user from
// their own disk in the browser: classic_ownership_model.json (schema going-private-classic-ownership-v1). Without the file nothing is estimated and nothing is shown.
// Production spec = salary_only: within each position, softmax over salary, salary^2 and the player's salary rank among same-position players, scaled so each position group
// matches the average number of roster slots it fills. Validated on 24 archived 2025-26 contests (fit on 42 earlier ones): MAE 3.0 percentage points, correlation .81,
// bias 0.0, 55% of the ten most-owned players found. The projection-based specs add little in replay and are not used.
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const state={model:null,fieldSq:null,poolRows:0};
const SCHEMA='going-private-classic-ownership-v1';
function load(json){
 let data=json;if(typeof json==='string'){try{data=JSON.parse(json);}catch{return {ok:false,reason:'The file is not valid JSON.'};}}
 if(!data||data.schema!==SCHEMA||!data.models?.salary_only||!data.slot_totals)return {ok:false,reason:'This is not a GOING private Classic ownership file.'};
 const spec=data.models.salary_only;
 const sound=Array.isArray(data.positions)&&data.positions.length>0&&data.positions.every(pos=>finite(data.slot_totals[pos])&&Array.isArray(spec[pos]?.features)&&Array.isArray(spec[pos]?.beta)&&spec[pos].features.length===spec[pos].beta.length&&spec[pos].beta.every(finite));
 if(!sound)return {ok:false,reason:'This Classic ownership file is incomplete (missing positions, features or coefficients).'};
 state.model=data;state.fieldSq=null;return {ok:true};
}
const clear=()=>{state.model=null;state.fieldSq=null;state.poolRows=0;};
const ready=()=>Boolean(state.model);
// Adds `ownership` (% of lineups holding the player) to each pool row (all positions the model covers). Rank is over every salaried row of the position, as in training.
function annotate(pool,key='salary_only'){
 const model=state.model;if(!model)return pool;
 const spec=model.models[key]||model.models.salary_only;
 for(const pos of model.positions){
  const group=pool.filter(p=>p.position===pos&&finite(p.salary)),cfg=spec[pos];
  if(!group.length||!cfg){group.forEach(p=>{p.ownership=null;});continue;}
  const eta=group.map(p=>{
   const s=(p.salary-5000)/1000,higher=group.filter(q=>q.salary>p.salary).length,f={s,s2:s*s,lrank:Math.log1p(higher)};
   return cfg.features.reduce((sum,name,i)=>sum+cfg.beta[i]*(f[name]??0),0);
  });
  const top=Math.max(...eta),e=eta.map(x=>Math.exp(x-top)),z=e.reduce((a,b)=>a+b,0);
  group.forEach((p,i)=>{p.ownership=Math.min(100,model.slot_totals[pos]*e[i]/z);p.ownershipSource='classic-salary-model';});
 }
 // Model-implied field-typical lineup sum: for a field of lineups, mean(sum of own_i over a lineup) = sum_i own_i^2 / 100 (an identity, verified on 73 archived contests to within 2%).
 const rows=pool.filter(p=>finite(p.ownership));state.fieldSq=rows.length?rows.reduce((s,p)=>s+p.ownership*p.ownership,0)/100:null;state.poolRows=rows.length;
 return pool;
}
// Optional private block (model.lineup_calibration, written by scripts/dfs_ownership_calibration.py): maps the model's lineup sum to the sum a real field lineup would have held.
// Fitted on earlier archived contests and scored on later ones; the salary model is right per player on average but shrunk toward the mean, so raw sums understate real ones.
function calibration(){const c=state.model?.lineup_calibration,p=c?.params;return c&&p&&[p.a,p.b,p.s].every(finite)&&Array.isArray(p.clamp)&&p.clamp.every(finite)&&Array.isArray(c.heldout?.realised_over_estimate_p10_p90)?c:null;}
function expectedSum(rawSum,sq){
 const c=calibration();if(!c||!finite(rawSum)||!finite(sq)||sq<=0)return null;
 const p=c.params,level=Math.exp(p.a)*sq**p.b,ratio=Math.min(p.clamp[1],Math.max(p.clamp[0],rawSum/sq)),mid=level*(1+p.s*(ratio-1)),[lo,hi]=c.heldout.realised_over_estimate_p10_p90;
 return {fieldTypical:level,expected:mid,low:mid*lo,high:mid*hi,heldout:c.heldout};
}
// SUM OF PLAYER OWNERSHIP over the 9 slots (percent points, not a probability and not a duplicate count), plus how many "chalk" players (model >= 15%) it holds.
// total/average are the RAW model sum (known to be low: field lineups held ~1.4x the model sum on held-out contests). `expected` is the calibrated estimate of the sum a real
// field lineup with these players would have held, present only when the private file carries lineup_calibration. Descriptive only: leverage is not shown to add ROI.
function lineupOwnership(lineup){
 if(!Array.isArray(lineup)||!lineup.length||!lineup.every(p=>finite(p.ownership)))return null;
 const total=lineup.reduce((s,p)=>s+p.ownership,0),out={total,average:total/lineup.length,chalk:lineup.filter(p=>p.ownership>=15).length,statistic:'sum of model player ownership (percent points)',fieldTypicalRaw:state.fieldSq};
 const cal=lineup.length===9?expectedSum(total,state.fieldSq):null;
 return cal?{...out,calibrated:true,...cal}:{...out,calibrated:false};
}
root.GoingDfsClassicField={SCHEMA,load,clear,ready,annotate,lineupOwnership,expectedSum,calibration,state};
if(typeof module!=='undefined')module.exports=root.GoingDfsClassicField;
})(globalThis);
