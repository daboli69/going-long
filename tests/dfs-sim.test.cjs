const {test}=require('node:test');
const assert=require('node:assert/strict');
require('../shared/dfs-correlations.js');
const S=require('../shared/dfs-sim.js');
const close=(a,b,tol=1e-6)=>assert.ok(Math.abs(a-b)<=tol,`${a} != ${b}`);

const wr={receptions:{family:'poisson',lambda:5,status:'ready'},
 rec_yds:{family:'lognormal',mu_log:Math.log(60)-0.5*0.36*0.36,sigma_log:0.6,positive_weight:0.9,nonpositive:[0],nonpositive_weights:[0.1],status:'ready'},
 rec_tds:{family:'poisson',lambda:0.4,status:'ready'}};
const qb={pass_yds:{family:'lognormal',mu_log:Math.log(250)-0.5*0.09,sigma_log:0.3,positive_weight:1,nonpositive:[],status:'ready'},pass_tds:{family:'poisson',lambda:1.6,status:'ready'},
 rush_yds:{family:'lognormal',mu_log:Math.log(25),sigma_log:0.8,positive_weight:.85,nonpositive:[0],nonpositive_weights:[.15],status:'ready'},rush_tds:{family:'poisson',lambda:.2,status:'ready'}};

test('normal inverse and distribution agree with reference values',()=>{
 close(S.normalPpf(.975),1.959963984540054,1e-7);close(S.normalPpf(.5),0,1e-12);close(S.normalPpf(.001),-3.090232306167813,1e-6);
 close(S.normalCDF(1.96),.9750021048517795,1e-6);
 for(const u of [.01,.3,.77,.999])close(S.normalCDF(S.normalPpf(u)),u,1e-6);
});

test('stat-model quantile functions match scipy',()=>{
 assert.deepEqual([.01,.2,.5,.9,.99].map(u=>S.ppfModel(wr.receptions,u)),[1,3,5,8,11]);
 assert.deepEqual([.5,.7,.9,.99].map(u=>S.ppfModel(wr.rec_tds,u)),[0,1,1,2]);
 assert.deepEqual([.05,.1,.11,.5,.9,.99].map(u=>S.ppfModel(wr.rec_yds,u)),[0,0,14,52,117,222]);
 assert.equal(S.ppfModel({family:'poisson',lambda:0,status:'ready'},.9),0);
 assert.equal(S.ppfModel({status:'insufficient'},.5),0);
});

test('scoring: DraftKings bonuses and FanDuel half-point receptions',()=>{
 close(S.score({pass_yds:300,pass_tds:2,rush_yds:20}),12+3+8+2);
 close(S.score({rec_yds:100,receptions:8,rec_tds:1}),10+3+8+6);
 close(S.score({receptions:8,rec_yds:100,rec_tds:1},'fanduel'),10+4+6);
});

test('a player distribution is deterministic, ordered and wider than independent components',()=>{
 const a=S.player(wr,'WR',{id:'p1'}),b=S.player(wr,'WR',{id:'p1'}),indep=S.player(wr,'WR',{id:'p1',independent:true});
 assert.equal(a.mean,b.mean);assert.equal(a.p90,b.p90);
 assert.ok(a.floor<=a.p25&&a.p25<=a.median&&a.median<=a.p75&&a.p75<=a.p90&&a.p90<=a.p95);
 assert.ok(a.sd>indep.sd*1.15,`copula sd ${a.sd} should clearly exceed independent ${indep.sd}`);
 close(a.mean,indep.mean,.6);
 assert.ok(a.boom>0&&a.boom<.5&&a.bust>0&&a.bust<.5);
 assert.equal(S.player({},'WR',{id:'x'}),null);assert.equal(S.player(wr,'K',{id:'x'}),null);
});

test('within-player dependence reproduces the measured receptions-yards correlation',()=>{
 const draws=4000,m=S.cholesky([[1,.752],[.752,1]]);assert.equal(m.shrink,1);
 const rngs=[],random=(()=>{let s=12345;return ()=>{s=(s*1664525+1013904223)%4294967296;return s/4294967296;};})();
 let sx=0,sy=0,sxx=0,syy=0,sxy=0;
 for(let i=0;i<draws;i++){const u=Math.sqrt(-2*Math.log(random()||1e-9))*Math.cos(2*Math.PI*random()),v=Math.sqrt(-2*Math.log(random()||1e-9))*Math.cos(2*Math.PI*random());const x=m.L[0][0]*u,y=m.L[1][0]*u+m.L[1][1]*v;sx+=x;sy+=y;sxx+=x*x;syy+=y*y;sxy+=x*y;}
 const r=(sxy/draws-sx*sy/draws/draws)/Math.sqrt((sxx/draws-(sx/draws)**2)*(syy/draws-(sy/draws)**2));close(r,.752,.03);
});

test('pair correlations come from the measured table and unlisted pairs are independent',()=>{
 const pool=S.assignRoles([{id:'q',team:'AAA',opponent:'BBB',position:'QB',projection:20},{id:'w1',team:'AAA',opponent:'BBB',position:'WR',projection:14},{id:'w2',team:'AAA',opponent:'BBB',position:'WR',projection:10},
  {id:'t',team:'AAA',opponent:'BBB',position:'TE',projection:8},{id:'r',team:'AAA',opponent:'BBB',position:'RB',projection:12},{id:'oq',team:'BBB',opponent:'AAA',position:'QB',projection:19},{id:'ow',team:'BBB',opponent:'AAA',position:'WR',projection:15},
  {id:'x',team:'CCC',opponent:'DDD',position:'QB',projection:18}]);
 const by=Object.fromEntries(pool.map(p=>[p.id,p]));
 assert.deepEqual(['q','w1','w2','t','r','oq','ow'].map(id=>by[id].dfsRole),['QB','WR1','WR2','TE1','RB1','QB','WR1']);
 const c=GoingDfsCorrelations.cross_player;
 close(S.pairCorrelation(by.q,by.w1),c['QB~WR1'].r);close(S.pairCorrelation(by.w1,by.q),c['QB~WR1'].r);
 assert.ok(S.pairCorrelation(by.q,by.w1)>.25);
 assert.ok(Math.abs(S.pairCorrelation(by.q,by.ow))<.1,'quarterback and opposing WR1 are essentially uncorrelated in the data');
 assert.ok(S.pairCorrelation(by.q,by.oq)>0&&S.pairCorrelation(by.q,by.oq)<.25);
 assert.equal(S.pairCorrelation(by.q,by.x),0);
 assert.ok(Math.abs(S.pairCorrelation(by.w1,by.w2))<.1);
});

test('a QB stack has a wider total than the same players treated as independent, and moments agree with simulation',()=>{
 const pool=S.assignRoles([{id:'q',team:'AAA',opponent:'BBB',position:'QB',projection:20,models:qb},{id:'w1',team:'AAA',opponent:'BBB',position:'WR',projection:14,models:wr},
  {id:'w2',team:'AAA',opponent:'BBB',position:'WR',projection:10,models:wr},{id:'x',team:'CCC',opponent:'DDD',position:'WR',projection:14,models:wr}]);
 for(const p of pool){p.distribution=S.player(p.models,p.position,{id:p.id,draws:3000});}
 const stack=pool.filter(p=>['q','w1','w2'].includes(p.id)),nonStack=[pool[0],pool[1],pool[3]];
 const moments=S.lineupMoments(stack),plain=S.lineupMoments(stack,{correlations:{cross_player:{}}});
 assert.ok(moments.sd>plain.sd*1.08);close(moments.mean,plain.mean,1e-9);
 const sim=S.lineupDistribution(stack,{draws:6000,seed:7}),indep=S.lineupDistribution(stack,{draws:6000,seed:7,independent:true});
 close(sim.sd,moments.sd,moments.sd*.1);close(indep.sd,plain.sd,plain.sd*.1);
 assert.ok(sim.p95>indep.p95,'stacking raises the ceiling');
 const unrelated=S.lineupMoments(nonStack),unrelatedPlain=S.lineupMoments(nonStack,{correlations:{cross_player:{}}});
 assert.ok(unrelated.sd/unrelatedPlain.sd<moments.sd/plain.sd,'a stack gains more spread than a QB with an unrelated receiver');
 assert.ok(S.probabilityAtLeast(sim,sim.median)>.45&&S.probabilityAtLeast(sim,sim.median)<.55);
 assert.equal(S.lineupDistribution([{...pool[0],distribution:null}]),null);
});

test('Captain multiplier scales both mean and spread',()=>{
 const p={id:'w',team:'AAA',opponent:'BBB',position:'WR',projection:14,models:wr};S.assignRoles([p]);p.distribution=S.player(wr,'WR',{id:'w',draws:2000});
 const base=S.lineupMoments([{...p,multiplier:1}]),captain=S.lineupMoments([{...p,multiplier:1.5}]);close(captain.mean,1.5*base.mean,1e-9);close(captain.sd,1.5*base.sd,1e-9);
});

test('the measured build style prefers a quarterback stack over the same projections spread across teams, and attaches a simulated range',()=>{
 const D=require('../shared/football-dfs.js');
 const mk=(id,team,opponent,position,projection,models)=>({id,name:id,team,opponent,position,projection,salary:5000,game:'AAA @ BBB',kickoff:'2099-01-01T18:00:00Z',models});
 const pool=S.assignRoles([
  mk('qa','AAA','BBB','QB',20,qb),mk('qb','BBB','AAA','QB',20,qb),
  mk('ra1','AAA','BBB','RB',12,wr),mk('ra2','AAA','BBB','RB',11,wr),mk('rb1','BBB','AAA','RB',12,wr),mk('rb2','BBB','AAA','RB',11,wr),
  mk('wa1','AAA','BBB','WR',14,wr),mk('wa2','AAA','BBB','WR',13,wr),mk('wa3','AAA','BBB','WR',12,wr),mk('wb1','BBB','AAA','WR',14,wr),mk('wb2','BBB','AAA','WR',13,wr),mk('wb3','BBB','AAA','WR',12,wr),
  mk('ta','AAA','BBB','TE',9,wr),mk('tb','BBB','AAA','TE',9,wr)]);
 for(const p of pool){p.distribution=S.player(p.models,p.position,{id:p.id,draws:1500});p.sd=p.distribution.sd;delete p.models;}
 const result=D.optimize(pool,{mode:'measured',projectionOnly:true,count:3,minUnique:1,now:Date.parse('2026-01-01T00:00:00Z')});
 assert.ok(result.lineups.length>=1,result.reason);
 const best=result.lineups[0],qbs=best.players.filter(p=>p.position==='QB'),mates=best.players.filter(p=>p.team===qbs[0].team&&['WR','TE'].includes(p.position));
 assert.ok(mates.length>=2,'the best measured lineup stacks its quarterback with receivers');
 assert.ok(best.simulation&&best.simulation.p90>best.simulation.median&&best.simulation.floor<best.simulation.median);
 assert.ok(!('sorted' in JSON.parse(JSON.stringify(best.simulation))),'frozen lineups keep only summaries');
 const legacy=D.optimize(pool,{mode:'balanced',projectionOnly:true,count:1,minUnique:1,now:Date.parse('2026-01-01T00:00:00Z')});
 assert.ok(legacy.lineups[0].simulation,'every mode reports the simulated range');
});

test('Champion v2 is its own tracker cohort and injury scaling keeps its pooled spread and zero mass',async()=>{
 const {modelCohort}=await import('../shared/model-cohort.mjs');
 assert.equal(modelCohort({model_evidence:{seasonEvidence:{method:'prior-strength blend c=2 (champion-v2)'}}}),'champion-v2');
 assert.equal(modelCohort({model_evidence:{seasonEvidence:{method:'80% current / 20% historical policy; unvalidated accuracy improvement'}}}),'current-80-20');
});
