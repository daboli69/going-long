(function(root){
'use strict';
const teams=new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
const canonical=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[String(x||'').toUpperCase()]||String(x||'').toUpperCase();
const seasonOf=now=>{const d=new Date(now);return d.getUTCFullYear()-(d.getUTCMonth()<2?1:0);};
const stamp=x=>{const m=typeof x==='string'&&x.match(/^(\d{4})-(\d{2})-(\d{2})T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(?:\.\d+)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$/);if(!m||/[+-]14:(?!00)/.test(x))return NaN;const calendar=new Date(Date.UTC(+m[1],+m[2]-1,+m[3]));return calendar.toISOString().slice(0,10)===x.slice(0,10)?Date.parse(x):NaN;};
const integer=x=>Number.isSafeInteger(x)&&x>=0;
const components=['sacks','sacksSuffered','interceptions','interceptionsThrown','fumbleRecoveries','defensiveTDs','returnTDs','safeties','blockedKicks','conversionReturns','unclassifiedFumbleTDs','teamFinalScore','opponentFinalScore','opponentDefensiveTDs','opponentSafeties','opponentUnclassifiedFumbleTDs','pointsAllowed'];
function pointsAllowedScore(n){return n===0?10:n<=6?7:n<=13?4:n<=20?1:n<=27?0:n<=34?-1:-4;}
function score(row){
 if(!row||!components.every(k=>integer(row[k])))throw Error('Defense scoring components are missing or malformed.');
 const allowed=row.opponentFinalScore-6*row.opponentDefensiveTDs-2*row.opponentSafeties;
 if(allowed<0||row.pointsAllowed!==allowed||6*(row.defensiveTDs+row.returnTDs)+2*(row.safeties+row.conversionReturns)>row.teamFinalScore)throw Error('Defense scoring components conflict with final scores.');
 return row.sacks+2*(row.interceptions+row.fumbleRecoveries+row.safeties+row.blockedKicks+row.conversionReturns)+6*(row.defensiveTDs+row.returnTDs)+pointsAllowedScore(allowed);
}
function project(salary,snapshot,{now=Date.now()}={}){
 const blocked=reason=>({status:'blocked',projection:null,n:0,season:seasonOf(now),concerns:[reason],source:'Current-season defensive evidence unavailable'});
 try{
  if(!Number.isFinite(now))throw Error('Current time is invalid.');
  const season=seasonOf(now),own=canonical(salary?.team),opp=canonical(salary?.opponent),kickoff=stamp(salary?.kickoff);
  if(!teams.has(own)||!teams.has(opp)||own===opp||!Number.isFinite(kickoff)||kickoff<=now||seasonOf(kickoff)!==season)throw Error('Defense game is started or its current-season matchup is unverified.');
  if(snapshot?.schemaVersion!==1||snapshot.season!==season||snapshot.defenseStatus!=='current-season-partial')throw Error('No verified current-season defensive scoring snapshot; DraftKings salary averages are not a substitute.');
  const generated=stamp(snapshot.generatedAt),retrieved=stamp(snapshot.retrievedAt),released=stamp(snapshot.releaseUpdatedAt);
  if(![generated,retrieved,released].every(Number.isFinite)||released>retrieved||retrieved>generated||generated>now||now-generated>36*3600000||now-retrieved>36*3600000||now-released>8*86400000)throw Error('Defensive source timestamps are missing, stale, future-dated or contradictory.');
  if(snapshot.sourceURL!==`https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_${season}.csv`||!['sourceSha256','resultsSHA256'].every(k=>/^[a-f0-9]{64}$/i.test(snapshot[k]||'')))throw Error('Official defensive source identity and hash receipts are required.');
  const rows=snapshot.teams?.[own];if(!Array.isArray(rows)||!rows.length)throw Error('No completed current-season games for this defense.');
  const seen=new Set(),values=[],gameIds=[],stats=Object.fromEntries(components.map(k=>[k,0]));let ambiguity=0;
  for(const row of rows){
   const id=String(row?.gameId||''),match=id.match(/^(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})$/),other=canonical(row?.opponent),date=stamp(row?.kickoff);
   if(!match||+match[1]!==season||+match[2]<1||+match[2]>18||!teams.has(match[3])||!teams.has(match[4])||match[3]===match[4]||canonical(row?.team)!==own||!teams.has(other)||other===own||![match[3],match[4]].includes(own)||![match[3],match[4]].includes(other)||!Number.isFinite(date)||date>=now||date>=released||date>=kickoff||seasonOf(date)!==season||seen.has(id))throw Error('Invalid, duplicate or non-current completed defensive game.');
   const reciprocal=snapshot.teams?.[other]?.filter(r=>r.gameId===id);
   if(!Array.isArray(reciprocal)||reciprocal.length!==1||canonical(reciprocal[0].team)!==other||canonical(reciprocal[0].opponent)!==own||stamp(reciprocal[0].kickoff)!==date)throw Error('Completed defensive game has no unique opposing-team receipt.');
   const d=row.dst,o=reciprocal[0].dst;score(o);
   if(d?.opponentFinalScore!==o.teamFinalScore||d.teamFinalScore!==o.opponentFinalScore||d.opponentDefensiveTDs!==o.defensiveTDs||d.opponentSafeties!==o.safeties||d.opponentUnclassifiedFumbleTDs!==o.unclassifiedFumbleTDs||d.sacks!==o.sacksSuffered||d.sacksSuffered!==o.sacks||d.interceptions!==o.interceptionsThrown||d.interceptionsThrown!==o.interceptions)throw Error('Opposing defensive scoring receipts disagree.');
   values.push(score(d));seen.add(id);gameIds.push(id);for(const k of components)stats[k]+=d[k];
   ambiguity+=d.unclassifiedFumbleTDs+d.opponentUnclassifiedFumbleTDs;
  }
  const n=values.length,projection=values.reduce((s,x)=>s+x,0)/n,sorted=Float64Array.from(values).sort(),q=p=>{const i=(n-1)*p,a=Math.floor(i);return sorted[a]+(sorted[Math.min(a+1,n-1)]-sorted[a])*(i-a);};
  const sd=Math.sqrt(values.reduce((s,v)=>s+(v-projection)**2,0)/n),distribution={n,mean:projection,sd,floor:q(.1),p25:q(.25),median:q(.5),p75:q(.75),p90:q(.9),p95:q(.95),method:'Observed current-season partial DST scores; not a simulated future distribution'};
  Object.defineProperty(distribution,'sorted',{value:sorted,enumerable:false});
  return {status:'ready',season,n,projection,tdMean:0,distribution,stats:Object.fromEntries(Object.entries(stats).map(([k,v])=>[k,v/n])),gameIds,
   source:'Current-season NFLverse defensive scoring mean',
   evidence:[`${n} completed ${season} defensive games; no previous-season or imported salary averages.`,`${(stats.sacks/n).toFixed(2)} sacks, ${(stats.interceptions/n).toFixed(2)} interceptions, ${(stats.fumbleRecoveries/n).toFixed(2)} opponent fumble recoveries per game.`],
   concerns:['Empirical partial defensive scoring baseline; no validated matchup adjustment or future ceiling.',`Fumble recovery TDs cannot be separated into offensive/defensive scores in the team feed; omitted from scored TDs and retained in opponent points allowed (${ambiguity} ambiguous TD observations).`,`${n} current-season games form a small sample; observed quantiles are descriptive, not calibrated future probabilities.`],
   provenance:{sourceURL:snapshot.sourceURL,sourceSha256:snapshot.sourceSha256,resultsSHA256:snapshot.resultsSHA256,generatedAt:snapshot.generatedAt,retrievedAt:snapshot.retrievedAt,releaseUpdatedAt:snapshot.releaseUpdatedAt}};
 }catch(error){return blocked(error.message);}
}
root.GoingDfsCurrentDefense={project,score,pointsAllowedScore,seasonOf};
if(typeof module!=='undefined')module.exports=root.GoingDfsCurrentDefense;
})(globalThis);
