// Chronological comparison of equal-weight, research-weighted and learned market consensus on the private historical odds archive.
// Input comes from scripts/missions_history_export.py (kept outside Git). Prints a report; writes nothing inside the repository.
// One pre-kickoff board per game: this scores probability quality, not betting returns, and says nothing about Novig/Kalshi (absent).
const fs=require('node:fs'),path=require('node:path');
const SC=require('../shared/sharp-consensus.js'),V=require('../shared/market-validation.js'),W=require('../config/sharp_weights.json');
const normalize=SC.makeNormalizer(W.aliases);

/* Optional external forecasts: {"<gameId>|<market>|<line>": {"p": probability side A wins (home / over / home ML), "asOf": ISO time}}.
 * A forecast made after the pricing board is future information and is refused, never silently used. */
function buildRecords(input,{devig='probit',minSources=3,models=null}={}){
 const byMarket={moneyline:[],spread:[],total:[]},refused={future:0,invalid:0};
 for(const r of input.records||[]){
  const t=Date.parse(r.snapshotAt),probs={};
  if(!Number.isFinite(t)||!(r.y===0||r.y===1)||!byMarket[r.market])continue;
  for(const [book,[a,b]] of Object.entries(r.quotes||{})){
   const d=SC.devigPair(SC.americanToDecimal(a),SC.americanToDecimal(b),devig);
   // Same crossed-quote rule as live consensus; several books can map to one canonical source, the later one is dropped.
   if(!d||d.overround<.985)continue;
   const s=normalize(book);if(!(s in probs))probs[s]=d.pA;
  }
  if(Object.keys(probs).length<minSources)continue;
  const row={t,gameId:r.gameId,y:r.y,probs},f=models?.[[r.gameId,r.market,r.line].join('|')];
  if(f){
   if(!(f.p>0&&f.p<1)||!Number.isFinite(Date.parse(f.asOf)))refused.invalid++;
   else if(Date.parse(f.asOf)>t)refused.future++;
   else row.model=f.p;
  }
  byMarket[r.market].push(row);
 }
 Object.defineProperty(byMarket,'refused',{value:refused,enumerable:false});
 return byMarket;
}
function run(input,opts={}){
 const by=buildRecords(input,opts),out={schema:'going-missions-backtest-v1',note:input.note,gaps:input.gaps,externalForecastsRefused:by.refused,markets:{}};
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
 const args=process.argv.slice(2),take=name=>{const i=args.indexOf(name);if(i<0)return null;const v=args[i+1];args.splice(i,2);return v;};
 const modelFile=take('--model'),outFile=take('--out'),[file]=args,flag=outFile?'--out':null,dest=outFile;
 if(!file){console.error('usage: node scripts/missions_backtest.cjs <missions-backtest-input.json> [--model forecasts.json] [--out report.json]');process.exit(2);}
 const report=run(JSON.parse(fs.readFileSync(file,'utf8')),{models:modelFile?JSON.parse(fs.readFileSync(modelFile,'utf8')):null});
 if(flag==='--out'){
  const root=path.resolve(__dirname,'..'),target=path.resolve(dest);
  if(target===root||target.startsWith(root+path.sep)){console.error('Refusing to write private archive derivatives inside the repository.');process.exit(2);}
  fs.writeFileSync(target,JSON.stringify(report,null,1));
 }
 console.log(JSON.stringify(report,null,1));
}
