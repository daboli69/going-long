// Per-record equal-weight de-vigged pregame probabilities from the private missions export (kept outside Git).
// Uses exactly the same books->source normalisation, de-vig and crossed-quote rule as scripts/missions_backtest.cjs.
// usage: node scripts/archive_market_probs.cjs <missions-backtest-input.json> <out.json>   (refuses to write inside the repository)
const fs=require('node:fs'),path=require('node:path');
const SC=require('../shared/sharp-consensus.js'),V=require('../shared/market-validation.js'),W=require('../config/sharp_weights.json');
const normalize=SC.makeNormalizer(W.aliases);
function marketProbs(input,{devig='probit',minSources=3}={}){
 const rows=[];
 for(const r of input.records||[]){
  const probs={};
  for(const [book,[a,b]] of Object.entries(r.quotes||{})){
   const d=SC.devigPair(SC.americanToDecimal(a),SC.americanToDecimal(b),devig);
   if(!d||d.overround<.985)continue;
   const s=normalize(book);if(!(s in probs))probs[s]=d.pA;
  }
  const n=Object.keys(probs).length;
  if(n<minSources)continue;
  const p=V.pool(probs,Object.fromEntries(Object.keys(probs).map(s=>[s,1])));
  rows.push({gameId:r.gameId,market:r.market,line:r.line,y:r.y,snapshotAt:r.snapshotAt,kickoff:r.kickoff,pEqual:p,sources:n});
 }
 return rows;
}
module.exports={marketProbs};
if(require.main===module){
 const [file,out]=process.argv.slice(2);
 if(!file||!out){console.error('usage: node scripts/archive_market_probs.cjs <input.json> <out.json>');process.exit(2);}
 const root=path.resolve(__dirname,'..'),target=path.resolve(out);
 if(target===root||target.startsWith(root+path.sep)){console.error('Refusing to write private archive derivatives inside the repository.');process.exit(2);}
 const rows=marketProbs(JSON.parse(fs.readFileSync(file,'utf8')));
 fs.writeFileSync(target,JSON.stringify(rows));
 console.log(JSON.stringify({records:rows.length}));
}
