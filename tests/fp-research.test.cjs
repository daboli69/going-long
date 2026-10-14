const {test}=require('node:test'),assert=require('node:assert/strict');
const browser=require('../shared/fp-research.js');
const now=Date.parse('2026-10-13T21:00:00Z');
const ds=()=>({season:2026,scope:'prior_week',observed_week:5,table:'receiving_advanced',exported_at:'2026-10-13T19:00:00Z',known_at:'2026-10-13T20:00:00Z',groups:['Player Details','Receiving','FP'],columns:['Player Details.Name','Player Details.Team','Player Details.POS','Receiving.RTE %','FP.FP','FP.XFP'],records:[{'Player Details.Name':'Player','Player Details.Team':'BUF','Player Details.POS':'WR','Receiving.RTE %':80,'FP.FP':9,'FP.XFP':12}],reference_rows:[{'Receiving.RTE %':'50'}]});
test('private source produces descriptive notes without serializing raw metric tables',async()=>{
 const {deriveResearch}=await import('../server/fp-research.mjs');const d=deriveResearch([ds()],{season:2026,week:6,now});assert.equal(d.players.length,1);assert.match(d.players[0].notes.join(' '),/Week 5.*opportunity/);assert.match(d.players[0].notes.join(' '),/route participation/);assert.doesNotMatch(JSON.stringify(d),/records|reference_rows|80|source_path/);
 assert.equal(deriveResearch([{...ds(),known_at:'2026-10-14T00:00:00Z'}],{season:2026,week:6,now}).players.length,0);
});
test('route-tree share is not mislabeled participation and duplicate player rows are withheld',async()=>{
 const {deriveResearch}=await import('../server/fp-research.mjs');const d=ds();d.columns[3]='Slant.RTE %';d.records[0]['Slant.RTE %']=80;d.reference_rows=[{'Slant.RTE %':'50'}];assert.doesNotMatch(deriveResearch([d],{season:2026,week:6,now}).players[0].notes.join(' '),/participation/);d.records.push(d.records[0]);assert.equal(deriveResearch([d],{season:2026,week:6,now}).players.length,0);
});
test('private team evidence uses canonical team identity and scope-qualified descriptions',async()=>{
 const {deriveResearch}=await import('../server/fp-research.mjs');const d={...ds(),scope:'season_to_date',table:'coverage_matrix',groups:['Team Details'],columns:['Team Details.Name','Man/Zone.ZONE %','Man/Zone.MAN %'],records:[{'Team Details.Name':'Buffalo Bills','Man/Zone.ZONE %':70,'Man/Zone.MAN %':30}],reference_rows:[]};const result=deriveResearch([d],{season:2026,week:6,now});assert.equal(result.teams[0].team,'BUF');assert.match(result.teams[0].notes[0],/Current-season coverage leaned zone/);
});
test('protected read endpoint is fail closed when ACL is absent and does not grant access merely on a bearer string',async t=>{
 const {default:handler}=await import('../api/fp-research.mjs');const old=process.env.GOING_FP_ALLOWED_USERS;t.after(()=>{if(old===undefined)delete process.env.GOING_FP_ALLOWED_USERS;else process.env.GOING_FP_ALLOWED_USERS=old;});delete process.env.GOING_FP_ALLOWED_USERS;
 let body;const res={setHeader(){},end(text){body=JSON.parse(text);}};await handler({method:'GET',headers:{authorization:'Bearer arbitrary'},query:{season:'2026',week:'6'}},res);assert.equal(res.statusCode,503);assert.equal(body.players,undefined);process.env.GOING_FP_ALLOWED_USERS='owner';await handler({method:'GET',headers:{},query:{}},res);assert.equal(res.statusCode,401);
});
test('browser does not fetch private data without a session; verified schedule determines week',async()=>{
 let requests=0;await browser.refresh({season:2026,week:6,token:null,now,fetchImpl:async()=>{requests++;}});assert.equal(requests,0);assert.equal(browser.panel({player:'Player',team:'BUF'}),'');
 assert.deepEqual(browser.predictionPeriod({games:[{id:'2026_06_SEA_DEN',kickoff:'2026-10-16T00:15:00Z'}]},now),{season:2026,week:6});assert.equal(browser.predictionPeriod({games:{}},now),null);
});
test('browser renders authorized notes safely and logout or a period change removes them',async()=>{
 const envelope={schema:'going-private-fp-research-v1',season:2026,week:6,players:[{name:'Player',team:'BUF',position:'WR',notes:['<script>unsafe</script>']}],teams:[]};
 await browser.refresh({season:2026,week:6,token:'fixture',now:now+1,fetchImpl:async()=>({ok:true,json:async()=>envelope})});assert.match(browser.panel({player:'Player',team:'BUF'}),/&lt;script&gt;/);
 await browser.refresh({season:2026,week:7,token:null,now:now+2});assert.equal(browser.panel({player:'Player',team:'BUF'}),'');
});

test('nonscalar identities never expose input objects',async()=>{
 const {deriveResearch}=await import('../server/fp-research.mjs');const d=ds();d.records[0]['Player Details.Name']={licensed_metric:12345};assert.equal(deriveResearch([d],{season:2026,week:6,now}).players.length,0);
});
test('newest period request queued during older response replaces evidence',async()=>{
 let release;const calls=[];const fetchImpl=async url=>{calls.push(url);if(calls.length===1)await new Promise(r=>release=r);const week=url.includes('week=7')?7:6;return {ok:true,json:async()=>({schema:'going-private-fp-research-v1',season:2026,week,players:[],teams:[]})};};
 const first=browser.refresh({season:2026,week:6,token:'old',now:now+10,fetchImpl});await browser.refresh({season:2026,week:7,token:'new',now:now+11,fetchImpl});release();await first;assert.equal(calls.length,2);assert.match(calls[1],/week=7/);assert.match(browser.status,/Week 7/);
});

test('logout cancels queued authenticated refresh',async()=>{
 let release;let calls=0;const fetchImpl=async()=>{calls++;await new Promise(r=>release=r);return {ok:true,json:async()=>({schema:'going-private-fp-research-v1',season:2026,week:6,players:[{name:'Player',team:'BUF',position:'WR',notes:['private']}],teams:[]})};};
 const first=browser.refresh({season:2026,week:6,token:'A',now:now+20,fetchImpl});await browser.refresh({season:2026,week:7,token:'B',now:now+21,fetchImpl});await browser.refresh({season:2026,week:7,token:null,now:now+22});release();await first;assert.equal(calls,1);assert.equal(browser.panel({player:'Player',team:'BUF'}),'');
});

test('new receiver coverage and alignment exports produce qualified descriptive context',async()=>{
 const {deriveResearch}=await import('../server/fp-research.mjs');const a=ds();a.table='receiving_man_vs_zone';a.columns.push('Man.TPRR','Zone.TPRR');Object.assign(a.records[0],{'Man.TPRR':30,'Zone.TPRR':20});
 assert.match(deriveResearch([a],{season:2026,week:6,now}).players[0].notes.join(' '),/higher against man/);
 a.table='receiving_routes_run';a.columns.push('Wide.RTE','Slot.RTE');Object.assign(a.records[0],{'Wide.RTE':30,'Slot.RTE':10});assert.match(deriveResearch([a],{season:2026,week:6,now}).players[0].notes.join(' '),/came from Wide/);
 a.records[0]['Slot.RTE']=30;assert.doesNotMatch(deriveResearch([a],{season:2026,week:6,now}).players[0].notes.join(' '),/came from/);
});
test('cross-tab sign-out clears private cached notes immediately',async()=>{
 const vm=require('node:vm'),fs=require('node:fs');let storage;const context={module:{exports:{}},globalThis:null,Date,Event,localStorage:{length:0},addEventListener(type,fn){if(type==='storage')storage=fn;},dispatchEvent(){}};context.globalThis=context;vm.runInNewContext(fs.readFileSync(require.resolve('../shared/fp-research.js'),'utf8'),context);
 const b=context.module.exports;await b.refresh({season:2026,week:6,token:'fixture',now,fetchImpl:async()=>({ok:true,json:async()=>({schema:'going-private-fp-research-v1',season:2026,week:6,players:[{name:'Player',team:'BUF',position:'WR',notes:['private']}],teams:[]})})});assert.match(b.panel({player:'Player',team:'BUF'}),/private/);storage({key:'sb-project-auth-token',newValue:null});assert.equal(b.panel({player:'Player',team:'BUF'}),'');
});

test('missing separation reference cannot be interpreted as zero',async()=>{
 const {deriveResearch}=await import('../server/fp-research.mjs');for(const value of ['', '   ', null, false]){const d=ds();d.table='separation_role';d.columns.push('Overall.WIN RATE');d.records[0]['Overall.WIN RATE']=50;d.reference_rows=[{'Overall.WIN RATE':value}];assert.doesNotMatch(deriveResearch([d],{season:2026,week:6,now}).players[0].notes.join(' '),/win rate exceeded/);}
});

test('missing alignment counts cannot produce a dominant-role claim',async()=>{
 const {deriveResearch}=await import('../server/fp-research.mjs');for(const missing of [null,'',undefined]){const d=ds();d.table='receiving_routes_run';d.columns.push('Wide.RTE','Slot.RTE');Object.assign(d.records[0],{'Wide.RTE':10,'Slot.RTE':missing});assert.doesNotMatch(deriveResearch([d],{season:2026,week:6,now}).players[0].notes.join(' '),/most recorded routes/);}
});

test('private numeric preview is visible only for the matching player and future matchup',async()=>{
 const kickoff=new Date(Date.now()+86400000).toISOString(),row={name:'Player',team:'BUF',position:'WR',opponent:'NE',market:'rec_yds',status:'prospective_research_not_promoted',mean:52.5,baseline:60,delta:-7.5,kickoff};
 const data={schema:'going-private-fp-research-v1',season:2026,week:6,players:[],teams:[],challenger:{forecasts:[row]}};
 await browser.refresh({season:2026,week:6,token:'numeric-preview',now:now+100,fetchImpl:async()=>({ok:true,json:async()=>data})});
 assert.match(browser.panel({player:'Player',team:'BUF',opponent:'NE',kickoff}),/52.5 receiving yards/);assert.match(browser.panel({player:'Player',team:'BUF',opponent:'NE',kickoff}),/not yet validated/);
 assert.equal(browser.panel({player:'Player',team:'BUF',opponent:'MIA',kickoff}),'');assert.equal(browser.panel({player:'Player',team:'BUF',opponent:'NE',kickoff:new Date(Date.now()+172800000).toISOString()}),'');
 data.challenger.forecasts={};assert.equal(browser.panel({player:'Player',team:'BUF',opponent:'NE',kickoff}),'');
 await browser.refresh({season:2026,week:6,token:null,now:now+101});
});
