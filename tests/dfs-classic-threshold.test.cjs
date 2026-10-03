const {test}=require('node:test');
const assert=require('node:assert/strict');
const threshold=require('../shared/dfs-threshold.js'); // Registers the explicit evaluator before optimizer load.
const dfs=require('../shared/dfs-classic.js');
const NOW='2026-10-03T17:00:00Z';
// SYNTHETIC salary/player/evidence fixtures only. These are not real DK recommendations.
function fixture(){
 const rows=[
  ['QB','BUF',7,30,6500],['QB','KC',4,20,6500],['QB','MIA',5,31,6500],
  ['RB','DEN',0,10,4000],['RB','DEN',0,10,4000],['RB','DEN',0,10,4000],
  ['WR','DEN',0,10,4000],['WR','DEN',0,10,4000],['WR','DEN',0,10,4000],
  ['TE','DEN',0,10,4000],['DST','BUF',999,7,2500]
 ];
 const pool=rows.map(([position,team,tdMean,projection,salary],i)=>{
  const game=['BUF','MIA'].includes(team)?'BUF@MIA':'KC@DEN',teams=game.split('@');
  return {id:String(i+1),name:`Synthetic Threshold Fixture ${i+1}`,athleteId:`synthetic-${i+1}`,position,team,opponent:teams.find(t=>t!==team),salary,projection,tdMean,matched:true,unavailable:false,sourceSalary:'draftkings-csv',gameId:game+'|2026-10-04T17:00:00.000Z',kickoff:'2026-10-04T17:00:00.000Z'};
 });
 const tdScenario={version:'team-budget-v1',teams:{
  BUF:{counts:[7],denominator:7,n:1,allVerifiedPlayerMean:7,provenance:{source:'Synthetic seven-TD budget'}},
  KC:{counts:[0,8],denominator:4,n:2,allVerifiedPlayerMean:4,provenance:{source:'Synthetic variable eight-TD budget'}},
  MIA:{counts:[0,5,8],denominator:5,n:3,allVerifiedPlayerMean:5,provenance:{source:'Synthetic five-TD mean allocation'}},
  DEN:{counts:[0,0],denominator:1,n:2,allVerifiedPlayerMean:0,provenance:{source:'Synthetic zero-TD budget'}}
 }};
 return {pool,tdScenario,options:{mode:'throne',now:NOW,tdScenario,beamWidth:400}};
}
function verify(result,pool,options){assert.equal(result.lineup.length,9);assert.equal(dfs.validateLineup(result.lineup,pool,options).valid,true);assert.ok(result.salaryUsed<=50000);assert.equal(new Set(result.lineup.map(p=>p.id)).size,9);assert.ok(new Set(result.lineup.map(p=>p.gameId)).size>=2);if(options.mode==='best'){assert.equal(result.tdThreshold,null);return;}assert.equal(result.tdThreshold.valid,true);assert.deepEqual(result.tdThreshold.bins,threshold.evaluate(result.lineup,options.tdScenario).bins);}
test('throne selects the whole-lineup eight-plus scenario instead of the larger TD mean',()=>{
 const {pool,options}=fixture(),result=dfs.optimize(pool,options);verify(result,pool,options);assert.equal(result.lineup[0].id,'2');assert.equal(result.tdThreshold.tailMass,.5);assert.equal(result.tdMean,4);
 const higherMean=dfs.optimize(pool,{...options,lockedSlots:{0:'1'}});verify(higherMean,pool,{...options,lockedSlots:{0:'1'}});assert.equal(higherMean.tdMean,7);assert.equal(higherMean.tdThreshold.tailMass,0);assert.ok(result.tdThreshold.tailMass>higherMean.tdThreshold.tailMass);
});
test('BEST mode retains its separate DFS projection objective and ignores the Throne scenario',()=>{
 const {pool,options}=fixture(),result=dfs.optimize(pool,{...options,mode:'best'});verify(result,pool,{...options,mode:'best'});assert.equal(result.lineup[0].id,'3');assert.equal(result.lineup[0].projection,31);assert.equal(result.tdThreshold,null);
});
test('threshold scenario ignores QB passing and DST fake TDs throughout optimizer ranking',()=>{
 const {pool,options}=fixture(),first=dfs.optimize(pool,options),altered=pool.map(p=>({...p,pass_tds:999,passingTdMean:999,tdMean:p.position==='DST'?1_000_000:p.tdMean})),second=dfs.optimize(altered,options);verify(second,altered,options);assert.deepEqual(first.lineup.map(p=>p.id),second.lineup.map(p=>p.id));assert.deepEqual(first.tdThreshold.bins,second.tdThreshold.bins);assert.equal(second.tdMean,4);
});
test('locks, exclusions and exact slots survive threshold optimization',()=>{
 const {pool,options}=fixture(),locked={...options,lockedSlots:{2:'6'},excludedIds:['1']},result=dfs.optimize(pool,locked);verify(result,pool,locked);assert.equal(result.lineup[2].id,'6');assert.equal(result.lineup[0].id,'2');assert.ok(result.lineup.every(p=>p.id!=='1'));
 const forced={...options,excludedIds:['2','3']},fallback=dfs.optimize(pool,forced);verify(fallback,pool,forced);assert.equal(fallback.lineup[0].id,'1');assert.equal(fallback.tdThreshold.tailMass,0);
});
test('the highest threshold scenario cannot override salary or two-game eligibility',()=>{
 const {pool,options}=fixture(),tooExpensive=pool.map(p=>p.id==='2'||p.id==='3'?{...p,salary:45000}:p),affordable=dfs.optimize(tooExpensive,options);verify(affordable,tooExpensive,options);assert.equal(affordable.lineup[0].id,'1');
 const oneGameAlternative=pool.filter(p=>p.id!=='3').map(p=>p.position==='DST'?{...p,team:'KC',opponent:'DEN',gameId:'KC@DEN|2026-10-04T17:00:00.000Z'}:p),diverse=dfs.optimize(oneGameAlternative,options);verify(diverse,oneGameAlternative,options);assert.equal(diverse.lineup[0].id,'1');
});
test('smart swaps rank whole-lineup threshold deltas and preserve the other eight spots',()=>{
 const {pool,options}=fixture(),base=dfs.optimize(pool,{...options,lockedSlots:{0:'1'}}).lineup,result=dfs.alternatives(base,0,pool,options);assert.equal(result.errors.length,0);assert.equal(result.alternatives.length,2);assert.equal(result.alternatives[0].player.id,'2');assert.equal(result.alternatives[0].tdThresholdDelta,.5);assert.equal(result.alternatives[0].tdThreshold.tailMass,.5);assert.ok(Math.abs(result.alternatives[1].tdThresholdDelta-1/3)<1e-12);assert.ok(result.alternatives[0].tdMeanDelta<result.alternatives[1].tdMeanDelta);
 for(const alternative of result.alternatives){assert.equal(dfs.validateLineup(alternative.lineup,pool,options).valid,true);base.forEach((p,i)=>{if(i!==0)assert.equal(alternative.lineup[i].id,p.id);});assert.deepEqual(alternative.tdThreshold.bins,threshold.evaluate(alternative.lineup,options.tdScenario).bins);assert.equal(alternative.salaryRemaining,50000-alternative.lineup.reduce((sum,p)=>sum+p.salary,0));}
});
test('malformed or missing-team scenarios fail closed without reverting to the mean objective',()=>{
 const {pool,options}=fixture(),bad=[{},null,{version:'other',teams:{}},{...options.tdScenario,teams:{BUF:options.tdScenario.teams.BUF}},{...options.tdScenario,teams:{...options.tdScenario.teams,KC:{counts:[0,8],denominator:1}}}];
 for(const tdScenario of bad){const result=dfs.optimize(pool,{...options,tdScenario});assert.equal(result.lineup.length,0);assert.ok(result.reason||result.errors?.length);}
 const base=dfs.optimize(pool,{...options,lockedSlots:{0:'1'}}).lineup,swap=dfs.alternatives(base,0,pool,{...options,tdScenario:{version:'team-budget-v1',teams:{}}});assert.equal(swap.alternatives.length,0);assert.ok(swap.errors?.length);
});
test('repeated threshold runs remain deterministic',()=>{
 const {pool,options}=fixture(),a=dfs.optimize(pool,options),b=dfs.optimize(pool.slice().reverse(),options);verify(a,pool,options);verify(b,pool,options);assert.deepEqual(a.lineup.map(p=>p.id),b.lineup.map(p=>p.id));assert.deepEqual(a.tdThreshold.bins,b.tdThreshold.bins);
});
