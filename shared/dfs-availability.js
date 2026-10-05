(function(root){
'use strict';

const VERSION='dfs-availability-v1';
const base=root.GoingFootballInjuries||(typeof require==='function'?require('./football-injuries.js'):null);
const NONACTIVE=new Set(['o','out','ir','pup','inactive','suspended','nfi','reserve','ina','res','dev','cut','ret','exe','development','retired','exempt']);
const ACTIVE=new Set(['act','active','active roster','healthy','available']);
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const clean=value=>String(value||'').trim().toLowerCase().replace(/[_-]+/g,' ');
const canonicalTeam=value=>({LAR:'LA',JAC:'JAX',WSH:'WAS',OAK:'LV',SD:'LAC',STL:'LA'})[String(value||'').toUpperCase()]||String(value||'').toUpperCase();
if(!base)throw Error('The base football injury adapter is required.');

function createContext(snapshot,profiles={},now=Date.now(),evidence=null){
 const normalized={...snapshot,players:(snapshot?.players||[]).map(player=>({...player,
  roster_status:player.roster_status||player.status,
  status:player.roster_status||player.status,
  pos:player.position||player.pos,
  injury_status:player.injury_status||player.injury,
 }))};
 const context=base.createContext(normalized,profiles,now,evidence),roles=evidence?.current_players||{},baseByIdentity=new Map(normalized.players.map(player=>[canonicalTeam(player.team)+'|'+base.normalize(player.name),player]));
 for(const [identity,player] of context.byIdentity){
  const role=roles[identity],source=baseByIdentity.get(identity);
  if(role?.roster_status!=null){player.roster_status=role.roster_status;player.status=role.roster_status;}
  if(!finite(role?.role_order)&&finite(source?.depth_chart_order))player.depth_chart_order=source.depth_chart_order;
 }
 return context;
}

function availability(player){
 const rosterStatus=clean(player?.roster_status||player?.status),rawInjury=clean(player?.injury_status||player?.injury),injuryStatus=({q:'questionable',d:'doubtful',p:'probable'})[rawInjury]||rawInjury,statuses=[rosterStatus,injuryStatus];
 const blocking=statuses.find(status=>NONACTIVE.has(status)||status.startsWith('injured reserve')||status==='physically unable to perform');
 if(blocking)return {state:'out',label:blocking.toUpperCase(),scale:0,uncertainty:1,block:true};
 const knownRoster=!rosterStatus||ACTIVE.has(rosterStatus);
 const medicalStatus=['doubtful','questionable','probable'].includes(rosterStatus)&&!injuryStatus?rosterStatus:null;
 const adapted={...player,injury_status:medicalStatus||injuryStatus};
 const result=base.availability(knownRoster?adapted:{...adapted,status:'ACT'});
 if(result.state!=='available')return result;
 if(rosterStatus&&!knownRoster)return {state:'unknown',label:player?.roster_status||player?.status,scale:1,uncertainty:1,block:false};
 return result;
}

function starterEligibility({name,team,position,context}){
 if(String(position||'').toUpperCase()!=='QB')return {known:false,eligible:true,reason:'Starter filtering applies only to quarterbacks.'};
 if(!context?.fresh)return {known:false,eligible:false,reason:'Fresh depth-chart data is unavailable; a starting quarterback was not inferred.'};
 const canonical=canonicalTeam(team),key=canonical+'|'+base.normalize(name),player=context.byIdentity.get(key);
 if(!player)return {known:false,eligible:false,reason:'Quarterback is not matched to the current roster snapshot.'};
 const order=candidate=>finite(candidate?._usage?.role_order)?candidate._usage.role_order:candidate?.depth_chart_order;
 const quarterbacks=(context.byTeamPosition.get(canonical+'|QB')||[]).filter(candidate=>finite(order(candidate))&&!availability(candidate).block).sort((a,b)=>order(a)-order(b));
 if(!quarterbacks.length)return {known:false,eligible:false,reason:'No active quarterback with a verified depth role is identified.'};
 if(quarterbacks.length>1&&order(quarterbacks[0])===order(quarterbacks[1]))return {known:false,eligible:false,reason:'Quarterback depth order is ambiguous; a starter was not inferred.'};
 const first=quarterbacks[0],eligible=base.normalize(first.name)===base.normalize(player.name);
 return {known:true,eligible,starter:first.name,depthOrder:order(player),reason:eligible?`${first.name} is the first available quarterback on the current depth chart.`:`${player.name} is behind ${first.name} on the current depth chart.`};
}

root.GoingDfsAvailability={VERSION,normalize:base.normalize,createContext,availability,starterEligibility};
if(typeof module!=='undefined')module.exports=root.GoingDfsAvailability;
})(globalThis);
