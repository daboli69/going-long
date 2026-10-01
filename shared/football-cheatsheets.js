/* NFL cheatsheets built only from GOING's published model, usage, outcome and price data. */
(function(root){
 'use strict';
 const STORE='goinglong.cheatsheets.v2';
 const SHEETS=[
  ['markets','Market board'],['game-lines','Game lines'],['hit-rates','Hit rates'],['roles','Player roles'],
  ['matchups','Role matchups'],['coverage','Coverage'],['teams','Team trends'],
  ['defense','Defense & explosives'],['odds','Odds differences']
 ];
 const MARKETS={pass_yds:'Pass yards',pass_tds:'Pass TDs',rush_yds:'Rush yards',rush_tds:'Rush TDs',rec_yds:'Receiving yards',receptions:'Receptions',rec_tds:'Receiving TDs',atd:'Any TD',first_td:'First TD',pass_yds_1h:'1H pass yards',pass_yds_1q:'Q1 pass yards',rush_yds_1h:'1H rush yards',rush_yds_1q:'Q1 rush yards',rec_yds_1h:'1H receiving yards',rec_yds_1q:'Q1 receiving yards',receptions_1h:'1H receptions',receptions_1q:'Q1 receptions'};
 const MARKET_STATS={pass_yds:'pass_yds',pass_tds:'pass_tds',rush_yds:'rush_yds',rush_tds:'rush_tds',rec_yds:'rec_yds',receptions:'receptions',rec_tds:'rec_tds',atd:'atd'};
 const DEFAULT={sheet:'roles',query:'',team:'ALL',position:'ALL',market:'ALL',book:'ALL',window:'season',sort:'target_share',freshOnly:true,minGames:0,activeOnly:false};
 const GROUPS=[['Players',['roles','hit-rates']],['Matchups',['defense','matchups','coverage','teams']],['Markets',['markets','game-lines','odds']]];
 const DESCRIPTIONS={roles:'Compare target, carry and snap shares. Open a player for the measured role and sample.', 'hit-rates':'Compare recorded results with today’s exact line, then inspect the game-by-game chart.',defense:'Find the defenses allowing explosive plays by position and play type.',matchups:'See how a player’s current usage fits an opponent’s measured weakness.',coverage:'Compare conditional defensive coverage and quarterback target tendencies.',teams:'Compare the upcoming teams’ pace, passing tendencies and opponent profiles.',markets:'Compare GOING projections with real sportsbook lines and prices.','game-lines':'Compare upcoming game projections with available spread, total and moneyline prices.',odds:'Compare prices across books for the same player, game, market and line.'};
 let visibleLimit=40,cardCharts=[],cardMini=[],filtersOpen=false;
 const SHEET_SORT={markets:'edge','game-lines':'kickoff','hit-rates':'hit-rate',roles:'target_share',matchups:'active',coverage:'active',teams:'pace_seconds',defense:'explosive_rate',odds:'gap'};
 let state=readState(),dataRef=null,paintTimer=null;
 function readState(){try{const stored=JSON.parse(localStorage.getItem(STORE)||'{}'),linked=new URL(location.href).searchParams.get('sheet'),sheet=SHEETS.some(([id])=>id===linked)?linked:SHEETS.some(([id])=>id===stored.sheet)?stored.sheet:DEFAULT.sheet;return {...DEFAULT,...stored,sheet,sort:linked?SHEET_SORT[sheet]:stored.sort||DEFAULT.sort};}catch{return {...DEFAULT};}}
 function saveState(){try{localStorage.setItem(STORE,JSON.stringify(state));const url=new URL(location.href);if(url.searchParams.get('tab')==='cheatsheets'){url.searchParams.set('sheet',state.sheet);history.replaceState(history.state,'',url);}}catch{}}
 function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
 function finite(v){return v!==null&&v!==''&&Number.isFinite(Number(v));}
 function num(v,d=1){return finite(v)?Number(v).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d}):'—';}
 function pct(v,d=1){return finite(v)?`${(Number(v)*100).toFixed(d)}%`:'—';}
 function odds(v){return finite(v)?`${Number(v)>0?'+':''}${Number(v)}`:'—';}
 function date(v){const t=Date.parse(v);return Number.isFinite(t)?new Date(t).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'time unavailable';}
 function label(m){return MARKETS[m]||String(m||'Market').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());}
 function cap(v){return String(v||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());}
 function fmtStat(v){return finite(v)?num(v,2):'Unavailable';}
 function roleName(v){return cap(String(v||'').replace(/_RECEIVING|_RUSHING/g,''));}
 function shareBar(v){if(!finite(v))return '';const width=Math.max(0,Math.min(100,Number(v)*100));return `<span class="gcs-bar" aria-hidden="true"><i style="width:${width.toFixed(1)}%"></i></span>`;}
 function setOptions(values,current,allText='All teams'){
  const list=[...new Set(values.map(x=>String(x||'')).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  return `<option value="ALL">${allText}</option>${list.map(v=>`<option value="${esc(v)}" ${v===current?'selected':''}>${esc(v)}</option>`).join('')}`;
 }
 function currentScope(d){return d.context?.scopes?.[String(d.season||d.context?.season)]||{};}
 function teamSet(d){const scope=currentScope(d),set=new Set(Object.keys(scope.teams||{}));for(const p of Object.values(scope.players||{}))if(p.team)set.add(p.team);for(const g of d.schedule||[]){if(g.home)set.add(g.home);if(g.away)set.add(g.away);}return [...set];}
 function playersFor(d){return Object.values(currentScope(d).players||{});}
 function currentQuotes(d){return (d.props||[]).filter(p=>(!d.isCurrentProp||d.isCurrentProp(p))&&!p.dfs&&(finite(p.line)||['atd','first_td'].includes(p.market))&&(finite(p.overOdds)||finite(p.underOdds)));}
 function quoteIsFresh(d,p){if(d.quoteStatus){try{return !d.quoteStatus(p);}catch{return false;}}const k=Date.parse(p.kickoff),u=Date.parse(p.updatedAt);return (!Number.isFinite(k)||k>Date.now())&&(!Number.isFinite(u)||Date.now()-u<24*3600000);}
 function groupedQuotes(d){
  const map=new Map();
  for(const p of currentQuotes(d)){
   const id=JSON.stringify([p.eventId||`${p.awayName||''}|${p.homeName||''}|${p.kickoff||''}`,p.profileId||p.player,p.market,p.line]);
   if(!map.has(id))map.set(id,{id,player:p.player,profileId:p.profileId,team:p.team,opp:p.opp,market:p.market,line:finite(p.line)?Number(p.line):p.market==='atd'?.5:null,kickoff:p.kickoff,homeName:p.homeName,awayName:p.awayName,position:d.history?.profiles?.[p.profileId]?.position||'',offers:[]});
   map.get(id).offers.push(p);
  }
  return [...map.values()];
 }
 function sourceNote(d){return `Current-season usage ${d.asOf||'date unavailable'} · player model ${d.modelUpdated?date(d.modelUpdated):'date unavailable'} · matchup signals ${d.learningUpdated?date(d.learningUpdated):'date unavailable'} · prices ${cap(d.priceStatus||'unavailable')}${d.quotesUpdated?` (${date(d.quotesUpdated)})`:''}.`}
 function metric(label,value,note=''){const match=String(value).match(/^([\d.]+)%$/),bar=match&&Number(match[1])<=100?`<span class="gcs-meter" aria-hidden="true"><i style="width:${Number(match[1])}%"></i></span>`:'';return `<div class="gcs-metric"><small>${esc(label)}</small><b>${esc(value)}</b>${bar}${note?`<small>${esc(note)}</small>`:''}</div>`;}
 function compareChart(title,series,unit=''){
  const values=series.filter(x=>finite(x[1]));if(!values.length)return '';
  const low=Math.min(0,...values.map(x=>Number(x[1]))),high=Math.max(unit==='%'?100:0,...values.map(x=>Number(x[1]))),span=high-low||1,zero=(0-low)/span*100;
  return `<figure class="gcs-comparison"><figcaption>${esc(title)}</figcaption>${values.map(([name,value],i)=>`<div class="gcs-chart-line"><span>${esc(name)}</span><span class="gcs-chart-track" aria-hidden="true"><i class="tone-${i%2}" style="left:${Math.min(zero,(Number(value)-low)/span*100)}%;width:${Math.abs(Number(value))/span*100}%"></i></span><b>${esc(num(value,1))}${esc(unit)}</b></div>`).join('')}</figure>`;
 }
 function historyChart(games,field,line){
  const rows=games.filter(g=>finite(g[field])).slice(-10);if(!rows.length)return '';
  const max=Math.max(1,Number(line)||0,...rows.map(g=>Number(g[field]))),min=Math.min(0,...rows.map(g=>Number(g[field]))),span=max-min||1,y=v=>110-(v-min)/span*82,w=288/rows.length;
  return `<figure class="gcs-history"><figcaption>Game results vs line ${esc(num(line,1))} <small>${games.length>10?'Latest 10 shown · full log below':'Oldest → newest'}</small></figcaption><svg viewBox="0 0 320 140" role="img" aria-label="Recorded game results compared with line ${esc(line)}">${rows.map((g,i)=>{const value=Number(g[field]),status=value>line?'over':value===line?'push':'under',x=16+i*w;return `<g><title>${esc(g.date||`${g.season} week ${g.week}`)}: ${value}, ${status}</title><rect class="${status}" x="${x+3}" y="${Math.min(y(value),y(0))}" width="${Math.max(2,w-6)}" height="${Math.max(1,Math.abs(y(value)-y(0)))}" rx="3"/><text x="${x+w/2}" y="${y(value)-5}" text-anchor="middle">${value}</text><text class="gcs-axis" x="${x+w/2}" y="130" text-anchor="middle">${esc(g.week?`W${g.week}`:String(g.date||'').slice(5,10))}</text></g>`;}).join('')}<line class="gcs-line" x1="12" x2="308" y1="${y(line)}" y2="${y(line)}"/></svg><div class="gcs-legend"><span>Green: over</span><span>Coral: under</span><span>Amber: push</span><span>Dashed: market line</span></div></figure>`;
 }
 function pill(text,kind=''){const display=text==='too_few_plays'?'Small sample':String(text||'').replaceAll('_',' ');return `<span class="gcs-pill ${kind}">${esc(display)}</span>`;}
 function empty(message){return `<div class="gcs-empty">${esc(message)}</div>`;}
 function navMarkup(d){return `<aside class="gcs-sidebar"><div class="gcs-sidebar-title">Cheatsheets</div><nav class="gcs-tabs" aria-label="NFL cheatsheets">${GROUPS.map(([group,ids])=>`<div class="gcs-nav-group"><span>${group}</span>${ids.map(id=>`<button type="button" data-cheat-sheet="${id}" aria-pressed="${state.sheet===id}">${esc(SHEETS.find(s=>s[0]===id)[1])}<span aria-hidden="true">›</span></button>`).join('')}</div>`).join('')}</nav><button class="gcs-back" data-cheat-open-tab="best">← Today's picks</button></aside>`;}
 function summaryMarkup(d){
  const q=currentQuotes(d),fresh=q.filter(p=>quoteIsFresh(d,p)).length,players=playersFor(d),signals=d.learning?.matchup_signals||[],active=signals.filter(x=>x.active_signal).length;
  return `<div class="gcs-summary">${metric('Games this week',String((d.schedule||[]).length))}${metric('Priced prop rows',String(q.length),`${fresh} with a current quote`)}${metric('Current-season players',String(players.length),`${d.season||'Season'} role samples`)}${metric('Active role edges',String(active),`${signals.length} role records reviewed`)}</div>`;
 }
 function quickLinks(){return `<div class="gcs-shortcuts" aria-label="Go to a GOING Long tool"><button type="button" data-cheat-open-tab="score">GOING Score</button><button type="button" data-cheat-open-tab="firsttd">First TD</button><button type="button" data-cheat-open-tab="games">Game lines</button><button type="button" data-cheat-open-tab="props">All markets</button><button type="button" data-cheat-open-tab="parlays">Parlay Lab</button></div>`;}
 function toolbarMarkup(d){
  const sheet=state.sheet,players=playersFor(d),teams=teamSet(d),markets=[...new Set(currentQuotes(d).map(p=>p.market))],books=[...new Set(currentQuotes(d).flatMap(p=>[p.book].filter(Boolean)))];
  const commonSearch=`<label class="gcs-search">Search<input type="search" data-cheat-filter="query" aria-label="Search cheatsheets" placeholder="Player, team, market or role" value="${esc(state.query)}"></label>`;
  const teamControl=`<label>Team<select data-cheat-filter="team">${setOptions(teams,state.team)}</select></label>`;
  const posValues=sheet==='roles'?players.map(p=>p.position):sheet==='defense'?['WR','TE','RB','QB']:sheet==='matchups'?(d.learning?.matchup_signals||[]).map(x=>roleName(x.role)):[];
  const posControl=posValues.length?`<label>${sheet==='defense'?'Role':'Position'}<select data-cheat-filter="position">${setOptions(posValues,state.position,'All positions')}</select></label>`:'';
  const marketControl=['markets','hit-rates','odds'].includes(sheet)?`<label>Market<select data-cheat-filter="market"><option value="ALL">All markets</option>${markets.map(m=>`<option value="${esc(m)}" ${state.market===m?'selected':''}>${esc(label(m))}</option>`).join('')}${state.market!=='ALL'&&!markets.includes(state.market)?`<option selected value="${esc(state.market)}">${esc(label(state.market))}</option>`:''}</select></label>`:'';
  const bookControl=['markets','game-lines','hit-rates','odds'].includes(sheet)?`<label>Book<select data-cheat-filter="book">${setOptions(sheet==='game-lines'?(d.games||[]).map(g=>g.book):books,state.book,'All books')}</select></label>`:'';
  const windowControl=sheet==='hit-rates'?`<label>Game window<select data-cheat-filter="window"><option value="season" ${state.window==='season'?'selected':''}>${esc(d.season||'Current')} season</option><option value="last5" ${state.window==='last5'?'selected':''}>Last 5 recorded games</option><option value="prior" ${state.window==='prior'?'selected':''}>${Number(d.season||0)-1} season</option></select></label><label>Minimum games<input type="number" min="0" max="25" step="1" value="${Number(state.minGames)||0}" data-cheat-filter="minGames" aria-label="Minimum sample games"></label>`:'';
  const freshControl=['markets','game-lines','hit-rates','odds'].includes(sheet)?`<button type="button" class="gcs-filter-toggle" data-cheat-fresh aria-pressed="${state.freshOnly}">${state.freshOnly?'✓ Fresh prices only':'Include saved / stale prices'}</button>`:'';
  const sortOptions={markets:[['edge','Estimated return'],['projection','Projection'],['kickoff','Kickoff']], 'game-lines':[['kickoff','Kickoff'],['model-margin','Model margin'],['model-total','Model total']], 'hit-rates':[['hit-rate','Observed hit rate'],['sample','Sample size'],['player','Player']],roles:[['target_share','Target share'],['rush_share','Rush share'],['share','Snap share'],['games','Games']],matchups:[['active','Signal status'],['confidence','Confidence'],['player','Player']],coverage:[['active','Signal status'],['coverage','Coverage rate'],['player','Player']],teams:[['pace_seconds','Pace'],['pass_over_expected','Pass rate over expected'],['plays_per_game','Plays per game']],defense:[['explosive_rate','Explosive rate allowed'],['yards_per_opportunity','Yards per opportunity'],['redzone_rate','Red-zone rate'],['sample','Opportunities']],odds:[['books','Sportsbooks'],['gap','Price range'],['player','Player']]}[sheet]||[];
  const sortControl=sortOptions.length?`<label>Sort<select data-cheat-filter="sort">${sortOptions.map(([v,l])=>`<option value="${v}" ${state.sort===v?'selected':''}>${l}</option>`).join('')}</select></label>`:'';
  const activeFilters=['team','position','market','book'].filter(k=>state[k]!=='ALL').length+(state.minGames>0?1:0);
  return `<div class="gcs-toolbar">${commonSearch}<button class="gcs-mobile-filter" type="button" data-cheat-filters aria-expanded="${filtersOpen}" aria-controls="gcsFilterFields">Filters${activeFilters?` · ${activeFilters}`:''} ▾</button><div id="gcsFilterFields" class="gcs-filter-fields ${filtersOpen?'is-open':''}">${teamControl}${posControl}${marketControl}${bookControl}${windowControl}${sortControl}${freshControl}</div></div>`;
 }
 function matchesQuery(text){const q=String(state.query||'').toLowerCase().trim();return !q||String(text||'').toLowerCase().includes(q);}
 function matchFilter(text,rowTeam='',rowPosition=''){
  return matchesQuery(text)&&(state.team==='ALL'||state.team===rowTeam)&&(state.position==='ALL'||state.position===rowPosition);
 }
 function filterGroups(d){
  const groups=groupedQuotes(d),freshOnly=state.freshOnly;
  return groups.map(g=>({...g,offers:g.offers.filter(p=>(state.book==='ALL'||p.book===state.book)&&(!freshOnly||quoteIsFresh(d,p)))}))
   .filter(g=>g.offers.length&&(state.market==='ALL'||g.market===state.market)&&matchFilter(`${g.player} ${g.team} ${g.opp} ${label(g.market)} ${g.homeName} ${g.awayName}`,g.team,g.position));
 }
 function evaluateGroup(d,g){
  const evaluated=g.offers.map(p=>({p,result:d.evaluateQuote?.(p)||{},fresh:quoteIsFresh(d,p)}));
  const best=evaluated.slice().sort((a,b)=>(b.result.best?.ev??-Infinity)-(a.result.best?.ev??-Infinity))[0];
  const over=evaluated.filter(x=>finite(x.p.overOdds)).sort((a,b)=>Number(b.p.overOdds)-Number(a.p.overOdds))[0];
  const under=evaluated.filter(x=>finite(x.p.underOdds)).sort((a,b)=>Number(b.p.underOdds)-Number(a.p.underOdds))[0];
  return {best,over,under,books:new Set(g.offers.map(x=>x.bookKey||x.book).filter(Boolean)).size,prices:evaluated};
 }
 function sortGroups(d,groups){
  const key=state.sort;
  return groups.map(g=>({...g,_view:evaluateGroup(d,g)})).sort((a,b)=>{
   const val=(x)=>key==='projection'?x._view.best?.p?.projMean:key==='kickoff'?Date.parse(x.kickoff):x._view.best?.result?.best?.ev;
   const av=val(a),bv=val(b);if(!finite(av)&&!finite(bv))return 0;if(!finite(av))return 1;if(!finite(bv))return -1;return key==='kickoff'?Number(av)-Number(bv):Number(bv)-Number(av);
  });
 }
 function marketCard(d,g,index){
  const e=g._view||evaluateGroup(d,g),best=e.best?.p||g.offers[0],res=e.best?.result||{},prob=res.probabilities||{},bookOver=e.over?.p,bookUnder=e.under?.p,profile=d.history?.profiles?.[g.profileId]||{},games=profile.games?.length||0,injury=best.injury;
  const model=best.model||{},displayOdds=[bookOver?`Over ${odds(bookOver.overOdds)} · ${bookOver.book}`:'',bookUnder?`Under ${odds(bookUnder.underOdds)} · ${bookUnder.book}`:''].filter(Boolean).join('  ·  ')||'Price unavailable';
  const status=e.best?.fresh?'Current quote':'Saved / stale quote';
  const evidence=[model.family?`Projection family: ${model.family}`:'Projection family unavailable',finite(model.n)?`Model sample: ${model.n} recorded games`:'Model sample unavailable',injury?.status?`Availability: ${injury.status}${injury.reason?` — ${injury.reason}`:''}`:'No matched injury designation in this quote',best.updatedAt?`Quote observed: ${date(best.updatedAt)}`:'Quote timestamp unavailable',best.adjustment||null,best.matchStatus||null].filter(Boolean);
  const reasons=res.best?.trust?.reasons||[];
  cardCharts.push(compareChart('Projection and market line',[['GOING projection',best.projMean],['Market line',g.line]]));
  return `<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(label(g.market))} · ${esc(g.team||'Team unavailable')}${g.opp?` vs ${esc(g.opp)}`:''}</span><h3>${esc(g.player||'Player unavailable')}</h3><small>${esc(g.homeName||'')} ${g.awayName&&g.homeName?'·':''} ${esc(g.awayName||'')} · ${esc(date(g.kickoff))}</small></div>${pill(status,e.best?.fresh?'good':'watch')}</div><div class="gcs-metrics">${metric('Line',g.market==='atd'?'Any TD':g.market==='first_td'?'First TD':num(g.line,1))}${metric('GOING projection',finite(best.projMean)?num(best.projMean,1):'Unavailable',finite(model.n)?`${model.n} modeled games`:best.matchStatus||'No matched profile')}${metric('Over probability',pct(prob.over),finite(prob.push)&&prob.push>0?`${pct(prob.push)} push probability`:'Model estimate')}${metric('Under probability',pct(prob.under),'Model estimate')}</div><div class="gcs-card-price"><b>${esc(displayOdds)}</b><span>${e.books} sportsbook${e.books===1?'':'s'} · ${res.best?.side?`best model-price side: ${esc(res.best.side)}`:'No supported probability'}</span></div><p class="gcs-note">${res.best?.reason?esc(res.best.reason):finite(res.best?.ev)?`Model estimate at the displayed price: ${(Number(res.best.ev)*100).toFixed(1)}% expected return per $1 before uncertainty.`:'No price-adjusted estimate available.'} ${injury?.reason?esc(injury.reason):''}</p><details><summary>Show the data</summary><div class="gcs-evidence">${evidence.map(x=>`<span>${esc(x)}</span>`).join('')}${reasons.map(x=>`<span>${esc(x)}</span>`).join('')}</div><div class="gcs-price-list">${e.prices.map(({p,fresh})=>`<div><b>${esc(p.book||'Book unavailable')}</b><span>O ${esc(odds(p.overOdds))} · U ${esc(odds(p.underOdds))} · ${fresh?'current':'saved / stale'} · ${esc(date(p.updatedAt))}</span></div>`).join('')}</div><small>Actual available prices only. Projection/probability is GOING’s model output; descriptive historical rate is on the Hit rates sheet. No sheet grade is substituted for probability.</small></details></article>`;
 }
 function marketsSheet(d){
  const rows=sortGroups(d,filterGroups(d));
  const note=`${rows.length} player / market / line combinations after filters. Prices are grouped only when player, event, market and line match.`;
  return `<p class="gcs-note">${esc(note)} GOING probabilities are estimates, not guaranteed outcomes. Select a sportsbook to narrow the exact quotes.</p><div class="gcs-grid">${rows.map((r,i)=>marketCard(d,r,i)).join('')||empty('No current, matched prop quotes meet these filters. Refresh live props or change the book, market, search, or freshness filter.')}</div>`;
 }
 function gameLinesSheet(d){
  const groups=new Map();
  for(const g of d.games||[]){
   if(g.sport!=='nfl'||!d.isCurrentGame?.(g.kickoff)||Date.parse(g.kickoff)<=Date.now())continue;
   const home=g.homeCode||g.home,away=g.awayCode||g.away,key=[away,home,g.kickoff].join('|');
   if(!groups.has(key))groups.set(key,{home,away,kickoff:g.kickoff,quotes:[],model:g.model||null});
   const group=groups.get(key);group.quotes.push(g);if(!group.model&&g.model)group.model=g.model;
  }
  let rows=[...groups.values()].map(g=>({...g,quotes:g.quotes.filter(q=>(state.book==='ALL'||q.book===state.book)&&(!state.freshOnly||d.freshGameQuote?.(q)!==false))})).filter(g=>g.quotes.length&&(state.team==='ALL'||state.team===g.home||state.team===g.away)&&matchesQuery(`${g.home} ${g.away}`));
   rows.sort((a,b)=>{const key=state.sort==='model-margin'?'margin_mean':state.sort==='model-total'?'total_mean':null;if(key){const x=finite(a.model?.[key])?Number(a.model[key]):-Infinity,y=finite(b.model?.[key])?Number(b.model[key]):-Infinity;return y-x;}return Date.parse(a.kickoff)-Date.parse(b.kickoff);});
  return `<p class="gcs-note">GOING’s published game projection and current book lines are shown side by side. The model is not changed here. Quotes can differ by book; verify the actual ticket before betting.</p><div class="gcs-grid">${rows.map(g=>{
   const best=d.bestGameLines?.(g.quotes)||{},m=g.model||{},sp=best.spread,total=best.total,ml=best.ml;
   const homeLine=sp&&finite(sp.spread)?`${sp.spread>0?'+':''}${num(sp.spread,1)}`:'Unavailable',totalLine=total&&finite(total.total)?num(total.total,1):'Unavailable';
   const modelMargin=finite(m.margin_mean)?`${Number(m.margin_mean)>0?'+':''}${num(m.margin_mean,1)} ${esc(g.home)} margin`:'Unavailable',modelTotal=finite(m.total_mean)?num(m.total_mean,1):'Unavailable';
   const fresh=Boolean(sp||total||ml),bookCount=new Set(g.quotes.map(q=>q.book).filter(Boolean)).size;
   cardCharts.push(compareChart('Total points',[['GOING total',m.total_mean],['Book total',total?.total]])+compareChart(`${g.home} margin (positive = home lead)`,[['GOING margin',m.margin_mean],['Book-implied margin',finite(sp?.spread)?-Number(sp.spread):null]]));
   return `<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(date(g.kickoff))}</span><h3>${esc(g.away)} @ ${esc(g.home)}</h3></div>${pill(fresh?'Current odds':'Saved / stale odds',fresh?'good':'watch')}</div><div class="gcs-metrics">${metric('GOING margin',modelMargin,`${m.home_n??'—'} home / ${m.away_n??'—'} away sample`)}${metric('GOING total',modelTotal,'Model mean · not sportsbook line')}${metric('Home spread',homeLine,sp?`${esc(sp.book||'Book unavailable')} · ${odds(sp.homeSpreadOdds)}`:'No matched price')}${metric('Game total',totalLine,total?`${esc(total.book||'Book unavailable')} · O ${odds(total.overOdds)} / U ${odds(total.underOdds)}`:'No matched price')}</div><div class="gcs-card-price"><b>${g.quotes.length} quote rows · ${bookCount} book${bookCount===1?'':'s'}</b><span>${ml?`${esc(ml.book||'')} · ML ${esc(g.home)} ${odds(ml.mlHome)} / ${esc(g.away)} ${odds(ml.mlAway)}`:'Moneyline quote unavailable'}</span></div><details><summary>Show the data and book lines</summary><div class="gcs-evidence"><span>GOING home win probability ${pct(m.home_wp)}</span><span>Mean margin ${modelMargin}</span><span>Mean total ${modelTotal}</span><span>Model sample ${m.home_n??'—'} home games / ${m.away_n??'—'} away games</span>${m.confidence?`<span>Projection confidence ${esc(m.confidence)}</span>`:''}</div><div class="gcs-price-list">${g.quotes.map(q=>`<div><b>${esc(q.book||'Book unavailable')}</b><span>Spread ${finite(q.spread)?`${q.spread>0?'+':''}${num(q.spread,1)} (${odds(q.homeSpreadOdds)}) · ${d.currentGameMarket?.(q,'spreads')===false?'stale':'current'}`:'—'} · Total ${finite(q.total)?`${num(q.total,1)} O ${odds(q.overOdds)} / U ${odds(q.underOdds)} · ${d.currentGameMarket?.(q,'totals')===false?'stale':'current'}`:'—'} · ML ${odds(q.mlHome)} / ${odds(q.mlAway)} · ${d.currentGameMarket?.(q,'h2h')===false?'stale':'current'} · ${esc(date(q.updatedAt))}</span></div>`).join('')}</div><small>Model projections, observed sportsbook prices and sample sizes remain separate. No price is called current unless its freshness check passes.</small></details></article>`;
  }).join('')||empty('No current game lines match this team, book or freshness filter. Open Games for the full slate and off-board fixtures.')}</div>`;
 }
 function statField(market){return MARKET_STATS[market]||null;}
 function historyFor(profile,market,line,d){
  const field=statField(market);if(!field)return {unsupported:true,games:[],wins:0,pushes:0,rate:null};
  let logs=(profile?.games||[]).filter(g=>finite(g[field])&&(!g.date||Date.parse(g.date)<=Date.now()));
  if(profile?.position==='QB'&&['pass_yds','pass_tds','atd'].includes(market))logs=logs.filter(g=>g.verified_start===true);
  if(state.window==='season')logs=logs.filter(g=>Number(g.season)===Number(d.season));
  else if(state.window==='prior')logs=logs.filter(g=>Number(g.season)===Number(d.season)-1);
  logs.sort((a,b)=>Date.parse(a.date||'')-Date.parse(b.date||''));
  if(state.window==='last5')logs=logs.slice(-5);
  let wins=0,pushes=0;for(const g of logs){if(g[field]>line)wins++;else if(g[field]===line)pushes++;}
  const decisive=logs.length-pushes;return {unsupported:false,games:logs,wins,pushes,decisive,rate:decisive?wins/decisive:null};
 }
 function hitRateSheet(d){
  const groups=filterGroups(d).map(g=>{const p=g.offers[0],line=g.market==='atd'?.5:g.line,profile=d.history?.profiles?.[g.profileId],result=historyFor(profile,g.market,line,d);return {...g,_hit:result,_profile:profile};}).filter(g=>g._hit.games.length>=Math.max(0,Number(state.minGames)||0));
  groups.sort((a,b)=>state.sort==='player'?String(a.player).localeCompare(String(b.player)):state.sort==='sample'?b._hit.games.length-a._hit.games.length:(b._hit.rate??-1)-(a._hit.rate??-1));
  return `<p class="gcs-note">Observed result frequency against today’s exact line, calculated from GOING’s appearance-aware player game log. It is not a projection, market probability, or ROI. ${groups.length} lines shown; ties are excluded from the over denominator and displayed separately.</p><div class="gcs-grid">${groups.map(g=>{
   const h=g._hit,profile=g._profile,field=statField(g.market),line=g.market==='atd'?.5:g.line,offer=g.offers.slice().sort((a,b)=>Number(b.overOdds??-Infinity)-Number(a.overOdds??-Infinity))[0],rate=pct(h.rate),years=state.window==='season'?`${d.season} season`:state.window==='prior'?`${Number(d.season)-1} season`:'last 5 recorded games';
   const msg=h.unsupported?`No player-game outcome field is published for ${label(g.market)}; first-TD outcomes are game-level.`:!h.decisive?'No decisive logged games for this line and window.':`${h.wins} over hits in ${h.decisive} decisive ${h.decisive===1?'game':'games'}${h.pushes?` · ${h.pushes} push${h.pushes===1?'':'es'} excluded`:''}.`;
   cardCharts.push(historyChart(h.games,field,line));
   cardMini.push(h.games.length?`<div class="gcs-mini-log"><small>Latest recorded outcomes · line ${esc(num(line,1))}</small><div>${h.games.slice(-5).map(x=>{const status=x[field]>line?'over':x[field]===line?'push':'under';return `<span class="${status}" title="${esc(x.date||`${x.season} week ${x.week}`)} · ${status}"><small>${esc(x.week?`W${x.week}`:String(x.date||'').slice(5,10))}</small><b>${esc(num(x[field],1))}</b><small>${status}</small></span>`;}).join('')}</div></div>`:'');
   return `<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(label(g.market))} · ${esc(g.team||'')} vs ${esc(g.opp||'')}</span><h3>${esc(g.player||'Player unavailable')}</h3><small>${years} · current line ${num(line,1)} · ${esc(offer?.book||'Book unavailable')} ${esc(odds(offer?.overOdds))}</small></div>${pill(rate,h.rate!==null?'':'watch')}</div><div class="gcs-metrics">${metric('Observed over rate',rate,`${h.wins} hits / ${h.decisive||0} decisive`)}${metric('Logged games',String(h.games.length),profile?.position==='QB'?'Verified starts only for pass markets':'Appearances with a recorded outcome')}${metric('Pushes',String(h.pushes||0),'Not counted as over hits')}${metric('Historical average',field&&h.games.length?num(h.games.reduce((s,x)=>s+Number(x[field]),0)/h.games.length,1):'—',field||'Outcome not supported')}</div><p class="gcs-note">${esc(msg)} A changing role, opponent and game script can make prior-game frequencies poor forecasts.</p><details><summary>Show the data</summary><div class="gcs-evidence">${h.games.map(x=>`<span>${esc(x.date||`${x.season} week ${x.week}`)} · ${esc(x.season)} · ${num(x[field],1)} ${x[field]>line?'over':x[field]===line?'push':'under'} ${num(line,1)}</span>`).join('')||'<span>No eligible log rows in this window.</span>'}</div><small>Historical box-score outcomes · ${esc(d.history?.sources?.nflverse||d.history?.sources?.pbp||'source lineage recorded in model snapshot')}.</small></details></article>`;
  }).join('')||empty('No current prices and matched player outcomes meet this hit-rate filter.')}</div>`;
 }
 function roleFeature(d,p){const scope=currentScope(d),id=p.player_id||p.id,feature=d.history?.features?.nfl?.players?.[`${p.team}|${id}`]||null;return feature&&String(feature.last_game||'').startsWith(String(d.season))?feature:null;}
 function roleSheet(d){
  let rows=playersFor(d).filter(p=>matchFilter(`${p.name} ${p.team} ${p.position} ${p.share_type}`,p.team,p.position));
  rows.sort((a,b)=>{const x=state.sort==='rush_share'?a.rush_share:state.sort==='share'?a.share:state.sort==='games'?a.games:a.target_share,y=state.sort==='rush_share'?b.rush_share:state.sort==='share'?b.share:state.sort==='games'?b.games:b.target_share;return (Number(y)||-1)-(Number(x)||-1);});
  const scope=currentScope(d);
  return `<p class="gcs-note">${rows.length} players with a current-season usage row. Snap share keeps its source type visible; charted routes appear only where the feed measured them. Sample size and data-through date are shown per player.</p><div class="gcs-grid">${rows.map(p=>{
    const f=roleFeature(d,p),snapLabel=/proxy/i.test(p.share_type||'')?'Passing-snap proxy':p.share_type==='offensive_snap_share'?'Offensive snap share':'Snap share · type unavailable',team=scope.teams?.[p.team],opp=(d.schedule||[]).find(g=>g.home===p.team||g.away===p.team),opponent=opp?(opp.home===p.team?opp.away:opp.home):'';
   const cards=[metric('Target share',pct(p.target_share),`${p.targets??0} targets`),metric('Rush share',pct(p.rush_share),`${p.rush_attempts??0} carries`),metric(snapLabel,pct(p.share),`${p.games??0} games`),metric('Route participation',f?pct(f.route_participation):'Unavailable',f?`${f.participation_charted_dropbacks??0} charted dropbacks`:'No measured route participation')];
   if(f?.shares)cards.push(metric('Red-zone target share',pct(f.shares.red_zone_targets),`${f.last_game||'current snapshot'} · ${f.red_zone_targets??'count unavailable'} targets`));
   if(f?.shares)cards.push(metric('Goal-line carry share',pct(f.shares.goal_line_carries),`${f.last_game||'current snapshot'}`));
   cardCharts.push(compareChart('Share of team opportunities',[['Targets',finite(p.target_share)?p.target_share*100:null],['Carries',finite(p.rush_share)?p.rush_share*100:null],[snapLabel,finite(p.share)?p.share*100:null],['Measured routes',finite(f?.route_participation)?f.route_participation*100:null]],'%'));
   return `<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(p.team)} · ${esc(p.position)}${opponent?` · vs ${esc(opponent)}`:''}</span><h3>${esc(p.name||'Player unavailable')}</h3><small>${p.games??0} current-season games · last observed ${esc(p.last_game||scope.teams?.[p.team]?.last_game||'unavailable')}</small></div>${p.opportunity_flag?pill('Usage flag','good'):pill('Role evidence','')}</div><div class="gcs-metrics">${cards.join('')}</div><details><summary>Usage definitions and sample</summary><div class="gcs-evidence"><span>Offensive snaps ${p.offense_snaps??'—'} / team snaps ${p.team_snaps??'—'} · ${esc(p.share_type||'share type unavailable')}</span><span>Targets ${p.targets??'—'} · carries ${p.rush_attempts??'—'} · routes ${finite(p.routes)?p.routes:'not charted'}</span><span>Target / rush shares use team totals from current-season play-by-play.</span><span>Team sample: ${team?.games??'unavailable'} games · ${team?.last_game||'date unavailable'}</span>${f?`<span>Charting coverage ${pct(f.charting_coverage)} · charted dropbacks ${f.participation_charted_dropbacks??0}</span>`:''}</div></details></article>`;
  }).join('')||empty('No current-season player-role records meet these filters.')}</div>`;
 }
 function weaknessStats(block){
  if(!block)return '<span>Not available</span>';
  const items=[['Sample',block.sample],['Games',block.games],['Yards / opportunity',block.yards_per_opportunity],['Explosive rate',finite(block.explosive_rate)?pct(block.explosive_rate):null],['Red-zone rate',finite(block.redzone_rate)?pct(block.redzone_rate):null]];
  return items.filter(([,v])=>finite(v)||typeof v==='string').map(([k,v])=>`<span>${esc(k)} · ${esc(typeof v==='string'?v:k.endsWith('rate')?v:num(v,1))}</span>`).join('')||'<span>Raw metric detail unavailable</span>';
 }
 function roleMatchupSheet(d){
  let rows=(d.learning?.matchup_signals||[]).filter(r=>matchFilter(`${r.player} ${r.team} ${r.opponent} ${r.role} ${r.status} ${r.plain_language}`,r.team,roleName(r.role)));
  if(state.activeOnly)rows=rows.filter(r=>r.active_signal);
  rows.sort((a,b)=>state.sort==='player'?String(a.player).localeCompare(String(b.player)):Number(Boolean(b.active_signal))-Number(Boolean(a.active_signal))||(String(a.status).localeCompare(String(b.status))));
  const weaknessMap=new Map((d.learning?.defensive_weaknesses||[]).map(w=>[w.id,w]));
  return `<p class="gcs-note">${rows.length} player-to-defense role records. “Active” means the existing GOING activation rule passed; watch/uncertain records remain visible but are not treated as bets.</p><div class="gcs-controls"><button type="button" class="gcs-filter-toggle" data-cheat-active aria-pressed="${state.activeOnly}">${state.activeOnly?'✓ Active signals only':'Show active and watch signals'}</button></div><div class="gcs-grid">${rows.map(r=>{
   const w=weaknessMap.get(r.weakness_id),h=w?.historical,c=w?.current,weights=w?.weights,active=Boolean(r.active_signal),u=r.usage||{};
   cardCharts.push(compareChart('Defense yards allowed per opportunity',[[`${h?.season||'Historical'} baseline`,h?.yards_per_opportunity],[`${c?.season||d.season} observed`,c?.yards_per_opportunity]]));
   return `<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(roleName(r.role))} · ${esc(r.team)} vs ${esc(r.opponent)} · ${esc(date(r.kickoff))}</span><h3>${esc(r.player||'Player unavailable')}</h3></div>${pill(active?'Active GOING signal':cap(r.status||w?.current_status||'Watch'),active?'good':'watch')}</div><p>${esc(r.plain_language||'No plain-language explanation was published for this matchup.')}</p><div class="gcs-metrics">${metric('Current usage',pct(u.share),`${u.opportunities??0} role opportunities · ${u.games??0} games`)}${metric('Snap share',pct(u.snap_share),u.snap_share_type||'Type unavailable')}${metric('2025 baseline',h?`${num(h.yards_per_opportunity,1)} yds / opp`:'Unavailable',h?`${h.sample??0} opportunities · ${h.games??0} games`:'No matched weakness record')}${metric('2026 observation',c?`${num(c.yards_per_opportunity,1)} yds / opp`:'Unavailable',c?`${c.sample??0} opportunities · ${c.games??0} games`:'No current record')}</div><details><summary>Show the data</summary><div class="gcs-evidence"><b>2025 historical baseline</b>${weaknessStats(h)}<b>${esc(String(c?.season||d.season||'Current'))} current observations</b>${weaknessStats(c)}${weights?`<span>Historical weight ${pct(weights.historical_weight)} · current weight ${pct(weights.current_weight)} · effective historical sample ${num(weights.historical_effective_sample,1)}</span>`:''}<span>Status ${esc(w?.current_status||r.status||'uncertain')} · confidence ${esc(w?.confidence||r.confidence||'unavailable')}</span>${w?.opponent_adjustment?`<span>Opponent adjustment: ${esc(w.opponent_adjustment)}</span>`:''}${w?.structural_change?`<span>Verified structural change: ${w.structural_change.verified?'yes':'no'}${w.structural_change.source?` · ${esc(w.structural_change.source)}`:''}</span>`:''}${(r.lineage||w?.lineage||[]).map(x=>`<span>Source path · ${esc(x)}</span>`).join('')}</div><small>Historical weakness is not a stand-alone bet. The player’s current role must match; the status reflects multiple observations and uncertainty, not a single-game swing.</small></details></article>`;
  }).join('')||empty('No role-matched defensive observations are published for this slate.')}</div>`;
 }
 function coverageSheet(d){
  let rows=(d.learning?.coverage_matchup_signals||[]).filter(r=>matchFilter(`${r.qb} ${r.player||''} ${r.team} ${r.opponent} ${r.role} ${r.coverage_tendency?.shell} ${r.plain_language}`,r.team,roleName(r.role)));
  if(state.activeOnly)rows=rows.filter(r=>r.active_signal);
  rows.sort((a,b)=>Number(Boolean(b.active_signal))-Number(Boolean(a.active_signal))||(Number(b.coverage_tendency?.rate_lift)||-1)-(Number(a.coverage_tendency?.rate_lift)||-1));
  return `<p class="gcs-note">Coverage tendencies are conditional on the projected game-state bucket. They describe prior charted behavior, not a claim that a defense will call that coverage on a particular snap. Inactive records are watch-only.</p><div class="gcs-controls"><button type="button" class="gcs-filter-toggle" data-cheat-active aria-pressed="${state.activeOnly}">${state.activeOnly?'✓ Active signals only':'Show active and watch signals'}</button></div><div class="gcs-grid">${rows.map(r=>{
   const ct=r.coverage_tendency||{},qt=r.qb_tendency||{},weak=r.defense_role_weakness||{},stateName=r.projected_game_state?.bucket||'state unavailable',margin=r.projected_game_state?.defense_margin;
   cardCharts.push(compareChart('Defense coverage frequency',[['Projected score state',finite(ct.rate)?ct.rate*100:null],['All score states',finite(ct.overall_rate)?ct.overall_rate*100:null]],'%')+compareChart('QB role target frequency',[['Against this shell',finite(qt.target_rate)?qt.target_rate*100:null],['All coverages',finite(qt.overall_target_rate)?qt.overall_target_rate*100:null]],'%'));
   return `<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(r.team)} vs ${esc(r.opponent)} · ${esc(roleName(r.role))} · ${esc(date(r.kickoff))}</span><h3>${esc(ct.shell||'Coverage')} in ${esc(stateName)}</h3></div>${pill(r.active_signal?'Active conditional fit':'Watch · not promoted',r.active_signal?'good':'watch')}</div><p>${esc(r.plain_language||'No published explanation.')}</p><div class="gcs-metrics">${metric('Coverage rate',pct(ct.rate),`${ct.plays??0} charted plays · ${ct.state_games??0} games`)}${metric('Score-state dropbacks',String(ct.state_dropbacks??'—'),finite(margin)?`Projected margin ${Number(margin)>0?'+':''}${num(margin,1)}`:'Projection unavailable')}${metric('QB target rate vs shell',pct(qt.target_rate),`${qt.targets??0} targets / ${qt.dropbacks??0} dropbacks`)}${metric('Role weakness status',cap(weak.status||'unavailable'),`${cap(weak.confidence||'confidence unavailable')} · ${r.coverage_role_results?.targets??0} role targets in results sample`)}</div><details><summary>Show the coverage evidence</summary><div class="gcs-evidence"><span>Defense tendency season ${ct.season??'—'} · ${pct(ct.rate)} in ${esc(stateName)} vs ${pct(ct.overall_rate)} overall · ${ct.plays??0} observed plays across ${ct.state_games??0} games.</span><span>QB split season ${qt.season??'—'} · ${esc(qt.position||roleName(r.role))} target rate ${pct(qt.target_rate)} vs ${pct(qt.overall_target_rate)} overall · ${qt.targets??0} targets / ${qt.dropbacks??0} dropbacks in ${qt.games??0} games.</span><span>Role outcome sample: ${r.coverage_role_results?.targets??0} targets · ${r.coverage_role_results?.games??0} games · ${num(r.coverage_role_results?.yards_per_target,1)} yards / target.</span>${(r.beneficiaries||[]).map(p=>`<span>Current role match · ${esc(p.player)} · ${p.targets??0} targets · ${pct(p.target_share)} team target share.</span>`).join('')}${(r.lineage||[]).map(x=>`<span>Source path · ${esc(x)}</span>`).join('')}</div><small>The current game-state estimate and historical shell/QB samples remain separate inputs. This conditional signal is not treated as a forecast of exact coverage or an automatic bet.</small></details></article>`;
  }).join('')||empty('No conditional coverage records are published for the selected team or search.')}</div>`;
 }
 function upcomingGames(d){return (d.schedule||[]).filter(g=>g.home&&g.away).slice().sort((a,b)=>Date.parse(a.kickoff)-Date.parse(b.kickoff));}
 function teamBox(d,team,opp){
  const scope=currentScope(d),t=scope.teams?.[team]||{},wr=scope.defense_receiving?.[`${opp}|WR`],te=scope.defense_receiving?.[`${opp}|TE`],rb=scope.defense_receiving?.[`${opp}|RB`],rush=scope.defense_rushing?.[`${opp}|RB`],qbRush=scope.defense_rushing?.[`${opp}|QB`];
  const tendencies=[['Plays / game',finite(t.plays_per_game)?num(t.plays_per_game,1):'—'],['Seconds / play',finite(t.pace_seconds)?num(t.pace_seconds,1):'—'],['Pass rate over expected',finite(t.pass_over_expected)?pct(t.pass_over_expected):'—'],['Opening-drive pass rate',pct(t.opening_pass_rate)],['11 personnel share',pct(t.personnel_11_share)],['RB target share',pct(t.rb_target_share)],['TE target share',pct(t.te_target_share)]];
  const defense=[['WR',wr,'targets','yards_per_target'],['TE',te,'targets','yards_per_target'],['RB rec',rb,'targets','yards_per_target'],['RB rush',rush,'carries','yards_per_carry'],['QB rush',qbRush,'carries','yards_per_carry']];
  return `<div class="gcs-team-side"><div class="gcs-team-title"><b>${esc(team)}</b><span>${esc(d.season||'')} · ${t.games??0} games</span></div><div class="gcs-team-stats">${tendencies.map(([k,v])=>`<span>${esc(k)} <b>${esc(v)}</b></span>`).join('')}</div><div class="gcs-defense-lines"><small>Opponent defense · ${esc(opp)}</small>${defense.map(([role,r,nKey,yKey])=>r?`<div><b>${esc(role)}</b><span>${r[nKey]??0} opps · ${r.explosives??0} explosives (${pct(r.explosive_rate)}) · ${num(r[yKey],1)} yds / opp · RZ ${pct(r.redzone_target_rate??r.redzone_carry_rate)} · ${r.games??0} games · ${esc(r.status||'status unavailable')}</span></div>`:`<div><b>${esc(role)}</b><span>Current-season sample unavailable</span></div>`).join('')}</div></div>`;
 }
 function teamSheet(d){
  const games=upcomingGames(d).filter(g=>(state.team==='ALL'||g.home===state.team||g.away===state.team)&&matchesQuery(`${g.home} ${g.away}`));
  return `<p class="gcs-note">Team usage and defense allowed are actual current-season aggregates. Receiving/rushing explosive and red-zone rates include observed opportunity counts and games; early-season samples are small and are not adjusted into player projections here.</p><div class="gcs-game-list">${games.map(g=>`<article class="gcs-game-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(date(g.kickoff))}</span><h3>${esc(g.away)} @ ${esc(g.home)}</h3></div>${pill('Current-season data','')}</div><div class="gcs-team-grid">${teamBox(d,g.away,g.home)}${teamBox(d,g.home,g.away)}</div></article>`).join('')||empty('No upcoming games match this team filter, or current schedule data are unavailable.')}</div>`;
 }
 function defenseRows(d){
  const scope=currentScope(d),inSlate=new Set(upcomingGames(d).flatMap(g=>[g.home,g.away]));let rows=[];
  for(const [key,v] of Object.entries(scope.defense_receiving||{})){const [team,role]=key.split('|');if(!inSlate.has(team))continue;rows.push({team,role,kind:'Receiving',opportunities:v.targets,explosives:v.explosives,rate:v.explosive_rate,yards:v.yards_per_target,redzone:v.redzone_target_rate,games:v.games,status:v.status,depth:v.depth});}
  for(const [key,v] of Object.entries(scope.defense_rushing||{})){const [team,role]=key.split('|');if(!inSlate.has(team))continue;rows.push({team,role,kind:'Rushing',opportunities:v.carries,explosives:v.explosives,rate:v.explosive_rate,yards:v.yards_per_carry,redzone:v.redzone_carry_rate,games:v.games,status:v.status});}
  rows=rows.filter(r=>matchFilter(`${r.team} ${r.role} ${r.kind} ${r.status}`,r.team,r.role));
  const key=state.sort;rows.sort((a,b)=>{const x=key==='sample'?a.opportunities:key==='yards_per_opportunity'?a.yards:key==='redzone_rate'?a.redzone:a.rate,y=key==='sample'?b.opportunities:key==='yards_per_opportunity'?b.yards:key==='redzone_rate'?b.redzone:b.rate;return (Number(y)||-1)-(Number(x)||-1);});return rows;
 }
 function defenseSheet(d){
  const rows=defenseRows(d);
  cardCharts=rows.map(r=>compareChart('Observed opportunity rates',[['Explosive plays',finite(r.rate)?r.rate*100:null],['Red-zone usage',finite(r.redzone)?r.redzone*100:null]],'%'));
  return `<p class="gcs-note">Current defenses against each position in this week's slate. Explosive play = the source's play-level definition; receiving uses targets and rushing uses carries. This is the defense's observed rate allowed, not an individual player's explosive rate.</p><div class="gcs-grid">${rows.map(r=>`<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(r.team)} defense · ${esc(r.kind)}</span><h3>${esc(r.role)} allowed</h3></div>${pill(r.status||'Observed',r.status==='observed'?'good':'watch')}</div><div class="gcs-metrics">${metric('Opportunities',String(r.opportunities??0),`${r.games??0} games`)}${metric('Explosives allowed',String(r.explosives??0),`${pct(r.rate)} of ${r.kind==='Receiving'?'targets':'carries'}`)}${metric('Yards / opportunity',num(r.yards,1),r.kind==='Receiving'?'Yards per target':'Yards per carry')}${metric('Red-zone rate',pct(r.redzone),r.kind==='Receiving'?'Targets in red zone / targets':'Carries in red zone / carries')}</div>${r.depth?`<details><summary>Show receiving depth split</summary><div class="gcs-evidence">${Object.entries(r.depth).map(([depth,v])=>`<span>${esc(cap(depth))} · ${v.targets??0} targets · ${num(v.yards_per_target,1)} yards / target</span>`).join('')}</div></details>`:''}<p class="gcs-note">Sample status: ${esc(r.status||'unreported')}. Do not read a small early-season rate as a stable defensive trait.</p></article>`).join('')||empty('No current-season opponent defensive play-type data are available for this slate.')}</div>`;
 }
 function oddsSheet(d){
  const implied=price=>{if(!finite(price)||Number(price)===0)return null;const n=Number(price);return n>0?100/(n+100):Math.abs(n)/(Math.abs(n)+100);};
  const rows=filterGroups(d).map(g=>{const offers=g.offers,over=offers.filter(p=>finite(p.overOdds)).map(p=>Number(p.overOdds)),under=offers.filter(p=>finite(p.underOdds)).map(p=>Number(p.underOdds)),range=values=>{const p=values.map(implied).filter(finite);return p.length?Math.max(...p)-Math.min(...p):0;},bookCount=new Set(offers.map(p=>p.bookKey||p.book).filter(Boolean)).size;return {...g,bookCount,gap:Math.max(range(over),range(under)),overMin:over.length?Math.min(...over):null,overMax:over.length?Math.max(...over):null,underMin:under.length?Math.min(...under):null,underMax:under.length?Math.max(...under):null};}).filter(g=>g.bookCount>=2);
  rows.sort((a,b)=>state.sort==='player'?String(a.player).localeCompare(String(b.player)):state.sort==='books'?b.bookCount-a.bookCount:b.gap-a.gap);
  return `<p class="gcs-note">Same player, game, market and exact line only. An odds range is a price-disagreement indicator—not a devigged edge, probability, or ROI. Choose “All books” to compare books.</p><div class="gcs-grid">${rows.map(g=>`<article class="gcs-card"><div class="gcs-card-top"><div><span class="gcs-kicker">${esc(label(g.market))} · ${esc(g.team||'')} vs ${esc(g.opp||'')}</span><h3>${esc(g.player)} · ${num(g.line,1)}</h3><small>${esc(date(g.kickoff))}</small></div>${pill(`${g.bookCount} books`,'')}</div><div class="gcs-metrics">${metric('Over price range',g.overMin==null?'Unavailable':`${odds(g.overMin)} to ${odds(g.overMax)}`,`${g.offers.filter(p=>finite(p.overOdds)).length} observed offers`)}${metric('Under price range',g.underMin==null?'Unavailable':`${odds(g.underMin)} to ${odds(g.underMax)}`,`${g.offers.filter(p=>finite(p.underOdds)).length} observed offers`)}${metric('Best over',odds(Math.max(...g.offers.filter(p=>finite(p.overOdds)).map(p=>Number(p.overOdds)), -Infinity)),'Current matching line')}${metric('Best under',odds(Math.max(...g.offers.filter(p=>finite(p.underOdds)).map(p=>Number(p.underOdds)), -Infinity)),'Current matching line')}</div><details><summary>Show book-by-book prices</summary><div class="gcs-price-list">${g.offers.map(p=>`<div><b>${esc(p.book||'Book unavailable')}</b><span>Over ${esc(odds(p.overOdds))} · Under ${esc(odds(p.underOdds))} · ${esc(date(p.updatedAt))} · ${quoteIsFresh(d,p)?'current':'saved / stale'}</span></div>`).join('')}</div></details></article>`).join('')||empty('No exact-line price differences across multiple books meet the selected filters.')}</div>`;
 }
 function contentMarkup(d){
  if(!d.history&&!d.context)return empty('Football research data are still loading. Reopen Cheatsheets after the board finishes loading.');
  if(state.sheet==='markets')return marketsSheet(d);
  if(state.sheet==='game-lines')return gameLinesSheet(d);
  if(state.sheet==='hit-rates')return hitRateSheet(d);
  if(state.sheet==='roles')return roleSheet(d);
  if(state.sheet==='matchups')return roleMatchupSheet(d);
  if(state.sheet==='coverage')return coverageSheet(d);
  if(state.sheet==='teams')return teamSheet(d);
  if(state.sheet==='defense')return defenseSheet(d);
  return oddsSheet(d);
 }
 function organizeCards(host,d){
  const content=host.querySelector('.gcs-content'),cards=[...content.querySelectorAll('.gcs-card')],teams=teamSet(d);
  const note=content.querySelector(':scope > .gcs-note');if(note)host.querySelector('.gcs-method').append(note);
  cards.forEach((card,i)=>{
   if(i>=visibleLimit){card.remove();return;}
   const top=card.querySelector('.gcs-card-top');if(!top)return;
   const row=document.createElement('details');row.className='gcs-row';
   const summary=document.createElement('summary'),identity=top.cloneNode(true),metrics=document.createElement('div');metrics.className='gcs-row-values';
   const matched=teams.filter(team=>new RegExp(`\\b${team}\\b`).test(top.textContent)).slice(0,2);
   if(root.GoingUI?.teamMarks&&matched.length)identity.insertAdjacentHTML('afterbegin',root.GoingUI.teamMarks(matched));
   const primary={defense:[1,2,3],matchups:[0,2,3],'hit-rates':[0,1,3]}[state.sheet]||[0,1,2];
   const allMetrics=[...card.querySelectorAll(':scope > .gcs-metrics > .gcs-metric')];primary.forEach(index=>{if(allMetrics[index])metrics.append(allMetrics[index].cloneNode(true));});
   if(state.sheet==='defense')metrics.classList.add('gcs-rate-notes');
   summary.append(identity,metrics);summary.insertAdjacentHTML('beforeend','<span class="gcs-expand" aria-hidden="true">+</span>');
   if(cardMini[i])summary.insertAdjacentHTML('beforeend',cardMini[i]);
   const body=document.createElement('div');body.className='gcs-row-detail';top.remove();
   if(cardCharts[i])body.insertAdjacentHTML('afterbegin',cardCharts[i]);
   while(card.firstChild)body.append(card.firstChild);
   row.append(summary,body);if(i===0&&['hit-rates','coverage','matchups'].includes(state.sheet))row.open=true;
   card.replaceWith(row);
  });
  const total=cards.length||content.querySelectorAll('.gcs-game-card').length;
  const count=host.querySelector('.gcs-count');if(count)count.textContent=`${total.toLocaleString()} ${['teams','game-lines'].includes(state.sheet)?'games':'rows'} · ${d.season||'Current'} season`;
  if(cards.length>visibleLimit)content.insertAdjacentHTML('beforeend',`<div class="gcs-pagination"><span>Showing ${visibleLimit} of ${cards.length} matching rows</span><button type="button" data-cheat-more>Show 40 more</button></div>`);
 }
 function paint(host,d){
  const active=document.activeElement,keep=active&&host.contains(active)&&active.hasAttribute('data-cheat-filter'),filter=keep?active.dataset.cheatFilter:null,selection=keep&&active.selectionStart;
  cardCharts=[];cardMini=[];
  const sheetName=SHEETS.find(s=>s[0]===state.sheet)?.[1]||'Cheatsheets',content=contentMarkup(d);
  host.innerHTML=`<div class="gcs-page">${navMarkup(d)}<main class="gcs-workspace"><label class="gcs-mobile-nav">Cheatsheets<select data-cheat-select aria-label="Choose a cheatsheet">${GROUPS.map(([group,ids])=>`<optgroup label="${group}">${ids.map(id=>`<option value="${id}" ${state.sheet===id?'selected':''}>${esc(SHEETS.find(s=>s[0]===id)[1])}</option>`).join('')}</optgroup>`).join('')}</select></label><header class="gcs-heading"><div><span class="gcs-kicker">NFL · Cheatsheets</span><h2>${esc(sheetName)}</h2><p>${esc(DESCRIPTIONS[state.sheet])}</p></div><button class="gcs-back" data-cheat-open-tab="best">Today's picks ↗</button></header>${toolbarMarkup(d)}<div class="gcs-results-head"><span class="gcs-count" role="status"></span><button type="button" data-cheat-reset>Reset filters</button></div><div class="gcs-content">${content}</div><details class="gcs-method"><summary>Sources & how to read this sheet</summary><p class="gcs-source">${esc(sourceNote(d))}</p><ul><li>Bars show actual values. Higher does not automatically mean a better bet.</li><li>Historical hit rates are observed results against today's line, not future probabilities.</li><li>Passing-snap proxies and measured routes are labeled separately. Missing data stays unavailable.</li><li>Small samples and watch-only signals retain their original status. Open a row to inspect the full evidence.</li></ul></details></main></div>`;
  organizeCards(host,d);
  if(keep){const next=host.querySelector(`[data-cheat-filter="${filter}"]`);next?.focus();if(next&&typeof next.setSelectionRange==='function'&&selection!=null)try{next.setSelectionRange(selection,selection);}catch{}}
 }
 function wire(host){
  if(host.dataset.gcsWired)return;host.dataset.gcsWired='true';
  host.addEventListener('click',e=>{
   if(e.target.closest('[data-cheat-filters]')){filtersOpen=!filtersOpen;render(host,dataRef,true);return;}
   const more=e.target.closest('[data-cheat-more]');if(more){visibleLimit+=40;render(host,dataRef,true);return;}
   const reset=e.target.closest('[data-cheat-reset]');if(reset){state={...DEFAULT,sheet:state.sheet,sort:SHEET_SORT[state.sheet]};visibleLimit=40;saveState();render(host,dataRef,true);return;}
   const sheet=e.target.closest('[data-cheat-sheet]');if(sheet){state.sheet=sheet.dataset.cheatSheet;state.sort=SHEET_SORT[state.sheet]||'edge';state.position='ALL';state.query='';state.activeOnly=false;visibleLimit=40;saveState();render(host,dataRef,true);host.scrollIntoView?.({block:'start',behavior:'instant'});return;}
   const open=e.target.closest('[data-cheat-open-tab]');if(open){dataRef?.openTab?.(open.dataset.cheatOpenTab);return;}
   const fresh=e.target.closest('[data-cheat-fresh]');if(fresh){state.freshOnly=!state.freshOnly;saveState();render(host,dataRef,true);return;}
   const active=e.target.closest('[data-cheat-active]');if(active){state.activeOnly=!state.activeOnly;saveState();render(host,dataRef,true);}
  });
  host.addEventListener('input',e=>{const field=e.target.closest('[data-cheat-filter="query"]');if(!field)return;state.query=field.value;clearTimeout(paintTimer);paintTimer=setTimeout(()=>{saveState();render(host,dataRef,true);},180);});
  host.addEventListener('change',e=>{if(e.target.matches('[data-cheat-select]')){host.querySelector(`[data-cheat-sheet="${e.target.value}"]`)?.click();return;}const field=e.target.closest('[data-cheat-filter]');if(!field||field.dataset.cheatFilter==='query')return;state[field.dataset.cheatFilter]=field.type==='number'?Math.max(0,Number(field.value)||0):field.value;visibleLimit=40;saveState();render(host,dataRef,true);});
 }
 function sameData(a,b){return a&&b&&a.props===b.props&&a.games===b.games&&a.history===b.history&&a.context===b.context&&a.learning===b.learning&&a.season===b.season&&a.week?.start===b.week?.start&&a.priceStatus===b.priceStatus&&a.quotesUpdated===b.quotesUpdated;}
 function render(host,d,force=false){
  if(!host||!d)return;wire(host);if(d.sport!=='nfl'){host.innerHTML=`<div class="gcs-page">${empty('These play-by-play, role and matchup cheatsheets currently use NFL charting and season data. NCAA markets remain available under Markets and Games.')}</div>`;return;}
  if(!force&&sameData(dataRef,d)&&host.dataset.gcsState===JSON.stringify(state))return;
  dataRef=d;paint(host,d);host.dataset.gcsState=JSON.stringify(state);
 }
 root.GoingFootballCheatsheets={render,sheets:SHEETS.map(([id,label])=>({id,label}))};
})(window);
