'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const P=require('../shared/football-picks.js'),html=fs.readFileSync(require.resolve('../index.html'),'utf8');
const source=html.slice(html.indexOf('function saveTonightPick(row){'),html.indexOf('function addGoingPick(button){'));
const now=Date.parse('2026-10-12T18:00:00Z');
const base={kind:'prop',sport:'nfl',home:'LA',away:'BUF',team:'BUF',profileId:'p',player:'Player',profileDate:'2026-10-04',kickoff:'2026-10-13T00:15:00Z',market:'rush_yds',side:'Over',line:55.5,projMean:75,projSd:20,prob:.6,push:0,n:12,odds:-110,dec:1+100/110,book:'Book',updatedAt:new Date(now-30000).toISOString()};
function setup(current=base,actionable=true){
 const saved=[],sandbox={Date:class extends Date{static now(){return now;}},GoingFootballPicks:P,GoingUI:{add:p=>saved.push(p)},goingPicksCandidates:()=>Array.isArray(current)?current:[current],bettingEligibility:()=>({decide:()=>({actionable})}),confidenceEvidenceOptions:()=>({now,season:2026,historyAt:new Date(now).toISOString(),currentRoleEvidence:{playerId:'p',team:'BUF',season:2026,games:4,latest:'2026-10-04',means:{rush_yds:75,carries:15}}}),BET:{context:{},injuryLearning:{}},opportunityIdentity:c=>P.contractKey(c),bestPlayLabel:c=>c.side+' '+c.line,MARKET_LABEL:{}};
 vm.createContext(sandbox);vm.runInContext(source,sandbox);return {save:sandbox.saveTonightPick,saved};
}
test('real Tonight save adapter rechecks exact current offer and writes the shared local shortlist',()=>{const s=setup();assert.equal(s.save({candidate:base}),true);assert.equal(s.saved.length,1);assert.equal(s.saved[0].book,'Book');assert.equal(s.saved[0].label,'Over 55.5');});
test('Tonight save adapter rejects quote expiry, changed price and changed availability at click time',()=>{for(const [c,active] of [[{...base,updatedAt:new Date(now-600000).toISOString()},true],[{...base,odds:-115,dec:1+100/115},true],[base,false],[{...base,injury:{blockRecommendation:true}},true]]){const s=setup(c,active);assert.equal(s.save({candidate:c.updatedAt!==base.updatedAt?c:base}),false);assert.equal(s.saved.length,0);}});

test('Tonight save cannot reuse an older duplicate when the same book has a newer changed quote',()=>{const s=setup([base,{...base,odds:-115,dec:1+100/115,updatedAt:new Date(now-10000).toISOString()}]);assert.equal(s.save({candidate:base}),false);assert.equal(s.saved.length,0);});
