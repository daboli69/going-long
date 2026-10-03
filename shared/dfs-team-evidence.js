(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x),canonical=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[String(x||'').toUpperCase()]||String(x||'').toUpperCase();
const NFL=new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
const nameKey=x=>String(x||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const fail=message=>{throw Error('Touchdown Throne team evidence: '+message);};
function buildScenario({teamSnapshot,profiles={},context,injuryContext,generatedAt,now=Date.now(),makeModel,injuries,slateGames,pool=[]}={}){
 if(!finite(now))fail('current time is invalid.');
 const seasonOf=stamp=>{const d=new Date(stamp);return d.getUTCFullYear()-(d.getUTCMonth()<2?1:0);},season=seasonOf(now),fresh=(stamp,label)=>{const t=Date.parse(stamp);if(!Number.isFinite(t)||t>now||now-t>36*3600000)fail(label+' is missing, future-dated or older than 36 hours; refresh the public evidence.');return t;};
 if(teamSnapshot?.schemaVersion!==1||teamSnapshot.season!==season)fail('a current-season schema 1 team TD snapshot is required.');
 const at=fresh(teamSnapshot.generatedAt,'Team snapshot'),retrieved=fresh(teamSnapshot.retrievedAt,'Team source retrieval'),released=fresh(teamSnapshot.releaseUpdatedAt,'Team source release');
 if(released>retrieved||retrieved>at)fail('team source receipt chronology is invalid.');
 if(teamSnapshot.sourceURL!==`https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_${season}.csv`||!/^[a-f0-9]{64}$/i.test(teamSnapshot.sourceSha256||''))fail('official nflverse source URL and SHA-256 receipt are required.');
 fresh(generatedAt,'GOING player models');fresh(context?.generated_at,'Current role snapshot');
 if(context?.season!==season||!context.scopes?.[season]?.players)fail('verified current-season player roles are missing.');
 if(!injuryContext?.fresh)fail('fresh roster/injury evidence is required.');
 fresh(injuryContext.generatedAt,'Roster/injury snapshot');
 if(typeof makeModel!=='function'||!injuries?.normalize||!injuries?.availability||!injuries?.starterEligibility)fail('the existing GOING TD and availability adapters are required.');
 if(!Array.isArray(slateGames)||!slateGames.length)fail('import the actual contest game set first.');
 const upcoming=new Map(),slateIds=new Set();
 for(const g of slateGames){
  const home=canonical(g.home),away=canonical(g.away),kick=Date.parse(g.kickoff);
  if(!NFL.has(home)||!NFL.has(away)||home===away||!g.gameId||!Number.isFinite(kick)||seasonOf(kick)!==season||slateIds.has(g.gameId))fail('imported slate has invalid or duplicate NFL game identities.');
  slateIds.add(g.gameId);
  for(const [t,opponent]of [[home,away],[away,home]]){if(upcoming.has(t))fail(t+' appears in conflicting slate games.');upcoming.set(t,{team:t,opponent,kickoff:g.kickoff,gameId:g.gameId});}
 }
 const all=Object.values(profiles),identities=new Map(),ids=new Set();
 for(const p of all){
  if(!p?.id||ids.has(String(p.id)))fail('GOING profile IDs are missing or duplicated.');ids.add(String(p.id));
  const key=canonical(p.team)+'|'+nameKey(p.name)+'|'+p.position;identities.set(key,(identities.get(key)||0)+1);
 }
 const provenance={sourceURL:teamSnapshot.sourceURL,sourceSha256:teamSnapshot.sourceSha256,releaseUpdatedAt:teamSnapshot.releaseUpdatedAt,retrievedAt:teamSnapshot.retrievedAt,generatedAt:teamSnapshot.generatedAt,resultsSHA256:teamSnapshot.resultsSHA256,modelGeneratedAt:generatedAt,roleGeneratedAt:context.generated_at,injuryGeneratedAt:injuryContext.generatedAt};
 const teams={},currentPlayers=context.scopes[season].players;
 for(const [t,game]of upcoming){
  const rows=teamSnapshot.teams?.[t];if(!Array.isArray(rows)||rows.length<3)fail(t+' needs at least three completed current-season team TD observations.');
  const seen=new Set(),counts=[],gameIds=[];let lastKickoff='';
  for(const r of rows){
   const parsed=String(r?.gameId||'').match(/^(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})$/),kick=Date.parse(r?.kickoff),opponent=canonical(r?.opponent);
   if(!parsed||+parsed[1]!==season||+parsed[2]<1||+parsed[2]>18||canonical(r.team)!==t||!NFL.has(opponent)||opponent===t||!NFL.has(parsed[3])||!NFL.has(parsed[4])||parsed[3]===parsed[4]||![parsed[3],parsed[4]].includes(t)||![parsed[3],parsed[4]].includes(opponent)||!Number.isFinite(kick)||kick>=now||kick>=retrieved||seen.has(r.gameId))fail(t+' has an invalid, future or duplicate completed team-game identity.');
   if(seasonOf(kick)!==season||![r.rushTDs,r.recTDs,r.qualifyingTDs].every(v=>Number.isSafeInteger(v)&&v>=0)||r.qualifyingTDs!==r.rushTDs+r.recTDs)fail(t+' has missing or inconsistent rushing/receiving TD counts.');
   seen.add(r.gameId);counts.push(r.qualifyingTDs);gameIds.push(r.gameId);if(r.kickoff>lastKickoff)lastKickoff=r.kickoff;
  }
  const playerMeans={},playerShares={},playerRoleSources={},missingQBReceiving=[];let allVerifiedPlayerMean=0;
  for(const p of all){
   if(canonical(p.team)!==t||!['QB','RB','WR','TE','FB'].includes(p.position))continue;
   const c=currentPlayers[p.id],identity=t+'|'+nameKey(p.name)+'|'+p.position;
   const identityMatches=c&&c.player_id===p.id&&canonical(c.team)===t&&c.season===season&&c.position===p.position;
   if(p.position==='QB'){if(c&&!identityMatches)continue;}
   else if(!identityMatches||!(c.games>0)||!(c.targets>0||c.rush_attempts>0))continue;
   if(identities.get(identity)!==1)fail('ambiguous current player identity for '+p.name+'; resolve the GOING identity before generating.');
   const recent=stamp=>{const n=Date.parse(stamp);return Number.isFinite(n)&&n<=now&&now-n<=28*86400000;};
   if(!recent(p.last_game)||(p.position!=='QB'&&!recent(c.last_game)))continue;
   const roster=injuryContext.byIdentity?.get(t+'|'+injuries.normalize(p.name));if(roster&&injuries.availability(roster)?.block)continue;
   if(p.position==='QB'){const starter=injuries.starterEligibility({name:p.name,team:t,position:p.position,context:injuryContext});if(!starter?.known||!starter.eligible)continue;}
   const rush=makeModel(p,'rush_tds',game),rec=makeModel(p,'rec_tds',game),ready=row=>row?.model?.status==='ready'&&finite(row.projMean)&&row.projMean>=0;
   if(!ready(rush)||(p.position!=='QB'&&!ready(rec))||[rush,rec].some(row=>row&&((row.profileId!=null&&row.profileId!==p.id)||row.injury?.state==='out'||row.injury?.blockRecommendation)))continue;
   if(p.position==='QB'&&!ready(rec))missingQBReceiving.push(p.id);
   const mean=rush.projMean+(ready(rec)?rec.projMean:0);playerMeans[p.id]=mean;allVerifiedPlayerMean+=mean;
   playerRoleSources[p.id]=p.position==='QB'?'Fresh verified starting quarterback; rushing/receiving usage is not required.':'Verified current-season targets/carries.';
  }
  if(!Object.keys(playerMeans).length)fail(t+' has no uniquely verified current-role players with ready rushing/receiving TD models.');
  const mean=counts.reduce((sum,n)=>sum+n,0)/counts.length;
  // In the all-zero case 1 is only a zero-share division guard, not estimated TDs.
  const denominator=Math.max(mean,allVerifiedPlayerMean)||1;
  for(const [id,value]of Object.entries(playerMeans))playerShares[id]=value/denominator;
  teams[t]={...game,counts,n:counts.length,mean,denominator,allVerifiedPlayerMean,playerMeans,playerShares,playerRoleSources,missingQBReceiving,otherShare:Math.max(0,1-allVerifiedPlayerMean/denominator),gameIds,lastKickoff,zeroMeanGuard:mean===0&&allVerifiedPlayerMean===0,provenance};
 }
 const poolIds=new Set();
 for(const p of pool){
  if(p.position==='DST'||p.unavailable||p.matched!==true)continue;
  const id=String(p.profileId||p.athleteId||''),t=canonical(p.team),e=teams[t],profile=profiles[id];
  if(!id||poolIds.has(id)||!e||!profile||nameKey(profile.name)!==nameKey(p.name)||canonical(profile.team)!==t||profile.position!==p.position||p.gameId!==e.gameId||canonical(p.opponent)!==e.opponent||Date.parse(p.kickoff)!==Date.parse(e.kickoff)||!finite(p.tdMean)||!Object.hasOwn(e.playerMeans,id)||Math.abs(e.playerMeans[id]-p.tdMean)>1e-9)fail((p.name||'Imported player')+' does not match the independently verified current TD evidence; refresh or resolve the player match.');
  poolIds.add(id);
 }
 return {version:'team-budget-v1',season,teams,provenance,limitations:['Experimental relative eight-TD scenario ranking; not calibrated real-world probability.','Only three or four current-season completed games per team; no fabricated tail smoothing.','Teammates share each observed team TD budget; different teams are assumed independent, including opposing teams.','Current player TD shares reuse existing uncalibrated role/injury-adjusted models. Final participation still requires checking.','A QB with unavailable receiving TD evidence contributes modeled rushing TDs only; affected IDs are listed in missingQBReceiving.']};
}
root.GoingDfsTeamEvidence={buildScenario};if(typeof module!=='undefined')module.exports=root.GoingDfsTeamEvidence;
})(globalThis);
