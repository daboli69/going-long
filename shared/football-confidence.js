(function(root){
'use strict';
const VERSION='football-readiness-v2';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=Number.isFinite, pct=x=>finite(x)?(100*x).toFixed(1)+'%':'Unavailable';
const seasonOf=at=>{const d=new Date(at);return d.getUTCFullYear()-(d.getUTCMonth()<6?1:0);};
const team=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'})[x]||x;
function recent(at,now,limit){const t=Date.parse(at);return finite(t)&&t<=now&&now-t<=limit;}
const mean=(rows,key)=>rows.length&&rows.every(r=>finite(r[key]))?rows.reduce((n,r)=>n+r[key],0)/rows.length:null;
function resultsIssue(results,sport,now=Date.now()){
 if(!results||results.sources?.[sport]?.status!=='loaded')return 'The current finals feed is unavailable; retained results may omit recent games.';
 if(!recent(results.generated_at,now,86400000)||!recent(results.sources[sport].checked_at,now,86400000))return 'Final-results source confirmation is missing, stale or future-dated.';
 return '';
}
function currentPlayerEvidence(profile,c,{now=Date.now(),season=seasonOf(now)}={}){
 if(!profile||profile.id!==c.profileId||team(profile.team)!==team(c.team))return null;
 const rows=(profile.games||[]).filter(g=>g.season===season&&Date.parse(g.date)<now&&seasonOf(g.date)===season);
 const relevant=profile.position==='QB'?rows.filter(g=>g.verified_start===true):rows;
 const latest=relevant.map(g=>g.date).sort().at(-1);
 return {playerId:profile.id,team:profile.team,season,position:profile.position,games:relevant.length,latest,
  verifiedStarts:rows.filter(g=>g.verified_start===true).length,
  means:Object.fromEntries(['attempts','carries','targets','pass_yds','rush_yds','rec_yds','receptions','pass_tds','rush_tds','rec_tds','atd'].map(k=>[k,mean(relevant,k)])),
  tdAppearances:relevant.length&&relevant.every(g=>finite(g.rush_tds)&&finite(g.rec_tds))?relevant.filter(g=>g.rush_tds+g.rec_tds>0).length:null,
  source:'Published history.json player appearance rows; current season only; QB verified starts only'};
}
function currentGameEvidence(games,c,{now=Date.now(),season=seasonOf(now),source='Published completed current-season team scores',resultsAt,sourceStatus,sourceCheckedAt}={}){
 if(resultsAt&&(!recent(resultsAt,now,86400000)||sourceStatus!=='loaded'||!recent(sourceCheckedAt,now,86400000)))return null;
 const observations=t=>(games||[]).filter(g=>g.season===season&&g.sport===c.sport&&Date.parse(g.kickoff)<now&&g.completed===true&&finite(g.homeScore)&&finite(g.awayScore)&&[team(g.home),team(g.away)].includes(team(t))).map(g=>({date:g.kickoff,scored:team(g.home)===team(t)?g.homeScore:g.awayScore,allowed:team(g.home)===team(t)?g.awayScore:g.homeScore}));
 const home=observations(c.home),away=observations(c.away);
 if(!home.length||!away.length)return null;
 const h=(mean(home,'scored')+mean(away,'allowed'))/2,a=(mean(away,'scored')+mean(home,'allowed'))/2;
 return {season,sport:c.sport,home:c.home,away:c.away,homeGames:home.length,awayGames:away.length,latest:[...home,...away].map(g=>g.date).sort().at(-1),homeScored:mean(home,'scored'),awayScored:mean(away,'scored'),homeAllowed:mean(home,'allowed'),awayAllowed:mean(away,'allowed'),totalContext:h+a,marginContext:h-a,source:source+'; symmetric scoring context, not a new forecast'};
}
function assess(c,{now=Date.now(),season=seasonOf(now),contextAt,learningAt,historyAt,matchup,weakness,currentRoleEvidence,currentGameEvidence:gameContext,gameEvidenceIssue}={}){
 const supports=[],concerns=[],footballChecks=[],priceChecks=[],facts=[],dimensions=[];
 const add=(label,value)=>{if(value!==undefined&&value!==null&&value!=='')facts.push([label,String(value)]);};
 const check=(code,label,detail)=>{if(!footballChecks.some(x=>x.code===code))footballChecks.push({code,label,detail});};
 const quoteAt=Date.parse(c.updatedAt),age=now-quoteAt,expectedDecimal=c.odds>0?1+c.odds/100:1+100/Math.abs(c.odds),validPrice=finite(c.dec)&&c.dec>1&&finite(c.odds)&&Math.abs(c.odds)>=100&&Math.abs(c.dec-expectedDecimal)<=.005&&typeof c.book==='string'&&!!c.book.trim(),fresh=validPrice&&finite(age)&&age>=0&&age<=300000;
 const eligible=['nfl','ncaa'].includes(c.sport)&&['game','prop'].includes(c.kind)&&!(c.sport==='ncaa'&&c.kind==='prop')&&finite(c.prob)&&c.prob>0&&c.prob<1&&finite(c.push??0)&&(c.push??0)>=0&&c.prob+(c.push??0)<=1+1e-12&&finite(c.n)&&c.n>=5&&Date.parse(c.kickoff)>now&&!c.manual&&!c.dfs;
 if(!fresh)priceChecks.push({code:'price',label:'Check price',detail:!validPrice?'No valid matching sportsbook price is attached.':!finite(age)||age<0?'Price timestamp is missing or future-dated.':`Saved price is ${Math.floor(age/3600000)}h ${Math.floor(age%3600000/60000)}m old. Confirm this exact line and odds at your book.`});
 if(!recent(historyAt,now,86400000))check('model_freshness','Check model freshness','The model snapshot is missing, future-dated or over 24 hours old.');
 if(c.kind==='prop'&&!recent(c.profileDate,now,28*86400000))check('observation','Check player data','The player observation cutoff is missing, future-dated or over 28 days old.');
 if((c.flags||[]).some(f=>f.id==='check'&&!f.historicalOnly))check('model','Check model','An unresolved model audit flag needs review; it is not independent football confirmation.');
 if(c.injury?.stale||c.injury?.blockRecommendation)check('availability','Check player status','Availability evidence is stale or participation is unresolved.');
 const availabilityConcern=!!c.injury&&!c.injury.stale&&!c.injury.blockRecommendation;
 if(availabilityConcern)concerns.push(c.injury.reason||'Availability or a replacement-role scenario may change workload.');
 const s=c.seasonEvidence,g=c.gameSeasonEvidence;
 const seasonMatches=season===seasonOf(now)&&(!s||s.season===season);
 let current=c.kind==='prop'?seasonMatches&&s?.current_games>0:seasonMatches&&g?.home_current_games>0&&g?.away_current_games>0;
 if(c.kind==='prop'&&s){add('Current / older player games',`${s.current_games??'unknown'} / ${s.historical_games??'unknown'}`);add('Projection season',s.season);add('Current-season model weight',pct(s.current_weight));add('Weighting policy',s.method);}
 if(c.kind==='game'&&g){add('Away / home current model games',`${g.away_current_games} / ${g.home_current_games}`);add('Away / home current weights',`${pct(g.away_current_weight)} / ${pct(g.home_current_weight)}`);add('Weighting policy',g.policy);}
 if(!current)check('current_sample','Check current-season data','Current-season identity or sample coverage is missing for this exact estimate.');
 if(s?.sample_confidence==='low'||c.kind==='game')concerns.push('Small current-season sample; recent production may not describe the next game.');
 if(s?.historical_games>0||g)concerns.push('Current/older model weighting is an unvalidated policy; the current observations below are kept separate.');
 const direction=c.side==='Over'?1:c.side==='Under'?-1:0;
 const role=currentRoleEvidence;
 const roleValid=c.kind==='prop'&&role?.playerId===c.profileId&&team(role.team)===team(c.team)&&role.season===season&&role.games>0&&recent(role.latest,now,28*86400000);
 const families={rec_yds:'receiving',receptions:'receiving',rush_yds:'rushing',pass_yds:'passing',pass_tds:'passing',rush_tds:'touchdown',rec_tds:'touchdown',atd:'touchdown'};
 const family=c.kind==='game'?(['total','spread','moneyline'].includes(c.market)?'game':'unsupported'):families[c.market]||'unsupported';
 let currentDirection=false,modelDirection=c.prob>1-c.prob-(c.push||0),opportunity=false;
 if(roleValid){
  const volume=family==='receiving'?role.means.targets:family==='rushing'?role.means.carries:family==='passing'?role.means.attempts:finite(role.means.targets)&&finite(role.means.carries)?role.means.targets+role.means.carries:null;
  opportunity=finite(volume)&&volume>0&&(family!=='passing'||role.verifiedStarts>0);
  const production=role.means[c.market];
  if(direction&&finite(c.line)&&finite(production)){currentDirection=direction*(production-c.line)>0;modelDirection=finite(c.projMean)?direction*(c.projMean-c.line)>0:c.prob>1-c.prob-(c.push||0);}
  else if(c.market==='atd'&&['Yes','Over'].includes(c.side)){currentDirection=finite(role.tdAppearances)&&role.tdAppearances>0;modelDirection=c.prob>0;}
  add('Current appearance source',role.source);add('Current-only observed appearances',role.games);add('Current appearance cutoff',role.latest);add('Current-only attempts / carries / targets',`${role.means.attempts??'missing'} / ${role.means.carries??'missing'} / ${role.means.targets??'missing'}`);add('Current-only market average',production);add('Current TD appearances',role.tdAppearances);
  if(opportunity){dimensions.push('current_role');supports.push(`${role.games} current-season ${role.position==='QB'?'verified starts':'appearances'} show ${volume.toFixed(1)} ${family==='receiving'?'targets':family==='rushing'?'carries':family==='passing'?'pass attempts':'carries + targets'} per game.`);}
  if(currentDirection){const names={rec_yds:'receiving yards',receptions:'receptions',rush_yds:'rushing yards',pass_yds:'passing yards',pass_tds:'passing TDs',rush_tds:'rushing TDs',rec_tds:'receiving TDs'};dimensions.push('current_production');supports.unshift(c.market==='atd'?`Rushing/receiving TDs were recorded in ${role.tdAppearances} of ${role.games} current appearances, with current offensive opportunity.`:`Current-season ${names[c.market]||c.market} average ${production.toFixed(1)} is ${direction>0?'above':'below'} this ${c.line} line.`);}
  else if(opportunity)concerns.unshift('The current-only production does not support this exact direction; the weighted model and current sample need comparing.');
 }else if(c.kind==='prop')concerns.push('Exact-player current-season opportunity data is missing; older role/charting is not substituted.');
 const r=c.evidence?.opportunity;
 const roleSignal=c.kind==='prop'&&c.sport==='nfl'&&c.side==='Over'&&['rec_yds','receptions'].includes(c.market)&&r?.season===season&&finite(r.adjustedShare)&&finite(r.average)&&r.adjustedShare>r.average&&recent(r.last_game,now,28*86400000)&&seasonOf(r.last_game)===season&&recent(contextAt,now,86400000);
 if(roleSignal){dimensions.push('current_role_signal');supports.unshift(`Current recorded pass-snap role: ${pct(r.adjustedShare)} adjusted share versus ${pct(r.average)} for comparable positions.`);}
 const matchedRole=c.market==='rec_yds'?/RECEIVING$/.test(matchup?.role||''):c.market==='rush_yds'?/RUSHING$/.test(matchup?.role||''):false;
 const matchedIdentity=matchup?.player_id===c.profileId&&matchup?.opponent===(team(c.team)===team(c.home)?c.away:c.home)&&matchup?.weakness_id===weakness?.id&&Math.abs(Date.parse(matchup?.kickoff)-Date.parse(c.kickoff))<60000;
 const matchSupported=matchedRole&&matchedIdentity&&c.kind==='prop'&&c.sport==='nfl'&&matchup?.active_signal===true&&weakness?.current?.season===season&&weakness.current.sample>0&&finite(weakness.current.value)&&direction*weakness.current.value>0&&Array.isArray(matchup.lineage)&&matchup.lineage.length>0&&Array.isArray(weakness.lineage)&&weakness.lineage.length>0&&recent(learningAt,now,86400000)&&current;
 if(matchSupported){dimensions.push('current_matchup');supports.unshift(`Current role-matched defensive residual ${weakness.current.value>=0?'+':''}${weakness.current.value.toFixed(2)} yards per opportunity (${weakness.current.sample} opportunities) supports this direction.`);}
 const gameValid=c.kind==='game'&&gameContext?.season===season&&gameContext.sport===c.sport&&gameContext.home===c.home&&gameContext.away===c.away&&gameContext.homeGames>0&&gameContext.awayGames>0&&recent(gameContext.latest,now,28*86400000);
 if(gameValid){
  const context=c.market==='total'?gameContext.totalContext:gameContext.marginContext;
  currentDirection=finite(context)&&finite(c.line)&&(c.market==='total'?direction*(context-c.line)>0:c.market==='spread'?(c.side==='Home'?1:c.side==='Away'?-1:0)*(context+c.line)>0:c.market==='moneyline'?(c.side==='Home'?1:c.side==='Away'?-1:0)*context>0:false);
  modelDirection=c.prob>1-c.prob-(c.push||0);
  opportunity=true;dimensions.push('current_team_samples');
  supports.push(`${c.away}: ${gameContext.awayGames} current finals, ${gameContext.awayScored.toFixed(1)} scored / ${gameContext.awayAllowed.toFixed(1)} allowed; ${c.home}: ${gameContext.homeGames}, ${gameContext.homeScored.toFixed(1)} / ${gameContext.homeAllowed.toFixed(1)}.`);
  if(currentDirection){dimensions.push('current_scoring_direction');supports.unshift(`Current-only scoring context ${context.toFixed(1)} ${c.market==='total'?'total points':'home margin'} supports ${c.side}${c.market==='spread'?' against the recorded spread':''}.`);}
  else concerns.unshift('Current-only team scoring context does not support this exact direction.');
  add('Current team evidence source',gameContext.source);add('Current team evidence cutoff',gameContext.latest);add('Current-only scoring context',context);
 }else if(c.kind==='game')concerns.unshift(gameEvidenceIssue||'Completed current-season team score rows for both teams are missing; no NFL player-role requirement applies.');
 if(family==='unsupported'){check('market','Check market coverage','This market needs a separate evidence definition; current support is not claimed.');supports.unshift('An existing estimate is attached, but this market needs its own current football evidence definition.');footballChecks.sort((a,b)=>(a.code==='market'?-1:0)-(b.code==='market'?-1:0));}
 if((opportunity&&currentDirection||roleSignal||matchSupported)&&!modelDirection)concerns.unshift('The existing model does not favor this exact direction despite the current observations.');
 if(!matchSupported&&c.kind==='prop')concerns.push('No verified direction-matched current defensive signal is attached; matchup and personnel remain limitations.');
 if(gameValid)concerns.push('Raw team scoring context is descriptive, not opponent/personnel-adjusted or an independently validated forecast.');
 if(c.evidence?.chartingAt&&(!recent(c.evidence.chartingAt,now,28*86400000)||seasonOf(c.evidence.chartingAt)!==season))concerns.push('Charted participation is historical and is not presented as current role evidence.');
 const footballSupport=current&&modelDirection&&(roleSignal||matchSupported||opportunity&&currentDirection);
 if(!supports.length)supports.push(`${c.n??'Unknown'} recorded games support the existing model; current football observations need checking.`);
 if(footballSupport&&modelDirection)dimensions.push('existing_model_direction');
 if(validPrice&&finite(c.ev)&&c.ev<=0)priceChecks.push({code:'value',label:'No positive model value',detail:'The model estimates a non-positive return at this saved price. Football support is separate from betting value.'});
 if(c.odds< -300)concerns.push('Short price: one loss costs more than the profit from one win.');
 concerns.push('Predictive calibration and profitable betting value are not established.');
 const group=!eligible||footballChecks.length?'check':footballSupport&&!availabilityConcern?'support':'developing';
 const label={support:'Current support',developing:'Developing',check:'Check first'}[group];
 add('Recorded model games',c.n);add('Model observation cutoff',c.profileDate);add('Model snapshot',historyAt);add('Context snapshot',contextAt);add('Matchup snapshot',learningAt);add('Price observed',c.updatedAt);add('Estimated win chance',pct(c.prob));add('Win-only book break-even',validPrice?pct(1/c.dec):'Unavailable');add('Estimated push chance',pct(c.push));
 const checks=[...footballChecks,...priceChecks].map(x=>x.detail);
 return {version:VERSION,group,label,eligible,supports,concerns,footballChecks,priceChecks,checks,reasonCodes:footballChecks.map(x=>x.code),dimensions:[...new Set(dimensions)],facts,why:supports[0],concern:footballChecks[0]?.detail||concerns[0],fresh,validPrice,quoteAge:age,footballSupport:!!footballSupport,currentGames:roleValid?role.games:gameValid?Math.min(gameContext.homeGames,gameContext.awayGames):0};
}
function groups(rows,options){
 const out={support:[],developing:[],check:[]};
 for(const c of rows){const e=assess(c,typeof options==='function'?options(c):options);if(e.eligible)out[e.group].push({candidate:c,evidence:e});}
 // A transparent descriptive order, not a learned score or betting-value ranking.
 const cutoff=e=>Date.parse(e.facts.find(([k])=>k==='Current appearance cutoff'||k==='Current team evidence cutoff')?.[1])||0;
 for(const list of Object.values(out))list.sort((a,b)=>b.evidence.currentGames-a.evidence.currentGames||cutoff(b.evidence)-cutoff(a.evidence)||Date.parse(a.candidate.kickoff)-Date.parse(b.candidate.kickoff));
 return out;
}
function card(c,e,{label,key,teamLabel,gameKey,extra=[],saved=false,canSave=true}={}){
 const odds=e.validPrice?(c.odds>0?'+'+c.odds:String(c.odds)):'Unavailable',stamp=new Date(c.kickoff).toLocaleString('en-US',{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/New_York'});
 const priceReady=e.validPrice&&finite(e.quoteAge)&&e.quoteAge>=0&&e.quoteAge<=86400000;
 const priceLabel=e.fresh?'Recently observed price':'Check price';
 return `<article class="confidence-card" data-confidence-key="${esc(key)}"><div class="confidence-label ${esc(e.group)}">${esc(e.label)}${e.footballChecks.length?' · '+esc(e.footballChecks[0].label):''}</div><h4>${esc(c.kind==='prop'&&!String(label).startsWith(c.player)?c.player+' · ':'')}${esc(label)}</h4><p class="confidence-game">${esc(teamLabel(c.away,c.sport))} @ ${esc(teamLabel(c.home,c.sport))} · ${esc(stamp)} ET</p><p><strong>Why GOING is interested</strong>${esc(e.why)}</p><p class="confidence-concern"><strong>Biggest concern</strong>${esc(e.concern)}</p><div class="confidence-price"><div><small>Estimated likelihood</small><b>${esc(pct(c.prob))}</b><small>Model estimate · not Confidence</small></div><div><small>${esc(priceLabel)}</small><b>${e.validPrice?esc(c.book)+' '+esc(odds):'No matched price'}</b><small>${e.validPrice?esc(pct(1/c.dec))+' win-only break-even':'Football evidence is separate'}</small></div></div><p class="confidence-value">${e.fresh?'Verify the line at your book.':esc(e.priceChecks.find(x=>x.code==='price')?.detail||'Saved price; verify the exact line and payout.')} ${e.priceChecks.some(x=>x.code==='value')?'No positive model value at this saved price.':''}</p><details data-confidence-detail="${esc(key)}"><summary>View evidence &amp; checks</summary><ul>${[...e.supports.slice(1),...e.checks,...e.concerns].map(s=>`<li>${esc(s)}</li>`).join('')}</ul><dl>${[...e.facts,...extra].map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl><p>${e.validPrice&&finite(c.ev)?`Push-aware model return ${(100*c.ev).toFixed(1)}¢ per $1 at the recorded price. `:''}This is not proven value. Observations overlap; GOING Score is not used.</p></details><div class="confidence-actions"><button type="button" data-confidence-add="${esc(key)}" aria-pressed="${saved}" ${canSave&&priceReady?'':'disabled title="A matched price within 24 hours is required for saving"'}>${saved?'✓ Shortlisted':'+ Compare / parlay'}</button><button type="button" data-slate-action="games" data-slate-game="${esc(gameKey)}">Research this game</button></div></article>`;
}
root.GoingFootballConfidence={VERSION,assess,groups,card,currentPlayerEvidence,currentGameEvidence,resultsIssue};if(typeof module!=='undefined')module.exports=root.GoingFootballConfidence;
})(globalThis);
