const number=n=>typeof n==='number'&&Number.isFinite(n);
const error=n=>number(n)&&n>=0?n:null;
const count=n=>Number.isInteger(n)&&n>=0?n:null;
const interval=r=>Array.isArray(r)&&r.length===2&&r.every(number)&&r[0]<=r[1]?r:null;

export function gameDiagnostic(d){
 if(d?.schema_version!==1||d.validation_scope!=='chronological_week_ahead_score_diagnostic'||count(d.games)===null||error(d.margin_error_points)===null||error(d.total_error_points)===null)throw Error('Game backtest snapshot is invalid.');
 const c=d.opponent_adjusted||{};
 return {games:d.games,seasons:Array.isArray(d.seasons)&&d.seasons.length===2&&d.seasons.every(Number.isInteger)?d.seasons:null,generatedAt:d.generated_at||null,
  rows:[['Margin','margin'],['Total','total']].map(([label,k])=>({label,baseline:d[k+'_error_points'],challenger:error(c[k+'_error_points']),improvementRange:interval(c[k+'_improvement_range_95'])})),
  // Historical score diagnostics never acquire hypothetical odds or ROI.
  roi:null};
}
export function roleDiagnostic(d){
 if(d?.schema_version!==1||d.validation_scope!=='chronological_next_game_diagnostic'||!Array.isArray(d.groups)||!Number.isInteger(d.season))throw Error('Role backtest snapshot is invalid.');
 const rows=d.groups.filter(g=>['all_eligible','above_average_role','role_ahead_of_results'].includes(g.name)&&count(g.players_games)!==null).map(g=>({name:g.name,games:g.players_games,baseline:error(g.yards_baseline_mae),challenger:error(g.yards_role_adjusted_mae)}));
 if(!rows.some(r=>r.name==='all_eligible'))throw Error('Role backtest sample is missing.');
 return {season:d.season,rows,roi:null};
}
export async function loadDiagnostic(file,parse,{fetcher=globalThis.fetch,base=globalThis.document?.baseURI,stamp=Date.now()}={}){
 if(!['football_game_validation.json','football_role_validation.json'].includes(file))throw Error('Unknown backtest source.');
 let lastError;
 for(const path of [`../api/snapshot?file=${file}&t=${stamp}`,`../data/${file}?t=${stamp}`]){
  try{const r=await fetcher(new URL(path,base));if(!r.ok)throw Error(`HTTP ${r.status}`);return parse(await r.json());}catch(e){lastError=e;}
 }
 throw Error(`Backtest snapshot unavailable (${lastError?.message||'no published source'}).`);
}
