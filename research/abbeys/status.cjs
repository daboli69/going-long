'use strict';
// Product status only. Never changes v1 model/protocol bytes or captures a board.
const fs=require('node:fs'),path=require('node:path');
const core=require('../../shared/abbeys-core.cjs');
function currentStatus(schedule,weeks,now=new Date().toISOString()) {
  const clock=Date.parse(now),receipt=Date.parse(schedule?.generated_at);
  if (!Number.isFinite(clock) || !Number.isFinite(receipt) || receipt>clock || clock-receipt>36*3600000) return {status:'unavailable',reason:'Current NFL schedule is missing, stale or future-dated. Frozen historical boards remain available.'};
  const season=schedule.season;
  const input=core.projectSources(schedule,{generated_at:schedule.generated_at,games:{}},season,now);
  const pools=[...new Set(input.schedule.map(g=>g.week))].map(week=>({week,games:core.gameWindow(input,week)})).filter(p=>p.games.length && Date.parse(p.games.at(-1).kickoff)+12*3600000>=clock).sort((a,b)=>a.week-b.week);
  if (!pools.length) return {season,status:'complete',reason:'No remaining regular-season Sunday/Monday week is in this schedule.'};
  const {week,games}=pools[0],frozen=weeks.find(w=>w.season===season && w.week===week);
  const wholeWeek=input.schedule.filter(g=>g.week===week);
  const origin=new Date(Math.min(...wholeWeek.map(g=>Date.parse(g.kickoff)))-12*3600000).toISOString();
  return {season,week,status:frozen?'frozen':'not-frozen',captureDeadline:games[0].kickoff,registeredOrigin:origin,scheduledOriginPassed:clock>Date.parse(origin),
    reason:frozen?'Current-week official board is frozen.':`Week ${week} has not been captured or published. ${clock>=Date.parse(games[0].kickoff)?'The first applicable kickoff has passed; official picks cannot be backfilled.':'A prospective manual board may still be captured before the first Sunday/Monday kickoff.'} ${clock>Date.parse(origin)?'The registered scheduled origin has passed; no scheduled holdout catch-up is allowed.':''}`.trim()};
}
function readStatus(root,weeks,now) {
  try {return currentStatus(JSON.parse(fs.readFileSync(path.join(root,'data/nfl_betting.json'),'utf8')),weeks,now);}
  catch {return {status:'unavailable',reason:'Current NFL schedule could not be verified. Frozen historical boards remain available.'};}
}
if(require.main===module){const root=path.resolve(process.argv[2]||'.'),board=JSON.parse(fs.readFileSync(path.join(root,'data/abbeys-board.json'),'utf8'));console.log(JSON.stringify(readStatus(root,board.weeks||[]),null,2));}
module.exports={currentStatus,readStatus};
