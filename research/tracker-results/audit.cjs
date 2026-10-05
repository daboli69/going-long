// Read-only public-ledger diagnostics. No collection, fitting, holdouts or backfill.
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const finite=Number.isFinite;
const stamp=value=>Date.parse(value);
const norm=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
function day(value){if(!finite(stamp(value)))return 'invalid';return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));}
const gameKey=p=>[p.sport,norm(p.home),norm(p.away),day(p.kickoff)].join('|');
function cohort(p){if(p.model_cohort)return p.model_cohort;const e=p.model_evidence||{};if(String(e.seasonEvidence?.method||e.gameSeasonEvidence?.policy||'').includes('80% current'))return 'current-80-20';return e.roleEvidence||e.seasonEvidence?'role-aware-equal-weight':'legacy';}
const contractKey=p=>[cohort(p),p.tracking_group,gameKey(p),p.profile_id||norm(p.player),p.market,p.side_index??p.side,p.line??'',p.period||'full_game',p.rules||((p.canonical_contract||p.selection||'').split('|').at(-1))].join('|');
const count=(rows,key)=>rows.reduce((a,r)=>{const k=key(r);a[k]=(a[k]||0)+1;return a;},{});
const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
function interval(a){const m=mean(a);if(a.length<10)return {games:a.length,mean:m,lower:null,upper:null,method:'Insufficient game clusters (<10); no interval'};const se=Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/(a.length-1)/a.length);return {games:a.length,mean:m,lower:m-1.96*se,upper:m+1.96*se,method:'Descriptive normal 95% game-cluster interval; repeated teams/week dependence remains'};}
function probability(p){const push=p.model_evidence?.push??0;const q=p.probability/(1-push);return finite(p.probability)&&push>=0&&push<1&&q>0&&q<1?q:null;}
const playerMarket={player_passing_yards:'pass_yds',player_rushing_yards:'rush_yds',player_receiving_yards:'rec_yds',player_receptions:'receptions',player_passing_tds:'pass_tds',player_rushing_tds:'rush_tds',player_receiving_tds:'rec_tds',atd:'atd'};
function grade(p,g,results){
 let actual,target=p.line,over=p.side_index===0;
 if(p.market==='totals')actual=g.homeScore+g.awayScore;
 else if(['spreads','h2h'].includes(p.market)){actual=g.homeScore-g.awayScore+(p.market==='spreads'?p.line:0);target=0;}
 else if(playerMarket[p.market]){actual=results.players?.[`${p.profile_id}|${day(g.kickoff)}`]?.[playerMarket[p.market]];if(p.market==='atd'){target=.5;over=true;}}
 else return {reason:'unsupported_market'};
 if(!finite(actual)||!finite(target))return {reason:'player_result_or_line_missing'};
 return {actual,status:actual===target?'refund':((actual>target)===over?'win':'loss')};
}
function metrics(rows){
 const binary=rows.filter(r=>['win','loss'].includes(r.status)&&r.prob!==null),profit=rows.reduce((s,r)=>s+r.profit,0),games=new Map();
 for(const r of binary){const a=games.get(r.game)||[];a.push(r);games.set(r.game,a);}
 const paired=binary.filter(r=>r.marketProb!==null),pairedGames=new Map();for(const r of paired){const a=pairedGames.get(r.game)||[];a.push((r.prob-r.y)**2-(r.marketProb-r.y)**2);pairedGames.set(r.game,a);}
 const bins=[];for(let i=0;i<10;i++){const a=binary.filter(r=>Math.min(9,Math.floor(r.prob*10))===i);if(a.length)bins.push({bin:`${i*10}-${(i+1)*10}%`,contracts:a.length,games:new Set(a.map(r=>r.game)).size,forecast:mean(a.map(r=>r.prob)),observed:mean(a.map(r=>r.y))});}
 return {settled:rows.length,games:new Set(rows.map(r=>r.game)).size,statuses:count(rows,r=>r.status),stake_per_selection:100,turnover:rows.length*100,profit,roi:rows.length?profit/(rows.length*100):null,decisive:binary.length,average_probability:mean(binary.map(r=>r.prob)),win_rate:mean(binary.map(r=>r.y)),brier:mean(binary.map(r=>(r.prob-r.y)**2)),log_loss:mean(binary.map(r=>-(r.y*Math.log(r.prob)+(1-r.y)*Math.log(1-r.prob)))),game_balanced_brier:interval([...games.values()].map(a=>mean(a.map(r=>(r.prob-r.y)**2)))),paired_reference_contracts:paired.length,paired_reference_brier:mean(paired.map(r=>(r.marketProb-r.y)**2)),paired_champion_brier:mean(paired.map(r=>(r.prob-r.y)**2)),paired_brier_difference:interval([...pairedGames.values()].map(mean)),calibration:bins};
}
function audit(tracker,results,{asOf=tracker.generated_at,targetDates={nfl:'2026-10-04',ncaa:'2026-10-03'}}={}){
 if(!finite(stamp(asOf)))throw new Error('A valid explicit as-of timestamp is required');
 const records=tracker.records||[],predictions=records.filter(r=>r.kind==='prediction').map(r=>({...r.payload,id:r.payload?.id||r.id})).sort((a,b)=>stamp(a.observed_at)-stamp(b.observed_at)),settlements=new Map(),resultGames=new Map(),issues={},rows=[],selected=[],seen=new Map(),duplicates=[];
 for(const r of records.filter(r=>r.kind==='settlement')){const a=settlements.get(r.payload.prediction_id)||[];a.push(r.payload);settlements.set(r.payload.prediction_id,a);}
 for(const g of Object.values(results.games||{})){const a=resultGames.get(gameKey(g))||[];a.push(g);resultGames.set(gameKey(g),a);}
 const addIssue=(reason,p)=>{const a=issues[reason]||[];a.push(p.id);issues[reason]=a;};
 for(const original of predictions){
  const exact=resultGames.get(gameKey(original))||[],near=exact.length?exact:Object.values(results.games||{}).filter(g=>g.sport===original.sport&&norm(g.home)===norm(original.home)&&norm(g.away)===norm(original.away)&&Math.abs(stamp(g.kickoff)-stamp(original.kickoff))<=10*60000);
  const p=near.length===1?{...original,recorded_kickoff:original.kickoff,kickoff:near[0].kickoff}:original;
  const key=contractKey(p),prior=seen.get(key);if(prior){duplicates.push({id:p.id,first_id:prior.id,book_changed:p.book!==prior.book,kickoff_changed:(p.recorded_kickoff||p.kickoff)!==(prior.recorded_kickoff||prior.kickoff)});continue;}seen.set(key,p);selected.push(p);
  if(stamp(p.observed_at)>stamp(asOf)){addIssue('capture_after_as_of',p);continue;}
  if(!(stamp(p.observed_at)<stamp(original.kickoff))){addIssue('capture_not_before_vendor_kickoff',p);continue;}
  if(!finite(p.odds)||p.odds<=1){addIssue('invalid_decimal_price',p);continue;}
  if(!finite(stamp(p.quoted_at))||stamp(p.quoted_at)>stamp(p.observed_at)){addIssue('quote_timestamp_missing_or_future',p);continue;}
  const inputs=Object.values(p.provenance?.inputs||{});if(inputs.some(x=>stamp(x.generated_at)>stamp(p.observed_at))){addIssue('future_input_timestamp',p);continue;}
  const matches=resultGames.get(gameKey(p))||[],s=settlements.get(p.id)||[];
  if(stamp(p.kickoff)>stamp(asOf)){if(s.length)addIssue('upcoming_has_settlement',p);continue;}
  if(matches.length!==1){addIssue(matches.length?'ambiguous_official_game':'official_final_missing',p);continue;}
  const g=matches[0];if(!(stamp(p.observed_at)<stamp(g.kickoff))){addIssue('capture_not_before_official_kickoff',p);continue;}
  if(!finite(g.homeScore)||!finite(g.awayScore)){addIssue('partial_official_final',p);continue;}
  const expected=grade(p,g,results);if(expected.reason){addIssue(expected.reason,p);continue;}
  if(s.length!==1){addIssue(s.length?'duplicate_settlement':'settlement_missing_despite_available_result',p);continue;}
  if(!(stamp(s[0].observed_at)>stamp(g.kickoff))||stamp(s[0].observed_at)>stamp(asOf)){addIssue('settlement_chronology_invalid',p);continue;}
  if(s[0].status!==expected.status||s[0].actual!==expected.actual){addIssue('settlement_disagrees_with_public_result',p);continue;}
  if(s[0].method!=='published_full_game_result'){addIssue('unsupported_settlement_provenance',p);continue;}
  const prob=probability(p),ref=p.model_evidence?.reference,marketProb=finite(ref?.win)&&finite(ref?.loss)&&ref.win>=0&&ref.loss>=0&&ref.win+ref.loss>0?ref.win/(ref.win+ref.loss):null;
  rows.push({...p,cohort:cohort(p),game:gameKey(p),date:day(p.kickoff),status:expected.status,prob,marketProb,y:expected.status==='win'?1:0,profit:expected.status==='win'?100*(p.odds-1):expected.status==='loss'?-100:0});
 }
 const grouped=new Map();for(const r of rows){const k=[r.sport,r.cohort,r.tracking_group].join('|'),a=grouped.get(k)||[];a.push(r);grouped.set(k,a);}
 const target={};for(const [sport,date] of Object.entries(targetDates)){const ps=selected.filter(p=>p.sport===sport&&day(p.kickoff)===date),games=[...resultGames.entries()].filter(([,a])=>a[0].sport===sport&&day(a[0].kickoff)===date&&finite(a[0].homeScore)&&finite(a[0].awayScore)),covered=new Set(ps.map(gameKey));target[sport]={date,predictions:ps.length,recorded_games:covered.size,published_final_games:games.length,published_finals_without_prediction:games.filter(([k])=>!covered.has(k)).map(([,a])=>({home:a[0].home,away:a[0].away})),groups:[...new Set(ps.map(p=>p.tracking_group))].map(group=>({group,...metrics(rows.filter(r=>r.sport===sport&&r.date===date&&r.tracking_group===group))}))};}
 const orphanSettlements=[...settlements.keys()].filter(id=>!predictions.some(p=>p.id===id));
 return {schema_version:1,as_of:asOf,tracking_started_at:predictions[0]?.observed_at||null,predictions:predictions.length,unique_cohort_group_contracts:selected.length,duplicate_equivalent_contracts:duplicates.length,duplicate_books_changed:duplicates.filter(r=>r.book_changed).length,duplicate_kickoff_changed:duplicates.filter(r=>r.kickoff_changed).length,duplicate_record_ids:records.length-new Set(records.map(r=>r.id)).size,orphan_settlements:orphanSettlements.length,prospective_game_dates:count(selected,p=>`${p.sport}|${day(p.kickoff)}`),capture_dates:count(selected,p=>day(p.observed_at)),groups:[...grouped.entries()].map(([group,a])=>({group,...metrics(a),markets:[...new Set(a.map(r=>r.market))].map(m=>({market:m,...metrics(a.filter(r=>r.market===m))}))})),target,exclusions:Object.fromEntries(Object.entries(issues).map(([k,a])=>[k,{count:a.length,sample_ids:a.slice(0,5)}])),evidence:{confidence:count(selected,p=>p.model_evidence?.seasonEvidence?.sample_confidence||'not_frozen'),readiness_snapshot_frozen:selected.filter(p=>p.readiness_snapshot?.schema_version===2&&p.readiness_snapshot?.version==='football-readiness-v2'&&p.readiness_snapshot?.captured_at&&p.readiness_snapshot?.assessor_sha256).length,readiness_snapshot_missing:selected.filter(p=>!p.readiness_snapshot).length,missing_model_source_hash:selected.filter(p=>!p.provenance?.model_source_sha256).length,missing_input_provenance:selected.filter(p=>!Object.keys(p.provenance?.inputs||{}).length).length,reference_missing:selected.filter(p=>!p.model_evidence?.reference).length,quote_over_24h:selected.filter(p=>stamp(p.observed_at)-stamp(p.quoted_at)>86400000).length},methodology:{stake:'Hypothetical $100 risk per frozen selection; win=100*(decimal-1), loss=-100, refund=0; turnover includes refunded stakes. No personal bankroll or executable-price claim.',deduplication:'First captured equivalent sport/matchup/Eastern date/player/market/side/line/rules per cohort and group; books and vendor kickoff drift do not create independent trials. Groups/cohorts overlap; do not sum them.',calibration:'Win/loss only; conditional p=probability/(1-push); pushes excluded from Brier/log loss. Reference is frozen same-book two-way devigged price, not guaranteed closing price.',uncertainty:'Game-balanced descriptive normal intervals only with >=10 games; not multiplicity-corrected; shared players/teams/weeks and market dependence persist.',scope:'Public tracker/results only; no private Score/DFS or preregistered Today-v1/ABBEYS holdouts. Snapshot provenance hashes record inputs but cannot prove their event-time contents without separate version audit.'}};
}
module.exports={audit,metrics,day,gameKey,contractKey};
if(require.main===module){const root=path.resolve(__dirname,'../..'),trackerPath=path.join(root,'data/public_tracker.json'),resultsPath=path.join(root,'data/results.json'),trackerBytes=fs.readFileSync(trackerPath),resultsBytes=fs.readFileSync(resultsPath);const report=audit(JSON.parse(trackerBytes),JSON.parse(resultsBytes),{asOf:process.argv[2]||JSON.parse(trackerBytes).generated_at});report.sources={tracker_sha256:crypto.createHash('sha256').update(trackerBytes).digest('hex'),results_sha256:crypto.createHash('sha256').update(resultsBytes).digest('hex')};process.stdout.write(JSON.stringify(report,null,2)+'\n');}
