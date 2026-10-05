const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const {webcrypto}=require('node:crypto');
const {TextEncoder}=require('node:util');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
function setup(t,before=()=>{}){
 const dom=new JSDOM(read('index.html'),{url:'https://going.test/long/?mode=betting',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,d=w.document;
 w.matchMedia=q=>({matches:!q.includes('max-width'),addEventListener(){},removeEventListener(){}});
 w.HTMLElement.prototype.scrollIntoView=function(){};w.scrollTo=()=>{};
 const shell=d.createElement('header');shell.id='going-shell';shell.innerHTML='<div class="going-shell-inner"><a class="going-wordmark">GOING LONG</a><nav class="going-global-nav"><a href="/">Home</a><a href="/long/">Football</a><a href="/yard/">Baseball</a><a href="/players/">Players</a><a href="/results/">Results</a></nav></div>';d.body.prepend(shell);d.body.dataset.goingWorkspace='long';
 before(w,d);w.eval(read('shared/visual-system.js'));w.eval(read('shared/reference-workspace.js'));
 t.after(()=>w.close());return {w,d};
}
const frame=()=>new Promise(r=>setTimeout(r,45));
async function select(ui,section){ui.d.querySelectorAll('#btTabGroup button[data-section]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.section===section)));await frame();}
test('reference adapters retain the same search/filter controls and preserve query/listeners across tools',async t=>{
 let control,events=0;const ui=setup(t,(w,d)=>{control=d.getElementById('bestSearch');control.value='Saved query';control.addEventListener('input',()=>events++);});
 assert.equal(ui.d.querySelector('.r-search-label input'),control);assert.equal(control.value,'Saved query');control.dispatchEvent(new ui.w.Event('input',{bubbles:true}));assert.equal(events,1);
 const globalQuery=ui.d.getElementById('goingSearch');assert.equal(globalQuery.closest('.going-search').parentElement.className,'v-header-actions');
 await select(ui,'cheatsheets');assert.equal(ui.d.body.dataset.referenceActive,'false');assert.equal(globalQuery.closest('.going-search').parentElement.className,'bt-wrap');
 await select(ui,'score');assert.equal(ui.d.querySelector('.v-score-context #goingSearch'),globalQuery);
 await select(ui,'today');assert.equal(ui.d.querySelector('.r-search-label input'),control);assert.equal(control.value,'Saved query');
 const ids=[...ui.d.querySelectorAll('[id]')].map(e=>e.id);assert.equal(ids.length,new Set(ids).size);
});
test('Best Plays changes presentation only, preserves candidate order and restores Today hero',async t=>{
 const ui=setup(t,(w,d)=>{d.getElementById('bestChance').innerHTML='<article class="g-card" data-original="a">Original A</article><article class="g-card" data-original="b">Original B</article>';});
 const cards=[...ui.d.querySelectorAll('#bestChance>article')],sort=ui.d.getElementById('bestSort');sort.value='payout';
 ui.d.querySelector('[data-reference-view="plays"]').click();assert.equal(ui.d.body.dataset.referenceView,'plays');assert.match(ui.d.querySelector('.v-football-hero').textContent,/BEST PLAYS/);assert.equal(ui.d.querySelector('.r-ranked-lists').open,true);assert.equal(new URL(ui.w.location.href).searchParams.get('view'),'plays');
 assert.deepEqual([...ui.d.querySelectorAll('#bestChance>article')],cards);assert.equal(sort.value,'payout');
 ui.d.querySelector('[data-reference-view="games"]').click();assert.match(ui.d.querySelector('.v-football-hero').textContent,/NFL TODAY/);assert.equal(ui.d.body.dataset.referenceView,'default');assert.equal(new URL(ui.w.location.href).searchParams.has('view'),false);
});
test('Best Plays facts and expandable risk keep the original values and delegated action',async t=>{
 let clicks=0;const ui=setup(t,(w,d)=>{d.getElementById('bestChance').innerHTML='<article class="g-card"><div class="g-bet-head"><h3>Synthetic fixture</h3><span class="g-price">+120</span></div><p><strong>Why</strong> · Synthetic evidence</p><p class="g-warning">Exact original availability concern</p><details><summary>Show me the data</summary><dl class="best-evidence"><dt>Projection average</dt><dd>42.1</dd><dt>Model probability</dt><dd>51.0%</dd><dt>Price</dt><dd>+120</dd><dt>Estimated return</dt><dd>+12.2¢ per $1</dd></dl></details><div class="g-actions"><button data-going-pick="fixture">Original action</button></div></article>';d.getElementById('bestChance').addEventListener('click',e=>{if(e.target.closest('[data-going-pick]'))clicks++;});});
 const values=[...ui.d.querySelectorAll('.r-play-facts b')].map(e=>e.textContent);assert.deepEqual(values,['42.1','51.0%','+120','+12.2¢ per $1']);assert.match(ui.d.querySelector('.r-play-risk').textContent,/Exact original availability concern/);ui.d.querySelector('[data-going-pick]').click();assert.equal(clicks,1);assert.equal(ui.d.querySelectorAll('.g-price').length,1);
});

test('Games selection uses unchanged rendered quotes and original compare dialog delegate; period rows stay available',async t=>{
 let comparisons=[];const ui=setup(t,(w,d)=>{d.getElementById('btGamesList').innerHTML=[0,1].map(i=>`<article class="bt-game"><button data-compare="${i}" class="bt-game-summary"><span class="bt-game-head"><b>Fixture away ${i} @ Fixture home ${i}</b><span class="bt-coverage">2 Books</span></span><time>Future fixture</time><span class="bt-best-grid"><span><b>+${i+2}.5</b><small>Spread</small></span></span><span class="bt-compare-hint"><strong>Unvalidated fixture estimate</strong></span></button></article>`).join('');d.getElementById('btGamesList').addEventListener('click',e=>{const b=e.target.closest('[data-compare]');if(b)comparisons.push(b.dataset.compare);});});
 await select(ui,'games');ui.d.querySelector('[data-reference-game="1"]').click();assert.match(ui.d.querySelector('.r-selected-game').textContent,/Fixture away 1/);assert.match(ui.d.querySelector('.r-selected-game .bt-best-grid').textContent,/\+3.5/);ui.d.querySelector('[data-reference-compare]').click();assert.deepEqual(comparisons,['1']);
 assert.ok(ui.d.getElementById('btGamesList').closest('details'));ui.d.getElementById('btGamesList').innerHTML='<article class="bt-game"><h3>Actual period fixture</h3><table><tr><td>Existing period price</td></tr></table></article>';await frame();assert.equal(ui.d.querySelector('.r-games-workspace').hidden,true);assert.equal(ui.d.querySelector('.r-original-games').open,true);
 await select(ui,'props');assert.equal(ui.d.getElementById('btPeriodGroup').parentElement.className,'bt-wrap');assert.equal(ui.d.querySelectorAll('#btOverview .r-stat-icon').length,0);
});
test('Jackpot reproduces the existing first-TD eligibility/order and never manufactures a combined estimate',async t=>{
 const future=new Date(Date.now()+86400000).toISOString();const ui=setup(t,w=>{w.inCurrentFootballWeek=()=>true;w.americanOddsLabel=n=>String(n);w.BET={history:{derivatives:{first_td:{fixture:{status:'ready',kickoff:future,away:'AWAY',home:'HOME',outcomes:{a:{player_id:'a',name:'Synthetic scorer A',team:'AWAY',probability:.12,fair_odds:733},b:{player_id:'b',name:'Synthetic scorer B',team:'HOME',probability:.2,fair_odds:400},invalid:{name:'Unknown',probability:.5}}}}}}};});
 await select(ui,'jackpot');const rows=ui.d.querySelectorAll('.r-jackpot-players tbody tr');assert.equal(rows.length,2);assert.match(rows[0].textContent,/Synthetic scorer B/);assert.match(rows[0].textContent,/20.0%/);assert.match(ui.d.querySelector('.r-jackpot-players').textContent,/not a combined jackpot probability/);assert.ok(ui.d.getElementById('slateBreaker').closest('.r-jackpot-offers'));assert.ok(ui.d.getElementById('promoDate'));
 const query=ui.d.getElementById('rJackpotSearch');query.value='scorer A';query.dispatchEvent(new ui.w.Event('input',{bubbles:true}));assert.equal(rows[0].hidden,true);assert.equal(rows[1].hidden,false);query.value='';query.dispatchEvent(new ui.w.Event('input',{bubbles:true}));assert.equal(rows[0].hidden,false);
});
test('DFS native import, confirmation, generation, lock and clear survive workspace moves and rerenders',async t=>{
 const ui=setup(t,w=>{Object.defineProperty(w.crypto,'subtle',{value:webcrypto.subtle});w.TextEncoder=TextEncoder;for(const f of ['shared/dfs-threshold.js','shared/dfs-tournament.js','shared/dfs-classic.js','shared/dfs-classic-ui.js'])w.eval(read(f));
 w.GoingDfsClassicUI.mount(w.document.getElementById('dfsClassicRoot'),{generatedAt:'synthetic fixture',buildPool:rows=>rows.map((p,i)=>({...p,matched:true,unavailable:false,projection:12+i%6,tdMean:p.position==='DST'?0:.3,athleteId:p.id,concerns:['Synthetic fixture only']})),buildScenario:()=>null});});
 await frame();assert.equal(ui.d.querySelectorAll('.r-empty-roster li').length,9);const header='Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame',date=new Date(Date.now()+86400000),stamp=`${String(date.getUTCMonth()+1).padStart(2,'0')}/${String(date.getUTCDate()).padStart(2,'0')}/${date.getUTCFullYear()} 01:00PM ET`;
 let id=1;const rows=[header];for(const [pos,n] of Object.entries({QB:2,RB:4,WR:5,TE:2,DST:2}))for(let i=0;i<n;i++){const name=`Synthetic ${pos} ${i}`,key=id++;rows.push(`${pos},${name} (${key}),${name},${key},${pos==='QB'||pos==='DST'?pos:pos+'/FLEX'},${pos==='DST'?2500:4500},${i%2?'KC@DEN':'BUF@MIA'} ${stamp},${i%2?'KC':'BUF'},10`);}
 ui.d.getElementById('dk-paste').value=rows.join('\n');ui.d.getElementById('dk-load').click();for(let i=0;i<60&&!ui.d.getElementById('dk-confirm');i++)await frame();const confirmed=ui.d.getElementById('dk-confirm');assert.ok(confirmed);confirmed.checked=true;confirmed.dispatchEvent(new ui.w.Event('change',{bubbles:true}));await frame();ui.d.getElementById('dk-best').click();await frame();ui.d.getElementById('dk-generate').click();for(let i=0;i<60&&!ui.d.querySelector('.dk-roster');i++)await frame();
 assert.equal(ui.d.querySelectorAll('.r-dfs-lineup .dk-roster>li').length,9);assert.match(ui.d.querySelector('.r-dfs-lineup .dk-budget').textContent,/\$50,000/);ui.d.getElementById('dk-lock-1').click();await frame();assert.equal(ui.d.getElementById('dk-lock-1').getAttribute('aria-pressed'),'true');ui.d.getElementById('dk-clear').click();await frame();assert.equal(ui.d.querySelectorAll('.r-empty-roster li').length,9);assert.equal(ui.d.querySelectorAll('.r-dfs-workspace').length,1);
});
