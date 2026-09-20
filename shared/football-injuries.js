(function(root){
'use strict';

const VERSION='injury-role-1';
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
function createContext(snapshot,profiles={},now=Date.now()){
 const generatedAt=snapshot?.generated_at,ageHours=(now-Date.parse(generatedAt))/3600000,fresh=Number.isFinite(ageHours)&&ageHours>=-.25&&ageHours<=MAX_AGE_HOURS;
 const players=(snapshot?.players||[]).filter(player=>player?.name&&player?.team);
 const byIdentity=new Map(),byTeamPosition=new Map(),profileByIdentity=new Map();
 for(const player of players){
  const identity=team(player.team)+'|'+normalize(player.name);byIdentity.set(identity,player);
  const key=team(player.team)+'|'+String(player.pos||'').toUpperCase();if(!byTeamPosition.has(key))byTeamPosition.set(key,[]);byTeamPosition.get(key).push(player);
 }
 for(const profile of Object.values(profiles||{}))profileByIdentity.set(team(profile.team)+'|'+normalize(profile.name),profile);
 for(const rows of byTeamPosition.values())rows.sort((a,b)=>(depthOrder(a)??99)-(depthOrder(b)??99)||String(a.name).localeCompare(String(b.name)));
 return {version:VERSION,generatedAt,ageHours,fresh,byIdentity,byTeamPosition,profileByIdentity};
}
function nextRoleBoost(player,market,model,context){
 const position=String(player?.pos||'').toUpperCase(),rule=MARKET_ROLE[position]?.[market];
 const currentOrder=depthOrder(player);
 if(!rule||currentOrder===null||availability(player).state!=='available')return null;
 const teammates=context.byTeamPosition.get(team(player.team)+'|'+position)||[];
 const outs=teammates.filter(row=>depthOrder(row)!==null&&depthOrder(row)<currentOrder&&availability(row).state==='out');
 if(!outs.length)return null;
 const nearestOut=outs.sort((a,b)=>depthOrder(b)-depthOrder(a))[0];
 const nextHealthy=teammates.filter(row=>depthOrder(row)!==null&&depthOrder(row)>depthOrder(nearestOut)&&availability(row).state==='available').sort((a,b)=>depthOrder(a)-depthOrder(b))[0];
 if(!nextHealthy||normalize(nextHealthy.name)!==normalize(player.name))return null;
 const absentProfile=context.profileByIdentity.get(team(nearestOut.team)+'|'+normalize(nearestOut.name)),absentModel=absentProfile?.stats?.[market];
 if(!finite(absentModel?.mean)||absentModel.mean<=0||!finite(model?.mean)||model.mean<=0)return null;
 const [transfer,cap]=rule,added=Math.min(model.mean*cap,absentModel.mean*transfer),scale=1+added/model.mean;
 return {scale,uncertainty:1.10,added,cap,transfer,players:[nearestOut.name],reason:`Next healthy ${position} behind ${nearestOut.name} (${nearestOut.injury_status||nearestOut.status||'Out'})`};
}
function adjustModel({model,name,team:teamCode,position,market,context}){
 if(!model||model.status!=='ready'||!context)return {model,injury:null};
 const player=context.byIdentity.get(team(teamCode)+'|'+normalize(name));
 if(!player)return {model,injury:null};
 const state=availability(player),base={version:VERSION,source:'Sleeper roster/injury feed',updatedAt:context.generatedAt,status:state.label,state:state.state,bodyPart:player.injury_body_part||null,practice:player.practice_description||player.practice_participation||null,depthOrder:depthOrder(player),position:player.depth_chart_position||player.pos||position||null,blockRecommendation:state.block,stale:!context.fresh};
 if(!context.fresh)return {model,injury:{...base,applied:false,reason:'Roster snapshot is stale; no projection adjustment was applied.'}};
 if(state.state==='out')return {model:{...model,status:'unavailable',mean:null,sd:null,injury_scale:0},injury:{...base,applied:true,projectionScale:0,reason:'Confirmed unavailable; removed from modeled betting recommendations.'}};
 let adjusted=model,totalScale=state.scale,uncertainty=state.uncertainty,parts=[];
 if(state.scale!==1)parts.push(`${state.label} availability adjustment ${(100*(state.scale-1)).toFixed(0)}%`);
 const boost=nextRoleBoost(player,market,model,context);
 if(boost){totalScale*=boost.scale;uncertainty*=boost.uncertainty;parts.push(`${boost.reason}; capped role reallocation +${(100*(boost.scale-1)).toFixed(0)}%`);}
 if(totalScale!==1||uncertainty!==1)adjusted=scaleModel(model,totalScale,uncertainty);
 if(!parts.length)return {model,injury:null};
 return {model:adjusted,injury:{...base,applied:true,projectionScale:totalScale,uncertaintyMultiplier:uncertainty,roleBoost:boost?{scale:boost.scale,added:boost.added,players:boost.players}:null,reason:parts.join(' · ')}};
}

root.GoingFootballInjuries={VERSION,MAX_AGE_HOURS,normalize,availability,scaleModel,createContext,adjustModel};
if(typeof module!=='undefined')module.exports=root.GoingFootballInjuries;
})(globalThis);
