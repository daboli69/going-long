'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const defense=require('../shared/dfs-current-defense.js');
const now=Date.parse('2026-10-11T15:00:00Z'),salary={team:'BUF',opponent:'MIA',kickoff:'2026-10-11T17:00:00Z',avgPointsPerGame:999};
const dst=(changes={})=>({sacks:2,sacksSuffered:2,interceptions:1,interceptionsThrown:1,fumbleRecoveries:1,defensiveTDs:0,returnTDs:0,safeties:0,blockedKicks:0,conversionReturns:0,unclassifiedFumbleTDs:0,teamFinalScore:21,opponentFinalScore:14,opponentDefensiveTDs:0,opponentSafeties:0,opponentUnclassifiedFumbleTDs:0,pointsAllowed:14,...changes});
function fixture(){return {schemaVersion:1,season:2026,defenseStatus:'current-season-partial',generatedAt:'2026-10-11T14:00:00Z',retrievedAt:'2026-10-11T14:00:00Z',releaseUpdatedAt:'2026-10-11T09:00:00Z',sourceURL:'https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_2026.csv',sourceSha256:'a'.repeat(64),resultsSHA256:'b'.repeat(64),teams:{BUF:[{team:'BUF',opponent:'MIA',gameId:'2026_01_BUF_MIA',kickoff:'2026-09-13T17:00:00Z',dst:dst()}],MIA:[{team:'MIA',opponent:'BUF',gameId:'2026_01_BUF_MIA',kickoff:'2026-09-13T17:00:00Z',dst:dst({teamFinalScore:14,opponentFinalScore:21,pointsAllowed:21})}]}};}
test('DST computes documented scoring components and every points-allowed boundary',()=>{
 assert.deepEqual([0,1,6,7,13,14,20,21,27,28,34,35].map(defense.pointsAllowedScore),[10,7,7,4,4,1,1,0,0,-1,-1,-4]);
 assert.equal(defense.score(dst()),7);
 assert.equal(defense.score(dst({teamFinalScore:30,defensiveTDs:1,returnTDs:1,safeties:1,blockedKicks:1,conversionReturns:1})),25);
});
test('DST uses only actual current-season source rows and ignores salary averages',()=>{
 const x=defense.project(salary,fixture(),{now});assert.equal(x.status,'ready');assert.equal(x.n,1);assert.equal(x.season,2026);assert.equal(x.projection,7);assert.equal(x.distribution.p90,7);assert.equal(x.tdMean,0);assert.match(x.concerns.join(' '),/partial/);
});
test('DST empirical mean and quantiles use each unique current game once',()=>{
 const s=fixture();for(const own of ['BUF','MIA'])s.teams[own].push({...s.teams[own][0],gameId:'2026_02_BUF_MIA',kickoff:'2026-09-20T17:00:00Z',dst:{...s.teams[own][0].dst,sacks:6,sacksSuffered:6}});
 const x=defense.project(salary,s,{now});assert.equal(x.n,2);assert.equal(x.projection,9);assert.equal(x.distribution.median,9);assert.equal(x.distribution.p90,10.6);assert.equal(x.distribution.sd,2);
});
test('DST excludes unknown components instead of treating missing values as zero',()=>{
 for(const key of Object.keys(dst())){const s=fixture();delete s.teams.BUF[0].dst[key];assert.equal(defense.project(salary,s,{now}).status,'blocked',key);}
});
test('DST fails closed for prior seasons, duplicates, impossible scores and mismatched opponent receipts',()=>{
 for(const mutate of [s=>s.season=2025,s=>s.teams.BUF[0].gameId='2025_01_BUF_MIA',s=>s.teams.BUF.push(s.teams.BUF[0]),s=>s.teams.BUF[0].dst.pointsAllowed=0,s=>s.teams.BUF[0].dst.returnTDs=10,s=>delete s.teams.MIA,s=>s.teams.MIA.push(s.teams.MIA[0]),s=>s.teams.MIA[0].dst.teamFinalScore=15,s=>s.teams.BUF[0].dst.sacks=-1,s=>s.teams.BUF[0].dst.interceptions='1']){const s=fixture();mutate(s);assert.equal(defense.project(salary,s,{now}).status,'blocked');}
});
test('DST fails closed for missing/stale/future/malformed provenance and started games',()=>{
 for(const mutate of [s=>s.generatedAt='2026-10-12T00:00:00Z',s=>s.retrievedAt='2026-10-09T00:00:00Z',s=>s.releaseUpdatedAt='2026-10-01T00:00:00Z',s=>s.generatedAt='2026-10-11T14:00:00+99:00',s=>s.generatedAt='2026-02-31T14:00:00Z',s=>s.sourceURL='https://example.test',s=>delete s.resultsSHA256,s=>s.defenseStatus='missing-components',s=>s.teams.BUF[0].kickoff='2026-10-11T18:00:00Z']){const s=fixture();mutate(s);assert.equal(defense.project(salary,s,{now}).status,'blocked');}
 assert.equal(defense.project({...salary,kickoff:'2026-10-11T14:00:00Z'},fixture(),{now}).status,'blocked');
});
test('DST removes known opposing defensive scores, counts return TDs and discloses ambiguous recovery TDs',()=>{
 const s=fixture(),a=s.teams.BUF[0].dst,b=s.teams.MIA[0].dst;
 Object.assign(a,{opponentDefensiveTDs:1,opponentSafeties:1,pointsAllowed:6,opponentUnclassifiedFumbleTDs:1,unclassifiedFumbleTDs:1});
 Object.assign(b,{defensiveTDs:1,safeties:1,unclassifiedFumbleTDs:1,opponentUnclassifiedFumbleTDs:1});
 const x=defense.project(salary,s,{now});assert.equal(x.status,'ready');assert.equal(x.projection,13);assert.match(x.concerns.join(' '),/2 ambiguous TD observations/);
});
