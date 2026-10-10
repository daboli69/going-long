/* GOING eligibility engine: ONE decision about whether a player can be an actionable recommendation, used by every surface (props/Today/Best Plays/Signals/Parlays/Markets,
 * projections, GOING Score, Players to Target, DFS pools, Jackpot builders via the Python mirror scripts/eligibility.py, the tracker collector).
 *
 * Fail-safe rules (in order):
 *  1. Confirmed unavailable statuses are excluded even when the data is stale: reserve/IR/PUP/NFI (RES, INA, PUP, IR), suspended, retired, exempt, released, practice squad/development,
 *     a current-week Out/Inactive/Doubtful report, or a team on bye.
 *  2. Everyone else is only actionable when the roster AND injury snapshots are fresh. With stale or missing data a player is 'unverified' and not actionable (nothing is guessed active).
 *  3. A player missing from the roster snapshot is 'unknown' and not actionable; no recent game (21 days) is 'stale'.
 *  4. Questionable, game-time decision, did-not-practice and limited practice stay actionable with a caution.
 *  5. A published expected_return_week makes a reserve player 'returning' (stash only, never actionable now).
 * Game-day inactives (about 90 minutes before kickoff) are not in the free feeds; an 'Inactive'/'Out' report excludes the player as soon as it appears in a refresh.
 * Rollback: set globalThis.GOING_ELIGIBILITY_STRICT=false to keep only rule 1 (confirmed unavailable) and skip the freshness requirement.
 */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const RESERVE=new Set(['RES','INA','PUP','IR','NFI']),REMOVED=new Set(['CUT','REL','WAIVED']),PRACTICE=new Set(['DEV','PRA','PS','PSQ']);
const ACTIVE=new Set(['ACT','ACTIVE']);
const object=x=>x!=null&&typeof x==='object'&&!Array.isArray(x);
const status=x=>typeof x==='string'?x.trim().toUpperCase():'';
const idOk=x=>typeof x==='string'&&x.trim().length>0;
const weekNumber=x=>typeof x==='number'&&Number.isInteger(x)&&x>0&&x<=22?x:typeof x==='string'&&/^\d+$/.test(x)&&Number(x)>0&&Number(x)<=22?Number(x):null;
const reportCurrent=(r,week)=>weekNumber(week)==null||weekNumber(r.week)==null||weekNumber(r.week)>=weekNumber(week);
const reportValid=v=>object(v)&&['report_status','practice_status'].every(k=>v[k]==null||typeof v[k]==='string')&&(v.week==null||weekNumber(v.week)!=null);
const playerValid=v=>object(v)&&['roster_status','team'].every(k=>v[k]==null||typeof v[k]==='string')&&(v.roster_week==null||weekNumber(v.roster_week)!=null);
function validInjury(x){return object(x)&&object(x.current_players)&&object(x.current_reports)&&Object.values(x.current_players).every(v=>playerValid(v)&&idOk(v.gsis_id))&&Object.values(x.current_reports).every(v=>reportValid(v)&&idOk(v.gsis_id));}
function validRoster(x){return object(x)&&(x.week==null||weekNumber(x.week)!=null)&&Array.isArray(x.players)&&x.players.every(v=>playerValid(v)&&idOk(v.id)&&(v.injury==null||reportValid(v.injury)))&&(x.bye_carry_forward_teams==null||Array.isArray(x.bye_carry_forward_teams)&&x.bye_carry_forward_teams.every(v=>typeof v==='string'));}
const LIMITS={injuryHours:36,rosterHours:36,staleGameDays:21};
const hoursOld=(t,now)=>{
 if(typeof t!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(t))return null;
 const year=Number(t.slice(0,4)),month=Number(t.slice(5,7)),day=Number(t.slice(8,10)),leap=year%4===0&&(year%100!==0||year%400===0),days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
 if(year===0||month<1||month>12||day<1||day>days[month-1]||Number(t.slice(11,13))>23||Number(t.slice(14,16))>59||Number(t.slice(17,19))>59)return null;
 const ms=Date.parse(t);return Number.isFinite(ms)?(now-ms)/3600000:null;
};
function freshness(injury,roster,now=Date.now(),limits=LIMITS){
 const iAge=hoursOld(injury?.generated_at,now),rAge=hoursOld(roster?.generated_at,now);
 const injuryOk=validInjury(injury)&&iAge!=null&&iAge>=-.5&&iAge<=limits.injuryHours,rosterOk=validRoster(roster)&&rAge!=null&&rAge>=-.5&&rAge<=limits.rosterHours;
 const reasons=[];
 if(!injury)reasons.push('injury file missing');else if(!validInjury(injury))reasons.push('injury file malformed');else if(!injuryOk)reasons.push(iAge==null?'injury file has no timestamp':`injury file ${Math.round(iAge)} hours old`);
 if(!roster)reasons.push('roster snapshot missing');else if(!validRoster(roster))reasons.push('roster snapshot malformed');else if(!rosterOk)reasons.push(rAge==null?'roster snapshot has no timestamp':`roster snapshot ${Math.round(rAge)} hours old`);
 const rw=weekNumber(roster?.week),weeksAgree=rw==null||!validInjury(injury)||Object.values(injury.current_players).every(v=>v.roster_week==null||weekNumber(v.roster_week)===rw);
 if(!weeksAgree)reasons.push('roster weeks disagree');
 return {ok:injuryOk&&rosterOk&&weeksAgree,injuryOk,rosterOk,injuryAsOf:injury?.generated_at||null,rosterAsOf:roster?.generated_at||null,injuryAgeHours:iAge,rosterAgeHours:rAge,reason:reasons.join('; ')};
}
function strict(){return root.GOING_ELIGIBILITY_STRICT!==false;}
function severity(r){const s=String(r?.report_status||'').trim().toLowerCase();return /^out|^inactive|injured reserve|suspend/.test(s)?4:/doubtful/.test(s)?3:/questionable|game.?time|^gtd/.test(s)?2:/did not/.test(String(r?.practice_status||'').toLowerCase())?1:0;}
// Merge the injury file (statuses incl. reserve/practice squad) with the all-teams roster snapshot (bye teams, injury objects).
function index(injury,roster,week){
 const players=Object.create(null),reports=Object.create(null),bye=new Set(Array.isArray(roster?.bye_carry_forward_teams)?roster.bye_carry_forward_teams:[]);
 const merge=v=>{const prior=players[v.gsis_id],rs=status(v.roster_status),ps=status(prior?.roster_status),rank=s=>RESERVE.has(s)||REMOVED.has(s)||PRACTICE.has(s)||['SUS','RET','EXE'].includes(s)?2:ACTIVE.has(s)?0:1;
  const conflict=prior?.team&&v.team&&prior.team!==v.team;
  players[v.gsis_id]=!prior||rank(rs)>rank(ps)?{...v}:{...prior};
  if(conflict||prior?.teamConflict)players[v.gsis_id].teamConflict=true;
 };
 for(const v of Object.values(object(injury?.current_players)?injury.current_players:{}))if(object(v)&&idOk(v.gsis_id))merge(v);
 const mergeReport=r=>{if(object(r)&&idOk(r.gsis_id)&&reportCurrent(r,week)&&(!reports[r.gsis_id]||severity(r)>severity(reports[r.gsis_id])))reports[r.gsis_id]=r;};
 for(const v of Object.values(object(injury?.current_reports)?injury.current_reports:{}))mergeReport(v);
 for(const v of Array.isArray(roster?.players)?roster.players:[])if(object(v)&&idOk(v.id)){
  merge({gsis_id:v.id,roster_status:v.roster_status,team:v.team,from_roster:true});
  const r=v.injury;if(object(r))mergeReport({...r,gsis_id:v.id});
 }
 return {players,reports,bye};
}
function create({injury,roster,week,now=Date.now(),limits=LIMITS}={}){
 week=weekNumber(roster?.week)??weekNumber(week);
 const idx=index(injury,roster,week),fresh=freshness(injury,roster,now,limits),asOf=injury?.generated_at||roster?.generated_at||null;
 const ctxWeek=finite(week)?week:null;
 function decide(id,{team=null,lastGame=null,hasGame=null,requireRecentGame=true}={}){
  const entry=idx.players[id],rep=idx.reports[id],rs=status(entry?.roster_status),club=team||entry?.team||null;
  const mk=(state,actionable,label,detail,extra={})=>({state,actionable,caution:false,label,detail,asOf,verified:fresh.ok,fresh:fresh.ok,...extra});
  if(club&&idx.bye.has(club))return mk('bye',false,'Team on bye','This team does not play this week.');
  if(hasGame===false)return mk('no_game',false,'No upcoming game','No game is scheduled for this player in the window.');
  if(entry&&!rs)return mk('unknown',false,'Availability unconfirmed','The roster snapshot has no status for this player; not treated as active.');
  if(entry&&RESERVE.has(rs)){
   const ret=finite(entry.expected_return_week)?entry.expected_return_week:null;
   return mk(ret!=null?'returning':'reserve',false,'Reserve / injured list',ret!=null?`Expected back around week ${ret}: stash only, not a start or a bet until active.`:'Return date not available in our data. A reserve designation is not automatically season-ending (minimum four games), so check the team report; excluded until active.',{stashOnly:ret!=null,returnWeek:ret});
  }
  if(entry&&rs==='SUS')return mk('suspended',false,'Suspended','Suspended; check the reinstatement date. Excluded until active.');
  if(entry&&rs==='RET')return mk('retired',false,'Retired','Retired; excluded.');
  if(entry&&rs==='EXE')return mk('exempt',false,'Exempt list','Exempt list; excluded until reinstated.');
  if(entry&&REMOVED.has(rs))return mk('released',false,'Released','Released or waived; excluded.');
  if(entry&&PRACTICE.has(rs))return mk('practice_squad',false,'Practice squad','Practice squad or development roster; not on the active roster.');
  const reportStatus=String(rep?.report_status||'').trim().toLowerCase(),practice=String(rep?.practice_status||'').trim().toLowerCase();
  if(/^out|^inactive|injured reserve|suspend/.test(reportStatus))return mk('out',false,'Ruled out',`Game status: ${rep.report_status}.`);
  if(/doubtful/.test(reportStatus))return mk('doubtful',false,'Doubtful','Listed doubtful; treated as out unless upgraded.');
  if(!entry)return mk('unknown',false,'Availability unconfirmed','Not found in the current roster snapshot; not treated as active.');
  if(!ACTIVE.has(rs))return mk('unknown',false,'Availability unconfirmed','The roster status is not recognized as active; not treated as active.');
  if(entry.teamConflict||(team&&entry.team&&team!==entry.team))return mk('unknown',false,'Team assignment unconfirmed','Player team assignments disagree; not treated as active.');
  if(strict()&&!fresh.ok)return mk('unverified',false,'Availability unverified',`Roster/injury data is stale or missing (${fresh.reason}); nothing is assumed active until the next refresh.`);
  if(requireRecentGame){const t=Date.parse(lastGame);if(!finite(t)||t>now||now-t>limits.staleGameDays*86400000)return mk('stale',false,'No recent game',`No appearance in the last ${limits.staleGameDays} days; history is not current form.`);}
  if(/questionable|game.?time|^gtd/.test(reportStatus))return mk('questionable',true,'Questionable','Game status questionable. Inactives are announced about 90 minutes before kickoff.',{caution:true});
  if(/did not|^dnp/.test(practice))return mk('dnp',true,'Missed practice','Did not practice this week; confirm the final report.',{caution:true});
  if(/limited/.test(practice))return mk('limited',true,'Limited in practice','Limited participation this week.',{caution:true});
  return mk('active',true,'Active','Active on the roster; no current report. Game-day inactives are announced about 90 minutes before kickoff.');
 }
 // Every id the engine currently refuses (confirmed statuses and, in strict mode with stale data, everyone: callers should use decide() for per-player answers).
 function blockedIds(profiles=null){
  const out=new Set();
  for(const id of new Set([...Object.keys(idx.players),...Object.keys(idx.reports)])){const d=decide(id,{requireRecentGame:false});if(!d.actionable)out.add(id);}
  if(profiles)for(const id of Object.keys(profiles)){const d=decide(id,{team:profiles[id]?.team,requireRecentGame:false});if(!d.actionable)out.add(id);}
  return out;
 }
 return {decide,blockedIds,fresh,asOf,week:ctxWeek,index:idx,limits};
}
const api={LIMITS,freshness,index,create};
root.GoingEligibility=api;
if(typeof module!=='undefined')module.exports=api;
})(globalThis);
