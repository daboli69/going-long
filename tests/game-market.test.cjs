const {test}=require('node:test'),assert=require('node:assert/strict');
const G=require('../shared/game-market.js');
const raw={margin_mean:7.2,total_mean:51.4,margin_sd:12,total_sd:11,home_n:8,away_n:8};
test('anchoring replaces trailing means with the posted line and keeps the raw model for provenance',()=>{
 const a=G.anchor({sport:'nfl',spread:-3,total:44.5},raw);
 assert.equal(a.margin_mean,3);assert.equal(a.total_mean,44.5);assert.equal(a.total_sd,13.3);assert.equal(a.margin_sd,12.75);
 assert.equal(a.anchored.raw_total_mean,51.4);assert.equal(a.home_n,8);assert.equal(raw.total_mean,51.4);
});
test('missing lines fall back to the raw model per market; NCAA uses its own SD',()=>{
 const a=G.anchor({sport:'ncaa',total:55},raw,'ncaa');assert.equal(a.total_mean,55);assert.equal(a.total_sd,15);assert.equal(a.margin_mean,7.2);assert.equal(a.margin_sd,12);
 assert.equal(G.anchor({sport:'nfl'},raw),raw);assert.equal(G.anchor({spread:-3},null),null);
});
test('period models scale from the anchored full game by the pipeline fractions',()=>{
 const per={total_mean:51.4*.25,total_sd:11*Math.sqrt(.25),margin_mean:7.2*.25,margin_sd:12*Math.sqrt(.25)};
 const p=G.anchorPeriod({spread:-4,total:40},raw,per,'nfl');
 assert.ok(Math.abs(p.total_mean-10)<1e-9);assert.ok(Math.abs(p.margin_mean-1)<1e-9);assert.ok(Math.abs(p.total_sd-13.3/2)<1e-9);
});
test('kill switch restores the raw model',()=>{
 globalThis.GOING_GAME_ANCHOR=false;try{assert.equal(G.anchor({spread:-3,total:44},raw),raw);}finally{delete globalThis.GOING_GAME_ANCHOR;}
});
test('anchored over/under on the posted total is a coin flip so EV is minus the vig',()=>{
 const a=G.anchor({spread:-3,total:44.5},raw),z=(44.5+.5-a.total_mean)/a.total_sd;assert.ok(Math.abs(z)<.05);
});
test('strict period anchoring refuses to price without both posted lines',()=>{
 const per={total_mean:12,total_sd:6,margin_mean:1,margin_sd:6};
 assert.equal(G.anchorPeriod({spread:-3},raw,per,'nfl',{strict:true}),null);
 assert.equal(G.anchorPeriod({},raw,per,'nfl',{strict:true}),null);
 assert.ok(G.anchorPeriod({spread:-3,total:44},raw,per,'nfl',{strict:true}));
});
test('moneyline keeps a 0.4% tie, not the ~3% a discretised normal implies',()=>{
 const m=G.moneyline({over:.4,under:.57,push:.03});assert.ok(Math.abs(m.push-.004)<1e-12);assert.ok(Math.abs(m.over+m.under+m.push-1)<1e-12);assert.ok(Math.abs(m.over/m.under-.4/.57)<1e-9);
 assert.equal(G.moneyline(null),null);
});
test('anchored spread pushes follow the key numbers, half points stay 50/50, raw models are untouched',()=>{
 const m=G.anchor({spread:-3,total:44},raw),n={over:.5,under:.5,push:0};
 const s3=G.spread({over:.485,under:.485,push:.03},m,-3);assert.equal(s3.push,.09);assert.ok(Math.abs(s3.over-.455)<1e-9);
 assert.equal(G.spread({over:.5,under:.5,push:0},G.anchor({spread:-3.5},raw),-3.5).over,.5);
 assert.equal(G.spread(n,raw,-3),n);assert.ok(G.spreadPush(7)>G.spreadPush(5));assert.equal(G.spreadPush(3.5),0);
});
test('a row with a moneyline but no spread is anchored to the de-vigged moneyline, not the raw model',()=>{
 const g={mlHome:-200,mlAway:170},a=G.anchor(g,raw,'nfl');
 assert.equal(a.anchored.marginSource,'moneyline');assert.ok(a.margin_mean>3&&a.margin_mean<9);
 // the discretised two-way split of the anchored model reproduces the fair moneyline probability
 const ph=(1/1.5)/(1/1.5+1/2.7),cdf=x=>{const t=1/(1+.2316419*Math.abs(x)),d=.3989423*Math.exp(-x*x/2),p=d*t*(.3193815+t*(-.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));return x>0?1-p:p;};
 const over=1-cdf((.5-a.margin_mean)/a.margin_sd),under=cdf((-.5-a.margin_mean)/a.margin_sd);assert.ok(Math.abs(over/(over+under)-ph)<1e-3);
 assert.equal(G.anchor({spread:-3,mlHome:-200,mlAway:170},raw,'nfl').anchored.marginSource,'spread');
 assert.equal(G.anchor({mlHome:null,mlAway:null},raw,'nfl'),raw);
});
