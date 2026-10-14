/* Reproducible bankroll Monte Carlo for GOING Missions.
 * - Seeded; common random numbers: every strategy sees the same leg outcomes in the same run, so comparisons are paired.
 * - Joint outcomes: legs load on a per-event latent factor (Gaussian copula); loading 0 means independent.
 * - Probability uncertainty: a run-level systematic error (persists across weekends) plus a per-leg per-weekend error,
 *   both in logit space, so strategies are not optimized against unrealistically precise probabilities.
 * - Pushes void a parlay leg (remaining legs' posted prices multiply); fully pushed tickets refund.
 * The template of opportunities is reused for every simulated weekend: that is an assumption, not a forecast of future edges. */
(function(root){
'use strict';
const S=root.GoingSharpConsensus||(typeof require!=='undefined'?require('./sharp-consensus.js'):null);
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const logit=p=>Math.log(p/(1-p)),invLogit=x=>1/(1+Math.exp(-x));

function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const mix=h=>{h=Math.imul(h^h>>>16,0x85EBCA6B);h=Math.imul(h^h>>>13,0xC2B2AE35);return(h^h>>>16)>>>0;};
// Seed and run index are hashed separately and then combined, so different seeds never reuse the same set of run streams.
function runSeed(seed,run){return mix((mix((Number(seed)>>>0)+0x9E3779B9)+Math.imul(run+1,0x7F4A7C15))>>>0);}
function gauss(r){let u=0;while(u===0)u=r();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*r());}

const DEFAULTS={bankroll:50,target:150,withdrawTarget:100,reserve:50,weeks:1,maxExposure:.6,minStake:1,runs:20000,seed:20261014,
 sigmaLeg:.1,sigmaSystematic:.05,probShift:0,withdraw:true,marks:[4,8,12],preserveLevel:null};

function validateConfig(c){
 const o={...DEFAULTS,...c};
 const bad=[];
 if(!(o.bankroll>0))bad.push('bankroll');if(!(o.target>o.bankroll))bad.push('target must exceed bankroll');
 if(!(o.reserve>=0&&o.reserve<=o.target))bad.push('reserve');if(!(o.withdrawTarget>=0))bad.push('withdrawTarget');
 if(!Number.isInteger(o.weeks)||o.weeks<1||o.weeks>52)bad.push('weeks (1-52)');
 if(!(o.maxExposure>0&&o.maxExposure<=1))bad.push('maxExposure (0-1]');
 if(!Number.isInteger(o.runs)||o.runs<100||o.runs>200000)bad.push('runs (100-200000)');
 if(!(o.sigmaLeg>=0&&o.sigmaSystematic>=0))bad.push('sigma');
 if(bad.length)throw new Error('Invalid mission settings: '+bad.join(', '));
 return o;
}
const pct=(arr,q)=>{const a=Float64Array.from(arr).sort();return a.length?a[Math.min(a.length-1,Math.max(0,Math.floor(q*(a.length-1)+.5)))]:NaN;};
const se=(p,n)=>Math.sqrt(Math.max(0,p*(1-p))/n);
const round2=x=>Math.round(x*100)/100;

/* pool: [{id,eventId,p (win prob given no push),push,loading,dec}]
 * strategies: [{id,name,tickets:[{id,legIds:[...],decs:[...],weight}]}]; weights are normalized per strategy. */
function simulate({pool,strategies,config}){
 const c=validateConfig(config),legs=[...pool].sort((a,b)=>a.id<b.id?-1:1),events=[...new Set(legs.map(l=>l.eventId))].sort();
 const legIndex=new Map(legs.map((l,i)=>[l.id,i])),eventIndex=new Map(events.map((e,i)=>[e,i]));
 for(const l of legs){if(!(l.p>0&&l.p<1))throw new Error('Leg probability out of range: '+l.id);if(!(Math.abs(l.loading||0)<1))throw new Error('Leg loading must be in (-1,1): '+l.id);}
 const total=Math.max(12,c.weeks,...c.marks),preserve=c.preserveLevel??c.reserve;
 const plan=strategies.map(s=>{
  const wsum=s.tickets.reduce((a,t)=>a+t.weight,0);
  return {id:s.id,name:s.name,tickets:s.tickets.map(t=>({id:t.id,idx:t.legIds.map(id=>{if(!legIndex.has(id))throw new Error('Unknown leg '+id);return legIndex.get(id);}),decs:t.decs,w:wsum>0?t.weight/wsum:0}))};
 });
 const acc=plan.map(()=>({ending:new Float64Array(c.runs),value:new Float64Array(c.runs),withdrawn:new Float64Array(c.runs),reachWeek:new Int16Array(c.runs).fill(0),ruinWeek:new Int16Array(c.runs).fill(0),
  keep:c.marks.map(()=>new Uint8Array(c.runs)),solvent:c.marks.map(()=>new Uint8Array(c.runs)),belowDownside:new Uint8Array(c.runs),maxDrawdown:new Float64Array(c.runs)}));
 const outcome=new Int8Array(legs.length),pTrue=new Float64Array(legs.length),factor=new Float64Array(events.length);
 for(let run=0;run<c.runs;run++){
  const r=mulberry32(runSeed(c.seed,run)),sys=c.sigmaSystematic*gauss(r);
  const st=plan.map(()=>({b:c.bankroll,peak:c.bankroll,withdrawn:0,reach:0,ruin:0,dd:0,out:false}));
  for(let w=1;w<=total;w++){
   for(let e=0;e<events.length;e++)factor[e]=gauss(r);
   for(let i=0;i<legs.length;i++){
    const l=legs[i],load=l.loading||0,idio=gauss(r),z=gauss(r),adj=Math.min(.995,Math.max(.005,l.p-c.probShift));
    const pc=invLogit(logit(adj)+sys+c.sigmaLeg*idio),pw=pc*(1-(l.push||0)),pl=l.push||0;
    pTrue[i]=pc;
    const lat=load*factor[eventIndex.get(l.eventId)]+Math.sqrt(1-load*load)*z,u=S.normalCdf(lat);
    outcome[i]=u<pw?1:u<pw+pl?0:-1;
   }
   plan.forEach((s,k)=>{
    const a=st[k];
    if(!a.out&&a.b<c.minStake){a.ruin=a.ruin||w;a.out=true;}
    if(!a.out){
     const budget=a.b*c.maxExposure;let net=0;
     for(const t of s.tickets){
      const stake=round2(budget*t.w);if(stake<c.minStake||stake>a.b)continue;
      let mult=1,wins=0,lost=false;
      for(let j=0;j<t.idx.length;j++){const o=outcome[t.idx[j]];if(o<0){lost=true;break;}if(o>0){mult*=t.decs[j];wins++;}}
      net+=lost?-stake:wins===0?0:stake*(mult-1);
     }
     a.b=round2(a.b+net);
     if(a.b>a.peak)a.peak=a.b;a.dd=Math.max(a.dd,(a.peak-a.b)/a.peak);
     if(w<=c.weeks&&!a.reach&&a.b>=c.target)a.reach=w;
     if(c.withdraw&&c.withdrawTarget>0&&a.b>=c.reserve+c.withdrawTarget){const take=round2(a.b-c.reserve);a.withdrawn+=take;a.b=c.reserve;a.peak=Math.max(a.b,c.bankroll);}
     if(a.b<c.minStake)a.ruin=a.ruin||w;
    }
    c.marks.forEach((m,mi)=>{if(w===m){acc[k].keep[mi][run]=a.b>=preserve&&a.b>=c.minStake?1:0;acc[k].solvent[mi][run]=a.b>=c.minStake?1:0;}});
    if(w===c.weeks){acc[k].ending[run]=a.b;acc[k].value[run]=a.b+a.withdrawn;acc[k].withdrawn[run]=a.withdrawn;acc[k].belowDownside[run]=a.b<c.bankroll*(1-(c.acceptableDownside??1))?1:0;}
   });
  }
  plan.forEach((s,k)=>{const a=st[k];acc[k].reachWeek[run]=a.reach;acc[k].ruinWeek[run]=a.ruin;acc[k].maxDrawdown[run]=a.dd;});
 }
 const n=c.runs;
 return plan.map((s,k)=>{
  const A=acc[k];let reach=0,ruin=0,ruinH=0,below=0,belowBr=0,anyW=0,sumEnd=0,sumW=0,sumV=0,dd=0,down=0;
  for(let i=0;i<n;i++){
   if(A.reachWeek[i])reach++;if(A.ruinWeek[i])ruin++;if(A.ruinWeek[i]&&A.ruinWeek[i]<=c.weeks)ruinH++;
   if(A.value[i]<c.bankroll-1e-9)below++;if(A.ending[i]<c.bankroll-1e-9)belowBr++;if(A.withdrawn[i]>0)anyW++;
   sumEnd+=A.ending[i];sumW+=A.withdrawn[i];sumV+=A.value[i];dd+=A.maxDrawdown[i];down+=A.belowDownside[i];
  }
  const p=x=>x/n,ci=x=>[Math.max(0,p(x)-1.96*se(p(x),n)),Math.min(1,p(x)+1.96*se(p(x),n))];
  const keep=c.marks.map((m,mi)=>{const x=A.keep[mi].reduce((a,b)=>a+b,0);const y=A.solvent[mi].reduce((a,b)=>a+b,0);return {weekends:m,p:p(x),ci:ci(x),pSolvent:p(y),pSolventCI:ci(y)};});
  return {id:s.id,name:s.name,runs:n,seed:c.seed,
   pReachTarget:p(reach),pReachTargetCI:ci(reach),
   expectedEnding:sumEnd/n,medianEnding:pct(A.ending,.5),endingP10:pct(A.ending,.1),endingP90:pct(A.ending,.9),
   totalValueMean:sumV/n,totalValueMedian:pct(A.value,.5),totalValueP10:pct(A.value,.1),totalValueP90:pct(A.value,.9),
   pRuin:p(ruinH),pRuinCI:ci(ruinH),pRuinWithin12:p(ruin),
   pEndBelowStart:p(below),pEndBelowStartCI:ci(below),pBankrollBelowStart:p(belowBr),
   expectedWithdrawal:sumW/n,pAnyWithdrawal:p(anyW),meanMaxDrawdown:dd/n,
   pBreachDownside:p(down),preservation:keep};
 });
}

const api={simulate,validateConfig,DEFAULTS,mulberry32,runSeed};
root.GoingMissionSim=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
