'use strict';

// ABBEYS is an independent, current-season-only score benchmark. The predictive
// boundary copies a small allowlist; market data, ratings and older seasons never
// enter it. Context is attached only after the prediction has been journaled.
const MODEL_VERSION = 'abbeys-current-season-v1';
const TEAMS = new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
const team = value => value === 'LAR' ? 'LA' : value;
const iso = value => {
  if (typeof value!=='string' || !/^(\d{4})-(\d{2})-(\d{2})T\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value) || !Number.isFinite(Date.parse(value))) return false;
  const [y,m,d]=value.slice(0,10).split('-').map(Number),check=new Date(Date.UTC(y,m-1,d));
  return check.getUTCFullYear()===y && check.getUTCMonth()===m-1 && check.getUTCDate()===d;
};
const finiteScore = value => Number.isInteger(value) && value >= 0 && value <= 100;
function identity(id, season) {
  const m = /^(\d{4})_(\d{2})_([A-Z]+)_([A-Z]+)$/.exec(id || '');
  if (!m || +m[1] !== season || +m[2] < 1 || +m[2] > 18) return null;
  const away = team(m[3]), home = team(m[4]);
  if (!TEAMS.has(away) || !TEAMS.has(home) || away === home) throw new Error(`Invalid NFL identity: ${id}`);
  return {gameId:id, season, week:+m[2], away, home};
}
function checkReceipt(data, cutoff, label) {
  if (!iso(data?.generated_at) || Date.parse(data.generated_at) > Date.parse(cutoff)) throw new Error(`${label}: missing/future receipt`);
}
function projectSources(scheduleSource, resultSource, season, cutoff) {
  if (!Number.isInteger(season) || !iso(cutoff)) throw new Error('Explicit season and ISO cutoff required');
  checkReceipt(scheduleSource, cutoff, 'schedule');
  checkReceipt(resultSource, cutoff, 'results');
  const schedules = new Map(), results = new Map();
  for (const raw of scheduleSource.games || []) {
    const id = identity(raw.game_id, season);
    if (!id) {if (raw.season===season) throw new Error('Malformed current-season schedule identity');continue;}
    if (raw.season !== season || raw.week !== id.week || team(raw.away) !== id.away || team(raw.home) !== id.home || !iso(raw.kickoff)) throw new Error(`Conflicting schedule identity: ${id.gameId}`);
    const row = {...id,kickoff:raw.kickoff,neutral:raw.location === 'Neutral' || raw.neutral_site === true};
    if (schedules.has(row.gameId)) throw new Error(`Duplicate schedule: ${row.gameId}`);
    schedules.set(row.gameId,row);
  }
  for (const raw of Object.values(resultSource.games || {})) {
    if (raw.sport !== 'nfl') continue;
    const id = identity(raw.id,season);
    if (!id) {if (String(raw.id||'').startsWith(String(season))) throw new Error('Malformed current-season result identity');continue;}
    if (team(raw.away) !== id.away || team(raw.home) !== id.home || !iso(raw.kickoff) || !finiteScore(raw.awayScore) || !finiteScore(raw.homeScore)) throw new Error(`Invalid result: ${id.gameId}`);
    if (Date.parse(raw.kickoff) >= Date.parse(cutoff)) throw new Error(`Future result: ${id.gameId}`);
    const scheduled = schedules.get(id.gameId);
    if (!scheduled || Date.parse(scheduled.kickoff) !== Date.parse(raw.kickoff)) throw new Error(`Result/schedule mismatch: ${id.gameId}`);
    if (results.has(id.gameId)) throw new Error(`Duplicate result: ${id.gameId}`);
    results.set(id.gameId,{...id,kickoff:raw.kickoff,awayScore:raw.awayScore,homeScore:raw.homeScore});
  }
  return {season,cutoff,schedule:[...schedules.values()].sort(order),results:[...results.values()].sort(order)};
}
function order(a,b) { return Date.parse(a.kickoff)-Date.parse(b.kickoff) || a.gameId.localeCompare(b.gameId); }
function easternParts(kickoff) {
  return Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(kickoff)).map(p=>[p.type,p.value]));
}
function gameWindow(input,week) {
  if (!Number.isInteger(week) || week < 1 || week > 18) throw new Error('Invalid NFL regular-season week');
  return input.schedule.filter(g=>g.week===week).filter(g=>{
    const p=easternParts(g.kickoff);
    return p.weekday==='Mon' || (p.weekday==='Sun' && (+p.hour*60 + +p.minute >= 570));
  }).sort(order);
}
function averageModel(results) {
  if (!results.length) return {stats:{},mean:null,homeEdge:null};
  const stats={}; let total=0,edge=0;
  for (const g of results) {
    for (const [t,pf,pa] of [[g.away,g.awayScore,g.homeScore],[g.home,g.homeScore,g.awayScore]]) {
      const s=stats[t] ||= {games:0,pf:0,pa:0,wins:0,losses:0,ties:0};
      s.games++;s.pf+=pf;s.pa+=pa;s.wins+=pf>pa?1:0;s.losses+=pf<pa?1:0;s.ties+=pf===pa?1:0;
    }
    total+=g.awayScore+g.homeScore;edge+=g.homeScore-g.awayScore;
  }
  for (const s of Object.values(stats)) {s.pf/=s.games;s.pa/=s.games;}
  return {stats,mean:total/(2*results.length),homeEdge:edge/results.length};
}
function scoreGame(model,g) {
  if (model.mean===null) return {away:null,home:null,margin:null};
  const a=model.stats[g.away] || {pf:model.mean,pa:model.mean},h=model.stats[g.home] || {pf:model.mean,pa:model.mean};
  const venue=g.neutral?0:model.homeEdge;
  const away=Math.max(0,(a.pf+h.pa)/2-venue/2),home=Math.max(0,(h.pf+a.pa)/2+venue/2);
  return {away,home,margin:home-away};
}
function winnerOf(g,score) {return score.margin===null || score.margin===0 ? [g.away,g.home].sort()[0] : score.margin>0?g.home:g.away;}
function integerScore(g,score,winner) {
  if (score.home===null) return {away:null,home:null};
  let away=Math.round(score.away),home=Math.round(score.home);
  if ((winner===g.home && home>away) || (winner===g.away && away>home)) return {away,home};
  // Closest nonnegative integer score consistent with the declared winner.
  const pairs=winner===g.home ? [{away,home:away+1},{away:Math.max(0,home-1),home}] : [{away:home+1,home},{away,home:Math.max(0,away-1)}];
  return pairs.filter(p=>winner===g.home?p.home>p.away:p.away>p.home).sort((a,b)=>((a.away-score.away)**2+(a.home-score.home)**2)-((b.away-score.away)**2+(b.home-score.home)**2) || a.away+a.home-b.away-b.home)[0];
}
function predictWeek(input,week) {
  const games=gameWindow(input,week);
  if (!games.length) throw new Error('No Sunday/Monday games in this week');
  if (games.some(g=>Date.parse(g.kickoff)<=Date.parse(input.cutoff))) throw new Error('Weekly official board must freeze before its first kickoff; no backfill');
  // Earlier weeks only: Thursday in the target week is intentionally excluded.
  const training=input.results.filter(g=>g.week<week && Date.parse(g.kickoff)+12*3600000<Date.parse(input.cutoff));
  const model=averageModel(training), priorWeeks=[...new Set(training.map(g=>g.week))];
  const refits=priorWeeks.map(w=>averageModel(training.filter(g=>g.week!==w)));
  const picks=games.map(g=>{
    const raw=scoreGame(model,g),winner=winnerOf(g,raw),integer=integerScore(g,raw,winner);
    const a=model.stats[g.away],h=model.stats[g.home];
    const limited=!a || !h || a.games<3 || h.games<3 || refits.some(m=>!m.stats[g.away]?.games || !m.stats[g.home]?.games);
    const stable=!limited && raw.margin!==0 && refits.every(m=>m.stats[g.away]?.games>=1 && m.stats[g.home]?.games>=1 && scoreGame(m,g).margin!==0 && winnerOf(g,scoreGame(m,g))===winner);
    const sensitivity=refits.map(m=>scoreGame(m,g).margin).filter(Number.isFinite);
    const confidence=raw.margin===null?'No score evidence':raw.margin===0?'Toss-up':limited?'Limited evidence':stable?'Stable lean':'Sensitive lean';
    const s=model.stats[winner],opp=model.stats[winner===g.away?g.home:g.away],other=winner===g.away?g.home:g.away;
    const support=s&&opp ? [
      `${winner} scores ${s.pf.toFixed(1)} points/game; ${other} allows ${opp.pa.toFixed(1)} in this season's earlier games.`,
      `${winner} allows ${s.pa.toFixed(1)} points/game; ${other} scores ${opp.pf.toFixed(1)}. Both scoring and prevention enter the forecast equally.`,
      `Net scoring: ${winner} ${(s.pf-s.pa>=0?'+':'')+(s.pf-s.pa).toFixed(1)}/game versus ${other} ${(opp.pf-opp.pa>=0?'+':'')+(opp.pf-opp.pa).toFixed(1)}/game.`
    ] : ['Current-season scoring evidence is incomplete; no prior-season strength or sportsbook fallback is used.'];
    const concerns=[];
    if (raw.margin===0 || raw.margin===null) concerns.push('No model separation: the alphabetically first team code breaks the tie; this is not evidence of an advantage.');
    if (limited) concerns.push(`Only ${a?.games||0} ${g.away} and ${h?.games||0} ${g.home} earlier-season games; limited evidence.`);
    if (!stable && !limited && raw.margin!==0) concerns.push('Omitting one earlier week changes or ties the pick. The direction is sensitive to this small sample.');
    if (s&&opp && s.pf<opp.pf) concerns.push(`${other} has the higher raw scoring average (${opp.pf.toFixed(1)} vs ${s.pf.toFixed(1)}); defense and the designated-home term drive the other direction.`);
    if (s&&opp && s.pa>opp.pa) concerns.push(`${winner} has allowed more points/game than ${other} (${s.pa.toFixed(1)} vs ${opp.pa.toFixed(1)}).`);
    concerns.push('Scores include special-teams/defensive scoring. Opponent strength, personnel changes and weather are not quantified by this benchmark.');
    if (!g.neutral) concerns.push(`Venue adjustment uses this season's designated-home margin (${model.homeEdge===null?'unavailable':model.homeEdge.toFixed(1)} points). Neutral-site metadata is incomplete.`);
    return {...g,winner,confidence,projectedAway:integer.away,projectedHome:integer.home,rawAway:raw.away,rawHome:raw.home,support,concerns,gamesAway:a?.games||0,gamesHome:h?.games||0,sensitivityRange:sensitivity.length?[Math.min(...sensitivity),Math.max(...sensitivity)]:null,settlement:null};
  });
  const monday=[...picks].filter(g=>easternParts(g.kickoff).weekday==='Mon').at(-1);
  return {season:input.season,week,modelVersion:MODEL_VERSION,picks,monday:monday?{gameId:monday.gameId,away:monday.away,home:monday.home,predictedAway:monday.projectedAway,predictedHome:monday.projectedHome}:null,training,methodology:{name:'Current-season scoring benchmark',description:'Symmetric average of team points scored and opponent points allowed, plus this season’s designated-home scoring margin. Earlier weeks only; no odds or prior-season ratings.',limitations:['Direction stability is a leave-one-week-out sensitivity diagnostic, not win probability.','No validated opponent/recency/personnel weighting; exact score is an illustrative point forecast.','Historical method checks use each season independently; official prospective results start with this frozen board.']}};
}
function settlementFor(pick,result,source,settledAt) {
  if (!result || result.gameId!==pick.gameId || result.away!==pick.away || result.home!==pick.home || Date.parse(result.kickoff)!==Date.parse(pick.kickoff)) return {state:'unresolved',reason:'Missing or ambiguous game identity'};
  if (!finiteScore(result.awayScore) || !finiteScore(result.homeScore) || !iso(settledAt) || Date.parse(settledAt)<=Date.parse(pick.kickoff)) return {state:'unresolved',reason:'Invalid or premature result evidence'};
  const actualWinner=result.awayScore===result.homeScore?null:result.awayScore>result.homeScore?result.away:result.home;
  return {state:'settled',outcome:actualWinner===null?'tie':actualWinner===pick.winner?'win':'loss',actualAway:result.awayScore,actualHome:result.homeScore,settledAt,source};
}
module.exports={MODEL_VERSION,projectSources,gameWindow,averageModel,scoreGame,predictWeek,settlementFor,easternParts,integerScore};
