(function(root){
'use strict';
const SOURCE='dfs-current-season-empirical-v1';
const KEYS=['pass_yds','pass_tds','rush_yds','rush_tds','rec_yds','rec_tds','receptions'];
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const seasonOf=now=>{const d=new Date(now);return d.getUTCFullYear()-(d.getUTCMonth()<2?1:0);};
function sample(profile,{now=Date.now(),kickoff}={}){
 const season=seasonOf(now),cutoff=Math.min(now,Number.isFinite(Date.parse(kickoff))?Date.parse(kickoff):now),seen=new Set(),rows=[];
 for(const g of profile?.games||[]){
  if(g.season!==season)continue;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(g.date||'')||!Number.isInteger(g.week)||g.week<1||g.week>18)continue;
  const date=Date.parse(g.date+'T00:00:00Z');
  if(!Number.isFinite(date)||new Date(date).toISOString().slice(0,10)!==g.date||date+86400000>cutoff)continue;
  if(!KEYS.every(k=>finite(g[k])&&g[k]>=0))continue;
  // A duplicate week is ambiguous evidence, never additional sample size.
  if(seen.has(g.week))return {season,rows:[],reason:'Duplicate current-season player game; projection withheld.'};
  seen.add(g.week);
  if(profile.position==='QB'&&!(finite(g.attempts)&&g.attempts>=10))continue;
  rows.push(g);
 }
 rows.sort((a,b)=>a.week-b.week);
 return {season,rows,reason:rows.length?'':'No completed current-season game sample; no prior-season fallback.'};
}
function model(profile,market,options={}){
 const {season,rows,reason}=sample(profile,options);
 if(!KEYS.includes(market)||rows.length<2)return {status:'unavailable',n:rows.length,season,source:SOURCE,reason:reason||'At least two completed current-season games are required; small samples are not backfilled.'};
 const values=rows.map(g=>g[market]).sort((a,b)=>a-b),mean=values.reduce((s,v)=>s+v,0)/values.length,sd=Math.sqrt(values.reduce((s,v)=>s+(v-mean)**2,0)/(values.length-1));
 return {family:'empirical',status:'ready',source:SOURCE,season,n:values.length,mean,sd,values,season_evidence:{current_games:values.length,historical_games:0,method:'Current-season sample mean; unvalidated forecasting baseline'}};
}
function bonusProbability(row,line){
 const m=row?.model;
 return m?.source===SOURCE&&m.status==='ready'&&Array.isArray(m.values)&&m.values.length?m.values.filter(v=>v>line).length/m.values.length:null;
}
function distribution(profile,{now=Date.now(),kickoff,site='draftkings',points}={}){
 const {season,rows}=sample(profile,{now,kickoff});if(rows.length<2||typeof points!=='function')return null;
 const values=rows.map(g=>points({...g,pass_300_probability:g.pass_yds>=300?1:0,rush_100_probability:g.rush_yds>=100?1:0,rec_100_probability:g.rec_yds>=100?1:0},site)).sort((a,b)=>a-b);
 if(!values.every(finite))return null;
 const mean=values.reduce((s,v)=>s+v,0)/values.length,sd=Math.sqrt(values.reduce((s,v)=>s+(v-mean)**2,0)/values.length),at=q=>values[Math.max(0,Math.ceil(q*values.length)-1)];
 const out={source:SOURCE,season,n:values.length,mean,sd,floor:at(.1),p25:at(.25),median:at(.5),p75:at(.75),p90:at(.9),p95:at(.95),boom:values.filter(v=>v>=Math.max(20,1.6*mean)).length/values.length,bust:values.filter(v=>v<=.5*mean).length/values.length,site,definitions:{floor:'Observed current-season 10th percentile; not a validated future floor',boom:'Observed current-season scores at or above max(20, 1.6 x mean)',bust:'Observed current-season scores at or below half the mean'}};
 Object.defineProperty(out,'sorted',{value:Float64Array.from(values),enumerable:false});return out;
}
root.GoingDfsCurrentSeason={SOURCE,KEYS,seasonOf,sample,model,bonusProbability,distribution};
if(typeof module!=='undefined')module.exports=root.GoingDfsCurrentSeason;
})(globalThis);
