(function(root){
'use strict';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const S={mode:'fantasy',window:'season',cat:'all',pos:'ALL',team:'ALL',limit:12,host:null,ctx:{},ovp:undefined,score:undefined};
const FCAT={all:'All',buy_low:'Buy low',emerging:'Emerging opportunity',stash:'Waiver / stash',sell_high:'Sell high / avoid',monitor:'Monitor'};
const FNOTE={buy_low:'Scored below a real opportunity. Descriptive only: such gaps have not predicted future points in our tests.',emerging:'Role is growing and GOING Score supports it.',stash:'Growing role, modest current usage.',sell_high:'Scoring ahead of opportunity or a shrinking role. Not a prediction of a collapse.',monitor:'High opportunity, but a current injury report: check status before acting.'};
async function load(){
 if(S.ovp===undefined){try{S.ovp=await (await fetch('/data/charts/opportunity_vs_production.json',{cache:'no-cache'})).json();}catch{S.ovp=null;}}
 if(S.score===undefined){try{S.score=await (await fetch('/data/going_score.json',{cache:'no-cache'})).json();}catch{S.score=null;}}
}
const ago=t=>{const ms=Date.now()-Date.parse(t);if(!Number.isFinite(ms))return 'time unknown';const h=Math.round(ms/3600000);return h<1?'under an hour ago':h<48?h+' h ago':Math.round(h/24)+' days ago';};
const AVCLS={active:'ok',questionable:'warn',dnp:'warn',limited:'warn',doubtful:'bad',out:'bad',reserve:'bad',returning:'warn',unknown:'warn',stale:'bad',inactive_roster:'bad'};
const badge=a=>`<span class="gt-av ${AVCLS[a.state]||'warn'}" title="${esc(a.detail)}">${esc(a.label)}</span>`;
const spark=(vals,label)=>root.GoingCharts&&vals.filter(finite).length>=2?root.GoingCharts.sparkline(vals.filter(finite),{label}):'';
const link=id=>'/players/?player='+encodeURIComponent(id);
function fcard(p){
 return `<article class="gs-card gt-card"><div class="gs-top"><div><h3>${esc(p.name)}</h3><small>${esc(p.pos)} · ${esc(p.team)} · ${p.games} games</small></div><div class="gs-score"><strong>${esc(FCAT[p.category]||p.category)}</strong>${p.score!=null?`<small>GOING Score ${Math.round(p.score)}</small>`:''}</div></div>
 <p class="gt-line">${badge(p.availability)} ${spark(p.series.map(x=>x.exp),'Expected points by week')}<small>expected</small> ${spark(p.series.map(x=>x.act),'Actual points by week')}<small>actual</small></p>
 <ul class="gt-why">${p.why.map(x=>`<li><b>Why</b> ${esc(x)}</li>`).join('')}${p.concern.map(x=>`<li class="c"><b>Concern</b> ${esc(x)}</li>`).join('')}</ul>
 <div class="gs-actions"><a href="${link(p.id)}">Player card</a><a href="/long/?tab=score">GOING Score</a></div></article>`;
}
function bcard(t){
 const price=t.priced?`${esc(t.direction)} ${esc(t.line)} at ${esc(t.odds>0?'+'+t.odds:t.odds)} (${esc(t.book||'book')}, quote ${esc(ago(t.updatedAt))})`:'No posted line in our feed';
 const prob=t.prob!=null?`${(t.prob*100).toFixed(0)}% model probability. ${esc(t.calibration)}.`:'';
 const val=t.ev!=null?`Market-shrunk value ${(t.ev*100).toFixed(1)}% on this exact price (de-vigged price with a ${Math.round(GoingTargets.RULES.marketWeight*100)}% model weight; model-only estimate ${t.evModelOnly!=null?(t.evModelOnly*100).toFixed(1)+'%':'n/a'}). A price comparison, not proof of an edge.`:t.evWithheld?'Estimated value withheld: model and price disagree too much to trust.':t.evUnavailable&&t.priced?'No value estimate: the sportsbook margin cannot be removed from a one-sided price.':'No estimated value: needs a posted price.';
 return `<article class="gs-card gt-card"><div class="gs-top"><div><h3>${esc(t.name)}</h3><small>${esc(t.pos)} · ${esc(t.team)} · ${esc(t.marketLabel)}</small></div><div class="gs-score"><strong>${esc(t.direction)}</strong><small>${esc(t.status)}</small></div></div>
 <p class="gt-line">${badge(t.availability)}</p>
 <dl class="gt-tiers"><dt>1. Opportunity signal</dt><dd>${esc(t.opportunity.signal)} <small>${esc(t.opportunity.evidence)} ${esc(t.opportunity.beyondPrice)}</small></dd>
 <dt>2. Price check</dt><dd><span class="gt-price">${price}</span><br>${prob} ${val}</dd>
 <dt>3. Recommendation</dt><dd>${esc(t.recommendation.text)}</dd></dl>
 <ul class="gt-why">${t.concern.map(x=>`<li class="c"><b>Concern</b> ${esc(x)}</li>`).join('')}</ul>
 <div class="gs-actions"><a href="${link(t.id)}">Player card</a><a href="/long/?tab=props">Markets</a><a href="/long/?tab=score">GOING Score</a></div></article>`;
}
function weekOf(inj){let w=0;for(const v of Object.values(inj?.current_players||{}))if(Number.isFinite(v.roster_week)&&v.roster_week>w)w=v.roster_week;return w||null;}
function draw(){
 const host=S.host,T=root.GoingTargets,c=S.ctx;if(!host||!T)return;
 const inj=c.injury;if(!inj){host.innerHTML='<p class="gc-empty">Injury and roster data have not loaded, so no targets are shown (availability cannot be confirmed).</p>';return;}
 const week=weekOf(inj),common={profiles:c.profiles||{},injury:inj,roster:c.roster,week,now:Date.now(),pos:S.pos};
 const teams=[...new Set(Object.values(c.profiles||{}).map(p=>p.team).filter(Boolean))].sort();
 const head=`<div class="charts-chips" role="group" aria-label="Target type"><button type="button" data-gt-mode="fantasy" aria-pressed="${S.mode==='fantasy'}">Fantasy targets</button><button type="button" data-gt-mode="betting" aria-pressed="${S.mode==='betting'}">Betting targets</button></div>`;
 const filters=`<div class="charts-filters"><label>Position<select data-gt="pos">${(S.mode==='betting'?['ALL','RB','WR','TE']:['ALL','QB','RB','WR','TE']).map(p=>`<option ${p===S.pos?'selected':''}>${p}</option>`).join('')}</select></label><label>Team<select data-gt="team"><option>ALL</option>${teams.map(t=>`<option ${t===S.team?'selected':''}>${esc(t)}</option>`).join('')}</select></label>${S.mode==='fantasy'?`<label>Window<select data-gt="window"><option value="season" ${S.window==='season'?'selected':''}>Season to date</option><option value="l3" ${S.window==='l3'?'selected':''}>Last 3 games</option></select></label><label>Category<select data-gt="cat">${Object.entries(FCAT).map(([k,v])=>`<option value="${k}" ${k===S.cat?'selected':''}>${v}</option>`).join('')}</select></label>`:''}</div>`;
 const stamp=`<p class="bt-note"><b>Availability data:</b> injury and roster snapshot ${esc(ago(inj.generated_at))} (${esc(inj.generated_at||'unknown')}). Players on injured reserve or other reserve lists, suspended, retired, off the roster, not seen in 21+ days, or not found in the roster snapshot are excluded from recommendations. Game-day inactives are announced about 90 minutes before kickoff; re-check then. GOING Score data as of ${esc(S.score?.as_of||'unknown')}.</p>`;
 let body;
 if(S.mode==='fantasy'){
  if(!S.ovp){body='<p class="gc-empty">Opportunity data is not published yet; it is built by the weekly refresh.</p>';}
  else{
   const r=T.fantasyTargets({...common,ovp:{players:(S.ovp.data?.players||S.ovp.players||[])},score:S.score,window:S.window});
   const keep=p=>(S.pos==='ALL'||p.pos===S.pos)&&(S.team==='ALL'||p.team===S.team);
   const cats=S.cat==='all'?['buy_low','emerging','stash','sell_high','monitor']:[S.cat];
   body=cats.map(k=>{const rows=r.categories[k].filter(keep);return `<h4>${esc(FCAT[k])} <small>(${rows.length})</small></h4><p class="bt-note">${esc(FNOTE[k])}</p>${rows.length?`<div class="gs-list">${rows.slice(0,S.limit).map(fcard).join('')}</div>`:'<p class="gc-empty">No players meet the evidence rules right now.</p>'}`;}).join('');
   const un=r.unavailable.filter(keep),ret=un.filter(x=>x.availability.stashOnly);
   if(ret.length)body+=`<h4>Returning from injury (stash only) <small>(${ret.length})</small></h4><p class="bt-note">Not available now. A stash candidate only; not a start or a bet until active.</p><div class="gs-list">${ret.slice(0,S.limit).map(fcard).join('')}</div>`;
   body+=`<details class="gt-un"><summary>Not available (${un.length}): excluded from every list above</summary>${un.slice(0,40).map(p=>`<p>${esc(p.name)} ${esc(p.pos)} · ${esc(p.team)}: ${badge(p.availability)} ${esc(p.availability.detail)}</p>`).join('')||'<p>None.</p>'}${un.length>40?`<p>…and ${un.length-40} more.</p>`:''}</details>`;
  }
 }else{
  const cands=(typeof c.candidates==='function'?c.candidates():c.candidates)||[];
  const r=T.bettingTargets(common,cands);
  const rows=r.targets.filter(t=>(S.team==='ALL'||t.team===S.team)&&(S.pos==='ALL'||t.pos===S.pos));
  const priced=rows.filter(t=>t.priced),unpriced=rows.filter(t=>!t.priced);
  body=`<p class="bt-note">These are players whose usage trends justify <b>research</b>. A role change is not a sportsbook edge: trends were validated for next-game volume, not for beating prices. Estimated value appears only for a fresh posted price and is withheld when the model and book disagree too much.</p>
  <h4>With a posted price <small>(${priced.length})</small></h4>${priced.length?`<div class="gs-list">${priced.slice(0,S.limit).map(bcard).join('')}</div>`:'<p class="gc-empty">No priced targets right now.</p>'}
  <h4>Research targets without a price <small>(${unpriced.length})</small></h4>${unpriced.length?`<div class="gs-list">${unpriced.slice(0,S.limit).map(bcard).join('')}</div>`:'<p class="gc-empty">None.</p>'}
  <details class="gt-un"><summary>Excluded for availability (${r.excluded.length})</summary>${r.excluded.slice(0,40).map(x=>`<p>${esc(x.name)} ${esc(x.pos)} · ${esc(x.team)}, ${esc(T.MARKET_LABEL[x.market])}: ${esc(x.reason)}. ${esc(x.detail)}</p>`).join('')||'<p>None.</p>'}</details>`;
 }
 host.innerHTML=head+filters+stamp+body+`<p class="bt-note">Showing up to ${S.limit} per list. <button type="button" data-gt-more>Show more</button></p>`;
}
async function render(host,ctx){
 if(!host)return;S.host=host;S.ctx=ctx||{};
 if(!host.dataset.gtBound){host.dataset.gtBound='1';
  host.addEventListener('click',e=>{const m=e.target.closest('[data-gt-mode]');if(m){S.mode=m.dataset.gtMode;draw();return;}if(e.target.closest('[data-gt-more]')){S.limit+=12;draw();}});
  host.addEventListener('change',e=>{const k=e.target.dataset?.gt;if(k){S[k]=e.target.value;S.limit=12;draw();}});}
 host.innerHTML='<p class="bt-note">Loading targets…</p>';await load();draw();
}
root.GoingTargetsUI={render,state:S};
if(typeof module!=='undefined')module.exports=root.GoingTargetsUI;
})(globalThis);
