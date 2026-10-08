const {test}=require('node:test');
const assert=require('node:assert/strict');
require('../shared/dfs-correlations.js');
const S=require('../shared/dfs-sim.js');
const F=require('../shared/dfs-field.js');
const D=require('../shared/football-dfs.js');
const close=(a,b,tol=1e-9)=>assert.ok(Math.abs(a-b)<=tol,`${a} != ${b}`);

// A toy model with the private file's schema. It contains no licensed data.
const bins=30,ramp=Array.from({length:bins},(_,i)=>Math.max(.2,30*Math.exp(-i/5)));
const toy={schema:'going-private-showdown-models-v1',ownership:{CPT:{bins,table:{QB:ramp,SKILL:ramp,DK:ramp.map(x=>x/3)},total:100},FLEX:{bins,table:{QB:ramp,SKILL:ramp,DK:ramp.map(x=>x/3)},total:500}},
 duplication:{features:['cpt_own','sum_flex_own','min_flex_own','log_prod_own','unused','cpt_salary_rank_pct','max_team','n_stars','cpt_pos_QB','log_entries'],mean:[5,40,2,-18,800,.3,4,1.5,.2,10],sd:[5,20,2,4,900,.25,1,1,.4,1],intercept:1.4,coef:[.3,.2,.1,.15,-.1,-.1,.05,.1,.05,.2],resid_sd:1}};

function pool(){
 const teams=['AAA','BBB'],positions=['QB','RB','WR','WR','WR','TE','DST'],rows=[];let id=1;
 for(const team of teams)positions.forEach((position,i)=>{const base=12000-i*1500-(team==='BBB'?400:0);for(const role of ['CPT','FLEX']){rows.push({id:id,name:`${team}${position}${i}`,team,opponent:team==='AAA'?'BBB':'AAA',position,showdownRole:role,salary:role==='CPT'?base*1.5:base,projection:(role==='CPT'?1.5:1)*(20-i*2),sd:6,game:'AAA @ BBB',kickoff:'2099-01-01T00:00:00Z'});}id++;});
 return rows;
}

test('loading validates the schema and nothing is shown without a model',()=>{
 F.clear();assert.equal(F.ready(),false);assert.equal(F.duplication([]),null);
 assert.equal(F.load('not json').ok,false);assert.equal(F.load({schema:'other'}).ok,false);
 assert.equal(F.load(toy).ok,true);assert.equal(F.ready(),true);
});

test('ownership is normalised to 100% Captain and 500% FLEX and falls with salary rank',()=>{
 F.load(toy);const p=F.annotate(pool());
 for(const [role,total] of [['CPT',100],['FLEX',500]]){const rows=p.filter(x=>x.showdownRole===role);close(rows.reduce((s,x)=>s+x.ownership,0),total,1e-6);assert.ok(rows.every(x=>x.ownership>=0&&x.ownership<=100));}
 const flex=p.filter(x=>x.showdownRole==='FLEX').sort((a,b)=>b.salary-a.salary);
 assert.ok(flex[0].ownership>=flex[flex.length-1].ownership);
 assert.ok(flex.find(x=>x.position==='DST'&&x.salary===Math.min(...flex.filter(y=>y.position==='DST').map(y=>y.salary))).ownership<flex[0].ownership);
});

test('duplication follows the stored linear model exactly and a more popular lineup duplicates more',()=>{
 F.load(toy);const p=F.annotate(pool()),by=(role,name)=>p.find(x=>x.showdownRole===role&&x.name===name);
 const chalk=[{...by('CPT','AAAQB0'),slot:'CPT',multiplier:1.5},...['AAAWR2','AAARB1','BBBQB0','BBBWR2','AAATE5'].map(n=>({...by('FLEX',n),slot:'FLEX',multiplier:1}))];
 const odd=[{...by('CPT','BBBDST6'),slot:'CPT',multiplier:1.5},...['AAADST6','AAATE5','BBBTE5','BBBWR4','AAAWR4'].map(n=>({...by('FLEX',n),slot:'FLEX',multiplier:1}))];
 const f=F.lineupFeatures(chalk,30000),spec=toy.duplication,x=spec.features.map(k=>f[k]);
 const expected=spec.intercept+x.reduce((s,v,i)=>s+(v-spec.mean[i])/spec.sd[i]*spec.coef[i],0);
 close(F.duplication(chalk,30000).logDup,expected);close(F.duplication(chalk,30000).expectedCopies,Math.exp(expected+.5));
 assert.ok(F.duplication(chalk,30000).expectedCopies>F.duplication(odd,30000).expectedCopies);
 assert.ok(['low','moderate','high'].includes(F.duplication(odd,30000).band));
 assert.equal(F.duplication(chalk.slice(0,4),30000),null);
});

test('Showdown build styles use the field model, report ownership and duplication, and fall back cleanly without it',()=>{
 const make=()=>{const p=S.assignRoles(pool());for(const x of p){x.distribution=S.player({receptions:{family:'poisson',lambda:x.projection/4,status:'ready'},rec_yds:{family:'lognormal',mu_log:Math.log(Math.max(x.projection*3,5)),sigma_log:.6,positive_weight:.9,nonpositive:[0],nonpositive_weights:[.1],status:'ready'}},x.position==='QB'?'WR':x.position==='DST'?'WR':x.position,{id:String(x.id)+x.showdownRole,draws:300});x.sd=x.distribution?.sd??6;}return p;};
 F.load(toy);let p=F.annotate(make());
 const opts={contest:'showdown',projectionOnly:false,count:3,minUnique:1,now:Date.parse('2026-01-01T00:00:00Z'),entries:30000};
 const best=D.optimize(p,{...opts,mode:'best'});assert.ok(best.lineups.length>=1,best.reason);
 const top=best.lineups[0];assert.ok(top.ownership&&top.duplication&&top.simulation);assert.equal(top.players[0].slot,'CPT');close(top.ownership.flexTotal,top.players.slice(1).reduce((s,x)=>s+x.ownership,0),1e-9);
 const lowdup=D.optimize(p,{...opts,mode:'lowdup'}),balanced=D.optimize(p,{...opts,mode:'balanced'});
 assert.ok(lowdup.lineups[0].duplication.expectedCopies<=balanced.lineups[0].duplication.expectedCopies+1e-9,'the lower-duplication style does not pick a more duplicated lineup than the projection-only style');
 F.clear();p=make();const plain=D.optimize(p,{...opts,mode:'best'});assert.ok(plain.lineups.length>=1);assert.equal(plain.lineups[0].duplication,undefined);assert.equal(plain.lineups[0].ownership,undefined);
});
