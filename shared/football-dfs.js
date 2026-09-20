(function(root){
'use strict';

const RULES={
 draftkings:{label:'DraftKings Classic',cap:50000,maxTeam:8,receptionPoints:1,slots:['QB','RB','RB','WR','WR','WR','TE','FLEX','DST']},
 fanduel:{label:'FanDuel Main',cap:60000,maxTeam:4,receptionPoints:.5,slots:['QB','RB','RB','WR','WR','WR','TE','FLEX','DST']},
};
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const norm=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[.'’]/g,'').replace(/\s+(jr|sr|ii|iii|iv|v)\.?$/,'').replace(/[^a-z0-9]/g,'');
const canonicalTeam=value=>({JAC:'JAX',LAR:'LA',WSH:'WAS'})[String(value||'').trim().toUpperCase()]||String(value||'').trim().toUpperCase();
function csvRows(text){
 const rows=[];let row=[],field='',quoted=false;
 for(let i=0;i<String(text||'').length;i++){
  const char=text[i],next=text[i+1];
  if(char==='"'&&quoted&&next==='"'){field+='"';i++;}
  else if(char==='"')quoted=!quoted;
  else if(char===','&&!quoted){row.push(field);field='';}
  else if((char==='\n'||char==='\r')&&!quoted){if(char==='\r'&&next==='\n')i++;row.push(field);if(row.some(value=>value.trim()))rows.push(row);row=[];field='';}
  else field+=char;
 }
 row.push(field);if(row.some(value=>value.trim()))rows.push(row);return rows;
}
function value(record,...keys){for(const key of keys){const hit=Object.keys(record).find(header=>header.toLowerCase()===key.toLowerCase());if(hit&&record[hit]!==undefined)return record[hit];}return '';}
function gameTeams(raw){const match=String(raw||'').toUpperCase().match(/([A-Z]{2,4})\s*@\s*([A-Z]{2,4})/);return match?[canonicalTeam(match[1]),canonicalTeam(match[2])]:[];}
function parseSalaryCsv(text,requestedSite){
 const rows=csvRows(text);if(rows.length<2)return {site:requestedSite||null,players:[],errors:['No salary rows were found.']};
 const headers=rows[0].map(header=>header.trim().replace(/^\uFEFF/,'')),records=rows.slice(1).map(cells=>Object.fromEntries(headers.map((header,index)=>[header,(cells[index]||'').trim()])));
 const detected=headers.some(header=>/^name \+ id$/i.test(header)||/^roster position$/i.test(header))?'draftkings':headers.some(header=>/^nickname$/i.test(header)||/^fppg$/i.test(header))?'fanduel':null,site=requestedSite||detected;
 if(!RULES[site])return {site:null,players:[],errors:['Could not identify a DraftKings or FanDuel salary CSV.']};
 const players=[];
 for(const record of records){
  const suppliedName=value(record,'Name','Nickname','Name + ID'),name=(suppliedName||`${value(record,'First Name')} ${value(record,'Last Name')}`.trim()).replace(/\s*\(\d+\)\s*$/,''),rawPosition=(value(record,'Position','Roster Position').split('/')[0]||'').toUpperCase(),position=['D','DEF'].includes(rawPosition)?'DST':rawPosition,salary=Number(String(value(record,'Salary')).replace(/[$,]/g,'')),team=canonicalTeam(value(record,'TeamAbbrev','Team','Team Abbrev')),game=value(record,'Game Info','Game'),teams=gameTeams(game),opponent=canonicalTeam(value(record,'Opponent'))||(teams.find(candidate=>candidate!==team)||''),id=value(record,'ID','Id','Player ID')||norm(name)+'|'+team;
  const siteProjection=Number(value(record,'AvgPointsPerGame','FPPG','FPPG Played'))||null,injury=value(record,'Injury Indicator','Injury Status','Injury');
  if(!name||!finite(salary)||salary<=0||!['QB','RB','WR','TE','DST'].includes(position))continue;
  players.push({id:String(id),name,position,salary,team,opponent,game,siteProjection,injury,sourceRow:record});
 }
 const duplicateIds=new Set(),seen=new Set();for(const player of players){if(seen.has(player.id))duplicateIds.add(player.id);seen.add(player.id);}
 return {site,players:players.filter((player,index)=>players.findIndex(other=>other.id===player.id)===index),errors:[...(players.length?[]:['No supported NFL players were found in the CSV.']),...(duplicateIds.size?[`${duplicateIds.size} duplicate player IDs were collapsed.`]:[])]};
}
function projectedPoints(stats,site){
 const rule=RULES[site];if(!rule)return null;
 const get=key=>finite(stats?.[key])?stats[key]:0,bonuses=get('pass_300_probability')*3+get('rush_100_probability')*3+get('rec_100_probability')*3;
 return .04*get('pass_yds')+4*get('pass_tds')+.1*(get('rush_yds')+get('rec_yds'))+6*(get('rush_tds')+get('rec_tds'))+rule.receptionPoints*get('receptions')+bonuses;
}
function eligible(position,slot){return position===slot||(slot==='FLEX'&&['RB','WR','TE'].includes(position));}
function opponentConflict(lineup){
 const defense=lineup.find(player=>player.position==='DST');if(!defense)return 0;
 return lineup.filter(player=>player.position!=='DST'&&player.team===defense.opponent).length;
}
function correlation(lineup,mode){
 const qb=lineup.find(player=>player.position==='QB');if(!qb)return 0;
 const stack=lineup.some(player=>['WR','TE'].includes(player.position)&&player.team===qb.team),bringBack=lineup.some(player=>['RB','WR','TE'].includes(player.position)&&player.team===qb.opponent);
 return (stack?(mode==='ceiling'?1.1:.35):mode==='ceiling'?-1:0)+(stack&&bringBack&&mode==='ceiling'?.45:0)-1.25*opponentConflict(lineup);
}
function objective(player,mode){const projection=player.projection||0,sd=finite(player.sd)?player.sd:projection*.32;return mode==='floor'?projection-.18*sd:mode==='ceiling'?projection+.28*sd:projection;}
function optimize(players,{site='draftkings',mode='balanced',count=5,beamWidth=5000,minUnique=2}={}){
 const rule=RULES[site];if(!rule)return {lineups:[],reason:'Unsupported DFS platform.'};
 const available=players.filter(player=>finite(player.projection)&&player.projection>0&&finite(player.salary)&&player.salary>0&&!['o','out','ir'].includes(String(player.injury||'').toLowerCase())&&!player.unavailable);
 const bySlot=Object.fromEntries(rule.slots.map(slot=>[slot,available.filter(player=>eligible(player.position,slot)).sort((a,b)=>objective(b,mode)-objective(a,mode)).slice(0,slot==='FLEX'?90:60)]));
 const missing=[...new Set(rule.slots.filter(slot=>!bySlot[slot].length))];if(missing.length)return {lineups:[],reason:`No eligible ${missing.join(', ')} players were matched.`};
 let states=[{players:[],ids:new Set(),teams:{},salary:0,base:0}];
 for(const slot of rule.slots){
  const next=[];
  for(const state of states)for(const player of bySlot[slot]){
   if(state.ids.has(player.id)||state.salary+player.salary>rule.cap||(state.teams[player.team]||0)>=rule.maxTeam)continue;
   const ids=new Set(state.ids);ids.add(player.id);next.push({players:[...state.players,{...player,slot}],ids,teams:{...state.teams,[player.team]:(state.teams[player.team]||0)+1},salary:state.salary+player.salary,base:state.base+objective(player,mode)});
  }
  next.sort((a,b)=>b.base-a.base||b.salary-a.salary);states=next.slice(0,beamWidth);if(!states.length)return {lineups:[],reason:`No legal lineup fits the ${rule.label} salary cap.`};
 }
 const ranked=states.filter(state=>Object.keys(state.teams).length>=2).map(state=>({...state,projection:state.players.reduce((sum,player)=>sum+player.projection,0),objective:state.base+correlation(state.players,mode),conflicts:opponentConflict(state.players)})).sort((a,b)=>b.objective-a.objective||b.projection-a.projection||b.salary-a.salary);
 const lineups=[];for(const candidate of ranked){const ids=new Set(candidate.players.map(player=>player.id)),different=lineups.every(lineup=>lineup.players.filter(player=>!ids.has(player.id)).length>=minUnique);if(different)lineups.push(candidate);if(lineups.length>=Math.max(1,Math.min(20,count)))break;}
 return {lineups,reason:lineups.length?null:'No sufficiently distinct legal lineups were found.',eligible:available.length,rule};
}

root.GoingFootballDfs={RULES,norm,parseSalaryCsv,projectedPoints,optimize,correlation};
if(typeof module!=='undefined')module.exports=root.GoingFootballDfs;
})(globalThis);
