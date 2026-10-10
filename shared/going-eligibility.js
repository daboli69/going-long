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
const LIMITS={injuryHours:36,rosterHours:36,staleGameDays:21};
const hoursOld=(t,now)=>{const ms=Date.parse(t);return Number.isFinite(ms)?(now-ms)/3600000:null;};
function freshness(injury,roster,now=Date.now(),limits=LIMITS){
 const iAge=hoursOld(injury?.generated_at,now),rAge=hoursOld(roster?.generated_at,now);
 const injuryOk=iAge!=null&&iAge>=-.5&&iAge<=limits.injuryHours,rosterOk=rAge!=null&&rAge>=-.5&&rAge<=limits.rosterHours;
 const reasons=[];
 if(!injury)reasons.push('injury file missing');else if(!injuryOk)reasons.push(iAge==null?'injury file has no timestamp':`injury file ${Math.round(iAge)} hours old`);
 if(!roster)reasons.push('roster snapshot missing');else if(!rosterOk)reasons.push(rAge==null?'roster snapshot has no timestamp':`roster snapshot ${Math.round(rAge)} hours old`);
 return {ok:injuryOk&&rosterOk,injuryOk,rosterOk,injuryAsOf:injury?.generated_at||null,rosterAsOf:roster?.generated_at||null,injuryAgeHours:iAge,rosterAgeHours:rAge,reason:reasons.join('; ')};
}
function strict(){return root.GOING_ELIGIBILITY_STRICT!==false;}
function severity(r){const s=String(r?.report_status||'').toLowerCase();return /^out|^inactive|injured reserve|suspend/.test(s)?4:/doubtful/.test(s)?3:/questionable|game.?time|^gtd/.test(s)?2:/did not/.test(String(r?.practice_status||'').toLowerCase())?1:0;}
// Merge the injury file (statuses incl. reserve/practice squad) with the all-teams roster snapshot (bye teams, injury objects).
function index(injury,roster,week){
 const players={},reports={},bye=new Set(roster?.bye_carry_forward_teams||[]);
 for(const v of Object.values(injury?.current_players||{}))if(v?.gsis_id)players[v.gsis_id]=v;
 for(const v of Object.values(injury?.current_reports||{}))if(v?.gsis_id&&(!finite(week)||!finite(v.week)||v.week>=week))reports[v.gsis_id]=v;
 for(const v of roster?.players||[])if(v?.id){
  if(!players[v.id])players[v.id]={gsis_id:v.id,roster_status:v.roster_status,team:v.team,from_roster:true};
  const r=v.injury;if(r&&(!finite(week)||!finite(r.week)||r.week>=week)){const cand={gsis_id:v.id,...r};// two sources disagree: keep the more severe report
   if(!reports[v.id]||severity(cand)>severity(reports[v.id]))reports[v.id]=cand;}
 }
 return {players,reports,bye};
}
function create({injury,roster,week,now=Date.now(),limits=LIMITS}={}){
 const idx=index(injury,roster,week),fresh=freshness(injury,roster,now,limits),asOf=injury?.generated_at||roster?.generated_at||null;
 const ctxWeek=finite(week)?week:null;
 function decide(id,{team=null,lastGame=null,hasGame=null,requireRecentGame=true}={}){
  const entry=idx.players[id],rep=idx.reports[id],rs=String(entry?.roster_status||'').toUpperCase(),club=team||entry?.team||null;
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
  const status=String(rep?.report_status||'').toLowerCase(),practice=String(rep?.practice_status||'').toLowerCase();
  if(/^out|^inactive|injured reserve|suspend/.test(status))return mk('out',false,'Ruled out',`Game status: ${rep.report_status}.`);
  if(/doubtful/.test(status))return mk('doubtful',false,'Doubtful','Listed doubtful; treated as out unless upgraded.');
  if(!entry)return mk('unknown',false,'Availability unconfirmed','Not found in the current roster snapshot; not treated as active.');
  if(strict()&&!fresh.ok)return mk('unverified',false,'Availability unverified',`Roster/injury data is stale or missing (${fresh.reason}); nothing is assumed active until the next refresh.`);
  if(requireRecentGame){const t=Date.parse(lastGame);if(!finite(t)||now-t>limits.staleGameDays*86400000)return mk('stale',false,'No recent game',`No appearance in the last ${limits.staleGameDays} days; history is not current form.`);}
  if(/questionable|game.?time|^gtd/.test(status))return mk('questionable',true,'Questionable','Game status questionable. Inactives are announced about 90 minutes before kickoff.',{caution:true});
  if(/did not|^dnp/.test(practice))return mk('dnp',true,'Missed practice','Did not practice this week; confirm the final report.',{caution:true});
  if(/limited/.test(practice))return mk('limited',true,'Limited in practice','Limited participation this week.',{caution:true});
  return mk('active',true,'Active','Active on the roster; no current report. Game-day inactives are announced about 90 minutes before kickoff.');
 }
 // Every id the engine currently refuses (confirmed statuses and, in strict mode with stale data, everyone: callers should use decide() for per-player answers).
 function blockedIds(profiles=null){
  const out=new Set();
  for(const id of Object.keys(idx.players)){const d=decide(id,{requireRecentGame:false});if(!d.actionable)out.add(id);}
  if(profiles&&strict()&&!fresh.ok)for(const id of Object.keys(profiles))out.add(id);
  return out;
 }
 return {decide,blockedIds,fresh,asOf,week:ctxWeek,index:idx,limits};
}
const api={LIMITS,freshness,index,create};
root.GoingEligibility=api;
if(typeof module!=='undefined')module.exports=api;
})(globalThis);
