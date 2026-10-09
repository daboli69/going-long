import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFile,writeFile} from 'node:fs/promises';
import {loadTrackerSnapshot,writeTrackerStore,writeLegacyTombstone} from './tracker_store.mjs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {modelCohort} from '../shared/model-cohort.mjs';
import {createRequire} from 'node:module';
import {calibrationRows,calibrationAudit,shadowPrediction,workloadAudit} from './calibration_audit.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {validReadinessReceipt}=createRequire(import.meta.url)('../shared/football-readiness-snapshot.cjs');
const {validPickReceipt}=createRequire(import.meta.url)('../shared/football-picks-snapshot.cjs');
const OUTPUT=path.join(ROOT,'data','public_tracker.json');
const GROUPS=new Set(['all_projection','best_model','best_value','going_picks_v1','going_picks_v2','going_picks_v3']);
const PICK_VERSIONS={going_picks_v1:'football-case-v1',going_picks_v2:'football-case-v2',going_picks_v3:'football-case-v3'};
const MARKET={spread:'spreads',total:'totals',moneyline:'h2h',pass_yds:'player_passing_yards',rush_yds:'player_rushing_yards',rec_yds:'player_receiving_yards',receptions:'player_receptions',pass_tds:'player_passing_tds',rush_tds:'player_rushing_tds',rec_tds:'player_receiving_tds',atd:'atd'};
const PLAYER_RESULT={player_passing_yards:'pass_yds',player_rushing_yards:'rush_yds',player_receiving_yards:'rec_yds',player_receptions:'receptions',player_passing_tds:'pass_tds',player_rushing_tds:'rush_tds',player_receiving_tds:'rec_tds',atd:'atd'};
const hash=value=>createHash('sha256').update(String(value)).digest('hex');
const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const oddsBand=d=>d<1.67?'<1.67':d<=2?'1.67–2.00':d<=3?'2.01–3.00':'>3.00';
const easternDate=stamp=>{const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(stamp)).map(x=>[x.type,x.value]));return `${parts.year}-${parts.month}-${parts.day}`;};

// Keep the public audit meaningful and small enough for a phone. The full board remains
// available in the application; the tracker records one representative projection line,
// every explicitly qualified GOING play, and every independently price-qualified value.
export function selectTrackedPlays(plays){
 const minimumAmerican=-500,selected=[];
 for(const row of plays){
  if(PICK_VERSIONS[row.tracking_group]){
   // the -500 floor applies to every tracked group, GOING Picks included (it was bypassed here before 2026-10-08)
   if(row.picks_snapshot?.version===PICK_VERSIONS[row.tracking_group]&&row.picks_snapshot.price?.saveable&&Number.isFinite(row.odds)&&row.odds>=minimumAmerican)selected.push(row);
   continue;
  }
  if(!GROUPS.has(row.tracking_group)||!Number.isFinite(row.odds)||row.odds<minimumAmerican)continue;
  if(row.tracking_group==='best_model'){
   const flags=row.flags||[],qualified=row.ev>=.03&&flags.some(flag=>flag.id==='gap')&&!flags.some(flag=>flag.id==='check');
   if(qualified&&!row.isAltLine)selected.push(row);
  }else if(row.tracking_group==='best_value'&&!row.isAltLine)selected.push(row);
 }
 const gameKey=row=>[row.sport,normalize(row.home),normalize(row.away),easternDate(row.kickoff)].join('|'),entityKey=row=>row.profileId||normalize(row.player)||row.kind;
 const distinct=new Map();for(const row of selected){const key=[row.tracking_group,gameKey(row),entityKey(row),row.market,row.side,row.line].join('|'),prior=distinct.get(key);if(!prior||row.dec>prior.dec)distinct.set(key,row);}
 const projections=plays.filter(row=>row.tracking_group==='all_projection'&&Number.isFinite(row.odds)&&row.odds>=minimumAmerican),families=new Map();
 for(const row of projections){
  const key=[gameKey(row),row.kind,entityKey(row),row.market,row.side].join('|'),prior=families.get(key);
  if(!prior||Math.abs(row.dec-1.91)<Math.abs(prior.dec-1.91)||(Math.abs(row.dec-1.91)===Math.abs(prior.dec-1.91)&&row.dec>prior.dec))families.set(key,row);
 }
 return [...distinct.values(),...families.values()];
}

export function freezePredictions(records,plays,observedAt){
 const now=Date.parse(observedAt),existing=new Set(records.filter(r=>r.kind==='prediction').map(r=>r.id)),added=[];
 const frozenContracts=new Set(records.filter(r=>r.kind==='prediction').map(({payload:p})=>[modelCohort(p),p.tracking_group,p.canonical_contract||p.selection].join('|')));
 const training=calibrationRows(records);
 for(const row of plays){
  const market=MARKET[row.market],kickoff=Date.parse(row.kickoff),group=row.tracking_group,contract=row.canonicalContract||row.contract;
  if(!GROUPS.has(group)||!market||!contract||!Number.isFinite(kickoff)||kickoff<=now||!Number.isFinite(row.dec)||!Number.isFinite(row.prob)||row.prob<=0||row.prob>=1)continue;
  const cohort=modelCohort(row),frozenKey=[cohort,group,contract].join('|'),id=hash(`public-tracker-1|${group}|${contract}${cohort==='legacy'?'':'|'+cohort}`);if(existing.has(id)||frozenContracts.has(frozenKey))continue;
  const payload={id,tracking_group:group,event:row.event,selection:contract,canonical_contract:contract,sport:row.sport,home:row.home,away:row.away,kickoff:row.kickoff,player:row.kind==='prop'?row.player:null,profile_id:row.profileId||null,market,line:row.line,side:row.side,side_index:['Under','Away'].includes(row.side)?1:0,book:row.book,odds:row.dec,american:row.odds,probability:row.prob,ev:row.ev,odds_band:oddsBand(row.dec),observed_at:observedAt,quoted_at:row.updatedAt,model_version:'public-tracker-1',model_evidence:{n:row.n??null,profileDate:row.profileDate??null,push:row.push??0,gameSeasonEvidence:row.gameSeasonEvidence??null,seasonEvidence:row.seasonEvidence??null,roleEvidence:row.roleEvidence??null},provenance:row.provenance||null};
  const readiness=row.readiness_snapshot;if(validReadinessReceipt(readiness,row,row.provenance,observedAt))payload.readiness_snapshot=readiness;
  payload.model_cohort=cohort;payload.model_version='board-research-3';
  payload.model_evidence={...payload.model_evidence,calibration:row.calibration||null,reference:row.reference||null,projection_mean:row.projMean??null,projection_sd:row.projSd??null,workload:row.workloadEvidence||null};
  payload.calibration_shadow=shadowPrediction(payload,training);
  if(PICK_VERSIONS[group]){
   const receipt=row.picks_snapshot;
   if(!validPickReceipt(receipt,row,row.provenance,observedAt)||!receipt.price?.saveable)continue;
   payload.picks_snapshot=receipt;payload.model_version=receipt.version;payload.calibration_shadow=null;
  }
  const record={id,kind:'prediction',observed_at:observedAt,payload};records.push(record);added.push(record);existing.add(id);frozenContracts.add(frozenKey);
 }
 return added;
}

function matchingGame(prediction,games){
 // Match the unique official matchup/day, not a vendor's delayed kickoff clock.
 const matchup=games.filter(game=>game.sport===prediction.sport&&normalize(game.home)===normalize(prediction.home)&&normalize(game.away)===normalize(prediction.away));
 const sameDay=matchup.filter(game=>easternDate(game.kickoff)===easternDate(prediction.kickoff));
 // A small vendor clock drift can cross Eastern midnight (23:59 vs 00:00).
 // Only accept a unique nearby official matchup; never guess another day.
 return sameDay.length?sameDay:matchup.filter(game=>Math.abs(Date.parse(game.kickoff)-Date.parse(prediction.kickoff))<=10*60000);
}

export function settlementReason(p,results,observedAt){
 if(!(Date.parse(p.kickoff)<Date.parse(observedAt)))return 'upcoming';
 const matches=matchingGame(p,Object.values(results.games||{}));
 if(matches.length!==1)return matches.length?'ambiguous_game':'official_final_missing';
 const g=matches[0];
 if(!(Date.parse(p.observed_at)<Date.parse(g.kickoff)))return 'not_before_official_kickoff';
 if(!Number.isFinite(g.homeScore)||!Number.isFinite(g.awayScore))return 'partial_final';
 if(PLAYER_RESULT[p.market]){
  const row=results.players?.[`${p.profile_id}|${easternDate(g.kickoff)}`];
  if(!row)return 'player_participation_or_result_missing';
  if(!Number.isFinite(row[PLAYER_RESULT[p.market]]))return 'player_market_result_missing';
 }else if(!['totals','spreads','h2h'].includes(p.market))return 'unsupported_settlement_rules';
 return null;
}

export function settlementAudit(records,results,observedAt){
 const settled=new Set(records.filter(r=>r.kind==='settlement').map(r=>r.payload.prediction_id)),pending=[],counts={};
 for(const {payload:p} of records.filter(r=>r.kind==='prediction')){
  if(settled.has(p.id))continue;const reason=settlementReason(p,results,observedAt);if(!reason||reason==='upcoming')continue;
  counts[reason]=(counts[reason]||0)+1;pending.push({prediction_id:p.id,player:p.player,market:p.market,group:p.tracking_group,cohort:modelCohort(p),reason});
 }return {checked_at:observedAt,counts,pending,note:'Missing player participation is not zero and does not establish book-specific void rules.'};
}

export function settlePredictions(records,results,observedAt){
 const games=Object.values(results.games||{}),players=results.players||{},settled=new Set(records.filter(r=>r.kind==='settlement').map(r=>r.payload?.prediction_id)),added=[];
 for(const record of records.filter(r=>r.kind==='prediction')){
  const p=record.payload;if(settled.has(p.id)||settlementReason(p,results,observedAt))continue;
  const matched=matchingGame(p,games);if(matched.length!==1)continue;const game=matched[0];let actual=null,target=p.line,over=p.side_index===0;
  if(p.market==='totals')actual=game.homeScore+game.awayScore;
  else if(p.market==='spreads'){actual=game.homeScore-game.awayScore+p.line;target=0;over=p.side_index===0;}
  else if(p.market==='h2h'){actual=game.homeScore-game.awayScore;target=0;over=p.side_index===0;}
  else if(PLAYER_RESULT[p.market]&&p.profile_id){actual=players[`${p.profile_id}|${easternDate(game.kickoff)}`]?.[PLAYER_RESULT[p.market]];if(p.market==='atd'){target=.5;over=true;}}
  if(!Number.isFinite(actual)||!Number.isFinite(target))continue;
  const status=actual===target?'refund':((actual>target)===over?'win':'loss'),id=hash(`public-tracker-1|settlement|${p.id}`),payload={sport:p.sport,prediction_id:p.id,event:p.event,status,actual,observed_at:observedAt,source_url:'https://github.com/daboli69/going-long/blob/main/data/results.json',source_generated_at:results.generated_at,source_sha256:hash(JSON.stringify(game)),method:'published_full_game_result',rules_note:'Public research settlement; book-specific injury and void exceptions are not inferred.'};
  payload.actual_workload=players[`${p.profile_id}|${easternDate(game.kickoff)}`]||null;
  payload.official_game_id=game.id;payload.official_kickoff=game.kickoff;
  payload.source_sha256=hash(JSON.stringify({game,player:payload.actual_workload}));
  const settlement={id,kind:'settlement',observed_at:observedAt,payload};records.push(settlement);added.push(settlement);settled.add(p.id);
 }
 return added;
}

export function summarizeSnapshot(records){
 const counts={};for(const group of GROUPS)counts[group]={predictions:records.filter(r=>r.kind==='prediction'&&r.payload?.tracking_group===group).length,settled:records.filter(r=>r.kind==='settlement'&&records.some(p=>p.kind==='prediction'&&p.id===r.payload?.prediction_id&&p.payload?.tracking_group===group)).length};return counts;
}

export function settlePickResearch(records,results,observedAt){
 const settled=new Set(records.filter(r=>r.kind==='pick_research_settlement').map(r=>r.payload.research_id));
 const proxies=records.filter(r=>r.kind==='pick_research'&&!settled.has(r.id)).map(r=>({id:r.id,kind:'prediction',payload:{...r.payload,id:r.id,market:MARKET[r.payload.market],observed_at:r.payload.picks_snapshot.captured_at,side_index:['Under','Away'].includes(r.payload.side)?1:0}}));
 const outcomes=settlePredictions(proxies,results,observedAt).map(r=>({id:hash(`picks-research-result-v1|${r.payload.prediction_id}`),kind:'pick_research_settlement',observed_at:observedAt,payload:{...r.payload,research_id:r.payload.prediction_id,price_scope:'No stake or ROI is assigned to this research receipt.'}}));
 records.push(...outcomes);return outcomes;
}

export function resultCoverage(records,results,observedAt){
 const predictions=records.filter(r=>r.kind==='prediction').map(r=>r.payload),slates=new Map(),games=Object.values(results.games||{}),trackedGames=new Set();
 for(const p of predictions){const matches=matchingGame(p,games);if(matches.length===1&&Date.parse(p.observed_at)<Date.parse(matches[0].kickoff))trackedGames.add(matches[0]);}
 for(const game of games){
  if(!['nfl','ncaa'].includes(game.sport)||!Number.isFinite(game.homeScore)||!Number.isFinite(game.awayScore)||!(Date.parse(game.kickoff)<Date.parse(observedAt)))continue;
  const date=easternDate(game.kickoff),key=game.sport+'|'+date;
  const slate=slates.get(key)||{sport:game.sport,date,finals:0,tracked_finals:0,games:[]};
  const tracked=trackedGames.has(game);
  slate.finals++;if(tracked)slate.tracked_finals++;
  slate.games.push({...game,tracked});slates.set(key,slate);
 }
 return {checked_at:observedAt,method:'Published finals compared with any original pregame selection; untracked finals never create retrospective bets',slates:[...slates.values()].sort((a,b)=>b.date.localeCompare(a.date)||a.sport.localeCompare(b.sport))};
}

export function captureClosingPrices(records,quotes,observedAt){
 const now=Date.parse(observedAt),existing=new Set(records.map(r=>r.id)),added=[];
 const key=(p,raw=false)=>[p.sport,normalize(p.home),normalize(p.away),easternDate(p.kickoff),raw?(MARKET[p.market]||p.market):p.market,raw?p.profileId||'':p.profile_id||'',p.line,p.side,normalize(p.book)].join('|');
 const available=new Map();
 for(const q of quotes){
  const quoted=Date.parse(q.updatedAt),kickoff=Date.parse(q.kickoff);
  if(!Number.isFinite(q.dec)||q.dec<=1||!Number.isFinite(quoted)||quoted>now||now-quoted>10*60000||now>=kickoff)continue;
  const k=key(q,true),old=available.get(k);if(!old||Date.parse(old.updatedAt)<quoted)available.set(k,q);
 }
 for(const {payload:p} of records.filter(r=>r.kind==='prediction')){
  const q=available.get(key(p));if(!q||!(Date.parse(q.updatedAt)>Date.parse(p.observed_at))||now>=Date.parse(p.kickoff))continue;
  const id=hash(`sampled-close|${p.id}|${q.updatedAt}`);if(existing.has(id))continue;
  const ref=q.reference,probability=Number.isFinite(ref?.win)&&Number.isFinite(ref?.loss)&&ref.win+ref.loss>0?ref.win/(ref.win+ref.loss):null;
  const payload={prediction_id:p.id,sport:p.sport,book:p.book,quoted_at:q.updatedAt,observed_at:observedAt,decimal:q.dec,probability,
   near_kickoff:Date.parse(p.kickoff)-Date.parse(q.updatedAt)<=10*60000,
   method:'same-book exact-line scheduled observation; not guaranteed final closing price',source:'existing scheduled odds snapshot'};
  const row={id,kind:'closing',observed_at:observedAt,payload};records.push(row);added.push(row);existing.add(id);
 }return added;
}

async function readJson(file,fallback){try{return JSON.parse(await readFile(file,'utf8'));}catch{return fallback;}}
// The collector prints every surfaced play as one JSON document (77MB on 2026-10-07 and growing with the odds feed). A buffer that is too small
// makes the whole tracker step fail with ENOBUFS and silently stops capture and settlement, so keep generous headroom (tests warn at 50%).
export const COLLECTOR_MAX_BUFFER=1024*1024*1024;
export async function build({now=null,plays=null,output=OUTPUT,settleOnly=false,store=null}={}){
 // The real tracker lives in the segmented store; a custom `output` (tests) stays a single file unless store:true.
 const useStore=store??(path.resolve(output)===path.resolve(OUTPUT)),dataDir=path.dirname(output);
 const previous=(useStore?await loadTrackerSnapshot(dataDir):null)??(useStore?{schema_version:1,records:[]}:await readJson(output,{schema_version:1,records:[]})),records=Array.isArray(previous.records)?previous.records:[],results=await readJson(path.join(ROOT,'data','results.json'),{});
 if(settleOnly)plays=[];
 if(!plays){const stdout=execFileSync(process.execPath,[path.join(ROOT,'scripts','collect_model_plays.cjs')],{cwd:ROOT,encoding:'utf8',maxBuffer:COLLECTOR_MAX_BUFFER,env:{...process.env,GOING_TRACKER_LOCAL_DATA:'1',GOING_CAPTURE_QUOTES:'1'}});plays=JSON.parse(stdout);}
 // Freeze at the real post-collection time so the row receipt is never future-dated.
 now=now||new Date().toISOString();
 // Preserve every surfaced football thesis, including unavailable prices, apart
 // from priced predictions. Missing prices never enter a hypothetical ROI.
 const researchKeys=new Set(records.filter(r=>r.kind==='pick_research').map(r=>r.id));
 for(const row of plays.filter(r=>PICK_VERSIONS[r.tracking_group])){
  const receipt=row.picks_snapshot;if(!validPickReceipt(receipt,row,row.provenance,now))continue;
  const id=hash(`picks-research-${receipt.version==='football-case-v1'?'v1':receipt.version==='football-case-v3'?'v3':'v2'}|${row.canonicalContract||row.contract}`);if(researchKeys.has(id))continue;
  records.push({id,kind:'pick_research',observed_at:now,payload:{contract:row.canonicalContract||row.contract,sport:row.sport,home:row.home,away:row.away,kickoff:row.kickoff,player:row.player,profile_id:row.profileId||null,market:row.market,side:row.side,line:row.line,model_probability:row.prob,model_mean:row.projMean??row.modelMean,picks_snapshot:receipt,provenance:row.provenance}});researchKeys.add(id);
 }
 const tracked=selectTrackedPlays(plays),nowMs=Date.parse(now),eligible=new Set(tracked.filter(row=>GROUPS.has(row.tracking_group)&&MARKET[row.market]&&(row.canonicalContract||row.contract)&&Date.parse(row.kickoff)>nowMs&&Number.isFinite(row.dec)&&Number.isFinite(row.prob)&&row.prob>0&&row.prob<1).map(row=>`${row.tracking_group}|${row.canonicalContract||row.contract}`)).size,captured=freezePredictions(records,tracked,now),settled=settlePredictions(records,results,now),first=records.filter(r=>r.kind==='prediction').map(r=>r.observed_at).sort()[0]||null,snapshot={schema_version:1,generated_at:now,tracking_started_at:first,records,groups:summarizeSnapshot(records),latest_run:{eligible,captured:captured.length,settled:settled.length},sources:{predictions:{status:'FRESH',method:'scheduled GOING board snapshot'},results:{status:results.generated_at?'FRESH':'FAILED',generated_at:results.generated_at||null}},methodology:{minimum_american_odds:-500,best_model:'Non-alternate plays carrying the board’s price-gap qualification without a blocking check.',best_value:'Non-alternate selections independently qualified against reference-book prices.',all_projection:'One line per event, player, market and side, chosen closest to standard -110 pricing.'},limitations:'Prospective selections only; no retroactive winners. Results use published full-game outcomes. Book-specific void and injury rules are not inferred. Public research is separate from user-entered bets.'};
 const closing=captureClosingPrices(records,plays,now);
 snapshot.latest_run.kind=settleOnly?'settlement_only':'capture_and_settle';
 snapshot.sources.predictions.last_capture_at=now;
 if(settleOnly){
  snapshot.sources.predictions={...previous.sources?.predictions,status:'RETAINED',last_capture_at:previous.sources?.predictions?.last_capture_at||previous.generated_at||null,method:'Existing frozen predictions retained; this refresh checks published results only'};
 }
 snapshot.latest_run.closing_observations=closing.length;
 snapshot.settlement_audit=settlementAudit(records,results,now);
 snapshot.result_coverage=resultCoverage(records,results,now);
 snapshot.calibration_audit=calibrationAudit(records,now);
 snapshot.workload_audit=workloadAudit(records);
 const researchSettled=settlePickResearch(records,results,now);
 snapshot.picks_research={saved:records.filter(r=>r.kind==='pick_research').length,graded:records.filter(r=>r.kind==='pick_research_settlement').length,new_outcomes:researchSettled.length,unpriced:records.filter(r=>r.kind==='pick_research'&&!r.payload.picks_snapshot.price?.saveable).length,note:'Football thesis results are separate from priced $100 predictions. Unknown prices never create ROI.'};
 snapshot.methodology.best_model='Model-screened research, not a validated betting edge. Includes legacy qualified selections; no outcome-driven deletion.';
 snapshot.methodology.going_picks_v1='Football-case-v1: first prospective rating/badges/evidence frozen separately. Priced contracts enter the $100 research record; missing prices remain research receipts without ROI. No backfill or demonstrated pricing edge.';
 snapshot.methodology.going_picks_v2='Football-case-v2: /100 evidence bands with within-band directional projection-gap/model-spread refinement. Separate prospective cohort; v1 receipts stay unchanged. Heuristic, not probability or proven value.';
 snapshot.methodology.going_picks_v3='Football-case-v3 (from 2026-10-09): same /100 bands and refinement as v2, but correlated evidence no longer stacks (model, current production and the usage split are one source), a model edge must clear 0.25 forecast SD, a usage split needs role-share agreement or six games, game lines cap at tier 3, and an injured higher-depth teammate counts against Unders. v2 receipts stay unchanged. Heuristic, not probability or proven value.';
 snapshot.methodology.closing_prices='Scheduled same-book/exact-line observations from existing pulls. Only samples within 10 minutes are labeled near kickoff; the twice-daily schedule cannot guarantee closing coverage.';
 if(useStore){await writeTrackerStore({dataDir,snapshot});await writeLegacyTombstone(dataDir);}else await writeFile(output,JSON.stringify(snapshot),{encoding:'utf8'});
 return snapshot;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))build({settleOnly:process.argv.includes('--settle-only')}).then(snapshot=>console.log(`Public tracker: ${snapshot.latest_run.captured} frozen, ${snapshot.latest_run.settled} settled, ${snapshot.records.length} records.`)).catch(error=>{console.error(error.message);process.exitCode=1;});
