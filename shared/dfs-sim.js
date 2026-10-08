(function(root){
'use strict';
// DFS simulator: player point distributions from the same stat models the betting side uses, joined by MEASURED correlations
// (data/dfs_correlations.json -> shared/dfs-correlations.js; research experiments P3-8 and P3-9). It forecasts the spread of next-game core DraftKings points
// (modelled components plus yardage bonuses). It does not know salaries, ownership or the contest field, so it says nothing about tournament value by itself.
const SOURCE='dfs-sim-v1';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const COMPONENTS={QB:['pass_yds','pass_tds','rush_yds','rush_tds'],RB:['rush_yds','rush_tds','receptions','rec_yds','rec_tds'],WR:['receptions','rec_yds','rec_tds'],TE:['receptions','rec_yds','rec_tds']};
const BONUS={pass_yds:300,rush_yds:100,rec_yds:100};
const QUANTILES={floor:.1,p25:.25,median:.5,p75:.75,p90:.9,p95:.95};

function normalCDF(z){
 if(z===Infinity)return 1;if(z===-Infinity)return 0;
 const x=Math.abs(z)/Math.SQRT2,t=1/(1+0.3275911*x);
 const erf=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-x*x);
 return .5*(1+(z<0?-erf:erf));
}
// Acklam's rational approximation of the inverse normal CDF (relative error < 1.2e-9).
function normalPpf(p){
 if(!(p>0&&p<1))return p<=0?-Infinity:Infinity;
 const a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00],
  b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01],
  c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00],
  d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00],low=.02425;
 let q,r;
 if(p<low){q=Math.sqrt(-2*Math.log(p));return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
 if(p>1-low){q=Math.sqrt(-2*Math.log(1-p));return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
 q=p-.5;r=q*q;
 return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
}
function hashSeed(text){let h=2166136261;for(const ch of String(text)){h^=ch.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}
function rng(seed){let a=seed>>>0;return ()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return ((t^t>>>14)>>>0)/4294967296;};}
function gaussian(random){let u=0,v=0;while(u===0)u=random();while(v===0)v=random();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);}

function cholesky(matrix){
 // Shrink off-diagonals until the matrix is positive definite: measured pairwise correlations need not be jointly consistent.
 let shrink=1;
 for(let attempt=0;attempt<40;attempt++,shrink*=.92){
  const n=matrix.length,L=Array.from({length:n},()=>new Array(n).fill(0));let ok=true;
  const m=matrix.map((row,i)=>row.map((value,j)=>i===j?1:value*shrink));
  for(let i=0;i<n&&ok;i++)for(let j=0;j<=i;j++){
   let sum=m[i][j];for(let k=0;k<j;k++)sum-=L[i][k]*L[j][k];
   if(i===j){if(sum<=1e-9){ok=false;break;}L[i][j]=Math.sqrt(sum);}else L[i][j]=sum/L[j][j];
  }
  if(ok)return {L,shrink};
 }
 const n=matrix.length;return {L:Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>i===j?1:0)),shrink:0};
}

// Inverse CDF of a stat model at probability u (rows of the betting stat models: poisson lambda, or lognormal with an empirical nonpositive mass).
function ppfModel(model,u){
 if(!model||model.status!=='ready')return 0;
 if(model.family==='poisson'){
  const lambda=Math.max(0,model.lambda??model.mean??0);if(lambda<=1e-9)return 0;
  let k=0,term=Math.exp(-lambda),cdf=term;
  if(lambda>600)return Math.max(0,Math.round(lambda+Math.sqrt(lambda)*normalPpf(u)));
  while(cdf<u&&k<2000){k++;term*=lambda/k;cdf+=term;}
  return k;
 }
 if(model.family==='lognormal'){
  const mass=model.nonpositive||[],weights=model.nonpositive_weights||mass.map(()=>1/(model.n||mass.length||1)),total=weights.reduce((s,w)=>s+w,0);
  if(mass.length&&u<=total){
   const order=mass.map((value,index)=>[value,weights[index]]).sort((a,b)=>a[0]-b[0]);let run=0;
   for(const [value,weight] of order){run+=weight;if(u<=run)return value;}
   return order[order.length-1][0];
  }
  const weight=model.positive_weight??1;
  if(!(weight>0)||!finite(model.mu_log)||!finite(model.sigma_log))return 0;
  const inner=Math.min(1-1e-12,Math.max(1e-12,(u-total)/Math.max(1-total,1e-12)));
  return Math.max(0,Math.round(Math.exp(model.mu_log+model.sigma_log*normalPpf(inner))));
 }
 return 0;
}

function score(components,site='draftkings'){
 const get=key=>finite(components[key])?components[key]:0,reception=site==='fanduel'?.5:1;
 let points=.04*get('pass_yds')+4*get('pass_tds')+.1*(get('rush_yds')+get('rec_yds'))+6*(get('rush_tds')+get('rec_tds'))+reception*get('receptions');
 if(site==='draftkings')for(const [key,threshold] of Object.entries(BONUS))if(get(key)>=threshold)points+=3;
 return points;
}

function withinMatrix(position,present,correlations){
 const spec=correlations?.within_player?.[position];if(!spec)return present.map((_,i)=>present.map((__,j)=>i===j?1:0));
 const index=Object.fromEntries(spec.components.map((key,i)=>[key,i]));
 return present.map(a=>present.map(b=>a===b?1:(index[a]!==undefined&&index[b]!==undefined?spec.matrix[index[a]][index[b]]:0)));
}
function summarize(sorted){
 const n=sorted.length,mean=sorted.reduce((s,v)=>s+v,0)/n,variance=sorted.reduce((s,v)=>s+(v-mean)**2,0)/(n-1||1),at=q=>sorted[Math.min(n-1,Math.max(0,Math.ceil(q*n)-1))];
 const out={mean,sd:Math.sqrt(variance),n};for(const [name,q] of Object.entries(QUANTILES))out[name]=at(q);return out;
}
// Distribution of one player's core points. `models` maps stat key -> betting stat model (attachProjection().model).
function player(models,position,{draws=1000,site='draftkings',seed,correlations=root.GoingDfsCorrelations,id='',independent=false}={}){
 const wanted=COMPONENTS[position];if(!wanted)return null;
 const present=wanted.filter(key=>models?.[key]&&models[key].status==='ready');
 if(!present.length)return null;
 const R=independent?present.map((_,i)=>present.map((__,j)=>i===j?1:0)):withinMatrix(position,present,correlations),{L}=cholesky(R),random=rng(seed??hashSeed('player|'+id+'|'+position));
 const values=new Float64Array(draws);
 for(let d=0;d<draws;d++){
  const z=present.map(()=>gaussian(random)),correlated=L.map(row=>row.reduce((sum,w,k)=>sum+w*z[k],0)),components={};
  present.forEach((key,i)=>{components[key]=ppfModel(models[key],normalCDF(correlated[i]));});
  values[d]=score(components,site);
 }
 const sorted=Float64Array.from(values).sort();
 const summary=summarize(sorted),mean=summary.mean;
 // the sorted draws stay available to the lineup simulator but are not enumerable, so copies and JSON keep only the summary
 const out={...summary,boom:sorted.filter(v=>v>=Math.max(20,1.6*mean)).length/draws,bust:sorted.filter(v=>v<=.5*mean).length/draws,components:present,source:SOURCE,site,
  definitions:{boom:'share of simulated outcomes at or above max(20, 1.6 x projection)',bust:'share at or below half the projection',floor:'10th percentile'}};
 Object.defineProperty(out,'sorted',{value:sorted,enumerable:false});
 return out;
}

// Pair correlation between two players. Same team: role pair; opposing teams: role vs opponent role. Unmeasured pairs are treated as independent.
function pairCorrelation(a,b,correlations=root.GoingDfsCorrelations){
 if(!a.dfsRole||!b.dfsRole||!correlations?.cross_player)return 0;
 const table=correlations.cross_player,get=key=>table[key]?.r;
 if(a.team===b.team){const keys=[[a.dfsRole,b.dfsRole],[b.dfsRole,a.dfsRole]].map(([x,y])=>x+'~'+y);return get(keys[0])??get(keys[1])??0;}
 if(a.opponent&&a.opponent===b.team){
  const direct=get(a.dfsRole+'~opp_'+b.dfsRole),reverse=get(b.dfsRole+'~opp_'+a.dfsRole),found=[direct,reverse].filter(finite);
  return found.length?found.reduce((s,v)=>s+v,0)/found.length:0;
 }
 return 0;
}
// Roles from the pool itself: QB, RB1, WR1-3, TE1 by projection within team and position (the research assigned roles by pre-game targets / carries).
function assignRoles(players){
 const byTeam=new Map();
 for(const p of players){if(!p.team)continue;const key=p.team+'|'+p.position;if(!byTeam.has(key))byTeam.set(key,[]);byTeam.get(key).push(p);}
 for(const rows of byTeam.values()){
  rows.sort((x,y)=>(y.projection||0)-(x.projection||0));
  rows.forEach((p,i)=>{const pos=p.position;p.dfsRole=pos==='QB'?(i===0?'QB':null):pos==='RB'?(i===0?'RB1':null):pos==='WR'?(i<3?'WR'+(i+1):null):pos==='TE'?(i===0?'TE1':null):null;});
 }
 return players;
}
// Analytic moments of a lineup total with the measured correlations (multipliers apply to CPT/MVP).
function lineupMoments(lineup,{correlations=root.GoingDfsCorrelations}={}){
 let mean=0,variance=0;
 for(const p of lineup){const m=p.multiplier||1,sd=finite(p.distribution?.sd)?p.distribution.sd:(finite(p.sd)?p.sd:0);mean+=m*(p.distribution?.mean??p.projection??0);variance+=(m*sd)**2;}
 for(let i=0;i<lineup.length;i++)for(let j=i+1;j<lineup.length;j++){
  const a=lineup[i],b=lineup[j],r=pairCorrelation(a,b,correlations);if(!r)continue;
  const sa=finite(a.distribution?.sd)?a.distribution.sd:(a.sd||0),sb=finite(b.distribution?.sd)?b.distribution.sd:(b.sd||0);
  variance+=2*r*(a.multiplier||1)*sa*(b.multiplier||1)*sb;
 }
 return {mean,sd:Math.sqrt(Math.max(0,variance))};
}
// Monte Carlo lineup total with a Gaussian copula over the players (each mapped through his own simulated distribution).
function lineupDistribution(lineup,{draws=2000,correlations=root.GoingDfsCorrelations,seed=1,independent=false}={}){
 const usable=lineup.filter(p=>p.distribution?.sorted);if(usable.length!==lineup.length)return null;
 const n=lineup.length,R=lineup.map((a,i)=>lineup.map((b,j)=>i===j?1:(independent?0:pairCorrelation(a,b,correlations)))),{L,shrink}=cholesky(R),random=rng(seed>>>0),totals=new Float64Array(draws);
 for(let d=0;d<draws;d++){
  const z=lineup.map(()=>gaussian(random));let total=0;
  for(let i=0;i<n;i++){
   let s=0;for(let k=0;k<=i;k++)s+=L[i][k]*z[k];
   const sorted=lineup[i].distribution.sorted,index=Math.min(sorted.length-1,Math.floor(normalCDF(s)*sorted.length));
   total+=(lineup[i].multiplier||1)*sorted[index];
  }
  totals[d]=total;
 }
 const sorted=Float64Array.from(totals).sort(),summary=summarize(sorted),out={...summary,shrink,source:SOURCE,independent};
 Object.defineProperty(out,'sorted',{value:sorted,enumerable:false});
 return out;
}
function probabilityAtLeast(distribution,threshold){if(!distribution?.sorted)return null;let lo=0,hi=distribution.sorted.length;while(lo<hi){const mid=(lo+hi)>>1;if(distribution.sorted[mid]<threshold)lo=mid+1;else hi=mid;}return (distribution.sorted.length-lo)/distribution.sorted.length;}

root.GoingDfsSim={SOURCE,COMPONENTS,normalCDF,normalPpf,ppfModel,score,player,pairCorrelation,assignRoles,lineupMoments,lineupDistribution,probabilityAtLeast,cholesky,hashSeed};
if(typeof module!=='undefined')module.exports=root.GoingDfsSim;
})(globalThis);
