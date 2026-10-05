(function(root){
'use strict';

// Transparent descriptive tournament research helpers. No ownership model,
// covariance estimate, correlation bonus, or contest-win probability is implied.
const VERSION='dfs-tournament-research-v1';
const UPSIDE_SOURCE='observed-partial-fantasy-residual-v1';
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const text=value=>String(value==null?'':value).trim();
const teamKey=p=>text(p?.team).toUpperCase();
const opponentKey=p=>text(p?.opponent).toUpperCase();
const playerKey=p=>String(p?.id??`${text(p?.name)}|${teamKey(p)}`);
const role=p=>text(p?.position).toUpperCase();
const captainRole=p=>['CPT','MVP'].includes(text(p?.slot||p?.rosterPosition||p?.showdownRole).toUpperCase())||p?.captain===true;
function validUpside(player){
 const u=player?.upside;
 return u&&u.source===UPSIDE_SOURCE&&finite(u.value)&&u.value>=0&&Number.isInteger(u.n)&&u.n>=8&&Number.isInteger(u.currentGames)&&u.currentGames>=0&&u.currentGames<=u.n&&Number.isFinite(Date.parse(u.asOf))?u:null;
}

function playerObjective(player,options={}){
 const multiplier=finite(options)?options:(finite(options.multiplier)?options.multiplier:1);
 const projection=finite(player?.projection)?player.projection:null;
 const supplied=validUpside(player);
 const upside=supplied?supplied.value:null;
 const score=upside??projection;
 return {
  version:VERSION,
  score:finite(score)?score*multiplier:null,
  basis:upside==null?(projection==null?'unavailable':'projection-fallback'):'supplied-upside',
  projection:projection==null?null:projection*multiplier,
  upside:upside==null?null:upside*multiplier,
  ceilingStatus:upside==null?'unknown':'provided-unvalidated',
  upsideEvidence:supplied?{source:supplied.source,n:supplied.n,currentGames:supplied.currentGames,asOf:supplied.asOf}:null,
  multiplier
 };
}
function objective(player,options={}){return playerObjective(player,options).score;}

function evaluate(lineup,{contest='classic',site='draftkings'}={}){
 const players=Array.isArray(lineup)?lineup:[];
 const showdown=contest==='showdown';
 const qb=players.find(p=>role(p)==='QB');
 const captain=showdown?players.find(captainRole)||players[0]:null;
 const captainTeam=teamKey(captain);
 const captainPosition=role(captain);
 const captainPairs=captain?players.filter(p=>p!==captain).map(p=>({
  playerId:playerKey(p),name:text(p.name),team:teamKey(p),position:role(p),
  relation:teamKey(p)===captainTeam?'same-team':'opponent-or-other-team',
  interpretation:captainPosition==='WR'||captainPosition==='TE'?(role(p)==='QB'&&teamKey(p)===captainTeam?'positive-pass-correlation candidate':'unmodeled'):
   captainPosition==='QB'&&['WR','TE'].includes(role(p))&&teamKey(p)===captainTeam?'same-team-pass-catcher':
   captainPosition==='QB'&&teamKey(p)!==captainTeam?'opposing-player; game-script relation unmodeled':'unmodeled'
 })).filter(x=>x.playerId!==playerKey(captain)):[];
 const teams={};for(const p of players){const t=teamKey(p)||'UNKNOWN';teams[t]=(teams[t]||0)+1;}
 const gameIds=[...new Set(players.map(p=>text(p.gameId||p.game)).filter(Boolean))];
 const salaryUsed=players.reduce((sum,p)=>sum+(finite(p.salary)?p.salary:0),0);
 const objectiveRows=players.map(p=>({playerId:playerKey(p),...playerObjective(p,{multiplier:showdown&&p===captain?1.5:1})}));
 const objectiveValue=objectiveRows.some(row=>!finite(row.score))?null:objectiveRows.reduce((sum,row)=>sum+row.score,0);
 const cap=site==='fanduel'?60000:site==='draftkings'?50000:null;
 const salaryRemaining=cap==null?null:cap-salaryUsed;
 const classicStack=qb?players.filter(p=>p!==qb&&['WR','TE'].includes(role(p))&&teamKey(p)===teamKey(qb)):[];
 const classicBringbacks=qb?players.filter(p=>p!==qb&&['RB','WR','TE'].includes(role(p))&&teamKey(p)===opponentKey(qb)):[];
 const dst=players.find(p=>role(p)==='DST');
 const dstConflicts=dst?players.filter(p=>role(p)!=='DST'&&teamKey(p)===opponentKey(dst)):[];
 return {
  version:VERSION,contest,site,
  format:{type:showdown?'single-game':'multi-game',gameIds,gameCount:gameIds.length},
  classic:showdown?null:{
   qb:qb?playerKey(qb):null,
   sameTeamPassCatchers:classicStack.map(playerKey),
   stackSize:classicStack.length,
   bringBacks:classicBringbacks.map(playerKey),
   dst:dst?playerKey(dst):null,
   dstOpposingOffenseConflicts:dstConflicts.map(playerKey)
  },
  showdown:showdown?{
   captain:captain?playerKey(captain):null,
   captainPosition:captainPosition||null,
   captainTeam:captainTeam||null,
   captainPairings:captainPairs,
   teamComposition:teams
  }:null,
  salary:{cap,salaryUsed,salaryRemaining,interpretation:'context-only; no uniqueness inference'},
  objective:{value:objectiveValue,basis:objectiveRows.some(row=>row.basis==='supplied-upside')?'sum-of-player-upside-with-projection-fallback':'sum-of-available-projections',jointCeiling:'not-estimated',coverage:{provided:objectiveRows.filter(row=>row.basis==='supplied-upside').length,missing:objectiveRows.filter(row=>row.basis!=='supplied-upside').length,players:objectiveRows}},
  ownership:{status:'unknown',values:null,uniqueness:'unknown'},
  ceiling:{status:players.every(p=>validUpside(p))?'provided-unvalidated':'unknown-with-projection-fallback',source:'caller-supplied observed-partial-fantasy-residual-v1 only; no estimate is created'},
  constraints:{hardCorrelationRules:[],hardOwnershipRules:[],hardSalaryRemainingRules:[]},
  limitations:['Descriptive construction context only; no fitted player covariance, ownership, duplication, field or win-probability model.','Classic stack and bring-back labels describe roster relationships and do not claim measured correlation.','Showdown pair labels are qualitative roster relationships, not estimated joint outcomes.','Salary remaining alone does not establish lineup uniqueness.']
 };
}

function constructionTie(lineup,contest){
 const qb=lineup.find(p=>role(p)==='QB');
 if(contest==='showdown'){
  const captain=lineup.find(captainRole)||lineup[0];
  return {preferred:captainPositionHasPassCatchers(captain,lineup)?1:0};
 }
 const stack=qb?lineup.filter(p=>p!==qb&&['WR','TE'].includes(role(p))&&teamKey(p)===teamKey(qb)).length:0;
 const bringback=qb?lineup.some(p=>teamKey(p)===opponentKey(qb)&&['RB','WR','TE'].includes(role(p))):false;
 return {preferred:stack>=2?2:stack===1?1:0,stack,bringback};
}
function captainPositionHasPassCatchers(captain,lineup){return !!captain&&['WR','TE'].includes(role(captain))&&lineup.some(p=>p!==captain&&role(p)==='QB'&&teamKey(p)===teamKey(captain));}
function compare(a,b,{contest='classic'}={}){
 const rows=[a,b].map(lineup=>{
  const players=Array.isArray(lineup)?lineup:lineup?.lineup||[];
  const captain=contest==='showdown'?players.find(p=>['CPT','MVP'].includes(text(p?.slot||p?.rosterPosition).toUpperCase())||p?.captain===true)||players[0]:null;
  const values=players.map(p=>playerObjective(p,{multiplier:contest==='showdown'&&p===captain?1.5:1}).score);
  const total=values.some(v=>!finite(v))?null:values.reduce((sum,v)=>sum+v,0);
  const covered=players.filter(p=>validUpside(p)).length;
  return {lineup:players,score:total,upsideCovered:covered,playerCount:players.length,basis:covered===players.length&&players.length?'provided-upside':'projection-fallback',ceilingStatus:covered===players.length&&players.length?'provided-unvalidated':'partially-unknown'};
 });
 // Stable, explicit comparison; it ranks sums of caller-supplied player values,
 // not a joint lineup quantile or tournament equity estimate.
 for(const row of rows)row.tie=constructionTie(row.lineup,contest);
 const ordered=rows.slice().sort((x,y)=>(finite(y.score)?y.score:-Infinity)-(finite(x.score)?x.score:-Infinity)||(y.tie.preferred||0)-(x.tie.preferred||0));
 return {version:VERSION,contest,method:ordered.some(x=>x.upsideCovered)?'sum-of-player-upside-with-projection-fallback':'sum-of-available-projections',jointCeiling:'not-estimated',tieBreak:'construction descriptor only; used only for exact objective ties',ranked:ordered.map(x=>({score:x.score,basis:x.basis,ceilingStatus:x.ceilingStatus,upsideCovered:x.upsideCovered,playerCount:x.playerCount,constructionTie:x.tie,lineup:x.lineup}))};
}

const api={VERSION,UPSIDE_SOURCE,objective,playerObjective,evaluate,compare};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.GoingDfsTournament=api;
})(typeof globalThis!=='undefined'?globalThis:this);
