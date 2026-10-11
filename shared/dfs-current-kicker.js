(function(root){
'use strict';
const SOURCE='dfs-current-season-kicker-v1';
const fields=['fg_made_0_19','fg_made_20_29','fg_made_30_39','fg_made_40_49','fg_made_50_59','fg_made_60_','fg_made','fg_att','pat_made','pat_att'];
const teams=new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
const canonical=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[String(x||'').toUpperCase()]||String(x||'').toUpperCase();
const seasonOf=now=>{const d=new Date(now);return d.getUTCFullYear()-(d.getUTCMonth()<2?1:0);};
const stamp=x=>{const m=typeof x==='string'&&x.match(/^(\d{4})-(\d{2})-(\d{2})T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(?:\.\d+)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$/);if(!m||/[+-]14:(?!00)/.test(x))return NaN;return new Date(Date.UTC(+m[1],+m[2]-1,+m[3])).toISOString().slice(0,10)===x.slice(0,10)?Date.parse(x):NaN;};
const count=x=>Number.isSafeInteger(x)&&x>=0&&x<=100;
function score(c){
 if(!c||!fields.every(k=>count(c[k]))||fields.slice(0,6).reduce((s,k)=>s+c[k],0)!==c.fg_made||c.fg_made>c.fg_att||c.pat_made>c.pat_att)throw Error('Missing or contradictory kicker scoring counts.');
 return 3*(c.fg_made_0_19+c.fg_made_20_29+c.fg_made_30_39)+4*c.fg_made_40_49+5*(c.fg_made_50_59+c.fg_made_60_)+c.pat_made;
}
function project(salary,snapshot,{now=Date.now(),playerId}={}){
 const blocked=reason=>({status:'blocked',projection:null,n:0,season:seasonOf(now),source:SOURCE,concerns:[reason]});
 try{
  const season=seasonOf(now),team=canonical(salary?.team),opponent=canonical(salary?.opponent),kickoff=stamp(salary?.kickoff);
  if(!Number.isFinite(now)||!teams.has(team)||!teams.has(opponent)||team===opponent||!Number.isFinite(kickoff)||kickoff<=now||seasonOf(kickoff)!==season)throw Error('Kicker current-season future matchup is unverified or started.');
  if(!/^00-\d{7}$/.test(playerId||''))throw Error('Fresh roster player identity is required for kicker projection.');
  if(snapshot?.schemaVersion!==1||snapshot.season!==season||snapshot.status!=='current-season-kickers')throw Error('No current-season kicker snapshot; salary averages cannot substitute.');
  const generated=stamp(snapshot.generatedAt),retrieved=stamp(snapshot.retrievedAt),released=stamp(snapshot.releaseUpdatedAt);
  if(![generated,retrieved,released].every(Number.isFinite)||released>retrieved||retrieved>generated||generated>now||now-generated>36*3600000||now-retrieved>36*3600000||now-released>8*86400000)throw Error('Kicker source timestamps are stale, missing or contradictory.');
  const resultsGenerated=stamp(snapshot.resultsGeneratedAt),resultsChecked=stamp(snapshot.resultsCheckedAt);
  if(![resultsGenerated,resultsChecked].every(Number.isFinite)||resultsChecked>resultsGenerated||resultsGenerated>generated||now-resultsGenerated>36*3600000||now-resultsChecked>36*3600000)throw Error('Kicker final-game result receipts are stale or contradictory.');
  if(snapshot.sourceURL!==`https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_${season}.csv`||!['sourceSha256','resultsSHA256'].every(k=>/^[a-f0-9]{64}$/i.test(snapshot[k]||'')))throw Error('Official kicker source and result hash receipts are required.');
  const player=snapshot.players?.[playerId];
  if(player?.playerId!==playerId||!Array.isArray(player.games))throw Error('Kicker identity has no verified current-season history.');
  const values=[],gameIds=[],seen=new Set(),weeks=new Set();let lastDate=-Infinity;
  for(const g of player.games){
   const match=String(g?.gameId||'').match(/^(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})$/),date=stamp(g?.kickoff),own=canonical(g?.team),other=canonical(g?.opponent);
   if(!match||+match[1]!==season||+match[2]<1||+match[2]>18||!teams.has(match[3])||!teams.has(match[4])||match[3]===match[4]||!teams.has(own)||!teams.has(other)||own===other||![match[3],match[4]].includes(own)||![match[3],match[4]].includes(other)||seen.has(g.gameId)||weeks.has(+match[2])||!Number.isFinite(date)||date<=lastDate||date>=released||date>=now||date>=kickoff||seasonOf(date)!==season)throw Error('Kicker history contains invalid, duplicate, future or mismatched games.');
   seen.add(g.gameId);weeks.add(+match[2]);lastDate=date;
   const points=score(g.counts);
   if(!count(g.teamFinalScore)||3*g.counts.fg_made+g.counts.pat_made>g.teamFinalScore||g.points!==points)throw Error('Kicker scoring conflicts with final-game receipt.');
   // Keep only this current team stint; traded-player samples are not blended.
   if(own!==team){values.length=0;gameIds.length=0;continue;}
   values.push(points);gameIds.push(g.gameId);
  }
  if(values.length<2)throw Error('At least two completed current-season games for this kicker and team are required.');
  const n=values.length,mean=values.reduce((s,v)=>s+v,0)/n,sorted=Float64Array.from(values).sort(),at=q=>sorted[Math.max(0,Math.ceil(q*n)-1)],sd=Math.sqrt(values.reduce((s,v)=>s+(v-mean)**2,0)/n);
  const distribution={source:SOURCE,season,n,mean,sd,floor:at(.1),p25:at(.25),median:at(.5),p75:at(.75),p90:at(.9),p95:at(.95),method:'Observed current-season kicker scores; not calibrated future quantiles'};
  Object.defineProperty(distribution,'sorted',{value:sorted,enumerable:false});
  return {status:'ready',source:SOURCE,season,n,projection:mean,tdMean:0,distribution,gameIds,playerId,evidence:[`${n} completed ${season} games on ${team}; field-goal distance and made extra points use DraftKings scoring.`],concerns:['Current-season empirical baseline; no validated matchup adjustment or future ceiling.',`${n} games are a small sample; observed quantiles are descriptive.`],provenance:{sourceURL:snapshot.sourceURL,sourceSha256:snapshot.sourceSha256,resultsSHA256:snapshot.resultsSHA256,resultsGeneratedAt:snapshot.resultsGeneratedAt,resultsCheckedAt:snapshot.resultsCheckedAt,generatedAt:snapshot.generatedAt,retrievedAt:snapshot.retrievedAt,releaseUpdatedAt:snapshot.releaseUpdatedAt}};
 }catch(error){return blocked(error.message);}
}
root.GoingDfsCurrentKicker={SOURCE,fields,score,project,seasonOf};
if(typeof module!=='undefined')module.exports=root.GoingDfsCurrentKicker;
})(globalThis);
