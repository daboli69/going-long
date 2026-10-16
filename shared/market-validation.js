/* Chronological, leakage-free validation tools for market-consensus and prop-calibration hypotheses.
 * Everything here operates on records the caller supplies; it never invents historical odds or outcomes.
 * A record's `t` is the decision timestamp (ms) and its probabilities must be the ones available at that time. */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const clip=p=>Math.min(1-1e-9,Math.max(1e-9,p));
const brier=(p,y)=>(p-y)**2,logLoss=(p,y)=>-(y?Math.log(clip(p)):Math.log(1-clip(p)));
const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:NaN;
function rng(seed){let a=seed>>>0;return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}

function calibrationBins(pairs,bins=10){
 const out=Array.from({length:bins},(_,i)=>({lo:i/bins,hi:(i+1)/bins,n:0,p:0,y:0}));
 for(const {p,y} of pairs){const b=out[Math.min(bins-1,Math.floor(p*bins))];b.n++;b.p+=p;b.y+=y;}
 return out.filter(b=>b.n).map(b=>({lo:b.lo,hi:b.hi,n:b.n,meanPredicted:b.p/b.n,observed:b.y/b.n}));
}
/* Cluster bootstrap of a paired per-record loss difference, resampling whole games (correlated records stay together). */
function clusterBootstrap(diffs,clusters,{iterations=2000,seed=1}={}){
 const groups=new Map();diffs.forEach((d,i)=>groups.set(clusters[i],[...(groups.get(clusters[i])||[]),d]));
 const list=[...groups.values()],r=rng(seed),est=[];
 for(let it=0;it<iterations;it++){let s=0,n=0;for(let k=0;k<list.length;k++){const g=list[Math.floor(r()*list.length)];for(const d of g){s+=d;n++;}}est.push(s/n);}
 est.sort((a,b)=>a-b);
 return {mean:mean(diffs),lo:est[Math.floor(.025*(est.length-1))],hi:est[Math.ceil(.975*(est.length-1))],clusters:list.length,n:diffs.length};
}

// ---- consensus pooling -------------------------------------------------------------------------------------------
/* Linear pool over the sources available in this record; missing sources are renormalized away. */
function pool(probs,weights){let s=0,w=0;for(const [k,p] of Object.entries(probs)){const x=weights[k]||0;if(x>0&&finite(p)){s+=x*p;w+=x;}}return w>0?s/w:null;}
/* Learns non-negative source weights (sum 1) minimizing log loss of the linear pool by exponentiated gradient.
 * Sources with few training records are shrunk toward the equal-weight prior (sample-size-aware reliability). */
function learnWeights(records,{sources,priorStrength=200,steps=500,rate=12}={}){
 const names=sources||[...new Set(records.flatMap(r=>Object.keys(r.probs)))];
 const count=Object.fromEntries(names.map(s=>[s,records.filter(r=>finite(r.probs[s])).length]));
 let w=Object.fromEntries(names.map(s=>[s,1/names.length]));
 if(!records.length)return {weights:w,counts:count,trained:0};
 for(let it=0;it<steps;it++){
  const g=Object.fromEntries(names.map(s=>[s,0]));
  for(const r of records){
   const p=clip(pool(r.probs,w)??.5),dl=r.y?-1/p:1/(1-p);
   let tot=0;for(const s of names)if(finite(r.probs[s]))tot+=w[s];
   if(!(tot>0))continue;
   // d pool / d w_s = (p_s - pool) / total weight present
   for(const s of names)if(finite(r.probs[s]))g[s]+=dl*(r.probs[s]-p)/tot;
  }
  let z=0;for(const s of names){w[s]*=Math.exp(-rate*g[s]/records.length);z+=w[s];}
  for(const s of names)w[s]/=z;
 }
 const raw={...w};
 for(const s of names){const a=count[s]/(count[s]+priorStrength);w[s]=a*raw[s]+(1-a)*(1/names.length);}
 const z=Object.values(w).reduce((a,b)=>a+b,0);for(const s of names)w[s]/=z;
 return {weights:w,counts:count,trained:records.length};
}
/* Expanding-window walk-forward. Each test fold is scored with weights learned only from strictly earlier records.
 * records: [{t,gameId,y(0/1),probs:{source:p},model?:p}] (pushes excluded by the caller). */
function walkForward(records,{research={},folds=4,minTrain=100,seed=7}={}){
 const sorted=[...records].sort((a,b)=>a.t-b.t),size=Math.floor(sorted.length/(folds+1));
 const res={equal:[],research:[],learned:[],model:[],games:[],weights:[]};
 if(size<1)return {ok:false,reason:'Too few records for chronological folds.'};
 const names=[...new Set(sorted.flatMap(r=>Object.keys(r.probs)))],equalW=Object.fromEntries(names.map(s=>[s,1]));
 for(let f=1;f<=folds;f++){
  const train=sorted.slice(0,f*size),test=sorted.slice(f*size,f===folds?sorted.length:(f+1)*size);
  // Records sharing a game with a training record that ends after the cut-off would leak; split on game boundaries.
  const cut=test[0]?.t,trainClean=train.filter(r=>r.t<cut);
  if(trainClean.length<minTrain)continue;
  const learned=learnWeights(trainClean,{sources:names});res.weights.push({fold:f,weights:learned.weights,trained:trainClean.length});
  for(const r of test){
   const e=pool(r.probs,equalW),rw=pool(r.probs,research),lw=pool(r.probs,learned.weights);
   if(e==null||lw==null)continue;
   res.equal.push([brier(e,r.y),logLoss(e,r.y)]);res.research.push([brier(rw??e,r.y),logLoss(rw??e,r.y)]);res.learned.push([brier(lw,r.y),logLoss(lw,r.y)]);
   if(finite(r.model))res.model.push([brier(r.model,r.y),logLoss(r.model,r.y)]);else res.model.push(null);
   res.games.push(r.gameId);
  }
 }
 if(!res.games.length)return {ok:false,reason:`No fold had ${minTrain}+ strictly earlier training records.`};
 const summarize=key=>{const rows=res[key];return {n:rows.filter(Boolean).length,brier:mean(rows.filter(Boolean).map(x=>x[0])),logLoss:mean(rows.filter(Boolean).map(x=>x[1]))};};
 const vs=(key,idx)=>{const d=[],c=[];res[key].forEach((x,i)=>{if(x){d.push(x[idx]-res.equal[i][idx]);c.push(res.games[i]);}});return d.length?clusterBootstrap(d,c,{seed}):null;};
 // A model's score is only meaningful against the market on the SAME records, so the matched subset is reported explicitly.
 const idx=res.model.map((x,i)=>x?i:-1).filter(i=>i>=0),sub=key=>({brier:mean(idx.map(i=>res[key][i][0])),logLoss:mean(idx.map(i=>res[key][i][1]))});
 const matched=idx.length?{n:idx.length,games:new Set(idx.map(i=>res.games[i])).size,equal:sub('equal'),model:sub('model')}:null;
 return {ok:true,n:res.games.length,matched,equal:summarize('equal'),research:summarize('research'),learned:summarize('learned'),model:summarize('model'),
  differencesVsEqual:{research:{brier:vs('research',0),logLoss:vs('research',1)},learned:{brier:vs('learned',0),logLoss:vs('learned',1)},model:{brier:vs('model',0),logLoss:vs('model',1)}},
  weights:res.weights,note:'Negative differences mean lower loss than equal weights. A 95% cluster-bootstrap interval that includes 0 is not evidence of improvement.'};
}

// ---- timestamped snapshots, CLV and price discovery ---------------------------------------------------------------
const BUCKETS=[['24h',24*3600e3,3*3600e3],['6h',6*3600e3,1*3600e3],['1h',3600e3,20*60e3],['close',0,10*60e3]];
/* Assigns a capture time to the nearest decision bucket for a kickoff, or null when it lies between buckets. */
function bucketFor(msToKick){for(const [name,center,tol] of BUCKETS)if(Math.abs(msToKick-center)<=tol)return name;return null;}
/* store: {contractKey: {bucket: {t, source: fairProbabilityOfSideA}}}; append-only per bucket (first capture wins). */
function recordSnapshot(store,contractKey,kickoffMs,t,sourceProbs){
 const b=bucketFor(kickoffMs-t);if(!b)return false;
 const slot=(store[contractKey]=store[contractKey]||{});if(slot[b])return false;
 slot[b]={t,probs:{...sourceProbs}};return true;
}
/* Closing-line value in price terms: how much better the bet price was than the fair closing price. Positive = beat the close. */
const clv=(betDecimal,closeFairProbability)=>finite(betDecimal)&&closeFairProbability>0&&closeFairProbability<1?betDecimal*closeFairProbability-1:null;
/* For each source: when it disagreed with the other sources at `from` by at least `delta`, how often and how far did the
 * leave-one-out consensus move toward it by `to`? Reported with counts; no verdict on predictive value. */
function priceDiscovery(store,{from='6h',to='close',delta=.01,weights=null}={}){
 const acc={};
 for(const slot of Object.values(store)){
  const a=slot[from],b=slot[to];if(!a||!b)continue;
  for(const [src,p] of Object.entries(a.probs)){
   const others=Object.entries(a.probs).filter(([s])=>s!==src),othersClose=Object.entries(b.probs).filter(([s])=>s!==src);
   if(others.length<2||othersClose.length<2)continue;
   const w=(s)=>weights?(weights[s]||0):1,avg=(list)=>{let t=0,s=0;for(const [k,x] of list){t+=w(k)*x;s+=w(k);}return s>0?t/s:null;};
   const c0=avg(others),c1=avg(othersClose);if(c0==null||c1==null)continue;
   const d=p-c0;if(Math.abs(d)<delta)continue;
   const move=(c1-c0)*Math.sign(d),frac=(c1-c0)/d;
   const r=acc[src]=acc[src]||{n:0,toward:0,fracSum:0};r.n++;if(move>0)r.toward++;r.fracSum+=Math.max(-1,Math.min(2,frac));
  }
 }
 return Object.fromEntries(Object.entries(acc).map(([s,r])=>[s,{disagreements:r.n,shareMovedToward:r.toward/r.n,meanConvergence:r.fracSum/r.n}]));
}

// ---- player-prop over/under calibration ----------------------------------------------------------------------------
/* records: {t,gameId,sport,category,book,side:'over'|'under',p (no-vig win prob given no push),result:'win'|'loss'|'push'}
 * Pushes are removed from the outcome (conditional on no push), matching how p is defined. */
function propGap(records,keys=['side']){
 const seg=new Map();
 for(const r of records){if(r.result==='push')continue;const k=keys.map(x=>r[x]).join('|'),s=seg.get(k)||{key:k,rows:[]};s.rows.push(r);seg.set(k,s);}
 return [...seg.values()].map(s=>{
  const y=s.rows.map(r=>r.result==='win'?1:0),p=s.rows.map(r=>r.p),gap=mean(y)-mean(p);
  const ci=clusterBootstrap(s.rows.map((r,i)=>y[i]-r.p),s.rows.map(r=>r.gameId),{iterations:1000});
  return {segment:s.key,n:s.rows.length,games:ci.clusters,meanImplied:mean(p),realized:mean(y),gap,ci:[ci.lo,ci.hi]};
 }).sort((a,b)=>b.n-a.n);
}
/* Fits a per-segment logit shift on earlier records (empirical-Bayes shrinkage by sample size), scores later records with and
 * without it, and approves a segment only when the out-of-sample log-loss improvement's interval excludes 0. */
function fitPropCorrection(records,{keys=['side'],holdout=.3,k=300,seed=3}={}){
 const sorted=[...records].filter(r=>r.result!=='push').sort((a,b)=>a.t-b.t),cut=Math.floor(sorted.length*(1-holdout));
 if(cut<50||sorted.length-cut<50)return {ok:false,reason:'Too few non-push records for a chronological holdout.'};
 const cutT=sorted[cut].t,train=sorted.filter(r=>r.t<cutT),test=sorted.filter(r=>r.t>=cutT);
 const logit=p=>Math.log(clip(p)/(1-clip(p))),inv=x=>1/(1+Math.exp(-x));
 const shifts=new Map();
 for(const g of propGap(train,keys)){const rows=train.filter(r=>keys.map(x=>r[x]).join('|')===g.segment),y=mean(rows.map(r=>r.result==='win'?1:0));
  shifts.set(g.segment,(g.n/(g.n+k))*(logit(clip(y))-logit(clip(g.meanImplied))));}
 const out=[];
 for(const [segment,shift] of shifts){
  const rows=test.filter(r=>keys.map(x=>r[x]).join('|')===segment);if(rows.length<20)continue;
  const d=rows.map(r=>{const y=r.result==='win'?1:0;return logLoss(inv(logit(r.p)+shift),y)-logLoss(r.p,y);});
  const ci=clusterBootstrap(d,rows.map(r=>r.gameId),{iterations:1000,seed});
  out.push({segment,shiftLogit:shift,trainN:train.filter(r=>keys.map(x=>r[x]).join('|')===segment).length,testN:rows.length,logLossChange:ci.mean,ci:[ci.lo,ci.hi],deploy:ci.hi<0});
 }
 return {ok:true,trainN:train.length,testN:test.length,segments:out,note:'deploy is true only when the out-of-sample log-loss change interval is entirely below 0. No fixed over discount is applied.'};
}

const api={brier,logLoss,calibrationBins,clusterBootstrap,pool,learnWeights,walkForward,bucketFor,recordSnapshot,clv,priceDiscovery,propGap,fitPropCorrection,BUCKETS};
root.GoingMarketValidation=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
