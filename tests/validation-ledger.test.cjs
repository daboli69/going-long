'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),dataDir=path.join(root,'data');
const mod=()=>import('../shared/validation-ledger.mjs');
const builder=()=>import('../scripts/validation_ledger.mjs');
const storeMod=()=>import('../scripts/tracker_store.mjs');
const support=()=>import('./support/validation-view.mjs');
const evidenceMod=()=>import('../apps/validation/evidence.mjs');
const tmp=()=>fs.mkdtempSync(path.join(os.tmpdir(),'validation-ledger-'));
const sha=t=>crypto.createHash('sha256').update(t).digest('hex');
const reader=dir=>async rel=>fs.readFileSync(path.join(dir,rel),'utf8');
const hasRealStore=fs.existsSync(path.join(dataDir,'public_tracker','manifest.json'));

// ---- synthetic records -------------------------------------------------------------------------------------
const PROV={model_source_sha256:'c'.repeat(64),inputs:{history:{generated_at:'2026-10-05T10:00:00Z',sha256:'a'.repeat(64)}}};
const pred=(id,kickoff,extra={})=>({id,kind:'prediction',observed_at:new Date(Date.parse(kickoff)-86400000).toISOString(),payload:{id,observed_at:new Date(Date.parse(kickoff)-86400000).toISOString(),tracking_group:'best_model',sport:'nfl',home:'NO',away:'ATL',kickoff,player:'P '+id,profile_id:'pid'+id,market:'rec_yds',side:'Over',side_index:0,line:50.5,book:'B',odds:1.9,american:-110,probability:.55,odds_band:'even',selection:'S|'+id+'|including_overtime',canonical_contract:'S|'+id+'|including_overtime',model_version:'v',quoted_at:'2026-01-01T00:00:00Z',ev:.01,provenance:structuredClone(PROV),readiness_snapshot:{label:'x'.repeat(40)},picks_snapshot:{version:'football-case-v2'},model_evidence:{push:.02,n:12,profileDate:'2026-10-01',seasonEvidence:{method:'80% current / 20% historical'},workload:{a:1}},...extra}});
const settle=(pid,at,status='win')=>({id:'s-'+pid,kind:'settlement',observed_at:at,payload:{prediction_id:pid,status,observed_at:at,actual:60,method:'published_full_game_result',official_kickoff:null,rules_note:'long rule text '.repeat(10),source_url:'https://x'}});
const closing=(pid,at)=>({id:'c-'+pid+at,kind:'closing',observed_at:at,payload:{prediction_id:pid,near_kickoff:true,quoted_at:at,probability:.5,method:'sampled',source:'https://x'}});
const research=id=>({id:'r-'+id,kind:'pick_research',observed_at:'2026-10-01T00:00:00Z',payload:{contract:id,picks_snapshot:{version:'football-case-v2'}}});

// ---- projection ---------------------------------------------------------------------------------------------
test('projection keeps what the dashboard reads, derives cohort/rules, and drops heavy evidence and unused kinds',async()=>{
 const {projectRecord,projectSegment}=await mod();
 const full=pred('p1','2026-10-11T17:00:00Z');
 const light=projectRecord(full);
 assert.deepEqual(Object.keys(light),['id','kind','observed_at','payload']);
 for(const k of ['provenance','readiness_snapshot','picks_snapshot','selection','canonical_contract','ev','quoted_at','model_version'])assert.equal(light.payload[k],undefined,k);
 assert.deepEqual(light.payload.model_evidence,{push:.02});
 assert.equal(light.payload.model_cohort,'current-80-20');
 assert.equal(light.payload.rules,'including_overtime');
 assert.equal(light.payload.odds_band,'even');
 const s=projectRecord(settle('p1','2026-10-12T00:00:00Z'));
 assert.deepEqual(Object.keys(s.payload).sort(),['actual','method','observed_at','official_kickoff','prediction_id','status']);
 assert.deepEqual(Object.keys(projectRecord(closing('p1','2026-10-11T16:55:00Z')).payload).sort(),['near_kickoff','prediction_id','probability','quoted_at']);
 assert.equal(projectRecord(research('x')),null);
 assert.equal(projectSegment([full,research('x')]).length,1);
 // A record the contract key cannot build from home/away/kickoff keeps the fallback fields.
 const odd=projectRecord(pred('p2','2026-10-11T17:00:00Z',{home:undefined,kickoff:'not a date'}));
 assert.equal(odd.payload.canonical_contract,'S|p2|including_overtime');
 assert.ok(odd.payload.event===undefined||typeof odd.payload.event==='string');
});

test('the projection is a pure function: same input, same bytes; the input is never mutated',async()=>{
 const {projectSegment}=await mod(),rows=[pred('p1','2026-10-11T17:00:00Z'),settle('p1','2026-10-12T00:00:00Z')],before=JSON.stringify(rows);
 assert.equal(JSON.stringify(projectSegment(rows)),JSON.stringify(projectSegment(structuredClone(rows))));
 assert.equal(JSON.stringify(rows),before);
});

// ---- real-data equivalence ----------------------------------------------------------------------------------
test('dashboard numbers and displayed fields are identical on the ledger and the full store (82 filter/group combinations)',{skip:!hasRealStore,timeout:300000},async()=>{
 const {loadTrackerSnapshot}=await storeMod(),{buildValidationLedger}=await builder(),{loadLedgerVerified}=await mod(),{view,combos}=await support();
 const work=tmp();fs.cpSync(path.join(dataDir,'public_tracker'),path.join(work,'public_tracker'),{recursive:true});
 await buildValidationLedger({dataDir:work});
 const snap=await loadTrackerSnapshot(work),manifest=JSON.parse(fs.readFileSync(path.join(work,'public_tracker','manifest.json'),'utf8'));
 const ledger=await loadLedgerVerified(reader(work),manifest),rows=ledger.rows();
 assert.ok(rows.length<snap.records.length&&rows.length>1000);
 const list=combos(snap.records);assert.ok(list.length>=80);
 for(const p of list)assert.equal(view(rows,snap,p),view(snap.records,snap,p),JSON.stringify(p));
 // Record kinds the dashboard reads keep their counts exactly.
 const count=(rs,k)=>rs.filter(r=>r.kind===k).length;
 for(const k of ['prediction','settlement','closing'])assert.equal(count(rows,k),count(snap.records,k),k);
 // Order of retained rows is the canonical order.
 const keep=new Set(rows.map(r=>r.id));assert.deepEqual(snap.records.filter(r=>keep.has(r.id)).map(r=>r.id),rows.map(r=>r.id));
});

test('lazy evidence equals the canonical record, uses only checksum-verified segments, and caches at most two segments',{skip:!hasRealStore,timeout:300000},async()=>{
 const {loadTrackerSnapshot}=await storeMod(),{buildValidationLedger}=await builder(),{loadLedgerVerified,makeEvidenceLoader}=await mod(),{recordedEvidence}=await evidenceMod();
 const work=tmp();fs.cpSync(path.join(dataDir,'public_tracker'),path.join(work,'public_tracker'),{recursive:true});
 await buildValidationLedger({dataDir:work});
 const snap=await loadTrackerSnapshot(work),manifest=JSON.parse(fs.readFileSync(path.join(work,'public_tracker','manifest.json'),'utf8'));
 const calls=[],getText=async rel=>{calls.push(rel);return fs.readFileSync(path.join(work,rel),'utf8');};
 const ledger=await loadLedgerVerified(getText,manifest);
 const loadEvidence=makeEvidenceLoader(getText,manifest,ledger.idToShard);
 const byId=new Map(snap.records.filter(r=>r.kind==='prediction').map(r=>[r.payload.id||r.id,r])),light=new Map(ledger.rows().filter(r=>r.kind==='prediction').map(r=>[r.payload.id||r.id,r]));
 const ids=manifest.segments.flatMap((s,i)=>{const inSeg=ledger.rows().filter(r=>r.kind==='prediction'&&ledger.idToShard.get(r.id)===i);return inSeg.length?[inSeg[0].id,inSeg.at(-1).id]:[];});
 assert.ok(ids.length>=8);
 for(const id of ids){
  const parts=await loadEvidence(id),full=byId.get(id).payload;
  for(const k of ['model_evidence','provenance','picks_snapshot','readiness_snapshot'])assert.equal(JSON.stringify(parts[k]),JSON.stringify(full[k]),k);
  assert.deepEqual(recordedEvidence({...light.get(id).payload,...parts,id}),recordedEvidence({...full,id}));
 }
 // Cache: a segment already held is not fetched again; only two stay resident.
 calls.length=0;const first=ids[0],second=ids.find(i=>ledger.idToShard.get(i)!==ledger.idToShard.get(first));
 const third=ids.find(i=>![ledger.idToShard.get(first),ledger.idToShard.get(second)].includes(ledger.idToShard.get(i)));
 const l2=makeEvidenceLoader(getText,manifest,ledger.idToShard);await l2(first);await l2(first);await l2(second);await l2(third);
 assert.equal(calls.filter(c=>c.startsWith('public_tracker/segments/')).length,3);
 await l2(first);assert.equal(calls.filter(c=>c.startsWith('public_tracker/segments/')).length,4,'the oldest cached segment was evicted');
 await assert.rejects(()=>l2('no-such-record'),/Unknown record/);
 // A tampered canonical segment is refused.
 const seg=manifest.segments[ledger.idToShard.get(first)].file,segPath=path.join(work,'public_tracker',seg);
 fs.writeFileSync(segPath,fs.readFileSync(segPath,'utf8').replace('"sport":"nfl"','"sport":"ncaa"'));
 await assert.rejects(()=>makeEvidenceLoader(getText,manifest,ledger.idToShard)(first),/out of sync/);
});

// ---- adversarial equivalence (cases real data does not currently exercise) ----------------------------------
test('edge cases give identical dashboard results on full and projected records',async()=>{
 const {projectSegment}=await mod(),{view,combos}=await support();
 const k1='2026-10-11T17:00:00Z',obs='2026-10-10T12:00:00Z';
 const mk=(id,extra={},kickoff=k1)=>{const r=pred(id,kickoff,extra);r.observed_at=obs;r.payload.observed_at=obs;return r;};
 const records=[
  mk('e1',{rules:''}),mk('e1b',{rules:undefined,profile_id:'pide1',player:'P e1'}),   // same contract in the full path: an empty-string `rules` must fall through like the key does, or the pair double-counts
  mk('e2',{rules:undefined}),mk('e3',{sport:undefined}),mk('e4',{home:undefined,away:undefined}),mk('e5',{model_cohort:undefined,model_evidence:{push:1.5,seasonEvidence:{method:'80% current'}}}),
  mk('e6',{probability:null}),mk('e7',{model_evidence:{push:-.2}}),mk('e8',{model_cohort:'legacy'}),mk('e9',{actionable:true}),
  {...mk('e10'),payload:{...mk('e10').payload,kickoff:'not a date'}},
  settle('e1','2026-10-12T03:00:00Z'),settle('e1','2026-10-12T04:00:00Z','loss'),            // duplicate settlements: last wins
  settle('e2','2026-10-09T00:00:00Z'),                                                       // settled before kickoff: not graded
  settle('e3','2026-10-12T03:00:00Z','refund'),settle('e5','2026-10-12T03:00:00Z','void'),settle('e7','2026-10-12T03:00:00Z','loss'),
  {...settle('e8','2026-10-12T03:00:00Z'),payload:{...settle('e8','2026-10-12T03:00:00Z').payload,official_kickoff:'2026-10-11T17:05:00Z'}},   // within 10 minutes
  {...settle('e9','2026-10-12T03:00:00Z'),payload:{...settle('e9','2026-10-12T03:00:00Z').payload,official_kickoff:'2026-10-11T19:30:00Z'}},   // outside
  {...settle('e6','2026-10-12T03:00:00Z'),payload:{...settle('e6','2026-10-12T03:00:00Z').payload,sport:'ncaa'}},                               // settlement sport overrides
  closing('e1','2026-10-11T16:55:00Z'),closing('e8','2026-10-11T16:58:00Z'),research('e1'),
 ];
 const light=projectSegment(records),meta={result_coverage:{slates:[]}};
 // Non-vacuity: the fixtures must actually flow through selection, grading, refunds and price moves.
 const probe=JSON.parse(view(records,meta,{cohort:'all',sport:'all',days:'all',date:'',game:'',group:'best_model'},Date.parse('2026-10-20T00:00:00Z')));
 assert.ok(probe.picks.length>=6,'selected picks: '+probe.picks.length);
 assert.ok(probe.receipts.length>=3,'graded receipts: '+probe.receipts.length);
 assert.ok(probe.rest.counts.refund+probe.rest.counts.void>=1);
 for(const asOf of [Date.parse('2026-10-09T00:00:00Z'),Date.parse('2026-10-11T18:00:00Z'),Date.parse('2026-10-20T00:00:00Z')])
  for(const p of [...combos(records),{cohort:'all',sport:'ncaa',days:'all',date:'',game:'',group:'best_model'},{cohort:'all',sport:'all',days:'7',date:'',game:'',group:'alerts'}])
   assert.equal(view(light,meta,p,asOf),view(records,meta,p,asOf),JSON.stringify(p)+' @'+asOf);
});

// ---- determinism, integrity, staleness ----------------------------------------------------------------------
async function syntheticStore(){
 const {writeTrackerStore}=await storeMod(),dir=tmp();
 const records=[
  pred('a1','2026-09-13T17:00:00Z'),pred('a2','2026-09-20T17:00:00Z'),research('a1'),settle('a1','2026-09-14T03:00:00Z'),closing('a1','2026-09-13T16:55:00Z'),
  pred('b1','2027-01-17T20:00:00Z'),pred('b2','2027-01-24T20:00:00Z'),settle('a2','2026-09-21T03:00:00Z','loss'),
  pred('c1','2027-09-12T17:00:00Z'),pred('c2','2027-09-19T17:00:00Z'),settle('b1','2027-09-13T03:00:00Z'),closing('b2','2027-09-12T00:00:00Z'),
  pred('d1','2027-09-26T17:00:00Z'),settle('c1','2027-09-27T03:00:00Z'),
 ];
 await writeTrackerStore({dataDir:dir,snapshot:{schema_version:1,generated_at:'2027-10-01T00:00:00Z',records,groups:{}},maxRaw:2600});
 return {dir,records};
}

test('the ledger is deterministic, content-addressed, rebuildable from scratch, and idempotent',async()=>{
 const {buildValidationLedger}=await builder(),{dir}=await syntheticStore();
 const first=await buildValidationLedger({dataDir:dir}),ld=path.join(dir,'derived','validation_ledger');
 assert.ok(first.shards>1&&first.rewritten===first.shards);
 const snapshot=()=>Object.fromEntries(fs.readdirSync(ld).map(f=>[f,fs.readFileSync(path.join(ld,f),'utf8')]));
 const before=snapshot();
 assert.equal((await buildValidationLedger({dataDir:dir})).rewritten,0);
 fs.rmSync(path.join(dir,'derived'),{recursive:true});await buildValidationLedger({dataDir:dir});
 assert.deepEqual(snapshot(),before,'regenerating from scratch reproduces identical bytes and names');
 const idx=JSON.parse(before['index.json']);
 assert.equal(idx.derived,true);assert.equal(idx.not_for_evaluation,true);assert.equal(idx.layout,'validation-ledger-v1');
 for(const s of idx.shards){const text=before[s.file];assert.equal(sha(text),s.sha256);assert.match(s.file,new RegExp('^ledger-\\d{6}-'+s.source_segment_sha256.slice(0,12)+'-'+s.sha256.slice(0,12)+'\\.json$'));}
 assert.equal(JSON.parse(before[idx.shards[0].file]).source.segment_sha256,idx.shards[0].source_segment_sha256);
 // Superseded files are removed only after the new index exists.
 fs.writeFileSync(path.join(ld,'ledger-000099-aaaaaaaaaaaa-bbbbbbbbbbbb.json'),'{}');
 const cleaned=await buildValidationLedger({dataDir:dir});assert.equal(cleaned.removed,1);
});

test('integrity: tampered shards, a stale or foreign index, and the wrong layout are all refused',async()=>{
 const {buildValidationLedger}=await builder(),{loadLedgerVerified,INDEX_PATH}=await mod(),{dir}=await syntheticStore();
 await buildValidationLedger({dataDir:dir});
 const manifest=()=>JSON.parse(fs.readFileSync(path.join(dir,'public_tracker','manifest.json'),'utf8')),ld=path.join(dir,'derived','validation_ledger');
 const idx=()=>JSON.parse(fs.readFileSync(path.join(ld,'index.json'),'utf8'));
 await loadLedgerVerified(reader(dir),manifest(),{seasons:'all'});
 const shard=path.join(ld,idx().shards[0].file),good=fs.readFileSync(shard,'utf8');
 fs.writeFileSync(shard,good.replace('"sport":"nfl"','"sport":"ncaa"'));
 await assert.rejects(()=>loadLedgerVerified(reader(dir),manifest(),{seasons:'all'}),/checksum/);
 fs.writeFileSync(shard,good);
 const stale=manifest();stale.segments[1].sha256='0'.repeat(64);
 await assert.rejects(()=>loadLedgerVerified(reader(dir),stale),/out of sync/);
 const shorter=manifest();shorter.segments=shorter.segments.slice(0,-1);shorter.total_records-=1;
 await assert.rejects(()=>loadLedgerVerified(reader(dir),shorter),/out of sync/);
 for(const mutate of [i=>{i.derived=false;},i=>{i.not_for_evaluation=false;},i=>{i.layout='public-tracker-segments-v1';},i=>{i.projection_version='validation-light-v0';}]){
  const bad=idx();mutate(bad);
  await assert.rejects(()=>loadLedgerVerified(async rel=>rel===INDEX_PATH?JSON.stringify(bad):fs.readFileSync(path.join(dir,rel),'utf8'),manifest()),/Not a validation ledger|projection version/);
 }
});

// ---- season windows -----------------------------------------------------------------------------------------
test('default load is the latest season; every loaded prediction has all its settlements and closings; loading earlier seasons restores everything in canonical order',async()=>{
 const {buildValidationLedger}=await builder(),{loadLedgerVerified,projectSegment,seasonOf}=await mod(),{loadTrackerSnapshot}=await storeMod(),{dir}=await syntheticStore();
 await buildValidationLedger({dataDir:dir});
 const manifest=JSON.parse(fs.readFileSync(path.join(dir,'public_tracker','manifest.json'),'utf8')),snap=await loadTrackerSnapshot(dir);
 assert.equal(seasonOf('2027-01-17T20:00:00Z'),2026);assert.equal(seasonOf('2027-09-12T17:00:00Z'),2027);
 const latest=await loadLedgerVerified(reader(dir),manifest);
 assert.ok(latest.skipped().length>0,'older shards are not loaded by default');
 const closure=(rows,seasons)=>{
  const ids=new Set(rows.map(r=>r.id)),loadedPred=rows.filter(r=>r.kind==='prediction'&&seasons.includes(seasonOf(r.payload.kickoff)));
  for(const p of loadedPred)for(const r of snap.records){
   const linked=(r.kind==='settlement'||r.kind==='closing')&&r.payload.prediction_id===p.id;
   if(linked)assert.ok(ids.has(r.id),`${r.kind} ${r.id} of ${p.id} must be loaded with it`);
  }
 };
 closure(latest.rows(),[2027]);
 // 2026 predictions whose settlement was appended in 2027 shards stay joinable when their season is selected.
 const s2026=await loadLedgerVerified(reader(dir),manifest,{seasons:[2026]});
 closure(s2026.rows(),[2026]);
 assert.ok(s2026.rows().some(r=>r.id==='s-b1'),'a 2027 settlement of a 2026 prediction is loaded with season 2026');
 const all=await latest.loadMore('all');
 assert.equal(JSON.stringify(all),JSON.stringify(projectSegment(snap.records)));
 assert.equal(latest.skipped().length,0);
});

// ---- safeguards -----------------------------------------------------------------------------------------------
test('nothing that writes, freezes, settles or evaluates the tracker can read the derived ledger',()=>{
 const forbidden=/validation[_-]ledger|derived\/validation/;
 const protectedFiles=['scripts/build_public_tracker.mjs','scripts/calibration_audit.mjs','research/tracker-results/audit.cjs','scripts/current_season_review.py','scripts/build_pipeline.py','scripts/build_consumer_data.mjs','shared/model-cohort.mjs','shared/tracker-store.mjs','scripts/tracker_store.mjs','scripts/tracker_store.py','scripts/signal_shards.mjs','shared/football-picks-snapshot.cjs','shared/football-readiness-snapshot.cjs'];
 for(const f of protectedFiles)assert.ok(!forbidden.test(fs.readFileSync(path.join(root,f),'utf8')),f+' must not reference the validation ledger');
 const importers=[],walk=d=>{for(const e of fs.readdirSync(path.join(root,d),{withFileTypes:true})){
  if(['node_modules','dist','tests','data','.git'].includes(e.name))continue;
  const rel=path.join(d,e.name);
  if(e.isDirectory())walk(rel);else if(/\.(mjs|cjs|js|jsx|py)$/.test(e.name)&&/validation[_-]ledger/.test(fs.readFileSync(path.join(root,rel),'utf8')))importers.push(rel.replace(/\\/g,'/'));
 }};
 for(const d of ['apps','scripts','shared','research','api','server'])walk(d);
 assert.deepEqual(importers.sort(),['api/snapshot.mjs','apps/validation/src.jsx','scripts/validation_ledger.mjs','server/worker.mjs','shared/validation-ledger.mjs'],'only the dashboard, its builder, the module and the two read-only path allowlists may name the ledger');
 const wf=fs.readFileSync(path.join(root,'.github/workflows/data.yml'),'utf8');
 assert.ok(wf.indexOf('scripts/build_public_tracker.mjs')<wf.indexOf('scripts/validation_ledger.mjs build'),'the ledger is built after the canonical tracker step');
});

test('the snapshot API serves only fixed-format ledger names',async()=>{
 const {default:handler}=await import('../api/snapshot.mjs'),before=global.fetch,calls=[];
 const response=()=>({statusCode:0,headers:{},setHeader(k,v){this.headers[k]=v;},end(body){this.body=body;}});
 try{
  global.fetch=async url=>{calls.push(String(url).split('/data/')[1]);return Response.json({ok:true});};
  for(const file of ['derived/validation_ledger/index.json','derived/validation_ledger/ledger-000001-0123456789ab-fedcba987654.json']){const res=response();await handler({method:'GET',url:'/api/snapshot?file='+encodeURIComponent(file)},res);assert.equal(res.statusCode,200,file);}
  assert.equal(calls.length,2);
  for(const file of ['derived/validation_ledger/../../secret.json','derived/validation_ledger/ledger-1-a-b.json','derived/other/index.json','derived/validation_ledger/','derived/validation_ledger/index.json/../x']){const res=response();await handler({method:'GET',url:'/api/snapshot?file='+encodeURIComponent(file)},res);assert.equal(res.statusCode,400,file);}
  assert.equal(calls.length,2);
 }finally{global.fetch=before;}
});

test('simultaneous evidence requests for one segment share a single download, and a failed download is not cached',{skip:!hasRealStore,timeout:300000},async()=>{
 const {buildValidationLedger}=await builder(),{loadLedgerVerified,makeEvidenceLoader}=await mod();
 const work=tmp();fs.cpSync(path.join(dataDir,'public_tracker'),path.join(work,'public_tracker'),{recursive:true});
 await buildValidationLedger({dataDir:work});
 const manifest=JSON.parse(fs.readFileSync(path.join(work,'public_tracker','manifest.json'),'utf8'));
 let fail=true;const calls=[],getText=async rel=>{if(rel.startsWith('public_tracker/segments/')){calls.push(rel);if(fail)throw new Error('HTTP 503');}return fs.readFileSync(path.join(work,rel),'utf8');};
 const ledger=await loadLedgerVerified(getText,manifest);
 const ids=ledger.rows().filter(r=>r.kind==='prediction'&&ledger.idToShard.get(r.id)===0).slice(0,3).map(r=>r.id);
 const load=makeEvidenceLoader(getText,manifest,ledger.idToShard);
 await assert.rejects(()=>load(ids[0]),/503/);fail=false;calls.length=0;
 const all=await Promise.all(ids.map(load));
 assert.equal(calls.length,1);assert.equal(all.length,3);assert.ok(all.every(x=>x.provenance));
});
