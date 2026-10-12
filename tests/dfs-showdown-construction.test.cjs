'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const D=require('../shared/football-dfs.js'),F=require('../shared/dfs-field.js');
function pool(){return ['QB','WR','WR','TE','RB','K','DST'].flatMap((position,i)=>['A','B'].map(team=>({id:team+i,name:team+position+i,position,team,opponent:team==='A'?'B':'A',game:'A@B',salary:4000+i*100,projection:25-i*2+(team==='A'?1:0),sd:3,kickoff:'2099-01-01T00:00:00Z'})));}
function build(extra={},policy={}){return D.optimize(pool(),{contest:'showdown',captainId:'A1',count:3,beamWidth:3000,minUnique:1,showdownConstruction:{...D.SHOWDOWN_DEFAULTS,...policy},...extra});}
test('WR Captain builds pair the QB, limit additional receivers, cap K/DST and preserve legality',()=>{
 const r=build();assert.ok(r.lineups.length,r.reason);
 for(const l of r.lineups){const c=l.players[0],same=l.players.slice(1).filter(p=>p.team===c.team);assert.equal(c.id,'A1');assert.ok(same.some(p=>p.position==='QB'));assert.ok(same.filter(p=>['WR','TE'].includes(p.position)).length<=1);assert.ok(l.players.filter(p=>['K','DST'].includes(p.position)).length<=2);assert.ok(l.salary<=50000);assert.equal(new Set(l.players.map(p=>p.name)).size,6);assert.equal(Object.keys(l.teams).length,2);assert.match(l.constructionNotes.join(' '),/paired with/);}
});
test('QB Captain double stack has an explicit one-receiver rushing-QB override',()=>{
 for(const n of [1,2,3]){const r=build({captainId:'A0'}, {qbReceivers:n});assert.ok(r.lineups.length,r.reason);for(const l of r.lineups)assert.ok(l.players.slice(1).filter(p=>p.team==='A'&&['WR','TE'].includes(p.position)).length>=n);}
});
test('specialist Captain is opt-in, remains available in FLEX, and opposing defense is not banned',()=>{
 assert.equal(build({captainId:'A5'}).lineups.length,0);
 assert.ok(build({captainId:'A5'}, {allowSpecialCaptain:true}).lineups.length);
 const r=build({lockedIds:['B6']});assert.ok(r.lineups.length,r.reason);assert.ok(r.lineups.every(l=>l.players.filter(p=>p.team==='A').length<=3));assert.match(r.lineups[0].constructionNotes.join(' '),/conflicting paths/);
});
test('salary ceiling and Captain-relative team splits are enforced; bad values fail closed',()=>{
 for(const n of [2,3,4]){const r=build({}, {maxSalary:30000,captainTeamCount:n});assert.ok(r.lineups.length,r.reason);for(const l of r.lineups){assert.ok(l.salary<=30000);assert.equal(l.players.filter(p=>p.team==='A').length,n);}}
 for(const p of [{maxSalary:50001},{maxSalary:NaN},{qbReceivers:1.2},{maxKD:-1},{lowOwnership:0},{captainTeamCount:6},{wrWithQb:'false'}])assert.equal(build({},p).lineups.length,0);
});
test('conflicting locks and preferences never relax a rule or silently drop a lock',()=>{
 const r=build({lockedIds:['A1','A2','A3']});assert.equal(r.lineups.length,0);assert.match(r.reason,/preferences/);
 assert.ok(build({lockedIds:['A1','A2','A3']},{wrExtra:2}).lineups.length);
 const out=pool().map(p=>({...p,injury:p.id==='A0'?'Out':null}));
 const failed=D.optimize(out,{contest:'showdown',captainId:'A1',showdownConstruction:D.SHOWDOWN_DEFAULTS});assert.equal(failed.lineups.length,0);
});
test('Classic and disabled preferences retain the existing objective and constraints',()=>{
 const a=D.optimize(pool(),{contest:'showdown',captainId:'A5',count:1}),b=build({captainId:'A5',count:1},{enabled:false});assert.equal(a.lineups[0].projection,b.lineups[0].projection);assert.equal(b.lineups[0].construction,null);
 const aClassic=D.optimize(pool()),bClassic=D.optimize(pool(),{showdownConstruction:{maxSalary:1}});assert.equal(aClassic.reason,bClassic.reason);
});
test('low ownership cannot be fabricated without the Showdown file or complete estimates',()=>{
 F.clear();assert.match(build({}, {lowOwnership:10}).reason,/loaded Showdown model/);
 const model=require('./fixtures/dfs-field-parity.json').model;assert.ok(F.load(model).ok);
 const players=pool().map(p=>({...p,ownership:p.id==='B4'?4:30}));
 const r=D.optimize(players,{contest:'showdown',captainId:'A1',showdownConstruction:{lowOwnership:5},count:1});assert.ok(r.lineups.length,r.reason);assert.ok(r.lineups[0].players.some(p=>p.id==='B4'));
 players[0].ownership=null;assert.match(D.optimize(players,{contest:'showdown',showdownConstruction:{lowOwnership:5}}).reason,/complete role-specific/);F.clear();
});
test('small randomized search agrees with exhaustive eligible construction enumeration',()=>{
 let seed=7;const random=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
 for(let trial=0;trial<5;trial++){
  const p=pool().filter(x=>!['K','DST'].includes(x.position)&&x.id!=='B3').map(x=>({...x,salary:4000+Math.floor(random()*2000),projection:5+random()*25})),c=p.find(x=>x.id==='A1'),rest=p.filter(x=>x!==c),cap=32000;
  let best=-Infinity;
  function choose(start,rows){if(rows.length===5){const same=rows.filter(x=>x.team==='A');if(!same.some(x=>x.position==='QB')||same.filter(x=>['WR','TE'].includes(x.position)).length>1||same.length===5)return;const salary=c.salary*1.5+rows.reduce((s,x)=>s+x.salary,0);if(salary<=cap)best=Math.max(best,c.projection*1.5+rows.reduce((s,x)=>s+x.projection,0));return;}for(let i=start;i<rest.length;i++)choose(i+1,[...rows,rest[i]]);}
  choose(0,[]);const r=D.optimize(p,{contest:'showdown',captainId:c.id,count:1,beamWidth:20000,showdownConstruction:{maxSalary:cap}});assert.ok(r.lineups.length,r.reason);assert.ok(Math.abs(r.lineups[0].projection-best)<1e-9);
 }
});
test('ownership product is separate from sum and is not an exact lineup probability',()=>{
 const own=F.lineupOwnership(Array.from({length:6},(_,i)=>({slot:i?'FLEX':'CPT',ownership:10})));assert.equal(own.flexTotal,50);assert.ok(Math.abs(own.productIndex-1e-6)<1e-12);
});
test('malformed private models are rejected without replacing the working model',()=>{
 const good=require('./fixtures/dfs-field-parity.json').model;F.load(good);
 for(const mutate of [m=>delete m.ownership.CPT.table.QB,m=>m.duplication.features='invalid',m=>m.duplication.sd[0]=0,m=>m.duplication.coef.pop(),m=>m.ownership.FLEX.table.DK[0]=-1,m=>m.duplication.intercept=Infinity,m=>m.duplication.decile_unique_share[0]=2]){
  const bad=JSON.parse(JSON.stringify(good));mutate(bad);assert.equal(F.load(bad).ok,false);assert.equal(F.state.models,good);
 }F.clear();
});
