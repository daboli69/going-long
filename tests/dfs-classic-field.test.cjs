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
