const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
test('Today routes exact market filters and exposes forecast provenance without changing the frozen board',()=>{
 assert.match(html,/x\.candidate\.market===PICKS_FAMILY\[sport\]/);
 assert.match(html,/GoingFootballPicks\.displayMix\(list/);
 assert.match(html,/gameAnchor:\{version:m\.anchored\?\.version,applicable:/);
 assert.match(html,/ratingPresentation\(x\.candidate,x\.evidence\)/);
 assert.match(html,/'Game','spread','total','moneyline'/);
});
test('legacy Signals automatic suggestions also exclude extreme, stale, unavailable and inconsistent prices',()=>{
 const start=html.indexOf('function signalBuild(rows,'),end=html.indexOf('function signalBuildSettlement(',start),now=Date.now();
 const context=vm.createContext({Date,finiteNumber:Number.isFinite,americanToDecimal:o=>o>0?1+o/100:1+100/-o});
 vm.runInContext(html.slice(start,end),context);
 const base={flags:[{id:'pace',family:'role',why:'Published pace'}],market:'total',prob:.6,ev:.1,push:0,odds:-110,dec:1+100/110,book:'Book',updatedAt:new Date(now-1000).toISOString(),kickoff:new Date(now+3600000).toISOString()};
 const pair=[{...base,event:'a'},{...base,event:'b'}];assert.ok(context.signalBuild(pair));
 for(const bad of [{odds:-40000,dec:1.0025},{dec:3},{updatedAt:new Date(now-86400001).toISOString()},{injury:{blockRecommendation:true}},{availability:{eligible:false}},{trust:{review:true}}])assert.equal(context.signalBuild(pair.map(r=>({...r,...bad}))),null);
});
