const test=require('node:test'),assert=require('node:assert/strict');
const {assess,currentPlayerEvidence,currentGameEvidence}=require('../shared/football-confidence.js');
const {VERSION,SCHEMA_VERSION,captureReadiness,validReadinessReceipt,candidateFingerprint,confidenceMatchup}=require('../shared/football-readiness-snapshot.cjs');
const capturedAt='2026-10-05T15:00:00Z',hash='a'.repeat(64),input={sha256:hash,generated_at:'2026-10-05T14:00:00Z'};
const inputs={history:input,context:input,learning:input,results:input,config:input,injury:input,roster:input,nfl_feed:input,ncaa_feed:input};
const profile={id:'player-1',team:'A',position:'RB',games:Array.from({length:3},(_,i)=>({season:2026,date:`2026-09-${String(10+i*5).padStart(2,'0')}`,verified_start:false,attempts:0,carries:12,targets:2,pass_yds:0,rush_yds:70,rec_yds:12,receptions:2,pass_tds:0,rush_tds:1,rec_tds:0,atd:1}))};
const sourceNames={history:'history.json',context:'football_context.json',learning:'season_learning.json',results:'results.json',config:'data.json',injury:'injury_context.json',roster:'players.json',nfl_feed:'nfl_betting.json',ncaa_feed:'ncaa_lines.json'};
const row={kind:'prop',sport:'nfl',home:'A',away:'B',team:'A',profileId:'player-1',player:'Example',event:'game-1',canonicalContract:'game-1|player-1|rush_yds|60.5|Over',market:'rush_yds',side:'Over',line:60.5,odds:-110,dec:1.91,prob:.62,push:0,ev:.1842,n:8,modelFamily:'role',profileDate:'2026-10-04',updatedAt:'2026-10-05T14:58:00Z',kickoff:'2026-10-05T19:00:00Z',projMean:70,seasonEvidence:{season:2026,current_games:3,historical_games:0,current_weight:1,sample_confidence:'medium'},flags:[],provenance:{schema_version:1,model_source_sha256:hash,readiness_assessor_sha256:hash,inputs:Object.fromEntries(Object.entries(inputs).map(([k,v])=>[sourceNames[k],v]))},readiness_inputs:inputs};
const history={generated_at:input.generated_at,profiles:{'player-1':profile},games:{nfl:[]}};
const learning={generated_at:input.generated_at,matchup_signals:[],defensive_weaknesses:[]};
const results={generated_at:input.generated_at,games:{}};
function options(overrides={}){return {capturedAt,season:2026,historyAt:history.generated_at,contextAt:input.generated_at,learningAt:learning.generated_at,resultsAt:results.generated_at,history,results,learning,historyHash:hash,contextHash:hash,learningHash:hash,resultsHash:hash,assessorHash:hash,historyInputAt:input.generated_at,contextInputAt:input.generated_at,learningInputAt:input.generated_at,resultsInputAt:input.generated_at,...overrides};}
function matchingOptions(c){const now=Date.parse(capturedAt),season=2026,role=c.market==='rec_yds'?'RECEIVING':c.market==='rush_yds'?'RUSHING':null,matchup=role?(learning.matchup_signals||[]).find(m=>m.player_id===c.profileId&&m.opponent===(c.team===c.home?c.away:c.home)&&String(m.role||'').endsWith(role)&&Math.abs(Date.parse(m.kickoff)-Date.parse(c.kickoff))<60000)||null:null;return {now,season,contextAt:input.generated_at,learningAt:input.generated_at,historyAt:input.generated_at,matchup,weakness:null,currentRoleEvidence:currentPlayerEvidence(history.profiles[c.profileId],c,{now,season}),currentGameEvidence:null};}
function valid(row,receipt){return validReadinessReceipt(receipt,row,row.provenance,capturedAt);}

test('v2 receipt freezes the exact production assessor evidence without changing the candidate',()=>{
 const before=JSON.stringify(row),receipt=captureReadiness(row,options()),expected=assess(row,matchingOptions(row));
 assert.equal(receipt.schema_version,SCHEMA_VERSION);assert.equal(receipt.version,VERSION);assert.equal(receipt.group,expected.group);assert.equal(receipt.label,expected.label);assert.equal(receipt.why,expected.why);assert.equal(receipt.concern,expected.concern);assert.deepEqual(receipt.football_checks,expected.footballChecks);assert.deepEqual(receipt.price_checks,expected.priceChecks);assert.deepEqual(receipt.facts,expected.facts);assert.equal(receipt.assessor_sha256,hash);assert.equal(receipt.candidate_sha256,candidateFingerprint(row));assert.equal(JSON.stringify(row),before);assert.equal(valid(row,receipt),true);
 assert.equal(valid({...row,prob:row.prob-.01},receipt),false);assert.equal(valid({...row,seasonEvidence:{...row.seasonEvidence,current_games:2}},receipt),false);assert.equal(valid({...row,injury:{stale:true}},receipt),false);
});

test('receipt matcher uses the exact market role, opponent and sub-minute kickoff identity',()=>{
 const candidate={...row,market:'rush_yds'},signal=(role,opponent,kickoff)=>({player_id:'player-1',role,opponent,kickoff,weakness_id:'A|RB_RUSHING'}),signals=[signal('QB_PASSING','B',candidate.kickoff),signal('RB_RUSHING','B','2026-10-05T19:00:30Z'),signal('RB_RUSHING','C',candidate.kickoff)];
 assert.equal(confidenceMatchup({matchup_signals:signals},candidate),signals[1]);assert.equal(confidenceMatchup({matchup_signals:signals}, {...candidate,market:'receptions'}),null);
});

test('current team facts require fresh published finals and a fresh loaded league source',()=>{
 const game={...row,kind:'game',market:'total',side:'Over',line:43,home:'A',away:'B',team:null,profileId:null,canonicalContract:'game-1|total|Over|43',gameSeasonEvidence:{home_current_games:1,away_current_games:1},seasonEvidence:null,prob:.6,n:12,projMean:47};
 const finals={generated_at:'2026-10-05T14:00:00Z',sources:{nfl:{status:'loaded',checked_at:'2026-10-05T14:00:00Z'},ncaa:{status:'failed',checked_at:'2026-10-05T14:00:00Z'}},games:{one:{sport:'nfl',home:'A',away:'X',kickoff:'2026-09-10T20:00:00Z',homeScore:30,awayScore:17},two:{sport:'nfl',home:'B',away:'Y',kickoff:'2026-09-15T20:00:00Z',homeScore:24,awayScore:17},partial:{sport:'nfl',home:'A',away:'B',kickoff:'2026-09-20T20:00:00Z',homeScore:31,awayScore:null},empty:null}};
 const receipt=captureReadiness(game,options({results:finals,resultsAt:finals.generated_at,resultsInputAt:finals.generated_at}));
 assert.equal(receipt.group,'support');assert.ok(receipt.facts.some(([k,v])=>k==='Current-only scoring context'&&Number(v)>43));assert.ok(receipt.facts.some(([k,v])=>k==='Current team evidence source'&&v.includes('Published results.json')));
 const stale=captureReadiness(game,options({results:finals,resultsAt:'2026-10-03T13:00:00Z',resultsInputAt:'2026-10-03T13:00:00Z'}));assert.equal(stale.group,'developing');
 const staleLeague={...finals,sources:{...finals.sources,nfl:{status:'loaded',checked_at:'2026-10-03T13:00:00Z'}}};
 const staleLeagueReceipt=captureReadiness(game,options({results:staleLeague}));assert.equal(staleLeagueReceipt.group,'developing');assert.ok(!staleLeagueReceipt.facts.some(([k])=>k==='Current-only scoring context'));assert.ok(staleLeagueReceipt.concerns.includes('Final-results source confirmation is missing, stale or future-dated.'));
 const retained={...finals,sources:{...finals.sources,nfl:{status:'retained',checked_at:'2026-10-05T14:00:00Z'}}};
 const retainedReceipt=captureReadiness(game,options({results:retained}));assert.equal(retainedReceipt.group,'developing');assert.ok(retainedReceipt.concerns.some(x=>x==='The current finals feed is unavailable; retained results may omit recent games.'));
 const futureCheck={...finals,sources:{...finals.sources,nfl:{status:'loaded',checked_at:'2026-10-05T16:00:00Z'}}};
 const futureReceipt=captureReadiness(game,options({results:futureCheck}));assert.equal(futureReceipt.group,'developing');assert.ok(!futureReceipt.facts.some(([k])=>k==='Current-only scoring context'));assert.ok(futureReceipt.concerns.includes('Final-results source confirmation is missing, stale or future-dated.'));
 const wrongSport=captureReadiness({...game,sport:'ncaa'},options({results:finals}));assert.equal(wrongSport.group,'developing');assert.ok(wrongSport.concerns.some(x=>x==='The current finals feed is unavailable; retained results may omit recent games.'));
});

test('invalid, changed or legacy receipts are omitted instead of being reconstructed',()=>{
 const receipt=captureReadiness(row,options());
 assert.equal(valid(row,{...receipt,version:'football-readiness-v1'}),false);
 assert.equal(valid({...row,line:61},receipt),false);
 assert.equal(valid(row,{...receipt,captured_at:'2026-10-05T15:01:00Z'}),false);
 assert.equal(valid(row,{...receipt,assessor_sha256:'b'.repeat(64)}),false);
 assert.equal(captureReadiness(row,options({historyAt:'2026-10-06T12:00:00Z'})),null);
 assert.equal(captureReadiness(row,options({capturedAt:'2026-10-05T20:00:00Z'})),null);
});
