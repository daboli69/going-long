// Shadow-only logistic recalibration. Actual settled records; no live retuning.
import {modelCohort} from '../shared/model-cohort.mjs';
const finite=Number.isFinite,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const logit=p=>Math.log(clamp(p,.001,.999)/(1-clamp(p,.001,.999)));
const sigmoid=x=>1/(1+Math.exp(-clamp(x,-30,30)));
export const gameKey=p=>[p.sport,String(p.home).toLowerCase(),String(p.away).toLowerCase(),new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(new Date(p.kickoff))].join('|');
export const familyKey=p=>[modelCohort(p),p.sport,p.market].join('|');
export function conditionalProbability(p){const push=p.model_evidence?.push||0;return finite(p.probability)&&push>=0&&push<1?p.probability/(1-push):null;}
export function calibrationRows(records){
 const outcomes=new Map(records.filter(r=>r.kind==='settlement').map(r=>[r.payload.prediction_id,r.payload]));
 const seen=new Set(),rows=[];
 for(const {payload:p} of records.filter(r=>r.kind==='prediction'&&r.payload?.tracking_group==='best_model').sort((a,b)=>Date.parse(a.payload.observed_at)-Date.parse(b.payload.observed_at))){
  const key=[modelCohort(p),p.canonical_contract||p.selection].join('|'),s=outcomes.get(p.id),prob=conditionalProbability(p);
  if(seen.has(key)||!(Date.parse(p.observed_at)<Date.parse(p.kickoff)))continue;seen.add(key);
  if(!s||s.method!=='published_full_game_result'||!['win','loss'].includes(s.status)||!(Date.parse(s.observed_at)>Date.parse(p.kickoff))||!finite(prob)||prob<0||prob>1)continue;
  const ref=p.model_evidence?.reference;
  const market=finite(ref?.win)&&finite(ref?.loss)&&ref.win+ref.loss>0?ref.win/(ref.win+ref.loss):null;
  rows.push({p,prob,y:s.status==='win'?1:0,available:Date.parse(s.observed_at),at:Date.parse(p.observed_at),game:gameKey(p),family:familyKey(p),market});
 }return rows;
}
export function fitCalibration(rows){
 const games=new Map();for(const r of rows)games.set(r.game,(games.get(r.game)||0)+1);
 if(games.size<10)return null;
 // Each game has equal total influence; ridge prior favors unchanged predictions.
 let a=0,b=1;
 for(let i=0;i<25;i++){
  let ga=5*a,gb=5*(b-1),aa=5,ab=0,bb=5;
  for(const r of rows){const x=logit(r.prob),w=1/games.get(r.game),p=sigmoid(a+b*x),d=w*p*(1-p);ga+=w*(p-r.y);gb+=w*(p-r.y)*x;aa+=d;ab+=d*x;bb+=d*x*x;}
  const det=aa*bb-ab*ab,da=(bb*ga-ab*gb)/det,db=(aa*gb-ab*ga)/det;
  a=clamp(a-da,-2,2);b=clamp(b-db,0,1);if(Math.abs(da)+Math.abs(db)<1e-6)break;
 }
 return {intercept:a,slope:b,training_games:games.size,training_contracts:rows.length,trained_through:new Date(Math.max(...rows.map(r=>r.available))).toISOString()};
}
export const calibrated=(prob,fit)=>fit?sigmoid(fit.intercept+fit.slope*logit(prob)):null;
export function shadowPrediction(p,rows){
 const at=Date.parse(p.observed_at),eligible=rows.filter(r=>r.family===familyKey(p)&&r.available<at&&r.game!==gameKey(p)),fit=fitCalibration(eligible),prob=conditionalProbability(p);
 return fit&&finite(prob)?{status:'shadow_only',conditional_probability:calibrated(prob,fit),...fit,method:'game-balanced ridge logistic; earlier published outcomes only'}:null;
}
export function calibrationAudit(records,now){
 const rows=calibrationRows(records),groups=new Map();
 for(const r of rows){const shadow=shadowPrediction(r.p,rows),g=groups.get(r.family)||{cohort:modelCohort(r.p),sport:r.p.sport,market:r.p.market,rows:[],holdout:[]};g.rows.push(r);if(shadow)g.holdout.push({...r,shadow:shadow.conditional_probability});groups.set(r.family,g);}
 return {generated_at:now,status:'shadow_only',live_adjustment:false,method:'Chronological replay, trained strictly before each original forecast; equal game weights, no cross-cohort training.',
  promotion_rule:'No automatic promotion. Require prospective same-cohort evidence across later weeks, game-cluster uncertainty and a same-book devigged benchmark.',
  families:[...groups.values()].map(g=>{const mean=(a,fn)=>a.length?a.reduce((s,r)=>s+fn(r),0)/a.length:null,paired=g.holdout.filter(r=>finite(r.market));return {cohort:g.cohort,sport:g.sport,market:g.market,contracts:g.rows.length,games:new Set(g.rows.map(r=>r.game)).size,
   predicted:mean(g.rows,r=>r.prob),observed:mean(g.rows,r=>r.y),holdout_contracts:g.holdout.length,holdout_games:new Set(g.holdout.map(r=>r.game)).size,
   raw_brier:mean(g.holdout,r=>(r.prob-r.y)**2),shadow_brier:mean(g.holdout,r=>(r.shadow-r.y)**2),paired_market_contracts:paired.length,
   devigged_market_brier:mean(paired,r=>(r.market-r.y)**2),paired_raw_brier:mean(paired,r=>(r.prob-r.y)**2),paired_shadow_brier:mean(paired,r=>(r.shadow-r.y)**2),status:'research_only'};})};
}

export function workloadAudit(records){
 const columns={player_passing_yards:'attempts',player_rushing_yards:'carries',player_receiving_yards:'targets',player_receptions:'targets'},outcomes=new Map(records.filter(r=>r.kind==='settlement').map(r=>[r.payload.prediction_id,r.payload])),groups=new Map(),seen=new Set();
 for(const {payload:p} of records.filter(r=>r.kind==='prediction').sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at))){
  const key=familyKey(p)+'|'+p.side,contract=key+'|'+(p.canonical_contract||p.selection);if(seen.has(contract)||!(Date.parse(p.observed_at)<Date.parse(p.kickoff)))continue;seen.add(contract);
  const s=outcomes.get(p.id),column=columns[p.market],expected=p.model_evidence?.workload?.[column]?.mean,actual=s?.actual_workload?.[column],projection=p.model_evidence?.projection_mean;
  if(!s||!['win','loss','refund'].includes(s.status)||!column||!finite(expected)||expected<=0||!finite(actual)||actual<=0||!finite(projection)||!finite(s.actual))continue;
  const efficiency=projection/expected,actualEfficiency=s.actual/actual,row=groups.get(key)||{cohort:modelCohort(p),market:p.market,side:p.side,contracts:0,volume_error:0,efficiency_error:0,projection_error:0};
  row.contracts++;row.volume_error+=(expected-actual)*efficiency;row.efficiency_error+=actual*(efficiency-actualEfficiency);row.projection_error+=projection-s.actual;groups.set(key,row);
 }
 return {status:'prospective_only',method:'Algebraic error attribution using frozen opportunity counts; positive error means overprojection, not a causal explanation. Missing/zero opportunity denominators are excluded.',families:[...groups.values()].map(g=>({...g,volume_error:g.volume_error/g.contracts,efficiency_error:g.efficiency_error/g.contracts,projection_error:g.projection_error/g.contracts}))};
}
