(function(root){
'use strict';
const VERSION='team-budget-v1',THRESHOLD=8;
const TEAMS=new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const canonicalTeam=x=>({JAC:'JAX',LAR:'LA',WSH:'WAS'})[String(x||'').trim().toUpperCase()]||String(x||'').trim().toUpperCase();
const zeroBins=()=>[1,0,0,0,0,0,0,0,0];
const roundoff=(a,b)=>32*Number.EPSILON*Math.max(1,Math.abs(a),Math.abs(b));
// Conditional on N team rushing/receiving TDs, the selected cohort receives
// Binomial(N, share). This is a marginal of finite multinomial allocation:
// selected teammates compete for the SAME team TDs; scores are not duplicated.
function conditionalBins(n,share){
 const bins=new Array(THRESHOLD+1).fill(0);
 if(n===0||share===0){bins[0]=1;return bins;}
 if(share===1){bins[Math.min(THRESHOLD,n)]=1;return bins;}
 let mass=Math.exp(n*Math.log1p(-share)),below=0;
 for(let k=0;k<THRESHOLD&&k<=n;k++){
  bins[k]=mass;below+=mass;
  mass*=((n-k)/(k+1))*(share/(1-share));
 }
 bins[THRESHOLD]=n<THRESHOLD?0:Math.max(0,Math.min(1,1-below));
 return bins;
}
function convolve(a,b){
 const result=new Array(THRESHOLD+1).fill(0);
 for(let i=0;i<=THRESHOLD;i++)for(let j=0;j<=THRESHOLD;j++)result[Math.min(THRESHOLD,i+j)]+=a[i]*b[j];
 return result;
}
function evaluate(lineup,scenario){
 const errors=[],fail=()=>({valid:false,reason:errors.join(' '),errors,method:VERSION,tailMass:null,expectedTDs:null,bins:null,support:[],provenance:[]});
 if(!scenario||scenario.version!==VERSION||!scenario.teams||typeof scenario.teams!=='object'||Array.isArray(scenario.teams)){errors.push('Missing supported empirical team-budget scenario.');return fail();}
 if(!Array.isArray(lineup)||!lineup.length){errors.push('A nonempty lineup is required.');return fail();}
 const budgets=new Map();
 for(const [rawTeam,entry] of Object.entries(scenario.teams)){
  const team=canonicalTeam(rawTeam);
  if(!TEAMS.has(team)||budgets.has(team)){errors.push('Invalid or duplicate canonical team in scenario.');continue;}
  if(!entry||!Array.isArray(entry.counts)||!entry.counts.length||entry.counts.some(n=>!Number.isSafeInteger(n)||n<0)){errors.push(`${team}: completed-game TD budgets must be nonnegative integer observations.`);continue;}
  if(entry.n!=null&&(!Number.isSafeInteger(entry.n)||entry.n!==entry.counts.length)){errors.push(`${team}: observation count does not match the empirical sample.`);continue;}
  const teamMean=entry.counts.reduce((a,n)=>a+n/entry.counts.length,0),denominator=entry.denominator;
  if(!finite(denominator)||denominator<=0||denominator+roundoff(denominator,teamMean)<teamMean){errors.push(`${team}: allocation denominator must cover the empirical team TD mean.`);continue;}
  // Optional complete-player-pool mean lets the caller expose and validate the
  // other denominator floor; a subset lineup cannot infer omitted player means.
  if(entry.allVerifiedPlayerMean!=null&&(!finite(entry.allVerifiedPlayerMean)||entry.allVerifiedPlayerMean<0||denominator+roundoff(denominator,entry.allVerifiedPlayerMean)<entry.allVerifiedPlayerMean)){errors.push(`${team}: denominator does not cover all verified player TD means.`);continue;}
  budgets.set(team,{entry,teamMean,denominator});
 }
 const selected=new Map();
 for(const p of lineup){
  if(p?.position==='DST')continue;
  if(!p||!['QB','RB','WR','TE'].includes(p.position)||!finite(p.tdMean)||p.tdMean<0){errors.push('Offensive players require supported nonnegative rushing/receiving TD means.');continue;}
  const team=canonicalTeam(p.team);
  if(!TEAMS.has(team)||!budgets.has(team)){errors.push(`${team||'Unknown team'}: empirical team TD support is missing.`);continue;}
  // Caller supplies rush + receive tdMean. QB passing fields are never read.
  selected.set(team,(selected.get(team)||0)+p.tdMean);
 }
 if(errors.length)return fail();
 let bins=zeroBins(),expectedTDs=0;
 const support=[],provenance=[];
 for(const [team,selectedMean] of [...selected.entries()].sort(([a],[b])=>a.localeCompare(b))){
  const {entry,teamMean,denominator}=budgets.get(team);
  if(!finite(selectedMean)||selectedMean>denominator+roundoff(selectedMean,denominator)){errors.push(`${team}: selected players exceed the finite team allocation budget.`);continue;}
  const share=Math.min(1,selectedMean/denominator),teamBins=new Array(THRESHOLD+1).fill(0);
  // Each observed completed game has equal weight; no synthetic team TD budget.
  for(const count of entry.counts){const conditional=conditionalBins(count,share);for(let k=0;k<=THRESHOLD;k++)teamBins[k]+=conditional[k]/entry.counts.length;}
  bins=convolve(bins,teamBins);expectedTDs+=teamMean*share;
  support.push({team,n:entry.counts.length,share,selectedMean,denominator,teamMean,maxTeamTDs:entry.counts.reduce((max,count)=>Math.max(max,count),0),bins:teamBins});
  provenance.push({team,provenance:entry.provenance??null});
 }
 if(errors.length)return fail();
 const total=bins.reduce((a,p)=>a+p,0);
 if(!finite(total)||total<=0||bins.some(p=>!finite(p)||p<0)){errors.push('Empirical allocation produced invalid probability mass.');return fail();}
 // Correct floating-point accumulation only; never modify inputs or fit values.
 bins=bins.map(p=>p/total);
 return {valid:true,errors:[],reason:null,method:VERSION,threshold:THRESHOLD,tailMass:bins[THRESHOLD],expectedTDs,bins,support,provenance,limitations:[
  'Uncalibrated empirical team-budget allocation scenario; internal threshold mass is not a validated lineup probability.',
  'Selected teammates share finite rushing/receiving TD budgets; allocation shares are fixed from available count means.',
  'Team budgets are convolved independently; opponent/game dependence and changing team scoring environments are not fitted.',
  'Equally weighted observed completed games can be a small or unrepresentative sample; player roles and participation can change.'
 ]};
}
root.GoingDfsThreshold={VERSION,THRESHOLD,evaluate};
if(typeof module!=='undefined')module.exports=root.GoingDfsThreshold;
})(globalThis);
