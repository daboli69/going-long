const test=require('node:test'),assert=require('node:assert/strict');
const identity=require('../shared/football-opportunity.js');
const base={sport:'nfl',home:'BUF',away:'DET',kickoff:'2026-09-18T00:15:00Z',kind:'prop',profileId:'00-1',market:'rec_yds',side:'Over',line:62.5,rules:'player_must_participate'};
test('canonical football identity is stable across aliases and timestamp formats',()=>{
 const a=identity.describe(base),b=identity.describe({...base,market:'player_receiving_yards',kickoff:'2026-09-17T20:15:00-04:00'});
 assert.equal(a.id,b.id);assert.equal(a.market,'rec_yds');assert.equal(a.period,'full_game');
});
test('period, side, line, entity and rules remain distinct',()=>{
 const id=identity.identity(base);
 for(const change of [{market:'rec_yds_1h'},{side:'Under'},{line:63.5},{profileId:'00-2'},{rules:'action_required'}])assert.notEqual(identity.identity({...base,...change}),id);
 assert.equal(identity.describe({...base,market:'rec_yds_1h'}).period,'first_half');
});
test('event identity includes sport, teams and exact kickoff instant',()=>{
 const id=identity.eventId(base);
 assert.notEqual(identity.eventId({...base,sport:'ncaa'}),id);assert.notEqual(identity.eventId({...base,home:'KC'}),id);assert.notEqual(identity.eventId({...base,kickoff:'2026-09-18T00:16:00Z'}),id);
});
