'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('../shared/dfs-starter-confirmations.js'),A=require('../shared/dfs-availability.js');
const now=Date.parse('2026-10-11T15:00:00Z'),game={team:'CHI',opponent:'GB',kickoff:'2026-10-11T17:00:00Z',now};
test('exact game announcement replaces depth rank without inventing an OUT designation',()=>{
 const c=C.decide({...game,name:'Caleb Williams'}),b=C.decide({...game,name:'Tyson Bagent'});
 assert.equal(c.known,true);assert.equal(c.eligible,false);assert.equal(b.eligible,true);assert.match(c.reason,/not the announced starter/);assert.match(c.sourceURL,/chicagobears\.com/);
 const context=A.createContext({generated_at:'2026-10-11T14:00:00Z',players:[{name:'Caleb Williams',team:'CHI',position:'QB',roster_status:'ACT',injury_status:'Questionable',depth_chart_order:1},{name:'Tyson Bagent',team:'CHI',position:'QB',roster_status:'ACT',depth_chart_order:2}]},{},now);
 assert.equal(A.availability(context.byIdentity.get('CHI|calebwilliams')).state,'questionable');
 assert.equal(A.starterEligibility({...game,name:'Caleb Williams',position:'QB',context}).eligible,false);
 assert.equal(A.starterEligibility({...game,name:'Tyson Bagent',position:'QB',context}).eligible,true);
 context.byIdentity.get('CHI|tysonbagent').injury_status='OUT';assert.equal(A.starterEligibility({...game,name:'Tyson Bagent',position:'QB',context}).eligible,false);
});
test('game confirmation cannot bleed to another opponent, kickoff, season or team',()=>{
 for(const patch of [{opponent:'ATL'},{kickoff:'2026-10-18T17:00:00Z'},{kickoff:'2027-10-11T17:00:00Z'},{team:'GB',opponent:'CHI'}])assert.equal(C.decide({...game,name:'Caleb Williams',...patch}),null);
 assert.equal(C.decide({...game,name:'Tyson Bagent',kickoff:'2026-10-11T17:00:00.000Z'}).eligible,true);
});
test('missing bindings, invalid current time, future publication, conflicts and started game fail closed',()=>{
 for(const patch of [{kickoff:null},{opponent:null},{now:NaN},{now:Date.parse(game.kickoff)}]){const d=C.decide({...game,name:'Tyson Bagent',...patch});assert.equal(d.eligible,false);assert.equal(d.known,false);}
 const r=C.CONFIRMATIONS[0];
 for(const records of [[{...r,sourcePublishedAt:'2026-10-11T16:00:00Z'}],[{...r,sourcePublishedAt:'malformed'}],[{...r,sourceURL:'javascript:alert(1)'}],[r,{...r,starter:'Caleb Williams'}]])assert.equal(C.decide({...game,name:'Tyson Bagent',confirmations:records}).eligible,false);
 assert.equal(C.decide({...game,name:'Tyson Bagent',confirmations:null}).eligible,false);
 assert.equal(C.decide({team:'CHI',name:'Caleb Williams',now:Date.parse('2026-10-12T12:00:00Z')}),null,'past game never creates a season-wide block');
});

test('a failed browser starter-confirmation script cannot silently revert to depth-rank inference',()=>{
 const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),sandbox={GoingFootballInjuries:require('../shared/football-injuries.js')};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../shared/dfs-availability.js'),'utf8'),sandbox);
 const result=sandbox.GoingDfsAvailability.starterEligibility({name:'Fixture QB',team:'BUF',position:'QB',context:{fresh:true}});
 assert.equal(result.eligible,false);assert.equal(result.known,false);assert.match(result.reason,/adapter is unavailable/);
});
