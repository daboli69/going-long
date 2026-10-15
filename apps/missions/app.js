(()=>{
'use strict';
const $=id=>document.getElementById(id),M=globalThis.GoingMissions;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=(x,d=1)=>Number.isFinite(x)?(x*100).toFixed(d)+'%':'—',usd=x=>Number.isFinite(x)?'$'+x.toFixed(x%1===0?0:2):'—';
const OBJ={survival:'Protect the bankroll: highest chance of still having funds for future weekends.',growth:'Grow the bankroll with controlled risk: ranked by a conservative, lower-bound growth rate.',parlay:'Find priced combinations whose payout can reach your target, ranked by the chance a single ticket does it.','cash-out':'Work toward a withdrawal while keeping a reserve; shows how long the approach survives.'};
const DEFAULTS={objective:'cash-out',bankroll:50,target:150,weeks:1,maxExposure:50,acceptableDownside:60,withdrawTarget:100,reserve:50,betTypes:'both',books:[],researchWeights:false};
let state={...DEFAULTS},feed=null,weights=null,model=null,timer=0;
try{Object.assign(state,JSON.parse(localStorage.getItem('going.missions.v1')||'{}'));}catch{}
const save=()=>{try{localStorage.setItem('going.missions.v1',JSON.stringify(state));}catch{}};
const replay=new URLSearchParams(location.search).get('asof')==='snapshot';

async function getJson(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(url+' unavailable');return r.json();}
async function load(){
 weights=await getJson('../config/sharp_weights.json');
 try{model=await getJson('../data/missions_model.json');}catch{model=null;}
 let source='live';
 if(!replay){try{feed=await getJson('/api/odds?sport=nfl');if(!Array.isArray(feed.games_raw))throw Error('bad payload');}catch{feed=null;}}
 if(!feed){source=replay?'replay':'saved';feed=await getJson('../data/nfl_betting.json');}
 feed.__source=source;
}
function readForm(){
 const f=$('msForm'),n=k=>Number(f.elements[k].value);
 state={...state,bankroll:n('bankroll'),target:n('target'),weeks:n('weeks'),maxExposure:n('maxExposure'),acceptableDownside:n('acceptableDownside'),withdrawTarget:n('withdrawTarget'),reserve:n('reserve'),betTypes:f.elements.betTypes.value,researchWeights:f.elements.researchWeights.checked,books:[...document.querySelectorAll('#msBooks input:checked')].map(i=>i.value)};
}
function writeForm(){
 const f=$('msForm');for(const k of ['bankroll','target','weeks','maxExposure','acceptableDownside','withdrawTarget','reserve','betTypes'])f.elements[k].value=state[k];
 f.elements.researchWeights.checked=Boolean(state.researchWeights);
}
function bookList(){
 const norm=globalThis.GoingSharpConsensus.makeNormalizer(weights.aliases),set=new Map();for(const e of feed.games_raw||[])for(const b of e.bookmakers||[]){const k=norm(b.key);if(!M.EXCHANGES.has(k))set.set(k,b.title||b.key);}
 $('msBooks').innerHTML=[...set].sort((a,b)=>a[1].localeCompare(b[1])).map(([k,t])=>`<label><input type="checkbox" value="${esc(k)}"${state.books.includes(k)?' checked':''}>${esc(t)}</label>`).join('');
}
function validate(){
 const s=state,bad=[];
 if(!(s.bankroll>0))bad.push('Bankroll must be positive.');if(!(s.target>s.bankroll))bad.push('Target must exceed the bankroll.');
 if(!Number.isInteger(s.weeks)||s.weeks<1||s.weeks>12)bad.push('Horizon must be 1–12 weekends.');
 if(!(s.maxExposure>=5&&s.maxExposure<=100)||!(s.acceptableDownside>=5&&s.acceptableDownside<=100))bad.push('Exposure and downside must be 5–100%.');
 if(!(s.reserve>=0)||s.reserve>s.target||!(s.withdrawTarget>=0))bad.push('Reserve cannot exceed the target; withdrawal cannot be negative.');
 return bad;
}
function compute(){
 const bad=validate(),err=$('msFormError');err.hidden=!bad.length;err.textContent=bad.join(' ');
 if(bad.length)return null;
 const asOf=replay?Date.parse(feed.generated_at):Date.now();
 return M.runMission(feed.games_raw,{now:asOf,objective:state.objective,weights:weights.game_lines,aliases:weights.aliases,model,oddsGeneratedAt:feed.generated_at,flags:{researchWeights:state.researchWeights},
  mission:{bankroll:state.bankroll,target:state.target,weeks:state.weeks,maxExposure:state.maxExposure/100,acceptableDownside:state.acceptableDownside/100,withdrawTarget:state.withdrawTarget,reserve:state.reserve,betTypes:state.betTypes,books:state.books,runs:10000}});
}
function ago(sec){return sec<90?Math.round(sec)+' s':sec<5400?Math.round(sec/60)+' min':(sec/3600).toFixed(1)+' h';}
function banners(r){
 const out=[],age=(Date.now()-Date.parse(feed.generated_at))/1000;
 if(replay)out.push(['danger','Replay of a saved snapshot taken '+new Date(feed.generated_at).toLocaleString()+'. These are NOT live prices; do not bet from this view.']);
 else if(feed.__source==='saved')out.push(['danger','Live prices are unavailable; showing the saved snapshot from '+new Date(feed.generated_at).toLocaleString()+' ('+ago(age)+' old). Opportunities require quotes under '+M.POLICY.offerMaxAgeSec/60+' minutes old, so a stale snapshot qualifies nothing.']);
 if(state.researchWeights)out.push(['','Experimental research weights are ON. They are third-party hypotheses, not validated; the equal-weight consensus is the default decision input.']);
 if(r.diagnostics.modelNote)out.push(['','GOING model cross-check unavailable: '+r.diagnostics.modelNote]);
 $('msBanner').innerHTML=out.map(([c,t])=>`<div class="ms-banner ${c}" role="note">${esc(t)}</div>`).join('');
}
function verdict(r){
 const q=r.qualified.length,best=r.strategies.filter(s=>s.qualified&&s.tickets.length);
 let html;
 if(!q){
  const refs=r.strategies.filter(s=>s.reference);
  html=`<div class="ms-verdict"><h2>No qualified opportunity right now</h2><p>${r.diagnostics.offerCount} sportsbook and exchange prices were checked against the independent market consensus. None cleared the ${pct(M.POLICY.minEv)} return hurdle with fresh quotes, agreeing sources and an executable price. Doing nothing keeps your bankroll intact.</p>${refs.length?`<p><b>What chasing ${usd(r.mission.target)} would cost.</b> The reference rows below use the least-bad available prices and are <b>negative expected value</b>; they show the trade-off, not a recommendation.</p>`:''}</div>`;
 }else{
  html=`<div class="ms-verdict ok"><h2>${q} qualified ${q===1?'opportunity':'opportunities'} · ${esc(r.objectiveLabel)} mission</h2><p>Qualified means fresh quotes, at least ${M.POLICY.minSources} independent sources agreeing, an executable sportsbook price, and an estimated return of at least ${pct(M.POLICY.minEv)} versus the market consensus. That is an estimate from market prices, not a validated edge or a promise of profit.</p></div>`;
 }
 $('msVerdict').innerHTML=html+nearMisses(r);
}
function nearMisses(r){
 if(r.qualified.length||!r.nearMisses.length)return '';
 return `<div class="ms-card"><h3>Closest to qualifying</h3><p class="ms-note">The best executable sportsbook prices against the market consensus, and why each fell short. Not recommendations.</p><ul>${r.nearMisses.map(n=>`<li><b>${esc(n.selection)}</b> ${esc(n.american)} @ ${esc(n.book)} — estimated return ${pct(n.ev)} (consensus ${pct(n.p)} vs ${pct(n.breakeven)} break-even, ${n.sources} sources). ${esc(n.reasons[0]||'')}</li>`).join('')}</ul><p class="ms-note">Missions currently prices NFL game lines only (moneyline, spread, total). Player props are not evaluated here yet.</p></div>`;
}
function oppCard(o,ticket){
 const legs=ticket.legs,isP=ticket.kind==='parlay';
 const head=isP?`${legs.length}-leg parlay · ${esc(ticket.book)}`:esc(legs[0].selection);
 const sub=isP?legs.map(l=>esc(l.selection)).join(' + '):`${esc(legs[0].away)} @ ${esc(legs[0].home)} · ${new Date(legs[0].kickoff).toLocaleString([], {weekday:'short',hour:'numeric',minute:'2-digit'})}`;
 const l0=legs[0],model=!isP&&l0.model?(l0.model.anchoredToLine?'Line-anchored (no independent signal)':pct(l0.model.prob)):'n/a';
 const ev=isP?ticket.ev:l0.ev;
 const evid=isP?[`Joint probability ${pct(ticket.pAllWin)} = product of leg consensus probabilities. Legs are in different games, so independence is assumed, not measured.`,'Ticket price is the product of posted leg prices; confirm the live parlay price in the book before betting.']:[`${l0.consensus.sources} independent sources (${esc(l0.consensus.mode)} weights, ${esc(l0.consensus.devig)} vig removal), range ${pct(l0.consensus.range[0])}–${pct(l0.consensus.range[1])}, dispersion ${(l0.consensus.dispersion*100).toFixed(2)} pp.`,`Quote ${ago(l0.ageSec)} old; consensus quotes ${ago(l0.consensus.newestAgeSec)}–${ago(l0.consensus.oldestAgeSec)} old.`,...(l0.consensus.copyClusters.length?['Copied-price books counted once: '+l0.consensus.copyClusters.map(c=>c.join('/')).join('; ')+'.']:[]),...(l0.warnings||[]),l0.clvNote];
 const srcs=!isP?l0.consensus.used.map(u=>`<li>${esc(u.source)}: ${pct(u.p)} fair (${pct(u.share,0)} weight)</li>`).join(''):legs.map(l=>`<li>${esc(l.selection)} @ ${esc(l.american)} — consensus ${pct(l.p)}, EV ${pct(l.ev)}</li>`).join('');
 return `<article class="ms-opp"><span class="ms-pill">${isP?'Parlay':'Bet'}</span><h3>${head}</h3><div class="ms-sub">${sub}</div>
 <div class="ms-metrics"><div><b>${esc(ticket.american)} @ ${esc(ticket.book)}</b><span>Offered odds (${pct(1/ticket.dec)} implied)</span></div><div><b>${pct(isP?ticket.pWin:l0.p)}</b><span>${isP?'All legs win (consensus)':'Market consensus'}</span></div><div><b>${model}</b><span>GOING model${isP?' (per leg in details)':''}</span></div><div><b>${pct(ev)}</b><span>Estimated return</span></div><div><b>${usd(ticket.stake)} → +${usd(ticket.toWin)}</b><span>Stake at your exposure</span></div><div><b>${pct(ticket.targetContribution,0)}</b><span>Of the gap to target</span></div><div><b>−${usd(ticket.stake)}</b><span>Bankroll downside</span></div><div><b>${usd(ticket.expectedProfit)}</b><span>Expected profit</span></div></div>
 <details><summary>Evidence and sources</summary><ul>${evid.map(e=>`<li>${esc(e)}</li>`).join('')}</ul><ul>${srcs}</ul></details></article>`;
}
function opps(r){
 const seen=new Set(),cards=[];
 for(const s of r.strategies.filter(s=>s.qualified))for(const t of s.tickets)if(!seen.has(t.id)){seen.add(t.id);cards.push(t);}
 $('msOpps').innerHTML=cards.length?cards.map(t=>oppCard(t.legs[0],t)).join(''):'<p class="ms-note">No qualified opportunities for these settings. Nothing is shown rather than a ranked list of unqualified bets.</p>';
}
function table(r){
 $('msRuns').textContent=r.strategies[0].result.runs.toLocaleString();
 const rows=[['Reach '+usd(r.mission.target)+(r.mission.weeks>1?' within '+r.mission.weeks+' weekends':''),s=>pct(s.result.pReachTarget)],['Lose the bankroll',s=>pct(s.result.pRuin)],['End below '+usd(r.mission.bankroll),s=>pct(s.result.pEndBelowStart)],['Expected ending bankroll',s=>usd(s.result.expectedEnding)],['Median ending bankroll',s=>usd(s.result.medianEnding)],['10th–90th percentile (total value)',s=>usd(s.result.totalValueP10)+'–'+usd(s.result.totalValueP90)],['Expected withdrawal',s=>usd(s.result.expectedWithdrawal)],['Still solvent after 4 / 8 / 12 weekends',s=>s.result.preservation.map(k=>pct(k.pSolvent,0)).join(' / ')],['Bankroll ≥ '+usd(r.mission.reserve)+' after 4 / 8 / 12',s=>s.result.preservation.map(k=>pct(k.p,0)).join(' / ')],['Stake per weekend',s=>usd(s.tickets.reduce((a,t)=>a+t.stake,0))],['Expected return on stakes',s=>s.tickets.length?pct(s.tickets.reduce((a,t)=>a+t.expectedProfit,0)/s.tickets.reduce((a,t)=>a+t.stake,0)):'—']];
 $('msTable').innerHTML=`<thead><tr><th scope="col">Outcome</th>${r.strategies.map(s=>`<th scope="col" class="${s.reference?'ref':''}">${esc(s.name)}${s.reference?'<br>(negative EV)':''}</th>`).join('')}</tr></thead><tbody>${rows.map(([l,f])=>`<tr><th scope="row">${esc(l)}</th>${r.strategies.map(s=>`<td>${f(s)}</td>`).join('')}</tr>`).join('')}</tbody>`;
}
function method(r){
 const d=r.diagnostics;
 $('msMethod').innerHTML=`<ul><li><b>Probability.</b> Each offer is judged against the leave-one-out consensus of all <em>other</em> fresh books (a book never judges itself or its price copies), after removing vig with the ${esc(d.policy.devig)} method. Only quotes for the identical contract and line are combined.</li><li><b>Equal weight is the default.</b> Research weights (Novig 7.5, FanDuel/Kalshi 1.1, …; <code>config/sharp_weights.json</code>) are an experimental hypothesis behind the toggle; learned weights are compared chronologically in <code>shared/market-validation.js</code> and none are promoted yet.</li><li><b>GOING model.</b> NFL spread and total probabilities are market-anchored (the posted line is the mean), so they are shown as a cross-check and can veto, never blended in; that would double count the market.</li><li><b>Exchanges.</b> Novig and similar prices inform consensus but are not offered as bets: fees, spread and size are not in the feed.</li><li><b>Simulation.</b> ${r.strategies[0].result.runs.toLocaleString()} seeded runs (seed ${r.strategies[0].result.seed}); probabilities are perturbed in logit space so estimates are not treated as exact.</li></ul><p><b>Assumptions</b></p><ul>${d.assumptions.map(a=>`<li>${esc(a)}</li>`).join('')}</ul><p><b>Policy thresholds (product constraints, not fitted):</b> ${esc(JSON.stringify({minEv:d.policy.minEv,minSources:d.policy.minSources,maxDispersion:d.policy.maxDispersion,offerMaxAgeMin:d.policy.offerMaxAgeSec/60}))}.</p><p><b>This snapshot:</b> ${d.events} games, ${d.offerCount} priced offers; rejected: ${esc(JSON.stringify(d.reject))}. Copy clusters: ${esc(JSON.stringify(d.copyClusters))}.</p><p><b>Not available:</b> historical CLV and price-discovery leadership need timestamped snapshots that are not yet being stored; player-prop consensus and the over/under calibration need historical prop prices with outcomes; same-game parlay pricing is not in the feed.</p>`;
}
function render(){
 for(const b of document.querySelectorAll('.ms-tabs button'))b.setAttribute('aria-selected',String(b.dataset.objective===state.objective));
 $('msObjective').textContent=OBJ[state.objective];
 const r=compute();if(!r){$('msVerdict').innerHTML='';$('msOpps').innerHTML='';$('msTable').innerHTML='';return;}
 const age=(Date.now()-Date.parse(feed.generated_at))/1000;
 $('msStatus').textContent=`${feed.__source==='live'?'Live NFL prices':feed.__source==='replay'?'Replay snapshot':'Saved NFL snapshot'} · generated ${new Date(feed.generated_at).toLocaleString()} (${ago(age)} ago) · ${r.diagnostics.events} games`;
 banners(r);verdict(r);opps(r);table(r);method(r);
}
function schedule(){readForm();save();clearTimeout(timer);timer=setTimeout(render,250);}
document.querySelector('.ms-tabs').addEventListener('click',e=>{const o=e.target.dataset?.objective;if(!o)return;state.objective=o;save();render();});
$('msForm').addEventListener('input',schedule);$('msForm').addEventListener('submit',e=>e.preventDefault());
load().then(()=>{writeForm();bookList();$('msBooks').addEventListener('input',schedule);render();}).catch(e=>{$('msStatus').textContent='Prices could not be loaded: '+e.message+'. No mission can be evaluated without them.';});
})();
