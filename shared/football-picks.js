/* GOING Picks v1: transparent research ordering, never probability or value.
 * The underlying models, GOING Score and frozen ranking policies are unchanged.
 */
(function(root){
'use strict';
const VERSION='football-case-v1';
const FAMILIES={rec_yds:'Receiving',receptions:'Receiving',rush_yds:'Rushing',pass_yds:'Passing',pass_tds:'Passing',rush_tds:'TD',rec_tds:'TD',atd:'TD',spread:'Game',total:'Game',moneyline:'Game'};
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const clean=x=>String(x??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const team=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[String(x||'').toUpperCase()]||String(x||'').toUpperCase();
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const etDate=x=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x));
const recent=(at,now,days=28)=>Number.isFinite(Date.parse(at))&&Date.parse(at)<=now&&now-Date.parse(at)<=days*86400000;
const avg=(rows,key)=>rows.length&&rows.every(r=>finite(r[key]))?rows.reduce((s,r)=>s+r[key],0)/rows.length:null;
function gameKey(c){return [c.sport,team(c.away),team(c.home),Number.isFinite(Date.parse(c.kickoff))?etDate(c.kickoff):'invalid'].join('|');}
function familyKey(c){return [gameKey(c),c.kind,c.profileId||'game',c.market].join('|');}
function contractKey(c){return [familyKey(c),c.side,c.line].join('|');}
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
function assess(c,options={}){
 const o={now:Date.now(),season:new Date().getUTCFullYear(),...options};
 const family=FAMILIES[c.market],price=quote(c,o.now),components=[],badges=[],facts=[],supports=[],concerns=[],unknown=[];
 const add=(id,points,detail)=>components.push({id,points,detail});
 const row=o.injuryLearning?.current_players?.[team(c.team)+'|'+clean(c.player)],status=String(row?.roster_status||'').toUpperCase();
 const invalid=!family||!['nfl','ncaa'].includes(c.sport)||!['game','prop'].includes(c.kind)||c.sport==='ncaa'&&c.kind==='prop'||!Number.isFinite(Date.parse(c.kickoff))||Date.parse(c.kickoff)<=o.now||c.manual||c.dfs||!finite(c.line)||!finite(c.prob)||c.prob<=0||c.prob>=1||!finite(c.n)||c.n<5||!recent(o.historyAt,o.now,1)||c.kind==='prop'&&(!c.profileId||!recent(c.profileDate,o.now))||c.injury?.blockRecommendation||['RES','INA','PUP','IR','SUS'].includes(status)||(c.flags||[]).some(f=>f.id==='check'&&!f.historicalOnly);
 const identityIssue=c.kind==='prop'&&(![team(c.home),team(c.away)].includes(team(c.team))||row?.gsis_id&&row.gsis_id!==c.profileId);
 if(invalid||identityIssue)return {version:VERSION,eligible:false,reason:identityIssue?'Player/team does not match this game':!family?'Market needs its own framework':c.injury?.blockRecommendation||['RES','INA','PUP','IR','SUS'].includes(status)?'Player is unavailable':'A matched pregame model/contract is unavailable',price};
 const direction=c.side==='Over'?1:c.side==='Under'?-1:c.side==='Home'?1:c.side==='Away'?-1:0;
 let modelSign=0;
 if(c.market==='spread')modelSign=Math.sign(direction*(c.modelMean+c.line));
 else if(c.market==='moneyline')modelSign=Math.sign(direction*c.modelMean);
 else if(c.market==='total')modelSign=Math.sign(direction*(c.modelMean-c.line));
 else if(c.market!=='atd'&&finite(c.projMean))modelSign=Math.sign(direction*(c.projMean-c.line));
 // ATD Yes lacks a comparable model-direction test. Any p>0 is not support.
 if(finite(modelSign)&&modelSign){add('model',2*modelSign,`Existing model ${modelSign>0?'favors':'opposes'} this exact direction${finite(c.projMean)?`: ${c.projMean.toFixed(1)} vs ${c.line}`:''}.`);if(modelSign>0){badges.push('MODEL +');supports.push(components.at(-1).detail);}else concerns.push(components.at(-1).detail);}
 else unknown.push(c.market==='atd'?'Any TD model direction is not graded.':'The model is neutral at this exact line.');
 const role=o.currentRoleEvidence,pc=playerContext(c,o);
 if(c.kind==='prop'){
  const production=role?.playerId===c.profileId&&team(role.team)===team(c.team)&&role.season===o.season&&recent(role.latest,o.now)?role.means?.[c.market]:null;
  if(c.market!=='atd'&&finite(production)&&direction){const sign=Math.sign(direction*(production-c.line));add('production',sign,`Current ${role.games}-game average ${production.toFixed(1)} ${sign>0?'agrees with':'does not favor'} ${c.side} ${c.line}.`);if(sign>0)supports.push(components.at(-1).detail);else if(sign<0)concerns.push(components.at(-1).detail);}
  else unknown.push('Comparable current production is unavailable.');
  const volume=family==='Receiving'?role?.means?.targets:family==='Rushing'?role?.means?.carries:family==='Passing'?role?.means?.attempts:null;
  if(finite(volume)&&volume>0){badges.push('VOLUME');facts.push(['Current opportunity',`${volume.toFixed(1)} ${family==='Receiving'?'targets':family==='Rushing'?'carries':'pass attempts'}/game (${role.games} observed games)`]);supports.push(facts.at(-1)[1]);}
  else if(pc)facts.push(['Observed offensive role',`${pc.player.games} games · ${finite(pc.player.target_share)?(100*pc.player.target_share).toFixed(1)+'% target share':'target share unknown'} · ${finite(pc.player.rush_share)?(100*pc.player.rush_share).toFixed(1)+'% rush share':'rush share unknown'}`]);
  else unknown.push('Current opportunity is unknown.');
  if(pc?.trend&&direction){const points=direction*pc.trend;add('usage',points,`${pc.volume==='targets'?'Targets':'Carries'} moved ${pc.before.toFixed(1)} → ${pc.after.toFixed(1)} per observed game (two chronological groups of ${Math.floor(pc.rows.length/2)}+).`);badges.push(pc.trend>0?'ROLE UP':'ROLE DOWN');(points>0?supports:concerns).unshift(components.at(-1).detail);concerns.push('Short usage trend; opportunity counts do not prove a lasting role change or an injury cause.');}
  else unknown.push('Role trend needs at least two observed games in each period.');
  if(pc){facts.push(['Current PBP role cutoff',pc.player.last_game],['Snap / route distinction',`${finite(pc.player.share)?(100*pc.player.share).toFixed(1)+'% '+pc.player.share_type:'Unknown snap share'}; measured routes ${pc.player.routes==null?'unavailable':pc.player.routes}`]);if(finite(pc.player.expected_catches)&&finite(pc.player.actual_catches)&&pc.player.catch_model_targets>0){facts.push(['Expected versus actual catches',`${pc.player.expected_catches.toFixed(1)} CP-summed expected / ${pc.player.actual_catches} actual on ${pc.player.catch_model_targets} modeled targets. Descriptive catch opportunity, not expected yards or a bounceback forecast.`]);}}
  if(c.market==='atd'&&role?.tdAppearances>0&&role.games>0){add('td_role',1,`Scored a rushing/receiving TD in ${role.tdAppearances}/${role.games} current appearances.`);supports.push(components.at(-1).detail);badges.push('TD ROLE');}
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
 if(c.injury){badges.push(c.injury.roleBoost?'ROLE SCENARIO':'STATUS WATCH');concerns.unshift(c.injury.roleBoost?'Opportunity depends on a teammate absence; redistribution is a scenario, not confirmed usage.':`${c.injury.status||'Uncertain availability'} in the latest report${row?.week?' (week '+row.week+')':''}; confirm participation for this game.`);facts.push(['Existing injury treatment',c.injury.reason||'Availability may change opportunity.']);if(c.injury.stale||['questionable','limited','practice_dnp'].includes(c.injury.state))add('availability',-1,'Availability/participation is uncertain.');if(c.injury.roleBoost)facts.push(['Injury redistribution','Existing bounded role-transfer scenario; not observed with/without evidence and earns no injury points.']);}
 if(role?.games<4||c.kind==='game'&&o.currentGameEvidence&&Math.min(o.currentGameEvidence.homeGames,o.currentGameEvidence.awayGames)<4)concerns.push('Only a few current games; the role or matchup can change.');
 const points=components.reduce((s,x)=>s+x.points,0),independent=components.filter(x=>x.points>0&&!['model','production'].includes(x.id)).length;
 let rating=Math.max(1,Math.min(5,points));if(!independent)rating=Math.min(rating,3);if(c.market==='atd')rating=Math.min(rating,2);
 const why=supports.slice(0,2).join(' ')||'A current model is attached; this direction needs stronger football evidence.';
 const concern=concerns[0]||(unknown.some(x=>x.includes('matchup'))?'Opponent personnel and coverage may change the projected opportunity.':unknown[0])||'Football outcomes remain uncertain; verify availability and the line.';
 const key=c.canonicalContract||c.contract||contractKey(c);
 return {version:VERSION,eligible:true,key,gameKey:gameKey(c),family,points,rating,components,badges:[...new Set(badges)].slice(0,4),facts,supports,concerns,unknown,why,concern,price,tdResearch:c.market==='atd',interesting:points>0};
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
function card(row,{label,key=row.evidence.key,rank=1,canSave=false}={}){
 const {candidate:c,evidence:e}=row,p=e.price,odds=c.odds>0?'+'+c.odds:String(c.odds),stamp=p.valid&&Number.isFinite(Date.parse(c.updatedAt))?new Date(c.updatedAt).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/New_York'})+' ET':'Time unavailable';
 return `<article class="picks-card" data-pick-key="${esc(key)}"><div class="picks-head"><span>#${rank} · ${esc(e.family)}</span><span class="picks-rating">GOING <b>${e.rating}/5</b></span></div><h3>${esc(c.kind==='prop'?c.player:c.away+' @ '+c.home)}</h3><h4>${esc(label)}</h4><div class="picks-badges">${e.badges.map(x=>`<span>${esc(x)}</span>`).join('')}${e.tdResearch?'<span>TD ROLE RESEARCH</span>':''}</div><p class="picks-copy"><strong>WHY</strong>${esc(e.why)}</p><p class="picks-copy concern"><strong>CONCERN</strong>${esc(e.concern)}</p><div class="picks-market"><b>${p.valid?esc(c.book)+' '+esc(odds):'Price unavailable'}</b><small>${p.fresh?'Recently observed':'PRICE NEEDS REFRESH'} · ${esc(stamp)}</small></div><details class="picks-detail" data-pick-detail="${esc(key)}"><summary>View research</summary><p>GOING ${e.rating}/5 is a heuristic football-case rating, not win chance or betting value. Model and current production overlap; unknown evidence earns zero points.</p><dl>${[...e.components.map(x=>[x.id,`${x.points>0?'+':''}${x.points}: ${x.detail}`]),...e.facts,...e.unknown.map(x=>['Unknown',x]),...e.concerns.slice(1).map(x=>['Concern',x]),['Existing model estimate',`${(100*c.prob).toFixed(1)}% win / ${(100*(c.push||0)).toFixed(1)}% push; calibration not established`],['Sources',`${VERSION}; model ${c.profileDate||'team snapshot'}; ${c.n} recorded games`],['Price/value','No demonstrated sportsbook-pricing edge. Check this exact line; stale prices do not erase the football case.']].map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>${row.offers?.length?`<p>Same-line offers: ${row.offers.map(x=>esc(x.book)+' '+esc(x.odds)).join(' · ')}</p>`:''}<p>Related player markets are correlated. ${row.alternatives||0} opposite/alternate/book observations remain in Markets.</p><a href="${c.profileId?'/players/?player='+encodeURIComponent(c.profileId):'/long/?mode=betting&tab=games'}">Full ${c.profileId?'player':'game'} research →</a></details><div class="picks-actions"><button type="button" data-picks-add="${esc(key)}" ${canSave&&p.saveable?'':'disabled'}>+ Compare / parlay</button></div></article>`;
}
root.GoingFootballPicks={VERSION,FAMILIES,gameKey,familyKey,contractKey,quote,playerContext,assess,board,card};if(typeof module!=='undefined')module.exports=root.GoingFootballPicks;
})(globalThis);
