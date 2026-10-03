(function(root){
'use strict';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=Number.isFinite, pct=x=>finite(x)?(100*x).toFixed(1)+'%':'Unavailable';
const seasonOf=at=>{const d=new Date(at);return d.getUTCFullYear()-(d.getUTCMonth()<6?1:0);};
function recent(at,now,limit){const t=Date.parse(at);return finite(t)&&t<=now&&now-t<=limit;}
function assess(c,{now=Date.now(),season,contextAt,learningAt,historyAt,matchup,weakness}={}){
 const supports=[],concerns=[],checks=[],facts=[];
 const add=(label,value)=>{if(value!==undefined&&value!==null&&value!=='')facts.push([label,String(value)]);};
 const quoteAt=Date.parse(c.updatedAt),age=now-quoteAt,fresh=finite(age)&&age>=0&&age<=300000;
 const eligible=['nfl','ncaa'].includes(c.sport)&&['game','prop'].includes(c.kind)&&!(c.sport==='ncaa'&&c.kind==='prop')&&finite(c.prob)&&c.prob>0&&c.prob<1&&finite(c.dec)&&c.dec>1&&finite(c.odds)&&Math.abs(c.odds)>=100&&finite(c.push??0)&&(c.push??0)>=0&&c.prob+(c.push??0)<=1+1e-12&&c.n>=5&&Date.parse(c.kickoff)>now&&!c.manual&&!c.dfs;
 const blocking=(c.flags||[]).some(f=>f.id==='check'&&!f.historicalOnly);
 if(!fresh){const note=!finite(age)||age<0?'Price timestamp is missing or in the future.':`Saved price is ${Math.floor(age/3600000)}h ${Math.floor(age%3600000/60000)}m old.`;checks.push(note+' Check the exact line and odds at your book.');}
 if(!recent(historyAt,now,86400000))checks.push('Model snapshot is missing, future-dated or over 24 hours old.');
 if(c.kind==='prop'&&!recent(c.profileDate,now,28*86400000))checks.push('Player observation cutoff is missing, future-dated or over 28 days old.');
 if(blocking)checks.push('An unresolved model check blocks this estimate.');
 if(c.injury?.stale||c.injury?.blockRecommendation)checks.push('Availability evidence is stale or participation is unresolved.');
 else if(c.injury)concerns.push('Availability or replacement-role scenario may change the actual workload.');
 const s=c.seasonEvidence,g=c.gameSeasonEvidence;
 const currentSeason=season===seasonOf(now)&&(!s||s.season===season);
 let current=false;
 if(c.kind==='prop'&&s&&finite(s.current_games)&&finite(s.historical_games)){
  current=currentSeason&&s.current_games>0;
  supports.push(`${s.current_games} ${s.season} player games / ${s.historical_games} older games inform the projection.`);
  if(s.sample_confidence==='low')concerns.push('The model marks the current-season player sample as limited.');
  if(s.historical_games>0)concerns.push('The current/older weighting is a policy choice, not a validated accuracy improvement.');
  add('Projection season',s.season);add('Current / older player games',`${s.current_games} / ${s.historical_games}`);add('Current-season model weight',pct(s.current_weight));add('Weighting method',s.method);
 }else if(c.kind==='game'&&g&&finite(g.home_current_games)&&finite(g.away_current_games)){
  current=currentSeason&&g.home_current_games>0&&g.away_current_games>0;
  supports.push(`${c.away}: ${g.away_current_games} current-season games; ${c.home}: ${g.home_current_games}.`);
  concerns.push(`Current-season samples are ${g.away_current_games} / ${g.home_current_games} games; the weighting has not demonstrated improved betting accuracy.`);
  add('Away / home current games',`${g.away_current_games} / ${g.home_current_games}`);add('Away / home current weights',`${pct(g.away_current_weight)} / ${pct(g.home_current_weight)}`);add('Weighting method',g.policy);
 }else concerns.push('Current-season sample counts are unavailable; older history must not be assumed current.');
 if(!current)concerns.push('Current-season identity or coverage is missing for this exact estimate.');
 const r=c.evidence?.opportunity;
 const role=(c.flags||[]).find(f=>f.id==='opportunity'&&f.family==='role');
 const roleSupported=c.kind==='prop'&&c.sport==='nfl'&&c.side==='Over'&&['rec_yds','receptions'].includes(c.market)&&role&&r?.season===season&&finite(r.adjustedShare)&&finite(r.average)&&r.adjustedShare>r.average&&recent(r.last_game,now,28*86400000)&&seasonOf(r.last_game)===season&&recent(contextAt,now,86400000);
 if(roleSupported)supports.unshift(`Current recorded pass-snap role: ${pct(r.adjustedShare)} adjusted share versus ${pct(r.average)} for comparable positions. This is role support, not a promise of production.`);
 const direction=c.side==='Over'?1:c.side==='Under'?-1:0;
 const matchedRole=c.market==='rec_yds'?/RECEIVING$/.test(matchup?.role||''):c.market==='rush_yds'?/RUSHING$/.test(matchup?.role||''):false;
 const matchedIdentity=matchup?.player_id===c.profileId&&matchup?.opponent===(c.team===c.home?c.away:c.home)&&matchup?.weakness_id===weakness?.id&&Math.abs(Date.parse(matchup?.kickoff)-Date.parse(c.kickoff))<60000;
 const matchSupported=matchedRole&&matchedIdentity&&c.kind==='prop'&&c.sport==='nfl'&&['rec_yds','rush_yds'].includes(c.market)&&matchup?.active_signal===true&&weakness?.current?.season===season&&weakness.current.sample>0&&finite(weakness.current.value)&&direction*weakness.current.value>0&&Array.isArray(matchup.lineage)&&matchup.lineage.length>0&&Array.isArray(weakness.lineage)&&weakness.lineage.length>0&&recent(learningAt,now,86400000)&&current;
 if(matchSupported)supports.unshift(`Current role-matched defensive residual: ${weakness.current.value>=0?'+':''}${weakness.current.value.toFixed(2)} yards per opportunity (${weakness.current.sample} opportunities). It supports this direction; it does not establish an edge.`);
 if(!roleSupported&&!matchSupported)concerns.push(c.sport==='ncaa'?'No verified current-season matchup or personnel signal is attached; this is a scoring-model comparison.':'No verified current-season, direction-relevant role or matchup signal is attached.');
 if(c.evidence?.chartingAt&&(!recent(c.evidence.chartingAt,now,28*86400000)||seasonOf(c.evidence.chartingAt)!==season))concerns.push('Charted participation is historical; the latest game date does not make it current.');
 if(finite(c.ev)&&c.ev<=0)concerns.push('At this recorded price, the model estimates a non-positive return. High likelihood is not attractive value by itself.');
 if(c.odds< -300)concerns.push('Short price: a loss costs more than the profit from one win. Compare likelihood with the required price.');
 if(!supports.length)supports.push(`${c.n??'Unknown'} recorded games inform the existing ${c.modelFamily||'scoring'} model; additional football support is unconfirmed.`);
 concerns.push('Prediction calibration and profitable betting value are not established.');
 const group=!eligible||blocking||checks.length?'check':current&&(roleSupported||matchSupported)&&s?.sample_confidence!=='low'&&!c.injury?'support':'developing';
 const label={support:'Current support attached',developing:'Developing evidence',check:'Check first'}[group];
 add('Recorded model games',c.n);add('Model observation cutoff',c.profileDate);add('Model snapshot',historyAt);add('Context snapshot',contextAt);add('Matchup snapshot',learningAt);add('Price observed',c.updatedAt);add('Estimated win chance',pct(c.prob));add('Book break-even, ignoring returned stake',pct(1/c.dec));add('Estimated push chance',pct(c.push));add('Push-aware model return',finite(c.ev)?`${(100*c.ev).toFixed(1)} cents per $1`:'Unavailable');
 return {group,label,eligible,supports,concerns,checks,facts,why:supports[0],concern:checks[0]||concerns[0],fresh,quoteAge:age,footballSupport:!!(roleSupported||matchSupported)};
}
function groups(rows,options){const out={support:[],developing:[],check:[]};for(const c of rows){const e=assess(c,typeof options==='function'?options(c):options);if(e.eligible)out[e.group].push({candidate:c,evidence:e});}return out;}
function card(c,e,{label,key,teamLabel,gameKey,extra=[],saved=false,canSave=true}={}){
 const odds=c.odds>0?'+'+c.odds:String(c.odds),stamp=new Date(c.kickoff).toLocaleString('en-US',{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/New_York'});
 return `<article class="confidence-card" data-confidence-key="${esc(key)}"><div class="confidence-label ${esc(e.group)}">${esc(e.label)}</div><h4>${esc(c.kind==='prop'?c.player+' · ':'')}${esc(label)}</h4><p class="confidence-game">${esc(teamLabel(c.away,c.sport))} @ ${esc(teamLabel(c.home,c.sport))} · ${esc(stamp)} ET</p><p><strong>Why investigate</strong>${esc(e.why)}</p><p class="confidence-concern"><strong>Biggest concern</strong>${esc(e.concern)}</p><div class="confidence-price"><div><small>Estimated likelihood</small><b>${esc(pct(c.prob))}</b><small>Model estimate · not Confidence</small></div><div><small>Recorded price</small><b>${esc(c.book)} ${esc(odds)}</b><small>${esc(pct(1/c.dec))} win-only break-even${c.push>0?' · pushes return stake':''}</small></div></div><p class="confidence-value">${finite(c.ev)?`Push-aware model return: ${c.ev>=0?'+':''}${(100*c.ev).toFixed(1)}¢ per $1. `:''}Estimated return is not proven value. ${e.fresh?'Quote observed within five minutes; verify at your book.':'Saved price; do not assume it is still available.'}</p><details data-confidence-detail="${esc(key)}"><summary>Evidence &amp; what needs checking</summary><ul>${[...e.supports.slice(1),...e.checks,...e.concerns].map(s=>`<li>${esc(s)}</li>`).join('')}</ul><dl>${[...e.facts,...extra].map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl><p>These are overlapping observations, not independent confirmations. GOING Score is a player index and is not used here.</p></details><div class="confidence-actions"><button type="button" data-confidence-add="${esc(key)}" aria-pressed="${saved}" ${canSave?'':'disabled title="Saving is unavailable; research this game instead"'}>${saved?'✓ Shortlisted':'+ Compare / parlay'}</button><button type="button" data-slate-action="games" data-slate-game="${esc(gameKey)}">Research this game</button></div></article>`;
}
root.GoingFootballConfidence={assess,groups,card};if(typeof module!=='undefined')module.exports=root.GoingFootballConfidence;
})(globalThis);
