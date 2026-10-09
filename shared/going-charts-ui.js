(function(root){
'use strict';
const C=()=>root.GoingCharts,esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const state={chart:'opp',pos:'ALL',team:'ALL',min:3,host:null,ctx:{},cache:{}};
const COLORS={QB:'#7aa7ff',RB:'#35e0c3',WR:'#e0a43a',TE:'#ff7a90'};
async function load(name){
 if(state.cache[name]!==undefined)return state.cache[name];
 try{const r=await fetch('/data/charts/'+name+'.json',{cache:'no-cache'});if(!r.ok)throw Error('missing');state.cache[name]=await r.json();}catch{state.cache[name]=null;}
 return state.cache[name];
}
const link=id=>'/players/?player='+encodeURIComponent(id);
const stale=(doc)=>{const t=Date.parse(doc?.as_of||doc?.generated_at);return !Number.isFinite(t)||Date.now()-t>9*86400000;};
const note=(doc,kind)=>`<p class="bt-note"><span class="charts-badge ${kind==='pred'?'pred':'desc'}">${kind==='pred'?'PREDICTIVE (validated)':'DESCRIPTIVE'}</span> ${doc?.as_of?`Data through ${esc(String(doc.as_of).slice(0,10))}.`:''}${doc&&stale(doc)?' <b>Older than a week: the weekly refresh may be behind.</b>':''}</p>`;
const CHARTS={
 opp:{label:'Opportunity vs production',file:'opportunity_vs_production',kind:'desc',help:'Expected fantasy points from workload and field position against actual points. Above the line = scored more than the opportunity predicts. Residuals are descriptive: they are not a promise of regression.',
  render(doc){const rows=filter(doc.rows).filter(r=>finite(r.expected)&&finite(r.actual)&&(r.games||0)>=state.min).map(r=>({id:r.id,label:`${r.name} (${r.position} ${r.team})`,x:r.expected,y:r.actual,group:r.position,href:link(r.id),note:`${r.games} games, residual ${(r.actual-r.expected).toFixed(1)}`}));
   return C().scatter(rows,{identity:true,fit:true,xLabel:'Expected PPR (season to date)',yLabel:'Actual PPR',colors:COLORS,title:'Expected vs actual PPR'});}},
 regress:{label:'Regression candidates',file:'opportunity_vs_production',kind:'desc',help:'Largest gaps between actual and expected points per game. A large positive gap means recent scoring ran ahead of opportunity; do not treat it as guaranteed regression or betting value.',
  render(doc){const rows=filter(doc.rows).filter(r=>finite(r.expected)&&finite(r.actual)&&(r.games||0)>=Math.max(3,state.min)).map(r=>({id:r.id,label:`${r.name} ${r.position}·${r.team}`,value:(r.actual-r.expected)/r.games,href:link(r.id),note:`${r.games} games`})).sort((a,b)=>b.value-a.value);
   const top=rows.slice(0,8),bottom=rows.slice(-8).reverse();return `<h4>Scored above opportunity (points per game)</h4>${C().bars(top,{title:'Positive residuals'})}<h4>Scored below opportunity</h4>${C().bars(bottom,{title:'Negative residuals'})}`;}},
 roles:{label:'Role expansion / contraction',file:null,kind:'desc',help:'Change in share of team targets or carries, and in snap share, over the last 3 games versus the last 6 (public nflverse). Describes opportunity; it is not a forecast.',
  render(){const profiles=Object.values(state.ctx.profiles||{}),I=root.GoingIntel;if(!I)return '<p class="gc-empty">Intelligence module unavailable.</p>';
   const rows=[];for(const p of profiles){if(!['WR','TE','RB'].includes(p.position)||!I.activeProfile(p)||(state.pos!=='ALL'&&p.position!==state.pos)||(state.team!=='ALL'&&p.team!==state.team))continue;const series=I.roleSeries(p.role_trend,p.position);if(!series.length||!(p.role_trend?.snap_share?.l6>=30))continue;const lead=series.slice().sort((a,b)=>Math.abs(b.change/(b.metric==='snap_share'?8:b.metric==='target_share'?.03:.05))-Math.abs(a.change/(a.metric==='snap_share'?8:a.metric==='target_share'?.03:.05)))[0];rows.push({id:p.id,label:`${p.name} ${p.position}·${p.team}`,value:lead.metric==='snap_share'?lead.change:lead.change*100,href:link(p.id),note:`${lead.label} ${lead.fmt(lead.l6)} → ${lead.fmt(lead.l3)}`,size:Math.abs(lead.change/(lead.metric==='snap_share'?8:lead.metric==='target_share'?.03:.05))});}
   rows.sort((a,b)=>b.size-a.size);const top=rows.slice(0,24).sort((a,b)=>b.value-a.value);return `<p class="bt-note">Largest movers (points of share, last 6 → last 3). ${rows.length} active players with a meaningful role.</p>${C().bars(top,{title:'Role change'})}`;}},
 scoring:{label:'Scoring opportunity',file:null,kind:'pred',help:'Expected touchdowns per game from carries and targets by field zone (x) against touchdowns actually scored per game (y), last 12 games. Expected TDs predicted anytime-TD scoring beyond the Champion rate in the 2025 holdout; the gap itself is descriptive.',
  render(){const rows=[];for(const p of Object.values(state.ctx.profiles||{})){const s=p.scoring_role;if(!s||s.confidence==='low'||!finite(s.xtd_pg_l12)||!finite(s.td_pg_l12)||(state.pos!=='ALL'&&p.position!==state.pos)||(state.team!=='ALL'&&p.team!==state.team)||!root.GoingIntel?.activeProfile(p))continue;rows.push({id:p.id,label:`${p.name} (${p.position} ${p.team})`,x:s.xtd_pg_l12,y:s.td_pg_l12,group:p.position,href:link(p.id),note:`${s.tier.toLowerCase()} role, ${Math.round(s.xtd_share_l6*100)}% of team xTD`});}
   return C().scatter(rows,{identity:true,fit:true,xLabel:'Expected TDs per game',yLabel:'Actual TDs per game',colors:COLORS,title:'Expected vs actual touchdowns'});}},
 calibration:{label:'Model calibration',file:'model_calibration',kind:'pred',help:'How often outcomes happened versus the model probability, from settled tracker predictions. Points on the diagonal are well calibrated; small samples are noisy.',
  render(doc){const out=[];for(const [market,m] of Object.entries(doc.markets||{})){if(!m?.bins?.length)continue;out.push(`<h4>${esc(market)} <small>n ${m.n}${finite(m.brier)?` · Brier ${m.brier.toFixed(3)}`:''}</small></h4>${C().reliability(m.bins,{title:'Calibration '+market,width:420,height:300})}`);}return out.join('')||'<p class="gc-empty">No settled predictions to chart yet.</p>';}},
};
function teamsOf(rows){return [...new Set((rows||[]).map(r=>r.team).filter(Boolean))].sort();}
function filter(rows){return (rows||[]).filter(r=>(state.pos==='ALL'||r.position===state.pos)&&(state.team==='ALL'||r.team===state.team));}
async function draw(){
 const host=state.host;if(!host)return;const def=CHARTS[state.chart],doc=def.file?await load(def.file):{};
 const teams=teamsOf(def.file?doc?.rows:Object.values(state.ctx.profiles||{}));
 const chips=Object.entries(CHARTS).map(([k,v])=>`<button type="button" data-chart="${k}" aria-pressed="${k===state.chart}">${esc(v.label)}</button>`).join('');
 const filters=`<div class="charts-filters"><label>Position<select data-f="pos">${['ALL','QB','RB','WR','TE'].map(p=>`<option ${p===state.pos?'selected':''}>${p}</option>`).join('')}</select></label><label>Team<select data-f="team"><option>ALL</option>${teams.map(t=>`<option ${t===state.team?'selected':''}>${esc(t)}</option>`).join('')}</select></label>${def.file&&state.chart!=='calibration'?`<label>Min games<select data-f="min">${[1,2,3,4,6].map(n=>`<option ${n===state.min?'selected':''}>${n}</option>`).join('')}</select></label>`:''}</div>`;
 let body;
 if(def.file&&!doc)body='<p class="gc-empty">This chart\'s data file has not been published yet. It is built by the weekly refresh; try again after the next refresh.</p>';
 else body=`${note(def.file?doc:{as_of:state.ctx.profileDate},def.kind)}<p class="bt-note">${esc(def.help)}</p>${def.render(doc||{})}`;
 host.innerHTML=`<div class="charts-chips" role="group" aria-label="Chart">${chips}</div>${filters}${body}`;
}
function render(host,ctx={}){
 if(!host||!root.GoingCharts)return;state.host=host;state.ctx=ctx;
 if(!host.dataset.bound){host.dataset.bound='1';
  host.addEventListener('click',e=>{const b=e.target.closest('[data-chart]');if(b){state.chart=b.dataset.chart;draw();}});
  host.addEventListener('change',e=>{const f=e.target.dataset?.f;if(!f)return;state[f]=f==='min'?Number(e.target.value):e.target.value;draw();});}
 draw();
}
root.GoingChartsUI={render,CHARTS,state};
if(typeof module!=='undefined')module.exports=root.GoingChartsUI;
})(globalThis);
