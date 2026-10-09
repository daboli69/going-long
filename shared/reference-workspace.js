/* October 4 approved references. DOM presentation adapters only.
 * The original controls, event delegates, data and research policies stay authoritative.
 * No ownership, team score, weather, movement or verified-performance values are inferred.
 */
(()=>{
'use strict';
const $=id=>document.getElementById(id),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),icon=n=>window.GoingVisual.icon(n);
const head=document.querySelector('.bt-head'),grid=$('btTabGroup');if(!head||!grid)return;
const active=new Set(['today','games','dfs','parlay','jackpot']);
const make=(tag,cls,html='')=>{const e=document.createElement(tag);e.className=cls;e.innerHTML=html;return e;};
const section=(title,body)=>`<section class="r-surface"><h3>${esc(title)}</h3>${body}</section>`;
const observe=(node,fn)=>{if(!node)return;let queued=false;new MutationObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;fn();});}).observe(node,{childList:true,subtree:true});fn();};
const setHtml=(e,html)=>{if(e&&e.innerHTML!==html)e.innerHTML=html;};
const reveal=e=>{if(!e)return;for(let p=e;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;e.scrollIntoView({block:'start',behavior:'smooth'});};
const search=$('goingSearch')?.closest('.going-search'),searchMarker=document.createComment('original global search position');if(search)search.before(searchMarker);
const status=document.querySelector('.g-source-status'),period=$('btPeriodGroup'),overview=$('btOverview'),periodMarker=document.createComment('original market period position'),overviewMarker=document.createComment('original board summary position');period?.before(periodMarker);overview?.before(overviewMarker);let todayHero='';
let plays=new URLSearchParams(location.search).get('view')==='plays';
function sync(){
 const tool=grid.querySelector('button[aria-pressed=true]')?.dataset.section||'today';
 document.body.dataset.referenceActive=String(active.has(tool));document.body.dataset.referenceView=plays&&tool==='today'?'plays':'default';
 const hero=head.querySelector('.v-football-hero');
 if(active.has(tool)&&hero){
  if(tool==='today'&&!hero.querySelector('.v-hero-kicker'))hero.prepend(make('small','v-hero-kicker',`${esc(document.body.dataset.visualLeague?.toUpperCase()||'NFL')} · GOING LONG`));
  if(tool==='today'&&!hero.querySelector('h1')?.textContent.includes('BEST PLAYS'))todayHero=hero.innerHTML;
  if(plays&&tool==='today'){setHtml(hero,`<small class="v-hero-kicker">${esc(document.body.dataset.visualLeague?.toUpperCase()||'NFL')} · GOING LONG</small><h1>BEST <em>PLAYS</em></h1><p>Select a game. See GOING picks, why, risk and price.</p><div class="v-hero-features"><span>${icon('target')}<b>Model-screened<br>research</b></span><span>${icon('bars')}<b>Traceable<br>evidence</b></span><span>${icon('game')}<b>Real markets<br>& prices</b></span></div>`);}
  else if(tool==='today'&&todayHero)setHtml(hero,todayHero);
  else if(tool!=='today'&&!hero.querySelector('.v-hero-features'))hero.insertAdjacentHTML('beforeend',`<div class="v-hero-features"><span>${icon('target')}<b>Model-driven<br>research</b></span><span>${icon('bars')}<b>Recorded<br>football data</b></span><span>${icon('game')}<b>Real markets<br>& prices</b></span></div>`);
  if(tool==='today'){if(plays)head.insertBefore(grid,hero);else head.insertBefore(hero,grid);}
 }
 if(search&&tool!=='score'){if(active.has(tool)&&matchMedia('(min-width:760px)').matches){const actions=document.querySelector('.v-header-actions');if(search.parentNode!==actions)actions.prepend(search);}else if(search.parentNode!==searchMarker.parentNode&&searchMarker.parentNode)searchMarker.after(search);}
 if(status&&tool!=='score'){if(active.has(tool)&&status!==head.parentElement.lastElementChild)head.parentElement.append(status);else if(!active.has(tool)&&status.parentNode===searchMarker.parentNode)searchMarker.before(status);}
 if(tool==='games'){const toolbar=document.querySelector('.r-games-toolbar'),workspace=document.querySelector('.r-games-workspace');if(period&&toolbar&&period.parentNode!==toolbar)toolbar.prepend(period);if(overview&&workspace&&overview.parentNode!==workspace.parentNode)workspace.before(overview);decorateOverview();}else{if(period&&periodMarker.parentNode&&period.parentNode!==periodMarker.parentNode)periodMarker.after(period);if(overview&&overviewMarker.parentNode&&overview.parentNode!==overviewMarker.parentNode)overviewMarker.after(overview);overview?.querySelectorAll('.r-stat-icon').forEach(e=>e.remove());}
 if(tool==='today'){const ranked=$('bestChance')?.closest('details');if(plays&&ranked)ranked.open=true;updatePlays();}
 if(tool==='games')updateGames();if(tool==='parlay')updateParlay();if(tool==='jackpot')updateJackpot();
}
new MutationObserver(sync).observe(grid,{subtree:true,attributes:true,attributeFilter:['aria-pressed']});window.addEventListener('resize',sync);
grid.addEventListener('click',e=>{if(e.target.closest('[data-section="today"]')&&plays){plays=false;const u=new URL(location.href);u.searchParams.delete('view');history.replaceState(history.state,'',u);sync();}});

// Today: retain existing filters and confidence views, with the reference's compact toolbar.
const today=$('btBestPanel');
if(today){
 const bar=make('div','r-today-toolbar'),date=$('bestDay')?.closest('.slate-primary');
 if(date)bar.append(date);const filter=make('details','r-filter-popover','<summary>Filters</summary>');
 const discovery=$('bestSearch')?.closest('details');if(discovery){discovery.querySelector('summary')?.remove();filter.append(...discovery.childNodes);discovery.remove();}
 const searchLabel=make('label','r-search-label','<span class="sr-only">Search research candidates</span>');const candidateSearch=filter.querySelector('#bestSearch');if(candidateSearch)searchLabel.append(candidateSearch);bar.append(searchLabel,filter);
 today.querySelector('.picks-legacy')?.append(bar);
 const view=make('div','r-view-tabs',`<button type="button" data-reference-view="games" aria-pressed="${!plays}">${icon('game')} Featured Matchups</button><button type="button" data-reference-view="plays" aria-pressed="${plays}">${icon('market')} Best Plays</button>`);
 $('bestTodaySummary')?.after(view);
 view.onclick=e=>{const b=e.target.closest('[data-reference-view]');if(!b)return;plays=b.dataset.referenceView==='plays';for(const x of view.querySelectorAll('button'))x.setAttribute('aria-pressed',String((x.dataset.referenceView==='plays')===plays));const u=new URL(location.href);plays?u.searchParams.set('view','plays'):u.searchParams.delete('view');history.replaceState(history.state,'',u);if(!plays&&typeof chooseBettingTab==='function')chooseBettingTab('best');sync();};
 const ranked=$('bestChance')?.closest('details');if(ranked){ranked.classList.add('r-ranked-lists');const aside=make('aside','r-plays-sidebar');ranked.append(aside);}
 const insights=make('section','r-today-insights',section('Slate insights','<p>Open a matchup to compare the current book prices and the evidence behind each selection.</p><div class="r-inline-links"><button type="button" data-best-tab="games">Compare matchups</button><a href="/results/">Evidence & results →</a></div>')+section('Price & availability checks','<p>Weather, public betting and line movement are unavailable in this view. A recent quote does not establish confirmed participation or betting value.</p>'));(today.querySelector('.picks-legacy')||today).append(insights);
 const advanced=make('div','r-today-advanced');for(const e of [...today.children])if(e.matches('details:not(.r-ranked-lists),.slate-primary'))advanced.append(e);today.append(advanced);
 observe($('bestTodaySummary'),()=>{const summary=$('bestTodaySummary');if(!summary.querySelector('.r-summary-four'))summary.append(make('div','r-summary-four',`${icon('book')}<b>Evidence</b><span>Inspect GOING Confidence</span>`));updatePlays();});
 observe($('bestChance'),updatePlays);
 observe($('bestGameSlate'),()=>{
  for(const card of $('bestGameSlate').querySelectorAll('.slate-game:not([data-reference-card])')){
   card.dataset.referenceCard='true';let lead;try{const key=card.querySelector('[data-slate-game]')?.dataset.slateGame,g=TODAY_GROUPS.get(key);lead=g?.model[0]||g?.price[0];}catch{}
   if(lead){const line=make('div','r-match-metrics',`<div><small>Estimated chance</small><b>${Number.isFinite(lead.prob)?(lead.prob*100).toFixed(1)+'%':'Unavailable'}</b></div><div><small>Observed price</small><b>${esc(typeof americanOddsLabel==='function'?americanOddsLabel(lead.odds):lead.odds)}</b></div><div><small>Sportsbook</small><b>${esc(lead.book||'Unavailable')}</b></div>`);card.querySelector('.slate-bets')?.before(line);}
   const bets=card.querySelector('.slate-bets'),body=bets?.querySelector('.slate-bets-body');for(const info of card.querySelectorAll(':scope>.slate-count,:scope>.slate-evidence'))if(body)bets.insertBefore(info,body);
  }
 });
}
function updatePlays(){
 for(const card of $('bestChance')?.querySelectorAll('.g-card:not([data-reference-play])')||[]){
  const head=card.querySelector('.g-bet-head');if(!head)continue;card.dataset.referencePlay='true';
  const main=make('div','r-play-main'),side=make('aside','r-play-actions'),details=card.querySelector(':scope>details'),price=head.querySelector('.g-price'),actions=card.querySelector('.g-actions');
  const facts=[...card.querySelectorAll('.best-evidence dt')].map(dt=>[dt.textContent.trim(),dt.nextElementSibling?.textContent.trim()||'Unavailable']);const fact=label=>facts.find(([name])=>name===label)?.[1]||'Unavailable';
  const tiles=make('div','r-play-facts',[['Projection','Projection average'],['Estimated chance','Model probability'],['Observed odds','Price'],['Estimated return','Estimated return']].map(([label,key])=>`<div><small>${esc(label)}</small><b>${esc(fact(key))}</b></div>`).join(''));
  const confidence=card.querySelector('.g-evidence .g-stat:last-child');if(price)side.append(price);if(actions)side.append(actions);if(confidence)side.append(confidence);
  for(const n of [...card.childNodes]){if(n===side||n===actions)continue;if(n.nodeType===1&&(n.matches('.g-evidence')||n.matches('.g-research-context,.g-score-context')||n.matches('p.g-note')&&n.textContent.includes('Parlay fit'))){if(details)details.append(n);else main.append(n);}else main.append(n);}
  const why=[...main.querySelectorAll(':scope>p')].find(p=>p.textContent.startsWith('Why'));if(why)why.after(tiles);else main.prepend(tiles);
  const risk=main.querySelector(':scope>.g-warning');if(risk){const disclosure=make('details','r-play-risk','<summary>Main risk · unvalidated estimate; confirm price & availability</summary>');risk.before(disclosure);disclosure.append(risk);}card.append(main,side);
 }
 const aside=document.querySelector('.r-plays-sidebar');if(!aside)return;
 const sum=$('bestTodaySummary');setHtml(aside,section('Research overview',`<p class="r-stamp">${esc(new Date().toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'America/New_York'}))} · Eastern</p><div class="r-sidebar-stats">${[...(sum?.children||[])].slice(0,2).map(e=>`<div><b>${esc(e.querySelector('b')?.textContent||'—')}</b><small>${esc(e.querySelector('span:last-child')?.textContent||'')}</small></div>`).join('')}</div><p>Order follows the existing Today settings. Estimated chance and betting value are different.</p>`)+section('Results & validation','<p>Verified ROI and a Best Plays performance curve are not available. No historical win-rate claim is made.</p><a href="/results/">Inspect recorded evidence →</a>')+section('Betting tools','<p>Use Add / compare / parlay on any candidate to inspect the selection or add it to your research draft.</p>'));
}

// Games: a selected-matchup workspace composed from the already-rendered quote cards.
const games=$('btGamesPanel');let chosenGame=0,gameFingerprint='';
function decorateOverview(){if(document.body.dataset.visualTool!=='games'||!overview)return;for(const [i,tile] of [...overview.children].entries())if(!tile.querySelector('.r-stat-icon'))tile.prepend(make('span','r-stat-icon',icon(['calendar','bars','book','file'][i])));}
if(games){
 const workspace=make('div','r-games-workspace'),left=make('section','r-games-list r-surface'),center=make('section','r-selected-game r-surface'),aside=make('aside','r-game-evidence');workspace.append(left,center,aside);
 const legacy=make('details','r-original-games','<summary>All matchup cards · book comparisons & period markets</summary>');const list=$('btGamesList');if(list){list.before(workspace,legacy);legacy.append(list);if($('btMoreGames'))legacy.append($('btMoreGames'));}
 const overview=$('btOverview');if(overview)games.insertBefore(overview,workspace);
 observe(overview,decorateOverview);
 const toolbar=make('div','r-games-toolbar');if($('btPeriodGroup'))toolbar.append($('btPeriodGroup'));if($('btGamesCount'))toolbar.append($('btGamesCount'));(overview||workspace).before(toolbar);if($('btLoadReal'))legacy.append($('btLoadReal'));
 left.onclick=e=>{const b=e.target.closest('[data-reference-game]');if(!b)return;chosenGame=Number(b.dataset.referenceGame);gameFingerprint='';updateGames();};
 center.onclick=e=>{if(e.target.closest('[data-reference-compare]'))$('btGamesList')?.querySelector(`[data-compare="${chosenGame}"]`)?.click();};
 observe(list,()=>{gameFingerprint='';updateGames();});observe(overview,()=>{gameFingerprint='';updateGames();});
}
function updateGames(){
 const workspace=document.querySelector('.r-games-workspace');if(!workspace)return;const cards=[...$('btGamesList').querySelectorAll('.bt-game')],full=!!cards[0]?.querySelector('[data-compare]');workspace.hidden=!full;
 const legacy=document.querySelector('.r-original-games');if(!full){legacy.open=true;return;}
 chosenGame=Math.min(chosenGame,Math.max(0,cards.length-1));const selected=cards[chosenGame],fingerprint=chosenGame+'|'+cards.map(c=>c.textContent).join('|');if(fingerprint===gameFingerprint)return;gameFingerprint=fingerprint;
 const left=workspace.children[0],center=workspace.children[1],aside=workspace.children[2];
 let rows=[];try{rows=BET.drawerGames||[];}catch{}const g=rows[chosenGame]?.[0],badge=code=>typeof window.teamBadge==='function'?window.teamBadge(code):'';
 left.innerHTML=`<h3>Games in this slate <small>${cards.length} games</small></h3><div class="r-game-rows">${cards.map((c,i)=>{const game=rows[i]?.[0];return `<button type="button" class="r-game-row" data-reference-game="${i}" aria-pressed="${i===chosenGame}" aria-label="Select ${esc(c.querySelector('.bt-game-head b')?.textContent)}"><span class="r-row-teams">${game?badge(game.awayCode||game.away)+`<b>${esc(game.awayCode||game.away)}</b>`+badge(game.homeCode||game.home)+`<b>${esc(game.homeCode||game.home)}</b>`:`<b>${esc(c.querySelector('.bt-game-head b')?.textContent)}</b>`}</span><span class="r-row-lines">${[...(c.querySelectorAll('.bt-best-grid b')||[])].slice(0,2).map(e=>`<b>${esc(e.textContent)}</b>`).join('')}</span><small>${game?esc(new Date(game.kickoff).toLocaleString('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'2-digit'}))+' ET':esc(c.querySelector('time')?.textContent)}</small></button>`;}).join('')}</div>`;
 const teams=g?`<div class="r-match-teams"><div>${badge(g.awayCode||g.away)}<b>${esc(g.away)}</b></div><span>@</span><div>${badge(g.homeCode||g.home)}<b>${esc(g.home)}</b></div></div>`:`<h2>${esc(selected.querySelector('.bt-game-head b')?.textContent)}</h2>`;
 const metrics=g?.model?`<div class="r-model-tiles"><div><small>Projected total points</small><b>${Number.isFinite(g.model.total_mean)?g.model.total_mean.toFixed(1):'Unavailable'}</b><span>Historical model</span></div><div><small>Projected home margin</small><b>${Number.isFinite(g.model.margin_mean)?g.model.margin_mean.toFixed(1):'Unavailable'}</b><span>Not a validated edge</span></div></div>`:'';
 center.innerHTML=`<header><small>${esc(selected.querySelector('time')?.textContent)}</small><button type="button" data-reference-compare>Compare books ↗</button></header>${teams}${selected.querySelector('.bt-best-grid')?.outerHTML||''}<div class="r-match-tabs"><b>Matchup</b><button type="button" data-reference-compare>Book prices</button><a href="/long/?mode=betting&tab=props">Player markets</a></div><h3>Matchup overview</h3><p>Compare available full-game prices. A large model-price disagreement needs review before it can support a bet.</p>${metrics}${selected.querySelector('.bt-compare-hint')?.outerHTML||''}<details open><summary>What matters in this game</summary>${(typeof window.gameIntelMarkup==='function'?window.gameIntelMarkup(g):'')}${selected.querySelector('.football-coaches')?.outerHTML||''}${(typeof window.gameIntelMarkup==='function'&&window.gameIntelMarkup(g))||selected.querySelector('.football-coaches')?'':'<p>Additional current matchup evidence is not available in this quote card.</p>'}</details><button type="button" data-reference-compare>Open every sportsbook price →</button>`;
 aside.innerHTML=section('Model evidence',`<p>${esc(selected.querySelector('.bt-compare-hint strong')?.textContent||'No positive estimated return shown for this matchup.')}</p><p>Historical research estimates are not validated. Estimated return is not a demonstrated edge.</p>`)+section('Book coverage',`<strong class="r-big-stat">${esc(selected.querySelector('.bt-coverage')?.textContent)}</strong><p>Best displayed lines use currently eligible quotes. Open Compare books for timestamps and both sides.</p>`)+section('Public betting & team index','<p>Public betting percentages and a universal team GOING Score are unavailable. Player GOING Score remains a separate evidence index.</p>');
}

// DFS: move the original import, objective, pool and roster controls into columns.
const dfs=$('dfsClassicRoot');
if(dfs)observe(dfs,()=>{
 if(!dfs.querySelector('.dk-heading')||dfs.querySelector('.r-dfs-workspace'))return;
 const workspace=make('div','r-dfs-workspace'),left=make('section','r-dfs-source'),middle=make('section','r-dfs-options'),right=make('section','r-dfs-lineup r-surface','<h3>Your lineup <small>DraftKings Classic</small></h3>');
 const heading=dfs.querySelector('.dk-heading');heading.classList.add('r-dfs-intro');
 const nodes=[...dfs.children];const pool=dfs.querySelector('.dk-pool'),importer=dfs.querySelector('.dk-import'),modes=dfs.querySelector('.dk-modes'),roster=dfs.querySelector('.dk-roster'),budget=dfs.querySelector('.dk-budget'),toolbar=dfs.querySelector('.dk-toolbar');
 if(importer){const guide=importer.querySelector(':scope > p');if(guide){const disclosure=make('details','r-import-guide','<summary>Contest verification · CSV instructions · paste import</summary>'),paste=importer.querySelector(':scope>details');disclosure.append(guide);if(paste)disclosure.append(paste);importer.append(disclosure);importer.querySelector('summary').after(make('p','r-import-brief','Upload the official DraftKings salary CSV for accurate salaries and player pool.'));}left.append(importer);}if(pool){pool.open=matchMedia('(min-width:1000px)').matches;const list=pool.querySelector('#dk-pool-list');if(list)list.before(make('div','r-pool-columns','<b>Player</b><span>Position · Team · Salary · DFS points · Rush/rec TD mean</span>'));left.append(pool);}
 middle.innerHTML='<h3>Quick build options</h3>';if(modes)middle.append(modes);
 for(const n of nodes){if(n===heading||n===importer||n===pool||n===modes||n===roster||n===budget||n===toolbar)continue;if(n.matches('details.dk-analysis'))middle.append(n);else if(n.matches('p'))middle.append(n);}
 if(budget)right.append(budget);else right.insertAdjacentHTML('beforeend','<div class="dk-budget r-empty-budget"><strong>$50,000<small>Salary remaining</small></strong><span>0 / 9<small>Roster spots filled</small></span></div>');
 if(roster)right.append(roster);else right.insertAdjacentHTML('beforeend',`<ol class="r-empty-roster">${['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'].map(s=>`<li><b>${s}</b><span>Select a player</span><span aria-hidden="true">＋</span></li>`).join('')}</ol>`);
 if(toolbar)right.append(toolbar);workspace.append(left,middle,right);dfs.append(workspace);
});

// Parlay: the original draft and settings keep their event-delegation parents.
const parlay=$('btParlaysPanel');
if(parlay){
 const steps=make('nav','r-parlay-steps','<button type="button" data-reference-step="build"><b>1</b> Build your parlay</button><button type="button" data-reference-step="analyze"><b>2</b> Analyze the evidence</button><button type="button" data-reference-step="review"><b>3</b> Review your draft</button>');steps.setAttribute('aria-label','Parlay workflow');parlay.prepend(steps);
 const work=make('div','r-parlay-workspace'),left=make('section','r-parlay-source r-surface','<h3>Choose your games</h3>'),center=make('section','r-parlay-builder'),aside=make('aside','r-parlay-evidence');
 const context=parlay.querySelector('.parlay-context'),picker=$('parlayGamePicker'),settings=parlay.querySelector('.parlay-settings'),build=$('parlayBuild')?.closest('.sig-actions');if(context)left.append(context);if(picker){left.append(picker);picker.open=matchMedia('(min-width:1000px)').matches;}if(settings)left.append(settings);if(build)center.append(build);if($('parlaysStatus'))center.append($('parlaysStatus'));if($('parlayDraft'))center.append($('parlayDraft'));work.append(left,center,aside);parlay.append(work);
 steps.onclick=e=>{const step=e.target.closest('[data-reference-step]')?.dataset.referenceStep;if(step==='build')reveal(settings);if(step==='analyze')reveal($('bestParlay')?.querySelector('details'));if(step==='review')reveal($('parlayDraft'));};
 observe($('bestParlay'),updateParlay);
}
function updateParlay(){
 const aside=document.querySelector('.r-parlay-evidence');if(!aside)return;const ticket=$('bestParlay')?.querySelector('.parlay-ticket'),legs=ticket?.querySelectorAll('.parlay-leg')||[],metric=[...(ticket?.querySelectorAll(':scope > p')||[])].find(p=>p.textContent.includes('estimated chance all legs win')),warning=ticket?.querySelector('.g-warning');
 setHtml(aside,section('Parlay insights',`<div class="r-ticket-ring"><b>${legs.length}</b><small>Draft legs</small></div><p>${esc(metric?.textContent||warning?.textContent||'Build a draft to inspect its current price and evidence.')}</p>`)+section('Construction & risk',`<p>${esc(ticket?.querySelector('.parlay-warnings')?.textContent||'Different-game estimates assume independence. Same-game joint probability is unavailable.')}</p>`)+section('Validation status','<p>No verified ROI or hit rate is available for this draft. Inspect each leg and confirm the actual book ticket.</p>'));
}

// Jackpot: visualize the existing first-TD field; never combine first/last/longest models.
const jackpot=$('btPromoPanel');let jackpotChoice=0,jackpotFingerprint='';
if(jackpot){
 const original=make('details','r-jackpot-offers','<summary>Specialized offers · last TD, longest TD & anytime-TD slips</summary>');original.append(...jackpot.childNodes);jackpot.append(original);
 const work=make('div','r-jackpot-workspace'),left=make('section','r-jackpot-games r-surface','<h3>Games · first touchdown research</h3>'),right=make('section','r-jackpot-players r-surface'),explanation=make('section','r-jackpot-insights',section('How to use Jackpot','<p>First TD, last TD and longest touchdown answer separate questions. Their estimates cannot be multiplied into a combined jackpot probability.</p>')+section('Evidence & limitations','<p>Review the complete eligible scorer field and current role/availability. Prior-season support and unverified game-day participation can limit these estimates.</p>'));
 const filters=make('div','r-jackpot-toolbar','<label><span class="sr-only">Search selected game scorers</span><input type="search" id="rJackpotSearch" placeholder="Search selected game scorers"></label><p>First TD field · current football week · select a game below</p>');filters.addEventListener('input',filterJackpot);
 work.append(left,right);original.before(filters,work,explanation);
 left.onclick=e=>{const b=e.target.closest('[data-reference-jackpot]');if(!b)return;jackpotChoice=Number(b.dataset.referenceJackpot);jackpotFingerprint='';updateJackpot();};
 observe($('btDataNote'),()=>{jackpotFingerprint='';if(document.body.dataset.visualTool==='jackpot')updateJackpot();});
}
function filterJackpot(){const query=$('rJackpotSearch')?.value.trim().toLowerCase()||'';document.querySelectorAll('.r-jackpot-players tbody tr').forEach(row=>{row.hidden=!!query&&!row.textContent.toLowerCase().includes(query);});}
function updateJackpot(){
 const work=document.querySelector('.r-jackpot-workspace');if(!work)return;
 let field=[];try{field=Object.values(BET.history?.derivatives?.first_td||{}).filter(g=>g.status==='ready'&&Date.parse(g.kickoff)>Date.now()&&inCurrentFootballWeek(g.kickoff)).sort((a,b)=>Date.parse(a.kickoff)-Date.parse(b.kickoff));}catch{}
 const fp=JSON.stringify(field)+jackpotChoice;if(fp===jackpotFingerprint)return;jackpotFingerprint=fp;const left=work.children[0],right=work.children[1];
 if(!field.length){left.innerHTML='<h3>Games · first touchdown research</h3><p>No ready pregame first-TD field is available. Specialized offers remain below.</p>';right.innerHTML='<h3>First-TD model evidence</h3><p>No probabilities or player names are invented.</p>';return;}
 const eligible=g=>Object.values(g.outcomes||{}).filter(p=>p.player_id&&p.name&&p.probability>0&&p.probability<1);
 jackpotChoice=Math.min(jackpotChoice,field.length-1);const g=field[jackpotChoice];left.innerHTML=`<h3>Games <small>${field.length} modeled matchups</small></h3><div class="r-game-rows">${field.map((g,i)=>`<button type="button" data-reference-jackpot="${i}" aria-pressed="${i===jackpotChoice}"><b>${esc(g.away)} @ ${esc(g.home)}</b><small>${esc(new Date(g.kickoff).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}))} ET</small><span>${eligible(g).length} eligible scorers</span></button>`).join('')}</div>`;
 const players=eligible(g).sort((a,b)=>b.probability-a.probability);right.innerHTML=`<h3>${esc(g.away)} @ ${esc(g.home)}</h3><p class="r-stamp">First-TD model estimates · not a combined jackpot probability</p><div class="r-table-scroll"><table><thead><tr><th>Player</th><th>First TD</th><th>Model break-even</th></tr></thead><tbody>${players.map(p=>`<tr><th>${esc(p.name)}<small>${esc(p.team)}</small></th><td><div class="r-model-bar"><i style="width:${Math.max(0,Math.min(100,100*p.probability))}%"></i></div>${Number.isFinite(p.probability)?(100*p.probability).toFixed(1)+'%':'Unavailable'}</td><td>${esc(typeof americanOddsLabel==='function'?americanOddsLabel(p.fair_odds):p.fair_odds)}</td></tr>`).join('')}</tbody></table></div><p>Break-even odds are model outputs, not sportsbook quotes. Defense, other scorers and no-TD outcomes remain in the field; these player estimates are not rescaled.</p>`;
 filterJackpot();
}
sync();
})();
