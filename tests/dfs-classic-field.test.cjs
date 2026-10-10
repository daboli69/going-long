const {test}=require('node:test'),assert=require('node:assert/strict');
const F=require('../shared/dfs-classic-field.js');
const toy={schema:'going-private-classic-ownership-v1',slot_totals:{QB:100},positions:['QB'],models:{salary_only:{QB:{features:['s','s2','lrank'],beta:[.8,0,-.1]}}}};
test('Classic ownership is off without the private file and sums to the slot total with it',()=>{
 const pool=[7000,6000,5000].map((salary,i)=>({id:i,position:'QB',salary}));
 F.annotate(pool);assert.equal(pool[0].ownership,undefined);
 assert.equal(F.load('{}').ok,false);assert.equal(F.load(toy).ok,true);F.annotate(pool);
 assert.ok(Math.abs(pool[0].ownership-62.49)<.01&&Math.abs(pool[1].ownership-26.20)<.01&&Math.abs(pool[2].ownership-11.30)<.01);
 assert.ok(Math.abs(pool.reduce((s,p)=>s+p.ownership,0)-100)<1e-9);
 assert.equal(F.lineupOwnership([{ownership:20},{ownership:10}]).chalk,1);assert.equal(F.lineupOwnership([{ownership:20},{}]),null);
 F.clear();assert.equal(F.ready(),false);
});

test('lineup ownership is a labelled sum; the calibrated estimate appears only with a lineup_calibration block and is monotone/clamped',()=>{
 const full={...toy,slot_totals:{QB:100}},lineup=Array.from({length:9},(_,i)=>({ownership:5+i}));
 F.load(full);F.state.fieldSq=100;
 let o=F.lineupOwnership(lineup);
 assert.equal(o.total,81);assert.equal(o.calibrated,false);assert.match(o.statistic,/sum of model player ownership/);
 F.load({...full,lineup_calibration:{params:{a:Math.log(2),b:.5,s:.25,clamp:[.4,1.6]},heldout:{realised_over_estimate_p10_p90:[.8,1.3],contests:25,lineup_mae_uncalibrated:80,lineup_mae_calibrated:40,field_level_bias_uncalibrated:-.28,field_level_bias_calibrated:-.06,within_contest_corr_P_vs_A:.17}}});
 F.state.fieldSq=100;o=F.lineupOwnership(lineup);
 // level = 2*sqrt(100) = 20 ; ratio .81 -> 20*(1+.25*(.81-1)) = 19.05
 assert.equal(o.calibrated,true);assert.ok(Math.abs(o.fieldTypical-20)<1e-9&&Math.abs(o.expected-19.05)<1e-9);
 assert.ok(Math.abs(o.low-19.05*.8)<1e-9&&Math.abs(o.high-19.05*1.3)<1e-9);
 const hi=F.expectedSum(1e6,100),lo=F.expectedSum(0,100);assert.ok(hi.expected<=20*(1+.25*.6)+1e-9&&lo.expected>=20*(1-.25*.6)-1e-9);
 assert.equal(F.expectedSum(81,0),null);assert.equal(F.lineupOwnership(lineup.slice(0,8)).calibrated,false);
 F.load({...full,lineup_calibration:{params:{a:'x'}}});F.state.fieldSq=100;assert.equal(F.lineupOwnership(lineup).calibrated,false);
 F.clear();
});

test('annotate records the model field-typical sum (sum of squares / 100)',()=>{
 const pool=[7000,6000,5000].map((salary,i)=>({id:i,position:'QB',salary}));F.load(toy);F.annotate(pool);
 const want=pool.reduce((s,p)=>s+p.ownership**2,0)/100;assert.ok(Math.abs(F.state.fieldSq-want)<1e-9);F.clear();assert.equal(F.state.fieldSq,null);
});
