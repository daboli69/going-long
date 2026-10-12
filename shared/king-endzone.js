(function(root){
'use strict';
let cached,pending,checked=0;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=x=>Number.isFinite(x)?(100*x).toFixed(1)+'%':'Not enough data';
const expired=(s,now)=>(s.games||[]).length>0&&s.games.every(g=>Date.parse(g.kickoff)+6*3600000<now);
const stamp=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(x)?Date.parse(x):NaN;
const fresh=(x,now,hours)=>Number.isFinite(stamp(x))&&stamp(x)<=now&&now-stamp(x)<=hours*3600000;
const validOdds=x=>typeof x==='number'&&Number.isFinite(x)&&Number.isInteger(x)&&Math.abs(x)>=100;
const american=x=>x>0?'+'+x:String(x);
const clock=x=>new Date(x).toLocaleString('en-US',{timeZone:'America/New_York'})+' ET';
function selection(c,ctx){
 if(c.kind!=='player'||!c.id||!Number.isFinite(c.probability)||c.probability<0||c.probability>1)return false;
 try{return ctx.eligibility?.(c.id,c.team)?.actionable===true;}catch{return false;}
}
function priceFor(c,s,ctx,now){
 const game=s.games.find(g=>[g.home,g.away].includes(c.team));if(!game)return null;
 const quotes=(ctx.props||[]).filter(q=>{
  if(q.profileId!==c.id||q.market!=='atd'||q.dfs||!(q.line==null||q.line===.5)||String(q.bookKey||q.book||'').toLowerCase()!=='draftkings'||!validOdds(q.overOdds)||!fresh(q.updatedAt,now,2)||!Number.isFinite(stamp(q.kickoff))||!Number.isFinite(stamp(game.kickoff))||Math.abs(stamp(q.kickoff)-stamp(game.kickoff))>60000)return false;
  const teams=(q.eventTeams||[q.homeName,q.awayName]).map(t=>ctx.resolveTeam?.(t)||t);
  if(teams.length!==2||!teams.includes(game.home)||!teams.includes(game.away))return false;
  return typeof ctx.quoteState==='function'&&!ctx.quoteState(q);
 });
 // Latest matching receipt; never select an older higher price after movement.
 return quotes.sort((a,b)=>stamp(b.updatedAt)-stamp(a.updatedAt))[0]||null;
}
function highlights(s,ctx,now){
 const candidates=(s.candidates||[]).filter(c=>selection(c,ctx)).sort((a,b)=>b.probability-a.probability||String(a.id).localeCompare(String(b.id)));
 const top=candidates[0];
 // Explicit product preference: highest real single price among the three
 // strongest longest-TD forecasts. Not EV, jackpot value or a fitted policy.
 const priced=candidates.slice(0,3).map(c=>({c,q:priceFor(c,s,ctx,now)})).filter(x=>x.q);
 const topPrice=top&&priceFor(top,s,ctx,now);
 const alternative=topPrice?priced.filter(x=>x.c.id!==top.id&&x.q.overOdds>topPrice.overOdds).sort((a,b)=>a.q.overOdds-b.q.overOdds).at(-1)||null:null;
 return {top,alternative,priced};
}
function matchup(c){return (c.evidence||[]).map(e=>`<p>${esc(e)}</p>`).join('');}
function markup(data,now=Date.now(),ctx={}){
 const s=data?.slate;
 if(!s)return '<p>No supported Monday forecast is available. Schedule or current-season evidence is missing; no picks have been invented.</p>';
 if(expired(s,now))return `<p><strong>No current King of the Endzone offer.</strong> The last modeled slate (${esc(s.date)}) has been played. The next successful refresh selects the next Monday.</p><details><summary>Saved predictions and results</summary>${results(data)}</details>`;
 if(!Array.isArray(s.games)||!s.games.length)return '<p>Monday schedule unavailable; selections paused.</p>';
 const closed=s.games.some(g=>!Number.isFinite(stamp(g.kickoff))||stamp(g.kickoff)<=now)||(s.offer?.cutoff&&(!Number.isFinite(stamp(s.offer.cutoff))||stamp(s.offer.cutoff)<=now));
 const stale=!fresh(s.generated_at,now,36)||!fresh(data.generated_at||s.generated_at,now,36);
 const {top,alternative}=closed||stale?{}:highlights(s,ctx,now);
 const card=(title,c,q)=>`<article><h4>${title}</h4><p><strong>${esc(c.name)} · ${esc(c.team)}</strong></p><p>${pct(c.probability)} experimental chance of scoring or sharing the longest TD.</p><p>${pct(c.td_probability)} chance of any TD.${q?` DraftKings anytime-TD single: <strong>${american(q.overOdds)}</strong> · quote ${esc(clock(q.updatedAt))}.`:' No fresh matching DraftKings anytime-TD price.'}</p><details><summary>Why this player?</summary>${matchup(c)}</details></article>`;
 return `<p><strong>${s.games.map(g=>esc(g.away+' at '+g.home)).join(' · ')} · ${esc(s.date)}</strong>${closed?' · Entries closed':''}</p>
 <p>Monday longest-touchdown research · user-supplied $2 million shared jackpot. Confirm this week’s games, prize and entry terms in DraftKings. A higher anytime-TD price pays that single; it does not mean a larger share of the jackpot.</p>
 <p>Experimental research · High uncertainty. Checked ${esc(clock(s.generated_at))}. ${esc(s.sample_policy||'Archived baseline')}. ${esc(s.eligibility_status)}</p>
 ${stale?'<p role="status"><strong>Forecast stale or timestamp unavailable; current selections paused.</strong></p>':closed?'<p>Saved pregame research only. All games on this Monday remain in the competition; no late-entry recommendation is shown.</p>':top?`<div class="king-highlights">${card('Top longest-TD chance',top,priceFor(top,s,ctx,now))}${alternative?card('Higher-paying alternative among the top three',alternative.c,alternative.q):'<article><h4>Higher-paying alternative</h4><p>No verified higher-paying alternative is available among the top three. Comparing payouts requires a fresh matching DraftKings price for the leader and alternative. Missing prices are never substituted from another sportsbook.</p></article>'}</div>`:'<p role="status">Current player availability is unverified, or no eligible player has enough current-season evidence. Highlighted selections are paused.</p>'}
 <p>Estimated chance of scoring or sharing the longest touchdown across every listed game. Returner and D/ST can win from the same play, and equal-distance ties count, so these chances need not total 100%.</p>
 <details><summary>Complete research field</summary><ol class="king-list">${(s.candidates||[]).map(c=>`<li><details><summary><strong>${esc(c.name)}${c.kind==='player'?' · '+esc(c.team):''}</strong> — <strong>${pct(c.probability)}</strong></summary><p>${esc(c.uncertainty)}. ${esc(c.eligible)}${c.kind==='player'&&!selection(c,ctx)?' Current availability not cleared; this is a saved forecast, not an actionable selection.':''}</p>${matchup(c)}</details></li>`).join('')}</ol></details>
 <details><summary>Offer rules and model assumptions</summary><p>${esc(s.offer?.note)}</p><p>Slate closes at the first listed kickoff. Equal-distance ties and returner/D/ST overlap are modeled for research; confirm actual qualifying selections and terms in your offer. Scoring counts use an independent-event scenario. TD distances blend this season’s player scores with five current-season league scoring plays; team rates use eight current-season league team-games. Unassigned scorers remain in the competition. Defensive weaknesses and offensive tendencies are shown where observed; missing coverage/alignment is disclosed. These descriptive matchup inputs do not retune probability without backtesting.</p><p>The alternative uses the highest actual anytime-TD price among the three highest longest-TD forecasts, excluding the leader. This is a transparent shortlist preference, not validated expected value. No number of winners, shared-prize dollar value or guaranteed hit rate is estimated.</p></details>
 <details><summary>Saved predictions and results</summary><p>The first pregame forecast is saved once and preserved. Published play-by-play grades completed slates; results are research outcomes, not accepted bets or bonus payouts.</p>${results(data)}</details>`;
}
function results(data){return (data.results||[]).map(r=>`<p>${esc(r.date)} · Longest TD: ${esc(r.longest_yards??'No touchdown')}${r.longest_yards!=null?' yards':''} · ${esc(r.status)}</p>`).join('')||'<p>No completed saved slate has been graded yet.</p>';}
async function render(ctx={}){
 const target=document.getElementById('kingEndzone');if(!target)return;
 try{
  if(!cached||Date.now()-checked>=55000){
   if(!cached)target.innerHTML='<p>Loading Monday research…</p>';
   if(!pending)pending=fetch('/api/snapshot?file=king-endzone.json',{cache:'no-store',signal:AbortSignal.timeout(12000)}).then(r=>r.ok?r:fetch('/data/king-endzone.json',{cache:'no-store',signal:AbortSignal.timeout(12000)})).then(r=>{if(!r.ok)throw Error('unavailable');return r.json();}).then(x=>{cached=x;checked=Date.now();}).finally(()=>pending=null);
   await pending;
  }
  target.innerHTML=markup(cached,Date.now(),ctx);
 }catch{target.innerHTML='<p role="status">Monday forecast refresh failed; selections are paused. Automatic checks retry while Jackpot is open.</p>';}
}
root.GoingKingEndzone={render,markup,highlights,priceFor};if(typeof module!=='undefined')module.exports=root.GoingKingEndzone;
})(globalThis);
