const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {webcrypto}=require('node:crypto');
const {TextEncoder}=require('node:util');
const {JSDOM}=require('jsdom');
const ROOT=path.join(__dirname,'..');
const NOW=Date.parse('2026-10-03T17:00:00Z');
// These are deliberately synthetic names/salaries/evidence; this test never represents a real DK slate.
function officialShape(counts={QB:3,RB:7,WR:9,TE:4,DST:3}){
 let id=1;const rows=['Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame'];
 for(const [position,n] of Object.entries(counts))for(let i=0;i<n;i++){
  const name=`Synthetic Fixture ${position} ${i}`,game=i%2?'KC@DEN':'BUF@MIA',ownTeam=i%2?'KC':'BUF',salary=position==='DST'?2500+i*100:4500+i*100;
  rows.push([position,`${name} (${id})`,name,id++,['QB','DST'].includes(position)?position:`${position}/FLEX`,salary,game+' 10/04/2026 01:00PM ET',ownTeam,'10.5'].join(','));
 }
 return rows.join('\n');
}
function enrich(rows){return rows.map((p,i)=>({...p,matched:true,unavailable:false,athleteId:'fixture-'+p.id,projection:10+(i%7),tdMean:p.position==='DST'?0:.2+(i%6)/10,reasons:['Synthetic verified opportunity for construction testing only.'],evidence:['Synthetic fixture evidence.'],concerns:['Synthetic fixture; no real recommendation.']}));}
function mount(t,{buildPool=enrich,loadField,buildScenario=()=>({version:'team-budget-v1',releaseUpdatedAt:'2026-10-03T16:00:00Z',teams:{BUF:{counts:[4,4,4],denominator:20},KC:{counts:[4,4,4],denominator:20}}})}={}){
 const dom=new JSDOM('<main id="fixture"></main>',{url:'https://going.test/',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,scroll=[];
 Object.defineProperty(w.crypto,'subtle',{value:webcrypto.subtle});w.TextEncoder=TextEncoder;
 w.fixtureNow=NOW;w.Date=class extends Date{constructor(...args){super(...(args.length?args:[w.fixtureNow]));}static now(){return w.fixtureNow;}};
 Object.defineProperty(w,'scrollY',{get:()=>240});w.scrollTo=opts=>scroll.push(opts);
 for(const file of ['shared/dfs-threshold.js','shared/dfs-journal.js','shared/dfs-matchup-csv.js','shared/dfs-classic-field.js','shared/dfs-tournament.js','shared/dfs-classic.js','shared/dfs-classic-ui.js'])w.eval(fs.readFileSync(path.join(ROOT,file),'utf8'));
 w.GoingDfsClassicUI.mount(w.document.getElementById('fixture'),{defaultMode:'throne',generatedAt:'2026-10-03T16:00:00Z',injuryAt:'2026-10-03T16:00:00Z',buildPool,buildScenario,loadField});
 t.after(()=>w.close());
 return {w,d:w.document,scroll};
}
function click(ui,selector){const button=ui.d.querySelector(selector);assert.ok(button,selector);button.focus();button.click();}
async function waitFor(check){for(let i=0;i<100;i++){if(check())return;await new Promise(resolve=>setTimeout(resolve,10));}assert.fail('UI async condition timed out.');}
async function load(ui,text=officialShape()){
 ui.d.getElementById('dk-paste').value=text;click(ui,'#dk-load');await waitFor(()=>ui.d.getElementById('dk-confirm')||/invalid|required|rejected/i.test(ui.d.getElementById('dk-status').textContent));
}
function confirm(ui){const input=ui.d.getElementById('dk-confirm');input.checked=true;input.dispatchEvent(new ui.w.Event('change',{bubbles:true}));}
async function generate(ui){click(ui,'#dk-generate');assert.equal(ui.d.getElementById('dk-generate').disabled,true);await waitFor(()=>!ui.d.getElementById('dk-generate').disabled);}
test('historical JSON plus matchup CSV controls actually reach lineup generation and frozen evidence',async t=>{
 let ui;
 const positions=['QB','RB','WR','TE','DST'],model={schema:'going-private-classic-ownership-v1',positions,slot_totals:{QB:100,RB:240,WR:340,TE:120,DST:100},models:{salary_only:Object.fromEntries(positions.map(p=>[p,{features:['s'],beta:[-2]}]))}};
 ui=mount(t,{buildPool:rows=>ui.w.GoingDfsClassicField.annotate(enrich(rows).map(p=>({...p,projectionSource:'dfs-current-season-empirical-v1',projectionSeason:2026}))),loadField:text=>ui.w.GoingDfsClassicField.load(text)});
 assert.equal(ui.d.getElementById('dk-history-own').disabled,true);
 await load(ui);await loadMatchups(ui);confirm(ui);click(ui,'#dk-tournament');
 const input=ui.d.getElementById('dk-field-file');Object.defineProperty(input,'files',{value:[{name:'synthetic.json',text:async()=>JSON.stringify(model)}]});input.dispatchEvent(new ui.w.Event('change',{bubbles:true}));await waitFor(()=>!ui.d.getElementById('dk-history-own').disabled);
 click(ui,'#dk-history-own');await generate(ui);
 assert.equal(ids(ui).length,9);assert.match(ui.d.body.textContent,/Historical ownership influenced this draft/);assert.match(ui.d.body.textContent,/minimum .*2% budget/);
 assert.match(ui.d.body.textContent,/Local opponent positional FPG adjusts/);
 assert.equal(ui.d.querySelectorAll('#dk-history-own').length,1);
 click(ui,'[data-act="freeze"]');
 const receipts=ui.w.GoingDfsJournal.read(ui.w.localStorage).receipts,receipt=receipts.at(-1);
 assert.equal(receipt.researchPolicy.ownership,true);assert.equal(receipt.historicalSelection.source,'imported-historical-classic-ownership');assert.equal(receipt.strategyVersion,'historical-ownership-construction-research-v1');
 assert.match(receipt.historicalSelection.ownershipModelHash,/^[a-f0-9]{64}$/);
 assert.ok(receipt.players.some(p=>p.matchupResearch));
 click(ui,'#dk-generate');assert.equal(ui.d.getElementById('dk-history-own').disabled,true);assert.equal(ui.d.getElementById('dk-field-file').disabled,true);await waitFor(()=>!ui.d.getElementById('dk-generate').disabled);
 assert.equal(ui.d.getElementById('dk-history-own').checked,true);
});
test('ownership upload blocks overlapping mutations and rejects loader errors without damaging the slate',async t=>{
 let release;const pending=new Promise(resolve=>release=resolve),ui=mount(t,{loadField:()=>{throw Error('synthetic failure');}});
 await load(ui);confirm(ui);
 const input=ui.d.getElementById('dk-field-file');Object.defineProperty(input,'files',{value:[{name:'synthetic.json',size:20,text:()=>pending}]});input.dispatchEvent(new ui.w.Event('change',{bubbles:true}));
 assert.equal(ui.d.getElementById('dk-generate').disabled,true);assert.equal(ui.d.getElementById('dk-history-stack').disabled,true);
 release('{}');await waitFor(()=>/Import rejected/.test(ui.d.getElementById('dk-field-status').textContent));
 assert.match(ui.d.getElementById('dk-field-status').textContent,/synthetic failure/);assert.equal(ui.d.getElementById('dk-generate').disabled,false);assert.equal(ui.d.getElementById('dk-confirm').checked,true);
});
function ids(ui){return [...ui.d.querySelectorAll('.dk-roster>li')].map(li=>li.querySelector('[data-act="exclude"]').dataset.id);}
test('actual pasted-import flow gates contest confirmation then generates a valid nine-slot lineup',async t=>{
 const ui=mount(t);assert.equal(ui.d.getElementById('dk-generate').disabled,true);assert.equal(typeof ui.w.Worker,'undefined');
 await load(ui);assert.equal(ui.d.getElementById('dk-generate').disabled,true);assert.match(ui.d.body.textContent,/26 imported players/);assert.match(ui.d.body.textContent,/2 games/);assert.match(ui.d.body.textContent,/File fingerprint [a-f0-9]{16}/);
 confirm(ui);assert.equal(ui.d.getElementById('dk-generate').disabled,false);await generate(ui);
 assert.equal(ids(ui).length,9);assert.equal(new Set(ids(ui)).size,9);assert.deepEqual([...ui.d.querySelectorAll('.dk-slot')].map(n=>n.textContent),['QB','RB','RB','WR','WR','WR','TE','FLEX','DST']);
 assert.match(ui.d.querySelector('.dk-budget').textContent,/\$50,000/);assert.match(ui.d.querySelector('.dk-budget').textContent,/remaining/);assert.match(ui.d.getElementById('dk-status').textContent,/Valid nine-player/);assert.match(ui.d.body.textContent,/not the chance of reaching eight/);
});
test('actual file input uses the same official parser, confirmation and generation gate',async t=>{
 const ui=mount(t),input=ui.d.getElementById('dk-file');Object.defineProperty(input,'files',{value:[{name:'synthetic-fixture.csv',text:async()=>officialShape()}]});input.dispatchEvent(new ui.w.Event('change',{bubbles:true}));await waitFor(()=>ui.d.getElementById('dk-confirm'));assert.equal(ui.d.getElementById('dk-generate').disabled,true);confirm(ui);await generate(ui);assert.equal(ids(ui).length,9);
});

test('Classic salary CSV stays the only direct upload; optional ownership cannot cover it',t=>{
 const ui=mount(t),salary=ui.d.getElementById('dk-file'),ownership=ui.d.getElementById('dk-field-file');
 assert.equal(salary.getAttribute('accept'),'.csv,text/csv');
 assert.equal(salary.closest('label').className,'dk-salary-upload');
 assert.equal(ui.d.querySelectorAll('.dk-import:not(.dk-matchup-import):not(.dk-history-import)>label:not(.dk-confirm)').length,1);
 assert.match(salary.closest('label').textContent,/salary CSV \(\.csv\)/);
 assert.match(ui.d.getElementById(salary.getAttribute('aria-describedby')).textContent,/DKSalaries.csv/);
 const optional=ownership.closest('details');
 assert.equal(optional.className,'dk-ownership-import');assert.equal(optional.open,false);
 assert.match(optional.textContent,/Not required to import salaries or build a lineup/);
 const css=fs.readFileSync(path.join(ROOT,'shared/reference-workspace.css'),'utf8');
 assert.match(css,/\.dk-import>label\.dk-salary-upload\{position:absolute/);
 assert.doesNotMatch(css,/\.dk-import>label:not\(\.dk-confirm\)\{position:absolute/);
 // Presentation adapter selects the first nested disclosure as the paste guide.
 assert.equal(ui.d.querySelector('.dk-import>details button').id,'dk-load');
});

function matchupCsv(w){const at=new Date(w.Date.now()-60000).toISOString().slice(0,16).replace('T',' '),teams='ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' ');return ['TEAM,TEAM,TEAM,TEAM,FP','Rank,Name,POS,G,FP/G',',,,,10',...teams.map((t,i)=>`${i+1},${t},vs. WR,4,20`),`Exported from Data Suite 2.0 on ${at} UTC,,,,`].join('\n');}
async function loadMatchups(ui){const confirmation=ui.d.getElementById('dk-matchup-confirm');confirmation.checked=true;confirmation.dispatchEvent(new ui.w.Event('change',{bubbles:true}));const input=ui.d.getElementById('dk-matchup-files');Object.defineProperty(input,'files',{value:[{name:'fantasy-points-allowed-wr.csv',size:500,text:async()=>matchupCsv(ui.w)}]});input.dispatchEvent(new ui.w.Event('change',{bubbles:true}));await waitFor(()=>/Opponent data loaded/.test(ui.d.getElementById('dk-matchup-status').textContent));}
test('local matchup CSV controls import, persist across refresh and revoke inputs when season confirmation is withdrawn',async t=>{
 const ui=mount(t);assert.equal(ui.d.getElementById('dk-matchup-files').disabled,true);await load(ui);await loadMatchups(ui);
 assert.equal(ui.d.querySelector('.dk-matchup-import').open,true);assert.equal(ui.d.getElementById('dk-matchup-enabled').checked,true);assert.ok(ui.w.localStorage.getItem('going-dfs-matchups-v1'));assert.match(ui.d.body.textContent,/unfitted sensitivity scenario/);
 ui.w.GoingDfsClassicUI.mount(ui.d.getElementById('fixture'),{generatedAt:'2026-10-03T16:00:00Z',injuryAt:'2026-10-03T16:00:00Z',buildPool:enrich});assert.equal(ui.d.getElementById('dk-matchup-enabled').checked,true);
 const checkbox=ui.d.getElementById('dk-matchup-confirm');checkbox.checked=false;checkbox.dispatchEvent(new ui.w.Event('change',{bubbles:true}));assert.equal(ui.w.localStorage.getItem('going-dfs-matchups-v1'),null);assert.equal(ui.d.getElementById('dk-matchup-enabled'),null);assert.equal(ui.d.getElementById('dk-matchup-files').disabled,true);
});
test('matchup inputs cannot change while a lineup build is running',async t=>{
 const ui=mount(t);await load(ui);await loadMatchups(ui);confirm(ui);click(ui,'#dk-generate');
 assert.equal(ui.d.getElementById('dk-matchup-confirm').disabled,true);assert.equal(ui.d.getElementById('dk-matchup-enabled').disabled,true);assert.equal(ui.d.getElementById('dk-matchup-files').disabled,true);
 const enabled=ui.d.getElementById('dk-matchup-enabled');enabled.checked=false;enabled.dispatchEvent(new ui.w.Event('change',{bubbles:true}));await waitFor(()=>!ui.d.getElementById('dk-generate').disabled);assert.equal(ui.d.getElementById('dk-matchup-enabled').checked,true);
});

test('separate optional ownership upload retains its JSON loader and salary slate',async t=>{
 let received;const ui=mount(t,{loadField:text=>{received=text;return {ok:true};}});
 await load(ui);confirm(ui);
 const input=ui.d.getElementById('dk-field-file');
 input.closest('details').open=true;
 Object.defineProperty(input,'files',{value:[{name:'synthetic-ownership.json',text:async()=>'{"fixture":true}'}]});
 input.dispatchEvent(new ui.w.Event('change',{bubbles:true}));
 await waitFor(()=>/Classic ownership model loaded/.test(ui.d.getElementById('dk-field-status').textContent));
 assert.equal(received,'{"fixture":true}');
 assert.equal(ui.d.getElementById('dk-field-file').closest('details').open,true);
 assert.equal(ui.d.getElementById('dk-confirm').checked,true);
 assert.equal(ui.d.getElementById('dk-generate').disabled,false);
 assert.match(ui.d.body.textContent,/26 imported players/);
 assert.equal(ui.d.getElementById('dk-file').getAttribute('accept'),'.csv,text/csv');
});
test('lock, objective switch, rebuild, swap, exclusion and clear work together through real controls',async t=>{
 const ui=mount(t);await load(ui);confirm(ui);await generate(ui);const initial=ids(ui),locked=initial[1];
 click(ui,'#dk-lock-1');assert.equal(ui.d.getElementById('dk-lock-1').getAttribute('aria-pressed'),'true');assert.equal(ui.d.getElementById('dk-swap-1').disabled,true);
 click(ui,'#dk-best');assert.match(ui.d.body.textContent,/Draft initially built for Touchdown Throne/);assert.equal(ui.d.getElementById('dk-best').getAttribute('aria-pressed'),'true');await generate(ui);assert.equal(ids(ui)[1],locked);
 click(ui,'#dk-throne');await generate(ui);assert.equal(ids(ui)[1],locked);
 const beforeSwap=ids(ui);click(ui,'#dk-swap-3');assert.match(ui.d.querySelector('.dk-swap').textContent,/Other eight roster spots stay unchanged/);assert.match(ui.d.querySelector('.dk-swap').textContent,/salary/);assert.match(ui.d.querySelector('.dk-swap').textContent,/points/);assert.match(ui.d.querySelector('.dk-swap').textContent,/TD mean/);
 const alternative=ui.d.querySelector('.dk-swap [data-act="replace"]');assert.ok(alternative);const replacement=alternative.dataset.id;click(ui,'.dk-swap [data-act="replace"]');const afterSwap=ids(ui);assert.equal(ui.d.activeElement.id,'dk-swap-3');assert.equal(afterSwap[3],replacement);assert.equal(ui.d.querySelector('.dk-swap'),null);beforeSwap.forEach((id,i)=>{if(i!==3)assert.equal(afterSwap[i],id);});
 const excluded=afterSwap[4];click(ui,`.dk-roster [data-act="exclude"][data-id="${excluded}"]`);assert.equal(ids(ui).length,0);assert.match(ui.d.getElementById('dk-status').textContent,/Player excluded/);await generate(ui);assert.equal(ids(ui)[1],locked);assert.ok(!ids(ui).includes(excluded));
 click(ui,'#dk-clear');assert.equal(ids(ui).length,0);assert.match(ui.d.getElementById('dk-status').textContent,/locks and exclusions cleared/);assert.equal(ui.d.getElementById('dk-generate').disabled,false);await generate(ui);assert.equal(ids(ui).length,9);assert.equal(ui.d.getElementById('dk-lock-1').getAttribute('aria-pressed'),'false');
});
test('pool lock preserves the selected exact slot, exclusion can be included again and search retains focus',async t=>{
 const ui=mount(t);await load(ui);confirm(ui);
 const first=ui.d.querySelector('#dk-pool-list [data-act="pick"]'),locked=first.dataset.id;click(ui,'#dk-pool-list [data-act="pick"]');await generate(ui);assert.ok(ids(ui).includes(locked));
 const query=ui.d.getElementById('dk-query');query.focus();query.value='Synthetic Fixture WR';query.dispatchEvent(new ui.w.Event('input',{bubbles:true}));assert.equal(ui.d.activeElement.id,'dk-query');assert.ok([...ui.d.querySelectorAll('#dk-pool-list article')].every(a=>/Fixture WR/.test(a.textContent)));
 const excluded=ui.d.querySelector('#dk-pool-list [data-act="exclude"]').dataset.id;click(ui,`#dk-pool-list [data-act="exclude"][data-id="${excluded}"]`);const restore=ui.d.querySelector(`[data-act="include"][data-id="${excluded}"]`);assert.ok(restore);click(ui,`[data-act="include"][data-id="${excluded}"]`);assert.equal(ui.d.querySelector(`[data-act="include"][data-id="${excluded}"]`),null);
});
test('no alternative is communicated while the existing lineup remains intact',async t=>{
 const ui=mount(t);await load(ui,officialShape({QB:1,RB:2,WR:3,TE:2,DST:1}));confirm(ui);await generate(ui);const initial=ids(ui);click(ui,'#dk-swap-0');assert.match(ui.d.querySelector('.dk-swap').textContent,/No eligible alternative fits/);assert.equal(ui.d.querySelector('.dk-swap [data-act="replace"]'),null);assert.deepEqual(ids(ui),initial);click(ui,'.dk-swap [data-act="close"]');assert.equal(ui.d.querySelector('.dk-swap'),null);
});
test('empty eligible pool reports a useful failure and recovers from busy state',async t=>{
 const ui=mount(t,{buildPool:rows=>enrich(rows).map(p=>({...p,unavailable:true}))});await load(ui);confirm(ui);await generate(ui);assert.equal(ids(ui).length,0);assert.match(ui.d.getElementById('dk-status').textContent,/No eligible matched players/);assert.equal(ui.d.getElementById('dk-generate').disabled,false);
});
test('malformed import fails closed and successful reimport clears previous locks/lineup',async t=>{
 const ui=mount(t);await load(ui);confirm(ui);await generate(ui);click(ui,'#dk-lock-0');
 ui.d.getElementById('dk-paste').value='invalid csv';click(ui,'#dk-load');await waitFor(()=>/required headers|No DraftKings salary rows/.test(ui.d.getElementById('dk-status').textContent));assert.equal(ids(ui).length,0);assert.equal(ui.d.getElementById('dk-generate').disabled,true);assert.equal(ui.d.getElementById('dk-confirm'),null);
 await load(ui);confirm(ui);await generate(ui);assert.equal(ui.d.getElementById('dk-lock-0').getAttribute('aria-pressed'),'false');
});
test('busy controls ignore mutations; keyboard focus and scroll survive rebuild and locking',async t=>{
 const ui=mount(t);await load(ui);confirm(ui);await generate(ui);click(ui,'#dk-lock-1');assert.equal(ui.d.activeElement.id,'dk-lock-1');assert.equal(ui.scroll.at(-1).top,240);
 click(ui,'#dk-generate');assert.equal(ui.d.getElementById('dk-generate').disabled,true);ui.d.getElementById('dk-best').click();ui.d.getElementById('dk-clear').click();assert.equal(ui.d.getElementById('dk-throne').getAttribute('aria-pressed'),'true');await waitFor(()=>!ui.d.getElementById('dk-generate').disabled);assert.equal(ids(ui).length,9);assert.equal(ui.d.activeElement.id,'dk-generate');assert.equal(ui.scroll.at(-1).top,240);
});
test('fallback optimizer exceptions report errors and restore generation controls',async t=>{
 const ui=mount(t);await load(ui);confirm(ui);const original=ui.w.GoingDfsClassic.optimize;ui.w.GoingDfsClassic.optimize=()=>{throw Error('Synthetic fixture optimizer failure.');};
 click(ui,'#dk-generate');await waitFor(()=>!ui.d.getElementById('dk-generate').disabled);assert.match(ui.d.getElementById('dk-status').textContent,/Synthetic fixture optimizer failure/);assert.equal(ids(ui).length,0);ui.w.GoingDfsClassic.optimize=original;await generate(ui);assert.equal(ids(ui).length,9);
});
test('pool picking a later-game player fills an unlocked slot and preserves every started incumbent',async t=>{
 let ui;ui=mount(t,{buildPool:(rows,options={})=>enrich(rows).map(p=>{if(Date.parse(p.kickoff)>ui.w.Date.now())return p;const old=options.incumbentLineup?.find(old=>old.id===p.id);return old?{...old,incumbentLocked:true}:{...p,unavailable:true,projection:null};})});const text=officialShape().replaceAll('KC@DEN 10/04/2026 01:00PM ET','KC@DEN 10/04/2026 04:25PM ET');await load(ui,text);confirm(ui);const parsed=ui.w.GoingDfsClassic.parseCsv(text).players,earlyRB=parsed.find(p=>p.position==='RB'&&p.team==='BUF');click(ui,`#dk-pool-list [data-act="pick"][data-id="${earlyRB.id}"]`);await generate(ui);click(ui,'#dk-lock-1');const prior=ids(ui);
 const started=prior.map((id,i)=>({p:parsed.find(p=>p.id===id),i})).filter(({p})=>p.team==='BUF');assert.ok(started.some(({p,i})=>p.position==='RB'&&i===1));
 ui.w.fixtureNow=Date.parse('2026-10-04T18:00:00Z');
 const next=parsed.find(p=>p.position==='RB'&&p.team==='KC'&&!prior.includes(p.id));assert.ok(next);click(ui,`#dk-pool-list [data-act="pick"][data-id="${next.id}"]`);await generate(ui);assert.equal(ids(ui).length,9);assert.ok(ids(ui).includes(next.id));for(const {p,i} of started)assert.equal(ids(ui)[i],p.id);
});
test('NFL index integration loads isolated modules in dependency order and retains advanced DFS',()=>{
 const html=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');assert.match(html,/data-section="dfs" data-tab="dfs"/);assert.match(html,/id="dfsClassicRoot"/);assert.match(html,/id="dfsAdvanced"/);assert.ok(html.indexOf('/shared/dfs-classic.js')<html.indexOf('/shared/dfs-classic-ui.js'));assert.ok(html.indexOf('/shared/dfs-evidence.js')<html.indexOf('/shared/dfs-classic-ui.js'));assert.match(html,/GoingDfsClassicUI\.mount\(\$\('dfsClassicRoot'\)/);
});

test('missing eight-TD evidence fails Throne closed without preventing Best DFS',async t=>{const ui=mount(t,{buildScenario:()=>{throw Error('Synthetic stale team evidence');}});await load(ui);confirm(ui);await generate(ui);assert.equal(ids(ui).length,0);assert.match(ui.d.getElementById('dk-status').textContent,/Synthetic stale team evidence/);click(ui,'#dk-best');await generate(ui);assert.equal(ids(ui).length,9);});
test('Throne UI uses full-lineup threshold scenario and never displays a precise chance',async t=>{const ui=mount(t);await load(ui);confirm(ui);await generate(ui);assert.match(ui.d.body.textContent,/8-TD scenario ready/);assert.match(ui.d.body.textContent,/complete lineup’s experimental eight-TD scenario/);click(ui,'#dk-swap-3');assert.match(ui.d.querySelector('.dk-swap').textContent,/8-TD scenario:/);assert.doesNotMatch(ui.d.body.textContent,/\d+\.\d+% chance/);});

test('overlapping imports cannot mix salary fingerprint with a different slate',async t=>{let unblock;const pending=new Promise(resolve=>unblock=resolve),ui=mount(t,{buildScenario:async()=>{await pending;return {version:'team-budget-v1',teams:{BUF:{counts:[4,4,4],denominator:20},KC:{counts:[4,4,4],denominator:20}}};}});ui.d.getElementById('dk-paste').value=officialShape();click(ui,'#dk-load');await new Promise(resolve=>setTimeout(resolve,20));assert.equal(ui.d.getElementById('dk-generate').disabled,true);ui.d.getElementById('dk-paste').value='invalid second import';ui.d.getElementById('dk-load').click();unblock();await waitFor(()=>ui.d.getElementById('dk-confirm')&&!ui.d.getElementById('dk-load').disabled);assert.match(ui.d.body.textContent,/26 imported players/);confirm(ui);await generate(ui);assert.equal(ids(ui).length,9);});
test('evidence builder exceptions during rebuild report a recoverable failure',async t=>{let broken=false;const ui=mount(t,{buildPool:rows=>{if(broken)throw Error('Synthetic evidence builder failure');return enrich(rows);}});await load(ui);confirm(ui);broken=true;click(ui,'#dk-generate');await waitFor(()=>/Synthetic evidence builder failure/.test(ui.d.getElementById('dk-status').textContent));assert.match(ui.d.getElementById('dk-status').textContent,/Synthetic evidence builder failure/);assert.equal(ui.d.getElementById('dk-generate').disabled,false);broken=false;await generate(ui);assert.equal(ids(ui).length,9);});

test('zero eight-TD scenario support is disclosed instead of pretending the target is backed',async t=>{const ui=mount(t,{buildScenario:()=>({version:'team-budget-v1',teams:{BUF:{counts:[0,0,0],denominator:20},KC:{counts:[0,0,0],denominator:20}}})});await load(ui);confirm(ui);await generate(ui);assert.equal(ids(ui).length,9);assert.match(ui.d.getElementById('dk-status').textContent,/no eight-TD support/);assert.match(ui.d.getElementById('dk-status').textContent,/not treat this as an eight-TD recommendation/);});


test('tournament UI explains construction, unknown leverage and progressively exposes the full pool',async t=>{const ui=mount(t);await load(ui,officialShape({QB:3,RB:16,WR:25,TE:6,DST:4}));confirm(ui);click(ui,'#dk-tournament');await generate(ui);assert.equal(ids(ui).length,9);assert.match(ui.d.body.textContent,/Your tournament thesis/);assert.match(ui.d.body.textContent,/leverage and duplication remain unknown/);assert.equal(ui.d.querySelectorAll('#dk-pool-list article').length,40);click(ui,'[data-act="more-pool"]');assert.equal(ui.d.querySelectorAll('#dk-pool-list article').length,54);});


test('pregame lineup can be frozen without modifying the lineup and exports stay separate from betting journals',async t=>{const ui=mount(t);await load(ui);confirm(ui);click(ui,'#dk-tournament');await generate(ui);const before=ids(ui);click(ui,'[data-act="freeze"]');assert.match(ui.d.getElementById('dk-status').textContent,/Pregame DFS lineup frozen/);assert.deepEqual(ids(ui),before);const r=ui.w.GoingDfsJournal.read(ui.w.localStorage);assert.equal(r.ok,true);assert.equal(r.receipts.length,1);assert.equal(r.receipts[0].mode,'tournament');assert.equal(r.receipts[0].players.length,9);});

test('same-host refresh clears newly unavailable lineups and keeps historical frozen receipts',async t=>{
 let unavailable=false;const buildPool=rows=>enrich(rows).map(p=>({...p,unavailable})),ui=mount(t,{buildPool});
 await load(ui);confirm(ui);click(ui,'#dk-best');await generate(ui);click(ui,'[data-act="freeze"]');
 const before=JSON.stringify(ui.w.GoingDfsJournal.read(ui.w.localStorage).receipts);unavailable=true;
 ui.w.GoingDfsClassicUI.mount(ui.d.getElementById('fixture'),{buildPool});
 assert.equal(ids(ui).length,0);assert.equal(ui.d.querySelector('[data-act="freeze"]').disabled,true);
 assert.match(ui.d.getElementById('dk-status').textContent,/Availability changed/);
 assert.equal(ui.d.querySelectorAll('#dk-pool-list article').length,0);
 assert.equal(JSON.stringify(ui.w.GoingDfsJournal.read(ui.w.localStorage).receipts),before);
});

test('freeze checks current availability without needing a background refresh',async t=>{
 let unavailable=false;const ui=mount(t,{buildPool:rows=>enrich(rows).map(p=>({...p,unavailable}))});
 await load(ui);confirm(ui);click(ui,'#dk-best');await generate(ui);unavailable=true;click(ui,'[data-act="freeze"]');
 assert.equal(ids(ui).length,0);assert.match(ui.d.getElementById('dk-status').textContent,/Availability changed/);
 assert.equal(ui.w.GoingDfsJournal.read(ui.w.localStorage).receipts.length,0);
});

test('availability changing while asynchronous generation runs rejects the stale result',async t=>{
 let unavailable=false,calls=0;const ui=mount(t,{
  buildPool:rows=>enrich(rows).map(p=>({...p,unavailable})),
  buildScenario:async()=>{if(++calls>1){await new Promise(resolve=>setTimeout(resolve,10));unavailable=true;}return {version:'team-budget-v1',teams:{BUF:{counts:[4,4,4],denominator:20},KC:{counts:[4,4,4],denominator:20}}};}
 });
 await load(ui);confirm(ui);await generate(ui);assert.equal(ids(ui).length,0);
 assert.match(ui.d.getElementById('dk-status').textContent,/Availability changed during generation/);
 assert.equal(ui.d.querySelector('[data-act="freeze"]').disabled,true);
});
