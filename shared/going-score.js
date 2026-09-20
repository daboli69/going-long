(function(root){
'use strict';
const MARKET_SPECS={
 atd:{label:'Any TD',mode:'probability',weights:{projection:.75,role:.15,matchup:.06,environment:.04}},
 pass_yds:{label:'Pass Yards',weights:{projection:.45,role:.25,matchup:.20,environment:.10}},
 pass_tds:{label:'Pass TDs',weights:{projection:.50,role:.20,matchup:.15,environment:.15}},
 rush_yds:{label:'Rush Yards',weights:{projection:.45,role:.30,matchup:.15,environment:.10}},
 receptions:{label:'Receptions',weights:{projection:.45,role:.30,matchup:.15,environment:.10}},
};
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
function percentile(values,value){
 const valid=values.filter(finite).sort((a,b)=>a-b);
 if(!finite(value)||!valid.length)return null;
 if(valid.length===1)return 50;
 let below=0,equal=0;for(const candidate of valid){if(candidate<value)below++;else if(candidate===value)equal++;}
 return 100*(below+(equal-1)/2)/(valid.length-1);
}
function tier(score){
 if(score>=85)return {id:'elite',label:'Elite'};
 if(score>=70)return {id:'strong',label:'Strong'};
 if(score>=55)return {id:'watch',label:'Watch'};
 return {id:'neutral',label:'Neutral'};
}
function confidence(row,coverage){
 const history=clamp((Number(row.sampleGames)||0)/12,0,1);
 const currentGames=Number(row.currentGames)||0,current=clamp(currentGames/6,0,1);
 const uncapped=Math.round(100*(.55*history+.25*coverage+.20*current));
 const value=Math.min(uncapped,currentGames===0?59:currentGames<3?79:100);
 return {value,label:value>=80?'High':value>=60?'Moderate':'Limited'};
}
function probabilityScore(row,components,certainty){
 const probability=finite(row.scoreProbability)?clamp(row.scoreProbability,0,1):finite(row.probability)?clamp(row.probability,0,1):null;
 if(probability==null)return null;
 // An absolute TD evidence score: probability is the anchor and the other
 // components can move it only modestly. No player is promoted merely because
 // somebody must rank first on a small slate.
 let raw=12+106*probability;
 for(const [key,effect] of [['role',.08],['matchup',.04],['environment',.03]]){
  const pct=components[key]?.percentile;if(pct!=null)raw+=(pct-50)*effect;
 }
 const reliability=.85+.15*(certainty.value/100);
 return Math.round(10*clamp(50+(raw-50)*reliability,10,90))/10;
}
function scoreRows(rows,market){
 const spec=MARKET_SPECS[market];if(!spec)return [];
 const pools={};for(const key of Object.keys(spec.weights))pools[key]=rows.map(row=>row.components?.[key]?.value).filter(finite);
 return rows.map(row=>{
  let weighted=0,used=0,total=0;const components={};
  for(const [key,weight] of Object.entries(spec.weights)){
   total+=weight;const component=row.components?.[key],value=component?.value,pct=percentile(pools[key],value);
   components[key]={...component,percentile:pct,weight};
   if(pct!=null){weighted+=pct*weight;used+=weight;}
  }
  const coverage=total?used/total:0,certainty=confidence(row,coverage);
  const score=spec.mode==='probability'?probabilityScore(row,components,certainty):used?Math.round(10*weighted/used)/10:null;
  const ranked=Object.entries(components).filter(([,c])=>c.percentile!=null).sort((a,b)=>b[1].percentile-a[1].percentile);
  return {...row,market,score,tier:score==null?{id:'unrated',label:'Unrated'}:tier(score),confidence:certainty,componentCoverage:coverage,components,highlights:ranked.slice(0,2).map(([key,c])=>({key,label:c.label,percentile:c.percentile}))};
 }).filter(row=>row.score!=null).sort((a,b)=>b.score-a.score||String(a.player).localeCompare(String(b.player))).map((row,index)=>({...row,rank:index+1}));
}
function groupByGame(rows){
 const groups=new Map();for(const row of rows){const key=row.game||'Unassigned game';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
 return [...groups].map(([game,selections])=>({game,selections}));
}
root.GoingScore={MARKET_SPECS,scoreRows,groupByGame,percentile,tier};
if(typeof module!=='undefined')module.exports=root.GoingScore;
})(globalThis);
