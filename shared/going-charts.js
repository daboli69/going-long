(function(root){
'use strict';
// Reusable, dependency-free SVG chart primitives for GOING. Every chart is keyboard reachable, has text alternatives and tooltips, and takes plain row data.
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const nice=(min,max,n=5)=>{if(!(max>min)){max=min+1;}const span=max-min,step=Math.pow(10,Math.floor(Math.log10(span/n))),err=n/span*step,m=err<=.15?10:err<=.35?5:err<=.75?2:1,s=step*m,lo=Math.floor(min/s)*s,hi=Math.ceil(max/s)*s,t=[];for(let v=lo;v<=hi+1e-9;v+=s)t.push(+v.toFixed(6));return {lo,hi,ticks:t};};
function regression(points){
 const p=points.filter(q=>finite(q.x)&&finite(q.y)),n=p.length;if(n<3)return null;
 const mx=p.reduce((s,q)=>s+q.x,0)/n,my=p.reduce((s,q)=>s+q.y,0)/n;let sxx=0,sxy=0,syy=0;for(const q of p){sxx+=(q.x-mx)**2;sxy+=(q.x-mx)*(q.y-my);syy+=(q.y-my)**2;}
 if(sxx===0)return null;const slope=sxy/sxx,intercept=my-slope*mx,r=syy>0?sxy/Math.sqrt(sxx*syy):0;return {slope,intercept,r,r2:r*r,n};
}
// Scatter: rows {id,label,x,y,group?,href?,note?}. opts {xLabel,yLabel,identity:true draws y=x, fit:true draws a least-squares line, colors:{group:css}, width,height}.
function scatter(rows,opts={}){
 const W=opts.width||640,H=opts.height||420,m={l:46,r:14,t:12,b:40},pts=rows.filter(r=>finite(r.x)&&finite(r.y));
 if(!pts.length)return '<p class="gc-empty">No data for this view.</p>';
 const xs=nice(Math.min(...pts.map(p=>p.x)),Math.max(...pts.map(p=>p.x))),ys=nice(Math.min(...pts.map(p=>p.y)),Math.max(...pts.map(p=>p.y)));
 const X=v=>m.l+(v-xs.lo)/(xs.hi-xs.lo)*(W-m.l-m.r),Y=v=>H-m.b-(v-ys.lo)/(ys.hi-ys.lo)*(H-m.t-m.b),colors=opts.colors||{};
 const fit=opts.fit?regression(pts):null;
 const grid=xs.ticks.map(t=>`<line class="gc-grid" x1="${X(t)}" x2="${X(t)}" y1="${m.t}" y2="${H-m.b}"/><text class="gc-tick" x="${X(t)}" y="${H-m.b+14}" text-anchor="middle">${t}</text>`).join('')+ys.ticks.map(t=>`<line class="gc-grid" y1="${Y(t)}" y2="${Y(t)}" x1="${m.l}" x2="${W-m.r}"/><text class="gc-tick" x="${m.l-6}" y="${Y(t)+4}" text-anchor="end">${t}</text>`).join('');
 const lo=Math.max(xs.lo,ys.lo),hi=Math.min(xs.hi,ys.hi);
 const ident=opts.identity&&hi>lo?`<line class="gc-ref" x1="${X(lo)}" y1="${Y(lo)}" x2="${X(hi)}" y2="${Y(hi)}"/>`:'';
 const line=fit?`<line class="gc-fit" x1="${X(xs.lo)}" y1="${Y(fit.slope*xs.lo+fit.intercept)}" x2="${X(xs.hi)}" y2="${Y(fit.slope*xs.hi+fit.intercept)}"/>`:'';
 const dots=pts.map((p,i)=>{const tip=`${p.label}: ${opts.xLabel||'x'} ${p.x.toFixed(1)}, ${opts.yLabel||'y'} ${p.y.toFixed(1)}${p.note?' · '+p.note:''}`,c=colors[p.group]||'var(--g-accent,#35e0c3)',dot=`<circle class="gc-dot" cx="${X(p.x).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="${p.r||5}" fill="${c}" tabindex="0" role="img" aria-label="${esc(tip)}" data-i="${i}"><title>${esc(tip)}</title></circle>`;return p.href?`<a href="${esc(p.href)}">${dot}</a>`:dot;}).join('');
 return `<figure class="gc"><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(opts.title||'Scatter chart')}">${grid}${ident}${line}${dots}<text class="gc-axis" x="${(m.l+W-m.r)/2}" y="${H-4}" text-anchor="middle">${esc(opts.xLabel||'')}</text><text class="gc-axis" transform="translate(12 ${(m.t+H-m.b)/2}) rotate(-90)" text-anchor="middle">${esc(opts.yLabel||'')}</text></svg>${fit?`<figcaption class="gc-cap">Fitted line: slope ${fit.slope.toFixed(2)}, r² ${fit.r2.toFixed(2)}, n ${fit.n}.</figcaption>`:''}</figure>`;
}
// Multi-series line chart over a shared x axis. series: [{name,color?,points:[{x,y}]}], opts {xLabel,yLabel,percent:true}
function lines(series,opts={}){
 const W=opts.width||640,H=opts.height||300,m={l:44,r:14,t:12,b:34},all=series.flatMap(s=>s.points.filter(p=>finite(p.y)&&finite(p.x)));
 if(!all.length)return '<p class="gc-empty">No data for this view.</p>';
 const xs=nice(Math.min(...all.map(p=>p.x)),Math.max(...all.map(p=>p.x)),Math.min(8,new Set(all.map(p=>p.x)).size)),ys=nice(Math.min(0,...all.map(p=>p.y)),Math.max(...all.map(p=>p.y)));
 const X=v=>m.l+(v-xs.lo)/(xs.hi-xs.lo||1)*(W-m.l-m.r),Y=v=>H-m.b-(v-ys.lo)/(ys.hi-ys.lo)*(H-m.t-m.b),pal=['#35e0c3','#e0a43a','#7aa7ff','#ff7a90','#b48cff'];
 const fmt=v=>opts.percent?Math.round(v*100)+'%':v;
 const grid=xs.ticks.map(t=>`<text class="gc-tick" x="${X(t)}" y="${H-m.b+14}" text-anchor="middle">${t}</text>`).join('')+ys.ticks.map(t=>`<line class="gc-grid" y1="${Y(t)}" y2="${Y(t)}" x1="${m.l}" x2="${W-m.r}"/><text class="gc-tick" x="${m.l-6}" y="${Y(t)+4}" text-anchor="end">${fmt(t)}</text>`).join('');
 const paths=series.map((s,i)=>{const c=s.color||pal[i%pal.length],pts=s.points.filter(p=>finite(p.y)),d=pts.map((p,j)=>`${j?'L':'M'}${X(p.x).toFixed(1)} ${Y(p.y).toFixed(1)}`).join(' ');return `<path d="${d}" fill="none" stroke="${c}" stroke-width="2.2"/>${pts.map(p=>`<circle cx="${X(p.x).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="3.5" fill="${c}" tabindex="0" role="img" aria-label="${esc(s.name)} ${esc(opts.xLabel||'')} ${p.x}: ${fmt(+p.y.toFixed(3))}"><title>${esc(s.name)} · ${esc(opts.xLabel||'x')} ${p.x}: ${fmt(+p.y.toFixed(3))}</title></circle>`).join('')}`;}).join('');
 const legend=`<ul class="gc-legend">${series.map((s,i)=>`<li><i style="background:${s.color||pal[i%pal.length]}"></i>${esc(s.name)}</li>`).join('')}</ul>`;
 return `<figure class="gc"><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(opts.title||'Line chart')}">${grid}${paths}<text class="gc-axis" x="${(m.l+W-m.r)/2}" y="${H-2}" text-anchor="middle">${esc(opts.xLabel||'')}</text></svg>${legend}</figure>`;
}
// Horizontal diverging bars: rows [{label,value,href?,note?}], sorted by caller. Positive right (accent), negative left (amber).
function bars(rows,opts={}){
 const r=rows.filter(x=>finite(x.value));if(!r.length)return '<p class="gc-empty">No data for this view.</p>';
 const max=Math.max(...r.map(x=>Math.abs(x.value)),1e-9),W=opts.width||640,rowH=26,H=r.length*rowH+8,mid=W/2+(opts.shift||0),span=W/2-120;
 const items=r.map((x,i)=>{const w=Math.abs(x.value)/max*span,pos=x.value>=0,y=4+i*rowH,tip=`${x.label}: ${(+x.value.toFixed(2))}${x.note?' · '+x.note:''}`,bar=`<rect x="${pos?mid:mid-w}" y="${y+3}" width="${Math.max(1,w)}" height="${rowH-8}" rx="3" fill="${pos?'var(--g-accent,#35e0c3)':'#e0a43a'}" tabindex="0" role="img" aria-label="${esc(tip)}"><title>${esc(tip)}</title></rect>`,lab=`<text class="gc-tick" x="${pos?mid-6:mid+6}" y="${y+rowH/2+3}" text-anchor="${pos?'end':'start'}">${esc(x.label)}</text><text class="gc-tick" x="${pos?mid+w+5:mid-w-5}" y="${y+rowH/2+3}" text-anchor="${pos?'start':'end'}">${(+x.value.toFixed(1))}</text>`;return x.href?`<a href="${esc(x.href)}">${bar}${lab}</a>`:bar+lab;}).join('');
 return `<figure class="gc"><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(opts.title||'Bar chart')}"><line class="gc-ref" x1="${mid}" x2="${mid}" y1="0" y2="${H}"/>${items}</svg></figure>`;
}
// Reliability diagram: bins [{p,observed,n}] against the diagonal.
function reliability(bins,opts={}){
 return scatter(bins.map(b=>({id:String(b.p),label:`Predicted ${(b.p*100).toFixed(0)}% (n ${b.n})`,x:b.p*100,y:b.observed*100,r:Math.max(3,Math.min(10,Math.sqrt(b.n)/2))})),{...opts,identity:true,xLabel:'Predicted %',yLabel:'Observed %',title:opts.title||'Calibration'});
}
function sparkline(values,opts={}){
 const v=values.filter(finite);if(v.length<2)return '';const W=opts.width||64,H=opts.height||22,min=Math.min(...v),max=Math.max(...v),X=i=>i*(W/(v.length-1)),Y=x=>H-2-(x-min)/((max-min)||1)*(H-4);
 return `<svg class="gc-spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(opts.label||'trend')}"><polyline fill="none" stroke="currentColor" stroke-width="2" points="${v.map((x,i)=>X(i).toFixed(1)+','+Y(x).toFixed(1)).join(' ')}"/></svg>`;
}
root.GoingCharts={scatter,lines,bars,reliability,sparkline,regression,esc};
if(typeof module!=='undefined')module.exports=root.GoingCharts;
})(globalThis);
