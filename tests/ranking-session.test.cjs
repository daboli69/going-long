'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {execFileSync,spawn}=require('node:child_process');
const session=require('../research/today-ranking/session.cjs');
const collector=require('../research/today-ranking/collect.cjs');
const root=path.resolve(__dirname,'..');
function repo(t){const p=fs.mkdtempSync(path.join(os.tmpdir(),'going-cycle-test-'));execFileSync('git',['init','--quiet',p]);t.after(()=>fs.rmSync(p,{recursive:true,force:true}));return p;}
test('shared Git lock permits one cycle and only its recorded owner can release',t=>{
 const p=repo(t);assert.equal(session.owner(p),null);session.acquire(p,'cycle-one');assert.equal(session.owner(p).runId,'cycle-one');
 assert.throws(()=>session.acquire(p,'cycle-two'));assert.throws(()=>session.release(p,'cycle-two'),/owner/);
 assert.equal(session.owner(p).runId,'cycle-one');session.release(p,'cycle-one');assert.equal(session.owner(p),null);
});
test('incomplete crashed cycle lock fails closed without a stale takeover',t=>{
 const p=repo(t);fs.mkdirSync(session.location(p));assert.throws(()=>session.owner(p));assert.throws(()=>session.acquire(p,'cycle-other'));
 assert.ok(fs.existsSync(session.location(p)));
});
test('independent process races cannot both begin a development session',async t=>{
 const p=repo(t),script=path.join(root,'research/today-ranking/session.cjs');
 const run=id=>new Promise(resolve=>{const c=spawn(process.execPath,[script,'acquire',p,id],{stdio:'ignore'});c.on('close',resolve);});
 const codes=await Promise.all([run('process-one'),run('process-two')]);assert.deepEqual(codes.sort(),[0,1]);
 session.release(p,session.owner(p).runId);
});
test('each requested ET slot is unique; 8AM remains unambiguous across DST',()=>{
 const times=['06','12','14','16','18','21','00','02'];
 const keys=times.map((hour,i)=>collector.slotKey('v1',`${i>=6?'2026-10-04':'2026-10-03'}T${hour}:00:00Z`,'scheduled'));
 assert.equal(new Set(keys).size,8);
 assert.equal(collector.slotAt('2026-10-03T12:00:00Z').hour,8);
 assert.equal(collector.slotAt('2026-11-03T13:00:00Z').hour,8);
 assert.throws(()=>collector.slotKey('v1','2026-10-03T12:16:00Z','scheduled'),/window/);
 assert.notEqual(collector.slotKey('v1','2026-10-03T12:00:01Z','manual'),collector.slotKey('v1','2026-10-03T12:00:02Z','manual'));
});
test('fresh Today default respects saved preferences and explicit deep links',()=>{
 for(const [options,tab,sport] of [[{},'best','nfl'],[{storedView:{tab:'props',sport:'nfl'}},'props','nfl'],[{url:'http://localhost/?tab=games',storedView:{tab:'props',sport:'nfl'}},'games','nfl'],[{storedView:{tab:'best',sport:'ncaa'}},'best','ncaa']]){
  const s=collector.openSource(root,'2026-10-03T12:00:00Z',options);
  try{const vm=require('node:vm');assert.equal(vm.runInContext('BET.tab',s.context),tab);assert.equal(vm.runInContext('BET.sport',s.context),sport);
   assert.match(s.w.document.querySelector('#bestSort').textContent,/Estimated chance/);assert.doesNotMatch(s.w.document.querySelector('#bestSort').textContent,/GOING rank/);
  }finally{s.dom.window.close();}
 }
});
