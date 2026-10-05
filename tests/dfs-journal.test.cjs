'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const journal=require('../shared/dfs-journal.js');

const now=Date.parse('2026-10-05T19:00:00Z'),kickoff='2026-10-06T17:00:00Z',hash='a'.repeat(64);
const modelGeneratedAt='2026-10-05T18:00:00Z',injuryAt='2026-10-05T18:30:00Z';
function classicPlayers(){
 const rows=[
  ['QB','QB','BUF',6000,'BUF@MIA'],['RB','RB','BUF',7000,'BUF@MIA'],['RB','RB','MIA',6500,'BUF@MIA'],
  ['WR','WR','BUF',6500,'BUF@MIA'],['WR','WR','MIA',6000,'BUF@MIA'],['WR','WR','BUF',5500,'BUF@MIA'],
  ['TE','TE','MIA',4000,'BUF@MIA'],['FLEX','WR','MIA',5000,'BUF@MIA'],['DST','DST','NYJ',3000,'NYJ@BUF'],
 ];
 return rows.map(([slot,position,team,salary,game],i)=>({id:'p'+i,name:`Player ${i}`,team,position,slot,game,gameId:`${game}|2026-10-06`,kickoff,salary,projection:10+i,upside:null,evidence:[`evidence ${i}`],injury:null,concern:null,concerns:[],sourceSalary:'draftkings-csv'}));
}
function input(extra={}){return {players:classicPlayers(),contest:'classic',site:'draftkings',mode:'best',salaryHash:hash,modelGeneratedAt,injuryAt,now,...extra};}
function freeze(extra={}){return journal.freeze(input(extra));}
function showdownPlayers({pricedCaptain=true}={}){
 const rows=[['CPT','QB','BUF',pricedCaptain?12000:8000,pricedCaptain?'CPT':null],['FLEX','RB','BUF',6000,'FLEX'],['FLEX','WR','BUF',5000,'FLEX'],['FLEX','QB','MIA',7500,'FLEX'],['FLEX','RB','MIA',6000,'FLEX'],['FLEX','WR','MIA',8500,'FLEX']];
 return rows.map(([slot,position,team,salary,showdownRole],i)=>({id:'s'+i,name:`Showdown ${i}`,team,position,slot,game:'BUF@MIA',gameId:'BUF@MIA|2026-10-06T17:00:00Z',kickoff,salary,projection:20-i,upside:null,evidence:[],injury:null,concerns:[],showdownRole}));
}
function showdown(extra={}){return journal.freeze({...input({players:showdownPlayers(),contest:'showdown'}),...extra});}
function storage(){const data=new Map();return {data,getItem:key=>data.has(key)?data.get(key):null,setItem:(key,value)=>data.set(key,String(value))};}

test('freeze makes a pure, immutable exact Classic lineup receipt',()=>{
 const source=input(),before=JSON.stringify(source),result=journal.freeze(source);assert.equal(result.ok,true,result.error);
 assert.equal(JSON.stringify(source),before);assert.equal(Object.isFrozen(result.receipt),true);assert.equal(Object.isFrozen(result.receipt.players[0]),true);
 assert.equal(result.receipt.salaryUsed,49500);assert.equal(result.receipt.salaryCap,50000);assert.equal(result.receipt.players.length,9);
 assert.equal(result.receipt.modelGeneratedAt,modelGeneratedAt);assert.equal(result.receipt.injuryAt,injuryAt);assert.equal(result.receipt.players[0].slot,'QB');
 assert.equal(result.receipt.strategyVersion,'legacy-best');assert.equal(result.receipt.availabilityVersion,'dfs-availability-v1');
 assert.equal(result.receipt.players[0].sourceSalary,'draftkings-csv');assert.match(result.receipt.id,/^dfs-/);
 const roundTrip=JSON.parse(JSON.stringify(result.receipt));assert.equal(journal.append(storage(),roundTrip).ok,true);
});

test('freeze preserves sourced tournament upside evidence and optional opportunity context',()=>{
 const upside={value:24.5,source:'observed-partial-fantasy-residual-v1',n:12,currentGames:3,asOf:'2026-10-05T18:45:00Z',spread:7.25,historicalMean:17.25,historicalQ90:24.5,site:'draftkings',label:'historical proxy'};
 const players=classicPlayers().map((p,i)=>i===0?{...p,upside,stats:{targets:8},source:'local-profile',modelAgeHours:2.5}:p);
 const result=journal.freeze(input({players,mode:'tournament'}));assert.equal(result.ok,true,result.error);
 assert.deepEqual(result.receipt.players[0].upside,upside);assert.deepEqual(result.receipt.players[0].opportunityStats,{targets:8});
 assert.equal(result.receipt.players[0].opportunitySource,'local-profile');assert.equal(result.receipt.players[0].modelAgeHours,2.5);
 assert.equal(result.receipt.players[1].upside,null);assert.equal(result.receipt.players[1].opportunityStats,null);assert.equal(result.receipt.players[1].opportunitySource,null);assert.equal(result.receipt.players[1].modelAgeHours,null);
 assert.equal(result.receipt.upsideTotal,null);assert.equal(result.receipt.strategyVersion,'dfs-tournament-research-v1');
 const all=classicPlayers().map(p=>({...p,upside}));const complete=journal.freeze(input({players:all,mode:'tournament'}));assert.equal(complete.ok,true,complete.error);
 assert.equal(complete.receipt.upsideTotal,upside.value*9);
});

test('sourced upside and persisted receipt schema reject malformed evidence',()=>{
 const base={value:24.5,source:'observed-partial-fantasy-residual-v1',n:12,currentGames:3,asOf:'2026-10-05T18:45:00Z',spread:7.25,historicalMean:17.25,historicalQ90:24.5,site:'draftkings'};
 for(const upside of [23,{...base,source:'invented'},{...base,n:7},{...base,currentGames:13},{...base,asOf:'2026-10-05T19:01:00Z'},{...base,value:NaN}]){
  const result=journal.freeze(input({players:classicPlayers().map((p,i)=>i===0?{...p,upside}:p)}));assert.equal(result.ok,false);
 }
 const store=storage(),receipt=freeze().receipt;assert.equal(journal.append(store,receipt).ok,true);
 const data=JSON.parse(store.data.get(journal.KEY));delete data.receipts[0].availabilityVersion;store.data.set(journal.KEY,JSON.stringify(data));
 assert.equal(journal.read(store).ok,false);
});

test('freeze rejects invalid or already-started, unavailable, incomplete or non-genuine salary inputs',()=>{
 for(const patch of [
  {salaryHash:'not-a-hash'},
  {modelGeneratedAt:'invalid'},
  {modelGeneratedAt:'2026-10-05T19:01:00Z'},
  {injuryAt:'2026-10-05T19:01:00Z'},
  {now:NaN},
  {players:classicPlayers().slice(1)},
  {players:classicPlayers().map((p,i)=>i===0?{...p,kickoff:new Date(now).toISOString()}:p)},
  {players:classicPlayers().map((p,i)=>i===0?{...p,unavailable:true}:p)},
  {players:classicPlayers().map((p,i)=>i===0?{...p,injury:{state:'out'}}:p)},
  {players:classicPlayers().map((p,i)=>i===0?{...p,evidence:[NaN]}:p)},
  {players:classicPlayers().map((p,i)=>i===0?{...p,slotIndex:99}:p)},
  {players:classicPlayers().map((p,i)=>i===0?{...p,sourceSalary:'invented'}:p)},
 ])assert.equal(journal.freeze(input(patch)).ok,false,JSON.stringify(patch));
 const cyclic={};cyclic.self=cyclic;assert.equal(journal.freeze(input({players:classicPlayers().map((p,i)=>i===0?{...p,evidence:cyclic}:p)})).ok,false);
});

test('Classic enforces slots, player identity, game coverage, team limits and salary cap',()=>{
 const players=classicPlayers();
 assert.equal(journal.freeze(input({players:players.map((p,i)=>i===1?{...p,slot:'WR'}:p)})).ok,false);
 assert.equal(journal.freeze(input({players:players.map((p,i)=>i===1?{...p,id:players[0].id}:p)})).ok,false);
 assert.equal(journal.freeze(input({players:players.map(p=>({...p,gameId:'BUF@MIA'}))})).ok,false);
 assert.equal(journal.freeze(input({players:players.map(p=>({...p,team:'BUF'}))})).ok,false);
 assert.equal(journal.freeze(input({players:players.map((p,i)=>i===0?{...p,salary:9000}:p)})).ok,false);
});

test('Showdown applies captain projection multiplier and captain salary cost once',()=>{
 const priced=showdown();assert.equal(priced.ok,true,priced.error);assert.equal(priced.receipt.salaryUsed,45000);
 assert.equal(priced.receipt.players[0].salary,12000);assert.equal(priced.receipt.players[0].salaryCost,12000);
 assert.equal(priced.receipt.players[0].multiplier,1.5);assert.equal(priced.receipt.projectionTotal,115);
 const base=showdown({players:showdownPlayers({pricedCaptain:false})});assert.equal(base.ok,true,base.error);
 assert.equal(base.receipt.players[0].salary,8000);assert.equal(base.receipt.players[0].salaryCost,12000);assert.equal(base.receipt.salaryUsed,45000);
 assert.equal(showdown({players:showdownPlayers().map((p,i)=>i===5?{...p,game:'BUF@NYJ',gameId:'BUF@NYJ|2026-10-06'}:p)}).ok,false);
 assert.equal(showdown({players:showdownPlayers().map((p,i)=>i===5?{...p,kickoff:'2026-10-07T17:00:00Z'}:p)}).ok,false);
 assert.equal(showdown({players:showdownPlayers().map((p,i)=>i===0?{...p,multiplier:1}:p)}).ok,false);
});

test('append/read are separate, bounded, duplicate-safe and preserve malformed storage',()=>{
 const store=storage(),first=freeze();assert.equal(first.ok,true);assert.equal(journal.append(store,first.receipt).ok,true);
 assert.equal(journal.read(store).receipts.length,1);assert.equal(journal.append(store,first.receipt).ok,false);
 const before=store.data.get(journal.KEY);store.data.set(journal.KEY,'{bad json');
 assert.equal(journal.append(store,freeze({now:now+1000}).receipt).ok,false);assert.equal(store.data.get(journal.KEY),'{bad json');
 store.data.set(journal.KEY,before);
 const fullReceipts=Array.from({length:journal.CAPACITY},(_,i)=>freeze({now:now+i*1000}).receipt);
 store.data.set(journal.KEY,JSON.stringify({version:1,receipts:fullReceipts}));
 const full=journal.read(store);assert.equal(full.ok,true);assert.equal(full.receipts.length,journal.CAPACITY);
 assert.equal(journal.append(store,freeze({now:now+journal.CAPACITY*1000}).receipt).ok,false);assert.equal(journal.read(store).receipts.length,journal.CAPACITY);
});
