/* Static consumer feeds. Reuses frozen predictions and published Yard signals. */
import {readFile,writeFile,rename} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const require=createRequire(import.meta.url),ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const yard=require('../shared/yard-opportunities.js');
const read=async file=>JSON.parse(await readFile(file,'utf8'));
async function save(name,data){const file=path.join(ROOT,'data',name);await writeFile(file+'.tmp',JSON.stringify(data));await rename(file+'.tmp',file);}
export function footballRecords(snapshot){
 const settlements=new Map((snapshot.records||[]).filter(r=>r.kind==='settlement').map(r=>[r.payload.prediction_id,r.payload]));
 return (snapshot.records||[]).filter(r=>r.kind==='prediction'&&Date.parse(r.payload.observed_at)<Date.parse(r.payload.kickoff)).map(r=>{const p=r.payload,s=settlements.get(p.id);return {schema_version:1,id:p.id,sport:p.sport,event:{id:p.event,start:p.kickoff,home:p.home,away:p.away},entity:{id:p.profile_id||p.selection,name:p.player||`${p.away} @ ${p.home}`},signal_family:p.tracking_group.toUpperCase(),features:{probability:p.probability,ev:p.ev,market:p.market,line:p.line,side:p.side,book:p.book,decimal_odds:p.odds,...p.model_evidence},sample_sizes:{games:p.model_evidence?.n??null},rank:null,strength:null,model_version:p.model_version,observed_at:p.observed_at,source:p.provenance||{quoted_at:p.quoted_at},outcome:s?{values:{status:s.status,actual:s.actual},observed_at:s.observed_at,source:s.source_url}:null};});
}
export function footballCards(rows){
 const unique=new Map(),labels={atd:'Anytime touchdown',rush_yds:'Rushing yards',rec_yds:'Receiving yards',pass_yds:'Passing yards',receptions:'Receptions',pass_tds:'Passing TDs',total:'Total points',spread:'Spread',moneyline:'Moneyline'};
 for(const c of rows){
  const id=[c.canonicalContract||c.contract,c.book].join('|');if(unique.has(id))continue;
  const flags=c.flags||[],market=labels[c.market]||c.market,side=c.side==='Home'?c.home:c.side==='Away'?c.away:c.side;
  const label=c.market==='atd'?c.player+' to score a touchdown':c.market==='moneyline'?side+' to win':(c.player?c.player+' · ':'')+side+' '+c.line+' '+market.toLowerCase();
  const qualified=c.tracking_group==='best_value'||(c.ev>=.03&&flags.some(f=>f.id==='gap')&&!flags.some(f=>f.id==='check'));
  unique.set(id,{...c,id,label,qualification:qualified?'GOING candidate':'Price watchlist',marketLabel:market,
   projectionLabel:Number.isFinite(c.projMean)?c.projMean.toFixed(1)+' projected · '+(100*c.prob).toFixed(1)+'% model':Number.isFinite(c.prob)?(100*c.prob).toFixed(1)+'% model':'Unavailable',
   confidence:Number.isFinite(c.n)?c.n+' recorded games':'Sample unavailable',
   why:flags.filter(f=>f.id!=='check').map(f=>f.why||f.text||f.label||'').filter(Boolean).slice(0,2).join(' · ')||'Existing projection and quoted line are available for comparison; no separately qualified edge is asserted.',
   risk:flags.filter(f=>f.id==='check').map(f=>f.why||f.text||f.label||'').filter(Boolean).join(' · ')||'Projection uncertainty, role changes and stale quotes can change the assessment.',
   evidence:[['Model sample',c.n??'Unavailable'],['Quote timestamp',c.updatedAt||'Unknown'],['Profile cutoff',c.profileDate||'Unknown'],...flags.map(f=>[f.id,f.why||f.text||f.label||'No detail supplied'])],
   researchUrl:c.profileId?'/players/?player='+encodeURIComponent(c.profileId):null});
 }
 return [...unique.values()];
}
async function main(){const generated_at=new Date().toISOString(),sources={},old=await read(path.join(ROOT,'data/opportunities.json')).catch(()=>({opportunities:[]}));let football=[],mlb=[],mlbRecords=[];
 try{const rows=JSON.parse(execFileSync(process.execPath,['scripts/collect_model_plays.cjs'],{cwd:ROOT,env:{...process.env,GOING_TRACKER_LOCAL_DATA:'1'},maxBuffer:32*1024*1024,timeout:90000}));football=footballCards(rows);sources.football={status:'FRESH',note:'Published projection feed; individual quote timestamps determine price freshness.'};}catch{football=old.opportunities.filter(c=>c.sport!=='mlb');sources.football={status:football.length?'STALE':'FAILED',reason:'Football opportunity export failed; retained timestamps were not changed.'};}
 const fetchYard=async name=>{if(process.env.GOING_YARD_DATA_DIR)return read(path.join(process.env.GOING_YARD_DATA_DIR,name));const r=await fetch(`https://raw.githubusercontent.com/daboli69/hr-board/main/docs/${name}`,{signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Published Yard snapshot unavailable');return r.json();};
 try{const [model,ledger]=await Promise.all(['opportunities.json','signal_tracker.json'].map(fetchYard));mlb=yard.fromModel(model);mlbRecords=ledger.records;sources.mlb={status:Date.now()-Date.parse(model.generated_at)>30*3600000?'STALE':model.status,generated_at:model.generated_at,ledger_at:ledger.generated_at};}catch{mlb=old.opportunities.filter(c=>c.sport==='mlb');const previous=await read(path.join(ROOT,'data/signal_tracker.json')).catch(()=>({records:[]}));mlbRecords=previous.records.filter(r=>r.sport==='mlb');sources.mlb={status:mlb.length||mlbRecords.length?'STALE':'FAILED',reason:'Published Yard snapshot unavailable; retained observation timestamps.'};}
 const tracker=await read(path.join(ROOT,'data/public_tracker.json'));
 await save('opportunities.json',{schema_version:1,generated_at,sources,opportunities:[...football,...mlb]});
 await save('signal_tracker.json',{schema_version:1,generated_at,sources,records:[...footballRecords(tracker),...mlbRecords]});
 console.log(JSON.stringify({sources,football_offers:football.length,mlb_offers:mlb.length,mlb_records:mlbRecords.length}));
 if(Object.values(sources).some(s=>s.status==='FAILED'||s.status==='STALE'))process.exitCode=1;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))await main();
