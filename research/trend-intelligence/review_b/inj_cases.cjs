const O=require('./_orig.cjs'),Pt=require('./_patched.cjs');
const hist=require('../../../data/history.json');
function erf(x){const s=Math.sign(x);x=Math.abs(x);const t=1/(1+.3275911*x);const y=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-x*x);return s*y}
const nCDF=z=>.5*(1+erf(z/Math.SQRT2));
function cdf(x,m){const mass=m.nonpositive||[];const emp=mass.reduce((s,v,i)=>s+(v<=x?(m.nonpositive_weights?.[i]??1):0),0);const w=m.positive_weight??1;if(x<=0)return emp;return Math.min(1,emp+w*nCDF((Math.log(x)-m.mu_log)/m.sigma_log))}
function trueMean(m){const mass=(m.nonpositive||[]).reduce((s,v,i)=>s+v*(m.nonpositive_weights?.[i]??1),0);return mass+(m.positive_weight??1)*Math.exp(m.mu_log+m.sigma_log**2/2)}
function pz(m){return (m.nonpositive_weights||[]).reduce((a,b)=>a+b,0)}
const profs=hist.betting.profiles;const picks=[];
for(const [id,p] of Object.entries(profs)){const m=p.stats?.rec_yds;if(m&&m.policy==='champion-v2'&&m.mu_log!=null)picks.push([p.name||id,p.pos||p.position,m])}
picks.sort((a,b)=>a[2].mean-b[2].mean);
const chosen=[picks[Math.floor(picks.length*.2)],picks[Math.floor(picks.length*.5)],picks[Math.floor(picks.length*.85)]];
console.log('n champion-v2 rec_yds models',picks.length);
for(const [name,pos,m] of chosen){
 console.log(`\n== ${name} ${pos} mean=${m.mean.toFixed(1)} p0=${pz(m).toFixed(3)} sigma=${m.sigma_log.toFixed(3)} trueMean(base)=${trueMean(m).toFixed(2)}`);
 const lines=[m.mean*.6,m.mean*.85,m.mean,m.mean*1.2].map(x=>Math.round(x)+.5);
 console.log('scale unc | meanTarget | trueMean orig/patch | P0 orig/patch | P(over L) base -> orig / patch @ lines '+lines.join(','));
 for(const sc of [.6,.8,1,1.2,1.4])for(const u of [1,1.15,1.3]){
  if(sc===1&&u===1)continue;
  const a=O.scaleModel(m,sc,u),b=Pt.scaleModel(m,sc,u);
  const ov=(mm,L)=>(1-cdf(L,mm)).toFixed(3);
  console.log(`${sc} ${u} | ${(m.mean*sc).toFixed(1)} | ${trueMean(a).toFixed(1)} / ${trueMean(b).toFixed(1)} | ${cdf(0,a).toFixed(3)}/${cdf(0,b).toFixed(3)} | `+lines.map(L=>`${ov(m,L)}->${ov(a,L)}/${ov(b,L)}`).join('  '));
 }
}
// edge cases
console.log('\nedge: no mu_log',Pt.scaleModel({family:'lognormal',policy:'champion-v2',mean:20,sd:15},.8,1.1));
console.log('edge scale 0',JSON.stringify(Pt.scaleModel(chosen[1][2],0,1.2)).slice(0,300));
