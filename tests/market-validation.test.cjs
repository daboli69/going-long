const {test}=require('node:test'),assert=require('node:assert/strict');
const V=require('../shared/market-validation.js');
function rng(a){return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const inv=x=>1/(1+Math.exp(-x)),logit=p=>Math.log(p/(1-p));
// Synthetic market: source "sharp" sees the truth with small noise; "soft" sees it with large noise. Clearly synthetic.
function synth(n,seed,{softNoise=.9,sharpNoise=.15}={}){
 const r=rng(seed),g=()=>{let u=0;while(!u)u=r();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*r());},rows=[];
 for(let i=0;i<n;i++){const truth=inv(g()*.8),y=r()<truth?1:0;
  rows.push({t:i*1000,gameId:'g'+Math.floor(i/2),y,probs:{sharp:inv(logit(truth)+sharpNoise*g()),soft:inv(logit(truth)+softNoise*g())}});}
 return rows;
}
test('scoring rules and calibration bins',()=>{
 assert.ok(Math.abs(V.brier(.8,1)-.04)<1e-12);assert.ok(Math.abs(V.logLoss(.5,1)-Math.log(2))<1e-12);
 const bins=V.calibrationBins([{p:.1,y:0},{p:.12,y:0},{p:.9,y:1},{p:.95,y:0}],2);
 assert.equal(bins.length,2);assert.equal(bins[1].observed,.5);assert.equal(bins[0].n,2);
});
test('pooling renormalizes over the sources present in each record',()=>{
 assert.equal(V.pool({a:.6,b:.4},{a:1,b:1}),.5);assert.equal(V.pool({a:.6},{a:1,b:1}),.6);assert.equal(V.pool({a:.6},{b:1}),null);
});
test('learned weights favour the informative source and are shrunk when training data is scarce',()=>{
 const rows=synth(3000,4),w=V.learnWeights(rows,{priorStrength:50}).weights;
 assert.ok(w.sharp>w.soft+.2,JSON.stringify(w));
 const tiny=V.learnWeights(rows.slice(0,20),{priorStrength:2000}).weights;assert.ok(Math.abs(tiny.sharp-.5)<.05);
});
test('walk-forward uses only earlier data: learned beats equal out of sample when one source is better, and wrong research weights lose',()=>{
 const rows=synth(4000,9),wf=V.walkForward(rows,{research:{sharp:.1,soft:7.5},folds:4,minTrain:200});
 assert.ok(wf.ok);assert.ok(wf.learned.logLoss<wf.equal.logLoss);assert.ok(wf.research.logLoss>wf.equal.logLoss);
 assert.ok(wf.differencesVsEqual.learned.logLoss.hi<0,'interval excludes zero');assert.ok(wf.differencesVsEqual.research.logLoss.lo>0);
 assert.ok(wf.weights.every(f=>f.trained>=200));
});
test('walk-forward never trains on or after a test record, and equal-quality sources show no significant gain',()=>{
 const rows=synth(3000,3,{softNoise:.15,sharpNoise:.15}),wf=V.walkForward(rows,{research:{sharp:1,soft:1},folds:3});
 assert.ok(wf.differencesVsEqual.learned.logLoss.lo<=0&&wf.differencesVsEqual.learned.logLoss.hi>=0,'no spurious improvement');
 assert.equal(V.walkForward(rows.slice(0,3),{folds:4}).ok,false);
 const shuffled=[...rows].reverse();assert.deepEqual(V.walkForward(shuffled,{research:{sharp:1,soft:1},folds:3}).equal,wf.equal);
});
test('snapshot buckets, first-capture-wins and closing-line value',()=>{
 const h=3600e3;assert.equal(V.bucketFor(24*h+60e3),'24h');assert.equal(V.bucketFor(6*h-30*60e3),'6h');assert.equal(V.bucketFor(h),'1h');assert.equal(V.bucketFor(5*60e3),'close');assert.equal(V.bucketFor(12*h),null);
 const store={},kick=1e12;assert.equal(V.recordSnapshot(store,'c',kick,kick-6*h,{a:.5}),true);assert.equal(V.recordSnapshot(store,'c',kick,kick-6*h+60e3,{a:.9}),false);assert.equal(store.c['6h'].probs.a,.5);
 assert.equal(V.recordSnapshot(store,'c',kick,kick-12*h,{a:.5}),false);
 assert.ok(Math.abs(V.clv(2.1,.5)-.05)<1e-12);assert.equal(V.clv(2.1,0),null);
});
test('price discovery counts how often and how far consensus moved toward a disagreeing source',()=>{
 const store={};
 for(let i=0;i<10;i++)store['c'+i]={'6h':{t:0,probs:{lead:.55,x:.50,y:.50,z:.50}},close:{t:1,probs:{lead:.55,x:.54,y:.54,z:.54}}};
 store.n={'6h':{t:0,probs:{lead:.55,x:.5,y:.5,z:.5}},close:{t:1,probs:{lead:.55,x:.5,y:.5,z:.5}}};
 const r=V.priceDiscovery(store,{delta:.02});
 assert.equal(r.lead.disagreements,11);assert.ok(Math.abs(r.lead.shareMovedToward-10/11)<1e-9);assert.ok(r.lead.meanConvergence>.7);
 assert.equal(r.x?.disagreements??0,0);
});
function props(n,{overTax=0.0,seed=2}={}){
 const r=rng(seed),rows=[];
 for(let i=0;i<n;i++){const over=i%2===0,p=.4+.2*r(),pTrue=over?inv(logit(p)-overTax):p,x=r(),res=x<.03?'push':r()<pTrue?'win':'loss';
  rows.push({t:i,gameId:'g'+Math.floor(i/4),sport:'nfl',category:'rec_yds',book:'dk',side:over?'over':'under',p,result:res});}
 return rows;
}
test('prop gap excludes pushes and reports uncertainty by segment',()=>{
 const gaps=V.propGap(props(4000,{overTax:.15}),['side']),over=gaps.find(g=>g.segment==='over'),under=gaps.find(g=>g.segment==='under');
 assert.ok(over.gap<-.015&&over.ci[1]<0);assert.ok(Math.abs(under.gap)<.03);assert.ok(over.games<over.n);
 assert.ok(over.n<2000,'pushes removed from the denominator');
});
test('over correction deploys only when out-of-sample log loss improves; no fixed discount otherwise',()=>{
 const taxed=V.fitPropCorrection(props(30000,{overTax:.3}),{keys:['side']}),over=taxed.segments.find(s=>s.segment==='over');
 assert.ok(taxed.ok&&over.deploy&&over.shiftLogit<0&&over.ci[1]<0);
 const fair=V.fitPropCorrection(props(30000,{overTax:0,seed:5}),{keys:['side']});
 assert.ok(fair.segments.every(s=>!s.deploy),JSON.stringify(fair.segments));
 assert.equal(V.fitPropCorrection(props(40),{}).ok,false);
});
