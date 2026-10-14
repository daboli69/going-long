// Derived evidence only; raw CSVs and metric tables never leave this server path.
import matchupCsv from '../shared/dfs-matchup-csv.js';
const {team:canonicalTeam}=matchupCsv;
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const team=x=>canonicalTeam(({ARZ:'ARI',BLT:'BAL',CLV:'CLE',HST:'HOU'})[String(x||'').toUpperCase()]||x);
const key=(columns,name)=>{
 const matches=columns.filter(k=>k.split('.').at(-1).toUpperCase()===name.toUpperCase());
 if(name==='RTE %')return matches.find(k=>['Receiving','Overall'].includes(k.split('.')[0]));
 if(['FP','XFP'].includes(name))return matches.find(k=>['FP','Total','Overall'].includes(k.split('.')[0]))||(matches.length===1?matches[0]:undefined);
 return matches.length===1?matches[0]:undefined;
};
const metric=(row,columns,name)=>row[key(columns,name)];
const scoped=(row,columns,group,name)=>{const matches=columns.filter(k=>k.toLowerCase()===(group+'.'+name).toLowerCase());return matches.length===1?row[matches[0]]:undefined;};
export function deriveResearch(datasets,{season,week,now=Date.now()}){
 const players=new Map(),teams=new Map();
 const add=(map,id,entity,note)=>{if(!map.has(id))map.set(id,{...entity,notes:[]});const notes=map.get(id).notes;if(!notes.includes(note))notes.push(note);};
 for(const d of datasets){
  if(d.season!==season||Date.parse(d.exported_at)>now||now-Date.parse(d.exported_at)>8*86400000||Date.parse(d.known_at)>now)continue;
  const columns=d.columns,reference=d.reference_rows?.[0]||{},base=name=>{const v=metric(reference,columns,name);return v===''||v==null?null:Number(v);},period=d.scope==='prior_week'?`Week ${d.observed_week}`:'Current-season';
  const playerTable=(d.groups||[]).some(g=>String(g).toLowerCase().includes('player details'));
  const seen=new Map();for(const r of d.records){const id=[metric(r,columns,'NAME'),metric(r,columns,'TEAM'),metric(r,columns,'POS')].join('|');seen.set(id,(seen.get(id)||0)+1);}
  for(const r of d.records){
   const name=metric(r,columns,'NAME'),position=metric(r,columns,'POS'),t=team(metric(r,columns,'TEAM')||(!playerTable?name:'')),entity={name,team:t,position};
   if(!t||typeof t!=='string')continue;
   if(playerTable){
    const id=[name,metric(r,columns,'TEAM'),position].join('|');if(typeof name!=='string'||!name.trim()||name.length>128||typeof position!=='string'||!position.trim()||position.length>16||seen.get(id)!==1)continue;
    if(d.table==='receiving_man_vs_zone'){
     const man=scoped(r,columns,'Man','TPRR'),zone=scoped(r,columns,'Zone','TPRR');
     if(finite(man)&&finite(zone)&&man!==zone)add(players,id,entity,`${period} target rate per route was higher against ${man>zone?'man':'zone'} coverage in this export. This split is descriptive, not an opponent-specific forecast.`);
    }
    if(['receiving_routes_run','separation_role'].includes(d.table)){
     const groups=d.table==='separation_role'?['X (Wide, On the Line)','Z (Wide, Off the Line)','F (Slot)','Condensed (Wide, Reduced Split)']:['Wide','Slot','Inline','Backfield'];
     const reported=groups.filter(group=>columns.some(k=>k.toLowerCase()===(group+'.RTE').toLowerCase()));
     const counts=reported.map(group=>[group,scoped(r,columns,group,'RTE')]);
     const complete=counts.length>=2&&counts.every(x=>finite(x[1])&&x[1]>=0);counts.sort((a,b)=>b[1]-a[1]);
     if(complete&&counts[0][1]>0&&counts[0][1]>counts[1][1])add(players,id,entity,`${period} among the reported categories, most recorded routes came from ${counts[0][0]}. Role can change with personnel and game plan.`);
    }
    if(d.table.startsWith('receiving_separation_')||d.table.startsWith('separation_')){
     const win=scoped(r,columns,'Overall','WIN RATE'),raw=scoped(reference,columns,'Overall','WIN RATE');
     const avg=typeof raw==='number'?raw:typeof raw==='string'&&raw.trim()?Number(raw):NaN;
     if(finite(win)&&Number.isFinite(avg)&&win>avg)add(players,id,entity,`${period} overall route win rate exceeded the export reference. It does not establish a betting advantage.`);
    }
    const fp=metric(r,columns,'FP'),xfp=metric(r,columns,'XFP');
    if(finite(fp)&&finite(xfp)&&fp<xfp)add(players,id,entity,`${period} production trailed provider expected fantasy opportunity. Descriptive, not a bounce-back forecast.`);
    for(const [m,label] of [['RTE %','route participation'],['BACKFIELD XFP %','backfield opportunity share']]){
     const value=metric(r,columns,m),average=base(m);if(finite(value)&&finite(average)&&value>average)add(players,id,entity,`${period} ${label} exceeded this export’s reference. It does not change the projected points or probability.`);
    }
   }else{
    if(d.table==='coverage_matrix'){
     const zone=metric(r,columns,'ZONE %'),man=metric(r,columns,'MAN %');if(finite(zone)&&finite(man))add(teams,t,{team:t},`${period} coverage leaned ${zone>man?'zone':'man'} in the supplied sample; not a prediction of the next game’s coverage.`);
    }
    for(const [m,label] of [['PRESS %','pressure rate'],['PASS %','pass-calling rate']]){const value=metric(r,columns,m),average=base(m);if(finite(value)&&finite(average)&&value>average)add(teams,t,{team:t},`${period} ${label} exceeded this export’s reference. Personnel and opponent can change it.`);}
    if(d.table==='offensive_line_units')add(teams,t,{team:t},'Offensive-line unit history is available privately; these exports do not establish the next game’s healthy starting combination.');
    if(['coach_records','playcaller'].includes(d.table))add(teams,t,{team:t},'Current-season coaching/playcaller records are available as context; no coaching multiplier is applied to the forecast.');
   }
  }
 }
 return {schema:'going-private-fp-research-v1',season,week,players:[...players.values()],teams:[...teams.values()],modelStatus:'Descriptive evidence; forecasts unchanged'};
}
