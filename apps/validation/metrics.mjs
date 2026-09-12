export function summarize(records,group='alerts'){
 const byKind=kind=>records.filter(r=>r.kind===kind).map(r=>({...r.payload,id:r.payload.id||r.id}));
 const outcomes=new Map(byKind('settlement').sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at)).map(s=>[s.prediction_id,s]));
 const closes=new Map();for(const c of byKind('closing')){if(!closes.has(c.prediction_id))closes.set(c.prediction_id,[]);closes.get(c.prediction_id).push(c);}
 const picks=byKind('prediction').filter(p=>(group==='alerts'?p.actionable:p.tracking_group===group)&&Date.parse(p.observed_at)<Date.parse(p.kickoff)).sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at)||b.ev-a.ev),seen=new Set(),graded=[],bands={};
 for(const p of picks){const key=[p.event,p.selection,p.side].join('|');if(seen.has(key))continue;seen.add(key);const s=outcomes.get(p.id);if(!s||!['win','loss','refund','void'].includes(s.status)||!(Date.parse(s.observed_at)>Date.parse(p.kickoff)))continue;const profit=s.status==='win'?100*(p.odds-1):s.status==='loss'?-100:0;
  const close=(closes.get(p.id)||[]).filter(c=>c.near_kickoff&&Date.parse(c.quoted_at)>Date.parse(p.observed_at)&&Date.parse(c.quoted_at)<Date.parse(p.kickoff)).sort((a,b)=>Date.parse(b.quoted_at)-Date.parse(a.quoted_at))[0];
  const row={...p,...s,profit,priceMove:close?p.odds*close.probability-1:null};graded.push(row);const b=bands[p.odds_band]||(bands[p.odds_band]={bets:0,profit:0,decisive:0,error:0,games:new Set()});b.bets++;b.profit+=profit;b.games.add(p.event);if(['win','loss'].includes(s.status)){b.decisive++;b.error+=(p.probability-(s.status==='win'?1:0))**2;}
 }
 return {predictions:byKind('prediction'),graded,bands:Object.entries(bands).map(([band,b])=>({band,...b,games:b.games.size,roi:b.profit/(100*b.bets),brier:b.decisive?b.error/b.decisive:null})),profit:graded.reduce((a,b)=>a+b.profit,0),bets:graded.length,games:new Set(graded.map(p=>p.event)).size};
}
