const {test}=require('node:test');
const assert=require('node:assert/strict');
const threshold=require('../shared/dfs-threshold.js');
// Synthetic hand-verifiable counts/means; no real salaries, slate or calibrated prediction is claimed.
const p=(team,tdMean,position='RB',extra={})=>({team,tdMean,position,...extra});
const budget=(counts,denominator,extra={})=>({counts,denominator,n:counts.length,provenance:{source:'Synthetic completed-game fixture'},...extra});
const scenario=teams=>({version:'team-budget-v1',teams});
const close=(a,b,tolerance=1e-12)=>assert.ok(Math.abs(a-b)<=tolerance,`${a} != ${b}`);
function bruteForce(counts,share){
 const bins=new Array(9).fill(0);
 for(const n of counts)for(let mask=0;mask<2**n;mask++){
  let successes=0;for(let i=0;i<n;i++)successes+=(mask>>i)&1;
  bins[Math.min(8,successes)]+=share**successes*(1-share)**(n-successes)/counts.length;
 }
 return bins;
}
test('exact eight-TD binomial tail agrees with hand math',()=>{
 const result=threshold.evaluate([p('BUF',4)],scenario({BUF:budget([8],8)}));assert.equal(result.valid,true);close(result.tailMass,1/256);close(result.expectedTDs,4);close(result.bins[0],1/256);close(result.bins[1],8/256);close(result.bins.reduce((a,b)=>a+b,0),1);assert.equal(result.support[0].share,.5);
});
test('equally weighted empirical mixtures agree with exhaustive allocation outcomes',()=>{
 for(const share of [0,.1,.25,.5,.9,1]){
  const counts=[0,2,5,8,10],result=threshold.evaluate([p('BUF',5*share)],scenario({BUF:budget(counts,5)})),exact=bruteForce(counts,share);
  assert.equal(result.valid,true);result.bins.forEach((value,i)=>close(value,exact[i]));close(result.expectedTDs,counts.reduce((a,b)=>a+b,0)/counts.length*share);
 }
});
test('absorbing threshold convolution includes outcomes greater than eight',()=>{
 const result=threshold.evaluate([p('BUF',4),p('KC',5)],scenario({BUF:budget([4],4),KC:budget([5],5)}));assert.equal(result.valid,true);assert.equal(result.tailMass,1);assert.equal(result.expectedTDs,9);assert.deepEqual(result.bins,[0,0,0,0,0,0,0,0,1]);
 const uncertain=threshold.evaluate([p('BUF',2),p('KC',2)],scenario({BUF:budget([4],4),KC:budget([4],4)}));close(uncertain.tailMass,1/256);close(uncertain.expectedTDs,4);
});
test('eight-plus scenario ranking differs from ranking by summed means',()=>{
 const evidence=scenario({BUF:budget([7],7),KC:budget([0,8],4)}),higherMean=threshold.evaluate([p('BUF',7)],evidence),higherTail=threshold.evaluate([p('KC',4)],evidence);
 assert.ok(higherMean.expectedTDs>higherTail.expectedTDs);assert.equal(higherMean.tailMass,0);assert.equal(higherTail.tailMass,.5);assert.ok(higherTail.tailMass>higherMean.tailMass);
});
test('one player can receive several TDs; distribution is not binary anytime TD',()=>{
 const result=threshold.evaluate([p('BUF',2)],scenario({BUF:budget([4],4)}));assert.equal(result.valid,true);assert.ok(result.bins[2]>0);assert.ok(result.bins[3]>0);assert.ok(result.bins[4]>0);close(result.bins[2],6/16);close(result.bins[4],1/16);
 const solo=threshold.evaluate([p('BUF',8)],scenario({BUF:budget([8],8)}));assert.equal(solo.tailMass,1);
});
test('DST and passing TD fields never contribute; QB rushing/receiving tdMean does',()=>{
 const evidence=scenario({BUF:budget([8],8)}),base=threshold.evaluate([p('BUF',1,'QB')],evidence),passing=threshold.evaluate([p('BUF',1,'QB',{passTds:99,passingTdMean:99}),p('MISSING',Infinity,'DST')],evidence);
 assert.deepEqual(passing.bins,base.bins);assert.equal(passing.expectedTDs,1);close(passing.tailMass,(1/8)**8);
 const noRush=threshold.evaluate([p('BUF',0,'QB',{pass_tds:99})],evidence);assert.equal(noRush.expectedTDs,0);assert.equal(noRush.tailMass,0);assert.deepEqual(noRush.bins,[1,0,0,0,0,0,0,0,0]);
});
test('teammates share a finite budget with multinomial competition rather than duplicated team scores',()=>{
 const evidence=scenario({BUF:budget([2],2)}),a=threshold.evaluate([p('BUF',1)],evidence),b=threshold.evaluate([p('BUF',1),p('BUF',1)],evidence);
 close(a.bins[2],.25);assert.deepEqual(b.bins,[0,0,1,0,0,0,0,0,0]);assert.equal(b.expectedTDs,2);assert.equal(b.tailMass,0);
 // Conditional Cov(X_A,X_B)=-N*p_A*p_B=-0.5 for N=2,
 // p_A=p_B=0.5: Var(X_A+X_B)=0.5+0.5+2*(-0.5)=0.
 const variance=b.bins.reduce((sum,mass,k)=>sum+mass*(k-b.expectedTDs)**2,0);assert.equal(variance,0);
});
test('denominator surplus allocates unselected players residual opportunity and does not invent team TDs',()=>{
 const result=threshold.evaluate([p('BUF',4)],scenario({BUF:budget([2],8,{allVerifiedPlayerMean:8})}));assert.equal(result.valid,true);assert.equal(result.support[0].share,.5);assert.equal(result.expectedTDs,1);assert.equal(result.tailMass,0);
});
test('missing or corrupt empirical evidence fails closed',()=>{
 const good=budget([2,8],5),badScenarios=[null,{},scenario({}),{version:'other',teams:{BUF:good}},scenario({BUF:budget([],5)}),scenario({BUF:budget([1.5],5)}),scenario({BUF:budget([-1],5)}),scenario({BUF:budget([Infinity],5)}),scenario({BUF:budget([8],0)}),scenario({BUF:budget([8],7)}),scenario({BUF:budget([8],NaN)}),scenario({BUF:budget([8],8,{n:2})}),scenario({BUF:budget([8],8,{allVerifiedPlayerMean:9})}),scenario({FAKE:good}),scenario({JAX:good,JAC:good})];
 for(const evidence of badScenarios){const result=threshold.evaluate([p('BUF',1)],evidence);assert.equal(result.valid,false);assert.equal(result.tailMass,null);assert.equal(result.bins,null);assert.ok(result.errors.length);}
 for(const lineup of [[],[p('BUF',-1)],[p('BUF',NaN)],[p('BUF',1,'K')],[p('BUF',6)]])assert.equal(threshold.evaluate(lineup,scenario({BUF:good})).valid,false);
});
test('canonical aliases work and output is deterministic without mutating inputs',()=>{
 const evidence=scenario({LAR:budget([3,8],6)}),lineup=[p('LA',2),p('LAR',1)];const frozen=JSON.stringify({evidence,lineup}),one=threshold.evaluate(lineup,evidence),two=threshold.evaluate(lineup,evidence);
 assert.equal(one.valid,true);assert.deepEqual(one,two);assert.equal(one.support[0].team,'LA');assert.equal(JSON.stringify({evidence,lineup}),frozen);assert.deepEqual(one.provenance,[{team:'LA',provenance:{source:'Synthetic completed-game fixture'}}]);assert.match(one.limitations.join(' '),/not a validated lineup probability/);assert.match(one.limitations.join(' '),/independently/);
});
test('zero team history stays zero and allocation is numerically finite at extreme shares',()=>{
 const none=threshold.evaluate([p('BUF',1)],scenario({BUF:budget([0,0],2)}));assert.equal(none.tailMass,0);assert.equal(none.expectedTDs,0);
 for(const mean of [0,1e-12,1,8-1e-12,8]){const r=threshold.evaluate([p('BUF',mean)],scenario({BUF:budget([8],8)}));assert.equal(r.valid,true);assert.ok(r.bins.every(m=>Number.isFinite(m)&&m>=0));close(r.bins.reduce((a,b)=>a+b,0),1);assert.ok(r.tailMass>=0&&r.tailMass<=1);}
});
test('hundreds of full-lineup scenario evaluations remain bounded',()=>{
 const evidence=scenario({BUF:budget([0,1,2,3,4,5,6,8],4),KC:budget([1,2,3,4,5,7,9],5),DEN:budget([0,1,1,2,2,4],3)}),lineup=[p('BUF',.2,'QB'),p('BUF',1),p('KC',.8),p('BUF',.6,'WR'),p('KC',.5,'WR'),p('DEN',.4,'WR'),p('DEN',.3,'TE'),p('KC',.3,'RB'),p('FAKE',999,'DST')];
 const started=performance.now();for(let i=0;i<500;i++)assert.equal(threshold.evaluate(lineup,evidence).valid,true);assert.ok(performance.now()-started<1500,'500 complete candidate evaluations should finish within 1.5 seconds.');
});
