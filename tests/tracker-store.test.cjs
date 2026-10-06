'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const store=()=>import('../scripts/tracker_store.mjs');
const shared=()=>import('../shared/tracker-store.mjs');
const dir=()=>fs.mkdtempSync(path.join(os.tmpdir(),'tracker-store-'));
const sha=t=>crypto.createHash('sha256').update(t).digest('hex');
const PROV={inputs:{history:{generated_at:'2026-10-05T10:00:00Z',sha256:'a'.repeat(64)},nfl:{generated_at:'2026-10-05T10:01:00Z',sha256:'b'.repeat(64)}},model_source_sha256:'c'.repeat(64)};
const RULES='Automatic settlement from the published full-game result; pushes are refunded and ties on a line are never graded as wins.';
const pred=(i,extra={})=>({id:'p'+i,kind:'prediction',observed_at:`2026-10-0${1+Math.floor(i/5)}T10:00:00.000Z`,payload:{id:'p'+i,sport:'nfl',probability:.5+i/1000,provenance:structuredClone(PROV),selection:'S'+i,canonical_contract:'S'+i,...extra}});
const settle=i=>({id:'s'+i,kind:'settlement',observed_at:'2026-10-09T10:00:00.000Z',payload:{prediction_id:'p'+i,status:'win',rules_note:RULES}});
const snapshot=(records,extra={})=>({schema_version:1,generated_at:'2026-10-09T12:00:00Z',records,groups:{a:1},latest_run:{captured:records.length},...extra});
const seq=n=>Array.from({length:n},(_,i)=>pred(i));

test('interning is lossless, keeps key order, and removes exact duplicates only',async()=>{
 const {internRecords}=await store(),{expandSegment,LAYOUT}=await shared();
 const records=[...seq(12),settle(1),settle(2),pred(99,{note:'unique '+'x'.repeat(200)})];
 const {dict,records:encoded}=internRecords(records);
 const seg=JSON.parse(JSON.stringify({layout:LAYOUT,dict,records:encoded}));
 assert.equal(JSON.stringify(expandSegment(seg)),JSON.stringify(records));
 assert.ok(JSON.stringify(encoded).length<JSON.stringify(records).length*.6,'duplicated provenance and rules text are factored out');
 assert.equal(Object.values(dict).filter(v=>JSON.stringify(v)===JSON.stringify(PROV)).length,1);
 assert.ok(!JSON.stringify(dict).includes('unique x'),'a value that occurs once is never moved to the dictionary');
 assert.throws(()=>internRecords([{id:'bad',payload:{$ref:'x'}}]),/reserved \$ref/);
});

test('expansion copies by default, and shares dictionary objects only on request',async()=>{
 const {internRecords}=await store(),{expandSegment,LAYOUT}=await shared();
 const {dict,records}=internRecords(seq(6)),seg=JSON.parse(JSON.stringify({layout:LAYOUT,dict,records}));
 const copy=expandSegment(seg);copy[0].payload.provenance.model_source_sha256='mutated';
 assert.equal(copy[1].payload.provenance.model_source_sha256,'c'.repeat(64));
 const shared1=expandSegment(seg,{share:true});assert.equal(shared1[0].payload.provenance,shared1[1].payload.provenance);
 assert.equal(JSON.stringify(shared1),JSON.stringify(seq(6)));
});

test('write then read reproduces the single-file bytes, keeps top-level key order, and is idempotent',async()=>{
 const {writeTrackerStore,readTrackerStore}=await store(),d=dir(),snap=snapshot([...seq(30),...[1,2,3].map(settle)]);
 const first=await writeTrackerStore({dataDir:d,snapshot:snap,maxRaw:2500});
 assert.ok(first.segments>1);
 const back=await readTrackerStore(d);
 assert.equal(JSON.stringify(back.snapshot),JSON.stringify(snap));
 assert.deepEqual(Object.keys(back.snapshot),Object.keys(snap));
 const again=await writeTrackerStore({dataDir:d,snapshot:snap,maxRaw:2500});
 assert.equal(again.rewritten_segments,0);
 const man=JSON.parse(fs.readFileSync(path.join(d,'public_tracker','manifest.json'),'utf8'));
 for(const s of man.segments)assert.equal(sha(fs.readFileSync(path.join(d,'public_tracker',s.file),'utf8')),s.sha256);
 assert.equal(man.segments.filter(s=>s.sealed).length,man.segments.length-1);
 assert.equal(man.total_records,33);
});

test('appending replaces only the open segment; sealed segments stay byte-identical under the same names',async()=>{
 const {writeTrackerStore}=await store(),d=dir(),segDir=path.join(d,'public_tracker','segments');
 await writeTrackerStore({dataDir:d,snapshot:snapshot(seq(30)),maxRaw:2500});
 const before=Object.fromEntries(fs.readdirSync(segDir).map(f=>[f,fs.readFileSync(path.join(segDir,f),'utf8')]));
 const names=Object.keys(before).sort(),open=names.at(-1);
 const grown=await writeTrackerStore({dataDir:d,snapshot:snapshot([...seq(30),pred(30),pred(31)]),maxRaw:2500});
 assert.equal(grown.new_records,2);
 for(const f of names.slice(0,-1))assert.equal(fs.readFileSync(path.join(segDir,f),'utf8'),before[f]);
 assert.equal(fs.existsSync(path.join(segDir,open)),false,'the superseded open-segment version was removed after the manifest was replaced');
 assert.ok(fs.readdirSync(segDir).length<=names.length+1,'at most one new segment; superseded versions do not accumulate');
});

test('the store is append-only: changed, reordered or removed records are refused and nothing is written',async()=>{
 const {writeTrackerStore,readTrackerStore}=await store(),d=dir(),base=seq(20);
 await writeTrackerStore({dataDir:d,snapshot:snapshot(base),maxRaw:2500});
 const manifestBefore=fs.readFileSync(path.join(d,'public_tracker','manifest.json'),'utf8');
 const changed=structuredClone(base);changed[3].payload.probability=.99;
 await assert.rejects(()=>writeTrackerStore({dataDir:d,snapshot:snapshot(changed),maxRaw:2500}),/append-only/);
 await assert.rejects(()=>writeTrackerStore({dataDir:d,snapshot:snapshot([base[1],base[0],...base.slice(2)]),maxRaw:2500}),/append-only/);
 await assert.rejects(()=>writeTrackerStore({dataDir:d,snapshot:snapshot(base.slice(0,10)),maxRaw:2500}),/shrink/);
 assert.equal(fs.readFileSync(path.join(d,'public_tracker','manifest.json'),'utf8'),manifestBefore);
 assert.equal((await readTrackerStore(d)).snapshot.records.length,20);
});

test('integrity: tampered or missing segments and an orphaned tombstone fail loudly, never as an empty tracker',async()=>{
 const {writeTrackerStore,readTrackerStore,loadTrackerSnapshot,writeLegacyTombstone}=await store(),d=dir();
 assert.equal(await loadTrackerSnapshot(d),null,'a genuinely fresh checkout starts empty');
 await writeTrackerStore({dataDir:d,snapshot:snapshot(seq(20)),maxRaw:2500});
 const first=JSON.parse(fs.readFileSync(path.join(d,'public_tracker','manifest.json'),'utf8')).segments[0].file;
 const file=path.join(d,'public_tracker',first),text=fs.readFileSync(file,'utf8');
 fs.writeFileSync(file,text.replace('"sport":"nfl"','"sport":"ncaa"'));
 await assert.rejects(()=>readTrackerStore(d),/checksum/);
 fs.writeFileSync(file,text);fs.rmSync(file);
 await assert.rejects(()=>readTrackerStore(d));
 fs.writeFileSync(file,text);assert.equal((await readTrackerStore(d)).snapshot.records.length,20);
 // Legacy file: v1 is read, a tombstone without its manifest and a corrupt file both refuse.
 const e=dir();fs.writeFileSync(path.join(e,'public_tracker.json'),JSON.stringify(snapshot(seq(3))));
 assert.equal((await loadTrackerSnapshot(e)).records.length,3);
 assert.equal(await writeLegacyTombstone(e),true);assert.equal(await writeLegacyTombstone(e),false);
 await assert.rejects(()=>loadTrackerSnapshot(e),/manifest is missing/);
 const f=dir();fs.writeFileSync(path.join(f,'public_tracker.json'),'{"schema_version":1,"records":[{"id":');
 await assert.rejects(()=>loadTrackerSnapshot(f));
});

test('the browser loader verifies checksums so a cached manifest cannot mix with newer segments',async()=>{
 const {writeTrackerStore}=await store(),{loadTrackerVerified}=await shared(),d=dir(),snap=snapshot(seq(20));
 await writeTrackerStore({dataDir:d,snapshot:snap,maxRaw:2500});
 const read=rel=>fs.readFileSync(path.join(d,rel),'utf8');
 const rows=await loadTrackerVerified(async rel=>read(rel),{share:true});
 assert.equal(JSON.stringify(rows),JSON.stringify(snap));
 const firstFile=JSON.parse(read('public_tracker/manifest.json')).segments[0].file;
 await assert.rejects(()=>loadTrackerVerified(async rel=>rel.endsWith(firstFile)?read(rel).replace('nfl','xxx'):read(rel)),/out of sync/);
});

test('a segment above the hard size limit is refused before anything is written',async()=>{
 const {writeTrackerStore,MAX_FILE_BYTES}=await store(),d=dir();
 const huge=pred(1,{blob:Array.from({length:40},(_,i)=>String(i).repeat(1)+'y'.repeat(Math.ceil(MAX_FILE_BYTES/20))).join('|')});
 await assert.rejects(()=>writeTrackerStore({dataDir:d,snapshot:snapshot([huge]),maxRaw:1e9}),/over the .* limit/);
 assert.equal(fs.existsSync(path.join(d,'public_tracker','manifest.json')),false);
});

test('build() in store mode migrates a legacy file, replaces it with a tombstone, and re-runs idempotently',async()=>{
 const {loadTrackerSnapshot,readTrackerStore}=await store();
 const real=await loadTrackerSnapshot(path.resolve(__dirname,'../data'));
 assert.ok(real&&real.records.length>200,'repository tracker data is readable through the loader');
 const d=dir(),seed={...real,records:real.records.slice(0,300)},output=path.join(d,'public_tracker.json');
 fs.writeFileSync(output,JSON.stringify(seed));
 const {build}=await import('../scripts/build_public_tracker.mjs');
 const first=await build({output,store:true,settleOnly:true,now:'2026-10-07T00:00:00.000Z'});
 assert.ok(first.records.length>=300);
 assert.equal(JSON.parse(fs.readFileSync(output,'utf8')).schema_version,2,'legacy file is now a tombstone');
 const stored=(await readTrackerStore(d)).snapshot;
 assert.equal(JSON.stringify(stored.records),JSON.stringify(first.records));
 const again=await build({output,store:true,settleOnly:true,now:'2026-10-07T00:00:00.000Z'});
 assert.equal(JSON.stringify(again.records),JSON.stringify(first.records),'a second run appends nothing');
 // Removing the manifest after migration must stop the writer rather than restart an empty log.
 fs.rmSync(path.join(d,'public_tracker','manifest.json'));
 await assert.rejects(()=>build({output,store:true,settleOnly:true,now:'2026-10-07T00:00:00.000Z'}),/manifest is missing/);
});

test('the snapshot API serves only fixed-format tracker store paths',async()=>{
 const {default:handler}=await import('../api/snapshot.mjs'),before=global.fetch;let calls=[];
 const response=()=>({statusCode:0,headers:{},setHeader(k,v){this.headers[k]=v;},end(body){this.body=body;}});
 try{
  global.fetch=async url=>{calls.push(String(url));return Response.json({ok:true});};
  for(const file of ['public_tracker/manifest.json','public_tracker/segments/seg-000001-0123456789ab.json','public_tracker/segments/seg-000001.json']){
   const res=response();await handler({method:'GET',url:'/api/snapshot?file='+encodeURIComponent(file)},res);assert.equal(res.statusCode,200);
  }
  assert.deepEqual(calls.map(u=>u.split('/data/')[1]),['public_tracker/manifest.json','public_tracker/segments/seg-000001-0123456789ab.json','public_tracker/segments/seg-000001.json']);
  calls=[];
  for(const file of ['public_tracker/segments/../../secret.json','public_tracker/segments/seg-1.json','public_tracker/segments/seg-000001-XYZ.json','public_tracker/other.json','public_tracker/segments/seg-000001.json/../x','public_tracker/']){
   const res=response();await handler({method:'GET',url:'/api/snapshot?file='+encodeURIComponent(file)},res);assert.equal(res.statusCode,400,file);
  }
  assert.equal(calls.length,0);
 }finally{global.fetch=before;}
});

test('the export command reproduces the legacy single file byte-for-byte for rollback',async()=>{
 const {writeTrackerStore}=await store(),d=dir(),snap=snapshot([...seq(25),settle(1),settle(2)]);
 await writeTrackerStore({dataDir:d,snapshot:snap,maxRaw:2500});
 const {execFileSync}=require('node:child_process');
 const out=execFileSync(process.execPath,[path.resolve(__dirname,'../scripts/tracker_store.mjs'),'export',d],{encoding:'utf8',maxBuffer:64*1024*1024});
 assert.equal(out,JSON.stringify(snap));
});

test('crash safety: segments are content-addressed, an interrupted write leaves the old state loadable, and the next run cleans up',async()=>{
 const {writeTrackerStore,readTrackerStore}=await store(),d=dir(),segDir=path.join(d,'public_tracker','segments');
 await writeTrackerStore({dataDir:d,snapshot:snapshot(seq(30)),maxRaw:2500});
 const man=()=>JSON.parse(fs.readFileSync(path.join(d,'public_tracker','manifest.json'),'utf8'));
 const first=man();
 for(const s of first.segments)assert.match(s.file,/^segments\/seg-\d{6}-[0-9a-f]{12}\.json$/);
 // The open segment changes name when it changes content, so the old manifest's files all remain.
 const grown=await writeTrackerStore({dataDir:d,snapshot:snapshot([...seq(30),pred(30)]),maxRaw:2500});
 assert.equal(grown.new_records,1);assert.ok(grown.removed_superseded>=1,'the superseded open-segment version is removed only after the new manifest exists');
 const second=man();assert.notEqual(second.segments.at(-1).file,first.segments.at(-1).file);
 assert.deepEqual(second.segments.slice(0,-1).map(s=>s.file),first.segments.slice(0,-1).map(s=>s.file));
 for(const s of second.segments)assert.ok(fs.existsSync(path.join(d,'public_tracker',s.file)));
 // Simulated crash: new segment versions and temp files exist, but the manifest was never replaced.
 fs.writeFileSync(path.join(segDir,'seg-000009-aaaaaaaaaaaa.json'),'{"half":');
 fs.writeFileSync(path.join(segDir,'seg-000001-bbbbbbbbbbbb.json.tmp'),'x');
 assert.equal((await readTrackerStore(d)).snapshot.records.length,31,'the previous manifest still loads');
 const next=await writeTrackerStore({dataDir:d,snapshot:snapshot([...seq(30),pred(30),pred(31)]),maxRaw:2500});
 assert.ok(next.removed_superseded>=2);
 const names=new Set(fs.readdirSync(segDir)),listed=new Set(man().segments.map(s=>path.basename(s.file)));
 assert.deepEqual([...names].sort(),[...listed].sort(),'only manifest-referenced files remain');
 assert.equal((await readTrackerStore(d)).snapshot.records.length,32);
});

test('a corrupt manifest throws on read and on write instead of looking like a fresh store',async()=>{
 const {writeTrackerStore,readTrackerStore}=await store(),d=dir();
 await writeTrackerStore({dataDir:d,snapshot:snapshot(seq(10)),maxRaw:2500});
 const mp=path.join(d,'public_tracker','manifest.json'),good=fs.readFileSync(mp,'utf8');
 fs.writeFileSync(mp,good.slice(0,good.length/2));
 await assert.rejects(()=>readTrackerStore(d),SyntaxError);
 await assert.rejects(()=>writeTrackerStore({dataDir:d,snapshot:snapshot(seq(10)),maxRaw:2500}),SyntaxError);
 fs.writeFileSync(mp,'');
 await assert.rejects(()=>readTrackerStore(d));
 fs.writeFileSync(mp,good);assert.equal((await readTrackerStore(d)).snapshot.records.length,10);
 assert.equal(await readTrackerStore(dir()),null,'only a missing manifest means a fresh store');
});
