// Test support: mirrors the computations TrackerDashboard performs in apps/validation/src.jsx (lines ~52-71, 66-67,
// 79, 87) so equivalence tests can run the dashboard's own math (apps/validation/metrics.mjs) on two record sets and
// compare every number and every displayed field. Keep in step with src.jsx if the dashboard computations change.
import * as M from '../../apps/validation/metrics.mjs';

export const NOW=Date.parse('2026-10-06T12:00:00Z');
const FIELDS=['id','player','away','home','sport','market','side','line','side_index','book','kickoff','observed_at','probability','american','actionable','status','profit','actual','prediction_id','prediction_observed_at'];
const pick=p=>Object.fromEntries(FIELDS.map(f=>[f,p[f]]));

export function view(records,meta,{cohort,sport,days,date,game,group},asOf=NOW){
 const {filterTrackerRecords:F,summarize,slateDate,performanceGameKey}=M;
 const beforeGame=F(records,{cohort,sport,days,date,asOf});
 const games=[...new Map(beforeGame.filter(r=>r.kind==='prediction'&&r.payload.home&&r.payload.away).map(r=>{const p=r.payload;return [performanceGameKey(p),{key:performanceGameKey(p),label:`${(p.sport||'nfl').toUpperCase()} · ${p.away} at ${p.home} · ${slateDate(p.kickoff)}`}];})).values()].sort((a,b)=>b.label.slice(-10).localeCompare(a.label.slice(-10))||a.label.localeCompare(b.label));
 const scoped=game?F(beforeGame,{game,asOf}):beforeGame;
 const stats=summarize(scoped,group,asOf);
 const picks=[...stats.selected].sort((a,b)=>Date.parse(b.kickoff)-Date.parse(a.kickoff)||String(a.id).localeCompare(String(b.id)));
 const receipts=[...stats.graded].sort((a,b)=>Date.parse(b.observed_at)-Date.parse(a.observed_at)||String(a.prediction_id).localeCompare(String(b.prediction_id)));
 const settled=new Set(stats.graded.map(p=>p.prediction_id));
 const awaiting=picks.filter(p=>!settled.has(p.id)&&Date.parse(p.kickoff)<=asOf).map(p=>p.id);
 const slateDates=[...new Set([...records.filter(r=>r.kind==='prediction'&&(sport==='all'||(r.payload.sport||'nfl')===sport)).map(r=>slateDate(r.payload.kickoff)),...(meta?.result_coverage?.slates||[]).filter(s=>sport==='all'||s.sport===sport).map(s=>s.date)].filter(Boolean))].sort().reverse();
 const latest=l=>(meta?.result_coverage?.slates||[]).filter(s=>s.sport===l&&s.finals>0).map(s=>s.date).sort().at(-1)||records.filter(r=>r.kind==='prediction'&&r.payload.sport===l&&Date.parse(r.payload.kickoff)<asOf).map(r=>slateDate(r.payload.kickoff)).sort().at(-1);
 const {selected,graded,predictions,bands,series,...rest}=stats; // bands/predictions are never rendered by src.jsx
 return JSON.stringify({games,beforeLen:beforeGame.length,scopedLen:scoped.length,rest,bands:bands.map(b=>[b.band,b.bets,b.profit,b.decisive,b.error,b.games,b.roi]),series:series.map(s=>[s.at,s.cumulative,s.roi,s.drawdown,s.prediction_id]),picks:picks.map(pick),receipts:receipts.map(pick),awaiting,slateDates,latest:[latest('nfl'),latest('ncaa')],closingCount:records.filter(r=>r.kind==='closing').length});
}

export function combos(records){
 const out=[];const groups=['best_model','best_value','all_projection','going_picks_v3','going_picks_v2','going_picks_v1','alerts','all_model'];
 const cohorts=['all','current-80-20','role-aware-equal-weight','legacy','going-picks-v1','going-picks-v2','going-picks-v3'];
 for(const cohort of cohorts)for(const group of groups)out.push({cohort,sport:'all',days:'all',date:'',game:'',group});
 for(const [cohort,group] of [['current-80-20','best_model'],['all','all_projection'],['going-picks-v1','going_picks_v1']])
  for(const sport of ['nfl','ncaa'])for(const days of ['all','7','30','90'])out.push({cohort,sport,days,date:'',game:'',group});
 const dates=[...new Set(records.filter(r=>r.kind==='prediction').map(r=>M.slateDate(r.payload.kickoff)))].sort();
 for(const d of [dates[0],dates[Math.floor(dates.length/2)],dates.at(-2),dates.at(-1)])for(const group of ['best_model','all_projection'])out.push({cohort:'all',sport:'all',days:'all',date:d,game:'',group});
 const preds=records.filter(r=>r.kind==='prediction'&&r.payload.home&&r.payload.away);
 const keys=[...new Set(preds.map(r=>M.performanceGameKey(r.payload)))];
 for(const i of [0,Math.floor(keys.length/3),Math.floor(keys.length*2/3),keys.length-1])out.push({cohort:'all',sport:'all',days:'all',date:'',game:keys[i],group:'best_model'},{cohort:'all',sport:'all',days:'all',date:'',game:keys[i],group:'all_projection'});
 return out;
}
