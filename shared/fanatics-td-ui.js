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
const pct=p=>p>=.1?(100*p).toFixed(0)+'%':(100*p).toFixed(1)+'%';

// ---- manual price store (browser only) ----
let memory=[];
function loadManual(now,maxMinutes){
 let list=memory;
 try{const raw=root.localStorage?.getItem(STORE_KEY);if(raw)list=JSON.parse(raw);}catch{}
 memory=(Array.isArray(list)?list:[]).filter(e=>e&&e.playerId&&Number.isFinite(e.american)&&now-Date.parse(e.enteredAt)<=maxMinutes*60000);
 return memory;
}
function saveManual(list){memory=list;try{root.localStorage?.setItem(STORE_KEY,JSON.stringify(list));}catch{}}

// ---- roster screen (ESPN, via /api/promo-availability): the page's existing independent check ----
function rosterAvailability(info,p,ctx){
 const now=ctx.now;
 if(!info||!Array.isArray(info.teams)||!Number.isFinite(Date.parse(info.checkedAt))||now-Date.parse(info.checkedAt)>10*60000)return 'unknown';
 const team=info.teams.filter(t=>key(t.team)===key(p.team)||(ctx.resolveTeam&&ctx.resolveTeam(t.team)===ctx.resolveTeam(p.team)));
 const hits=team.flatMap(t=>t.players||[]).filter(r=>r.key===key(p.player));
 return hits.length===1?hits[0].availability:'unknown';
}

// Build engine legs from the page's props. One leg per player; the price is a real Fanatics quote or a price the user typed from Fanatics, never another book.
function buildLegs(ctx,manual=[]){
 const now=ctx.now,day=ctx.slateDate,byPlayer=new Map();
 for(const p of ctx.props||[]){
  if(p.market!=='atd'||!p.profileId||p.dfs||!(p.line==null||p.line===.5))continue;
  if(ctx.currentWeekProp&&!ctx.currentWeekProp(p))continue;
  const kick=Date.parse(p.kickoff);if(!Number.isFinite(kick)||etDay(kick)!==day)continue;
  const rec=byPlayer.get(p.profileId)||{any:null,fanatics:null};
  if(!rec.any||Date.parse(p.updatedAt)>Date.parse(rec.any.updatedAt))rec.any=p;
  if(String(p.bookKey||p.book).toLowerCase()==='fanatics'&&Number.isFinite(p.overOdds)&&(!rec.fanatics||Date.parse(p.updatedAt)>Date.parse(rec.fanatics.updatedAt)))rec.fanatics=p;
  byPlayer.set(p.profileId,rec);
 }
 const manualBy=new Map(manual.map(m=>[m.playerId,m]));
 const legs=[],pool=[],stats={players:byPlayer.size,fanaticsFeed:0,manual:0,noPrice:0};
 for(const [playerId,rec] of byPlayer){
  const p=rec.any,teams=Array.isArray(p.eventTeams)&&p.eventTeams.length===2?[...p.eventTeams].sort():null;
  pool.push({playerId,player:p.player});
  let price=null;
  if(rec.fanatics){stats.fanaticsFeed++;price={american:rec.fanatics.overOdds,source:'feed',book:'fanatics',updatedAt:rec.fanatics.updatedAt};}
  const m=manualBy.get(playerId);
  if(m&&(!price||Date.parse(m.enteredAt)>Date.parse(price.updatedAt))){price={american:m.american,source:'manual',book:'fanatics',updatedAt:m.enteredAt};stats.manual++;}
  if(!price)stats.noPrice++;
  const model=ctx.probability?ctx.probability(p):null;
  const dec=ctx.eligibility?ctx.eligibility(playerId,p):null;
  const profile=ctx.profiles?.[playerId];
  legs.push({playerId,player:p.player,team:p.team,opp:p.opp,event:teams?teams.join('|')+'|'+p.kickoff:null,gameLabel:p.homeName&&p.awayName?`${p.awayName} @ ${p.homeName}`:'',kickoff:p.kickoff,
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
function legMarkup(l,now,F_){
 const src=l.price.source==='manual'?`entered by you ${esc(ago(l.price.updatedAt,now))}`:`Fanatics feed ${esc(ago(l.price.updatedAt,now))}`;
 return `<li class="ft-leg"><div class="ft-leg-top"><b>${esc(l.player)}</b> <span>${esc(l.team||'')}${l.opp?' vs '+esc(l.opp):''}</span><span class="ft-odds">${esc(F_.fmtAmerican(l.price.american))}</span></div>
 <div class="ft-leg-sub">${l.gameLabel?esc(l.gameLabel)+' · ':''}${esc(etTime(l.kickoff))} · price: ${src}</div>
 <div class="ft-leg-sub">${esc(legWhy(l))}</div>
 <div class="ft-leg-sub">Availability: ${esc(LEG_STATE[l.availability]||l.availability)} · ${esc(l.eligibility?.label||'')}${l.eligibility?.caution?' (caution)':''}. Not official game-day clearance.</div></li>`;
}
function optionMarkup(o,i,ctx){
 const F_=F(),now=ctx.now,oldest=Math.min(...o.legs.map(l=>Date.parse(l.price.updatedAt))),manualUsed=o.legs.some(l=>l.price.source==='manual');
 const margin=(o.decimal/F_.decimal(ctx.terms.minCombinedAmerican)-1)*100;
 return `<article class="sig-card ft-card" data-rank="${i+1}"><div class="best-card-badges"><span class="best-badge go">#${i+1}</span><span class="best-badge">${esc(F_.fmtAmerican(o.american))} combined</span><span class="best-badge watch">UNVERIFIED OFFER RULES</span></div>
 <h3>${o.legs.map(l=>esc(l.player)).join(' + ')}</h3>
 <p class="ft-headline"><b>${pct(o.probability)}</b> estimated chance all three score <small>(model estimate assuming three different games are independent; not a proven hit rate)</small></p>
 <p class="ft-odds-line">Combined price ${esc(F_.fmtAmerican(o.american))} = ${o.decimal.toFixed(2)}x (${o.legs.map(l=>F_.decimal(l.price.american).toFixed(2)).join(' × ')}); clears the ${esc(F_.fmtAmerican(ctx.terms.minCombinedAmerican))} minimum by ${margin.toFixed(1)}%. Oldest price ${esc(ago(new Date(oldest).toISOString(),now))}${manualUsed?'; includes prices you entered':''}.</p>
 <ol class="ft-legs">${o.legs.map(l=>legMarkup(l,now,F_)).join('')}</ol>
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
 const s=legsInfo.stats,reasons=result.reasons||[],ex=Object.entries(result.excluded||{}).map(([k,v])=>`${v} ${k.toLowerCase()}`).join('; ');
 if(result.options.length)return {level:'ok',text:`${result.options.length} qualifying slip${result.options.length===1?'':'s'} from ${result.eligiblePlayers} eligible players in ${result.eligibleGames} games. ${reasons.join(' ')} ${ex?'Excluded: '+ex+'.':''}`};
 if(!s.fanaticsFeed&&!s.manual)return {level:'unavailable',text:`NO FANATICS PRICES: the odds feed currently has no Fanatics anytime-touchdown prices (${s.players} players have a game this Sunday; ${s.noPrice} have no Fanatics price). Nothing qualifies and no other sportsbook's price is substituted. Enter the Fanatics prices you see in their app below to build slips.`};
 return {level:'none',text:`No qualifying slip. ${reasons.join(' ')} ${ex?'Excluded: '+ex+'.':''}`};
}

// ---- DOM ----
const STATE={manualText:''};
function render(host,ctx){
 if(!host||!ctx)return;
 const F_=F(),now=ctx.now??Date.now();
 const terms=F_.validateTerms({...(ctx.termsOverride||{})});
 let html='';
 try{
  const manual=loadManual(now,terms.manualMaxAgeMinutes),{legs,pool,stats}=buildLegs({...ctx,now},manual);
  const result=F_.select(legs,{now,terms,excludedPlayers:ctx.excludedPlayers||[]});
  const st=statusFor(result,{stats},ctx),full={...ctx,now,terms};
  if(ctx.statusEl){ctx.statusEl.textContent=st.text;ctx.statusEl.dataset.level=st.level;}
  html+=termsMarkup();
  html+=`<details class="ft-manual" ${st.level==='unavailable'?'open':''}><summary>Enter Fanatics prices you can see (${manual.length} saved, valid ${terms.manualMaxAgeMinutes} min)</summary>
   <p class="bt-note">One player per line, anytime-TD American odds from the Fanatics app, for example <code>Amon-Ra St. Brown +120</code>. Prices stay in this browser only and expire after ${terms.manualMaxAgeMinutes} minutes; they are labelled "entered by you" on every slip.</p>
   <textarea id="ftManual" rows="6" spellcheck="false" aria-label="Fanatics anytime touchdown prices">${esc(STATE.manualText)}</textarea><div class="ft-actions"><button type="button" id="ftApply">Use these prices</button><button type="button" id="ftClear">Clear saved prices</button></div><div id="ftManualMsg" role="status"></div></details>`;
  if(result.options.length)html+=`<div class="ft-list">${result.options.map((o,i)=>optionMarkup(o,i,full)).join('')}</div>`;
  else html+=`<p class="gc-empty ft-empty">${esc(st.text)}</p>`;
  host.innerHTML=html;
  const area=host.querySelector('#ftManual'),msg=host.querySelector('#ftManualMsg');
  host.querySelector('#ftApply')?.addEventListener('click',()=>{
   STATE.manualText=area.value;const parsed=F_.parseManualPrices(area.value,pool,Date.now());
   const keep=loadManual(Date.now(),terms.manualMaxAgeMinutes).filter(m=>!parsed.entries.some(e=>e.playerId===m.playerId));
   saveManual([...keep,...parsed.entries]);
   if(ctx.onChange)ctx.onChange();else render(host,{...ctx,now:Date.now()});
   const m2=host.querySelector('#ftManualMsg');if(m2)m2.textContent=`${parsed.entries.length} price${parsed.entries.length===1?'':'s'} used.${parsed.errors.length?' Problems: '+parsed.errors.join(' '):''}`;
  });
  host.querySelector('#ftClear')?.addEventListener('click',()=>{STATE.manualText='';saveManual([]);if(ctx.onChange)ctx.onChange();else render(host,{...ctx,now:Date.now()});});
 }catch(e){
  if(ctx.statusEl){ctx.statusEl.textContent='Fanatics slips unavailable: '+e.message+' Nothing is shown rather than guessing.';ctx.statusEl.dataset.level='error';}
  host.innerHTML=`<p class="gc-empty ft-empty">Fanatics slips unavailable: ${esc(e.message)}</p>`;
 }
}
const api={buildLegs,rosterAvailability,optionMarkup,termsMarkup,statusFor,render,legWhy,loadManual,saveManual,_state:STATE};
root.GoingFanaticsTDUI=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis==='undefined'?this:globalThis);
