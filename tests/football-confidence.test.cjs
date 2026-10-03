'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {assess,groups,card}=require('../shared/football-confidence.js');
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
 assert.match(text,/Current support attached/);assert.match(text,/Model estimate · not Confidence/);assert.match(text,/52\.4% win-only break-even/);assert.doesNotMatch(text,/High confidence|60\.0% Confidence|best bet/i);
});
test('wrong direction, market, season, historical role or unavailable source never qualifies',()=>{
 for(const c of [role({side:'Under'}),role({market:'rush_yds'}),role({sport:'ncaa',kind:'game'}),role({evidence:{opportunity:{season:2025,last_game:'2026-09-27',adjustedShare:.7,average:.5}}})])assert.notEqual(assess(c,options).group,'support');
 assert.notEqual(assess(role(),{...options,contextAt:'2026-09-01'}).group,'support');
 assert.notEqual(assess(role({seasonEvidence:{season:2025,current_games:6,historical_games:6}}),options).group,'support');
});
test('small player sample, stale quote, model check and uncertain injury lower readiness',()=>{
 assert.equal(assess(role({seasonEvidence:{season:2026,current_games:2,historical_games:10,sample_confidence:'low'}}),options).group,'developing');
 for(const c of [role({updatedAt:'2026-10-03T01:00:00Z'}),role({flags:[{id:'check'}]}),role({injury:{stale:true}}),role({updatedAt:'2026-10-03T14:00:00Z'}),role({profileDate:'2026-10-05'}),role({profileDate:null})])assert.equal(assess(c,options).group,'check');
 assert.equal(assess(role({injury:{roleBoost:true}}),options).group,'developing');
 assert.equal(assess(role(),{...options,historyAt:'2026-09-30'}).group,'check');
});
test('NCAA exposes current versus older policy evidence without pretending scoring is matchup support',()=>{
 const c=row({kind:'game',sport:'ncaa',market:'total',seasonEvidence:null,gameSeasonEvidence:{home_current_games:2,away_current_games:3,home_current_weight:.8,away_current_weight:.8,policy:'80/20 existing unvalidated policy'}});
 const e=assess(c,options);assert.equal(e.group,'developing');assert.ok(e.supports[0].includes('3 current-season games'));assert.ok(e.concerns.some(x=>x.includes('personnel')));assert.ok(e.facts.some(([k,v])=>k==='Weighting method'&&v.includes('80/20')));
 assert.equal(assess({...c,kind:'prop'},options).eligible,false);
});
test('defensive support requires the exact player/opponent/role/weakness/market/direction',()=>{
 const c=row();assert.equal(assess(c,matchOptions()).group,'support');
 assert.notEqual(assess({...c,market:'rush_yds'},matchOptions()).group,'support');
 for(const patch of [{player_id:'other'},{opponent:'C'},{weakness_id:'other'},{role:'RB_RUSHING'},{active_signal:false},{lineage:[]},{kickoff:'2026-10-04T23:00:00Z'}]){
  const opts=matchOptions();opts.matchup={...opts.matchup,...patch};assert.notEqual(assess(c,opts).group,'support');
 }
 const opts=matchOptions();opts.weakness.current.value=-1;assert.notEqual(assess(c,opts).group,'support');assert.equal(assess({...c,side:'Under'},opts).group,'support');
});
test('historical charting is a concern and is not made current by the latest game date',()=>{
 const c=row({evidence:{chartingAt:'2026-01-04',playerObservedAt:'2026-09-27'},flags:[{id:'demand',family:'role'},{id:'pace',family:'role'}]});const e=assess(c,options);assert.equal(e.group,'developing');assert.ok(e.concerns.some(x=>x.includes('Charted participation is historical')));
});
test('groups preserve input order and calculations, expose all entries and safely escape source text',()=>{
 const rows=[role({profileId:'first',prob:.5}),role({profileId:'second',prob:.9})],before=JSON.stringify(rows),g=groups(rows,options);
 assert.deepEqual(g.support.map(x=>x.candidate.profileId),['first','second']);assert.equal(JSON.stringify(rows),before);
 const e=assess(row({player:'<script>',book:'<img>'}),options),text=card(row({book:'<img>'}),e,{label:'<script>alert(1)</script>',key:'" x',teamLabel:x=>x,gameKey:'g'});assert.ok(text.includes('&lt;script&gt;'));assert.ok(text.includes('&lt;img&gt;'));assert.ok(!text.includes('<script>'));
 assert.equal(groups(Array.from({length:27},(_,i)=>role({profileId:String(i)})),options).support.length,27);
});
test('January retains the previous football season rather than misclassifying current role evidence',()=>{
 const jan='2027-01-02T12:00:00Z',opts={...options,now:Date.parse(jan),historyAt:jan,contextAt:jan,learningAt:jan};
 const c=role({profileDate:'2026-12-27',kickoff:'2027-01-03T17:00:00Z',updatedAt:jan,evidence:{opportunity:{season:2026,last_game:'2026-12-27',adjustedShare:.7,average:.5}}});assert.equal(assess(c,opts).group,'support');
});
test('Confidence presentation preserves frozen Champion/generator/C1/C2 hashes',t=>{
 const root=path.resolve(__dirname,'..'),s=openSource(root,at);t.after(()=>s.dom.window.close());
 const registry=require('../research/today-ranking/experiment-v1.json');
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
 vm.runInContext("BET.sport='ncaa';renderGoingConfidence([])",s.context);assert.equal(d.querySelectorAll('.confidence-card').length,0);assert.match(d.getElementById('confidenceStatus').textContent,/No model-supported candidates/);assert.match(d.querySelector('.confidence-kicker').textContent,/NCAA/);
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
