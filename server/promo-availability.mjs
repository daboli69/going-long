// Roster screening is a research filter, never official game-day clearance.
export const nameKey=name=>String(name||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
export function rosterPlayers(body,now=Date.now()){
 const at=Date.parse(body?.timestamp);
 if(!Number.isFinite(at)||at>now+60000||now-at>3600000)throw Error('Roster timestamp is missing or stale');
 if(!Array.isArray(body.athletes)||!body.athletes.length)throw Error('Roster unavailable');
 const players=body.athletes.flatMap(group=>group.items||[]).filter(p=>p.fullName).map(p=>({
  name:p.fullName,key:nameKey(p.fullName),
  availability:p.status?.type==='active'&&Array.isArray(p.injuries)&&p.injuries.length===0?'expected':'unavailable',
  reason:p.status?.type!=='active'?'Not on active roster':!Array.isArray(p.injuries)?'Injury information missing':p.injuries.length?'Injury designation reported':'Listed on active roster without an injury designation'
 }));
 if(!players.length)throw Error('Roster is empty');
 return {players,sourceUpdatedAt:body.timestamp};
}
const cache=new Map(),pending=new Map();
async function json(url){const r=await fetch(url,{signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error('Public roster feed unavailable');return r.json();}
export async function availability(now=Date.now()){
 const old=cache.get('all');if(old&&now-old.at<300000)return old.body;
 if(pending.has('all'))return pending.get('all');
 const task=(async()=>{
  const directory=await json('https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams');
  const teams=directory.sports?.[0]?.leagues?.[0]?.teams;
  if(!Array.isArray(teams)||teams.length!==32)throw Error('NFL team directory unavailable');
  const out=[];
  // Eight concurrent free requests; one cache shared across every promo visitor.
  let cursor=0;
  await Promise.all(Array.from({length:8},async()=>{while(cursor<teams.length){
   const {team}=teams[cursor++];const source=`https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/${encodeURIComponent(team.id)}/roster`;
   try{out.push({team:team.displayName,code:team.abbreviation,source,...rosterPlayers(await json(source),Date.now())});}
   catch{out.push({team:team.displayName,code:team.abbreviation,source,players:[],error:'Roster check unavailable; players excluded'});}
  }}));
  const body={checkedAt:new Date().toISOString(),officialInactivesVerified:false,teams:out};cache.set('all',{at:Date.now(),body});return body;
 })().finally(()=>pending.delete('all'));pending.set('all',task);return task;
}
