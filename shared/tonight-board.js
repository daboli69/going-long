(function(root){
'use strict';
const STATES=new WeakMap(), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateKey=at=>Number.isFinite(Date.parse(at))?new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(at)):null;
const P=()=>root.GoingFootballPicks||(typeof require==='function'?require('./football-picks.js'):null);
const oddsLabel=x=>x>0?'+'+x:String(x),decimal=x=>x>0?1+x/100:1+100/Math.abs(x);
function todayGames(schedule,rows,now=Date.now(),sport='nfl'){
 const games=new Map(),day=dateKey(new Date(now).toISOString());
 for(const g of [...(schedule||[]),...(rows||[]).map(r=>r.candidate)]){
  if(!g||g.sport&&g.sport!==sport||dateKey(g.kickoff)!==day||!(Date.parse(g.kickoff)>now))continue;
  const c={...g,sport,home:g.homeCode||g.home,away:g.awayCode||g.away};
  if(!c.home||!c.away)continue;const key=P().gameKey(c);if(!games.has(key))games.set(key,c);
 }
 return [...games].sort((a,b)=>Date.parse(a[1].kickoff)-Date.parse(b[1].kickoff));
}
function offersFor(row,now){
 const c=row.candidate,offers=[{book:c.book,odds:c.odds,updatedAt:c.updatedAt},...(row.offers||[])],seen=new Map();
 for(const o of offers){
  const at=Date.parse(o.updatedAt),id=String(o.book||'').trim().toLowerCase();
  if(!id||!Number.isFinite(at)||at>now)continue;
  const previous=seen.get(id);
  // Choose the latest observation before checking its price. An invalid or
  // extreme latest quote must not resurrect an older attractive quote.
  if(!previous||at>Date.parse(previous.updatedAt))seen.set(id,o);
 }
 const result=[];
 for(const o of seen.values()){
  const next={...c,book:o.book,odds:o.odds,dec:decimal(o.odds),updatedAt:o.updatedAt},price=P().quote(next,now);
  if(price.valid&&price.saveable&&next.odds>=-500)result.push({...row,candidate:next,evidence:{...row.evidence,price}});
 }
 return result.sort((a,b)=>Number(b.evidence.price.fresh)-Number(a.evidence.price.fresh)||b.candidate.dec-a.candidate.dec||Date.parse(b.candidate.updatedAt)-Date.parse(a.candidate.updatedAt)||String(a.candidate.book).localeCompare(String(b.candidate.book)));
}
function selectRows(rows,{game,market='all',book='all',now=Date.now()}={}){
 const result=[];
 for(const row of rows||[]){
  const c=row?.candidate,e=row?.evidence;
  if(!c||!e?.eligible||!e.interesting||!(Date.parse(c.kickoff)>now)||c.injury?.blockRecommendation||e.gameKey!==game)continue;
  if(market!=='all'&&!(market==='props'?c.kind==='prop':market==='games'?c.kind==='game':c.market===market))continue;
  const offers=offersFor(row,now).filter(r=>book==='all'||r.candidate.book===book);if(!offers.length)continue;
  result.push({...offers[0],tonightOffers:offersFor(row,now)});
 }
 return result.sort((a,b)=>b.evidence.rating-a.evidence.rating||String(a.evidence.key).localeCompare(String(b.evidence.key)));
}
function savedRows(saved,rows,now=Date.now(),sport='nfl'){
 const day=dateKey(new Date(now).toISOString());
 return (saved||[]).filter(c=>c.sport===sport&&dateKey(c.kickoff)===day).map(c=>{
  const match=(rows||[]).find(r=>P().contractKey(r.candidate)===P().contractKey(c));
  const quote=match&&offersFor(match,now).find(r=>r.candidate.book===c.book);
  const status=Date.parse(c.kickoff)<=now?'Game started — archived selection':!quote||!quote.evidence.price.fresh?'Current exact quote unavailable — recheck':quote.candidate.odds!==c.odds?'Price changed: '+oddsLabel(c.odds)+' → '+oddsLabel(quote.candidate.odds):'Exact price still observed';
  return {candidate:c,status};
 });
}
function card(row,{index,label,onSave,saved}){
 const {candidate:c,evidence:e}=row,forecast=e.facts?.filter(f=>f[0]===(c.market==='total'?'Current-season total estimate':'Current-season margin estimate')||f[0]==='Forecast lean vs this line')||[],presentation=P().ratingPresentation(c,e);
 const projection=c.kind==='prop'&&Number.isFinite(c.projMean)?`Existing model projection ${c.projMean.toFixed(1)} · line ${c.line} · ${c.n} recorded model games. Current-season evidence is listed in research.`:forecast.map(f=>f[1]).join(' · ');
 const isSaved=(saved||[]).some(r=>P().contractKey(r.candidate)===P().contractKey(c)&&r.candidate.book===c.book);
 const watch=(c.injury&&c.injury.state!=='available')||e.facts?.some(f=>f[0]==='Teammate availability'),stamp=new Date(c.updatedAt).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
 return `<article class="tonight-card"><div class="tonight-card-head"><small>${esc(e.family)} · ${esc(presentation.label)}</small>${watch?'<span class="tonight-watch">Check availability</span>':''}</div><h3>${esc(c.kind==='prop'?c.player:c.away+' @ '+c.home)}</h3><h4>${esc(label?label(c):c.side+' '+c.line+' '+c.market)}</h4>${projection?`<p class="tonight-projection">${esc(projection)}</p>`:''}<p><strong>Why this lean</strong>${esc(e.why)}</p><p class="tonight-concern"><strong>What could change it</strong>${esc(e.concern)}</p><div class="tonight-price"><b>${esc(c.book)} ${esc(oddsLabel(c.odds))}</b><small class="${e.price.fresh?'':'tonight-watch'}">${e.price.fresh?'Recently observed':'SAVED PRICE — recheck current line'} · ${esc(stamp)} ET</small></div><details data-tonight-detail="${esc(e.key)}"><summary>Compare prices & research</summary><p>${esc(presentation.explanation)}</p>${c.market==='atd'?`<p>Existing model TD estimate ${(100*c.prob).toFixed(1)}%; uncertain, not a proven hit rate.</p>`:''}<p>Observed same-line quotes: ${row.tonightOffers.map(r=>esc(r.candidate.book)+' '+esc(oddsLabel(r.candidate.odds))+(r.evidence.price.fresh?' (recent)':' (saved — recheck)')).join(' · ')}</p><dl>${(e.facts||[]).map(f=>'<dt>'+esc(f[0])+'</dt><dd>'+esc(f[1])+'</dd>').join('')}</dl><p>${esc(e.priceCaution||'No established sportsbook edge. These observations support research, not a guaranteed result.')}</p></details><button type="button" data-tonight-save="${index}" aria-pressed="${isSaved}" ${onSave&&e.price.fresh?'':'disabled'}>${e.price.fresh?(isSaved?'Remove from comparison':'+ Save to comparison'):'Refresh price before saving'}</button></article>`;
}
function render(host,options={}){
 if(!host||!P())return;let state=STATES.get(host);if(!state){state={game:null,market:'all',book:'all',limit:8,open:new Set()};STATES.set(host,state);}
 const {board,schedule,sport='nfl',now=Date.now(),loading,label,teamLabel=x=>x,onSave,onOpen}=options,rows=board?.picks||[],games=todayGames(schedule,rows,now,sport),saved=savedRows(typeof options.saved==='function'?options.saved():options.saved,rows,now,sport);
 if(!games.some(([key])=>key===state.game)){state.game=games[0]?.[0]||null;state.limit=8;}
 const books=[...new Set(rows.filter(r=>r.evidence?.gameKey===state.game).flatMap(r=>offersFor(r,now).map(o=>o.candidate.book)))].sort();
 if(state.book!=='all'&&!books.includes(state.book))state.book='all';
 const selected=selectRows(rows,{...state,now}),shown=P().displayMix(selected,{mix:state.market==='all',limit:state.limit}),active=host.ownerDocument?.activeElement,focus=host.contains(active)?active?.dataset?.tonightControl:null;
 host.classList.add('tonight-board');
 host.innerHTML=`<div class="tonight-heading"><div><h2>Tonight’s Bets</h2><p>Football leans and observed quotes for today’s remaining games. Find a case, compare its price and save it.</p></div><button type="button" data-tonight-open="games">Game lines</button></div><p class="tonight-disclosure">A lean is a direction to research, not a promise of profit. Existing model estimates and availability checks remain unchanged.</p>${games.length?`<div class="tonight-controls"><label>Tonight’s game<select data-tonight-control="game">${games.map(([key,g])=>`<option value="${esc(key)}" ${key===state.game?'selected':''}>${esc(teamLabel(g.away,sport))} @ ${esc(teamLabel(g.home,sport))} · ${esc(new Date(g.kickoff).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'}))} ET</option>`).join('')}</select></label><label>Market<select data-tonight-control="market">${[['all','All markets'],['games','Game lines'],['spread','Spreads'],['total','Totals'],['moneyline','Moneylines'],['props','Player props'],['atd','Anytime TD']].map(([k,v])=>`<option value="${k}" ${state.market===k?'selected':''}>${v}</option>`).join('')}</select></label><label>Sportsbook<select data-tonight-control="book"><option value="all">Best observed same-line price</option>${books.map(b=>`<option value="${esc(b)}" ${b===state.book?'selected':''}>${esc(b)}</option>`).join('')}</select></label></div><p class="tonight-count" role="status">${selected.length} supported football leans · ${selected.filter(r=>r.evidence.price.fresh).length} recent prices · ${selected.filter(r=>!r.evidence.price.fresh).length} saved prices to recheck · prices shorter than -500 excluded</p><div class="tonight-grid">${shown.map((r,i)=>card(r,{index:i,label,onSave,saved})).join('')||`<p class="tonight-empty">${loading?'Loading tonight’s models and quotes…':!books.length?'No matched prices observed within the last 24 hours are available for this game. Open Markets or Game lines to inspect feed coverage; stale quotes are not actionable.':'No supported lean with an observed price matches these filters. Try All markets; a missing pick is not a prediction against that outcome.'}</p>`}</div>${selected.length>shown.length?'<button type="button" data-tonight-more>Show more tonight’s leans</button>':''}`:`<p class="tonight-empty" role="status">${loading?'Loading tonight’s schedule…':'No unstarted games remain today in the loaded schedule. Use GOING Picks below for upcoming games.'}</p>`}`;
 if(saved.length)host.insertAdjacentHTML('beforeend',`<details class="tonight-saved" open><summary>Your saved selections tonight · ${saved.length}</summary><ul>${saved.map(({candidate:c,status})=>`<li><b>${esc(c.label||label?.(c)||c.player||c.market)}</b><small>${esc(c.book)} ${esc(oddsLabel(c.odds))} · ${esc(status)}</small></li>`).join('')}</ul><p>${saved.some((r,i)=>saved.some((s,j)=>j!==i&&P().gameKey(r.candidate)===P().gameKey(s.candidate)))?'Several saved selections rely on the same game. Their outcomes can overlap; this is not independent diversification.':'Review the exact lines and final availability before placing a ticket.'} No combined hit rate is estimated.</p></details>`);
 host.onchange=event=>{const control=event.target.dataset?.tonightControl;if(!['game','market','book'].includes(control))return;state[control]=event.target.value;state.limit=8;render(host,options);};
 host.onclick=event=>{const save=event.target.closest('[data-tonight-save]'),open=event.target.closest('[data-tonight-open]');if(save){const row=shown[Number(save.dataset.tonightSave)];if(!row||!P().quote(row.candidate,Date.now()).fresh||!(Date.parse(row.candidate.kickoff)>Date.now())){render(host,{...options,now:Date.now()});return;}onSave?.(row);render(host,options);host.querySelector(`[data-tonight-save="${save.dataset.tonightSave}"]`)?.focus({preventScroll:true});}else if(open)onOpen?.(open.dataset.tonightOpen);else if(event.target.closest('[data-tonight-more]')){state.limit+=8;render(host,options);}};
 for(const detail of host.querySelectorAll('[data-tonight-detail]')){detail.open=state.open.has(detail.dataset.tonightDetail);detail.ontoggle=()=>detail.open?state.open.add(detail.dataset.tonightDetail):state.open.delete(detail.dataset.tonightDetail);}
 if(focus)host.querySelector(`[data-tonight-control="${focus}"]`)?.focus({preventScroll:true});
 return {games,selected};
}
root.GoingTonightUI={dateKey,todayGames,offersFor,selectRows,savedRows,render};if(typeof module!=='undefined')module.exports=root.GoingTonightUI;
})(globalThis);
