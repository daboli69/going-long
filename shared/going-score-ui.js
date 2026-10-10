(function(root){
'use strict';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const S={doc:null,loaded:null,pos:'ALL',team:'ALL',tier:'ALL',q:'',sort:'score',limit:25,compare:[],open:new Set(),host:null};
const LABEL={opportunity:'Opportunity',team_share:'Team share',efficiency:'Efficiency',availability:'Availability',role:'Role',production:'Production',opp_trend:'Opportunity trend'};
async function ensure(){
 if(S.loaded)return S.loaded;
 S.loaded=(async()=>{try{const r=await fetch('/data/going_score.json',{cache:'no-cache'});if(!r.ok)throw Error('missing');const doc=await r.json(),m=root.GoingScorePlayer.load(doc);if(!m.ok)throw Error(m.reason);S.doc=m;return m;}catch(e){S.doc=null;return null;}})();
 return S.loaded;
}
const delta=v=>!finite(v)?'':`<span class="gs-delta ${v>0?'up':v<0?'down':''}">${v>0?'▲':v<0?'▼':'—'} ${Math.abs(v).toFixed(1)}</span>`;
function spark(p){const v=(p.history||[]).map(h=>h.score).filter(finite);return root.GoingCharts?root.GoingCharts.sparkline(v,{label:'Score history'}):'';}
function breakdown(p){
 const rows=root.GoingScorePlayer.contributions(p),max=Math.max(...rows.map(r=>Math.abs(r.contribution)),.01);
 return `<ul class="gs-parts">${rows.map(r=>`<li><span>${esc(LABEL[r.key]||r.key)}<small>${Math.round(r.percentile)}th percentile · weight ${Math.round(r.weight*100)}%</small></span><i class="${r.contribution>=0?'pos':'neg'}" style="width:${Math.max(3,Math.abs(r.contribution)/max*100)}%"></i><b>${r.contribution>0?'+':''}${r.contribution.toFixed(2)}</b><em>${esc(r.explanation||'')}</em></li>`).join('')}</ul>`;
}
function card(p){
 const open=S.open.has(p.id),d=root.GoingScorePlayer.drivers(p,1),checked=S.compare.includes(p.id);
 return `<article class="gs-card"><div class="gs-top"><b class="gs-rank">${p.listRank}</b><div><h3>${esc(p.name)}</h3><small>${esc(p.position)} · ${esc(p.team)} · position rank ${p.rank} of ${p.of}</small></div><div class="gs-score"><strong>${Math.round(p.score)}</strong><small>${esc(p.tier?.label||'')}</small></div></div>
 <p class="gs-line">${spark(p)} ${delta(p.delta_3w)} <small>vs 3 weeks ago</small>${(p.flags||[]).map(f=>`<span class="gs-flag">${esc(f.replace(/_/g,' ').replace(':',' '))}</span>`).join('')}</p>
 <p class="gs-why">${d.up[0]?`Lifted by ${esc((LABEL[d.up[0].key]||d.up[0].key).toLowerCase())}. `:''}${d.down[0]?`Held back by ${esc((LABEL[d.down[0].key]||d.down[0].key).toLowerCase())}.`:''}</p>
 <details data-id="${esc(p.id)}" ${open?'open':''}><summary>Why this score</summary>${open?breakdown(p):''}</details>
 <div class="gs-actions"><a href="/players/?player=${encodeURIComponent(p.id)}">Player card</a><label><input type="checkbox" data-compare="${esc(p.id)}" ${checked?'checked':''}> Compare</label></div></article>`;
}
function compareMarkup(){
 const [a,b]=S.compare.map(id=>S.doc.byId[id]),G=root.GoingScorePlayer;if(!a||!b)return S.compare.length?'<p class="bt-note">Pick one more player to compare.</p>':'';
 const c=G.compare(a,b);
 return `<section class="gs-compare"><h3>${esc(a.name)} vs ${esc(b.name)}</h3><p class="bt-note">${esc(c.note)} Score ${a.score} vs ${b.score}.</p><table><thead><tr><th>Component</th><th>${esc(a.name)}</th><th>${esc(b.name)}</th></tr></thead><tbody>${c.components.filter(r=>r.aPercentile!=null||r.bPercentile!=null).map(r=>`<tr><td>${esc(LABEL[r.key]||r.key)}</td><td>${r.aPercentile==null?'—':Math.round(r.aPercentile)}</td><td>${r.bPercentile==null?'—':Math.round(r.bPercentile)}</td></tr>`).join('')}</tbody></table></section>`;
}
function draw(){
 const G=root.GoingScorePlayer,doc=S.doc;if(!S.host)return;
 if(!doc){S.host.innerHTML='<p class="gc-empty">The player score file is not available yet. It is built by the weekly refresh.</p>';return;}
 const teams=[...new Set(doc.players.map(p=>p.team).filter(Boolean))].sort();
 let rows=G.filter(doc.players,{position:S.pos==='ALL'?null:S.pos,team:S.team==='ALL'?null:S.team,tier:S.tier==='ALL'?null:S.tier,search:S.q});
 rows=G.rank(rows,S.sort);
 const mv=G.movers(doc.players.filter(p=>(S.pos==='ALL'||p.position===S.pos)),{limit:5,minAbsChange:5});
 const m=doc.meta,av=m.availability,avWarn=av&&av.ok===false?`<p class="bt-note gt-warn"><b>Availability data was stale when this was built</b> (${esc(av.reason)}). Players known to be unavailable are excluded; others are not confirmed active.</p>`:'';
 S.host.innerHTML=`${avWarn}<p class="bt-note"><b>What this is:</b> ${esc(m.meaning)} Season ${m.season}, through week ${m.week-1}. Method ${esc(m.methodology_version)}. Validated modestly: it matches trailing expected points for QB/RB/WR and beats it only for TE (docs/GOING_SCORE.md).</p>
 <div class="gs-filters"><label>Position<select data-gs="pos">${['ALL','QB','RB','WR','TE'].map(x=>`<option ${x===S.pos?'selected':''}>${x}</option>`).join('')}</select></label><label>Team<select data-gs="team"><option>ALL</option>${teams.map(t=>`<option ${t===S.team?'selected':''}>${esc(t)}</option>`).join('')}</select></label><label>Tier<select data-gs="tier">${['ALL','elite','strong','solid','modest','low'].map(x=>`<option ${x===S.tier?'selected':''}>${x}</option>`).join('')}</select></label><label>Sort<select data-gs="sort">${[['score','Score'],['delta_3w','3-week change'],['opportunity','Opportunity'],['availability','Availability']].map(([k,l])=>`<option value="${k}" ${k===S.sort?'selected':''}>${l}</option>`).join('')}</select></label><label>Search<input type="search" data-gs="q" value="${esc(S.q)}" placeholder="Player name"></label></div>
 <div class="gs-movers"><div><h4>Biggest risers (3 weeks)</h4>${mv.risers.map(p=>`<span>${esc(p.name)} ${delta(p.delta_3w)}</span>`).join('')||'<small>None</small>'}</div><div><h4>Biggest fallers</h4>${mv.fallers.map(p=>`<span>${esc(p.name)} ${delta(p.delta_3w)}</span>`).join('')||'<small>None</small>'}</div></div>
 ${compareMarkup()}<p class="bt-note">${rows.length} players. A higher score means a better underlying situation, not a better bet.</p>
 <div class="gs-list">${rows.slice(0,S.limit).map(card).join('')}</div>${rows.length>S.limit?`<button type="button" data-gs-more>Show 25 more</button>`:''}`;
}
function render(host){
 if(!host||!root.GoingScorePlayer)return;S.host=host;
 if(!host.dataset.bound){host.dataset.bound='1';
  host.addEventListener('change',e=>{const k=e.target.dataset?.gs;if(k){S[k]=e.target.value;S.limit=25;draw();return;}const c=e.target.dataset?.compare;if(c){S.compare=e.target.checked?[...S.compare,c].slice(-2):S.compare.filter(x=>x!==c);draw();}});
  host.addEventListener('input',e=>{if(e.target.dataset?.gs==='q'){S.q=e.target.value;S.limit=25;const pos=e.target.selectionStart;draw();const el=host.querySelector('[data-gs="q"]');el?.focus();el?.setSelectionRange(pos,pos);}});
  host.addEventListener('click',e=>{if(e.target.closest('[data-gs-more]')){S.limit+=25;draw();}});
  host.addEventListener('toggle',e=>{const d=e.target;if(d.tagName==='DETAILS'&&d.dataset.id){if(d.open){S.open.add(d.dataset.id);if(!d.querySelector('.gs-parts'))d.insertAdjacentHTML('beforeend',breakdown(S.doc.byId[d.dataset.id]));}else S.open.delete(d.dataset.id);}},true);}
 host.innerHTML='<p class="bt-note">Loading player scores…</p>';ensure().then(draw);
}
root.GoingScoreUI={render,state:S};
if(typeof module!=='undefined')module.exports=root.GoingScoreUI;
})(globalThis);
