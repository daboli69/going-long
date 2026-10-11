const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('../shared/dfs-current-season.js'),D=require('../shared/football-dfs.js'),E=require('../shared/dfs-evidence.js'),S=require('../shared/dfs-sim.js');
const now=Date.parse('2026-10-11T14:00:00Z'),kickoff='2026-10-11T17:00:00Z';
function profile(){return {id:'synthetic',name:'Synthetic Current Player',team:'BUF',position:'RB',last_game:'2026-10-04',games:[...Array.from({length:4},(_,i)=>({season:2026,week:i+1,date:['2026-09-13','2026-09-20','2026-09-27','2026-10-04'][i],attempts:0,pass_yds:0,pass_tds:0,rush_yds:40+i*20,rush_tds:i%2,rec_yds:10,receptions:2,rec_tds:0})),{season:2025,week:18,date:'2026-01-04',pass_yds:9999,pass_tds:99,rush_yds:9999,rush_tds:99,rec_yds:9999,receptions:99,rec_tds:99}]};}
test('current component means, bonuses, joint distribution and upside ignore every prior-year value',()=>{
 const p=profile(),options={now,kickoff};const first=C.model(p,'rush_yds',options);
 assert.equal(first.n,4);assert.equal(first.mean,70);assert.equal(first.season_evidence.historical_games,0);
 const distribution=C.distribution(p,{...options,points:D.projectedPoints});
 const stats=Object.fromEntries(C.KEYS.map(k=>[k,C.model(p,k,options).mean]));stats.rush_100_probability=C.bonusProbability({model:first},99.5);
 assert.ok(Math.abs(distribution.mean-D.projectedPoints(stats,'draftkings'))<1e-12);
 const upside=require('../shared/dfs-upside.js').observed(p,distribution.mean,{...options,points:D.projectedPoints});assert.equal(upside.n,4);assert.equal(upside.currentGames,4);
 p.games[p.games.length-1].rush_yds=1e9;
 assert.deepEqual(C.model(p,'rush_yds',options),first);assert.equal(C.distribution(p,{...options,points:D.projectedPoints}).mean,distribution.mean);
});
test('prior-only and one-game players never receive a historical projection fallback',()=>{
 const p=profile();p.games=p.games.filter(g=>g.season===2025);assert.equal(C.model(p,'rush_yds',{now}).status,'unavailable');
 p.games=[profile().games[0]];assert.equal(C.model(p,'rush_yds',{now}).status,'unavailable');assert.equal(C.distribution(p,{now,points:D.projectedPoints}),null);
});
test('duplicate weeks, invalid dates, future/current-day games and partial-QB games cannot inflate samples',()=>{
 const p=profile();p.games.push({...p.games[0]});assert.equal(C.model(p,'rush_yds',{now}).status,'unavailable');assert.equal(require('../shared/dfs-upside.js').observed(p,10,{now,points:D.projectedPoints}),null);
 for(const date of ['2026-09-31','2026-10-11','2026-10-12']){const q=profile();q.games.push({...q.games[0],week:5,date,rush_yds:999});assert.equal(C.model(q,'rush_yds',{now}).n,4);}
 const q=profile();q.position='QB';q.games.forEach(g=>g.attempts=20);q.games[0].attempts=1;assert.equal(C.model(q,'rush_yds',{now}).n,3);assert.equal(require('../shared/dfs-upside.js').observed(q,10,{now,points:D.projectedPoints}).n,3);
});
test('January uses the ongoing NFL season while kickoff enforces a point-in-time cutoff',()=>{
 assert.equal(C.model(profile(),'rush_yds',{now:Date.parse('2027-01-02')}).season,2026);
 assert.equal(C.model(profile(),'rush_yds',{now,kickoff:'2026-09-28T00:00:00Z'}).n,3);
});
function options(p=profile()){
 return {profiles:{[p.id]:p},generatedAt:new Date(now-60000).toISOString(),now,context:{season:2026,generated_at:new Date(now-60000).toISOString(),scopes:{2026:{players:{[p.id]:{player_id:p.id,team:p.team,season:2026,targets:8,rush_attempts:30,games:4,last_game:p.last_game}}}}},injuryContext:{fresh:true,byIdentity:new Map()},injuries:{normalize:x=>x,availability:()=>({block:false}),starterEligibility:()=>({known:true,eligible:true})},makeModel:(p,key,s)=>{const model=C.model(p,key,{now,kickoff:s.kickoff});return {model,projMean:model.mean};},bonusProbability:C.bonusProbability,points:D.projectedPoints};
}
const salary={id:'test',name:'Synthetic Current Player',team:'BUF',opponent:'MIA',position:'RB',salary:5000,kickoff};
test('default actual evidence pool requires current-source models; no archived adjustments or role trend leak',()=>{
 const p=profile();p.role_trend={old:'prior-year'};const [row]=E.buildPool([salary],options(p));assert.equal(row.unavailable,false);assert.equal(row.projectionSource,C.SOURCE);assert.equal(row.projectionSeason,2026);assert.equal(row.projectionAdjustment,0);assert.equal(row.roleTrend,null);assert.equal(row.distribution.n,4);assert.equal(row.sd,row.distribution.sd);assert.equal(row.upside.n,4);
 assert.equal(E.buildPool([salary],{...options(),makeModel:()=>({projMean:99,model:{status:'ready',mean:99}})})[0].unavailable,true);
 assert.equal(E.buildPool([{...salary,position:'DST',avgPointsPerGame:99}],options())[0].projection,null);
});
test('current-season lineup variance cannot reuse archived offensive or DST covariance',()=>{
 const a={position:'QB',dfsRole:'QB',team:'BUF',opponent:'MIA',projection:10,projectionSource:C.SOURCE,distribution:{mean:10,sd:3}},b={position:'WR',dfsRole:'WR1',team:'BUF',opponent:'MIA',projection:10,projectionSource:C.SOURCE,distribution:{mean:10,sd:4}};
 assert.equal(S.pairCorrelation(a,b,{cross_player:{'QB~WR1':{r:.99}}}),0);assert.equal(S.lineupMoments([a,b]).sd,5);
});

test('stale current-season context blocks QB and skill-position projection equally',()=>{const o=options();o.context.generated_at='2026-10-01T00:00:00Z';assert.equal(E.buildPool([salary],o)[0].unavailable,true);});

test('empirical distribution spread matches resampling its observed support',()=>{const p=profile();p.games=p.games.slice(0,2);p.games.forEach((g,i)=>{for(const k of C.KEYS)g[k]=0;g.rush_yds=i*80;});const d=C.distribution(p,{now,points:D.projectedPoints,site:'fanduel'});assert.equal(d.mean,4);assert.equal(d.sd,4);assert.deepEqual(Array.from(d.sorted),[0,8]);});

test('current production evidence rejects unknown, started and conflicting imported games',()=>{for(const change of [{kickoff:null},{kickoff:'bad'},{kickoff:'2026-10-10T17:00:00Z'},{opponent:'BUF'},{opponent:'XYZ'}])assert.equal(E.buildPool([{...salary,...change}],options())[0].unavailable,true);});
