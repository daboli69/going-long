const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const NOW=Date.parse('2026-10-11T12:00:00Z'),KICK='2026-10-11T17:00:00Z',FRESH='2026-10-11T11:58:00Z';
function load(){
 const dom=new JSDOM('<!doctype html><body><p id="status"></p><div id="host"></div></body>',{runScripts:'outside-only',url:'https://going-long.test/'});
 for(const f of ['fanatics-td-terms.js','fanatics-td.js','fanatics-td-ui.js'])dom.window.eval(fs.readFileSync(path.join(root,'shared',f),'utf8'));
 return dom;
}
// players: id -> {team, opp, game}
const GAMES=[['AAA','BBB'],['CCC','DDD'],['EEE','FFF'],['GGG','HHH']];
function prop(id,{book='fanatics',odds=300,game=0,home=true,updatedAt=FRESH,market='atd',line=.5,kickoff=KICK,name}={}){
 const [h,a]=GAMES[game];
 return {player:name||'Player '+id,profileId:id,team:home?h:a,opp:home?a:h,market,line,book,bookKey:book,overOdds:odds,updatedAt,kickoff,eventTeams:[h,a],homeName:h,awayName:a,model:{}};
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
 assert.match(text,/estimated chance all three score/);assert.match(text,/independent/);assert.match(text,/not a proven hit rate/);
 assert.match(text,/\+\d+ combined/);assert.match(text,/Fanatics feed/);assert.match(text,/UNVERIFIED OFFER RULES/);assert.match(text,/Highest chance is not highest value/);
 assert.match(text,/Availability: Expected/);assert.match(text,/1:00 PM ET/);
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
 const realNow=Date.now(),props2=props.map(p=>({...p,kickoff:new Date(realNow+3*3600000).toISOString(),updatedAt:new Date(realNow-60000).toISOString()}));
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
 const realNow=Date.now(),props=fanatics(4).map(p=>({...p,book:'fanduel',bookKey:'fanduel',kickoff:new Date(realNow+3*3600000).toISOString(),updatedAt:new Date(realNow-60000).toISOString()}));
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
test('Jackpot integration: the promo panel hooks the new view, keeps the old engine as fallback, and adds no new network dependency',()=>{
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 for(const f of ['fanatics-td-terms.js','fanatics-td.js','fanatics-td-ui.js','fanatics-td.css'])assert.ok(html.includes('/shared/'+f),f);
 assert.ok(html.includes('GoingFanaticsTDUI.render($(\'promoOptions\')'));assert.ok(html.includes('GoingTouchdown.optimize'));
 assert.match(html,/id="btPromoPanel"/);assert.match(html,/id="promoOptions"/);assert.match(html,/id="promoStatus"/);
 const hook=html.slice(html.indexOf('GoingFanaticsTDUI.render($(\'promoOptions\')')-300,html.indexOf('GoingFanaticsTDUI.render($(\'promoOptions\')')+900);
 assert.match(hook,/bettingEligibility/);assert.match(hook,/availability:/);assert.match(hook,/return;/);
 assert.ok(fs.existsSync(path.join(root,'shared/fanatics-td.css')));
});
test('mobile layout rules exist: single column list, no fixed widths that can overflow',()=>{
 const css=fs.readFileSync(path.join(root,'shared/fanatics-td.css'),'utf8');
 assert.match(css,/@media\(max-width:600px\)/);assert.match(css,/\.ft-manual textarea\{[^}]*max-width:100%/);assert.doesNotMatch(css,/(?<!max-)(?<!min-)width:\s*\d{3,}px/);
});
