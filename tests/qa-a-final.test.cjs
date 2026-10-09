'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const P=require('../shared/football-picks.js');
const now=Date.parse('2026-10-05T17:00:00Z');
const c={kind:'prop',sport:'nfl',home:'NO',away:'ATL',team:'NO',player:'Player',profileId:'p',profileDate:'2026-09-27',kickoff:'2026-10-06T00:15:00Z',market:'rec_yds',side:'Under',line:55.5,projMean:60,projSd:20,prob:.4,push:0,n:12,book:'Book',odds:-110,dec:1+100/110,updatedAt:'2026-10-05T16:00:00Z'};
const o={now,season:2026,historyAt:'2026-10-05T16:00:00Z',currentRoleEvidence:{playerId:'p',team:'NO',season:2026,games:3,latest:'2026-09-27',means:{rec_yds:70,targets:10}}};
test('v3: high volume is not offered as a reason (WHY/supports) for a receiving Under',()=>{
 const e=P.assess(c,o);
 assert.ok(!e.badges.includes('VOLUME'));
 assert.ok(!e.supports.some(x=>/targets\/game/.test(x)),'Under card lists "10.0 targets/game" as support: '+JSON.stringify(e.supports));
 assert.ok(!/targets\/game/.test(e.why));
});
