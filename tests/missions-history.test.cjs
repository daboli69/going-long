const {test}=require('node:test'),assert=require('node:assert/strict');
const {buildRecords,run}=require('../scripts/missions_backtest.cjs');
function rng(a){return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const am=p=>{const d=1/p;return d>=2?Math.round((d-1)*100):Math.round(-100/(d-1));};
// Clearly synthetic: pinnacle sees the truth closely, the others see noise. Never real odds.
function synthetic(n,seed=3){
 const r=rng(seed),g=()=>{let u=0;while(!u)u=r();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*r());},records=[];
 for(let i=0;i<n;i++){
  const truth=Math.min(.95,Math.max(.05,.5+.2*g())),y=r()<truth?1:0,quotes={};
  const book=(noise,vig)=>{const p=Math.min(.97,Math.max(.03,truth+noise*g()));const a=Math.min(.98,p*(1+vig/2)),b=Math.min(.98,(1-p)*(1+vig/2));return [am(a),am(b)];};
  quotes.pinnacle=book(.01,.04);quotes.draftkings=book(.08,.05);quotes.williamhill_us=book(.08,.05);quotes.fanatics=book(.08,.05);quotes.betonlineag=book(.08,.05);
  records.push({gameId:'g'+i,market:'moneyline',line:null,y,snapshotAt:new Date(Date.UTC(2025,8,1)+i*3600e3).toISOString(),quotes});
 }
 return {note:'synthetic',gaps:{},records};
}
test('records keep source aliases, drop crossed quotes and require enough independent sources',()=>{
 const rec=synthetic(5).records;rec[0].quotes.bovada=[200,200];rec[1].quotes={pinnacle:[-110,-110],draftkings:[-110,-110]};
 const by=buildRecords({records:rec});
 assert.ok('caesars' in by.moneyline[0].probs&&'betonline' in by.moneyline[0].probs);
 assert.ok(!('bovada' in by.moneyline[0].probs),'crossed pair dropped');
 assert.equal(by.moneyline.length,4,'two-source record excluded');
 assert.equal(buildRecords({records:[{...rec[2],y:.5}]}).moneyline.length,0);
});
test('walk-forward on synthetic archive: learned weights find the informative book; the single-book baseline is significant',()=>{
 const report=run(synthetic(1800),{minTrain:150}),m=report.markets.moneyline;
 assert.equal(m.games,1800);assert.ok(m.comparison.ok);
 const d=m.comparison.differencesVsEqual;
 assert.ok(d.learned.logLoss.mean<0,'learned improves the out-of-sample point estimate');
 const w=m.comparison.weights.at(-1).weights;assert.ok(w.pinnacle>.5&&w.pinnacle>Math.max(w.draftkings,w.fanatics),'learned weight finds the informative book');
 assert.ok(m.pinnacleOnly.differencesVsEqual.logLoss.hi<0);
 assert.match(report.conclusion,/includes 0/);assert.equal(report.markets.spread.records,0);
});
test('an external forecast is compared with the market on the same records and a forecast made after the board is refused',()=>{
 const input=synthetic(1500,11),models={};let n=0;
 for(const r of input.records){const key=[r.gameId,r.market,r.line].join('|'),t=Date.parse(r.snapshotAt);
  // synthetic "model": a noisy version of the truth, available an hour before the board for the first 600 games, and after it for 20
  const quotes=Object.values(r.quotes).map(([a,b])=>{const qa=1/(a>0?1+a/100:1+100/-a),qb=1/(b>0?1+b/100:1+100/-b);return qa/(qa+qb);}),mkt=quotes.reduce((x,y)=>x+y,0)/quotes.length;
  if(n<600)models[key]={p:Math.min(.95,Math.max(.05,mkt)),asOf:new Date(t-3600e3).toISOString()};
  else if(n<620)models[key]={p:.99,asOf:new Date(t+60e3).toISOString()};
  n++;}
 const by=buildRecords(input,{models});assert.equal(by.refused.future,20);assert.equal(by.moneyline.filter(r=>'model' in r).length,600);
 const out=run(input,{models,minTrain:150}).markets.moneyline.comparison;
 assert.ok(out.matched&&out.matched.n>0&&out.matched.n<=600,'scored on the matched subset only');
 assert.ok(out.matched.model.logLoss>0&&out.matched.equal.logLoss>0);
 assert.ok(Math.abs(out.matched.model.brier-out.matched.equal.brier)<.02,'a market-copy forecast scores like the market on the same records');
 assert.equal(buildRecords(input,{}).refused.future,0);
});

test('learned source weights stay finite and normalised when a vanishing-weight source is the only one on a board (regression: spread walk-forward returned no folds)',()=>{
 const V=require('../shared/market-validation.js'),r=rng(5),records=[];
 // One near-perfect source crushes the noise source's weight toward zero; boards that carry only the noise source then give an unbounded gradient.
 for(let i=0;i<150;i++){const y=r()<.5?1:0,probs={good:y?.97:.03,noise:.5+(r()-.5)*.1};if(i%25===0)delete probs.good;records.push({t:i,gameId:'g'+i,y,probs});}
 const {weights}=V.learnWeights(records,{sources:['good','noise']});
 const values=Object.values(weights);
 assert.ok(values.every(Number.isFinite),'every weight is finite');
 assert.ok(Math.abs(values.reduce((x,y)=>x+y,0)-1)<1e-9,'weights sum to one');
 assert.ok(weights.good>weights.noise,'the informative source still gets the larger weight');
});
