/* NFL Intelligence: read-only view of the NFL Ensemble Lab feed (schema going-nfl-lab-feed 1.x).
   Complements GOING's own predictions; it never replaces them. Every value comes from the published feed. */
(function(root){
 'use strict';
 const STALE_DEFAULT_H=36;
 const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const pct=p=>p==null?'—':(100*p).toFixed(0)+'%';
 const pct1=p=>p==null?'—':(100*p).toFixed(1)+'%';
 const num=(x,d=1)=>x==null?'—':(x>0?'+':'')+Number(x).toFixed(d);
 const when=t=>{if(!t)return '—';const d=new Date(t);return isNaN(d)?'—':d.toLocaleString([], {weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});};
 const ageH=(t,now)=>t?(now-Date.parse(t))/3.6e6:Infinity;
 // compare player names ignoring suffixes and punctuation ("Michael Penix Jr." == "Michael Penix")
 const normName=n=>String(n||'').toLowerCase().replace(/[.'-]/g,' ').split(/\s+/).filter(w=>w&&!['jr','sr','ii','iii','iv','v'].includes(w)).join(' ');

 function validate(feed){
  const errs=[];
  if(!feed||feed.schema!=='going-nfl-lab-feed')errs.push('schema');
  if(!/^1\./.test(String(feed&&feed.schema_version||'')))errs.push('schema_version');
  if(!Array.isArray(feed&&feed.games))errs.push('games');
  (feed&&feed.games||[]).forEach((g,i)=>{
   const p=g&&g.forecast&&g.forecast.champion&&g.forecast.champion.p_home;
   if(p!=null&&(p<0||p>1))errs.push('games['+i+'].p_home');
   if(g&&g.forecast&&g.forecast.archived_at&&Date.parse(g.forecast.archived_at)>=Date.parse(g.kickoff_utc))errs.push('games['+i+'] archived after kickoff');
  });
  return errs;
 }

 function freshness(feed,now){
  const lim=(feed.freshness&&feed.freshness.stale_after_hours)||STALE_DEFAULT_H;
  const h=ageH(feed.generated_at,now);
  return {hours:h,stale:h>lim,limit:lim};
 }

 function bar(p,home,away){
  if(p==null)return '<div class="nli-bar nli-empty">No probability</div>';
  const h=Math.round(100*p);
  return `<div class="nli-bar" role="img" aria-label="${esc(home)} ${h}% , ${esc(away)} ${100-h}%"><span class="nli-away" style="width:${100-h}%">${esc(away)} ${100-h}%</span><span class="nli-home" style="width:${h}%">${esc(home)} ${h}%</span></div>`;
 }

 function gameCard(g,feed,now){
  const f=g.forecast||{},c=f.champion||{},home=g.home_team,away=g.away_team;
  const fav=c.p_home==null?null:(c.p_home>=0.5?home:away),favP=c.p_home==null?null:Math.max(c.p_home,1-c.p_home);
  const status=g.status==='final'&&g.final_score?`Final: ${esc(away)} ${g.final_score.away} @ ${esc(home)} ${g.final_score.home}`:(g.status==='scheduled'?'Scheduled':'Started');
  const models=(f.models||[]).map(m=>`<tr><td>${esc(m.label)}</td><td>${pct1(m.p_home)}</td><td>${num(m.margin_home)}</td></tr>`).join('');
  const chall=(g.challengers||[]).map(x=>`<tr><td>${esc(x.label)}<small>${esc(x.version)}</small></td><td>${pct1(x.p_home)}</td></tr>`).join('')||'<tr><td colspan="2">None archived for this game.</td></tr>';
  const qb=side=>{const q=((g.player_intel||{}).qb||{})[side]||{};const t=side==='home'?home:away;
   const diff=q.live_projection&&q.champion_assumes&&normName(q.live_projection)!==normName(q.champion_assumes);
   return `<li><b>${esc(t)}</b>: champion assumes <b>${esc(q.champion_assumes||'unknown')}</b>${q.starter_listed_out?' (listed Out)':''}${q.starter_questionable?' (Questionable)':''}${q.live_projection?`; live monitoring: ${esc(q.live_projection)} <small>(${esc(q.live_status||'')})</small>`:''}${diff?' <span class="gcs-pill watch">QB differs</span>':''}<small>${esc(q.injury_report||'')}</small></li>`;};
  const lu=(g.player_intel||{}).lineups;
  const lineup=lu?['away','home'].map(side=>{const l=lu[side]||{},t=side==='home'?home:away;if(!l.available)return `<div><b>${esc(t)}</b>: no lineup analysis available</div>`;
   const abs=(l.important_absences||[]).map(a=>`<li>${esc(a.player)} <small>${esc(a.unit)} · ${esc(a.status)} · ${pct(a.availability)} likely to play</small></li>`).join('')||'<li>No starter expected out.</li>';
   return `<div><b>${esc(t)}</b>: ${l.starters_expected_out} starters expected out · OL ${l.ol_starters_expected}/${l.ol_regular_starters} regular starters expected<ul>${abs}</ul></div>`;}).join(''):'<p class="gcs-note">Lineup analysis is published for upcoming games only.</p>';
  const s=g.simulation;
  const sim=s?`<div class="gcs-metrics"><div class="gcs-metric"><small>Simulated ${esc(home)} margin</small><b>${num(s.margin_home)}</b><small>80% range ${num(s.margin_p10,0)} to ${num(s.margin_p90,0)}</small></div><div class="gcs-metric"><small>Simulated total</small><b>${s.total==null?'—':s.total.toFixed(1)}</b><small>80% range ${s.total_p10==null?'—':s.total_p10.toFixed(0)}–${s.total_p90==null?'—':s.total_p90.toFixed(0)}</small></div><div class="gcs-metric"><small>Simulated P(${esc(home)})</small><b>${pct(s.p_home)}</b><small>archived ${esc(when(s.archived_at))}</small></div></div><p class="gcs-note"><span class="gcs-pill watch">Experimental</span> Drive-and-scoring simulation. Historically its totals were less accurate than a league-average baseline.</p>`:'<p class="gcs-note">No simulation archived for this game.</p>';
  const m=g.market||{},at=m.at_forecast||{},lt=m.latest;
  const mkt=`<table class="nli-table"><thead><tr><th>Price</th><th>P(${esc(home)}) no-vig</th><th>${esc(home)} spread</th><th>As of</th></tr></thead><tbody>
   <tr><td>${esc(at.source||'At forecast')}</td><td>${pct1(at.p_home_novig)}</td><td>${num(at.spread_home)}</td><td>${esc(when(at.timestamp))}</td></tr>
   ${lt?`<tr><td>${esc(lt.source)} (opening)</td><td>${pct1(lt.p_home_novig_open)}</td><td>—</td><td>opening</td></tr><tr><td>${esc(lt.source)} (latest)</td><td>${pct1(lt.p_home_novig_current)}</td><td>${num(lt.spread_home_current)}</td><td>${esc(when(lt.retrieved_at))}</td></tr>`:''}
   </tbody></table><p class="gcs-note">Champion minus market at forecast time: <b>${m.champion_minus_market_at_forecast==null?'—':num(100*m.champion_minus_market_at_forecast,1)+' pts'}</b>. ${esc(m.warning||'')}</p>`;
  const stages=(g.stages||[]).map(x=>`<li>${esc(x.stage)} · ${esc(when(x.archived_at))} · ${pct1(x.p_home)}${x.timeliness?` <small>${esc(x.timeliness.replace('_',' '))}</small>`:''}</li>`).join('');
  return `<article class="gcs-game-card nli-card" data-game="${esc(g.game_id)}">
   <div class="gcs-card-top"><div><small>Week ${g.week} · ${esc(when(g.kickoff_utc))}</small><h3>${esc(away)} @ ${esc(home)}</h3><small>${esc(status)}</small></div><span class="gcs-pill">${esc(f.stage_label||f.stage||'')}</span></div>
   ${bar(c.p_home,home,away)}
   <div class="gcs-metrics"><div class="gcs-metric"><small>Lab champion pick</small><b>${esc(fav||'—')} ${pct(favP)}</b></div><div class="gcs-metric"><small>Predicted ${esc(home)} margin</small><b>${num(c.margin_home)}</b></div><div class="gcs-metric"><small>Six-model vote</small><b>${esc((f.disagreement||{}).vote||'—')}</b></div><div class="gcs-metric"><small>Forecast archived</small><b class="nli-small">${esc(when(f.archived_at))}</b></div></div>
   <details><summary>Six-model debate</summary><table class="nli-table"><thead><tr><th>Model</th><th>P(${esc(home)})</th><th>Margin</th></tr></thead><tbody>${models}</tbody></table><small>Spread between the six: ${pct1((f.disagreement||{}).range)}. ${esc((feed.notices||{}).correlation||'')}</small></details>
   <details><summary>Player intelligence</summary><ul class="nli-list">${qb('away')}${qb('home')}</ul>${lineup}<small>${esc(((g.player_intel||{}).lineup_note)||'')}</small></details>
   <details><summary>Game simulation (experimental)</summary>${sim}</details>
   <details><summary>Market comparison (benchmark)</summary>${mkt}</details>
   <details><summary>Challengers & forecast history</summary><table class="nli-table"><thead><tr><th>Registered challenger (research)</th><th>P(${esc(home)})</th></tr></thead><tbody>${chall}</tbody></table><ul class="nli-list">${stages}</ul><small>${esc((feed.notices||{}).challengers||'')}</small></details>
  </article>`;
 }

 function performance(feed){
  const p=feed.performance||{},h=p.historical,pr=p.prospective;
  const rows=(h&&h.windows||[]).map(w=>`<tr><td>${esc(w.window)}</td><td>${w.games}</td><td>${pct1(w.accuracy)}</td><td>${w.log_loss}</td><td>${w.brier}</td><td>${w.margin_mae}</td></tr>`).join('');
  const prow=(pr&&pr.by_version||[]).map(v=>`<tr><td>${esc(v.label||v.version)}</td><td>${v.games}</td><td>${pct1(v.accuracy)}</td><td>${v.log_loss==null?'—':Number(v.log_loss).toFixed(3)}</td><td>${v.brier==null?'—':Number(v.brier).toFixed(3)}</td><td>${v.margin_mae==null?'—':Number(v.margin_mae).toFixed(2)}</td></tr>`).join('');
  return `<section class="gcs-card nli-perf"><h3>Model performance</h3>
   <p class="gcs-note"><b>Prospective</b> (pregame forecasts archived before kickoff, scored afterwards): ${pr?`${pr.games} of ${pr.required_games} games needed before any conclusion.`:'not available.'} ${esc(pr&&pr.note||'')}</p>
   ${prow?`<table class="nli-table"><thead><tr><th>Version</th><th>Games</th><th>Accuracy</th><th>Log loss</th><th>Brier</th><th>Margin MAE</th></tr></thead><tbody>${prow}</tbody></table>`:''}
   <p class="gcs-note"><b>Historical</b> (champion, walk-forward): ${esc(h&&h.note||'not available')}</p>
   ${rows?`<table class="nli-table"><thead><tr><th>Window</th><th>Games</th><th>Accuracy</th><th>Log loss</th><th>Brier</th><th>Margin MAE</th></tr></thead><tbody>${rows}</tbody></table>`:''}
  </section>`;
 }

 function render(el,feed,opts){
  opts=opts||{};const now=opts.now||Date.now();
  if(!el)return;
  if(opts.loading){el.innerHTML='<p class="gcs-note" role="status">Loading NFL lab intelligence…</p>';return;}
  if(!feed||feed.status==='unavailable'||opts.error){el.innerHTML=`<div class="gcs-card"><h3>NFL lab intelligence is not available</h3><p class="gcs-note">${esc(opts.error||'The lab has not published a forecast feed yet.')} GOING's own predictions on the other tabs are unaffected.</p></div>`;return;}
  const errs=validate(feed);
  if(errs.length){el.innerHTML=`<div class="gcs-card"><h3>NFL lab feed could not be read</h3><p class="gcs-note">The published feed failed validation (${esc(errs.slice(0,3).join(', '))}). Nothing from it is shown.</p></div>`;return;}
  const fr=freshness(feed,now);
  const games=(feed.games||[]).slice().sort((a,b)=>Date.parse(a.kickoff_utc)-Date.parse(b.kickoff_utc));
  el.innerHTML=`<div class="gcs-page nli-page">
   <div class="gcs-heading"><div><span class="gcs-kicker">NFL Ensemble Lab · research</span><h2>NFL Intelligence</h2><p>Forecasts archived by the NFL Ensemble Lab before kickoff: six-model debate, quarterback and lineup intelligence, an experimental scoring simulation and a sportsbook benchmark. This complements GOING's own predictions and does not replace them.</p></div><span class="gcs-season">Published ${esc(when(feed.generated_at))}</span></div>
   ${fr.stale?`<div class="gcs-card nli-stale" role="alert"><b>Stale data.</b> The latest lab feed is ${Math.round(fr.hours)} hours old (limit ${fr.limit} h). Forecasts below may be out of date.</div>`:''}
   <p class="gcs-source">Champion ${esc((feed.source||{}).champion_version||'')} · latest forecast archived ${esc(when((feed.freshness||{}).latest_forecast_archived_at))}. ${esc((feed.notices||{}).market||'')} ${esc((feed.notices||{}).experimental||'')}</p>
   <div class="gcs-grid nli-grid">${games.map(g=>gameCard(g,feed,now)).join('')||'<p class="gcs-note">No games in the current feed window.</p>'}</div>
   ${performance(feed)}
  </div>`;
 }
 root.GoingNflIntel={render,validate,freshness};
})(typeof window!=='undefined'?window:globalThis);
