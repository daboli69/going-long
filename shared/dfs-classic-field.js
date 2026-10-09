(function(root){
'use strict';
// Classic (full-slate) ownership model. The code is public; the COEFFICIENTS are private (derived from the licensed stat-api contest archive) and are loaded by the user from
// their own disk in the browser: classic_ownership_model.json (schema going-private-classic-ownership-v1). Without the file nothing is estimated and nothing is shown.
// Production spec = salary_only: within each position, softmax over salary, salary^2 and the player's salary rank among same-position players, scaled so each position group
// matches the average number of roster slots it fills. Validated on 24 archived 2025-26 contests (fit on 42 earlier ones): MAE 3.0 percentage points, correlation .81,
// bias 0.0, 55% of the ten most-owned players found. The projection-based specs add little in replay and are not used.
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const state={model:null};
const SCHEMA='going-private-classic-ownership-v1';
function load(json){
 let data=json;if(typeof json==='string'){try{data=JSON.parse(json);}catch{return {ok:false,reason:'The file is not valid JSON.'};}}
 if(!data||data.schema!==SCHEMA||!data.models?.salary_only||!data.slot_totals)return {ok:false,reason:'This is not a GOING private Classic ownership file.'};
 const spec=data.models.salary_only;
 const sound=Array.isArray(data.positions)&&data.positions.length>0&&data.positions.every(pos=>finite(data.slot_totals[pos])&&Array.isArray(spec[pos]?.features)&&Array.isArray(spec[pos]?.beta)&&spec[pos].features.length===spec[pos].beta.length&&spec[pos].beta.every(finite));
 if(!sound)return {ok:false,reason:'This Classic ownership file is incomplete (missing positions, features or coefficients).'};
 state.model=data;return {ok:true};
}
const clear=()=>{state.model=null;};
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
 return pool;
}
// Sum of projected ownership over a lineup and how many "chalk" players (projected >= 15%) it holds. Descriptive only: leverage is not shown to add ROI.
function lineupOwnership(lineup){
 if(!lineup.every(p=>finite(p.ownership)))return null;
 return {total:lineup.reduce((s,p)=>s+p.ownership,0),average:lineup.reduce((s,p)=>s+p.ownership,0)/lineup.length,chalk:lineup.filter(p=>p.ownership>=15).length};
}
root.GoingDfsClassicField={SCHEMA,load,clear,ready,annotate,lineupOwnership,state};
if(typeof module!=='undefined')module.exports=root.GoingDfsClassicField;
})(globalThis);
