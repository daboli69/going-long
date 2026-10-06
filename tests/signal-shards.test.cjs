'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const NOW=Date.parse('2026-10-07T12:00:00Z');
const rec=(id,observed,extra={})=>({schema_version:1,id,sport:'nfl',observed_at:observed,entity:{name:id},event:{away:'A',home:'B',start:observed},signal_family:'F',features:{k:id},outcome:null,...extra});
const dir=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sig-test-'));
const mod=()=>import('../scripts/signal_shards.mjs');
const read=(d,f)=>JSON.parse(fs.readFileSync(path.join(d,f),'utf8'));
const root=path.resolve(__dirname,'..');

async function openResults(fetchImpl){
 // The page's ../shared paths resolve only in the deployed /results/ layout, so run its scripts directly.
 const {JSDOM,VirtualConsole}=require('jsdom'),vm=require('node:vm');
 const html=fs.readFileSync(path.join(root,'apps/results/index.html'),'utf8').replace(/<script[^>]*><\/script>/g,'');
 const dom=new JSDOM(html,{url:'https://going-long.test/results/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:new VirtualConsole()});
 const w=dom.window;w.fetch=fetchImpl;
 const ctx=dom.getInternalVMContext();
 for(const file of ['shared/evidence-ui.js','apps/results/results.js'])vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),ctx);
 const status=()=>w.document.getElementById('status').textContent;
 for(let i=0;i<80&&!status().includes('Published');i++)await new Promise(r=>setTimeout(r,25));
 return {dom,w,status,button:()=>[...w.document.querySelectorAll('button')].find(b=>b.textContent==='Load older observations')};
}

test('partition: current window by UTC observation day, older days sharded, undated stays visible',async()=>{
 const {partitionRecords}=await mod();
 const rows=[rec('a','2026-10-07T01:00:00Z'),rec('b','2026-09-30T23:59:59Z'),rec('c','2026-09-30T00:00:00Z'),rec('d','2026-09-01T00:00:00Z'),rec('e','not a date'),rec('f',undefined)];
 const p=partitionRecords(rows,{now:NOW,windowDays:7});
 assert.deepEqual(p.current.map(r=>r.id),['a','b','c','e','f']); // the cutoff day itself is still current
 assert.deepEqual([...p.shards.keys()],['2026-09-01']);
 const q=partitionRecords(rows,{now:NOW,windowDays:3});
 assert.deepEqual([...q.shards.keys()].sort(),['2026-09-01','2026-09-30']);
});

test('round trip is lossless; index counts and sha256 match the files; a second write changes nothing',async()=>{
 const {writeSignalTracker,readSignalRecords}=await mod(),d=dir();
 const rows=[rec('a','2026-10-07T01:00:00Z'),rec('b','2026-09-20T05:00:00Z',{outcome:{values:{x:1}}}),rec('c','2026-09-20T07:00:00Z'),rec('d','2026-09-21T07:00:00Z')];
 const r1=await writeSignalTracker({dataDir:d,generated_at:'g',sources:{s:1},records:rows,now:NOW});
 assert.deepEqual([r1.total,r1.current,r1.archived,r1.shards,r1.rewritten_shards],[4,1,3,2,2]);
 const back=(await readSignalRecords(d)).records;
 assert.deepEqual(new Map(back.map(r=>[r.id,JSON.stringify(r)])),new Map(rows.map(r=>[r.id,JSON.stringify(r)])));
 const main=read(d,'signal_tracker.json');
 assert.deepEqual(Object.keys(main),['schema_version','generated_at','sources','records','archive']);
 assert.equal(main.archive.total_records,4);assert.equal(main.archive.layout,'daily-shards-v1');
 for(const s of main.archive.shards){
  const text=fs.readFileSync(path.join(d,s.file),'utf8');
  assert.equal(crypto.createHash('sha256').update(text).digest('hex'),s.sha256);
  assert.equal(JSON.parse(text).records.length,s.records);assert.equal(Buffer.byteLength(text),s.bytes);
 }
 const r2=await writeSignalTracker({dataDir:d,generated_at:'g',sources:{s:1},records:rows,now:NOW});
 assert.equal(r2.rewritten_shards,0);
});

test('writes union with stored data: updates apply, nothing is ever dropped or deleted',async()=>{
 const {writeSignalTracker,readSignalRecords}=await mod(),d=dir();
 const old=rec('old','2026-09-20T05:00:00Z'),keep=rec('keep','2026-09-21T05:00:00Z');
 await writeSignalTracker({dataDir:d,generated_at:'1',sources:{},records:[old,keep,rec('new','2026-10-07T01:00:00Z')],now:NOW});
 // Later run: upstream no longer supplies 'keep' and attaches an outcome to 'old'.
 const settled={...old,outcome:{values:{result:'win'}}};
 const r=await writeSignalTracker({dataDir:d,generated_at:'2',sources:{},records:[settled,rec('new','2026-10-07T01:00:00Z')],now:NOW});
 const all=new Map((await readSignalRecords(d)).records.map(x=>[x.id,x]));
 assert.equal(all.size,3);
 assert.deepEqual(all.get('old').outcome,{values:{result:'win'}});
 assert.ok(all.get('keep'));
 assert.ok(fs.existsSync(path.join(d,'signal_archive','2026-09-21.json')));
 assert.equal(r.rewritten_shards,1); // only the updated day was rewritten
});

test('a record leaving the current window moves to its day shard without loss',async()=>{
 const {writeSignalTracker,readSignalRecords}=await mod(),d=dir(),row=rec('x','2026-10-01T10:00:00Z');
 await writeSignalTracker({dataDir:d,generated_at:'1',sources:{},records:[row],now:NOW});
 assert.equal(read(d,'signal_tracker.json').records.length,1);
 await writeSignalTracker({dataDir:d,generated_at:'2',sources:{},records:[row],now:Date.parse('2026-10-20T00:00:00Z')});
 assert.equal(read(d,'signal_tracker.json').records.length,0);
 assert.equal(read(d,'signal_archive/2026-10-01.json').records[0].id,'x');
 assert.equal((await readSignalRecords(d)).records.length,1);
});

test('Results page shows the current window, then lazily loads archived days without double counting',async()=>{
 const files={
  '../data/signal_tracker.json':{schema_version:1,generated_at:'2026-10-07T00:00:00Z',sources:{football:{status:'FRESH'}},records:[rec('c1','2026-10-07T01:00:00Z')],
   archive:{layout:'daily-shards-v1',current_window_days:7,total_records:3,archived_records:2,shards:[{date:'2026-09-20',file:'signal_archive/2026-09-20.json',records:2}]}},
  '../data/signal_archive/2026-09-20.json':{schema_version:1,date:'2026-09-20',records:[rec('o1','2026-09-20T05:00:00Z'),rec('o2','2026-09-20T06:00:00Z',{outcome:{values:{r:'w'}}})]}};
 const calls=[];
 const {dom,w,status,button}=await openResults(async u=>{calls.push(u);const body=files[u];return {ok:!!body,json:async()=>body};});
 assert.match(status(),/1 matching signal observations/);
 assert.match(status(),/2 older observations are archived and not loaded/);
 assert.equal(button().hidden,false);
 assert.deepEqual(calls,['../data/signal_tracker.json']);
 button().click();
 for(let i=0;i<80&&!status().includes('Full archive loaded');i++)await new Promise(r=>setTimeout(r,50));
 assert.match(status(),/3 matching signal observations/);
 assert.match(status(),/Full archive loaded/);
 assert.equal(button().hidden,true);
 assert.equal(w.document.querySelectorAll('#records article').length,3);
 assert.deepEqual(calls,['../data/signal_tracker.json','../data/signal_archive/2026-09-20.json']);
 dom.window.close();
});

test('a legacy single-file journal (no archive block) still renders and shows no archive control',async()=>{
 const {dom,w,status,button}=await openResults(async()=>({ok:true,json:async()=>({schema_version:1,generated_at:'2026-10-07T00:00:00Z',sources:{},records:[rec('l1','2026-10-07T01:00:00Z')]})}));
 assert.match(status(),/1 matching signal observations/);
 assert.doesNotMatch(status(),/archived/);
 assert.equal(button().hidden,true);
 assert.equal(w.document.querySelectorAll('#records article').length,1);
 dom.window.close();
});
