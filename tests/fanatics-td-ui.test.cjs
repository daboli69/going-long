const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const NOW=Date.parse('2026-10-11T12:00:00Z'),KICK='2026-10-11T17:00:00Z',FRESH='2026-10-11T11:58:00Z';
function load(){
 const dom=new JSDOM('<!doctype html><body><p id="status"></p><div id="host"></div></body>',{runScripts:'outside-only',url:'https://going-long.test/'});
 for(const f of ['fanatics-td-terms.js','fanatics-td.js','fanatics-td-ui.js'])dom.window.eval(fs.readFileSync(path.join(root,'shared',f),'utf8'));
 dom.window.Date.now=()=>NOW;return dom;
}
// players: id -> {team, opp, game}
const GAMES=[['AAA','BBB'],['CCC','DDD'],['EEE','FFF'],['GGG','HHH']];
function prop(id,{book='fanatics',odds=300,game=0,home=true,updatedAt=FRESH,market='atd',line=.5,kickoff=KICK,name}={}){
 const [h,a]=GAMES[game];
 return {player:name||'Player '+id,profileId:id,team:home?h:a,opp:home?a:h,market,line,book,bookKey:book,source:'parlay',overOdds:odds,updatedAt,kickoff,eventTeams:[h,a],homeName:h,awayName:a,model:{}};
}
function ctxFor(props,over={}){
 const dom=load(),w=dom.window;
 const status=w.document.getElementById('status'),host=w.document.getElementById('host');
 const info={checkedAt:new Date(NOW-60000).toISOString(),teams:[...new Set(props.map(p=>p.team))].map(t=>({team:t,players:props.filter(p=>p.team===t).map(p=>({key:w.GoingFanaticsTD.nameKey(p.player),availability:'expected'}))}))};
 const ctx={now:NOW,slateDate:'2026-10-11',props,probability:()=>.3,availability:info,eligibility:()=>({actionable:true,state:'active',label:'Active'}),profiles:{},statusEl:status,
  resolveTeam:t=>t,currentWeekProp:()=>true,...over};
 return {w,host,status,ctx};
}
const fanatics=n=>Array.from({length:n},(_,i)=>prop('F'+i,{game:i%4,odds:300+i*10,home:i<4}));

test('with real Fanatics prices the Jackpot view renders ranked, valid slips with every required field',()=>{
 const {w,host,status,ctx}=ctxFor(fanatics(8));
 w.GoingFanaticsTDUI.render(host,ctx);
 const cards=host.querySelectorAll('.ft-card');
 assert.ok(cards.length>=1&&cards.length<=5);
 assert.equal(status.dataset.level,'ok');
 const first=cards[0],text=first.textContent;
 assert.equal(first.querySelectorAll('.ft-leg').length,3);
 assert.match(text,/model estimate that all three score/);assert.match(text,/independent/);assert.match(text,/not a proven hit rate/);
 assert.match(text,/\+\d+ combined/);assert.match(text,/Fanatics feed/);assert.match(text,/UNVERIFIED OFFER RULES/);assert.match(text,/Highest chance is not highest value/);
 assert.match(text,/Availability: Expected/);assert.match(text,/1:00 PM ET/);assert.doesNotMatch(text,/starts after 1:00 PM ET/);// a 1:00 PM kickoff is not a later game
 assert.doesNotMatch(text,/profit|guaranteed|\$\d/i);
 // ranks are in descending probability order
 const probs=[...cards].map(c=>parseFloat(c.querySelector('.ft-headline b').textContent));
 for(let i=1;i<probs.length;i++)assert.ok(probs[i-1]>=probs[i]);
});
test('no Fanatics prices in the feed: honest unavailable state, no slip, other books are never substituted',()=>{
 const props=[...fanatics(6).map(p=>({...p,book:'fanduel',bookKey:'fanduel'}))];
 const {w,host,status,ctx}=ctxFor(props);
 w.GoingFanaticsTDUI.render(host,ctx);
 assert.equal(host.querySelectorAll('.ft-card').length,0);assert.equal(status.dataset.level,'unavailable');
 assert.match(status.textContent,/NO FANATICS PRICES/);assert.match(status.textContent,/no other sportsbook's price is substituted/);
 assert.ok(host.querySelector('details.ft-manual').hasAttribute('open'));
});
test('stale Fanatics quotes, unconfirmed roster, unknown or failed eligibility and started games produce no slip',()=>{
 const stale=fanatics(6).map(p=>({...p,updatedAt:'2026-10-11T10:00:00Z'}));
 let r=ctxFor(stale);r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);assert.match(r.status.textContent,/price needs refreshing/);
 r=ctxFor(fanatics(6),{availability:null});r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);assert.match(r.status.textContent,/roster screen did not confirm availability/);
 r=ctxFor(fanatics(6),{eligibility:()=>null});r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);assert.match(r.status.textContent,/eligibility not verified/);
 r=ctxFor(fanatics(6),{eligibility:()=>({actionable:false,state:'bye',label:'Team on bye'})});r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);assert.match(r.status.textContent,/team on bye/);
 r=ctxFor(fanatics(6).map(p=>({...p,kickoff:'2026-10-11T11:00:00Z'})));r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);
});
test('one player with a bad status is dropped while the rest still produce slips',()=>{
 const props=fanatics(8);
 const {w,host,ctx}=ctxFor(props,{eligibility:id=>id==='F0'?{actionable:false,state:'out',label:'Ruled out'}:{actionable:true,state:'active',label:'Active'}});
 w.GoingFanaticsTDUI.render(host,ctx);
 assert.ok(host.querySelectorAll('.ft-card').length>=1);
 assert.ok(![...host.querySelectorAll('.ft-leg b')].some(b=>b.textContent==='Player F0'));
});
test('a model error or missing probability excludes the player instead of throwing',()=>{
 const {w,host,status,ctx}=ctxFor(fanatics(6),{probability:()=>NaN});
 w.GoingFanaticsTDUI.render(host,ctx);assert.equal(host.querySelectorAll('.ft-card').length,0);assert.match(status.textContent,/model estimate/i);
 const bad=ctxFor(fanatics(6),{probability:()=>{throw Error('model offline');}});
 bad.w.GoingFanaticsTDUI.render(bad.host,bad.ctx);assert.equal(bad.status.dataset.level,'error');assert.match(bad.status.textContent,/model offline/);assert.match(bad.host.textContent,/unavailable/);
});
test('entering Fanatics prices builds slips when the feed has none, and labels them as entered by the user',()=>{
 const props=fanatics(8).map(p=>({...p,book:'fanduel',bookKey:'fanduel'}));
 const {w,host,status,ctx}=ctxFor(props);
 w.GoingFanaticsTDUI.render(host,ctx);assert.equal(status.dataset.level,'unavailable');
 host.querySelector('#ftManual').value=Array.from({length:8},(_,i)=>`Player F${i} +${300+i*10}`).join('\n');
 let changed=0;const ctx2={...ctx,onChange:()=>{changed++;w.GoingFanaticsTDUI.render(host,{...ctx,now:NOW});}};
 w.GoingFanaticsTDUI.render(host,ctx2);host.querySelector('#ftManual').value=Array.from({length:8},(_,i)=>`Player F${i} +${300+i*10}`).join('\n');
 // the UI stamps manual entries with the real clock; use a clock close to it for the rebuild
 const realNow=NOW,props2=props.map(p=>({...p,kickoff:new Date(realNow+3*3600000).toISOString(),updatedAt:new Date(realNow-60000).toISOString()}));
 const live=ctxFor(props2,{now:realNow,slateDate:new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(realNow+3*3600000))});
 live.ctx.availability={checkedAt:new Date(realNow).toISOString(),teams:live.ctx.availability.teams};
 live.w.GoingFanaticsTDUI.render(live.host,live.ctx);
 live.host.querySelector('#ftManual').value=Array.from({length:8},(_,i)=>`Player F${i} +${300+i*10}`).join('\n');
 live.host.querySelector('#ftApply').click();
 assert.ok(live.host.querySelectorAll('.ft-card').length>=1,'slips after entering prices');
 assert.match(live.host.textContent,/entered by you/);assert.match(live.host.textContent,/includes prices you entered/);
 live.host.querySelector('#ftClear').click();assert.equal(live.host.querySelectorAll('.ft-card').length,0);
});
test('manual lines that cannot be matched are reported, not guessed',()=>{
 const realNow=NOW,props=fanatics(4).map(p=>({...p,book:'fanduel',bookKey:'fanduel',kickoff:new Date(realNow+3*3600000).toISOString(),updatedAt:new Date(realNow-60000).toISOString()}));
 const day=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(realNow+3*3600000));
 const r=ctxFor(props,{now:realNow,slateDate:day});r.w.GoingFanaticsTDUI.render(r.host,r.ctx);
 r.host.querySelector('#ftManual').value='Nobody Real +500\nPlayer F0 +10';r.host.querySelector('#ftApply').click();
 const msg=r.host.querySelector('#ftManualMsg').textContent;assert.match(msg,/0 prices used/);assert.match(msg,/does not match/);assert.match(msg,/invalid American/);
});
test('the terms panel separates user-supplied, publicly stated and unverified rules and never calls them official',()=>{
 const {w,host,ctx}=ctxFor(fanatics(8));w.GoingFanaticsTDUI.render(host,ctx);
 const t=host.querySelector('.ft-terms').textContent;
 assert.match(t,/Supplied by you/);assert.match(t,/not the official rules/i);assert.match(t,/Conflicting or unverified/);assert.match(t,/could not be retrieved/);assert.match(t,/Ohio|OH/);
 assert.doesNotMatch(t,/officially verified/i);
});
test('names and teams are escaped (no markup injection from feed data)',()=>{
 const props=fanatics(8);props[0]={...props[0],player:'<img src=x onerror=alert(1)>'};
 const {w,host,ctx}=ctxFor(props);w.GoingFanaticsTDUI.render(host,ctx);
 assert.equal(host.querySelectorAll('img').length,0);
});
test('Jackpot integration hooks the verified selection view and pauses if the module is missing',()=>{
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 for(const f of ['fanatics-td-terms.js','fanatics-td.js','fanatics-td-ui.js','fanatics-td.css'])assert.ok(html.includes('/shared/'+f),f);
 assert.ok(html.includes('GoingFanaticsTDUI.render($(\'promoOptions\')'));assert.ok(!html.includes('GoingTouchdown.optimize'));assert.match(html,/selection is paused/);
 assert.match(html,/id="btPromoPanel"/);assert.match(html,/id="promoOptions"/);assert.match(html,/id="promoStatus"/);
 const hook=html.slice(html.indexOf('GoingFanaticsTDUI.render($(\'promoOptions\')')-300,html.indexOf('GoingFanaticsTDUI.render($(\'promoOptions\')')+900);
 assert.match(hook,/bettingEligibility/);assert.match(hook,/availability:/);assert.match(hook,/return;/);
 assert.ok(fs.existsSync(path.join(root,'shared/fanatics-td.css')));
});
test('mobile layout rules exist: single column list, no fixed widths that can overflow',()=>{
 const css=fs.readFileSync(path.join(root,'shared/fanatics-td.css'),'utf8');
 assert.match(css,/@media\(max-width:600px\)/);assert.match(css,/\.ft-manual textarea\{[^}]*max-width:100%/);assert.doesNotMatch(css,/(?<!max-)(?<!min-)width:\s*\d{3,}px/);
});

test('a leg from a game after 1:00 PM ET carries the unverified later-game caveat',()=>{
 const props=fanatics(8).map((p,i)=>i<4?p:{...p,kickoff:'2026-10-11T20:25:00Z'});
 const {w,host,ctx}=ctxFor(props);w.GoingFanaticsTDUI.render(host,ctx);
 assert.match(host.textContent,/starts after 1:00 PM ET\. Whether the promotion accepts legs from later games was not verified/);
});
test('typed prices and the open panel survive the page timer re-render, and a focused textarea is not rebuilt',()=>{
 const {w,host,ctx}=ctxFor(fanatics(8).map(p=>({...p,book:'fanduel',bookKey:'fanduel'})));
 w.GoingFanaticsTDUI.render(host,ctx);
 const area=host.querySelector('#ftManual');area.value='Player F0 +250';host.querySelector('details.ft-manual').open=true;
 w.GoingFanaticsTDUI.render(host,ctx);// timer re-render without pressing Apply
 assert.equal(host.querySelector('#ftManual').value,'Player F0 +250');assert.equal(host.querySelector('details.ft-manual').open,true);
 const a2=host.querySelector('#ftManual');a2.focus();a2.value='Player F1 +300';const before=host.querySelector('#ftManual');
 w.GoingFanaticsTDUI.render(host,ctx);assert.equal(host.querySelector('#ftManual'),before,'focused textarea element must be kept');assert.equal(before.value,'Player F1 +300');
});

test('a fresh typed price beats a stale feed quote for the same player (UI precedence)',()=>{
 const realNow=NOW,day=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(realNow+3*3600000));
 const props=fanatics(8).map(p=>({...p,kickoff:new Date(realNow+3*3600000).toISOString(),updatedAt:new Date(realNow-3*3600000).toISOString()}));// every Fanatics quote is 3 hours old
 const r=ctxFor(props,{now:realNow,slateDate:day});r.ctx.availability={checkedAt:new Date(realNow).toISOString(),teams:r.ctx.availability.teams};
 r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);assert.match(r.status.textContent,/price needs refreshing/);
 r.host.querySelector('#ftManual').value=Array.from({length:8},(_,i)=>`Player F${i} +${300+i*10}`).join('\n');r.host.querySelector('#ftApply').click();
 assert.ok(r.host.querySelectorAll('.ft-card').length>=1);assert.match(r.host.textContent,/entered by you/);
});

test('focused editor retains text and focus while invalidated cards are removed',()=>{
 const r=ctxFor(fanatics(4));r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,4);
 const area=r.host.querySelector('#ftManual');area.focus();area.value='Player F0 +250';area.setSelectionRange(4,8);
 r.w.GoingFanaticsTDUI.render(r.host,{...r.ctx,availability:null,eligibility:()=>({actionable:false})});
 assert.equal(r.host.querySelector('#ftManual'),area);assert.equal(r.w.document.activeElement,area);assert.equal(area.value,'Player F0 +250');assert.equal(area.selectionStart,4);
 assert.equal(r.host.querySelectorAll('.ft-card').length,0);assert.notEqual(r.status.dataset.level,'ok');
 r.w.GoingFanaticsTDUI.render(r.host,{...r.ctx,now:NOW+3*3600000});assert.equal(r.host.querySelectorAll('.ft-card').length,0);
});
test('feed prices cannot borrow another game contract and equivalent clocks mean the same game',()=>{
 const r=ctxFor([prop('A'),prop('A',{book:'fanduel',game:1,updatedAt:'2026-10-11T11:59:00Z'}),prop('B',{game:2}),prop('C',{game:3})]);
 const built=r.w.GoingFanaticsTDUI.buildLegs(r.ctx);assert.ok(!built.legs.some(l=>l.playerId==='A'));assert.ok(!built.pool.some(l=>l.playerId==='A'));
 const two=ctxFor([prop('A'),prop('B',{kickoff:'2026-10-11T13:00:00-04:00'}),prop('C',{game:1})]);
 two.w.GoingFanaticsTDUI.render(two.host,two.ctx);assert.equal(two.host.querySelectorAll('.ft-card').length,0);
});
test('future and malformed availability clocks fail closed; fresh rows replace missing clocks',()=>{
 for(const at of ['2027-01-01T00:00:00Z','2026-10-11T11:59:00','2026-10-11T11:59:00+00:60','2026-02-30T11:59:00Z']){const r=ctxFor(fanatics(4));r.ctx.availability.checkedAt=at;r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0,at);}
 const props=[prop('A',{updatedAt:undefined}),prop('A',{updatedAt:FRESH})];props[0].updatedAt=undefined;
 const r=ctxFor(props),built=r.w.GoingFanaticsTDUI.buildLegs(r.ctx);assert.equal(built.legs[0].price.updatedAt,FRESH);
});
test('manual prices persist for exactly120minutes but never migrate to another game',()=>{
 const r=ctxFor([prop('A',{book:'fanduel'})]),UI=r.w.GoingFanaticsTDUI,F=r.w.GoingFanaticsTD;
 const pool=UI.buildLegs(r.ctx).pool,entries=F.parseManualPrices('Player A +1000',pool,NOW).entries;
 assert.equal(entries.length,1);UI.saveManual(entries);assert.equal(UI.loadManual(NOW+120*60000,120).length,1);assert.equal(UI.loadManual(NOW+120*60000+1,120).length,0);
 UI.saveManual(entries);const next={...r.ctx,props:[prop('A',{book:'fanduel',game:1})]};assert.equal(UI.buildLegs(next,UI.loadManual(NOW,120)).legs[0].price,null);
 UI.saveManual([{...entries[0],enteredAt:'2026-10-11T12:00:00.001Z'}]);assert.equal(UI.loadManual(NOW,120).length,0);
});
test('canonical team resolver unifies book aliases and non-Sunday slates show no slips',()=>{
 const props=[prop('A'),prop('B'),prop('C',{game:1})];props[1].eventTeams=['Alias AAA','Alias BBB'];
 const r=ctxFor(props,{resolveTeam:t=>t.replace('Alias ', '')});r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);
 const non=ctxFor(fanatics(4).map(p=>({...p,kickoff:'2026-10-12T17:00:00Z'})),{slateDate:'2026-10-12'});non.w.GoingFanaticsTDUI.render(non.host,non.ctx);assert.equal(non.host.querySelectorAll('.ft-card').length,0);
});
test('feed prices require a known feed source and a player team belonging to the game',()=>{
 for(const change of [p=>delete p.source,p=>p.source='manual',p=>p.manual=true,p=>p.team='WRONG']){const props=fanatics(3);change(props[0]);const r=ctxFor(props);r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);}
 const r=ctxFor(fanatics(3),{profiles:{F0:{team:'WRONG'}}});r.w.GoingFanaticsTDUI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0);
});
test('NFL abbreviations resolve idempotently across roster and event aliases',()=>{
 for(const [code,alias] of [['LA','LAR'],['JAX','JAC'],['WAS','WSH']]){
  const props=[prop('A'),prop('B'),prop('C',{game:1})];props[0]={...props[0],team:alias,eventTeams:[code,'BBB']};props[1]={...props[1],team:code,eventTeams:[alias,'BBB']};
  const r=ctxFor(props,{resolveTeam:t=>t===alias?null:t,profiles:{A:{team:code},B:{team:alias}}});
  const built=r.w.GoingFanaticsTDUI.buildLegs(r.ctx);assert.equal(built.stats.conflicts,0,alias);assert.equal(built.legs[0].event,built.legs[1].event,alias);
 }
});
test('unique authoritative schedule reconciles one-minute bookmaker jitter and blocks started games',()=>{
 const props=[prop('A'),prop('A',{book:'fanduel',kickoff:'2026-10-11T17:01:00Z'}),prop('B',{kickoff:'2026-10-11T17:01:00Z'}),prop('C',{game:1})];
 const schedule=[{home:'AAA',away:'BBB',kickoff:KICK},{home:'CCC',away:'DDD',kickoff:KICK}];
 const r=ctxFor(props,{schedule}),UI=r.w.GoingFanaticsTDUI;let b=UI.buildLegs(r.ctx);
 assert.equal(b.stats.conflicts,0);assert.equal(b.legs[0].event,b.legs[1].event);assert.equal(Date.parse(b.legs[1].kickoff),Date.parse(KICK));
 UI.render(r.host,r.ctx);assert.equal(r.host.querySelectorAll('.ft-card').length,0,'two real games cannot form three-game slip');
 const three=ctxFor(fanatics(3).map(p=>({...p,kickoff:'2026-10-11T17:01:00Z',updatedAt:'2026-10-11T17:00:00Z'})),{now:Date.parse(KICK)+30000,schedule:[...schedule,{home:'EEE',away:'FFF',kickoff:KICK}]});three.ctx.availability.checkedAt=KICK;
 three.w.GoingFanaticsTDUI.render(three.host,three.ctx);assert.equal(three.host.querySelectorAll('.ft-card').length,0,'actual kickoff has passed');
 for(const kickoff of ['2026-10-11T17:01:00.001Z','2026-10-11T20:25:00Z']){b=UI.buildLegs({...r.ctx,props:[prop('A',{kickoff})]});assert.equal(b.stats.conflicts,1,kickoff);assert.equal(b.legs.length,0);}
 b=UI.buildLegs({...r.ctx,schedule:[...schedule,schedule[0]]});assert.ok(b.stats.conflicts>0,'ambiguous schedule fails closed');
});

// ---- slip builder: suggestion count, repeat limit, locked and excluded players ----
const keysOf=host=>[...host.querySelectorAll('.ft-card h3')].map(h=>h.textContent);
const click=(host,sel)=>{const b=host.querySelector(sel);assert.ok(b,sel);b.click();};
test('builder lists usable players and controls the number of suggestions up to fifty',()=>{
 const {w,host,ctx}=ctxFor(fanatics(16));w.GoingFanaticsTDUI.render(host,ctx);
 assert.equal(host.querySelectorAll('.ft-card').length,5);
 assert.equal(host.querySelectorAll('.ft-pool .ft-row').length,16);
 const count=host.querySelector('#ftCount');count.value='20';count.dispatchEvent(new w.Event('change',{bubbles:true}));
 assert.equal(host.querySelectorAll('.ft-card').length,20);
 assert.equal(w.GoingFanaticsTDUI.loadBuilder().count,20);
 assert.match(host.querySelector('details.ft-builder summary').textContent,/20 suggestions/);
});
test('locking a player builds every suggestion around them and marks the leg',()=>{
 const {w,host,ctx}=ctxFor(fanatics(16));w.GoingFanaticsTDUI.render(host,ctx);
 click(host,'button[data-ft-lock="F9"]');
 const cards=[...host.querySelectorAll('.ft-card')];assert.equal(cards.length,5);
 assert.ok(cards.every(c=>c.querySelector('h3').textContent.includes('Player F9')));
 assert.ok(cards.every(c=>c.querySelector('.ft-leg.is-locked .ft-lock-tag')));
 assert.match(host.querySelector('.ft-exposure').textContent,/Built around Player F9/);
 // Another player in F9's game cannot be locked with it; a player from a different game can.
 assert.ok(host.querySelector('button[data-ft-lock="F13"]').disabled);
 click(host,'button[data-ft-lock="F10"]');
 assert.ok([...host.querySelectorAll('.ft-card h3')].every(h=>/Player F9/.test(h.textContent)&&/Player F10/.test(h.textContent)));
 click(host,'.ft-chip-lock button[data-ft-lock="F9"]');
 assert.equal(JSON.stringify(w.GoingFanaticsTDUI.loadBuilder().locked.map(x=>x.id)),'["F10"]');
});
test('excluded players never appear and the repeat limit caps every unlocked player',()=>{
 const {w,host,ctx}=ctxFor(fanatics(16).map((p,i)=>({...p,odds:300+i*7})),{probability:p=>.6-Number(p.profileId.slice(1))*.02});
 w.GoingFanaticsTDUI.render(host,ctx);
 click(host,'button[data-ft-exclude="F0"]');
 assert.ok(keysOf(host).every(k=>!/Player F0\b/.test(k)));
 const cap=host.querySelector('#ftCap');cap.value='1';cap.dispatchEvent(new w.Event('change',{bubbles:true}));
 const count=host.querySelector('#ftCount');count.value='10';count.dispatchEvent(new w.Event('change',{bubbles:true}));
 const seen={};for(const k of keysOf(host))for(const name of k.split(' + '))seen[name]=(seen[name]||0)+1;
 assert.ok(Object.values(seen).every(v=>v<=1),JSON.stringify(seen));
 assert.match(host.querySelector('.ft-exposure').textContent,/limit 1 per player/);
 assert.match(host.querySelector('.ft-exposure').textContent+' '+ctx.statusEl.textContent,/no player more than 1 time|no repeated players/);
 click(host,'button[data-ft-reset]');
 const b=w.GoingFanaticsTDUI.loadBuilder();assert.deepEqual([b.count,b.cap,b.locked.length,b.excluded.length],[5,null,0,0]);
});
test('a locked player who loses a usable price produces no slips and a clear reason',()=>{
 const props=fanatics(16),{w,host,ctx}=ctxFor(props);w.GoingFanaticsTDUI.render(host,ctx);
 click(host,'button[data-ft-lock="F3"]');assert.equal(host.querySelectorAll('.ft-card').length,5);
 ctx.props=props.filter(p=>p.profileId!=='F3');w.GoingFanaticsTDUI._state.force=true;w.GoingFanaticsTDUI.render(host,ctx);
 assert.equal(host.querySelectorAll('.ft-card').length,0);
 assert.match(ctx.statusEl.textContent,/locked player is not currently usable/);
 assert.match(host.querySelector('.ft-chip-lock').textContent,/not usable now/);
});
test('pool search filters rows and survives the periodic re-render while focused',()=>{
 const {w,host,ctx}=ctxFor(fanatics(16));w.GoingFanaticsTDUI.render(host,ctx);
 const input=host.querySelector('#ftSearch');input.focus();input.value='player f1';input.dispatchEvent(new w.Event('input',{bubbles:true}));
 const visible=()=>[...host.querySelectorAll('.ft-row')].filter(r=>!r.hidden).length;
 assert.equal(visible(),7);// F1, F10..F15
 w.GoingFanaticsTDUI.render(host,ctx);
 assert.equal(w.document.activeElement,host.querySelector('#ftSearch'));assert.equal(host.querySelector('#ftSearch').value,'player f1');assert.equal(visible(),7);
});
test('builder settings in storage are validated and pool rows escape names',()=>{
 const props=fanatics(8);props[0]={...props[0],player:'<img src=x onerror=alert(1)>'};
 const {w,host,ctx}=ctxFor(props);
 w.localStorage.setItem('going.fanatics.builder.v1',JSON.stringify({count:999,cap:-2,locked:[{id:'F1',name:'<b>x</b>'},{id:5},{id:'F2'},{id:'F3'},{id:'F4'}],excluded:'nope'}));
 const b=w.GoingFanaticsTDUI.loadBuilder();assert.deepEqual([b.count,b.cap,b.locked.length,b.excluded.length],[5,null,3,0]);
 w.localStorage.removeItem('going.fanatics.builder.v1');w.GoingFanaticsTDUI.render(host,ctx);
 assert.equal(host.querySelectorAll('.ft-pool img').length,0);assert.match(host.querySelector('.ft-pool').innerHTML,/&lt;img/);
});
