// QA B regression pins. Each test here FAILS today and documents a confirmed defect (see QA B report).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const I=require('../shared/going-intel.js');
const Field=require('../shared/dfs-classic-field.js');

test('legRelations: spread legs on both sides store the HOME line; only a leg that backs a clear favourite implies its game script',()=>{
 const g={event:'e',home:'NO',away:'MIN',kind:'prop',dec:1.9};
 const rb=team=>({...g,player:'RB One',profileId:'r1',team,market:'rush_yds',side:'Over',line:60.5});
 // NO is a 3-point home favourite: both legs carry line -3.
 const noMinus3={event:'e',home:'NO',away:'MIN',kind:'game',market:'spread',side:'Home',line:-3,dec:1.9},minPlus3={...noMinus3,side:'Away'};
 assert.equal(I.legRelations([noMinus3,rb('NO')])[0]?.kind,'complement','backing the favourite NO supports the NO runner');
 assert.equal(I.legRelations([noMinus3,rb('MIN')])[0]?.kind,'conflict','NO covering works against the MIN runner');
 assert.equal(I.legRelations([minPlus3,rb('MIN')]).length,0,'MIN +3 backs the underdog: it says nothing clean about the MIN runner');
 // away favourite: home line +3, away leg backs the favourite
 const minMinus3={event:'e',home:'NO',away:'MIN',kind:'game',market:'spread',side:'Away',line:3,dec:1.9};
 assert.equal(I.legRelations([minMinus3,rb('MIN')])[0]?.kind,'complement');
});

test('classic ownership file with the right schema but missing structure must be rejected at load, not crash buildPool later',()=>{
 for(const bad of [{schema:Field.SCHEMA,models:{salary_only:{}},slot_totals:{}},{schema:Field.SCHEMA,models:{salary_only:{QB:{features:null,beta:null}}},slot_totals:{QB:1},positions:['QB']}]){
  Field.clear();
  const r=Field.load(bad);
  if(r.ok)assert.doesNotThrow(()=>Field.annotate([{position:'QB',salary:6000}]),'annotate threw after load() said ok');
 }
 Field.clear();
});

test('scoringRole tolerates an unknown tier without throwing',()=>{
 assert.doesNotThrow(()=>I.scoringRole({tier:'UNKNOWN',confidence:'ok',xtd_pg_l12:1,xtd_share_l6:.3,n:12},'WR','atd'));
});
