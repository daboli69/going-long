(function(root){
'use strict';
const SLOTS=Object.freeze(['QB','RB','RB','WR','WR','WR','TE','FLEX','DST']);
const CAP=50000;
const TEAMS=new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const team=value=>({JAC:'JAX',LAR:'LA',WSH:'WAS'})[value]||value;
// Preserve suffixes: stripping Jr./II can silently merge distinct identities.
const matchName=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const fits=(position,slot)=>position===slot||(slot==='FLEX'&&['RB','WR','TE'].includes(position));
function csvRows(text){
 const rows=[];let row=[],field='',quoted=false,closed=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(quoted){if(c==='"'){if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;closed=true;}}else field+=c;continue;}
  if(c==='"'){if(field||closed)throw Error('Malformed CSV quotation.');quoted=true;}
  else if(c===','||c==='\n'||c==='\r'){
   row.push(field);field='';closed=false;
   if(c!==','){if(c==='\r'&&text[i+1]==='\n')i++;if(row.some(v=>v.trim()))rows.push(row);row=[];}
  }else{if(closed)throw Error('Unexpected text after CSV quotation.');field+=c;}
 }
 if(quoted)throw Error('Unterminated CSV quotation.');
 row.push(field);if(row.some(v=>v.trim()))rows.push(row);return rows;
}
function kickoffET(month,day,year,hour,minute,meridian){
 hour=hour%12+(meridian==='PM'?12:0);
 const nominal=Date.UTC(year,month-1,day,hour,minute);
 const calendar=new Date(Date.UTC(year,month-1,day));
 if(calendar.getUTCFullYear()!==year||calendar.getUTCMonth()!==month-1||calendar.getUTCDate()!==day)return null;
 const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 for(const offset of [4,5]){
  const candidate=new Date(nominal+offset*3600000),parts=Object.fromEntries(fmt.formatToParts(candidate).map(p=>[p.type,p.value]));
  if(+parts.year===year&&+parts.month===month&&+parts.day===day&&+parts.hour===hour&&+parts.minute===minute)return candidate.toISOString();
 }
 return null;
}
function parseCsv(text){
 const fail=errors=>({players:[],errors,slate:null,source:'DraftKings salary CSV'});
 let rows;try{rows=csvRows(String(text||'').replace(/^\uFEFF/,''));}catch(error){return fail([error.message]);}
 if(rows.length<2)return fail(['No DraftKings salary rows found.']);
 const headers=rows[0].map(h=>h.trim()),required=['Position','Name + ID','Name','ID','Roster Position','Salary','Game Info','TeamAbbrev','AvgPointsPerGame'];
 if(new Set(headers).size!==headers.length)return fail(['Duplicate CSV headers.']);
 if(required.some(h=>!headers.includes(h)))return fail(['Import an official DraftKings NFL Classic salary CSV with all required headers.']);
 const players=[],errors=[],ids=new Set(),athletes=new Set(),games=new Map(),dates=new Set(),teamGames=new Map();
 for(let i=1;i<rows.length;i++){
  const cells=rows[i];if(cells.length!==headers.length){errors.push(`Row ${i+1}: incorrect column count.`);continue;}
  const r=Object.fromEntries(headers.map((h,j)=>[h,cells[j].trim()])),position=r.Position,id=r.ID,name=r.Name,salary=Number(r.Salary),ownTeam=team(r.TeamAbbrev);
  const gameMatch=r['Game Info'].match(/^([A-Z]{2,3})@([A-Z]{2,3}) (\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})(AM|PM) ET$/);
  const error=message=>errors.push(`Row ${i+1}: ${message}`);
  if(!/^\d+$/.test(id)||!name||r['Name + ID']!==`${name} (${id})`){error('invalid official player name/ID.');continue;}
  if(ids.has(id)){error('duplicate DraftKings ID; import rejected.');continue;}ids.add(id);
  if(!['QB','RB','WR','TE','DST'].includes(position)||r['Roster Position']!==(position==='DST'||position==='QB'?position:`${position}/FLEX`)){error('unsupported roster position; only NFL Classic is supported.');continue;}
  if(!/^\d+$/.test(r.Salary)||!Number.isSafeInteger(salary)||salary<=0||salary>CAP){error('salary must be a positive integer from the official CSV.');continue;}
  if(!gameMatch){error('invalid game or ET kickoff.');continue;}
  const [,awayRaw,homeRaw,m,d,y,h,min,ap]=gameMatch,away=team(awayRaw),home=team(homeRaw);
  const kickoff=(+h>=1&&+h<=12&&+min<=59)?kickoffET(+m,+d,+y,+h,+min,ap):null;
  if(!TEAMS.has(away)||!TEAMS.has(home)||away===home||!TEAMS.has(ownTeam)||![away,home].includes(ownTeam)||!kickoff){error('invalid NFL teams, team/game identity, or kickoff.');continue;}
  const date=`${y}-${m}-${d}`,gameId=`${away}@${home}|${kickoff}`,athlete=`${matchName(name)}|${ownTeam}|${position}`;
  if(athletes.has(athlete)){error('duplicate athlete identity; resolve the source CSV before import.');continue;}athletes.add(athlete);
  for(const t of [away,home]){if(teamGames.has(t)&&teamGames.get(t)!==gameId)error('NFL team appears in conflicting games.');teamGames.set(t,gameId);}
  if(r.AvgPointsPerGame!==''&&!/^-?\d+(\.\d+)?$/.test(r.AvgPointsPerGame)){error('invalid AvgPointsPerGame.');continue;}
  dates.add(date);games.set(gameId,{gameId,away,home,kickoff});
  players.push({id,name,position,rosterPosition:r['Roster Position'],salary,team:ownTeam,opponent:ownTeam===away?home:away,gameId,kickoff,gameInfo:r['Game Info'],avgPointsPerGame:r.AvgPointsPerGame===''?null:Number(r.AvgPointsPerGame),sourceSalary:'draftkings-csv'});
 }
 if(dates.size!==1)errors.push('Classic import must contain exactly one slate date; mixed dates are rejected.');
 if(games.size<2)errors.push('NFL Classic requires a player pool containing at least two games.');
 if(errors.length)return fail(errors);
 const gameList=[...games.values()].sort((a,b)=>a.kickoff.localeCompare(b.kickoff)||a.gameId.localeCompare(b.gameId));
 return {players,errors:[],source:'DraftKings salary CSV',slate:{date:[...dates][0],gameIds:gameList.map(g=>g.gameId),games:gameList,earliestKickoff:gameList[0].kickoff,latestKickoff:gameList.at(-1).kickoff}};
}
const athlete=p=>p.athleteId?String(p.athleteId):`${matchName(p.name)}|${p.team}`;
const td=p=>p.position==='DST'?0:p.tdMean;
function context(pool,options){
 const errors=[],byId=new Map(),now=options.now==null?Date.now():Date.parse(options.now),excluded=new Set((options.excludedIds||[]).map(String)),locks={...options.lockedSlots},incumbent=options.incumbentLineup||[],mode=options.mode||'best';
 if(!['best','throne'].includes(mode))errors.push('Unsupported DFS mode.');
 if(!Number.isFinite(now))errors.push('Invalid current time.');
 for(const p of pool||[]){const id=String(p.id);if(byId.has(id))errors.push('Duplicate DraftKings IDs in player pool.');byId.set(id,p);}
 // Game locks are immutable only when supplied with an existing complete roster.
 if(incumbent.length===9)incumbent.forEach((p,i)=>{const current=byId.get(String(p?.id));if(current&&Date.parse(current.kickoff)<=now){if(locks[i]!=null&&String(locks[i])!==String(current.id))errors.push('A started player cannot be moved or replaced.');locks[i]=String(current.id);}});
 const lockedIds=new Set();
 for(const [key,idRaw] of Object.entries(locks)){
  const index=Number(key),id=String(idRaw),p=byId.get(id);
  if(!Number.isInteger(index)||index<0||index>=9||!p||!fits(p.position,SLOTS[index]))errors.push('A locked player is missing or cannot fit the selected slot.');
  if(lockedIds.has(id))errors.push('A player cannot be locked twice.');lockedIds.add(id);locks[key]=id;
  if(excluded.has(id))errors.push('A locked player is also excluded.');
 }
 return {errors,byId,now,excluded,locks,lockedIds,incumbent,mode};
}
function allowed(p,index,c){
 const immutable=c.incumbent.length===9&&String(c.incumbent[index]?.id)===String(p.id)&&Date.parse(p.kickoff)<=c.now;
 if(!p||p.sourceSalary!=='draftkings-csv'||!Number.isSafeInteger(p.salary)||p.salary<=0||p.salary>CAP||!fits(p.position,SLOTS[index])||!p.gameId||!TEAMS.has(p.team)||!TEAMS.has(p.opponent)||p.team===p.opponent||!Number.isFinite(Date.parse(p.kickoff)))return false;
 if(c.excluded.has(String(p.id)))return false;
 if(c.locks[index]!=null&&c.locks[index]!==String(p.id))return false;
 if(c.lockedIds.has(String(p.id))&&c.locks[index]!==String(p.id))return false;
 if(!immutable&&(p.matched!==true||p.unavailable||!(finite(p.projection)&&p.projection>0)||Date.parse(p.kickoff)<=c.now))return false;
 if(!finite(p.projection)||p.projection<0)return false;
 if(c.mode==='throne'&&p.position!=='DST'&&(!finite(p.tdMean)||p.tdMean<0))return false;
 return true;
}
function totals(lineup){
 const salaryUsed=lineup.reduce((s,p)=>s+p.salary,0),projection=lineup.reduce((s,p)=>s+p.projection,0),tdMean=lineup.reduce((s,p)=>s+(finite(td(p))?td(p):0),0);
 return {salaryUsed,salaryRemaining:CAP-salaryUsed,projection,tdMean};
}
function validateLineup(lineup,pool,options={}){
 const c=context(pool,options),errors=[...c.errors];
 if(!Array.isArray(lineup)||lineup.length!==9)return {valid:false,errors:[...errors,'A Classic lineup requires exactly nine players.']};
 const ids=new Set(),athletes=new Set(),games=new Set();
 lineup.forEach((entry,index)=>{
  const p=c.byId.get(String(entry?.id));
  if(!p){errors.push(`Slot ${index+1}: player is outside the imported contest pool.`);return;}
  if(entry.name!==p.name||entry.salary!==p.salary||entry.position!==p.position||entry.gameId!==p.gameId||entry.team!==p.team||entry.opponent!==p.opponent||entry.kickoff!==p.kickoff||entry.projection!==p.projection||entry.tdMean!==p.tdMean)errors.push(`Slot ${index+1}: roster data differs from imported pool.`);
  if((entry.slot!=null&&entry.slot!==SLOTS[index])||(entry.slotIndex!=null&&entry.slotIndex!==index)||!allowed(p,index,c))errors.push(`Slot ${index+1}: player is ineligible, unavailable, excluded, started, or conflicts with a lock.`);
  if(ids.has(String(p.id))||athletes.has(athlete(p)))errors.push('Players must be unique across every roster slot.');ids.add(String(p.id));athletes.add(athlete(p));games.add(p.gameId);
 });
 const canonical=lineup.map(entry=>c.byId.get(String(entry?.id)));
 const result=canonical.every(Boolean)?totals(canonical):{salaryUsed:null,salaryRemaining:null,projection:null,tdMean:null};
 if(!Number.isFinite(result.salaryUsed)||result.salaryUsed>CAP)errors.push('Salary exceeds $50,000.');
 if(games.size<2)errors.push('Lineup must represent at least two NFL games.');
 return {valid:errors.length===0,errors,...result};
}
function compare(a,b,mode){return (mode==='throne'?b.tdMean-a.tdMean:0)||b.projection-a.projection||a.salary-b.salary||a.key.localeCompare(b.key);}
function thresholdEngine(){return root.GoingDfsThreshold||(typeof require==='function'?require('./dfs-threshold.js'):null);}
function thresholdCompare(a,b){return b.tdThreshold.tailMass-a.tdThreshold.tailMass||b.projection-a.projection||a.salary-b.salary||a.key.localeCompare(b.key);}
function optimize(pool,options={}){
 const c=context(pool,options),failure=reason=>({lineup:[],reason,errors:c.errors,heuristic:true});
 if(c.errors.length)return failure(c.errors.join(' '));
 const scenario=c.mode==='throne'&&options.tdScenario,engine=scenario&&thresholdEngine();
 if(c.mode==='throne'&&Object.hasOwn(options,'tdScenario')&&!scenario)return failure('Eight-TD scenario support is missing; no count-only fallback is allowed.');
 if(scenario&&!engine)return failure('The eight-TD scenario module is unavailable. Reload before building.');
 const width=Math.max(50,Math.min(3000,Number.isInteger(options.beamWidth)?options.beamWidth:800));
 const candidates=SLOTS.map((slot,i)=>[...c.byId.values()].filter(p=>allowed(p,i,c)).sort((a,b)=>String(a.id).localeCompare(String(b.id))));
 if(candidates.some(ps=>!ps.length))return failure('No eligible matched players with current evidence fit every required slot.');
 if(scenario){const check=engine.evaluate([...new Map(candidates.flat().map(p=>[String(p.id),p])).values()],scenario);if(!check.valid)return failure(check.reason);}
 const minRemaining=new Array(10).fill(0);
 for(let i=8;i>=0;i--)minRemaining[i]=minRemaining[i+1]+Math.min(...candidates[i].map(p=>p.salary));
 let states=[{players:[],ids:[],athletes:[],salary:0,projection:0,tdMean:0,key:''}];
 for(let i=0;i<9;i++){
  const next=[],seen=new Map();
  for(const state of states)for(const p of candidates[i]){
   const id=String(p.id),identity=athlete(p);
   if(state.ids.includes(id)||state.athletes.includes(identity)||state.salary+p.salary+minRemaining[i+1]>CAP)continue;
   if(i>0&&SLOTS[i]===SLOTS[i-1]&&c.locks[i]==null&&c.locks[i-1]==null&&id.localeCompare(String(state.players[i-1].id))<=0)continue;
   const salary=state.salary+p.salary;
   if(i===8&&new Set([...state.players.map(x=>x.gameId),p.gameId]).size<2)continue;
   const ids=[...state.ids,id],key=ids.slice().sort().join('|');
   // Equal selected sets at the same depth have equal objectives: do not spend the beam on permutations.
   if(seen.has(key))continue;seen.set(key,true);
   next.push({players:[...state.players,p],ids,athletes:[...state.athletes,identity],salary,projection:state.projection+p.projection,tdMean:state.tdMean+(finite(td(p))?td(p):0),key});
  }
  if(!next.length)return failure('No valid lineup was found within the salary, game and player restrictions.');
  next.sort((a,b)=>compare(a,b,c.mode));
  if(next.length<=width)states=next;
  else{
   // Reserve beam space across salary bands so cheap opportunity stays available for later slots.
   const keep=next.slice(0,Math.floor(width/2)),keys=new Set(keep.map(s=>s.key)),bands=new Map();
   for(const state of next){const band=Math.floor(state.salary/100);if(!bands.has(band))bands.set(band,state);}
   for(const state of [...bands.values()].sort((a,b)=>a.salary-b.salary))if(keep.length<width&&!keys.has(state.key)){keep.push(state);keys.add(state.key);}
   for(const state of next)if(keep.length<width&&!keys.has(state.key)){keep.push(state);keys.add(state.key);}
   states=keep;
  }
 }
 if(scenario){
  for(const state of states)state.tdThreshold=engine.evaluate(state.players,scenario);
  states=states.filter(state=>state.tdThreshold.valid);
  states.sort(thresholdCompare);
  // The beam supplies affordable complete seeds. Improve the best seeds against
  // the WHOLE lineup's eight-TD mass, preserving every roster and lock constraint.
  // This bounded ascent is deterministic, not a claim of a global optimum.
  const seeds=states.slice(0,3);
  for(let state of seeds){
   for(let pass=0;pass<3;pass++){
    let best=state;
    for(let i=0;i<9;i++){
     if(c.locks[i]!=null)continue;
     for(const p of candidates[i]){
      if(String(p.id)===String(state.players[i].id))continue;
      const players=state.players.map((entry,j)=>j===i?p:entry),salary=state.salary-state.players[i].salary+p.salary;
      if(salary>CAP||new Set(players.map(p=>String(p.id))).size!==9||new Set(players.map(athlete)).size!==9||new Set(players.map(p=>p.gameId)).size<2)continue;
      const tdThreshold=engine.evaluate(players,scenario);if(!tdThreshold.valid)continue;
      const sums=totals(players),candidate={players,salary,projection:sums.projection,tdMean:sums.tdMean,key:players.map(p=>String(p.id)).sort().join('|'),tdThreshold};
      if(thresholdCompare(candidate,best)<0)best=candidate;
     }
    }
    if(best===state)break;
    state=best;
   }
   states.push(state);
  }
  states.sort(thresholdCompare);
 }else states.sort((a,b)=>compare(a,b,c.mode));
 for(const state of states){
  const lineup=state.players.map((p,i)=>({...p,slot:SLOTS[i],slotIndex:i})),validation=validateLineup(lineup,pool,options);
  if(validation.valid)return {lineup,...totals(lineup),tdThreshold:state.tdThreshold||null,reason:null,errors:[],heuristic:true,method:scenario?'Eight-plus rushing/receiving TD scenario mass; DFS points break ties. Finite shared team budgets, independent teams; bounded uncalibrated scenario search.':c.mode==='throne'?'Expected rushing/receiving TD sum; DFS points break ties. Bounded search; no calibrated threshold probability.':'Projected DraftKings point sum. Bounded search; global optimum is not guaranteed.'};
 }
 return failure('No independently valid lineup survived the search.');
}
function alternatives(lineup,slotIndex,pool,options={}){
 if(!Number.isInteger(slotIndex)||slotIndex<0||slotIndex>8)return {alternatives:[],errors:['Invalid roster slot.']};
 const baseline=validateLineup(lineup,pool,options);
 if(!baseline.valid)return {alternatives:[],errors:baseline.errors};
 const c=context(pool,options),results=[];
 const scenario=c.mode==='throne'&&options.tdScenario,engine=scenario&&thresholdEngine(),baselineThreshold=scenario&&engine?.evaluate(lineup,scenario);
 if(c.mode==='throne'&&Object.hasOwn(options,'tdScenario')&&!scenario)return {alternatives:[],errors:['Eight-TD scenario support is missing.']};
 if(scenario&&!baselineThreshold?.valid)return {alternatives:[],errors:[baselineThreshold?.reason||'Eight-TD scenario support is unavailable.']};
 if(c.locks[slotIndex]!=null)return {alternatives:[],errors:['Unlock this player before swapping; started players cannot be swapped.']};
 for(const p of pool){
  if(String(p.id)===String(lineup[slotIndex].id)||!allowed(p,slotIndex,c))continue;
  const replaced=lineup.map((entry,i)=>i===slotIndex?{...p,slot:SLOTS[i],slotIndex:i}:entry),check=validateLineup(replaced,pool,options);
  const tdThreshold=scenario&&check.valid?engine.evaluate(replaced,scenario):null;
  if(check.valid&&(!scenario||tdThreshold.valid))results.push({player:p,lineup:replaced,salaryDelta:check.salaryUsed-baseline.salaryUsed,projectionDelta:check.projection-baseline.projection,tdMeanDelta:check.tdMean-baseline.tdMean,tdThreshold,tdThresholdDelta:scenario?tdThreshold.tailMass-baselineThreshold.tailMass:null,salaryRemaining:check.salaryRemaining});
 }
 results.sort((a,b)=>(scenario?b.tdThresholdDelta-a.tdThresholdDelta:c.mode==='throne'?b.tdMeanDelta-a.tdMeanDelta:0)||b.projectionDelta-a.projectionDelta||a.salaryDelta-b.salaryDelta||String(a.player.id).localeCompare(String(b.player.id)));
 return {alternatives:results,errors:[]};
}
root.GoingDfsClassic={SLOTS,CAP,matchName,parseCsv,validateLineup,optimize,alternatives};
if(typeof module!=='undefined')module.exports=root.GoingDfsClassic;
})(globalThis);
