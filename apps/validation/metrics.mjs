export const displayLine=p=>p.market==='h2h'?'':p.market==='spreads'&&p.side_index===1?-(p.line??0):(p.line??'');
export const performanceContractKey=p=>p.canonical_contract||[p.event,p.selection,p.market||'',p.period||p.period_label||'',p.side,p.side_index??'',p.line??'',p.rules||''].join('|');

function breakdown(rows,keyFor){
 const groups=new Map();
 for(const row of rows){const key=keyFor(row),item=groups.get(key)||{label:key,bets:0,decisive:0,wins:0,profit:0,forecastTotal:0,error:0,games:new Set()};item.bets++;item.profit+=row.profit;item.games.add(row.event);if(['win','loss'].includes(row.status)){const actual=row.status==='win'?1:0;item.decisive++;item.wins+=actual;item.forecastTotal+=row.probability;item.error+=(row.probability-actual)**2;}groups.set(key,item);}
 return [...groups.values()].map(item=>({...item,games:item.games.size,roi:item.profit/(100*item.bets),averageForecast:item.decisive?item.forecastTotal/item.decisive:null,winRate:item.decisive?item.wins/item.decisive:null,brier:item.decisive?item.error/item.decisive:null})).sort((a,b)=>b.bets-a.bets||String(a.label).localeCompare(String(b.label)));
}

const chanceRange=p=>p<.4?'Below 40%':p<.5?'40–49%':p<.6?'50–59%':p<.7?'60–69%':'70% and above';

export function performanceSeries(graded){
 const ordered=[...graded].sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at)||String(a.prediction_id).localeCompare(String(b.prediction_id)));
 let cumulative=0,peak=0,maxDrawdown=0;
 const series=[{index:0,at:null,profit:0,cumulative:0,drawdown:0}];
 for(const row of ordered){
  cumulative+=row.profit;
  peak=Math.max(peak,cumulative);
  const drawdown=peak-cumulative;
  maxDrawdown=Math.max(maxDrawdown,drawdown);
  series.push({index:series.length,at:row.observed_at,profit:row.profit,cumulative,drawdown,prediction_id:row.prediction_id});
 }
 return {series,maxDrawdown,endingProfit:cumulative};
}

export function summarize(records,group='alerts'){
 const byKind=kind=>records.filter(r=>r.kind===kind).map(r=>({...r.payload,id:r.payload.id||r.id}));
 const outcomes=new Map(byKind('settlement').sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at)).map(s=>[s.prediction_id,s]));
 const closes=new Map();for(const c of byKind('closing')){if(!closes.has(c.prediction_id))closes.set(c.prediction_id,[]);closes.get(c.prediction_id).push(c);}
 const picks=byKind('prediction').filter(p=>(group==='alerts'?p.actionable:p.tracking_group===group)&&Date.parse(p.observed_at)<Date.parse(p.kickoff)).sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at)||b.ev-a.ev),seen=new Set(),graded=[],bands={};
 for(const p of picks){const key=performanceContractKey(p);if(seen.has(key))continue;seen.add(key);const s=outcomes.get(p.id);if(!s||!['win','loss','refund','void'].includes(s.status)||!(Date.parse(s.observed_at)>Date.parse(p.kickoff)))continue;const profit=s.status==='win'?100*(p.odds-1):s.status==='loss'?-100:0;
  const close=(closes.get(p.id)||[]).filter(c=>c.near_kickoff&&Date.parse(c.quoted_at)>Date.parse(p.observed_at)&&Date.parse(c.quoted_at)<Date.parse(p.kickoff)).sort((a,b)=>Date.parse(b.quoted_at)-Date.parse(a.quoted_at))[0];
  const row={...p,...s,prediction_observed_at:p.observed_at,profit,priceMove:close?p.odds*close.probability-1:null};graded.push(row);const b=bands[p.odds_band]||(bands[p.odds_band]={bets:0,profit:0,decisive:0,error:0,games:new Set()});b.bets++;b.profit+=profit;b.games.add(p.event);if(['win','loss'].includes(s.status)){b.decisive++;b.error+=(p.probability-(s.status==='win'?1:0))**2;}
 }
 const performance=performanceSeries(graded);
 return {predictions:byKind('prediction').filter(p=>group==='alerts'?!p.tracking_group:p.tracking_group===group),graded,bands:Object.entries(bands).map(([band,b])=>({band,...b,games:b.games.size,roi:b.profit/(100*b.bets),brier:b.decisive?b.error/b.decisive:null})),markets:breakdown(graded,p=>p.market||'Unspecified market'),reliability:breakdown(graded.filter(p=>['win','loss'].includes(p.status)),p=>chanceRange(p.probability)),profit:performance.endingProfit,bets:graded.length,games:new Set(graded.map(p=>p.event)).size,...performance};
}
