(function(root){
'use strict';
let cached,pending;
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=value=>Number.isFinite(value)?(100*value).toFixed(2)+'%':'Unavailable';
const clock=value=>Number.isFinite(value)?`${Math.floor(value/60)}:${String(Math.round(value%60)).padStart(2,'0')}`:'Unavailable';
function row(selection){
 const f=selection.feature_snapshot||{};
 return `<tr><td data-label="Player/DST"><details class="sb-explain"><summary><strong>${esc(selection.name)}</strong> <small>${esc(selection.team)} · ${esc(selection.position)}</small></summary><h4>Why</h4>${(selection.evidence||[]).map(x=>`<p>${esc(x)}</p>`).join('')}<p>This game's modeled first-TD clock has a ${pct(f.first_td_by_5m_given_td)} chance to occur by 5:00, conditional on a touchdown.</p><details><summary>Show me the data</summary><dl><dt>First TD model</dt><dd>${esc(f.first_td_model)}</dd><dt>Clock median</dt><dd>${clock(f.median_first_td_seconds_given_td)} elapsed game time</dd><dt>Scoring input</dt><dd>${Number.isFinite(f.total)?f.total.toFixed(1):'Unavailable'} · ${esc(f.total_source)}</dd><dt>Player sample</dt><dd>${esc(f.first_td_profile_games)} recorded games</dd><dt>Roster status</dt><dd>${esc(f.active_roster_status)}</dd></dl></details></details></td><td data-label="Game">${esc(selection.game)}</td><td data-label="Slate Breaker %"><strong>${pct(selection.slate_breaker_probability)}</strong></td><td data-label="First TD %">${pct(selection.first_td_probability)}</td><td data-label="Estimate Confidence"><span class="sb-confidence">${esc(selection.confidence?.label)}</span><small>${esc(selection.confidence?.reason)}</small></td></tr>`;
}
function markup(data){
 const s=data?.slate;
 if(!s)return '<p>Slate Breaker is unavailable. No probabilities have been invented.</p>';
 const selections=s.selections||[],leader=selections[0],games=s.games||[],validation=s.validation?.models?.[s.validation.selected]||{};
 const groups=games.map(game=>{
  const name=`${game.away}-${game.home}`,field=selections.filter(x=>x.game_id===game.id);
  return `<details class="sb-game"><summary><strong>${esc(name)}</strong><span>${field.length} eligible selections · median first TD ${clock(game.median_first_td_seconds_given_td)}</span></summary><div class="sb-table-wrap"><table class="sb-table"><thead><tr><th>Player/DST</th><th>Game</th><th>Slate Breaker %</th><th>First TD %</th><th>Estimate Confidence</th></tr></thead><tbody>${field.map(row).join('')}</tbody></table></div></details>`;
 }).join('');
 return `<article class="sb-lead"><small>SIMPLE RESULT</small><h3>${leader?`${esc(leader.name)} · ${pct(leader.slate_breaker_probability)}`:'No eligible selections'}</h3><p>Estimated chance to score the first touchdown in its game and have that touchdown occur at the fastest elapsed game time across all ${games.length} eligible games. Kickoff time is ignored.</p></article><details><summary>Method and validation</summary><p>The existing First TD model estimates who scores. A separate ${esc(s.model.time_method)} clock model estimates when each game's first touchdown occurs. The app combines the full time distributions across every game; it does not rerank First TD percentages.</p><p>${esc(s.validation.method)} · ${esc(validation.n)} out-of-sample touchdown games · log loss ${Number.isFinite(validation.log_loss)?validation.log_loss.toFixed(3):'unavailable'} · Brier ${Number.isFinite(validation.brier)?validation.brier.toFixed(3):'unavailable'}.</p><p>Exact elapsed-time ties count for every tied selection. A return touchdown is one modeled event that can credit both the returner and D/ST, so selection probabilities need not sum to 100%.</p><p>${esc(s.eligibility_note)}</p></details><div class="sb-games">${groups}</div><details><summary>Saved forecasts and outcomes</summary>${(data.results||[]).map(result=>`<p>${esc(result.date)} · fastest first TD ${clock(result.winning_elapsed_seconds)} · ${esc(result.winner_selection_ids?.join(', ')||'No eligible winner')} · ${esc(result.status)}</p>`).join('')||'<p>No completed saved Slate Breaker slate has been graded yet.</p>'}</details>`;
}
async function render(){
 const target=document.getElementById('slateBreaker');if(!target)return;
 try{
  if(!cached){target.innerHTML='<p>Loading Slate Breaker…</p>';if(!pending)pending=fetch('/api/snapshot?file=slate-breaker.json',{signal:AbortSignal.timeout(12000)}).then(r=>r.ok?r:fetch(new URL('data/slate-breaker.json',document.baseURI),{signal:AbortSignal.timeout(12000)})).then(r=>{if(!r.ok)throw Error('unavailable');return r.json();}).then(x=>cached=x).finally(()=>pending=null);await pending;}
  target.innerHTML=markup(cached);
 }catch{target.innerHTML='<p>Slate Breaker is temporarily unavailable. Reopen Jackpot to retry.</p>';}
}
root.GoingSlateBreaker={render,markup};if(typeof module!=='undefined')module.exports=root.GoingSlateBreaker;
})(globalThis);
