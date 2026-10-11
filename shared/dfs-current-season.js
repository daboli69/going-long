(function(root){
'use strict';
const SOURCE='dfs-current-season-empirical-v1';
const QB_FALLBACK_SOURCE='dfs-prior-season-qb-fallback-v1';
const KEYS=['pass_yds','pass_tds','rush_yds','rush_tds','rec_yds','rec_tds','receptions'];
const COUNTS=['pass_tds','rush_tds','rec_tds','receptions'];
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const seasonOf=now=>{const d=new Date(now);return d.getUTCFullYear()-(d.getUTCMonth()<2?1:0);};
function seasonRows(profile,{now=Date.now(),kickoff}={},season=seasonOf(now),verifiedStartsOnly=false){
 const cutoff=Math.min(now,Number.isFinite(Date.parse(kickoff))?Date.parse(kickoff):now),seen=new Set(),rows=[];
 for(const g of profile?.games||[]){
  if(g.season!==season)continue;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(g.date||'')||!Number.isInteger(g.week)||g.week<1||g.week>18)continue;
  const date=Date.parse(g.date+'T00:00:00Z');
  if(!Number.isFinite(date)||new Date(date).toISOString().slice(0,10)!==g.date||seasonOf(date)!==season||date+86400000>cutoff)continue;
  // NFL yardage can be negative (kneels, sacks/laterals). Counts cannot.
  if(!KEYS.every(k=>finite(g[k]))||!COUNTS.every(k=>Number.isSafeInteger(g[k])&&g[k]>=0))continue;
  // A duplicate week is ambiguous evidence, never additional sample size.
  if(seen.has(g.week))return {season,rows:[],reason:'Duplicate current-season player game; projection withheld.'};
  seen.add(g.week);
  if(verifiedStartsOnly&&g.verified_start!==true)continue;
  if(profile.position==='QB'&&g.verified_start===false)continue;
  if(profile.position==='QB'&&!(finite(g.attempts)&&g.attempts>=10))continue;
  rows.push(g);
 }
 rows.sort((a,b)=>a.week-b.week);
 return {season,rows,reason:rows.length?'':'No completed current-season game sample; no prior-season fallback.'};
}
function sample(profile,options={}){return seasonRows(profile,options);}
function projectionSample(profile,options={}){
 const current=sample(profile,options);
 if(options.allowPriorSeasonQB!==true||profile?.position!=='QB'||current.rows.length>=2||/Duplicate/.test(current.reason))return {...current,source:SOURCE,sampleSeason:current.season,currentGames:current.rows.length};
 const previous=seasonRows(profile,options,current.season-1,true);
 if(previous.rows.length<2)return {...current,source:SOURCE,sampleSeason:current.season,currentGames:current.rows.length,reason:'Insufficient current-season starts and fewer than two verified prior-season QB starts; projection withheld.'};
 return {...previous,season:current.season,source:QB_FALLBACK_SOURCE,sampleSeason:current.season-1,currentGames:current.rows.length,reason:'Prior-season verified-start fallback; current-season starting sample insufficient.'};
}
function model(profile,market,options={}){
 const {season,rows,reason,source,sampleSeason,currentGames}=projectionSample(profile,options);
 if(!KEYS.includes(market)||rows.length<2)return {status:'unavailable',n:rows.length,season,source:SOURCE,reason:reason||'At least two completed current-season games are required; small samples are not backfilled.'};
 const values=rows.map(g=>g[market]).sort((a,b)=>a-b),mean=values.reduce((s,v)=>s+v,0)/values.length,sd=Math.sqrt(values.reduce((s,v)=>s+(v-mean)**2,0)/(values.length-1));
 return {family:'empirical',status:'ready',source,season,sampleSeason,n:values.length,mean,sd,values,season_evidence:{current_games:source===SOURCE?values.length:currentGames,historical_games:source===SOURCE?0:values.length,sample_season:sampleSeason,method:source===SOURCE?'Current-season sample mean; unvalidated forecasting baseline':`Prior-season ${sampleSeason} verified QB starts only; unvalidated fallback, no current/prior mixing`}};
}
function bonusProbability(row,line){
 const m=row?.model;
 return [SOURCE,QB_FALLBACK_SOURCE].includes(m?.source)&&m.status==='ready'&&Array.isArray(m.values)&&m.values.length?m.values.filter(v=>v>line).length/m.values.length:null;
}
function distribution(profile,{now=Date.now(),kickoff,site='draftkings',points,allowPriorSeasonQB=false}={}){
 const {season,rows,source,sampleSeason}=projectionSample(profile,{now,kickoff,allowPriorSeasonQB});if(rows.length<2||typeof points!=='function')return null;
 const values=rows.map(g=>points({...g,pass_300_probability:g.pass_yds>=300?1:0,rush_100_probability:g.rush_yds>=100?1:0,rec_100_probability:g.rec_yds>=100?1:0},site)).sort((a,b)=>a-b);
 if(!values.every(finite))return null;
 const mean=values.reduce((s,v)=>s+v,0)/values.length,sd=Math.sqrt(values.reduce((s,v)=>s+(v-mean)**2,0)/values.length),at=q=>values[Math.max(0,Math.ceil(q*values.length)-1)];
 const period=source===SOURCE?'current-season':`prior-season ${sampleSeason} QB starts`;
 const out={source,season,sampleSeason,n:values.length,mean,sd,floor:at(.1),p25:at(.25),median:at(.5),p75:at(.75),p90:at(.9),p95:at(.95),boom:values.filter(v=>v>=Math.max(20,1.6*mean)).length/values.length,bust:values.filter(v=>v<=.5*mean).length/values.length,site,definitions:{floor:`Observed ${period} 10th percentile; not a validated future floor`,boom:`Observed ${period} scores at or above max(20, 1.6 x mean)`,bust:`Observed ${period} scores at or below half the mean`}};
 Object.defineProperty(out,'sorted',{value:Float64Array.from(values),enumerable:false});return out;
}
root.GoingDfsCurrentSeason={SOURCE,QB_FALLBACK_SOURCE,KEYS,seasonOf,sample,projectionSample,model,bonusProbability,distribution};
if(typeof module!=='undefined')module.exports=root.GoingDfsCurrentSeason;
})(globalThis);
