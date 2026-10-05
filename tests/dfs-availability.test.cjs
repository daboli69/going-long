'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const availability=require('../shared/dfs-availability.js');
const {buildPool}=require('../shared/dfs-evidence.js');
const dfs=require('../shared/football-dfs.js');

const generatedAt='2026-10-05T12:00:00Z',now=Date.parse('2026-10-05T18:00:00Z');
const profile={id:'dfs-rb',name:'Roster Status Back',team:'BUF',position:'RB',last_game:'2026-09-28',games:[]};
const current={player_id:profile.id,team:'BUF',season:2026,games:3,last_game:'2026-09-28',targets:6,rush_attempts:20,target_share:.2,rush_share:.7};
const modelStats={rush_yds:80,rush_tds:1,rec_yds:20,rec_tds:.2,receptions:3};
function injuryContext(status,{reportStatus=null,practice=null}={}){
 return availability.createContext({generated_at:generatedAt,players:[{name:profile.name,team:'BUF',position:'RB',roster_status:'ACT',status:'ACT'}]},{},now,{
  current_players:{'BUF|rosterstatusback':{name:profile.name,team:'BUF',position:'RB',roster_status:status}},
  current_reports:reportStatus||practice?{'BUF|rosterstatusback':{name:profile.name,team:'BUF',position:'RB',report_status:reportStatus,practice_status:practice,primary_injury:practice?'Ankle':null}}:{},
 });
}
function dfsPool(context){
 return buildPool([{id:'salary-id',name:profile.name,team:'BUF',opponent:'MIA',position:'RB',salary:5000,kickoff:'2026-10-06T17:00:00Z'}],{
  profiles:{[profile.id]:profile},context:{season:2026,generated_at:generatedAt,scopes:{2026:{players:{[profile.id]:current}}}},injuryContext:context,generatedAt,now,injuries:availability,
  makeModel:(p,key)=>({projMean:modelStats[key],model:{status:'ready',mean:modelStats[key]}}),bonusProbability:()=>0,points:dfs.projectedPoints,
 });
}

test('DFS context gives exact evidence roster status precedence over all-ACT base rows',()=>{
 for(const status of ['INA','RES','DEV','CUT','RET','EXE']){
  const context=injuryContext(status),roster=context.byIdentity.get('BUF|rosterstatusback');
  assert.equal(roster.status,status);assert.equal(roster.roster_status,status);assert.equal(availability.availability(roster).state,'out');assert.equal(dfsPool(context)[0].unavailable,true);
 }
 for(const status of ['ACT','ACTIVE']){
  const context=injuryContext(status);assert.equal(availability.availability(context.byIdentity.get('BUF|rosterstatusback')).state,'available');
  assert.equal(dfsPool(context)[0].unavailable,false);
 }
});

test('unknown roster codes stay unknown; known injury and practice evidence still applies',()=>{
 const unknown=injuryContext('NEW-CODE');assert.equal(availability.availability(unknown.byIdentity.get('BUF|rosterstatusback')).state,'unknown');
 const questionable=injuryContext('NEW-CODE',{reportStatus:'Questionable'});assert.equal(availability.availability(questionable.byIdentity.get('BUF|rosterstatusback')).state,'questionable');
 const dnp=injuryContext('NEW-CODE',{practice:'Did Not Participate'});assert.equal(availability.availability(dnp.byIdentity.get('BUF|rosterstatusback')).state,'practice_dnp');
});

test('DFS QB starter requires a verified current role and skips explicit nonactive quarterbacks',()=>{
 const make=(rows)=>availability.createContext({generated_at:generatedAt,players:rows.map(row=>({name:row.name,team:'BUF',pos:'QB',status:'ACT'}))},{},now,{
  current_players:Object.fromEntries(rows.map(row=>['BUF|'+availability.normalize(row.name),{name:row.name,team:'BUF',position:'QB',roster_status:row.status,role_order:row.order}]))
 });
 let context=make([{name:'QB One',order:1,status:'ACT'},{name:'QB Two',order:2,status:'ACT'}]);
 assert.equal(availability.starterEligibility({name:'QB One',team:'BUF',position:'QB',context}).eligible,true);
 context=make([{name:'QB One',order:1,status:'INA'},{name:'QB Two',order:2,status:'ACT'}]);
 assert.equal(availability.starterEligibility({name:'QB Two',team:'BUF',position:'QB',context}).eligible,true);
 context=make([{name:'Alphabetical Backup',order:null,status:'ACT'}]);
 const unknown=availability.starterEligibility({name:'Alphabetical Backup',team:'BUF',position:'QB',context});assert.equal(unknown.known,false);assert.equal(unknown.eligible,false);
 context=availability.createContext({generated_at:generatedAt,players:[{name:'Depth One',team:'BUF',position:'QB',roster_status:'ACT',depth_chart_order:1},{name:'Depth Two',team:'BUF',position:'QB',roster_status:'ACT',depth_chart_order:2}]},{},now,{current_players:{'BUF|depthone':{name:'Depth One',team:'BUF',position:'QB',roster_status:'ACT',role_order:null},'BUF|depthtwo':{name:'Depth Two',team:'BUF',position:'QB',roster_status:'ACT',role_order:null}}});
 assert.equal(availability.starterEligibility({name:'Depth One',team:'BUF',position:'QB',context}).eligible,true);
 context=availability.createContext({generated_at:generatedAt,players:[{name:'Depth One',team:'BUF',position:'QB',roster_status:'ACT',depth_chart_order:1},{name:'Depth Tie',team:'BUF',position:'QB',roster_status:'ACT',depth_chart_order:1}]},{},now,{});
 const ambiguous=availability.starterEligibility({name:'Depth One',team:'BUF',position:'QB',context});assert.equal(ambiguous.known,false);assert.equal(ambiguous.eligible,false);
});


test('salary-file medical abbreviations cannot hide an OUT and do not call Q confirmed out',()=>{assert.equal(availability.availability({injury_status:'O'}).block,true);assert.equal(availability.availability({injury_status:'D'}).block,true);assert.equal(availability.availability({injury_status:'Q'}).state,'questionable');assert.equal(availability.availability({injury_status:'Q'}).block,false);});
