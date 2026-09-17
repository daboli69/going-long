(function(root){
'use strict';
let cached,pending;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=x=>Number.isFinite(x)?(100*x).toFixed(1)+'%':'Not enough data';
function markup(data,now=Date.now()){
 const s=data.slate;
 if(!s)return '<p>No supported forecast is available for the confirmed offer. No probabilities have been invented.</p>';
 const closed=s.games.some(g=>Date.parse(g.kickoff)<=now)||Date.parse(s.offer.cutoff)<=now;
 return `<p><strong>${s.games.map(g=>esc(g.away+' at '+g.home)).join(' · ')} · ${esc(s.date)}</strong>${closed?' · Entries closed':''}</p>
 <p>Estimated chance of scoring or sharing the longest touchdown. Returner and D/ST can win from the same play, and equal-distance ties count, so these chances need not total 100%.</p>
 <p>Experimental research · High uncertainty · No suggested stake. Checked ${esc(new Date(s.generated_at).toLocaleString())}. ${esc(s.eligibility_status)}</p>
 <ol class="king-list">${s.candidates.map(c=>`<li><details><summary><strong>${esc(c.name)}${c.kind==='player'?' · '+esc(c.team):''}</strong> — <strong>${pct(c.probability)}</strong></summary><p>${esc(c.uncertainty)}. ${esc(c.eligible)}</p>${c.td_probability!=null?`<p>${pct(c.td_probability)} estimated chance of at least one eligible touchdown. The longest-TD estimate also considers historical scoring distances and every other modeled scorer.</p>`:''}${c.evidence.map(e=>`<p>${esc(e)}</p>`).join('')}</details></li>`).join('')}</ol>
 <details><summary>Offer rules and model assumptions</summary><p>September 17: DET–BUF only. $5 minimum pregame TD-scorer single; opt in and apply the token. Passing touchdowns credit the scorer, not the passer. The supplied token cutoff is 8:20 p.m. ET; the schedule currently lists ${esc(new Date(s.games[0].kickoff).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'}))} ET. Entries must be pregame, so use the earlier time.</p><p>${esc(s.offer.note)}</p><p>Scoring counts use a simple independent-event model; TD distances blend player history with league scoring plays. This first version does not model possession-by-possession dependence or predict the number of other winning entrants. Unassigned team scorers remain in the competition. Missing player data is shown rather than assigned a made-up chance.</p><a href="${esc(s.rule_source)}" target="_blank" rel="noopener">DraftKings explanation of returner/D/ST shared winners</a></details>
 <details><summary>Saved predictions and results</summary><p>The first pregame forecast is saved automatically by the data pipeline. Results use published play-by-play after games finish; unavailable results remain pending. These are model research results, not accepted bets or bonus payouts.</p>${(data.results||[]).map(r=>`<p>${esc(r.date)} · Longest TD: ${r.longest_yards??'No touchdown'}${r.longest_yards!=null?' yards':''} · ${esc(r.status)}</p>`).join('')||'<p>No completed saved slate has been graded yet.</p>'}</details>`;
}
async function render(){
 const target=document.getElementById('kingEndzone');if(!target)return;
 try{
  if(!cached){target.innerHTML='<p>Loading Thursday research…</p>';if(!pending)pending=fetch('/data/king-endzone.json',{signal:AbortSignal.timeout(12000)}).then(r=>{if(!r.ok)throw Error('unavailable');return r.json();}).then(x=>cached=x).finally(()=>pending=null);await pending;}
  target.innerHTML=markup(cached);
 }catch{target.innerHTML='<p>Thursday research is temporarily unavailable. Reopen Jackpot to retry. Other betting views remain available.</p>';}
}
root.GoingKingEndzone={render,markup};if(typeof module!=='undefined')module.exports=root.GoingKingEndzone;
})(globalThis);
