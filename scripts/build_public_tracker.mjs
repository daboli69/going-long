import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const OUTPUT=path.join(ROOT,'data','public_tracker.json');
const GROUPS=new Set(['all_projection','best_model','best_value']);
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
 for(const row of plays){
  const market=MARKET[row.market],kickoff=Date.parse(row.kickoff),group=row.tracking_group,contract=row.canonicalContract||row.contract;
  if(!GROUPS.has(group)||!market||!contract||!Number.isFinite(kickoff)||kickoff<=now||!Number.isFinite(row.dec)||!Number.isFinite(row.prob)||row.prob<=0||row.prob>=1)continue;
  const id=hash(`public-tracker-1|${group}|${contract}`);if(existing.has(id))continue;
  const payload={id,tracking_group:group,event:row.event,selection:contract,canonical_contract:contract,sport:row.sport,home:row.home,away:row.away,kickoff:row.kickoff,player:row.kind==='prop'?row.player:null,profile_id:row.profileId||null,market,line:row.line,side:row.side,side_index:['Under','Away'].includes(row.side)?1:0,book:row.book,odds:row.dec,american:row.odds,probability:row.prob,ev:row.ev,odds_band:oddsBand(row.dec),observed_at:observedAt,quoted_at:row.updatedAt,model_version:'public-tracker-1',model_evidence:{n:row.n??null,profileDate:row.profileDate??null,push:row.push??0},provenance:row.provenance||null};
  const record={id,kind:'prediction',observed_at:observedAt,payload};records.push(record);added.push(record);existing.add(id);
 }
 return added;
}

function matchingGame(prediction,games){
 return games.filter(game=>game.sport===prediction.sport&&normalize(game.home)===normalize(prediction.home)&&normalize(game.away)===normalize(prediction.away)&&Math.abs(Date.parse(game.kickoff)-Date.parse(prediction.kickoff))<90000);
}

export function settlePredictions(records,results,observedAt){
 const games=Object.values(results.games||{}),players=results.players||{},settled=new Set(records.filter(r=>r.kind==='settlement').map(r=>r.payload?.prediction_id)),added=[];
 for(const record of records.filter(r=>r.kind==='prediction')){
  const p=record.payload;if(settled.has(p.id)||Date.parse(p.kickoff)>=Date.parse(observedAt))continue;
  const matched=matchingGame(p,games);if(matched.length!==1)continue;const game=matched[0];let actual=null,target=p.line,over=p.side_index===0;
  if(p.market==='totals')actual=game.homeScore+game.awayScore;
  else if(p.market==='spreads'){actual=game.homeScore-game.awayScore+p.line;target=0;over=p.side_index===0;}
  else if(p.market==='h2h'){actual=game.homeScore-game.awayScore;target=0;over=p.side_index===0;}
  else if(PLAYER_RESULT[p.market]&&p.profile_id){actual=players[`${p.profile_id}|${easternDate(game.kickoff)}`]?.[PLAYER_RESULT[p.market]];if(p.market==='atd'){target=.5;over=true;}}
  if(!Number.isFinite(actual)||!Number.isFinite(target))continue;
  const status=actual===target?'refund':((actual>target)===over?'win':'loss'),id=hash(`public-tracker-1|settlement|${p.id}`),payload={sport:p.sport,prediction_id:p.id,event:p.event,status,actual,observed_at:observedAt,source_url:'https://github.com/daboli69/going-long/blob/main/data/results.json',source_generated_at:results.generated_at,source_sha256:hash(JSON.stringify(game)),method:'published_full_game_result',rules_note:'Public research settlement; book-specific injury and void exceptions are not inferred.'};
  const settlement={id,kind:'settlement',observed_at:observedAt,payload};records.push(settlement);added.push(settlement);settled.add(p.id);
 }
 return added;
}

export function summarizeSnapshot(records){
 const counts={};for(const group of GROUPS)counts[group]={predictions:records.filter(r=>r.kind==='prediction'&&r.payload?.tracking_group===group).length,settled:records.filter(r=>r.kind==='settlement'&&records.some(p=>p.kind==='prediction'&&p.id===r.payload?.prediction_id&&p.payload?.tracking_group===group)).length};return counts;
}

async function readJson(file,fallback){try{return JSON.parse(await readFile(file,'utf8'));}catch{return fallback;}}
export async function build({now=new Date().toISOString(),plays=null,output=OUTPUT}={}){
 const previous=await readJson(output,{schema_version:1,records:[]}),records=Array.isArray(previous.records)?previous.records:[],results=await readJson(path.join(ROOT,'data','results.json'),{});
 if(!plays){const stdout=execFileSync(process.execPath,[path.join(ROOT,'scripts','collect_model_plays.cjs')],{cwd:ROOT,encoding:'utf8',maxBuffer:64*1024*1024,env:{...process.env,GOING_TRACKER_LOCAL_DATA:'1'}});plays=JSON.parse(stdout);}
 const tracked=selectTrackedPlays(plays),nowMs=Date.parse(now),eligible=new Set(tracked.filter(row=>GROUPS.has(row.tracking_group)&&MARKET[row.market]&&(row.canonicalContract||row.contract)&&Date.parse(row.kickoff)>nowMs&&Number.isFinite(row.dec)&&Number.isFinite(row.prob)&&row.prob>0&&row.prob<1).map(row=>`${row.tracking_group}|${row.canonicalContract||row.contract}`)).size,captured=freezePredictions(records,tracked,now),settled=settlePredictions(records,results,now),first=records.filter(r=>r.kind==='prediction').map(r=>r.observed_at).sort()[0]||null,snapshot={schema_version:1,generated_at:now,tracking_started_at:first,records,groups:summarizeSnapshot(records),latest_run:{eligible,captured:captured.length,settled:settled.length},sources:{predictions:{status:'FRESH',method:'scheduled GOING board snapshot'},results:{status:results.generated_at?'FRESH':'FAILED',generated_at:results.generated_at||null}},methodology:{minimum_american_odds:-500,best_model:'Non-alternate plays carrying the board’s price-gap qualification without a blocking check.',best_value:'Non-alternate selections independently qualified against reference-book prices.',all_projection:'One line per event, player, market and side, chosen closest to standard -110 pricing.'},limitations:'Prospective selections only; no retroactive winners. Results use published full-game outcomes. Book-specific void and injury rules are not inferred. Public research is separate from user-entered bets.'};
 await writeFile(output,JSON.stringify(snapshot),{encoding:'utf8'});return snapshot;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))build().then(snapshot=>console.log(`Public tracker: ${snapshot.latest_run.captured} frozen, ${snapshot.latest_run.settled} settled, ${snapshot.records.length} records.`)).catch(error=>{console.error(error.message);process.exitCode=1;});
