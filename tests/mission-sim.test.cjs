const {test}=require('node:test'),assert=require('node:assert/strict');
const {simulate,validateConfig}=require('../shared/mission-sim.js');
const base={bankroll:50,target:100,withdrawTarget:50,reserve:50,weeks:1,maxExposure:1,runs:20000,seed:11,sigmaLeg:0,sigmaSystematic:0};
const leg=(id,p,dec,o={})=>({id,eventId:o.eventId||id,p,push:o.push||0,loading:o.loading||0,dec});
const tk=(id,legs)=>({id,legIds:legs.map(l=>l.id),decs:legs.map(l=>l.dec),weight:1});
const strat=(id,tickets)=>({id,name:id,tickets});
const near=(a,b,tol,m)=>assert.ok(Math.abs(a-b)<=tol,`${m||''} ${a} vs ${b}`);

test('same seed reproduces results exactly; a different seed changes them',()=>{
 const a=leg('a',.5,2),run=seed=>simulate({pool:[a],strategies:[strat('s',[tk('t',[a])])],config:{...base,seed}})[0];
 assert.deepEqual(run(5),run(5));assert.notEqual(run(5).pReachTarget,run(6).pReachTarget);
});
test('no-bet baseline never moves, reaches nothing and never ruins',()=>{
 const r=simulate({pool:[],strategies:[strat('none',[])],config:base})[0];
 assert.equal(r.pReachTarget,0);assert.equal(r.expectedEnding,50);assert.equal(r.pRuin,0);assert.equal(r.pEndBelowStart,0);assert.equal(r.preservation[2].p,1);
});
test('fair double-or-nothing matches the analytic reach probability and its sampling interval',()=>{
 const a=leg('a',.5,2),r=simulate({pool:[a],strategies:[strat('s',[tk('t',[a])])],config:base})[0];
 near(r.pReachTarget,.5,.015);assert.ok(r.pReachTargetCI[0]<=.5&&.5<=r.pReachTargetCI[1]);
 near(r.pRuin,.5,.015);near(r.expectedWithdrawal,25,1);
});
test('independent parlay reach probability equals the product of leg probabilities',()=>{
 const legs=[leg('a',.6,1.8),leg('b',.55,1.9),leg('c',.5,2)];
 const r=simulate({pool:legs,strategies:[strat('p',[tk('p',legs)])],config:{...base,target:150,withdrawTarget:100,runs:60000}})[0];
 near(r.pReachTarget,.6*.55*.5,.006);
});
test('positively loaded legs in one game win together more often than independent legs',()=>{
 const indep=[leg('a',.5,3.7,{eventId:'g'}),leg('b',.5,3.7,{eventId:'h'})],corr=[leg('a',.5,3.7,{eventId:'g',loading:.9}),leg('b',.5,3.7,{eventId:'g',loading:.9})];
 const cfg={...base,target:150,withdrawTarget:100,runs:60000};
 const i=simulate({pool:indep,strategies:[strat('s',[tk('t',indep)])],config:cfg})[0].pReachTarget,c=simulate({pool:corr,strategies:[strat('s',[tk('t',corr)])],config:cfg})[0].pReachTarget;
 near(i,.25,.01);assert.ok(c>i+.1,`${c} vs ${i}`);
 const neg=[leg('a',.5,3.7,{eventId:'g',loading:.9}),leg('b',.5,3.7,{eventId:'g',loading:-.9})];
 assert.ok(simulate({pool:neg,strategies:[strat('s',[tk('t',neg)])],config:cfg})[0].pReachTarget<i-.1);
});
test('a push voids a parlay leg and refunds a fully pushed ticket',()=>{
 const a=leg('a',.5,2,{push:.5}),r=simulate({pool:[a],strategies:[strat('s',[tk('t',[a])])],config:{...base,target:100,withdrawTarget:0,withdraw:false,runs:40000}})[0];
 near(r.expectedEnding,50,.8);near(r.pReachTarget,.25,.01);
 const x=leg('x',.5,2,{push:1-1e-9}),y=leg('y',.5,2),two=simulate({pool:[x,y],strategies:[strat('s',[tk('t',[x,y])])],config:{...base,target:100,withdraw:false,runs:20000}})[0];
 near(two.pReachTarget,.5,.03,'parlay with a pushed leg pays like the remaining straight');
});
test('probability uncertainty widens outcomes without changing the central estimate much',()=>{
 const a=leg('a',.5,2),cfg={...base,target:60,withdrawTarget:0,withdraw:false,maxExposure:.2,weeks:12,runs:8000};
 const sure=simulate({pool:[a],strategies:[strat('s',[tk('t',[a])])],config:cfg})[0],unsure=simulate({pool:[a],strategies:[strat('s',[tk('t',[a])])],config:{...cfg,sigmaSystematic:.4}})[0];
 assert.ok(unsure.totalValueP90-unsure.totalValueP10>sure.totalValueP90-sure.totalValueP10);
});
test('negative expected value loses on average; withdrawal never exceeds balance above the reserve',()=>{
 const a=leg('a',.45,2),r=simulate({pool:[a],strategies:[strat('s',[tk('t',[a])])],config:{...base,weeks:8,maxExposure:.5}})[0];
 assert.ok(r.totalValueMean<50);assert.ok(r.expectedWithdrawal>=0);assert.ok(r.preservation[0].p>=r.preservation[2].p);
 assert.ok(r.preservation[2].pSolvent>=r.preservation[2].p);
});
test('invalid settings are rejected, never silently coerced',()=>{
 for(const bad of [{target:40},{bankroll:0},{weeks:0},{maxExposure:0},{maxExposure:1.2},{runs:5},{reserve:200}])assert.throws(()=>validateConfig({...base,...bad}),/Invalid mission settings/);
 assert.throws(()=>simulate({pool:[leg('a',1,2)],strategies:[],config:base}),/out of range/);
 assert.throws(()=>simulate({pool:[],strategies:[strat('s',[{id:'t',legIds:['zz'],decs:[2],weight:1}])],config:base}),/Unknown leg/);
});
