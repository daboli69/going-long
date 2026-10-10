(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const team=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[String(x||'').toUpperCase()]||String(x||'').toUpperCase();
// Preserve suffixes: two similar names are not permission to guess an identity.
const nameKey=x=>String(x||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const age=(stamp,now)=>(now-Date.parse(stamp))/3600000;
function observedCounts(profile,now){
 const games=(profile?.games||[]).filter(g=>Date.parse(g.date)<=now&&Number.isSafeInteger(g.rush_tds)&&g.rush_tds>=0&&Number.isSafeInteger(g.rec_tds)&&g.rec_tds>=0);
 const d=new Date(now),season=d.getUTCFullYear()-(d.getUTCMonth()<2?1:0),current=games.filter(g=>Number(g.season)===season),sample=current.length?current:games;
 const bins=[0,0,0,0];for(const g of sample)bins[Math.min(3,g.rush_tds+g.rec_tds)]++;
 return {bins,n:sample.length,season:current.length?season:'older',label:'Observed rushing + receiving TD counts; descriptive, not calibrated future odds'};
}
// Systematic bias corrections, each with a rollback switch (set enabled:false, or pass adjustments:false/{} to buildPool).
// qbTurnovers: the modelled core points leave out interceptions, lost fumbles and two-point conversions. Against ARCHIVED actual DraftKings points for 212 QB games with logged stat lines
// (2024-26), actual minus core-from-actual-stats was -0.52 (se .07, n=187, games before 2026-01-15) and -0.68 (se .22, n=25, later games): a stable -0.5 to -0.7. RB/WR/TE were 0.00 +/- .02
// (n=1,350), so nothing is applied to them. See docs/DFS_PROJECTION_BACKTEST.md.
const ADJUSTMENTS=Object.freeze({qbTurnovers:Object.freeze({enabled:true,points:-.52,positions:['QB']})});
function shiftDistribution(d,delta){
 if(!d||!finite(delta)||delta===0)return d;
 const out={...d};for(const k of ['mean','floor','p25','median','p75','p90','p95'])if(finite(out[k]))out[k]+=delta;
 const sorted=Float64Array.from(d.sorted||[],v=>v+delta);Object.defineProperty(out,'sorted',{value:sorted,enumerable:false});return out;
}
function buildPool(salaries,{profiles={},context=null,injuryContext=null,generatedAt,now=Date.now(),makeModel,bonusProbability,points,injuries,adjustments=ADJUSTMENTS}={}){
 const all=Object.values(profiles),fresh=age(generatedAt,now)>=0&&age(generatedAt,now)<=36;
 return salaries.map(s=>{
  const base={...s,matched:false,unavailable:true,projection:null,tdMean:null,reasons:[],concerns:[],evidence:[],modelGeneratedAt:generatedAt};
  if(s.position==='DST')return {...base,matched:true,unavailable:!finite(s.avgPointsPerGame)||s.avgPointsPerGame<=0,projection:s.avgPointsPerGame,tdMean:0,reasons:['Imported DraftKings average fantasy points; salary competes with offensive upgrades.'],concerns:['Historical platform average only: no current DST matchup projection. DST contributes zero promotional rushing/receiving TDs.'],source:'DraftKings DST average (fallback)'};
  const matches=all.filter(p=>nameKey(p.name)===nameKey(s.name)&&team(p.team)===team(s.team)&&p.position===s.position);
  if(matches.length!==1)return {...base,concerns:[matches.length?'Ambiguous GOING identity; excluded.':'No exact name/team/position GOING match; excluded.']};
  const p=matches[0],current=context?.scopes?.[String(context.season)]?.players?.[p.id],roster=injuryContext?.byIdentity?.get(team(s.team)+'|'+injuries?.normalize?.(s.name)),availability=roster&&injuries?.availability?.(roster),starter=injuries?.starterEligibility?.({name:p.name,team:p.team,position:p.position,context:injuryContext});
  base.matched=true;base.athleteId=p.id;base.profileId=p.id;base.counts=observedCounts(p,now);
  if(!fresh)return {...base,concerns:['GOING model snapshot missing, future-dated or older than 36 hours; excluded.']};
  if(!Number.isFinite(age(p.last_game,now))||age(p.last_game,now)<0||age(p.last_game,now)>28*24)return {...base,concerns:['No recent player game within 28 days; excluded.']};
  if(availability?.block)return {...base,concerns:['Roster reports unavailable: '+availability.state]};
  if(s.position==='QB'&&(!starter?.known||!starter.eligible))return {...base,concerns:[starter?.reason||'Starting QB identity is not verified; excluded.']};
  if(s.position!=='QB'&&(!current||current.player_id!==p.id||team(current.team)!==team(p.team)||Number(current.season)!==Number(context.season)||!Number.isFinite(age(context.generated_at,now))||age(context.generated_at,now)<0||age(context.generated_at,now)>36||!Number.isFinite(age(current.last_game,now))||age(current.last_game,now)<0||age(current.last_game,now)>28*24||!(current.targets>0||current.rush_attempts>0)))return {...base,concerns:['No verified current-season targets/carries; excluded rather than selected merely for price.']};
  const stats={},models={},keys=['pass_yds','pass_tds','rush_yds','rec_yds','receptions','rush_tds','rec_tds'];
  for(const key of keys){const row=makeModel(p,key,s),m=row?.model;models[key]=row;if(m?.status==='ready'&&finite(row.projMean)&&row.projMean>=0)stats[key]=row.projMean;}
  const required=s.position==='QB'?['pass_yds','pass_tds','rush_yds','rush_tds']:['rush_yds','rec_yds','receptions','rush_tds','rec_tds'];
  const missing=required.filter(k=>!finite(stats[k]));
  if(missing.length)return {...base,concerns:['Missing ready components: '+missing.join(', ')]};
  // Receiving TDs by a QB count when supported; missing QB receiving production is disclosed.
  if(s.position==='QB'&&!finite(stats.rec_tds))base.concerns.push('QB receiving TD contribution unavailable; only modeled rushing TDs counted.');
  for(const [key,market,line] of [['pass_300_probability','pass_yds',299.5],['rush_100_probability','rush_yds',99.5],['rec_100_probability','rec_yds',99.5]]){const prob=bonusProbability(models[market],line);if(finite(prob))stats[key]=prob;}
  const adjusted=Object.values(models).find(m=>m?.injury?.state==='out');if(adjusted)return {...base,concerns:['Current injury-adjusted model marks player unavailable.']};
  const rawProjection=points(stats,'draftkings'),turnover=adjustments?.qbTurnovers,delta=turnover?.enabled&&turnover.positions?.includes(s.position)&&finite(turnover.points)?turnover.points:0,projection=finite(rawProjection)?Math.max(0,rawProjection+delta):rawProjection,tdMean=stats.rush_tds+(stats.rec_tds||0);
  base.reasons.push(s.position==='QB'?`Passing production supports DFS points; ${stats.rush_tds.toFixed(2)} modeled rushing TDs support the promotion.`:`${stats.rush_tds.toFixed(2)} rushing + ${(stats.rec_tds||0).toFixed(2)} receiving TD mean from existing GOING count models.`);
  if(current){if(finite(current.target_share))base.evidence.push(`${Math.round(current.target_share*100)}% current-season target share`);if(finite(current.rush_share))base.evidence.push(`${Math.round(current.rush_share*100)}% current-season carry share`);base.evidence.push(`${current.games} current-season games; latest ${current.last_game||'unknown'}`);}
  const feature=models.rec_tds?.features||models.rush_tds?.features;
  if(feature&&feature.player_id===p.id&&team(feature.team)===team(p.team)){
   const fields=[['goal_line_carries','goal-line carries'],['red_zone_targets','red-zone targets'],['end_zone_targets','end-zone targets']];
   const labels=fields.filter(([key])=>finite(feature[key])&&feature[key]>0).map(([key,label])=>feature[key]+' '+label);
   if(labels.length)base.evidence.push('Pooled historical window: '+labels.join(', ')+'; latest game '+(feature.last_game||'unknown')+'. Not current-season-only evidence.');
  }
  const seasonEvidence=models.rush_tds?.model?.season_evidence||models.rec_tds?.model?.season_evidence;
  if(seasonEvidence)base.evidence.push('TD model evidence: '+seasonEvidence.current_games+' current / '+seasonEvidence.historical_games+' prior games; '+(seasonEvidence.method||'unvalidated policy')+'.');
  const injury=Object.values(models).find(m=>m?.injury&&m.injury.state!=='available')?.injury;
  if(injury)base.concerns.push(injury.reason||injury.status||'Availability uncertainty');
  if(!injuryContext?.fresh)base.concerns.push('Roster/injury snapshot is stale; final participation is not verified.');
  else base.concerns.push('Final game-day inactives and workload still need checking.');
  base.concerns.push('Count models are uncalibrated for multi-TD tails; no eight-TD lineup probability.');
  const upside=root.GoingDfsUpside?.observed(p,projection,{now,points,site:'draftkings'})||null;
  if(upside)base.evidence.push(`Historical partial DFS scoring spread: ${upside.n} completed games (${upside.currentGames} current season); prior roles may differ.`);
  // Simulated outcome distribution (floor/median/90th/boom/bust) from the same component models, with measured within-player correlations.
  const rawDistribution=root.GoingDfsSim?.player(Object.fromEntries(Object.entries(models).map(([k,row])=>[k,row?.model])),p.position,{id:p.id,site:'draftkings'})||null,distribution=shiftDistribution(rawDistribution,finite(rawProjection)?projection-rawProjection:0);
  if(delta)base.concerns.push(`Projection includes a ${delta.toFixed(2)} point allowance for interceptions and lost fumbles that the modelled components omit (measured on archived QB games).`);
  return {...base,distribution,roleTrend:p.role_trend||null,projection,projectionRaw:rawProjection,projectionAdjustment:delta,tdMean,stats,upside,unavailable:!finite(projection)||projection<=0,source:'Existing injury-adjusted GOING component models',injury,modelAgeHours:age(generatedAt,now),value:projection*1000/s.salary};
 });
}
root.GoingDfsEvidence={buildPool,observedCounts,nameKey,ADJUSTMENTS,shiftDistribution};if(typeof module!=='undefined')module.exports=root.GoingDfsEvidence;
})(globalThis);
