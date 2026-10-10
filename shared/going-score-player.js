(function(root){
'use strict';
// Reference helpers over data/going_score.json (schema going-score-v2). Display and sorting only.
// A GOING Score is a player-level situation index (opportunity, role, availability, trend). It is not a projection,
// a probability or a betting edge: a higher score is not a better bet.
const SCHEMA='going-score-v2';
const POSITIONS=['QB','RB','WR','TE'];
const TIER_ORDER={elite:4,strong:3,solid:2,modest:1,low:0};
const SCORED=['opportunity','team_share','efficiency','role','availability','opp_trend','role_trend'];
const finite=v=>typeof v==='number'&&Number.isFinite(v);

function load(doc){
 if(!doc||doc.schema!==SCHEMA||typeof doc.players!=='object')return {ok:false,players:[],meta:null,reason:'unsupported or missing going-score-v2 document'};
 const players=Object.entries(doc.players).map(([id,p])=>({id,...p}));
 return {ok:true,players,byId:Object.fromEntries(players.map(p=>[p.id,p])),meta:{availability:doc.availability||null,methodology_version:doc.methodology_version,as_of:doc.as_of,season:doc.season,week:doc.week,meaning:doc.meaning,counts:doc.counts,weights:doc.weights}};
}
function hasFlag(player,flag){return (player.flags||[]).some(f=>f===flag||f.startsWith(flag+':'));}
function filter(players,opts={}){
 const {position,team,tier,minScore,maxScore,minAbsolute,flag,excludeFlag,search}=opts;
 const needle=search?String(search).toLowerCase():null;
 return players.filter(p=>
  (!position||p.position===position)&&(!team||p.team===team)&&(!tier||p.tier?.id===tier)&&
  (!finite(minScore)||p.score>=minScore)&&(!finite(maxScore)||p.score<=maxScore)&&(!finite(minAbsolute)||p.absolute>=minAbsolute)&&
  (!flag||hasFlag(p,flag))&&(!excludeFlag||!hasFlag(p,excludeFlag))&&(!needle||String(p.name||'').toLowerCase().includes(needle)));
}
const SORTS={
 score:p=>p.score,absolute:p=>p.absolute,delta_1w:p=>p.delta_1w,delta_3w:p=>p.delta_3w,
 opportunity:p=>p.components?.opportunity?.raw,availability:p=>p.components?.availability?.raw,
};
function rank(players,by='score',dir='desc'){
 const get=SORTS[by]||SORTS.score,sign=dir==='asc'?1:-1;
 // Rows with no value always sort last; ties break on name for a stable, deterministic order.
 return [...players].sort((a,b)=>{
  const x=get(a),y=get(b);
  if(!finite(x)&&!finite(y))return String(a.name).localeCompare(String(b.name));
  if(!finite(x))return 1;if(!finite(y))return -1;
  return sign*(x-y)||String(a.name).localeCompare(String(b.name));
 }).map((p,i)=>({...p,listRank:i+1}));
}
function movers(players,{window='delta_3w',limit=10,minAbsChange=5}={}){
 const have=players.filter(p=>finite(p[window]));
 return {
  risers:rank(have.filter(p=>p[window]>=minAbsChange),window,'desc').slice(0,limit),
  fallers:rank(have.filter(p=>p[window]<=-minAbsChange),window,'asc').slice(0,limit),
 };
}
function contributions(player){
 return SCORED.map(key=>({key,...(player.components?.[key]||{})})).filter(c=>finite(c.contribution))
  .sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution));
}
function drivers(player,n=2){
 const rows=contributions(player);
 return {up:rows.filter(c=>c.contribution>0).slice(0,n),down:rows.filter(c=>c.contribution<0).slice(0,n)};
}
function compare(a,b){
 if(!a||!b)return null;
 const rows=SCORED.map(key=>{
  const x=a.components?.[key],y=b.components?.[key];
  return {key,aPercentile:x?.percentile??null,bPercentile:y?.percentile??null,aContribution:x?.contribution??null,bContribution:y?.contribution??null,
   edgeContribution:finite(x?.contribution)&&finite(y?.contribution)?Math.round(1e4*(x.contribution-y.contribution))/1e4:null};
 });
 const samePosition=a.position===b.position;
 return {samePosition,
  note:samePosition?'Both scores are percentiles within the same position.':'Scores are position percentiles; compare absolute (0-100) across positions only loosely.',
  scoreGap:finite(a.score)&&finite(b.score)?Math.round(10*(a.score-b.score))/10:null,
  absoluteGap:finite(a.absolute)&&finite(b.absolute)?Math.round(10*(a.absolute-b.absolute))/10:null,
  components:rows};
}
function groupByTier(players){
 const groups={};for(const p of players){const id=p.tier?.id||'unrated';(groups[id]=groups[id]||[]).push(p);}
 return Object.entries(groups).sort((a,b)=>(TIER_ORDER[b[0]]??-1)-(TIER_ORDER[a[0]]??-1)).map(([id,rows])=>({id,label:rows[0].tier?.label||'Unrated',players:rank(rows)}));
}
// Plain-language one-liner built only from the stored components.
function summary(player){
 const {up,down}=drivers(player,1);
 const parts=[`${player.tier?.label||'Unrated'} (${player.score} pct, ${player.position})`];
 if(up[0])parts.push(`lifted by ${up[0].key.replace('_',' ')}`);
 if(down[0])parts.push(`held back by ${down[0].key.replace('_',' ')}`);
 if((player.flags||[]).length)parts.push(player.flags.join(', '));
 return parts.join('; ');
}
root.GoingScorePlayer={SCHEMA,POSITIONS,SCORED,load,filter,rank,movers,contributions,drivers,compare,groupByTier,summary,hasFlag};
if(typeof module!=='undefined')module.exports=root.GoingScorePlayer;
})(globalThis);
