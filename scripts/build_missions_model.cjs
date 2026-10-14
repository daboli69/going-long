// Snapshot of the existing GOING NFL game-line model rows (the Best Plays math) for the Missions cross-check.
// Runs the unchanged production board code over local data only (no network) and keeps contract-level fields; no new model.
const {execFileSync}=require('node:child_process'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const out=execFileSync(process.execPath,[path.join(__dirname,'collect_model_plays.cjs')],{cwd:root,env:{...process.env,GOING_TRACKER_LOCAL_DATA:'1'},maxBuffer:256*1024*1024,timeout:300000});
const plays=JSON.parse(out.toString('utf8'));
const odds=JSON.parse(fs.readFileSync(path.join(root,'data/nfl_betting.json'),'utf8'));
const seen=new Set(),rows=[];
for(const r of plays){
 if(r.sport!=='nfl'||r.kind!=='game'||!['moneyline','spread','total'].includes(r.market))continue;
 const key=[r.book,r.kickoff,r.home,r.market,r.side,r.line].join('|');if(seen.has(key))continue;seen.add(key);
 rows.push({book:r.book,kickoff:r.kickoff,home:r.home,away:r.away,market:r.market,side:r.side,line:r.line,odds:r.odds,prob:r.prob,push:r.push,n:r.n,ev:r.ev,updatedAt:r.updatedAt});
}
const snapshot={schema_version:1,generated_at:new Date().toISOString(),odds_generated_at:odds.generated_at,
 note:'Existing GOING game-line model output (market-anchored). Cross-check only; Missions never blends it into consensus probabilities.',rows};
fs.writeFileSync(path.join(root,'data/missions_model.json'),JSON.stringify(snapshot));
console.log(`missions_model.json: ${rows.length} rows`);
