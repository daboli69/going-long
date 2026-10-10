/* GOING Picks v2: transparent research ordering, never probability or value.
 * The underlying models, GOING Score and frozen ranking policies are unchanged.
 */
(function(root){
'use strict';
const VERSION='football-case-v3';// v3 (2026-10-09): correlated evidence no longer stacks; see docs/GOING_PICKS.md
const FAMILIES={rec_yds:'Receiving',receptions:'Receiving',rush_yds:'Rushing',pass_yds:'Passing',pass_tds:'Passing',rush_tds:'TD',rec_tds:'TD',atd:'TD',spread:'Game',total:'Game',moneyline:'Game'};
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const intel=()=>root.GoingIntel||(typeof require!=='undefined'?require('./going-intel.js'):null);
const clean=x=>String(x??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const team=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[String(x||'').toUpperCase()]||String(x||'').toUpperCase();
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const etDate=x=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x));
const recent=(at,now,days=28)=>Number.isFinite(Date.parse(at))&&Date.parse(at)<=now&&now-Date.parse(at)<=days*86400000;
const avg=(rows,key)=>rows.length&&rows.every(r=>finite(r[key]))?rows.reduce((s,r)=>s+r[key],0)/rows.length:null;
function gameKey(c){return [c.sport,team(c.away),team(c.home),Number.isFinite(Date.parse(c.kickoff))?etDate(c.kickoff):'invalid'].join('|');}
function familyKey(c){return [gameKey(c),c.kind,c.profileId||'game',c.market].join('|');}
function contractKey(c){return [familyKey(c),c.side,c.line].join('|');}
// v3: the model, the current-production average and the 2-vs-2 usage split are all read from the same few games, so none of them counts as independent evidence;
// without a matchup, an injury split or another independent component the tier stops at 3. Game lines have no independent evidence on this board and stop at 3.
// v2 receipts keep their original rule (model and production only), so the frozen v2 cohort still validates.
function evidenceTier(points,components,market,version=VERSION){
 let tier=Math.max(1,Math.min(5,points));
 const dependent=version==='football-case-v2'?['model','production']:['model','production','usage'];
 if(!components.some(x=>x.points>0&&!dependent.includes(x.id)))tier=Math.min(tier,3);
 if(version!=='football-case-v2'&&['spread','total','moneyline'].includes(market))tier=Math.min(tier,3);
 return market==='atd'?Math.min(tier,2):tier;
}
function granularRating(c,tier){
 const direction=['Over','Home'].includes(c.side)?1:['Under','Away'].includes(c.side)?-1:0;
 const mean=c.kind==='game'?c.modelMean:c.projMean,sd=c.kind==='game'?c.modelSd:c.projSd;
 const gap=c.market==='atd'||!direction||!finite(mean)?null:direction*(mean+(c.market==='spread'?c.line:c.market==='moneyline'?0:-c.line));
 // Refine only WITHIN the existing evidence tier. One forecast SD saturates;
 // missing spread is unknown, not evidence against the football thesis.
 const strength=finite(gap)&&finite(sd)&&sd>0?Math.max(0,Math.min(1,gap/sd)):null;
 return {rating:(tier-1)*20+1+Math.round(19*(strength??0)),detail:{method:'directional-margin-sd-v1',gap,sd:finite(sd)&&sd>0?sd:null,strength}};
}
function quote(c,now=Date.now()){
 const decimal=c.odds>0?1+c.odds/100:1+100/Math.abs(c.odds),age=now-Date.parse(c.updatedAt);
 const valid=finite(c.odds)&&Math.abs(c.odds)>=100&&finite(c.dec)&&Math.abs(c.dec-decimal)<.005&&!!String(c.book||'').trim();
 return {valid,fresh:valid&&finite(age)&&age>=0&&age<=300000,age,saveable:valid&&finite(age)&&age>=0&&age<=86400000};
}
function playerContext(c,o){
 const scope=o.context?.scopes?.[String(o.season)],p=scope?.players?.[c.profileId];
 if(!p||p.player_id!==c.profileId||team(p.team)!==team(c.team)||p.season!==o.season||!recent(p.last_game,o.now)||!recent(o.context.generated_at,o.now,1))return null;
 const verified=o.context?.picks_evidence,log=verified?.season===o.season&&recent(verified.generated_at,o.now,1)?verified.recent_player_games?.[team(c.team)+'|'+c.profileId]?.games_log:null;
 const rows=(log||Object.values(scope.player_game_usage||{})).filter(r=>r.player_id===c.profileId&&team(r.team)===team(c.team)&&recent(r.date,o.now)&&new Date(r.date).getUTCFullYear()===o.season).sort((a,b)=>String(a.date).localeCompare(String(b.date))).map(r=>({...r,rush_attempts:r.carries??r.rush_attempts}));
 const volume=['rec_yds','receptions','rec_tds'].includes(c.market)?'targets':['rush_yds','rush_tds'].includes(c.market)?'rush_attempts':null;
 // Two observed games in each chronological half. Sparse absence is never zero.
 const split=Math.floor(rows.length/2),early=rows.slice(0,split),late=rows.slice(split),before=volume&&early.length>=2?avg(early,volume):null,after=volume&&late.length>=2?avg(late,volume):null;
 const trend=finite(before)&&finite(after)&&before>0&&Math.abs(after-before)>=1&&Math.abs(after/before-1)>=.2?Math.sign(after-before):0;
 return {player:p,rows,volume,before,after,trend,verified:!!log};
}
// Process evidence, not a forecast: pooled sd per sqrt(game) and floors come from the 2022-24 ffopportunity
// noise study; 2025 showed no replicated persistence, so these labels carry ZERO rating points.
const OPPORTUNITY_RULE={version:'opportunity-process-v1',sd:{RB:4.93,WR:4.91,TE:3.72},minGames:4,minExpectedPerGame:5,z:1.28,minAbsDelta:6,minRelDelta:.25,tdShare:.6};
function opportunityProcess(c,o){
 const ev=o.context?.picks_evidence,op=ev?.opportunity_process;
 if(c.kind!=='prop'||op?.season!==o.season||op.provenance?.expected_points?.status!=='loaded'||!recent(op.generated_at,o.now,1))return null;
 const key=team(c.team)+'|'+c.profileId,row=op.expected_vs_actual?.[key],usage=op.situational_usage?.[key],sd=OPPORTUNITY_RULE.sd[row?.position];
 const total=row?.totals?.fantasy_points,out={usage:usage?.player_id===c.profileId?usage:null,process:null};
 if(!row||row.player_id!==c.profileId||!sd||!total||!finite(total.expected)||!finite(total.actual)||row.games<OPPORTUNITY_RULE.minGames)return out;
 const delta=total.actual-total.expected,z=delta/(sd*Math.sqrt(row.games)),R=OPPORTUNITY_RULE;
 const td=finite(row.totals?.rec_tds?.delta)||finite(row.totals?.rush_tds?.delta)?6*((row.totals.rec_tds?.delta||0)+(row.totals.rush_tds?.delta||0)):null;
 if(total.expected/row.games<R.minExpectedPerGame||Math.abs(z)<R.z||Math.abs(delta)<R.minAbsDelta||Math.abs(delta)/total.expected<R.minRelDelta)return out;
 const tdDriven=finite(td)&&Math.sign(td)===Math.sign(delta)&&Math.abs(td)>=R.tdShare*Math.abs(delta),over=delta>0;
 out.process={state:over?'over':'under',delta,expected:total.expected,actual:total.actual,z,games:row.games,tdDriven,
  badge:tdDriven?(over?'TD ABOVE EXPECTED':'TD BELOW EXPECTED'):(over?'OVERPERFORMED OPPORTUNITY':'UNDERPERFORMED OPPORTUNITY'),
  detail:`${delta>0?'+':''}${delta.toFixed(1)} fantasy points vs expected over ${row.games} games (${total.actual.toFixed(1)} actual, ${total.expected.toFixed(1)} expected, z ${z>0?'+':''}${z.toFixed(1)})${tdDriven?'; mostly touchdowns above/below expectation':''}. Descriptive only: expected points already reflect opportunity, small samples are noisy, and this is not a bounce-back or regression forecast.`};
 return out;
}
function situationText(u,family){
 const pct=x=>finite(x)?Math.round(100*x)+'%':'n/a',parts=[];
 const kinds=family==='Receiving'?['targets']:family==='Rushing'?['carries']:['targets','carries'];
 for(const [label,k] of [['Red zone','red_zone'],['Inside 5','inside_5'],['Third down','third_down']])for(const kind of kinds){
  const x=u[k];if(!x||!(x['team_'+kind]>0))continue;
  parts.push(`${label} ${kind}: ${x[kind]} of team ${x['team_'+kind]} (${pct(x[kind==='targets'?'target_share':'carry_share'])})`);
 }
 return parts.join(' · ');
}
function assess(c,options={}){
 const o={now:Date.now(),season:new Date().getUTCFullYear(),...options};
 const family=FAMILIES[c.market],price=quote(c,o.now),components=[],badges=[],facts=[],supports=[],concerns=[],unknown=[];
 const add=(id,points,detail)=>components.push({id,points,detail});
 const row=o.injuryLearning?.current_players?.[team(c.team)+'|'+clean(c.player)],status=String(row?.roster_status||'').toUpperCase();
 const invalid=!family||!['nfl','ncaa'].includes(c.sport)||!['game','prop'].includes(c.kind)||c.sport==='ncaa'&&c.kind==='prop'||!Number.isFinite(Date.parse(c.kickoff))||Date.parse(c.kickoff)<=o.now||c.manual||c.dfs||!finite(c.line)||!finite(c.prob)||c.prob<=0||c.prob>=1||!finite(c.n)||c.n<5||!recent(o.historyAt,o.now,1)||c.kind==='prop'&&(!c.profileId||!recent(c.profileDate,o.now))||c.injury?.blockRecommendation||['RES','INA','PUP','IR','SUS'].includes(status);
 // Price is context, never a veto on the football case (docs/GOING_PICKS.md). A former `check` flag veto read c.flags, which this board never populates, so it never fired;
 // it was removed and an unusually large model/book disagreement is now shown as a price caution instead.
 const identityIssue=c.kind==='prop'&&(![team(c.home),team(c.away)].includes(team(c.team))||row?.gsis_id&&row.gsis_id!==c.profileId);
 if(invalid||identityIssue)return {version:VERSION,eligible:false,reason:identityIssue?'Player/team does not match this game':!family?'Market needs its own framework':c.injury?.blockRecommendation||['RES','INA','PUP','IR','SUS'].includes(status)?'Player is unavailable':'A matched pregame model/contract is unavailable',price};
 const direction=c.side==='Over'?1:c.side==='Under'?-1:c.side==='Home'?1:c.side==='Away'?-1:0;
 let modelSign=0;
 if(c.market==='spread')modelSign=Math.sign(direction*(c.modelMean+c.line));
 else if(c.market==='moneyline')modelSign=Math.sign(direction*c.modelMean);
 else if(c.market==='total')modelSign=Math.sign(direction*(c.modelMean-c.line));
 else if(c.market!=='atd'&&finite(c.projMean))modelSign=Math.sign(direction*(c.projMean-c.line));
 // v3: a model "edge" must clear a quarter of the forecast SD, and a yardage mean must be positive. The sign alone made lines the projection merely sat on look like support.
 let belowEdge=false;
 if(modelSign&&c.market!=='atd'){
  const sdGap=c.kind==='game'?c.modelSd:c.projSd,gap=Math.abs(c.market==='spread'?c.modelMean+c.line:c.market==='moneyline'?c.modelMean:c.market==='total'?c.modelMean-c.line:c.projMean-c.line);
  if(finite(sdGap)&&sdGap>0&&gap<.25*sdGap)belowEdge=true;
  if(c.kind==='prop'&&['rec_yds','rush_yds','pass_yds'].includes(c.market)&&!(c.projMean>0))belowEdge=true;
  if(belowEdge)modelSign=0;
 }
 // ATD Yes lacks a comparable model-direction test. Any p>0 is not support.
 if(finite(modelSign)&&modelSign){add('model',2*modelSign,`Existing model ${modelSign>0?'favors':'opposes'} this exact direction${finite(c.projMean)?`: ${c.projMean.toFixed(1)} vs ${c.line}`:''}.`);if(modelSign>0){badges.push('MODEL +');supports.push(components.at(-1).detail);}else concerns.push(components.at(-1).detail);}
 else unknown.push(c.market==='atd'?'Any TD model direction is not graded.':belowEdge?'The model is within a quarter of a standard deviation of this line: no edge.':'The model is neutral at this exact line.');
 let roleSign=0,volumeSign=0;
 const role=o.currentRoleEvidence,pc=playerContext(c,o);
 if(c.kind==='prop'){
  const production=role?.playerId===c.profileId&&team(role.team)===team(c.team)&&role.season===o.season&&recent(role.latest,o.now)?role.means?.[c.market]:null;
  if(c.market!=='atd'&&finite(production)&&direction){const sign=Math.sign(direction*(production-c.line));add('production',sign,`Current ${role.games}-game average ${production.toFixed(1)} ${sign>0?'agrees with':'does not favor'} ${c.side} ${c.line}.`);if(sign>0)supports.push(components.at(-1).detail);else if(sign<0)concerns.push(components.at(-1).detail);}
  else unknown.push('Comparable current production is unavailable.');
  const volume=family==='Receiving'?role?.means?.targets:family==='Rushing'?role?.means?.carries:family==='Passing'?role?.means?.attempts:null;
  if(finite(volume)&&volume>0){if(direction>=0)badges.push('VOLUME');facts.push(['Current opportunity',`${volume.toFixed(1)} ${family==='Receiving'?'targets':family==='Rushing'?'carries':'pass attempts'}/game (${role.games} observed games)`]);if(direction>=0)supports.push(facts.at(-1)[1]);}
  else if(pc)facts.push(['Observed offensive role',`${pc.player.games} games · ${finite(pc.player.target_share)?(100*pc.player.target_share).toFixed(1)+'% target share':'target share unknown'} · ${finite(pc.player.rush_share)?(100*pc.player.rush_share).toFixed(1)+'% rush share':'rush share unknown'}`]);
  else unknown.push('Current opportunity is unknown.');
  if(pc?.trend&&direction){const points=direction*pc.trend;add('usage',points,`${pc.volume==='targets'?'Targets':'Carries'} moved ${pc.before.toFixed(1)} → ${pc.after.toFixed(1)} per observed game (two chronological groups of ${Math.floor(pc.rows.length/2)}+).`);badges.push((pc.volume==='targets'?'TARGETS ':'CARRIES ')+(pc.trend>0?'↑':'↓')+(points<0?' vs '+(direction>0?'Over':'Under'):''));volumeSign=pc.trend;(points>0?supports:concerns).unshift(components.at(-1).detail);concerns.push('Short usage trend; opportunity counts do not prove a lasting role change or an injury cause.');}
  else unknown.push('Role trend needs at least two observed games in each period.');
  if(pc){facts.push(['Current PBP role cutoff',pc.player.last_game],['Snap / route distinction',`${finite(pc.player.share)?(100*pc.player.share).toFixed(1)+'% '+pc.player.share_type:'Unknown snap share'}; measured routes ${pc.player.routes==null?'unavailable':pc.player.routes}`]);if(finite(pc.player.expected_catches)&&finite(pc.player.actual_catches)&&pc.player.catch_model_targets>0){facts.push(['Expected versus actual catches',`${pc.player.expected_catches.toFixed(1)} CP-summed expected / ${pc.player.actual_catches} actual on ${pc.player.catch_model_targets} modeled targets. Descriptive catch opportunity, not expected yards or a bounceback forecast.`]);}}
  if(c.market==='atd'&&role?.tdAppearances>0&&role.games>0&&role.tdAppearances/role.games>=.5){add('td_role',1,`Scored a rushing/receiving TD in ${role.tdAppearances}/${role.games} current appearances.`);supports.push(components.at(-1).detail);badges.push('TD ROLE');}
 }else{
  const g=o.currentGameEvidence,valid=g&&g.sport===c.sport&&team(g.home)===team(c.home)&&team(g.away)===team(c.away)&&g.season===o.season;
  if(valid){const value=c.market==='total'?g.totalContext:g.marginContext,sign=Math.sign(direction*(value+(c.market==='spread'?c.line:0)-(c.market==='total'?c.line:0)));if(finite(value)&&sign){add('production',sign,`Current scoring context ${value.toFixed(1)} ${c.market==='total'?'total':'home margin'} ${sign>0?'agrees':'conflicts'} (${g.awayGames}/${g.homeGames} finals).`);(sign>0?supports:concerns).push(components.at(-1).detail);}facts.push(['Team context','Raw current scores, not an opponent-adjusted forecast.']);}else unknown.push(o.gameEvidenceIssue||'Completed current team context is unknown.');
  const scope=o.context?.scopes?.[String(o.season)];for(const t of [c.away,c.home]){const p=scope?.teams?.[t];if(p&&recent(p.last_game,o.now))facts.push([`${t} game environment`,`${p.games} games · ${finite(p.plays_per_game)?p.plays_per_game.toFixed(1):'?'} plays/game · ${finite(p.pass_over_expected)?(100*p.pass_over_expected).toFixed(1)+'% neutral pass above expectation':'pass tendency unknown'}`]);}
 }
 const match=o.matchup,weak=o.weakness,opponent=c.team===c.home?c.away:c.home,matchedRole=c.market==='rec_yds'?/RECEIVING$/.test(match?.role||''):c.market==='rush_yds'?/RUSHING$/.test(match?.role||''):false;
 if(direction&&matchedRole&&match?.active_signal&&match.player_id===c.profileId&&team(match.opponent)===team(opponent)&&Math.abs(Date.parse(match.kickoff)-Date.parse(c.kickoff))<60000&&weak?.current?.season===o.season&&finite(weak.current.value)&&weak.current.sample>0&&recent(o.learningAt,o.now,1)&&match.lineage?.length&&weak.lineage?.length){const sign=Math.sign(direction*weak.current.value);add('matchup',sign,`${opponent} verified role-matched residual ${weak.current.value.toFixed(2)} yards/opportunity (${weak.current.sample} opportunities).`);badges.push(sign>0?'MATCHUP +':'MATCHUP −');(sign>0?supports:concerns).push(components.at(-1).detail);}else unknown.push('Verified direction-matched matchup is unknown.');
 const injuryEvidence=o.context?.picks_evidence,metric=family==='Receiving'?'targets_per_game':family==='Rushing'?'carries_per_game':null;
 if(metric&&injuryEvidence?.season===o.season&&recent(injuryEvidence.generated_at,o.now,1)){
  const pairs=Object.values(injuryEvidence.teammate_out_splits||{}).filter(x=>x.player_id===c.profileId&&team(x.team)===team(c.team)&&x.season===o.season&&x.status==='descriptive_observed'&&x.with_n>=2&&x.without_n>=2&&finite(x.with?.[metric])&&finite(x.without?.[metric])).sort((a,b)=>Math.min(b.with_n,b.without_n)-Math.min(a.with_n,a.without_n)||String(a.teammate_id).localeCompare(String(b.teammate_id)));
  const effect=pairs[0];
  if(effect){const withValue=effect.with[metric],withoutValue=effect.without[metric],report=injuryEvidence.current_injury_reports?.players?.[team(c.team)+'|'+effect.teammate_id],schedule=(o.context.games||[]).find(g=>team(g.home)===team(c.home)&&team(g.away)===team(c.away)&&Math.abs(Date.parse(g.kickoff)-Date.parse(c.kickoff))<60000),week=Number(String(schedule?.id||'').split('_')[1]);
   const detail=`${effect.teammate_name}: ${withValue.toFixed(1)} ${metric==='targets_per_game'?'targets':'carries'}/game with, ${withoutValue.toFixed(1)} without (${effect.with_n}/${effect.without_n} games). Descriptive association, not a causal forecast.`;
   facts.push(['With/without teammate',detail],['With/without timing',effect.report_timing||'Weekly reports do not establish historical pregame knowledge.']);
   if(report?.week===week&&String(report.report_status).toLowerCase()==='out'&&direction&&Math.abs(withoutValue-withValue)>=1&&withValue>0&&Math.abs(withoutValue/withValue-1)>=.2){const sign=Math.sign(direction*(withoutValue-withValue));add('injury',sign,detail);badges.push('WITH/WITHOUT');(sign>0?supports:concerns).unshift(detail);}
   else facts.push(['Current injury applicability','Historical split only; no exact-game OUT confirmation or meaningful opportunity change. No injury rating points.']);
  }
 }
 if(c.kind==='prop'){
  facts.push(['Projection vs line',finite(c.projMean)?`GOING projects ${c.projMean.toFixed(1)} against a line of ${c.line}${c.market==='atd'?'':` (${c.side})`}.`:'No model projection is attached.']);
  const rt=intel()?.roleTrend(c.roleTrend,c.position,c.market);
  if(rt)roleSign=rt.state==='up'?1:rt.state==='down'?-1:0;
  if(rt){
   facts.push(['Role trend (last 6 games → last 3)',`${rt.text}. ${rt.sentence} Descriptive public data; it earns no rating points.`]);
   const against=direction&&roleSign&&roleSign!==direction;
   if(roleSign&&!against)badges.push(rt.badge);
   else if(against){badges.push(rt.badge+' vs '+(direction>0?'Over':'Under'));concerns.unshift(`${rt.text}: the role has ${rt.state==='up'?'grown':'shrunk'} recently, which works against this ${direction>0?'Over':'Under'}.`);}
   if(roleSign&&!against&&direction)supports.push(`${rt.text}: the role has ${rt.state==='up'?'expanded':'shrunk'} recently, which supports this ${direction>0?'Over':'Under'}.`);
  }
 }
 // Two different measures of the same thing (this season's volume halves vs the multi-season last-6/last-3 role share) can disagree. Say so once instead of showing opposite badges.
 if(volumeSign&&roleSign&&volumeSign!==roleSign){
  for(const b of [...badges])if(/^(TARGETS|CARRIES) [↑↓]( vs (Over|Under))?$/.test(b)||/^ROLE [↑↓]( vs (Over|Under))?$/.test(b))badges.splice(badges.indexOf(b),1);
  badges.push('USAGE MIXED');concerns.unshift('Volume and role signals disagree: the current season per-game volume and the last-6-to-last-3 role share point in opposite directions, so the role change is not clear.');
 }
 // v3: a usage split counts only when the multi-season role share agrees, or when it rests on at least six observed games (two-game halves are noise).
 const usageIndex=components.findIndex(x=>x.id==='usage');
 if(usageIndex>=0){
  const agrees=roleSign!==0?roleSign===volumeSign:(pc?.rows?.length||0)>=6;
  if(!agrees){
   const [gone]=components.splice(usageIndex,1);
   for(const list of [supports,concerns]){const i=list.indexOf(gone.detail);if(i>=0)list.splice(i,1);}
   for(const b of [...badges])if(/^(TARGETS|CARRIES) [↑↓]( vs (Over|Under))?$/.test(b))badges.splice(badges.indexOf(b),1);
   unknown.push('The recent usage split is too short or unconfirmed by the role share: it earns no points.');
  }
 }
 if(c.kind==='prop'&&['atd','rush_tds','rec_tds'].includes(c.market)){
  const sr=intel()?.scoringRole(c.scoringRole,c.position,c.market);
  if(sr){
   facts.push(['Scoring role',sr.text+'.'+(sr.luckText?' '+sr.luckText:'')]);
   badges.push(...sr.badges);
   const yes=direction>0||c.market==='atd';
   if(sr.tier==='PRIMARY'&&yes){supports.unshift(`Primary scoring role: ${Math.round(sr.share*100)}% of his team's expected TDs, ${sr.xtd.toFixed(2)} expected TDs per game. Descriptive; earns no rating points.`);}
   else if(sr.tier==='FRINGE'&&yes)concerns.unshift(`Fringe scoring role: ${Math.round(sr.share*100)}% of his team's expected TDs; touchdowns come from a thin opportunity.`);
   if(sr.luck==='above'&&yes)concerns.push(sr.luckText);
  }
 }
 const opp=['Receiving','Rushing','TD'].includes(family)?opportunityProcess(c,o):null;
 if(opp?.usage){const text=situationText(opp.usage,family);if(text)facts.push([`Situational usage (${o.season} PBP, completed games)`,`${text}. ${opp.usage.games} games observed; counts exclude kneels, spikes and two-point tries.`]);}
 if(opp?.process){facts.push(['Opportunity vs production',opp.process.detail]);if(!opp.process.tdDriven||family==='TD')badges.push(opp.process.badge);}// a touchdown-luck badge only belongs on touchdown markets
 // Missed time: a player who has appeared in far fewer games than his team has played is probably coming back from an injury or a role change; the recent sample may not describe him.
 if(c.kind==='prop'&&row&&finite(row.games)&&finite(row.roster_week)&&row.roster_week-1-row.games>=2){
  const text=`Appeared in ${row.games} of his team's ${row.roster_week-1} games this season: recent form rests on a short or interrupted sample.`;
  facts.push(['Games played this season',text]);concerns.unshift(text);
 }
 if(c.kind==='prop'&&row&&['RB','WR','TE'].includes(String(row.position||c.position).toUpperCase())&&o.injuryLearning?.current_players){
  const mates=Object.values(o.injuryLearning.current_players).filter(m=>team(m.team)===team(c.team)&&m.position===row.position&&m.gsis_id!==row.gsis_id&&finite(m.depth_rank)&&finite(row.depth_rank)&&m.depth_rank<row.depth_rank&&String(m.roster_status).toUpperCase()==='ACT');
  const reports=o.injuryLearning.current_reports||{},hurt=mates.map(m=>({m,r:reports[team(m.team)+'|'+clean(m.name)]})).find(x=>x.r&&/did not|dnp|out|doubtful/i.test(`${x.r.practice_status||''} ${x.r.report_status||''}`));
  if(hurt){
   const listed=/out|doubtful/i.test(hurt.r.report_status||'');
   const text=`${hurt.m.name} (depth ${hurt.m.depth_rank}, same position) ${listed?'is listed '+hurt.r.report_status:'did not practice'} (${hurt.r.primary_injury||'injury'}): if he sits, this player's role grows.`;
   facts.push(['Teammate availability',text]);
   if(direction<0){add('teammate',-1,text);concerns.unshift(text);}
   else if(direction>0)supports.push(text);
  }
 }
 if(c.injury){badges.push(c.injury.roleBoost?'ROLE SCENARIO':'STATUS WATCH');concerns.unshift(c.injury.roleBoost?'Opportunity depends on a teammate absence; redistribution is a scenario, not confirmed usage.':`${c.injury.status||'Uncertain availability'} in the latest report${row?.week?' (week '+row.week+')':''}; confirm participation for this game.`);facts.push(['Existing injury treatment',c.injury.reason||'Availability may change opportunity.']);if(c.injury.stale||['questionable','limited','practice_dnp'].includes(c.injury.state))add('availability',-1,'Availability/participation is uncertain.');if(c.injury.roleBoost)facts.push(['Injury redistribution','Existing bounded role-transfer scenario; not observed with/without evidence and earns no injury points.']);}
 if(role?.games<4||c.kind==='game'&&o.currentGameEvidence&&Math.min(o.currentGameEvidence.homeGames,o.currentGameEvidence.awayGames)<4)concerns.push('Only a few current games; the role or matchup can change.');
 const points=components.reduce((s,x)=>s+x.points,0),tier=evidenceTier(points,components,c.market);
 const {rating,detail:ratingDetail}=granularRating(c,tier);
 const why=supports.slice(0,2).join(' ')||'A current model is attached; this direction needs stronger football evidence.';
 const concern=concerns[0]||(c.kind==='game'?'Game script, injuries and weather can move this line; compare the price with where the line closes.':unknown.some(x=>x.includes('matchup'))?'Opponent personnel and coverage may change the projected opportunity.':unknown[0])||'Football outcomes remain uncertain; verify availability and the line.';
 const key=c.canonicalContract||c.contract||contractKey(c);
 return {version:VERSION,eligible:true,key,gameKey:gameKey(c),family,points,rating,evidenceTier:tier,ratingDetail,components,badges:[...new Set(badges)].slice(0,4),facts,supports,concerns,unknown,why,concern,price,tdResearch:c.market==='atd',interesting:points>0,priceCaution:finite(c.ev)&&c.ev>.25?'The model and the sportsbook disagree unusually strongly on this price. Check the current role, exact market and line before relying on it; the football rating above does not use price.':(finite(c.prob)&&(c.prob>=.85||(c.prob<=.15&&finite(c.dec)&&c.dec>=4))?'The model puts this at an extreme probability. Estimates above 85% have not held up in recorded results (94% predicted won 72%), so treat any value estimate as overstated; the football rating above does not use price.':null)};
}
function board(rows,options){
 const now=(typeof options==='function'&&rows.length?options(rows[0])?.now:options?.now)??Date.now(),groups=new Map(),excluded=[];
 for(const c of rows){const e=assess(c,typeof options==='function'?options(c):options);if(!e.eligible){excluded.push({candidate:c,evidence:e});continue;}const key=familyKey(c);if(!groups.has(key))groups.set(key,[]);groups.get(key).push({candidate:c,evidence:e});}
 const picks=[];
 for(const pool of groups.values()){
  // Choose a standard line BEFORE rating. Alternate lines cannot inflate the board.
  const distance=x=>{const q=quote(x.candidate,now);return q.valid?Math.abs(x.candidate.dec-1.91):Infinity;};
  pool.sort((a,b)=>distance(a)-distance(b)||a.candidate.line-b.candidate.line||String(a.candidate.side).localeCompare(String(b.candidate.side)));
  const line=pool[0].candidate.line,atLine=pool.filter(x=>x.candidate.line===line);
  atLine.sort((a,b)=>b.evidence.points-a.evidence.points||String(a.candidate.side).localeCompare(String(b.candidate.side))||Date.parse(b.candidate.updatedAt)-Date.parse(a.candidate.updatedAt));
  const side=atLine[0].candidate.side,offers=atLine.filter(x=>x.candidate.side===side);
  offers.sort((a,b)=>Number(b.evidence.price.saveable)-Number(a.evidence.price.saveable)||Date.parse(b.candidate.updatedAt)-Date.parse(a.candidate.updatedAt)||(b.candidate.dec||0)-(a.candidate.dec||0)||String(a.candidate.book).localeCompare(String(b.candidate.book)));
  const chosen=offers[0];chosen.offers=offers.map(x=>({book:x.candidate.book,odds:x.candidate.odds,updatedAt:x.candidate.updatedAt}));chosen.alternatives=pool.length-offers.length;picks.push(chosen);
 }
 picks.sort((a,b)=>b.evidence.rating-a.evidence.rating||b.evidence.points-a.evidence.points||Date.parse(a.candidate.kickoff)-Date.parse(b.candidate.kickoff)||contractKey(a.candidate).localeCompare(contractKey(b.candidate)));
 return {version:VERSION,picks,excluded};
}
// Display-time grouping: cards that are the same football thesis (e.g. Over receiving yards and Over receptions for one player) show once, with the others listed as related.
// board() itself is unchanged (the tracked football-case-v2 cohort keeps recording every contract).
function collapseTheses(picks){
 const seen=new Map(),out=[];
 for(const row of picks){
  const key=intel()?.thesisKey(row.candidate);
  if(!key){out.push(row);continue;}
  const first=seen.get(key);
  if(first){(first.related=first.related||[]).push(row);continue;}
  seen.set(key,row);out.push(row);
 }
 return out;
}
function relatedLabel(r){const c=r.candidate;return c.kind==='prop'?`${c.side} ${c.line} ${({rec_yds:'receiving yards',receptions:'receptions',pass_yds:'passing yards',pass_tds:'passing TDs',rush_yds:'rushing yards',rush_tds:'rushing TDs',rec_tds:'receiving TDs',atd:'anytime TD'})[c.market]||c.market}`:`${c.market} ${c.side} ${c.line}`;}
const ageText=ms=>!Number.isFinite(ms)||ms<0?'age unknown':ms<3600000?Math.max(1,Math.round(ms/60000))+'m':ms<86400000?Math.round(ms/3600000)+'h':Math.round(ms/86400000)+'d';
function card(row,{label,key=row.evidence.key,rank=1,canSave=false,gameLabel=''}={}){
 const {candidate:c,evidence:e}=row,p=e.price,odds=c.odds>0?'+'+c.odds:String(c.odds),stamp=p.valid&&Number.isFinite(Date.parse(c.updatedAt))?new Date(c.updatedAt).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/New_York'})+' ET':'Time unavailable';
 return `<article class="picks-card" data-pick-key="${esc(key)}"><div class="picks-head"><span>#${rank} · ${esc(e.family)}${gameLabel?` · ${esc(gameLabel)}`:''}</span><span class="picks-rating">GOING <b>${e.rating}/100</b></span></div><h3>${esc(c.kind==='prop'?c.player:c.away+' @ '+c.home)}</h3><h4>${esc(label)}</h4><div class="picks-badges">${e.badges.map(x=>`<span>${esc(x)}</span>`).join('')}${e.tdResearch?'<span>TD ROLE RESEARCH</span>':''}${row.trivial?'<span title="The model puts this line above 90%: the price, not the football case, decides whether it is worth anything">NEAR-CERTAIN LINE</span>':''}</div><p class="picks-copy"><strong>WHY</strong>${esc(e.why)}</p><p class="picks-copy concern"><strong>CONCERN</strong>${esc(e.concern)}</p><div class="picks-market"><b>${p.valid?esc(c.book)+' '+esc(odds):'Price unavailable'}</b>${p.valid?`<small class="${p.fresh?'':'picks-stale'}">${p.fresh?'Recently observed':'PRICE NEEDS REFRESH · '+ageText(Date.now()-Date.parse(c.updatedAt))+' old'} · ${esc(stamp)}</small>`:'<small class="picks-stale">PRICE NEEDS REFRESH · no valid quote</small>'}${e.priceCaution?`<small class="picks-caution">${esc(e.priceCaution)}</small>`:''}</div>${row.related?.length?`<p class="picks-copy related"><strong>SAME THESIS</strong>${esc(row.related.map(relatedLabel).join(' · '))}</p>`:''}<details class="picks-detail" data-pick-detail="${esc(key)}"><summary>View research</summary><p>GOING ${e.rating}/100 is a heuristic football-case rating, not win chance or betting value. Model and current production overlap; unknown evidence earns zero points.</p><dl>${[...e.components.map(x=>[x.id,`${x.points>0?'+':''}${x.points}: ${x.detail}`]),['Rating detail',e.ratingDetail.strength===null?'Model spread unavailable; no within-tier refinement.':`Directional projection gap ${e.ratingDetail.gap.toFixed(2)} / model spread ${e.ratingDetail.sd.toFixed(2)}. Evidence tier ${e.evidenceTier} of 5; larger favorable gap refines within its 20-point band only.`],...e.facts,...e.unknown.map(x=>['Unknown',x]),...e.concerns.slice(1).map(x=>['Concern',x]),['Existing model estimate',`${(100*c.prob).toFixed(1)}% win / ${(100*(c.push||0)).toFixed(1)}% push; ${c.kind==='game'?'market-anchored: the trailing-points model showed no information beyond the posted line in a 10-season backtest, so this is the book price before vig, not a model edge':c.calibrated?(['atd','rec_tds','rush_tds'].includes(c.market)?'touchdown mean corrected about 20% lower (walk-forward validated); touchdown probabilities remain uncertain':'validated calibration applied (receptions / passing yards; holdout slope about 1.0)'):'raw model probability, not calibrated: overconfident in audits'}`],['Sources',`${VERSION}; model ${c.profileDate||'team snapshot'}; ${c.n} recorded games`],['Price/value','No demonstrated sportsbook-pricing edge. Check this exact line; stale prices do not erase the football case.']].map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>${row.offers?.length?`<p>Same-line offers: ${row.offers.map(x=>esc(x.book)+' '+esc(x.odds)).join(' · ')}</p>`:''}<p>Related player markets are correlated. ${row.alternatives||0} opposite/alternate/book observations remain in Markets.</p><a href="${c.profileId?'/players/?player='+encodeURIComponent(c.profileId):'/long/?mode=betting&tab=games'}">Full ${c.profileId?'player':'game'} research →</a></details><div class="picks-actions"><button type="button" data-picks-add="${esc(key)}" ${canSave&&p.saveable?'':'disabled'}>+ Compare / parlay</button></div></article>`;
}
root.GoingFootballPicks={collapse:collapseTheses,VERSION,OPPORTUNITY_RULE,opportunityProcess,FAMILIES,gameKey,familyKey,contractKey,quote,playerContext,evidenceTier,granularRating,assess,board,card};if(typeof module!=='undefined')module.exports=root.GoingFootballPicks;
})(globalThis);
