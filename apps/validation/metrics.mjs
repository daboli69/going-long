import {modelCohort} from '../../shared/model-cohort.mjs';
export function cohortRecords(records,cohort='all'){
 if(cohort==='all')return records;
 const ids=new Set(records.filter(r=>r.kind==='prediction'&&modelCohort(r.payload)===cohort).map(r=>r.payload.id||r.id));
 return records.filter(r=>r.kind==='prediction'?ids.has(r.payload.id||r.id):ids.has(r.payload.prediction_id));
}
const easternDate=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'});
export function slateDate(at){return Number.isFinite(Date.parse(at))?easternDate.format(new Date(at)):'';}
function withOfficialDates(records){
 const finals=new Map(records.filter(r=>r.kind==='settlement'&&r.payload?.method==='published_full_game_result'&&Number.isFinite(Date.parse(r.payload.official_kickoff))).map(r=>[r.payload.prediction_id,r.payload.official_kickoff]));
 return records.map(r=>{const kickoff=finals.get(r.payload?.id||r.id);return r.kind==='prediction'&&kickoff&&Math.abs(Date.parse(kickoff)-Date.parse(r.payload.kickoff))<=10*60000?{...r,payload:{...r.payload,recorded_kickoff:r.payload.recorded_kickoff||r.payload.kickoff,kickoff}}:r;});
}
export function filterTrackerRecords(records,{cohort='all',sport='all',days='all',date='',asOf=Date.now()}={}){
 records=withOfficialDates(records);
 const since=days==='all'?0:asOf-Number(days)*86400000;
 const predictions=cohortRecords(records,cohort).filter(r=>r.kind==='prediction'&&Date.parse(r.payload.kickoff)>=since&&(sport==='all'||(r.payload.sport||'nfl')===sport)&&(!date||slateDate(r.payload.kickoff)===date));
 const ids=new Set(predictions.map(r=>r.payload.id||r.id));
 return records.filter(r=>r.kind==='prediction'?ids.has(r.payload.id||r.id):ids.has(r.payload.prediction_id));
}
const conditionalChance=p=>{const push=p.model_evidence?.push||0;return push>=0&&push<1?Math.min(1,p.probability/(1-push)):p.probability;};
export const displayLine=p=>p.market==='h2h'?'':p.market==='spreads'&&p.side_index===1?-(p.line??0):(p.line??'');
const normalize=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
export const performanceGameKey=p=>p.home&&p.away&&slateDate(p.kickoff)?[p.sport||'nfl',normalize(p.home),normalize(p.away),slateDate(p.kickoff)].join('|'):p.event;
export const performanceContractKey=p=>p.home&&p.away&&slateDate(p.kickoff)?[modelCohort(p),p.tracking_group,performanceGameKey(p),p.profile_id||normalize(p.player),p.market,p.side_index??p.side,p.line??'',p.period||p.period_label||'full_game',p.rules||((p.canonical_contract||p.selection||'').split('|').at(-1))].join('|'):p.canonical_contract||[p.event,p.selection,p.market||'',p.period||p.period_label||'',p.side,p.side_index??'',p.line??'',p.rules||''].join('|');

function breakdown(rows,keyFor){
 const groups=new Map();
 for(const row of rows){const key=keyFor(row),item=groups.get(key)||{label:key,bets:0,decisive:0,wins:0,profit:0,forecastTotal:0,error:0,games:new Set()};item.bets++;item.profit+=row.profit;item.games.add(performanceGameKey(row));if(['win','loss'].includes(row.status)){const actual=row.status==='win'?1:0;item.decisive++;item.wins+=actual;item.forecastTotal+=conditionalChance(row);item.error+=(conditionalChance(row)-actual)**2;}groups.set(key,item);}
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
  series.push({index:series.length,at:row.observed_at,profit:row.profit,cumulative,roi:cumulative/(series.length*100),drawdown,prediction_id:row.prediction_id});
 }
 return {series,maxDrawdown,endingProfit:cumulative};
}

export function summarize(records,group='alerts',asOf=Date.now()){
 records=withOfficialDates(records);
 const byKind=kind=>records.filter(r=>r.kind===kind).map(r=>({...r.payload,id:r.payload.id||r.id}));
 const outcomes=new Map(byKind('settlement').sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at)).map(s=>[s.prediction_id,s]));
 const closes=new Map();for(const c of byKind('closing')){if(!closes.has(c.prediction_id))closes.set(c.prediction_id,[]);closes.get(c.prediction_id).push(c);}
 const picks=byKind('prediction').filter(p=>(group==='alerts'?p.actionable:p.tracking_group===group)&&Date.parse(p.observed_at)<Date.parse(p.kickoff)).sort((a,b)=>Date.parse(a.observed_at)-Date.parse(b.observed_at)),seen=new Set(),selected=[],graded=[],bands={};
 for(const p of picks){const key=performanceContractKey(p);if(seen.has(key))continue;seen.add(key);selected.push(p);const s=outcomes.get(p.id);if(!s||!['win','loss','refund','void'].includes(s.status)||!(Date.parse(s.observed_at)>Date.parse(p.kickoff)))continue;const profit=s.status==='win'?100*(p.odds-1):s.status==='loss'?-100:0;
  const close=(closes.get(p.id)||[]).filter(c=>c.near_kickoff&&Date.parse(c.quoted_at)>Date.parse(p.observed_at)&&Date.parse(c.quoted_at)<Date.parse(p.kickoff)).sort((a,b)=>Date.parse(b.quoted_at)-Date.parse(a.quoted_at))[0];
  const row={...p,...s,prediction_observed_at:p.observed_at,profit,priceMove:Number.isFinite(close?.probability)?p.odds*close.probability-1:null};graded.push(row);const b=bands[p.odds_band]||(bands[p.odds_band]={bets:0,profit:0,decisive:0,error:0,games:new Set()});b.bets++;b.profit+=profit;b.games.add(performanceGameKey(p));if(['win','loss'].includes(s.status)){b.decisive++;b.error+=(conditionalChance(p)-(s.status==='win'?1:0))**2;}
 }
 const performance=performanceSeries(graded);
 const gradedKeys=new Set(graded.map(performanceContractKey)),upcoming=selected.filter(p=>Date.parse(p.kickoff)>asOf).length,awaiting=selected.filter(p=>Date.parse(p.kickoff)<=asOf&&!gradedKeys.has(performanceContractKey(p))).length,completed=selected.length-upcoming;
 const counts={win:0,loss:0,refund:0,void:0};for(const row of graded)counts[row.status]++;
 return {selected,counts,stake:graded.length*100,roi:graded.length?performance.endingProfit/(graded.length*100):null,winRate:counts.win+counts.loss?counts.win/(counts.win+counts.loss):null,predictions:byKind('prediction').filter(p=>group==='alerts'?!p.tracking_group:p.tracking_group===group),graded,bands:Object.entries(bands).map(([band,b])=>({band,...b,games:b.games.size,roi:b.profit/(100*b.bets),brier:b.decisive?b.error/b.decisive:null})),markets:breakdown(graded,p=>p.market||'Unspecified market'),reliability:breakdown(graded.filter(p=>['win','loss'].includes(p.status)),p=>chanceRange(conditionalChance(p))),coverage:{selected:selected.length,upcoming,completed,settled:graded.length,awaiting,settledShare:completed?graded.length/completed:null},profit:performance.endingProfit,bets:graded.length,games:new Set(graded.map(performanceGameKey)).size,...performance};
}
