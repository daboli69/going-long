// Chronological comparison of equal-weight, research-weighted and learned market consensus on the private historical odds archive.
// Input comes from scripts/missions_history_export.py (kept outside Git). Prints a report; writes nothing inside the repository.
// One pre-kickoff board per game: this scores probability quality, not betting returns, and says nothing about Novig/Kalshi (absent).
const fs=require('node:fs'),path=require('node:path');
const SC=require('../shared/sharp-consensus.js'),V=require('../shared/market-validation.js'),W=require('../config/sharp_weights.json');
const normalize=SC.makeNormalizer(W.aliases);

function buildRecords(input,{devig='probit',minSources=3}={}){
 const byMarket={moneyline:[],spread:[],total:[]};
 for(const r of input.records||[]){
  const t=Date.parse(r.snapshotAt),probs={};
  if(!Number.isFinite(t)||!(r.y===0||r.y===1)||!byMarket[r.market])continue;
  for(const [book,[a,b]] of Object.entries(r.quotes||{})){
   const d=SC.devigPair(SC.americanToDecimal(a),SC.americanToDecimal(b),devig);
   // Same crossed-quote rule as live consensus; several books can map to one canonical source, the later one is dropped.
   if(!d||d.overround<.985)continue;
   const s=normalize(book);if(!(s in probs))probs[s]=d.pA;
  }
  if(Object.keys(probs).length>=minSources)byMarket[r.market].push({t,gameId:r.gameId,y:r.y,probs});
 }
 return byMarket;
}
function run(input,opts={}){
 const by=buildRecords(input,opts),out={schema:'going-missions-backtest-v1',note:input.note,gaps:input.gaps,markets:{}};
 for(const [market,records] of Object.entries(by)){
  const research=V.walkForward(records,{research:W.game_lines,folds:opts.folds||4,minTrain:opts.minTrain||100});
  const pinnacle=V.walkForward(records,{research:{pinnacle:1},folds:opts.folds||4,minTrain:opts.minTrain||100});
  const sources={};for(const r of records)for(const s of Object.keys(r.probs))sources[s]=(sources[s]||0)+1;
  out.markets[market]={records:records.length,games:new Set(records.map(r=>r.gameId)).size,sources,
   firstSnapshot:records.length?new Date(Math.min(...records.map(r=>r.t))).toISOString():null,lastSnapshot:records.length?new Date(Math.max(...records.map(r=>r.t))).toISOString():null,
   calibrationEqual:V.calibrationBins(records.map(r=>({p:V.pool(r.probs,Object.fromEntries(Object.keys(r.probs).map(s=>[s,1]))),y:r.y}))),
   comparison:research,pinnacleOnly:pinnacle.ok?{equal:pinnacle.equal,pinnacle:pinnacle.research,differencesVsEqual:pinnacle.differencesVsEqual.research}:pinnacle};
 }
 out.conclusion='Differences whose 95% cluster-bootstrap interval includes 0 are not evidence of improvement. Closing-board proximity is not betting profit; no model is promoted.';
 return out;
}
module.exports={buildRecords,run};
if(require.main===module){
 const [file,flag,dest]=process.argv.slice(2);
 if(!file){console.error('usage: node scripts/missions_backtest.cjs <missions-backtest-input.json> [--out report.json]');process.exit(2);}
 const report=run(JSON.parse(fs.readFileSync(file,'utf8')));
 if(flag==='--out'){
  const root=path.resolve(__dirname,'..'),target=path.resolve(dest);
  if(target===root||target.startsWith(root+path.sep)){console.error('Refusing to write private archive derivatives inside the repository.');process.exit(2);}
  fs.writeFileSync(target,JSON.stringify(report,null,1));
 }
 console.log(JSON.stringify(report,null,1));
}
