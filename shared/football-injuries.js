(function(root){
'use strict';

const VERSION='injury-role-3';
const MAX_AGE_HOURS=36;
const HARD_OUT=new Set(['out','ir','pup','inactive','suspended','nfi','reserve']);
const MARKET_ROLE={
 RB:{rush_yds:[.45,.30],rush_tds:[.40,.28],rec_yds:[.25,.20],receptions:[.25,.20],rec_tds:[.22,.18],atd:[.35,.25],first_td:[.25,.20]},
 WR:{rec_yds:[.25,.18],receptions:[.25,.18],rec_tds:[.20,.15],rush_yds:[.15,.12],rush_tds:[.12,.10],atd:[.20,.15],first_td:[.15,.12]},
 TE:{rec_yds:[.25,.18],receptions:[.25,.18],rec_tds:[.20,.15],atd:[.20,.15],first_td:[.15,.12]},
};
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
function normalize(value){
 return String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[.'’]/g,'').replace(/-/g,' ').replace(/\s+(jr|sr|ii|iii|iv|v)\.?$/,'').replace(/[^a-z0-9]/g,'');
}
function team(value){return ({LAR:'LA',JAC:'JAX',WSH:'WAS',OAK:'LV',SD:'LAC',STL:'LA'})[String(value||'').toUpperCase()]||String(value||'').toUpperCase();}
function cleanStatus(value){return String(value||'').trim().toLowerCase().replace(/[_-]+/g,' ');}
function bodyGroup(value){
 const text=cleanStatus(value);if(!text||text.includes('not injury')||['rest','illness','personal'].includes(text))return null;
 const groups={hamstring:['hamstring'],ankle:['ankle'],knee:['knee'],hip:['hip'],groin:['groin'],foot:['foot'],toe:['toe'],calf:['calf'],quad:['quadricep','quad'],back:['back'],shoulder:['shoulder'],concussion:['concussion','head'],chest_rib:['rib','chest','sternum'],hand_wrist:['hand','wrist','finger','thumb'],elbow:['elbow'],achilles:['achilles'],neck:['neck']};
 return Object.entries(groups).find(([,terms])=>terms.some(term=>text.includes(term)))?.[0]||'other';
}
function depthOrder(player){const raw=player?.depth_chart_order;if(raw===null||raw===undefined||raw==='')return null;const value=Number(raw);return Number.isFinite(value)?value:null;}
function availability(player){
 const injury=cleanStatus(player?.injury_status),status=cleanStatus(player?.status),practice=cleanStatus(player?.practice_participation||player?.practice_description);
 const values=[injury,status];
 if(values.some(value=>HARD_OUT.has(value)||value.startsWith('injured reserve')||value==='physically unable to perform'))return {state:'out',label:player.injury_status||player.status||'Out',scale:0,uncertainty:1,block:true};
 if(values.some(value=>value==='doubtful'))return {state:'doubtful',label:player.injury_status||'Doubtful',scale:.40,uncertainty:1.25,block:true};
 if(values.some(value=>value==='questionable'))return {state:'questionable',label:player.injury_status||'Questionable',scale:.88,uncertainty:1.15,block:false};
 if(values.some(value=>value==='probable'))return {state:'probable',label:player.injury_status||'Probable',scale:.98,uncertainty:1.04,block:false};
 const hasInjury=Boolean(player?.injury_body_part||player?.injury_notes||injury);
 if(hasInjury&&(practice.includes('did not')||practice==='dnp'))return {state:'practice_dnp',label:'Did not practice',scale:.88,uncertainty:1.15,block:false};
 if(hasInjury&&practice.includes('limited'))return {state:'limited',label:'Limited practice',scale:.94,uncertainty:1.10,block:false};
 return {state:'available',label:'No current designation',scale:1,uncertainty:1,block:false};
}
function scaleModel(model,scale,uncertainty=1){
 const next={...model,injury_scale:scale,injury_uncertainty:uncertainty};
 if(model.family==='bernoulli'){
  const probability=clamp((model.probability??model.mean??0)*scale,0,.999);
  return {...next,probability,mean:probability,sd:Math.sqrt(probability*(1-probability))};
 }
 if(model.family==='poisson'){
  const lambda=Math.max(0,(model.lambda??model.mean??0)*scale),sd=finite(model.sd)?model.sd*scale*uncertainty:Math.sqrt(lambda)*uncertainty;
  return {...next,lambda,mean:lambda,sd};
 }
 if(model.family==='lognormal'){
  const mean=Math.max(0,(model.mean??0)*scale),sd=finite(model.sd)?Math.max(0,model.sd*scale*uncertainty):null;
  if(mean>0&&finite(sd)){
   const variance=Math.log1p((sd/mean)**2);
   return {...next,mean,sd,mu_log:Math.log(mean)-variance/2,sigma_log:Math.sqrt(variance),nonpositive:(model.nonpositive||[]).map(value=>Math.round(value*scale))};
  }
  return {...next,mean,sd};
 }
 return {...next,mean:finite(model.mean)?model.mean*scale:model.mean,sd:finite(model.sd)?model.sd*scale*uncertainty:model.sd};
}
function createContext(snapshot,profiles={},now=Date.now(),evidence=null){
 const generatedAt=snapshot?.generated_at,ageHours=(now-Date.parse(generatedAt))/3600000,fresh=Number.isFinite(ageHours)&&ageHours>=-.25&&ageHours<=MAX_AGE_HOURS;
 const roleRows=evidence?.current_players||{},reportRows=evidence?.current_reports||{},base=(snapshot?.players||[]).filter(player=>player?.name&&player?.team),players=base.map(player=>{const identity=team(player.team)+'|'+normalize(player.name),role=roleRows[identity],report=reportRows[identity];return {...player,depth_chart_order:role?.role_order??player.depth_chart_order,depth_chart_position:role?.position??player.depth_chart_position,_usage:role||null,_injuryBodyGroup:report?.body_part||null,injury_status:report?.report_status||player.injury_status,injury_body_part:report?.primary_injury||player.injury_body_part,practice_description:report?.practice_status||player.practice_description};});
 const identities=new Set(players.map(player=>team(player.team)+'|'+normalize(player.name)));for(const [identity,report] of Object.entries(reportRows)){if(identities.has(identity)||!report?.name||!report?.team||!report?.position)continue;const role=roleRows[identity];players.push({name:report.name,team:report.team,pos:report.position,status:role?.roster_status||'ACT',depth_chart_order:role?.role_order??null,depth_chart_position:report.position,injury_status:report.report_status,injury_body_part:report.primary_injury,practice_description:report.practice_status,_usage:role||null,_injuryBodyGroup:report.body_part||null});}
 const byIdentity=new Map(),byTeamPosition=new Map(),profileByIdentity=new Map();
 for(const player of players){
  const identity=team(player.team)+'|'+normalize(player.name);byIdentity.set(identity,player);
  const key=team(player.team)+'|'+String(player.pos||'').toUpperCase();if(!byTeamPosition.has(key))byTeamPosition.set(key,[]);byTeamPosition.get(key).push(player);
 }
 for(const profile of Object.values(profiles||{}))profileByIdentity.set(team(profile.team)+'|'+normalize(profile.name),profile);
 for(const rows of byTeamPosition.values())rows.sort((a,b)=>(depthOrder(a)??99)-(depthOrder(b)??99)||String(a.name).localeCompare(String(b.name)));
 return {version:VERSION,generatedAt,ageHours,fresh,byIdentity,byTeamPosition,profileByIdentity,evidence,effects:evidence?.effects||{},qbTendencies:evidence?.qb_tendencies||{},defenseScheme:evidence?.defense_scheme||{}};
}
function starterEligibility({name,team:teamCode,position,context}){
 if(String(position||'').toUpperCase()!=='QB')return {known:false,eligible:true,reason:'Starter filtering applies only to quarterbacks.'};
 if(!context?.fresh)return {known:false,eligible:true,reason:'Fresh depth-chart data is unavailable; starter status was not inferred.'};
 const player=context.byIdentity.get(team(teamCode)+'|'+normalize(name));if(!player)return {known:false,eligible:true,reason:'Quarterback is not matched to the current roster snapshot.'};
 const quarterbacks=context.byTeamPosition.get(team(teamCode)+'|QB')||[],starter=quarterbacks.find(candidate=>!availability(candidate).block);
 if(!starter)return {known:false,eligible:false,reason:'No available starting quarterback is identified in the current depth chart.'};
 const eligible=normalize(starter.name)===normalize(player.name);return {known:true,eligible,starter:starter.name,depthOrder:depthOrder(player),reason:eligible?`${starter.name} is the first available quarterback on the current depth chart.`:`${player.name} is behind ${starter.name} on the current depth chart.`};
}
function historicalEffect(player,position,market,state,context){
 const body=player?._injuryBodyGroup||bodyGroup(player?.injury_body_part||player?.injury_notes),effects=context?.effects||{};if(!body||!state||state==='available')return null;
 const exact=effects[[position,body,state,market].join('|')],fallback=effects[[position,'*',state,market].join('|')],effect=exact?.sample>=3?exact:fallback?.sample>=20?fallback:null;
 return effect?{...effect,bodyPart:body,fallback:effect===fallback}:null;
}
function nextRoleBoost(player,market,model,context,opponent){
 const position=String(player?.pos||'').toUpperCase(),rule=MARKET_ROLE[position]?.[market];
 const currentOrder=depthOrder(player);
 if(!rule||currentOrder===null||availability(player).state!=='available')return null;
 const teammates=context.byTeamPosition.get(team(player.team)+'|'+position)||[];
 const outs=teammates.filter(row=>depthOrder(row)!==null&&depthOrder(row)<currentOrder&&availability(row).state==='out');
 if(!outs.length)return null;
 const nearestOut=outs.sort((a,b)=>depthOrder(b)-depthOrder(a))[0];
 const candidates=teammates.filter(row=>depthOrder(row)!==null&&depthOrder(row)>depthOrder(nearestOut)&&availability(row).state==='available').sort((a,b)=>depthOrder(a)-depthOrder(b)).slice(0,position==='RB'?2:3);
 const opportunityKey=market.startsWith('rush')?'rush_share':'target_share',scores=candidates.map(row=>{const usage=row._usage||{},opportunity=finite(usage[opportunityKey])?usage[opportunityKey]:0,snap=finite(usage.snap_share)?usage.snap_share:0;return {row,score:.7*opportunity+.3*snap};});const total=scores.reduce((sum,row)=>sum+row.score,0),selected=scores.find(row=>normalize(row.row.name)===normalize(player.name));if(!selected)return null;let allocation;if(total)allocation=selected.score/total;else{if(selected!==scores[0])return null;allocation=1;}
 const absentProfile=context.profileByIdentity.get(team(nearestOut.team)+'|'+normalize(nearestOut.name)),absentModel=absentProfile?.stats?.[market];
 if(!finite(absentModel?.mean)||absentModel.mean<=0||!finite(model?.mean)||model.mean<=0)return null;
 const [transfer,cap]=rule,qb=context.qbTendencies?.[team(player.team)],targetRate=qb?.target_rate_by_position?.[position],roleEvidence=finite(player._usage?.[opportunityKey])?`${Math.round(100*player._usage[opportunityKey])}% current ${opportunityKey.replace('_',' ')}`:finite(player._usage?.snap_share)?`${Math.round(100*player._usage.snap_share)}% current snap share`:'depth order only',qbEvidence=finite(targetRate)?`; ${qb.qb_name||'current QB'} targets ${position}s on ${Math.round(100*targetRate)}% of recorded targets (n=${qb.targets})`:'';
 let schemeFactor=1,schemeEvidence='';const defense=context.defenseScheme?.[team(opponent)],blitz=qb?.blitz_splits?.blitz,nonBlitz=qb?.blitz_splits?.non_blitz,baseline=qb?.targets_per_dropback_by_position?.[position],blitzRate=defense?.blitz_rate,blitzTarget=blitz?.target_rate_by_position?.[position],nonBlitzTarget=nonBlitz?.target_rate_by_position?.[position];
 if(['rec_yds','receptions','rec_tds'].includes(market)&&defense?.supported_for_model&&qb?.supported_for_model&&blitz?.dropbacks>=20&&nonBlitz?.dropbacks>=20&&finite(baseline)&&baseline>0&&finite(blitzRate)&&finite(blitzTarget)&&finite(nonBlitzTarget)){const expected=blitzRate*blitzTarget+(1-blitzRate)*nonBlitzTarget;schemeFactor=clamp(expected/baseline,.9,1.1);schemeEvidence=`; ${team(opponent)} blitz mix changes the supported ${position} target tendency by ${Math.round(100*(schemeFactor-1))}%`;}
 const added=Math.min(model.mean*cap,absentModel.mean*transfer*allocation*schemeFactor),scale=1+added/model.mean;
 return {scale,uncertainty:1.10,added,cap,transfer:transfer*allocation,allocation,schemeFactor,players:[nearestOut.name],reason:`Replacement share behind ${nearestOut.name} (${nearestOut.injury_status||nearestOut.status||'Out'}): ${roleEvidence}${qbEvidence}${schemeEvidence}`};
}
function adjustModel({model,name,team:teamCode,position,market,context,opponent=null}){
 if(!model||model.status!=='ready'||!context)return {model,injury:null};
 const player=context.byIdentity.get(team(teamCode)+'|'+normalize(name));
 if(!player)return {model,injury:null};
 const state=availability(player),effect=historicalEffect(player,String(player.pos||position||'').toUpperCase(),market,state.state,context),stateScale=effect?.scale??state.scale,base={version:VERSION,source:effect?'NFLverse official injury reports and historical played-through cohort':'Sleeper roster/injury feed',updatedAt:context.generatedAt,status:state.label,state:state.state,bodyPart:player.injury_body_part||null,practice:player.practice_description||player.practice_participation||null,depthOrder:depthOrder(player),position:player.depth_chart_position||player.pos||position||null,blockRecommendation:state.block,stale:!context.fresh,historicalEffect:effect};
 if(!context.fresh)return {model,injury:{...base,applied:false,reason:'Roster snapshot is stale; no projection adjustment was applied.'}};
 if(state.state==='out')return {model:{...model,status:'unavailable',mean:null,sd:null,injury_scale:0},injury:{...base,applied:true,projectionScale:0,reason:'Confirmed unavailable; removed from modeled betting recommendations.'}};
 let adjusted=model,totalScale=stateScale,uncertainty=state.uncertainty,parts=[];
 if(effect)parts.push(`Historical ${effect.bodyPart.replace('_',' ')}/${state.state} cohort ${(100*(effect.scale-1)).toFixed(0)}% (n=${effect.sample}, ${effect.confidence}${effect.fallback?', position fallback':''})`);
 else if(state.scale!==1)parts.push(`${state.label} availability adjustment ${(100*(state.scale-1)).toFixed(0)}% (cohort unavailable)`);
 const boost=nextRoleBoost(player,market,model,context,opponent);
 if(boost){totalScale*=boost.scale;uncertainty*=boost.uncertainty;parts.push(`${boost.reason}; capped role reallocation +${(100*(boost.scale-1)).toFixed(0)}%`);}
 if(totalScale!==1||uncertainty!==1)adjusted=scaleModel(model,totalScale,uncertainty);
 if(!parts.length)return {model,injury:null};
 return {model:adjusted,injury:{...base,applied:true,projectionScale:totalScale,uncertaintyMultiplier:uncertainty,roleBoost:boost?{scale:boost.scale,added:boost.added,allocation:boost.allocation,schemeFactor:boost.schemeFactor,players:boost.players}:null,reason:parts.join(' · ')}};
}

root.GoingFootballInjuries={VERSION,MAX_AGE_HOURS,normalize,availability,scaleModel,createContext,starterEligibility,adjustModel,bodyGroup};
if(typeof module!=='undefined')module.exports=root.GoingFootballInjuries;
})(globalThis);
