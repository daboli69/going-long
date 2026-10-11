(function(root){
'use strict';
const team=value=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[String(value||'').toUpperCase()]||String(value||'').toUpperCase();
const name=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
// Manually verified, public, exact-game role evidence. This is not an injury rewrite
// or a season-wide depth chart. Remove/update only with a newer official statement.
const CONFIRMATIONS=Object.freeze([Object.freeze({
 team:'CHI',opponent:'GB',kickoff:'2026-10-11T17:00:00Z',starter:'Tyson Bagent',
 sourceURL:'https://www.chicagobears.com/news/injury-update-bears-rb-kyle-monangai-ruled-out-qb-caleb-williams-questionable-for-packers-game',
 sourcePublishedAt:'2026-10-09T20:43:41.707Z',
 evidence:'The Bears report that coach Ben Johnson announced Tyson Bagent will start in Green Bay; Caleb Williams remains officially Questionable.'
})]);
const denied=reason=>({known:false,eligible:false,reason});
function decide({name:playerName,team:ownTeam,opponent,kickoff,now=Date.now(),confirmations=CONFIRMATIONS}={}){
 const t=team(ownTeam),o=team(opponent),at=Date.parse(kickoff);
 if(!Array.isArray(confirmations))return denied('Published starter confirmations are malformed; starter not inferred.');
 const relevant=confirmations.filter(row=>team(row?.team)===t);
 if(!relevant.length)return null;
 if(typeof now!=='number'||!Number.isFinite(now))return denied('Current time is invalid; starter confirmation cannot be verified.');
 const active=relevant.filter(row=>Date.parse(row.kickoff)>now&&Date.parse(row.sourcePublishedAt)<=now);
 if(!o||!Number.isFinite(at))return active.length?denied('Exact opponent and kickoff are required to verify the announced starter.'):null;
 const matching=relevant.filter(row=>team(row.opponent)===o&&Date.parse(row.kickoff)===at);
 if(!matching.length)return null;
 if(at<=now)return denied('The confirmed starter game has already started; no new selection.');
 for(const row of matching){
  let source;try{source=new URL(row.sourceURL);}catch{return denied('Starter confirmation source is invalid; starter not inferred.');}
  const published=Date.parse(row.sourcePublishedAt);
  if(source.protocol!=='https:'||!name(row.starter)||!Number.isFinite(published)||published>now||published>=at)return denied('Starter confirmation lacks valid pregame provenance; starter not inferred.');
 }
 if(new Set(matching.map(row=>name(row.starter))).size!==1)return denied('Published game starter confirmations conflict; starter not inferred.');
 const record=matching[0],eligible=name(playerName)===name(record.starter);
 return {known:true,eligible,starter:record.starter,sourceURL:record.sourceURL,sourcePublishedAt:record.sourcePublishedAt,kickoff:record.kickoff,
  reason:eligible?record.starter+' is the officially announced starter for this game.':String(playerName)+' is not the announced starter; '+record.starter+' will start this game.'};
}
root.GoingDfsStarterConfirmations={CONFIRMATIONS,decide};
if(typeof module!=='undefined')module.exports=root.GoingDfsStarterConfirmations;
})(globalThis);
