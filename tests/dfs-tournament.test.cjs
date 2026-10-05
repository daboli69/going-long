const {test}=require('node:test');
const assert=require('node:assert/strict');
const T=require('../shared/dfs-tournament.js');

const upside=(value,n=10,currentGames=3,asOf='2026-10-04T16:00:00Z')=>({value,source:T.UPSIDE_SOURCE,n,currentGames,asOf});

test('classic review describes stack, opponent bring-back, DST conflict and unknown ownership',()=>{
 const lineup=[
  {id:'qb',position:'QB',team:'BUF',opponent:'MIA',gameId:'BUF@MIA'},
  {id:'wr',position:'WR',team:'BUF',opponent:'MIA',gameId:'BUF@MIA'},
  {id:'te',position:'TE',team:'BUF',opponent:'MIA',gameId:'BUF@MIA'},
  {id:'back',position:'WR',team:'MIA',opponent:'BUF',gameId:'BUF@MIA'},
  {id:'dst',position:'DST',team:'BUF',opponent:'MIA',gameId:'BUF@MIA'},
  {id:'opp',position:'RB',team:'MIA',opponent:'BUF',gameId:'BUF@MIA'}
 ];
 const result=T.evaluate(lineup,{contest:'classic'});
 assert.equal(result.format.type,'multi-game');
 assert.deepEqual(result.classic.sameTeamPassCatchers,['wr','te']);
 assert.deepEqual(result.classic.bringBacks,['back','opp']);
 assert.deepEqual(result.classic.dstOpposingOffenseConflicts,['back','opp']);
 assert.equal(result.ownership.status,'unknown');
 assert.equal(result.salary.interpretation,'context-only; no uniqueness inference');
 assert.equal(result.objective.value,null);
 assert.deepEqual(result.constraints.hardCorrelationRules,[]);
 assert.equal(result.showdown,null);
});

test('showdown describes captain pairings and team split without restrictions',()=>{
 const lineup=[
  {id:'cpt',position:'WR',team:'KC',slot:'CPT',salary:12000,projection:20},
  {id:'qb',position:'QB',team:'KC',slot:'FLEX'},
  {id:'opp',position:'WR',team:'BUF',slot:'FLEX'},
  {id:'dst',position:'DST',team:'BUF',slot:'FLEX'}
 ];
 const result=T.evaluate(lineup,{contest:'showdown'});
 assert.equal(result.format.type,'single-game');
 assert.equal(result.showdown.captain,'cpt');
 assert.equal(result.showdown.captainPairings.find(p=>p.playerId==='qb').interpretation,'positive-pass-correlation candidate');
 assert.equal(result.showdown.captainPairings.find(p=>p.playerId==='opp').interpretation,'unmodeled');
 assert.deepEqual(result.showdown.teamComposition,{KC:2,BUF:2});
 assert.deepEqual(result.constraints.hardCorrelationRules,[]);
 assert.deepEqual(result.constraints.hardOwnershipRules,[]);
});

test('objective only uses correctly sourced, sufficiently sampled upside; malformed evidence falls back',()=>{
 const supported={projection:15,upside:upside(23,8,3)};
 assert.equal(T.objective(supported),23);
 assert.equal(T.objective(supported,{multiplier:1.5}),34.5);
 assert.equal(T.objective(supported,1.5),34.5);
 assert.equal(T.playerObjective(supported).ceilingStatus,'provided-unvalidated');
 for(const malformed of [
  {value:99,source:'other',n:20,currentGames:3,asOf:'2026-10-04'},
  upside(99,7,3),upside(99,8,9),upside(99,8,3,'not-a-date')
 ]){
  assert.equal(T.objective({projection:15,upside:malformed}),15);
  assert.equal(T.playerObjective({projection:15,upside:malformed}).ceilingStatus,'unknown');
 }
 assert.equal(T.objective({projection:15,upside:{value:99}}),15);
 assert.equal(T.objective({}),null);
});

test('comparison uses supplied player upside with projection fallback and only descriptive exact-tie preference',()=>{
 const qb={id:'qb',position:'QB',team:'BUF',opponent:'MIA',projection:10,upside:upside(14)};
 const stack={id:'stack',position:'WR',team:'BUF',opponent:'MIA',projection:10};
 const plain={id:'plain',position:'WR',team:'NYJ',opponent:'NE',projection:10};
 const compared=T.compare([qb,plain],[qb,stack],{contest:'classic'});
 assert.equal(compared.ranked[0].lineup[1].id,'stack');
 assert.equal(compared.ranked[0].score,24);
 assert.equal(compared.ranked[0].upsideCovered,1);
 assert.match(compared.ranked[0].ceilingStatus,/unknown/);
 assert.equal(compared.jointCeiling,'not-estimated');
 assert.match(compared.tieBreak,/exact objective ties/);
});

test('showdown applies 1.5 fantasy multiplier at CPT even when imported salary is already CPT salary',()=>{
 const cpt={id:'cpt',position:'WR',team:'KC',slot:'CPT',salaryRole:'CPT',salary:15000,projection:20,upside:upside(24)};
 const flex={id:'flex',position:'QB',team:'KC',slot:'FLEX',salary:8000,projection:20,upside:upside(20)};
 const result=T.compare([cpt,flex],[{id:'plainCpt',position:'RB',team:'BUF',slot:'CPT',salaryRole:'CPT',salary:12000,projection:28,upside:upside(20)},flex],{contest:'showdown'});
 assert.equal(T.objective(cpt,{multiplier:1.5}),36);
 assert.equal(result.ranked[0].lineup[0].id,'cpt');
 assert.equal(result.ranked[0].score,56);
 assert.equal(T.evaluate([cpt,flex],{contest:'showdown'}).salary.salaryUsed,23000);
 assert.equal(T.evaluate([cpt,flex],{contest:'showdown'}).salary.salaryRemaining,27000);
 assert.equal(T.evaluate([cpt,flex],{contest:'showdown'}).objective.value,56);
});
