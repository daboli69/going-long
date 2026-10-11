/* Fanatics Sunday TD: leg building and presentation for the Jackpot section. The page supplies a context object (see the handoff doc); this module owns no global state
 * beyond the user's own manual Fanatics prices (kept in this browser only). No prices, probabilities or availability are invented here: every missing input excludes the player.
 */
(function(root){
'use strict';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const F=()=>root.GoingFanaticsTD||(typeof require!=='undefined'?require('./fanatics-td.js'):null);
const TERMS=()=>root.GoingFanaticsTDTerms||(typeof require!=='undefined'?require('./fanatics-td-terms.js'):null);
const STORE_KEY='going.fanatics.manualPrices.v1';
const etDay=t=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(t));
const etTime=t=>new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'2-digit'}).format(new Date(t))+' ET';
const ago=(t,now)=>{const m=Math.round((now-Date.parse(t))/60000);return !Number.isFinite(m)?'time unknown':m<1?'under a minute ago':m<90?m+' min ago':Math.round(m/60)+' h ago';};
const key=x=>String(x||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const etMinutes=t=>{const parts=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'numeric',hour12:false}).formatToParts(new Date(t));return (+parts.find(x=>x.type==='hour').value%24)*60+ +parts.find(x=>x.type==='minute').value;};
const pct=p=>p>=.1?(100*p).toFixed(0)+'%':(100*p).toFixed(1)+'%';

// ---- manual price store (browser only) ----
let memory=[];
function loadManual(now,maxMinutes){
 let list=memory;
 try{const raw=root.localStorage?.getItem(STORE_KEY);if(raw)list=JSON.parse(raw);}catch{}
 memory=(Array.isArray(list)?list:[]).filter(e=>e&&e.playerId&&typeof e.contract==='string'&&Number.isFinite(e.american)&&F().timestamp(e.enteredAt)!=null&&F().timestamp(e.enteredAt)<=now&&now-F().timestamp(e.enteredAt)<=maxMinutes*60000);
 return memory;
}
function saveManual(list){memory=list;try{root.localStorage?.setItem(STORE_KEY,JSON.stringify(list));}catch{}}

// ---- roster screen (ESPN, via /api/promo-availability): the page's existing independent check ----
function rosterAvailability(info,p,ctx){
 const now=ctx.now;
 const checked=F().timestamp(info?.checkedAt);
 if(!info||!Array.isArray(info.teams)||checked==null||checked>now||now-checked>10*60000)return 'unknown';
 const mine=F().canonicalTeam(p.team,ctx.resolveTeam),team=info.teams.filter(t=>key(t.team)===key(p.team)||(mine&&F().canonicalTeam(t.team,ctx.resolveTeam)===mine));
 const hits=team.flatMap(t=>t.players||[]).filter(r=>r.key===key(p.player));
 return hits.length===1?hits[0].availability:'unknown';
}

// Build engine legs from the page's props. One leg per player; the price is a real Fanatics quote or a price the user typed from Fanatics, never another book.
function buildLegs(ctx,manual=[]){
 const now=ctx.now,day=ctx.slateDate,byPlayer=new Map(),terms=F().validateTerms(ctx.termsOverride);
 const scheduled=new Map();
 for(const g of Array.isArray(ctx.schedule)?ctx.schedule:[]){
  const identity=F().gameIdentity({eventTeams:[g.home,g.away],kickoff:g.kickoff},ctx.resolveTeam),at=F().timestamp(g.kickoff);
  if(!identity||at==null||F().slateDay(at)!==day)continue;
  const pair=identity.split('|').slice(0,2).join('|');if(!scheduled.has(pair))scheduled.set(pair,[]);scheduled.get(pair).push(g);
 }
 for(const p of ctx.props||[]){
  if(p.market!=='atd'||!p.profileId||p.dfs||!(p.line==null||p.line===.5))continue;
  if(ctx.currentWeekProp&&!ctx.currentWeekProp(p))continue;
  let kick=F().timestamp(p.kickoff),event=F().gameIdentity(p,ctx.resolveTeam);if(kick==null||!event||!F().sunday(kick)||etDay(kick)!==day)continue;
  let scheduleConflict=false;
  if(ctx.schedule!=null){
   const matches=scheduled.get(event.split('|').slice(0,2).join('|'))||[];
   if(matches.length!==1||Math.abs(F().timestamp(matches[0].kickoff)-kick)>60000)scheduleConflict=true;
   else {kick=F().timestamp(matches[0].kickoff);event=F().gameIdentity({...p,kickoff:matches[0].kickoff},ctx.resolveTeam);}
  }
  const rec=byPlayer.get(p.profileId)||{any:null,fanatics:null,event,conflict:false};
  if(rec.event!==event||scheduleConflict)rec.conflict=true;
  const normalized={...p,eventTeams:p.eventTeams.map(t=>F().canonicalTeam(t,ctx.resolveTeam)),kickoff:new Date(kick).toISOString()};
  const playerTeam=F().canonicalTeam(p.team,ctx.resolveTeam),profileTeam=ctx.profiles?.[p.profileId]?.team;
  if(!playerTeam||!normalized.eventTeams.some(t=>key(t)===key(playerTeam))||(profileTeam&&key(F().canonicalTeam(profileTeam,ctx.resolveTeam))!==key(playerTeam)))rec.conflict=true;
  const at=F().timestamp(p.updatedAt),oldAt=F().timestamp(rec.any?.updatedAt);
  if(!rec.any||(at!=null&&at<=now&&(oldAt==null||oldAt>now||at>oldAt)))rec.any=normalized;
  const book=p.bookKey||p.book,oldFan=F().timestamp(rec.fanatics?.updatedAt);
  if(typeof book==='string'&&book.toLowerCase()==='fanatics'&&['parlay','nightly'].includes(p.source)&&!p.manual&&Number.isFinite(p.overOdds)&&(!rec.fanatics||(at!=null&&at<=now&&(oldFan==null||oldFan>now||at>oldFan))))rec.fanatics=normalized;
  byPlayer.set(p.profileId,rec);
 }
 const manualBy=new Map(manual.map(m=>[m.playerId,m]));
 const legs=[],pool=[],stats={players:byPlayer.size,fanaticsFeed:0,manual:0,noPrice:0,conflicts:0};
 for(const [playerId,rec] of byPlayer){
  if(rec.conflict){stats.conflicts++;continue;}
  const p=rec.any,event=rec.event,binding=F().contract(playerId,event);
  pool.push({playerId,player:p.player,contract:binding});
  const cands=[];
  if(rec.fanatics){stats.fanaticsFeed++;cands.push({american:rec.fanatics.overOdds,source:'feed',book:'fanatics',contract:binding,updatedAt:rec.fanatics.updatedAt});}
  const m=manualBy.get(playerId);
  if(m&&m.contract===binding){stats.manual++;cands.push({american:m.american,source:'manual',book:'fanatics',contract:binding,updatedAt:m.enteredAt});}
  // Freshest price still inside its own age limit (a stale feed quote must not hide a fresh typed price); otherwise the freshest, so the exclusion reason is shown.
  const within=c=>{const at=F().timestamp(c.updatedAt);return at!=null&&at<=now&&now-at<=(c.source==='manual'?terms.manualMaxAgeMinutes:terms.quoteMaxAgeMinutes)*60000;};
  const order=(x,y)=>(F().timestamp(y.updatedAt)??-Infinity)-(F().timestamp(x.updatedAt)??-Infinity);
  const price=cands.filter(within).sort(order)[0]||cands.sort(order)[0]||null;
  if(!price)stats.noPrice++;
  const model=ctx.probability?ctx.probability(p):null;
  const dec=ctx.eligibility?ctx.eligibility(playerId,p):null;
  const profile=ctx.profiles?.[playerId];
  legs.push({playerId,player:p.player,team:p.team,opp:p.opp,event,eventTeams:p.eventTeams,gameLabel:p.homeName&&p.awayName?`${p.awayName} @ ${p.homeName}`:'',kickoff:p.kickoff,
   probability:Number.isFinite(model)?model:null,availability:rosterAvailability(ctx.availability,p,ctx),eligibility:dec,price,
   scoringRole:profile?.scoring_role||null,calibrated:!!p.model?.calibration});
 }
 return {legs,pool,stats};
}

function legWhy(l){
 const sr=l.scoringRole,parts=[];
 if(sr&&sr.confidence!=='low'&&sr.tier&&Number.isFinite(sr.xtd_pg_l12))parts.push(`${String(sr.tier).toLowerCase()} scoring role (${sr.xtd_pg_l12.toFixed(2)} expected TDs per game, last 12)`);
 parts.push(`model ${pct(l.probability)} to score${l.calibrated?' (touchdown mean corrected)':''}`);
 return parts.join('; ');
}
const LEG_STATE={active:'Active',expected:'Expected (roster screen)'};
function legMarkup(l,now,F_,locked=false){
 const src=l.price.source==='manual'?`entered by you ${esc(ago(l.price.updatedAt,now))}`:`Fanatics feed ${esc(ago(l.price.updatedAt,now))}`;
 return `<li class="ft-leg${locked?' is-locked':''}"><div class="ft-leg-top"><b>${esc(l.player)}</b>${locked?' <span class="ft-lock-tag">Locked by you</span>':''} <span>${esc(l.team||'')}${l.opp?' vs '+esc(l.opp):''}</span><span class="ft-odds">${esc(F_.fmtAmerican(l.price.american))}</span></div>
 <div class="ft-leg-sub">${l.gameLabel?esc(l.gameLabel)+' · ':''}${esc(etTime(l.kickoff))} · price: ${src}</div>
 <div class="ft-leg-sub">${esc(legWhy(l))}</div>
 <div class="ft-leg-sub">Availability: ${esc(LEG_STATE[l.availability]||l.availability)} · ${esc(l.eligibility?.label||'')}${l.eligibility?.caution?' (caution)':''}. Not official game-day clearance.</div></li>`;
}
function optionMarkup(o,i,ctx){
 const F_=F(),now=ctx.now,oldest=Math.min(...o.legs.map(l=>Date.parse(l.price.updatedAt))),manualUsed=o.legs.some(l=>l.price.source==='manual');
 return `<article class="sig-card ft-card" data-rank="${i+1}"><div class="best-card-badges"><span class="best-badge go">#${i+1}</span><span class="best-badge">${esc(F_.fmtAmerican(o.american))} combined</span><span class="best-badge watch">UNVERIFIED OFFER RULES</span></div>
 <h3>${o.legs.map(l=>esc(l.player)).join(' + ')}</h3>
 <p class="ft-headline"><b>${pct(o.probability)}</b> model estimate that all three score <small>(assumes the three games are independent; joint estimates are not independently calibrated and may be inaccurate; not a proven hit rate)</small></p>
 <p class="ft-odds-line">Combined price ${esc(F_.fmtAmerican(o.american))} = ${o.decimal.toFixed(2)}x (${o.legs.map(l=>F_.decimal(l.price.american).toFixed(2)).join(' × ')}); the minimum is ${esc(F_.fmtAmerican(ctx.terms.minCombinedAmerican))} (${F_.decimal(ctx.terms.minCombinedAmerican).toFixed(2)}x). Oldest price ${esc(ago(new Date(oldest).toISOString(),now))}${manualUsed?'; includes prices you entered':''}.</p>
 <ol class="ft-legs">${o.legs.map(l=>legMarkup(l,now,F_,!!ctx.lockedSet?.has(l.playerId))).join('')}</ol>
 ${o.legs.some(l=>etMinutes(l.kickoff)>13*60)?'<p class="ft-note ft-late">Includes a game that starts after 1:00 PM ET. Whether the promotion accepts legs from later games was not verified.</p>':''}
 <p class="ft-note">Highest chance is not highest value: a likelier slip also pays less. No prize value is assumed and no betting edge has been validated. Confirm every price and the final ticket in the Fanatics app, and place it before 1:00 PM ET Sunday (per Fanatics' blog; not confirmed in official rules).</p></article>`;
}

function termsMarkup(){
 const T=TERMS(),F_=F();if(!T)return '';
 const d=F_.describeTerms(T),row=r=>`<li><b>${esc(r.key)}</b>: ${esc(r.value??'not stated')} <small>(${esc(r.status)}${r.source?'; '+esc(r.source):''})${r.note?' — '+esc(r.note):''}</small></li>`;
 return `<details class="ft-terms"><summary>Offer terms: what is and is not verified</summary><p class="bt-note">${esc(T.read_me)}</p>
 <h4>Supplied by you</h4><ul>${d.userSupplied.map(row).join('')}</ul><h4>Stated by public pages (not the official rules)</h4><ul>${d.verified.map(row).join('')}</ul>
 <h4>Conflicting or unverified</h4><ul>${d.unverified.map(row).join('')}</ul><p class="bt-note">Sources: ${T.sources.map(s=>`<a href="${esc(s.url)}" rel="noopener noreferrer" target="_blank">${esc(s.kind)}</a>`).join(' · ')}</p></details>`;
}

function statusFor(result,legsInfo,ctx){
 if(!legsInfo.stats.players)return {level:'none',text:'No anytime-touchdown props with a game on this Sunday are loaded yet (odds data may still be loading or unavailable). Nothing is shown.'};
 const s=legsInfo.stats,reasons=result.reasons||[],ex=Object.entries(result.excluded||{}).map(([k,v])=>`${v} ${k.toLowerCase()}`).join('; ');
 if(s.conflicts)reasons.push(`${s.conflicts} player${s.conflicts===1?'':'s'} excluded because their game identities conflict.`);
 if(result.options.length)return {level:'ok',text:`${result.options.length} slip${result.options.length===1?'':'s'} meeting the combined-price test from ${result.eligiblePlayers} eligible players in ${result.eligibleGames} games. ${reasons.join(' ')} ${ex?'Excluded: '+ex+'.':''}`};
 if(!s.fanaticsFeed&&!s.manual&&!s.conflicts)return {level:'unavailable',text:`NO FANATICS PRICES: the odds feed currently has no Fanatics anytime-touchdown prices (${s.players} players have a game this Sunday; ${s.noPrice} have no Fanatics price). Nothing qualifies and no other sportsbook's price is substituted. Enter the Fanatics prices you see in their app below to build slips.`};
 return {level:'none',text:`No slip meets the price test. ${reasons.join(' ')} ${ex?'Excluded: '+ex+'.':''}`};
}

// ---- slip builder settings (browser only): suggestion count, repeat limit, locked and excluded players ----
const BUILDER_KEY='going.fanatics.builder.v1',COUNTS=[5,10,15,20,25,30,40,50],CAPS=[1,2,3,4,5,6,8,10];
const ids=list=>(Array.isArray(list)?list:[]).filter(x=>x&&typeof x.id==='string'&&x.id).map(x=>({id:x.id,name:String(x.name||x.id).slice(0,80)}));
function loadBuilder(){
 let raw=null;try{raw=JSON.parse(root.localStorage?.getItem(BUILDER_KEY)||'null');}catch{}
 const b=raw&&typeof raw==='object'?raw:{};
 return {count:COUNTS.includes(b.count)?b.count:5,cap:CAPS.includes(b.cap)?b.cap:null,locked:ids(b.locked).slice(0,3),excluded:ids(b.excluded),open:b.open!==false};
}
function saveBuilder(b){try{root.localStorage?.setItem(BUILDER_KEY,JSON.stringify(b));}catch{}}

function builderMarkup(b,result,F_,now){
 const lockedIds=new Set(b.locked.map(x=>x.id)),excludedIds=new Set(b.excluded.map(x=>x.id));
 const lockedGames=new Set(result.pool.filter(p=>lockedIds.has(p.playerId)).map(p=>p.event));
 const usable=new Set(result.pool.map(p=>p.playerId));
 const chip=(x,kind)=>`<span class="ft-chip ft-chip-${kind}">${esc(x.name)}${usable.has(x.id)?'':' <small>(not usable now)</small>'} <button type="button" data-ft-${kind==='lock'?'lock':'exclude'}="${esc(x.id)}" data-ft-name="${esc(x.name)}" aria-label="Remove ${esc(x.name)} from ${kind==='lock'?'locked':'excluded'} players">✕</button></span>`;
 const rows=result.pool.map(p=>{
  const isLocked=lockedIds.has(p.playerId),isExcluded=excludedIds.has(p.playerId);
  const lockBlocked=!isLocked&&(lockedIds.size>=3?'Three players are already locked':lockedGames.has(p.event)?'A locked player is already in this game':'');
  const src=p.price.source==='manual'?'entered by you':'Fanatics feed';
  return `<div class="ft-row${isLocked?' is-locked':''}${isExcluded?' is-excluded':''}" role="listitem" data-ft-search="${esc([p.player,p.team,p.opp,p.gameLabel].join(' ').toLowerCase())}">
   <div class="ft-row-who"><b>${esc(p.player)}</b><small>${esc(p.team||'')}${p.gameLabel?' · '+esc(p.gameLabel):''} · ${esc(etTime(p.kickoff))}</small></div>
   <div class="ft-row-num"><b>${esc(F_.fmtAmerican(p.price.american))}</b><small>${src} ${esc(ago(p.price.updatedAt,now))}</small></div>
   <div class="ft-row-num"><b>${pct(p.probability)}</b><small>model${p.eligibility?.caution?' · caution':''}</small></div>
   <div class="ft-row-act"><button type="button" data-ft-lock="${esc(p.playerId)}" data-ft-name="${esc(p.player)}" aria-pressed="${isLocked}"${lockBlocked?` disabled title="${esc(lockBlocked)}"`:''}>${isLocked?'Unlock':'Lock'}</button><button type="button" data-ft-exclude="${esc(p.playerId)}" data-ft-name="${esc(p.player)}" aria-pressed="${isExcluded}"${isLocked?' disabled title="Unlock this player first"':''}>${isExcluded?'Include':'Exclude'}</button></div></div>`;
 }).join('');
 const opt=(v,label,cur)=>`<option value="${v??''}"${v===cur?' selected':''}>${label}</option>`;
 return `<details class="ft-builder"${b.open?' open':''}><summary>Build your slips (${b.count} suggestions · ${b.cap==null?'no repeat limit':'max '+b.cap+' per player'} · ${b.locked.length} locked · ${b.excluded.length} excluded)</summary>
  <div class="ft-controls"><label>Suggestions <select id="ftCount">${COUNTS.map(c=>opt(c,c,b.count)).join('')}</select></label>
  <label>Max slips per player <select id="ftCap">${opt(null,'No limit',b.cap)}${CAPS.map(c=>opt(c,c,b.cap)).join('')}</select></label>
  <button type="button" data-ft-reset>Reset builder</button></div>
  <p class="bt-note">Lock up to three players from different games and every suggestion is built around them. Exclude players you do not want. Locked players are exempt from the repeat limit. Only players with a usable Fanatics price, a model estimate and confirmed availability are listed.</p>
  ${b.locked.length?`<div class="ft-chips"><span>Locked:</span>${b.locked.map(x=>chip(x,'lock')).join('')}</div>`:''}
  ${b.excluded.length?`<div class="ft-chips"><span>Excluded:</span>${b.excluded.map(x=>chip(x,'exclude')).join('')}</div>`:''}
  <label class="ft-search"><span class="sr-only">Search the player pool</span><input type="search" id="ftSearch" placeholder="Search ${result.pool.length} usable players, teams or games" value="${esc(STATE.search)}" autocomplete="off"></label>
  <div class="ft-pool" role="list" aria-label="Usable players">${rows||'<p class="ft-note">No player currently has a usable Fanatics price, model estimate and confirmed availability.</p>'}</div></details>`;
}
function applySearch(host){
 const q=STATE.search.trim().toLowerCase();
 for(const row of host.querySelectorAll('.ft-row'))row.hidden=!!q&&!row.dataset.ftSearch.includes(q);
}

// ---- DOM ----
const STATE={manualText:'',open:undefined,force:false,msg:'',lastStatus:null,search:''};
function render(host,ctx){
 if(!host||!ctx)return;
 // Keep a focused editor (manual prices, builder search or selects) in place while every result revalidates.
 const active=root.document?.activeElement,keepSel=['details.ft-manual','details.ft-builder'];
 const old=host.querySelector('#ftManual');
 if(old){STATE.manualText=old.value;STATE.open=host.querySelector('details.ft-manual')?.open;}
 const search=host.querySelector('#ftSearch');if(search)STATE.search=search.value;
 const focusPanel=!STATE.force&&active&&host.contains(active)?keepSel.map(s=>active.closest?.(s)).find(Boolean)||null:null;
 const focusId=active&&host.contains(active)?active.id:'';
 STATE.force=false;
 const F_=F(),now=ctx.now??Date.now(),B=loadBuilder();
 const terms=F_.validateTerms({...(ctx.termsOverride||{}),optionCount:B.count,maxPlayerAppearances:B.cap});
 let html='';
 try{
  const manual=loadManual(now,terms.manualMaxAgeMinutes),{legs,pool,stats}=buildLegs({...ctx,now},manual);
  const result=F_.select(legs,{now,terms,slateDate:ctx.slateDate,excludedPlayers:[...(ctx.excludedPlayers||[]),...B.excluded.map(x=>x.id)],lockedPlayers:B.locked.map(x=>x.id)});
  const st=statusFor(result,{stats},ctx),lockedSet=new Set(result.locked),full={...ctx,now,terms,lockedSet};
  STATE.lastStatus=st;
  if(ctx.statusEl){ctx.statusEl.textContent=st.text;ctx.statusEl.dataset.level=st.level;}
  html+=termsMarkup();
  html+=`<details class="ft-manual" ${(STATE.open!==undefined?STATE.open:st.level==='unavailable')?'open':''}><summary>Enter Fanatics prices you can see (${manual.length} saved, valid ${terms.manualMaxAgeMinutes} min)</summary>
   <p class="bt-note">One player per line, anytime-TD American odds from the Fanatics app, for example <code>Amon-Ra St. Brown +120</code>. Prices stay in this browser only and expire after ${terms.manualMaxAgeMinutes} minutes; they are labelled "entered by you" on every slip.</p>
   <textarea id="ftManual" rows="6" spellcheck="false" aria-label="Fanatics anytime touchdown prices">${esc(STATE.manualText)}</textarea><div class="ft-actions"><button type="button" id="ftApply">Use these prices</button><button type="button" id="ftClear">Clear saved prices</button></div><div id="ftManualMsg" role="status">${esc(STATE.msg)}</div></details>`;
  html+=builderMarkup(B,result,F_,now);
  if(result.options.length){
   const names=new Map(result.options.flatMap(o=>o.legs.map(l=>[l.playerId,l.player])));
   const repeated=Object.entries(result.exposure).filter(([id,n])=>n>1&&!lockedSet.has(id)).map(([id,n])=>`${esc(names.get(id))} ${n}/${result.options.length}`).join(' · ')||'no repeated players';
   html+=`<p class="ft-note ft-exposure">${result.locked.length?`Built around ${result.locked.map(id=>esc(names.get(id))).join(' + ')} (locked, in every slip). `:''}Shared-player exposure across these ${result.options.length} slips: ${repeated}${result.cap!=null?` (limit ${result.cap} per player)`:''}. A shared player failing to score removes every slip containing them. This ranking maximizes each slip separately; it does not optimize the chance that at least one entry wins.</p><div class="ft-list">${result.options.map((o,i)=>optionMarkup(o,i,full)).join('')}</div>`;
  }else html+=`<p class="gc-empty ft-empty">${esc(st.text)}</p>`;
  const next=root.document.createElement('div');next.innerHTML=html;
  const keep=focusPanel&&host.contains(focusPanel)?focusPanel:null;
  if(keep){
   const sel=keepSel.find(s=>keep.matches(s)),replacement=next.querySelector(sel);
   keep.querySelector('summary').innerHTML=replacement.querySelector('summary').innerHTML;
   if(sel==='details.ft-manual')keep.querySelector('#ftManualMsg').textContent=STATE.msg;
   const nodes=[...next.childNodes].map(n=>n===replacement?keep:n),at=nodes.indexOf(keep);
   for(const child of [...host.childNodes])if(child!==keep)child.remove();
   nodes.forEach((n,i)=>{if(n===keep)return;if(i<at)host.insertBefore(n,keep);else host.appendChild(n);});
  }else{
   host.replaceChildren(...next.childNodes);
   if(focusId)host.querySelector('#'+focusId)?.focus({preventScroll:true});
  }
  applySearch(host);
  const area=host.querySelector('#ftManual');
  const rerender=()=>{STATE.force=true;if(ctx.onChange)ctx.onChange();else render(host,{...ctx,now:Date.now()});};
  host.querySelector('#ftApply').onclick=()=>{
   STATE.manualText=area.value;STATE.open=true;const parsed=F_.parseManualPrices(area.value,pool,Date.now());
   const keepManual=loadManual(Date.now(),terms.manualMaxAgeMinutes).filter(m=>!parsed.entries.some(e=>e.playerId===m.playerId));
   saveManual([...keepManual,...parsed.entries]);
   STATE.msg=`${parsed.entries.length} price${parsed.entries.length===1?'':'s'} used.${parsed.errors.length?' Problems: '+parsed.errors.join(' '):''}`;
   rerender();
  };
  host.querySelector('#ftClear').onclick=()=>{STATE.manualText='';STATE.msg='';STATE.open=true;saveManual([]);rerender();};
  host.onclick=e=>{
   const btn=e.target.closest?.('button[data-ft-lock],button[data-ft-exclude],button[data-ft-reset]');if(!btn||btn.disabled)return;
   const b=loadBuilder(),id=btn.dataset.ftLock||btn.dataset.ftExclude,name=btn.dataset.ftName||id;
   if(btn.hasAttribute('data-ft-reset')){saveBuilder({count:5,cap:null,locked:[],excluded:[],open:true});STATE.search='';rerender();return;}
   const list=btn.hasAttribute('data-ft-lock')?'locked':'excluded',other=list==='locked'?'excluded':'locked';
   if(b[list].some(x=>x.id===id))b[list]=b[list].filter(x=>x.id!==id);
   else{if(list==='locked'&&b.locked.length>=3)return;b[list].push({id,name});b[other]=b[other].filter(x=>x.id!==id);}
   b.open=true;saveBuilder(b);rerender();
  };
  host.onchange=e=>{
   if(e.target.id!=='ftCount'&&e.target.id!=='ftCap')return;
   const b=loadBuilder(),v=e.target.value===''?null:Number(e.target.value);
   if(e.target.id==='ftCount')b.count=COUNTS.includes(v)?v:5;else b.cap=CAPS.includes(v)?v:null;
   b.open=true;saveBuilder(b);rerender();
  };
  host.oninput=e=>{if(e.target.id==='ftSearch'){STATE.search=e.target.value;applySearch(host);}};
  host.ontoggle=null;const builder=host.querySelector('details.ft-builder');
  if(builder)builder.ontoggle=()=>{const b=loadBuilder();if(b.open!==builder.open){b.open=builder.open;saveBuilder(b);}};
 }catch(e){
  if(ctx.statusEl){ctx.statusEl.textContent='Fanatics slips unavailable: '+e.message+' Nothing is shown rather than guessing.';ctx.statusEl.dataset.level='error';}
  const keep=focusPanel&&host.contains(focusPanel)?focusPanel:null;
  if(keep){for(const child of [...host.childNodes])if(child!==keep)child.remove();const warning=root.document.createElement('p');warning.className='gc-empty ft-empty';warning.textContent='Fanatics slips unavailable: '+e.message;host.appendChild(warning);}
  else host.innerHTML=`<p class="gc-empty ft-empty">Fanatics slips unavailable: ${esc(e.message)}</p>`;
 }
}
const api={buildLegs,rosterAvailability,optionMarkup,termsMarkup,statusFor,render,legWhy,loadManual,saveManual,loadBuilder,saveBuilder,_state:STATE};
root.GoingFanaticsTDUI=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis==='undefined'?this:globalThis);
