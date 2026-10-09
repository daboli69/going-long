'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {assess,groups,card,currentPlayerEvidence,currentGameEvidence}=require('../shared/football-confidence.js');
const {openSource}=require('../research/today-ranking/collect.cjs');
const at='2026-10-03T13:00:00Z',now=Date.parse(at);
const options={now,season:2026,contextAt:at,learningAt:at,historyAt:at};
function row(overrides={}){return {kind:'prop',sport:'nfl',profileId:'p',player:'Player',team:'A',away:'A',home:'B',event:'e',market:'rec_yds',side:'Over',line:55.5,book:'Book',odds:-110,dec:1+100/110,prob:.6,push:0,ev:.6*(1+100/110)-1,n:12,profileDate:'2026-09-27',kickoff:'2026-10-04T17:00:00Z',updatedAt:at,flags:[],seasonEvidence:{season:2026,current_games:6,historical_games:6,current_weight:.8,sample_confidence:'moderate',method:'Unvalidated policy'},...overrides};}
function role(overrides={}){return row({flags:[{id:'opportunity',family:'role',why:'Role'}],evidence:{opportunity:{season:2026,last_game:'2026-09-27',adjustedShare:.7,average:.5}},...overrides});}
function matchOptions(overrides={}){return {...options,matchup:{player_id:'p',opponent:'B',kickoff:row().kickoff,weakness_id:'w',role:'WR_RECEIVING',active_signal:true,lineage:['current player usage']},weakness:{id:'w',current:{season:2026,sample:60,value:1.5},lineage:['current defensive opportunities']},...overrides};}

test('a high probability, expensive price or apparent return alone never earns current support',()=>{
 const e=assess(row({prob:.98,odds:-500,dec:1.2,ev:.176,flags:[{id:'gap',family:'model'}]}),options);
 assert.equal(e.group,'developing');assert.equal(e.footballSupport,false);
 assert.ok(e.concerns.some(x=>x.includes('Short price')));
 assert.ok(e.concerns.some(x=>x.includes('not established')));
});
test('traceable exact-direction role support is qualitative and separates likelihood and price',()=>{
 const c=role(),e=assess(c,options);assert.equal(e.group,'support');assert.ok(e.why.includes('pass-snap'));
 const text=card(c,e,{label:'Over 55.5 Receiving yards',key:'k',teamLabel:x=>x,gameKey:'g'});
 assert.match(text,/Current support/);assert.match(text,/Model estimate · not Confidence/);assert.match(text,/52\.4% win-only break-even/);assert.doesNotMatch(text,/High confidence|60\.0% Confidence|best bet/i);
});
test('wrong direction, market, season, historical role or unavailable source never qualifies',()=>{
 for(const c of [role({side:'Under'}),role({market:'rush_yds'}),role({sport:'ncaa',kind:'game'}),role({evidence:{opportunity:{season:2025,last_game:'2026-09-27',adjustedShare:.7,average:.5}}})])assert.notEqual(assess(c,options).group,'support');
 assert.notEqual(assess(role(),{...options,contextAt:'2026-09-01'}).group,'support');
 assert.notEqual(assess(role({seasonEvidence:{season:2025,current_games:6,historical_games:6}}),options).group,'support');
});
test('low samples remain descriptive; price, model and availability checks are separated',()=>{
 const low=assess(role({seasonEvidence:{season:2026,current_games:2,historical_games:10,sample_confidence:'low'}}),options);assert.equal(low.group,'support');assert.ok(low.concerns.some(x=>/small current-season sample/i.test(x)));
 const stale=assess(role({updatedAt:'2026-10-03T01:00:00Z'}),options);assert.equal(stale.group,'support');assert.equal(stale.footballChecks.length,0);assert.equal(stale.priceChecks[0].code,'price');
 for(const c of [role({flags:[{id:'check'}]}),role({injury:{stale:true}}),role({profileDate:'2026-10-05'}),role({profileDate:null})])assert.equal(assess(c,options).group,'check');
 assert.equal(assess(role({injury:{roleBoost:true}}),options).group,'developing');
 const future=assess(role({updatedAt:'2026-10-03T14:00:00Z'}),options);assert.equal(future.group,'support');assert.equal(future.priceChecks[0].code,'price');
 assert.equal(assess(role(),{...options,historyAt:'2026-09-30'}).group,'check');
});
test('NCAA exposes current versus older policy evidence without pretending scoring is matchup support',()=>{
 const c=row({kind:'game',sport:'ncaa',market:'total',seasonEvidence:null,gameSeasonEvidence:{home_current_games:2,away_current_games:3,home_current_weight:.8,away_current_weight:.8,policy:'80/20 existing unvalidated policy'}});
 const e=assess(c,options);assert.equal(e.group,'developing');assert.ok(e.concerns.some(x=>x.includes('Completed current-season')));assert.ok(e.facts.some(([k,v])=>k==='Away / home current model games'&&v==='3 / 2'));
 assert.equal(assess({...c,kind:'prop'},options).eligible,false);
});
test('defensive support requires the exact player/opponent/role/weakness/market/direction',()=>{
 const c=row();assert.equal(assess(c,matchOptions()).group,'support');
 assert.equal(assess(role({prob:.3}),options).group,'developing','role signal cannot override a model leaning the other way');
 assert.equal(assess({...c,prob:.3},matchOptions()).group,'developing','matchup signal cannot override a model leaning the other way');
 assert.notEqual(assess({...c,market:'rush_yds'},matchOptions()).group,'support');
 for(const patch of [{player_id:'other'},{opponent:'C'},{weakness_id:'other'},{role:'RB_RUSHING'},{active_signal:false},{lineage:[]},{kickoff:'2026-10-04T23:00:00Z'}]){
  const opts=matchOptions();opts.matchup={...opts.matchup,...patch};assert.notEqual(assess(c,opts).group,'support');
 }
 const opts=matchOptions();opts.weakness.current.value=-1;assert.notEqual(assess(c,opts).group,'support');assert.equal(assess({...c,side:'Under'},opts).group,'support');
});
test('historical charting is a concern and is not made current by the latest game date',()=>{
 const c=row({evidence:{chartingAt:'2026-01-04',playerObservedAt:'2026-09-27'},flags:[{id:'demand',family:'role'},{id:'pace',family:'role'}]});const e=assess(c,options);assert.equal(e.group,'developing');assert.ok(e.concerns.some(x=>x.includes('Charted participation is historical')));
});
test('groups keep calculations and safely escape source text while exposing all entries',()=>{
 const rows=[role({profileId:'first',prob:.6}),role({profileId:'second',prob:.9})],before=JSON.stringify(rows),g=groups(rows,options);
 assert.deepEqual(g.support.map(x=>x.candidate.profileId),['first','second']);assert.equal(JSON.stringify(rows),before);
 const e=assess(row({player:'<script>',book:'<img>'}),options),text=card(row({book:'<img>'}),e,{label:'<script>alert(1)</script>',key:'" x',teamLabel:x=>x,gameKey:'g'});assert.ok(text.includes('&lt;script&gt;'));assert.ok(text.includes('&lt;img&gt;'));assert.ok(!text.includes('<script>'));
 assert.equal(groups(Array.from({length:27},(_,i)=>role({profileId:String(i)})),options).support.length,27);
});
test('January retains the previous football season rather than misclassifying current role evidence',()=>{
 const jan='2027-01-02T12:00:00Z',opts={...options,now:Date.parse(jan),historyAt:jan,contextAt:jan,learningAt:jan};
 const c=role({profileDate:'2026-12-27',kickoff:'2027-01-03T17:00:00Z',updatedAt:jan,evidence:{opportunity:{season:2026,last_game:'2026-12-27',adjustedShare:.7,average:.5}}});assert.equal(assess(c,opts).group,'support');
});
test('Confidence presentation preserves the registered Champion/generator/C1/C2 hashes (today-ranking-v2)',t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 const registry=require('../research/today-ranking/experiment-v2.json');
 assert.equal(s.codeHashes.policy,registry.policyCodeHash);assert.equal(s.codeHashes.generator,registry.generatorCodeHash);
 assert.equal(require('../research/today-ranking/collect.cjs').textHash(fs.readFileSync(path.join(root,'shared/ranking-policies.cjs'))),registry.challengersSourceHash);
});
test('Today integration handles empty state, unlimited pagination, league separation, details and focus',t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 vm.runInContext(fs.readFileSync(path.join(root,'shared/football-confidence.js'),'utf8'),s.context);
 s.w.fixture=Array.from({length:11},(_,i)=>role({profileId:'p'+i,event:'e'+i}));
 vm.runInContext(`BET.sport='nfl';BET.history={generated_at:'${at}',season_review:{season:2026}};BET.context={generated_at:'${at}'};BET.learning={generated_at:'${at}'};renderGoingConfidence(fixture);`,s.context);
 const d=s.w.document;assert.equal(d.querySelectorAll('.confidence-card').length,4);assert.match(d.getElementById('confidenceCount').textContent,/4 of 11/);
 const detail=d.querySelector('[data-confidence-detail]');detail.open=true;detail.ontoggle();
 const more=d.getElementById('confidenceMore');more.focus();vm.runInContext('CONFIDENCE_LIMIT.nfl+=4;renderGoingConfidence()',s.context);
 assert.equal(d.querySelectorAll('.confidence-card').length,8);assert.equal(d.querySelector('[data-confidence-detail]').open,true);assert.equal(d.activeElement,more);
 vm.runInContext('CONFIDENCE_LIMIT.nfl+=4;renderGoingConfidence()',s.context);assert.equal(d.querySelectorAll('.confidence-card').length,11);assert.equal(more.hidden,true);assert.equal(d.activeElement,d.querySelector('.confidence-card:last-child summary'));
 vm.runInContext("BET.sport='ncaa';renderGoingConfidence([])",s.context);assert.equal(d.querySelectorAll('.confidence-card').length,0);assert.match(d.getElementById('confidenceStatus').textContent,/No eligible selections/);assert.match(d.querySelector('.confidence-kicker').textContent,/NCAA/);
});

test('Confidence saving preserves NCAA contract, league, quote and kickoff without losing focus',t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 s.w.pick=row({sport:'ncaa',kind:'game',market:'spread',side:'Home',line:-3.5,seasonEvidence:null});
 s.w.GoingUI={add:r=>{s.w.savedPick=r;return true;}};
 const button=s.w.document.createElement('button');s.w.document.getElementById('confidenceCards').append(button);button.focus();s.w.saveButton=button;
 vm.runInContext('const key=bestSelectionKey(pick);BEST_VISIBLE.set(key,pick);saveButton.dataset.confidenceAdd=key;addConfidencePick(saveButton)',s.context);
 assert.equal(s.w.savedPick.sport,'ncaa');assert.equal(s.w.savedPick.kickoff,s.w.pick.kickoff);assert.equal(s.w.savedPick.updatedAt,s.w.pick.updatedAt);assert.equal(s.w.savedPick.event,'e');assert.equal(s.w.savedPick.market,'spread');assert.equal(s.w.savedPick.line,-3.5);assert.equal(button.getAttribute('aria-pressed'),'true');assert.equal(s.w.document.activeElement,button);
 s.w.pick.updatedAt='2026-09-01T12:00:00Z';s.w.savedPick=null;vm.runInContext('addConfidencePick(saveButton)',s.context);assert.equal(s.w.savedPick,null);assert.equal(button.disabled,true);
});

test('Confidence shortcut stays inside Today despite the document base URL and focuses its heading',t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 const before=s.w.location.href;let shift=null;s.w.scrollBy=(x,y)=>{shift=y;};s.w.document.querySelector('.bt-head').getBoundingClientRect=()=>({bottom:360});s.w.document.getElementById('goingConfidence').getBoundingClientRect=()=>({top:130});vm.runInContext('wireBetting()',s.context);
 s.w.document.getElementById('confidenceJump').click();
 assert.equal(s.w.location.href,before);assert.equal(s.w.document.activeElement.id,'confidenceTitle');
 assert.equal(s.w.document.getElementById('confidenceJump').tagName,'BUTTON');assert.equal(shift,-242);
});

test('current-only player extraction rejects wrong identity, wrong team, future and prior-season rows; QB uses verified starts',()=>{
 const appearance=(date,patch={})=>({date,season:2026,verified_start:true,attempts:30,carries:5,targets:4,pass_yds:280,rush_yds:20,rec_yds:35,receptions:3,pass_tds:2,rush_tds:1,rec_tds:1,atd:1,...patch});
 const c=row(),profile={id:'p',team:'A',position:'QB',games:[appearance('2026-09-20'),appearance('2026-09-27'),appearance('2026-10-04'),appearance('2025-10-01',{season:2025}),appearance('2026-09-28',{verified_start:false})]};
 assert.equal(currentPlayerEvidence({...profile,id:'other'},c,options),null);assert.equal(currentPlayerEvidence({...profile,team:'C'},c,options),null);assert.equal(currentPlayerEvidence(null,c,options),null);
 const e=currentPlayerEvidence(profile,c,options);assert.equal(e.games,2);assert.equal(e.verifiedStarts,2);assert.equal(e.latest,'2026-09-27');assert.equal(e.means.attempts,30);assert.equal(e.source.includes('current season only'),true);
 const old={...profile,games:[appearance('2025-09-27',{season:2025})]};assert.equal(currentPlayerEvidence(old,c,options).games,0);
 const stale={...profile,games:[appearance('2026-08-01')]};const staleEvidence=currentPlayerEvidence(stale,c,options);assert.equal(staleEvidence.games,1);assert.equal(assess(c,{...options,currentRoleEvidence:staleEvidence}).group,'developing');
});

test('every supported player market family uses current-only opportunity and exact-direction production',()=>{
 const profile={id:'p',team:'A',position:'QB',games:[
  {date:'2026-09-20',season:2026,verified_start:true,attempts:30,carries:5,targets:4,pass_yds:280,rush_yds:20,rec_yds:35,receptions:3,pass_tds:2,rush_tds:1,rec_tds:1,atd:1},
  {date:'2026-09-27',season:2026,verified_start:true,attempts:32,carries:5,targets:4,pass_yds:300,rush_yds:22,rec_yds:37,receptions:3,pass_tds:2,rush_tds:1,rec_tds:1,atd:1}
 ]};
 const cases=[['rec_yds',20,'Over'],['receptions',1,'Over'],['rush_yds',5,'Over'],['pass_yds',200,'Over'],['pass_tds',.5,'Over'],['rush_tds',0,'Over'],['rec_tds',0,'Over'],['atd',.5,'Yes']];
 for(const [market,line,side] of cases){const c=row({market,line,side,projMean:line+1,seasonEvidence:{season:2026,current_games:2,historical_games:0,sample_confidence:'moderate'}}),currentRoleEvidence=currentPlayerEvidence(profile,c,options);const e=assess(c,{...options,currentRoleEvidence});assert.equal(e.group,'support',market);assert.ok(e.dimensions.includes('current_production'),market);assert.ok(e.dimensions.includes('current_role'),market);}
});

test('completed current-season NFL and NCAA score context supports game evidence without player-role inputs',()=>{
 for(const sport of ['nfl','ncaa']){
  const games=[{season:2026,sport,home:'B',away:'A',kickoff:'2026-09-27T17:00:00Z',completed:true,homeScore:28,awayScore:10}];
  const c=row({kind:'game',sport,market:'total',side:'Over',line:30,prob:.7,projMean:38,seasonEvidence:null,gameSeasonEvidence:{home_current_games:2,away_current_games:2,home_current_weight:.8,away_current_weight:.8}}),context=currentGameEvidence(games,c,options);
  assert.equal(context.totalContext,38);assert.equal(context.homeGames,1);assert.equal(context.awayGames,1);
  const e=assess(c,{...options,currentGameEvidence:context});assert.equal(e.group,'support',sport);assert.ok(e.dimensions.includes('current_scoring_direction'));assert.ok(e.supports.some(x=>x.includes('current finals')));
  assert.equal(currentGameEvidence(games,c,{...options,resultsAt:'2026-10-01T00:00:00Z'}),null);
  assert.equal(assess(c,{...options,currentGameEvidence:null}).group,'developing','model samples without published completed finals stay developing');
  assert.equal(currentGameEvidence(games.map(g=>({...g,completed:false})),c,options),null);
  assert.equal(currentGameEvidence(games.map(g=>({...g,sport:sport==='nfl'?'ncaa':'nfl'})),c,options),null);
 }
});

test('game support requires a fresh loaded source for the candidate league',()=>{
 const sport='ncaa',games=[{season:2026,sport,home:'B',away:'A',kickoff:'2026-09-27T17:00:00Z',completed:true,homeScore:28,awayScore:10}];
 const c=row({kind:'game',sport,market:'total',side:'Over',line:30,prob:.7,projMean:38,seasonEvidence:null,gameSeasonEvidence:{home_current_games:2,away_current_games:2}});
 const valid=currentGameEvidence(games,c,{...options,resultsAt:at,sourceStatus:'loaded',sourceCheckedAt:at});assert.ok(valid);
 const unavailable=currentGameEvidence(games,c,{...options,resultsAt:at,sourceStatus:'unavailable',sourceCheckedAt:at});
 const stale=currentGameEvidence(games,c,{...options,resultsAt:at,sourceStatus:'loaded',sourceCheckedAt:'2026-10-01T00:00:00Z'});
 const future=currentGameEvidence(games,c,{...options,resultsAt:at,sourceStatus:'loaded',sourceCheckedAt:'2026-10-03T14:00:00Z'});
 for(const context of [unavailable,stale,future]){assert.equal(context,null);const e=assess(c,{...options,currentGameEvidence:context,gameEvidenceIssue:'Current finals source unavailable, stale or future-dated.'});assert.notEqual(e.group,'support');}
});

test('unavailable, stale and future prices remain separate from verified football support',()=>{
 const c=role({projMean:65.5}),currentRoleEvidence={playerId:'p',team:'A',season:2026,position:'WR',games:6,latest:'2026-09-27',verifiedStarts:0,means:{targets:6,rec_yds:70},tdAppearances:0};
 for(const patch of [{updatedAt:'2026-10-03T01:00:00Z'},{updatedAt:'2026-10-03T14:00:00Z'},{book:'',odds:NaN,dec:NaN}]){
  const e=assess({...c,...patch},{...options,currentRoleEvidence});assert.equal(e.group,'support');assert.equal(e.footballSupport,true);assert.ok(e.footballChecks.length===0);assert.equal(e.priceChecks[0].code,'price');
 }
});

test('opposing current and model directions do not become current support',()=>{
 const currentRoleEvidence={playerId:'p',team:'A',season:2026,position:'WR',games:6,latest:'2026-09-27',verifiedStarts:0,means:{targets:6,rec_yds:70},tdAppearances:0};
 const e=assess(role({projMean:50,prob:.3}),{...options,currentRoleEvidence});assert.equal(e.group,'developing');assert.equal(e.footballSupport,false);
});

test('groups order current sample, then evidence freshness, then kickoff without odds or GOING Score',()=>{
 const candidates=[
  row({profileId:'few-fresh',kickoff:'2026-10-04T18:00:00Z',odds:-500,goingScore:99}),
  row({profileId:'many-old',kickoff:'2026-10-04T19:00:00Z',odds:150,goingScore:1}),
  row({profileId:'many-new-late',kickoff:'2026-10-04T20:00:00Z',odds:-110,goingScore:100}),
  row({profileId:'many-new-early',kickoff:'2026-10-04T17:00:00Z',odds:400,goingScore:0})
 ];
 const details={'few-fresh':[3,'2026-09-30'],'many-old':[6,'2026-09-24'],'many-new-late':[6,'2026-09-28'],'many-new-early':[6,'2026-09-28']};
 const out=groups(candidates,c=>{const [games,latest]=details[c.profileId];return {...options,currentRoleEvidence:{playerId:c.profileId,team:'A',season:2026,position:'WR',games,latest,verifiedStarts:0,means:{targets:6,rec_yds:70},tdAppearances:0}};});
 assert.deepEqual(out.support.map(x=>x.candidate.profileId),['many-new-early','many-new-late','many-old','few-fresh']);
});

test('Confidence UI has concise progressive method, football-only reason filtering and useful support-empty actions',t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 vm.runInContext(fs.readFileSync(path.join(root,'shared/football-confidence.js'),'utf8'),s.context);
 const base=role({profileId:'p1',player:'player p1',injury:{stale:true},projMean:65.5}),other=role({profileId:'p2',player:'player p2',profileDate:'2026-08-01',projMean:65.5});
 s.w.fixture=[base,other];s.w.profiles={p1:{id:'p1',team:'A',position:'WR',games:[{date:'2026-09-27',season:2026,verified_start:false,targets:6,rec_yds:70}]},p2:{id:'p2',team:'A',position:'WR',games:[{date:'2026-09-27',season:2026,verified_start:false,targets:6,rec_yds:70}]}};
 vm.runInContext(`BET.history={generated_at:'${at}',season_review:{season:2026},profiles:profiles};BET.sport='nfl';BET.context={generated_at:'${at}'};BET.learning={generated_at:'${at}'};wireBetting();renderGoingConfidence(fixture);`,s.context);
 const d=s.w.document;assert.match(d.querySelector('.confidence-empty').textContent,/Availability evidence is stale/);assert.equal(d.querySelectorAll('.confidence-empty button').length,2);
 assert.match(d.querySelector('.confidence-method summary').textContent,/How GOING Confidence works/);assert.equal(d.querySelector('.confidence-method').open,false);assert.match(d.querySelector('.confidence-method a').textContent,/Read the Confidence method/);
 vm.runInContext("CONFIDENCE_VIEW.nfl='check';renderGoingConfidence(fixture)",s.context);const reason=d.getElementById('confidenceReason');assert.equal(d.getElementById('confidenceReasonWrap').hidden,false);assert.ok([...reason.options].some(x=>x.value==='availability'));assert.ok([...reason.options].some(x=>x.value==='observation'));
 reason.value='availability';reason.dispatchEvent(new s.w.Event('change',{bubbles:true}));assert.equal(d.querySelectorAll('.confidence-card').length,1);assert.equal(d.querySelector('[data-confidence-key] h4').textContent.includes('p1'),true);
});

test('Confidence results loader falls back after API rejection and reuses a successful cache',async t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 const calls=[],payload={schema_version:1,generated_at:at,games:{}};
 s.w.fetch=async url=>{calls.push(url);if(url==='/api/snapshot?file=results.json')throw Error('network');return {ok:true,json:async()=>payload};};
 await vm.runInContext('confidenceLoadResults()',s.context);assert.deepEqual(calls,['/api/snapshot?file=results.json','/data/results.json']);assert.equal(vm.runInContext('CONFIDENCE_RESULTS.generated_at',s.context),at);
 await vm.runInContext('confidenceLoadResults()',s.context);assert.equal(calls.length,2,'successful results cache prevents duplicate fetches');
});

test('Confidence results loader coalesces concurrent requests and retries after total failure',async t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 let calls=0,finish;const payload={schema_version:1,generated_at:at,games:{}};
 s.w.fetch=()=>{calls++;return new Promise(resolve=>{finish=resolve;});};
 const one=vm.runInContext('confidenceLoadResults()',s.context),two=vm.runInContext('confidenceLoadResults()',s.context);await Promise.resolve();assert.equal(calls,1);
 finish({ok:true,json:async()=>payload});await Promise.all([one,two]);assert.equal(vm.runInContext('CONFIDENCE_RESULTS.generated_at',s.context),at);
 const retry=openSource(root,at);t.after(()=>retry.dom.window.close());let failing=0;retry.w.fetch=async url=>{failing++;if(url.startsWith('/api/'))throw Error('network');return {ok:false};};
 await vm.runInContext('confidenceLoadResults()',retry.context);assert.equal(failing,2);assert.equal(vm.runInContext('CONFIDENCE_RESULTS',retry.context),null);
 await vm.runInContext('confidenceLoadResults()',retry.context);assert.equal(failing,4,'a failed load does not poison future retries');
});

test('inconsistent prices stay unvalidated and cannot expose a return as though a valid quote exists',()=>{
 const c=role({dec:9,odds:-110,ev:4});const e=assess(c,options);assert.equal(e.group,'support');assert.equal(e.validPrice,false);assert.equal(e.priceChecks[0].code,'price');const text=card(c,e,{label:'Over 55.5 Receiving yards',key:'x',teamLabel:x=>x,gameKey:'g'});assert.match(text,/No matched price/);assert.doesNotMatch(text,/Push-aware model return/);assert.match(text,/disabled title=/);
});


test('Recent prices filter changes displayed cards only, rejects invalid quotes and stays league-local',t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 vm.runInContext(fs.readFileSync(path.join(root,'shared/football-confidence.js'),'utf8'),s.context);
 s.w.fixture=[role({profileId:'fresh',updatedAt:at}),role({profileId:'stale',updatedAt:'2026-10-03T12:00:00Z'}),role({profileId:'future',updatedAt:'2026-10-03T14:00:00Z'}),role({profileId:'missing',updatedAt:null}),role({profileId:'corrupt',dec:9}),role({profileId:'bookless',book:null})];
 const before=JSON.stringify(s.w.fixture);
 vm.runInContext(`BET.sport='nfl';BET.history={generated_at:'${at}',season_review:{season:2026}};BET.context={generated_at:'${at}'};BET.learning={generated_at:'${at}'};wireBetting();renderGoingConfidence(fixture);`,s.context);
 const d=s.w.document,button=d.getElementById('confidenceRecent');
 assert.equal(button.getAttribute('aria-pressed'),'false');assert.match(d.querySelector('[data-confidence-view="support"]').textContent,/6/);
 button.focus();button.click();assert.equal(d.querySelectorAll('.confidence-card').length,1);assert.match(d.querySelector('.confidence-card').dataset.confidenceKey,/fresh/);
 assert.equal(button.getAttribute('aria-pressed'),'true');assert.equal(d.activeElement,button);assert.match(d.getElementById('confidenceCount').textContent,/1 of 1.*6 total football entries.*within five minutes/);
 assert.match(d.querySelector('[data-confidence-view="support"]').textContent,/6/);assert.equal(JSON.stringify(s.w.fixture),before);
 vm.runInContext("BET.sport='ncaa';renderGoingConfidence([])",s.context);assert.equal(button.getAttribute('aria-pressed'),'false');
 vm.runInContext("BET.sport='nfl';renderGoingConfidence(fixture.slice(1))",s.context);assert.equal(button.getAttribute('aria-pressed'),'true');assert.equal(d.querySelectorAll('.confidence-card').length,0);assert.match(d.getElementById('confidenceCards').textContent,/No recently observed prices.*Freshness does not establish betting value/);
 button.click();assert.equal(d.querySelectorAll('.confidence-card').length,4);assert.equal(button.getAttribute('aria-pressed'),'false');
});
