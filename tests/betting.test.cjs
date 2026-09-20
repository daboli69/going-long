const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
function setup(t){
  t.mock.timers.enable({apis:['Date'],now:Date.parse('2026-09-09T12:00:00Z')});
  const dom=new JSDOM(html,{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
  const BrowserDate=dom.window.Date;
  dom.window.Date=class extends BrowserDate{constructor(...args){super(...(args.length?args:[Date.now()]));}static now(){return Date.now();}};
  t.after(()=>dom.window.close());
  dom.window.localStorage.setItem('goinglong.gateway.mode','fantasy');
  dom.window.requestAnimationFrame=cb=>dom.window.setTimeout(cb,0);
  dom.window.HTMLElement.prototype.scrollIntoView=function(){};
  const context=dom.getInternalVMContext();
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../shared/going-score.js'),'utf8'),context);
  for(const script of dom.window.document.querySelectorAll('script:not([src])')){
    vm.runInContext(script.textContent.replace(/\nboot\(\);/,'\n'),context);
  }
  vm.runInContext(`globalThis.api={bestPriceCandidates,rankBestPlays,filterBestPlays,bestBookKey,bestPlayCard,renderBestPlays,BET,americanToDecimal,normalCDF,poissonCDF,lognormalCDF,
    propProbabilities,computePropRow,evPercent,kellyFraction,quoteState,propsFromRealData,
    parsePropsPaste,parseGamesPaste,renderPropsTable,renderBetting,wireBetting,gameQuotes,
    mergePartialLive,footballNotes,footballOpportunity,footballRoleSignal,footballOpportunityMarkup,roleValidationMarkup,gameValidationMarkup,defensiveMemoryMarkup,defensiveMatchup,bestConfidence,globalSearchItems,SIGNAL,signalFlags,signalReference,signalGrade,signalSummary,signalTrack,signalPriceMove,signalBuild,signalBuildSettlement,signalCandidates,footballWeek,inCurrentFootballWeek,updateBetFilters,firstTdVigComparison,periodQuoteResult,activeGameQuote,bestGameLines,projectionBoard,scoreAtdAnchor,goingScoreCandidates,renderGoingScore,normalMarket,buildProfileIndex,attachProjection,loadBettingData,refreshLiveOdds,gamesFromParlay,opportunityPool,propOfferIdentity,consolidatePropOffers,persistBettingView};`,context);
  dom.window.api.BET.liveLoaded={nfl:true,ncaa:true};
  return {api:dom.window.api,w:dom.window,context};
}
const close=(actual,expected,tol=1e-7)=>assert.ok(Math.abs(actual-expected)<tol,`${actual} != ${expected}`);
const future=()=>new Date(Date.now()+86400000).toISOString();

test('Price flags use multiple distinct competing books, not duplicate quotes',t=>{
  const {api:a}=setup(t),c={book:'A',dec:2.2,prob:.5,ev:.1};
  assert.ok(!a.signalFlags(c,[{book:'B',dec:2},{book:'B',dec:2}],{}).some(f=>f.id==='price'));
  assert.ok(a.signalFlags(c,[{book:'B',dec:2},{book:'C',dec:2}],{}).some(f=>f.id==='price'));
  const r=a.signalReference(-110,-110,.1);close(r.win,.45);close(r.push,.1);close(r.loss,.45);
});

test('Football role flags need current charting and measured denominators',t=>{
  const {api:a}=setup(t),now=Date.now(),date=new Date(now-86400000).toISOString();
  const c={kind:'prop',team:'A',opp:'B',profileId:'p',market:'rec_yds',side:'Over',teamSpread:4};
  const h={features:{nfl:{players:{'A|p':{last_game:date,last_participation_game:date,pass_snaps_proxy:80,targets_per_pass_snap_proxy:.3,pass_snap_participation_proxy:.6,targets:35}},teams:{A:{games:8,participation_coverage:.9}}}}};
  assert.ok(a.signalFlags(c,[],h,now).some(f=>f.id==='demand'));
  h.features.nfl.players['A|p'].last_participation_game='2025-01-01';
  assert.ok(!a.signalFlags(c,[],h,now).some(f=>f.id==='demand'));
  assert.ok(!a.signalFlags({...c,side:'Under'},[],h,now).some(f=>f.id==='chase'));
});

test('Role validation describes the chronological result without promoting it',t=>{
 const {api:a}=setup(t),markup=a.roleValidationMarkup({season:2025,validation_scope:'chronological_next_game_diagnostic',projection_adjustment_decision:'do_not_promote',groups:[
  {name:'all_eligible',players_games:2160,mean_yards_vs_baseline:.1648},
  {name:'role_ahead_of_results',players_games:191,mean_yards_vs_baseline:4.2846,mean_yards_difference_from_all:4.1198,yards_difference_from_all_range_95:[-.5122,9.4737],yards_baseline_mae:25.0916,yards_role_adjusted_mae:25.5561}
 ]});
 assert.match(markup,/191 future player-games/);assert.match(markup,/\+4\.3 receiving yards/);assert.match(markup,/\+0\.2 yards/);
 assert.match(markup,/\+4\.1 yards compared/);assert.match(markup,/-0\.5 to \+9\.5 yards/);assert.match(markup,/includes no difference/);
 assert.match(markup,/error rose from 25\.1 to 25\.6 yards/);assert.match(markup,/not used in projections/);
 assert.match(markup,/remains experimental/);assert.match(markup,/does not change projections or suggested bets/);
 assert.doesNotMatch(markup,/proven|win rate of|lift/i);
});

test('Game validation rejects an opponent adjustment when uncertainty includes no total improvement',t=>{
 const {api:a}=setup(t),markup=a.gameValidationMarkup({validation_scope:'chronological_week_ahead_score_diagnostic',games:768,margin_error_points:13.599,total_error_points:13.624,opponent_adjusted:{margin_error_points:13.212,total_error_points:13.587,margin_improvement_range_95:[.011,.763],total_improvement_range_95:[-.239,.293],decision:'do_not_promote'}});
 assert.match(markup,/768 future games/);assert.match(markup,/13\.6 to 13\.2 points/);assert.match(markup,/-0\.2 to \+0\.3 points/);
 assert.match(markup,/not used in live projections/);assert.match(markup,/cannot claim betting profit/);
});

test('Defensive memory is usage-matched, lineage-backed and not promoted while uncertain',t=>{
 const {api:a}=setup(t),kickoff=future();a.BET.learning={completeness:{nfl:{status:'FRESH',actually_ingested:17,expected_completed:17},ncaa:{status:'FRESH',actually_ingested:115,expected_completed:115,supported_universe:'FBS regular-season games only'}},unsupported_granularity:['WR slot/outside'],defensive_weaknesses:[{id:'B|TE_RECEIVING',defense:'B',historical_weakness:'TE_RECEIVING',current_status:'uncertain',confidence:'low',historical:{season:2025,value:1.2},current:{season:2026,value:-.2,sample:8},weighted_estimate:.9,weights:{historical_weight:.8,current_weight:.2},opponent_adjustment:'same player comparison'}],matchup_signals:[{player_id:'p',player:'Player',team:'A',opponent:'B',kickoff,role:'TE_RECEIVING',status:'uncertain',confidence:'low',active_signal:false,usage:{opportunities:5,share:.2},weakness_id:'B|TE_RECEIVING',plain_language:'MATCHUP CONTEXT',lineage:['prediction','weakness','raw']} ]};
 const matchup=a.defensiveMatchup({kind:'prop',profileId:'p',team:'A',home:'B',away:'A',kickoff});assert.equal(matchup.status,'uncertain');assert.equal(matchup.active_signal,false);
 const markup=a.defensiveMemoryMarkup();assert.match(markup,/0 active matchup edges/);assert.match(markup,/UNCERTAIN — WATCH/);assert.match(markup,/FBS regular-season games only/);assert.match(markup,/prediction → weakness → raw/);
});

test('Global search exposes direct current player, game and market destinations',t=>{
 const {api:a}=setup(t);a.BET.props=[{player:'Example TE',team:'A',market:'rec_yds',kickoff:future()}];a.BET.games=[{home:'B',away:'A',homeCode:'B',awayCode:'A',sport:'nfl',kickoff:future()}];
 const items=a.globalSearchItems();assert.ok(items.some(x=>x.type==='Player'&&x.label==='Example TE'&&x.tab==='props'));assert.ok(items.some(x=>x.type==='Game'&&x.tab==='games'));assert.ok(items.some(x=>x.type==='Market'&&x.label==='Receiving yards'));
});

test('Pass-snap role separates above-average usage from unrewarded results',t=>{
  const {api:a}=setup(t),scope={teams:{A:{charted_dropbacks:120}}},base={team:'A',position:'WR',share_type:'passing_snap_proxy',position_average:.55,pass_snaps:120,charting_coverage:.9,catch_model_targets:25,catches_short:1,scope};
  let signal=a.footballRoleSignal(base);assert.equal(signal.status,'above_average_role');assert.equal(signal.unrewarded,false);
  signal=a.footballRoleSignal({...base,catches_short:3});assert.equal(signal.status,'role_ahead_of_results');assert.equal(signal.unrewarded,true);
  signal=a.footballRoleSignal({...base,pass_snaps:45,catches_short:3});assert.equal(signal.eligible,false);assert.equal(signal.above_average,false);
  signal=a.footballRoleSignal({...base,share_type:'offensive_snap_share',catches_short:3});assert.equal(signal.eligible,false);
});

test('Settlement uses exact game and player date; missing data is never a zero',t=>{
  const {api:a}=setup(t),kickoff='2026-09-10T00:20:00Z',now=Date.parse('2026-09-11T12:00:00Z');
  const r={kind:'prop',sport:'nfl',home:'A',away:'B',profileId:'p',market:'rec_yds',side:'Over',line:50,kickoff};
  const results={games:{g:{sport:'nfl',home:'A',away:'B',kickoff,homeScore:20,awayScore:10}},players:{'p|2026-09-09':{rec_yds:50}}};
  assert.equal(a.signalGrade(r,results,now).status,'refund');
  assert.equal(a.signalGrade({...r,line:49.5},results,now).status,'win');
  assert.equal(a.signalGrade({...r,profileId:'missing'},results,now),null);
  assert.equal(a.signalGrade({...r,market:'first_td'},results,now),null);
  assert.equal(a.signalGrade({...r,market:'rec_yds_1h'},results,now),null);
  assert.equal(a.signalGrade(r,results,Date.parse(kickoff)-1),null);
  assert.equal(a.signalGrade({...r,kind:'game',market:'spread',side:'Away',line:-10.5},results,now).status,'win');
});

test('Prospective log stays frozen and ignores entries after kickoff',t=>{
  const {api:a}=setup(t),now=Date.now(),r={key:'one',event:'event',book:'A',kickoff:future(),updatedAt:new Date(now-1000).toISOString(),flags:[],families:[],dec:2,prob:.6,push:0};
  a.signalTrack([r],now);a.signalTrack([{...r,dec:3,prob:.9}],now+1000);
  assert.equal(a.SIGNAL.ledger.records.one.dec,2);assert.equal(a.SIGNAL.ledger.records.one.prob,.6);
  a.signalTrack([{...r,key:'late',kickoff:new Date(now-1).toISOString()}],now);
  assert.equal(a.SIGNAL.ledger.records.late,undefined);
});

test('Accuracy uses only automatic prospective records and never promotes calibration',t=>{
  const {api:a}=setup(t),r={event:'e',signalVersion:'football-signals-2',loggedAt:'2026-09-09',kickoff:'2026-09-10',prob:.8,push:0,reference:{win:.5,push:0,loss:.5},settlement:{status:'win',method:'public result'}};
  const s=a.signalSummary([r,{...r,imported:true},{...r,settlement:{status:'loss',method:'manual'}},{...r,loggedAt:'2026-09-11'}]);
  assert.equal(s.n,1);assert.equal(s.games,1);close(s.modelError,.08);close(s.bookError,.5);assert.equal(s.status,'Early recorded results');
  assert.equal(a.signalSummary([]).modelError,null);
});

test('Closing comparison distinguishes a late sample from an earlier observation',t=>{
  const {api:a}=setup(t),r={dec:2.2,kickoff:'2026-09-10T20:00:00Z',closing:{dec:2,at:'2026-09-10T19:55:00Z'}};
  close(a.signalPriceMove(r).returnChange,.1);assert.equal(a.signalPriceMove(r).nearKickoff,true);
  r.closing.at='2026-09-10T16:00:00Z';assert.equal(a.signalPriceMove(r).nearKickoff,false);
});

test('Two-leg ideas reject same-game and cross-book combinations and price refunds correctly',t=>{
  const {api:a}=setup(t),r={key:'a',event:'one',book:'A',prob:.6,push:0,dec:2,ev:.2,kickoff:future(),flags:[{id:'gap'}]};
  assert.equal(a.signalBuild([r,{...r,key:'b'}]),null);
  assert.equal(a.signalBuild([r,{...r,key:'b',event:'two',book:'B'}]),null);
  assert.equal(a.signalBuild([{...r,market:'first_td'},{...r,key:'b',event:'two',market:'first_td'}]),null);
  assert.equal(a.signalBuild([{...r,flags:[{id:'check'}]},{...r,key:'b',event:'two',flags:[{id:'check'}]}]),null);
  const b=a.signalBuild([r,{...r,key:'b',event:'two'}]);close(b.prob,.36);close(b.dec,4);
  const result=a.signalBuildSettlement({keys:['a','b'],legs:[{dec:2.5},{dec:3}]},{a:{dec:2,settlement:{status:'win'}},b:{dec:3,settlement:{status:'void'}}});
  close(result.returnPerDollar,2.5);
});
test('Football week includes Monday night in Eastern time and rolls over Tuesday, including DST',t=>{
  const {api:a}=setup(t),now=Date.parse('2026-09-11T16:00:00Z');
  assert.equal(a.footballWeek(now).start,'2026-09-08');
  assert.ok(a.inCurrentFootballWeek('2026-09-15T03:59:00Z',now));
  assert.ok(!a.inCurrentFootballWeek('2026-09-15T04:00:00Z',now));
  assert.ok(!a.inCurrentFootballWeek('2026-09-08T03:59:00Z',now));
  assert.ok(!a.inCurrentFootballWeek(null,now));
  const winter=Date.parse('2026-11-04T16:00:00Z');
  assert.ok(!a.inCurrentFootballWeek('2026-11-03T04:59:00Z',winter));
  assert.ok(a.inCurrentFootballWeek('2026-11-03T05:00:00Z',winter));
});
test('Matchup filter and prop cards exclude future weeks and clear an obsolete selection',async t=>{
  const {api:a,w}=setup(t),kickoff=future(),later=new Date(Date.now()+14*86400000).toISOString();
  a.BET.history={team_names:{Home:'A',Current:'B',Future:'C'},games:{nfl:[{home:'A',away:'B',kickoff},{home:'A',away:'C',kickoff:later}]}};
  a.BET.props=[{id:'current',player:'Current Player',market:'atd',homeName:'Home',awayName:'Current',kickoff,source:'manual'},
    {id:'later',player:'Future Player',market:'atd',homeName:'Home',awayName:'Future',kickoff:later,source:'manual'}];
  a.BET.matchup='C @ A';a.updateBetFilters();
  assert.equal(a.BET.matchup,'ALL');
  const options=w.document.getElementById('btMatchup').textContent;
  assert.match(options,/B @ A/);assert.doesNotMatch(options,/C @ A/);
  await a.renderPropsTable();
  assert.equal(w.document.querySelectorAll('#btPropsTable .bt-row').length,1);
  assert.match(w.document.getElementById('btPropsTable').textContent,/Current Player/);
});
test('First TD uses game-level Bernoulli probability and book-specific conditional vig',t=>{
  const {api:a}=setup(t),kickoff=future(),updatedAt=new Date().toISOString();
  a.BET.history={profiles:{p:{id:'p',name:'Player One',team:'A',position:'RB',stats:{}}},derivatives:{first_td:{g:{home:'A',away:'B',kickoff,outcomes:{p:{probability:.2,fair_odds:400}}}}}};
  const p=a.attachProjection({player:'Player One',eventId:'g',market:'first_td',eventTeams:['A','B'],kickoff,updatedAt,source:'parlay',bookKey:'book',overOdds:500},a.buildProfileIndex(a.BET.history));
  close(a.computePropRow(p).prob,.2);close(a.computePropRow(p).ev,.2);assert.equal(p.model.fair_odds,400);
  a.BET.props=[p,{...p,profileId:'other',player:'Other Player',model:{probability:.1},overOdds:900}];
  a.firstTdVigComparison();close(p.bookConditionalProb,(1/6)/(1/6+1/10));close(p.listedModelMass,.3);
  close(a.computePropRow(p).ev,.2);
});
test('Period pricing matches kickoff and distinguishes pregame, in-play and three-way draws',t=>{
  const {api:a}=setup(t),kickoff=future();
  a.BET.history={team_names:{Home:'A',Away:'B'},games:{nfl:[{home:'A',away:'B',kickoff,period_models:{'1H':{margin_mean:0,margin_sd:7,total_mean:22,total_sd:9}}}]}};
  const q={home_team:'Home',away_team:'Away',kickoff,updatedAt:new Date().toISOString(),inPlay:false,period_key:'1H',market:'h2h',side:'home',price:100};
  const two=a.periodQuoteResult(q);assert.ok(two.push>0);assert.ok(Number.isFinite(two.ev));
  const three=a.periodQuoteResult({...q,threeWay:true});assert.equal(three.push,0);assert.ok(three.ev<two.ev);
  assert.equal(a.periodQuoteResult({...q,inPlay:true}).ev,null);
  assert.equal(a.periodQuoteResult({...q,kickoff:'2099-01-01'}).ev,null);
});
test('Best game lines ignore blank and stale books and compare the same betting side',t=>{
  const {api:a}=setup(t),base={source:'parlay',kickoff:future(),updatedAt:new Date().toISOString(),spread:-3,total:45,homeSpreadOdds:-110,overOdds:-110,mlHome:-150};
  const best=a.bestGameLines([{...base,book:'A'},{...base,book:'B',spread:-2.5,total:44,mlHome:-130},{...base,book:'stale',spread:3,total:40,mlHome:200,updatedAt:'2020-01-01'}]);
  assert.equal(best.spread.book,'B');assert.equal(best.total.book,'B');assert.equal(best.ml.book,'B');
  assert.ok(!a.activeGameQuote({source:'manual',kickoff:future(),spread:3}));
  assert.ok(!a.activeGameQuote({...base,marketTimes:{spreads:'2020-01-01',totals:'2020-01-01',h2h:'2020-01-01'}}));
});
test('Projection explorer includes unquoted players with correct matchup and no invented EV',t=>{
  const {api:a}=setup(t);
  a.BET.history={profiles:{p:{id:'p',name:'Unquoted Player',team:'BUF',stats:{rec_yds:{mean:60,sd:10,status:'ready'}}}},team_names:{'Buffalo Bills':'BUF','Miami Dolphins':'MIA'}};
  a.BET.games=[{sport:'nfl',home:'Buffalo Bills',away:'Miami Dolphins',homeCode:'BUF',awayCode:'MIA',kickoff:future()}];
  const rows=a.projectionBoard();assert.equal(rows.length,1);assert.equal(rows[0].projMean,60);assert.equal(rows[0].opp,'MIA');
  assert.equal(a.computePropRow(rows[0]).ev,null);assert.equal(rows[0].line,null);
});
test('Pressure proxy scales QB distributions without mutating history or pricing unsupported first TD',t=>{
  const {api:a}=setup(t);
  const model={family:'lognormal',status:'ready',mean:200,sd:40,mu_log:5,sigma_log:.2,n:12,nonpositive:[]};
  a.BET.history={profiles:{p:{id:'p',name:'Test QB',team:'A',position:'QB',stats:{pass_yds:model}}},features:{pressure_matchups:{'A|B':{status:'proxy',pass_scale:.9,scramble_yards_delta:2}}}};
  const index=a.buildProfileIndex(a.BET.history);
  const p=a.attachProjection({player:'Test QB',market:'pass_yds',eventTeams:['A','B']},index);
  close(p.projMean,180);close(p.model.mu_log,5+Math.log(.9));close(model.mean,200);
  const first=a.attachProjection({player:'Test QB',market:'first_td',eventTeams:['A','B']},index);
  assert.equal(a.propProbabilities(first),null);assert.match(first.matchStatus,/unavailable/);
});
test('American odds and push-aware EV/Kelly',t=>{
  const {api:a}=setup(t);
  close(a.americanToDecimal(-110),1+100/110); assert.equal(a.americanToDecimal(null),null);
  assert.equal(a.americanToDecimal(-99),null);assert.equal(a.americanToDecimal(Infinity),null);
  close(a.evPercent(.5,2,.1),.1);close(a.kellyFraction(.5,2,.1,1,1),1/9);
  assert.equal(a.kellyFraction(.9,2,0),.02);assert.equal(a.kellyFraction(.3,2),0);
  assert.equal(a.kellyFraction(0,2,1),0);
});
test('Poisson agrees with reference values including large lambda',t=>{
  const {api:a}=setup(t);
  close(a.poissonCDF(0,.7),Math.exp(-.7));
  close(a.poissonCDF(4,3),.8152632445237722,1e-12);
  close(a.poissonCDF(800,800),.5094016579999424,1e-10);
  assert.equal(a.poissonCDF(0,0),1);assert.equal(a.poissonCDF(-1,0),0);
  assert.equal(a.poissonCDF(2,-1),null);
});
test('Integer and half lines partition win/loss/push correctly',t=>{
  const {api:a}=setup(t),base={market:'receptions',manual:true,projMean:3};
  const integer=a.propProbabilities({...base,line:3}), half=a.propProbabilities({...base,line:3.5});
  close(integer.push,Math.exp(-3)*3**3/6,1e-12);
  close(integer.over+integer.under+integer.push,1);
  close(half.push,0);close(half.over,integer.over);
  close(a.propProbabilities({market:'atd',manual:true,projMean:.7}).over,1-Math.exp(-.7));
  close(a.propProbabilities({market:'atd',line:1.5,manual:true,projMean:.7}).over,1-Math.exp(-.7)*(1+.7));
});
test('Lognormal handles positive, negative and zero mass',t=>{
  const {api:a}=setup(t);
  close(a.lognormalCDF(100,{mu_log:Math.log(100),sigma_log:.4}),.5);
  const model={family:'lognormal',status:'ready',n:5,nonpositive:[-2,0],positive_weight:.6,mu_log:Math.log(20),sigma_log:.2};
  close(a.lognormalCDF(0,model),.4);close(a.lognormalCDF(-1,model),.2);
  const p=a.propProbabilities({market:'rush_yds',line:0,model});
  close(p.push,.2);close(p.over+p.under+p.push,1);
  assert.equal(a.propProbabilities({market:'pass_yds',manual:true,line:100,projMean:200,projSd:null}),null);
});
test('Quotes preserve book, event, line and Under-only markets',async t=>{
  const {api:a}=setup(t);
  a.BET.history={profiles:{p:{id:'p',name:'Josh Allen',team:'BUF',last_game:'2025-12-01',stats:{pass_yds:{family:'lognormal',status:'ready',n:12,mean:250,sd:50,mu_log:5.5,sigma_log:.2}}}},team_names:{Buffalo:'BUF',Miami:'MIA'}};
  const quote=(line,name,price)=>({description:'Josh Allen',point:line,name,price});
  const event={id:'e',home_team:'Buffalo',away_team:'Miami',commence_time:future(),bookmakers:[
    {key:'a',title:'Book A',markets:[{key:'player_pass_yds',outcomes:[quote(249.5,'Over',-110),quote(249.5,'Under',-105),quote(259.5,'Under',120)]}]},
    {key:'b',title:'Book B',markets:[{key:'player_pass_yds',outcomes:[quote(249.5,'Over',115)]}]}
  ]};
  const result=await a.propsFromRealData({props_raw:[event,{...event,id:'other'}]});
  assert.equal(result.length,6);
  const under=result.find(p=>p.line===259.5);assert.equal(under.overOdds,null);assert.equal(under.underOdds,120);
  assert.equal(result[0].projMean,250);assert.equal(result[0].team,'BUF');
});
test('Unmatched and ambiguous players stay unpriced',async t=>{
  const {api:a}=setup(t);
  a.BET.history={profiles:{a:{name:'John Smith',id:'a'},b:{name:'John Smith',id:'b'}}};
  const p=a.attachProjection({player:'John Smith',market:'receptions'},a.buildProfileIndex(a.BET.history));
  assert.equal(p.matchStatus,'Ambiguous name');assert.equal(a.computePropRow(p).ev,null);
  assert.equal(a.computePropRow({source:'manual',market:'atd',model:null,overOdds:200}).prob,null);
});
test('Stale, started and invalid quotes cannot produce a recommendation',t=>{
  const {api:a}=setup(t),p={source:'nightly',kickoff:future(),updatedAt:new Date(Date.now()-2*86400000).toISOString(),manual:true,projMean:1,market:'atd',overOdds:200};
  assert.equal(a.computePropRow(p).ev,null); // manual projection cannot freshen a stale quote
  assert.equal(a.quoteState({...p,updatedAt:new Date().toISOString(),kickoff:'garbage'}),'Started / invalid kickoff');
  assert.equal(a.quoteState({...p,updatedAt:new Date().toISOString(),kickoff:new Date(0).toISOString()}),'Started / invalid kickoff');
});
test('Manual imports validate fields and use automatic projections when omitted',t=>{
  const {api:a}=setup(t);
  assert.equal(a.parsePropsPaste('Unknown, BUF, MIA, nonsense, 1, -110').length,0);
  assert.equal(a.parsePropsPaste('Josh Allen, BUF, MIA, pass_yds, , -110').length,0);
  const p=a.parsePropsPaste('Josh Allen, BUF, MIA, pass_yds, 249.5, -110, -110, 260, 40')[0];
  assert.ok(a.computePropRow(p).prob>0);assert.ok(Number.isFinite(a.computePropRow(p).ev));
});
test('Routing hides inactive views and scopes Settings to draft',t=>{
  const {w}=setup(t);
  const click=name=>w.document.querySelector(`#glNav [data-view="${name}"]`).click();
  click('trade');assert.equal(w.document.getElementById('view-betting').hidden,true);
  click('settings');assert.equal(w.document.getElementById('view-draft').hidden,false);
  assert.equal(w.document.querySelector('#view-betting details').open,false);
  click('betting');assert.equal(w.document.getElementById('clockBar').hidden,true);
  assert.equal(w.document.querySelectorAll('#glNav [aria-current]').length,1);
});

test('Sportsbook prop offers collapse to one contract with the best side prices',t=>{
 const {api:a}=setup(t),base={player:'Receiver',profileId:'p',team:'A',eventId:'event-one',eventTeams:['A','B'],kickoff:future(),market:'rec_yds',line:50.5,source:'parlay',updatedAt:new Date().toISOString(),projMean:55,projSd:20,model:{status:'ready',family:'lognormal',mu_log:3.9,sigma_log:.4,n:12}};
 const rows=[
  {p:{...base,id:'one',book:'Book A',overOdds:-110,underOdds:-105}},
  {p:{...base,id:'two',book:'Book B',kickoff:new Date(Date.parse(base.kickoff)+60000).toISOString(),overOdds:105,underOdds:-120}},
  {p:{...base,id:'three',book:'Book C',line:51.5,overOdds:110,underOdds:-110}}
 ];
 const offers=a.consolidatePropOffers(rows);assert.equal(offers.length,2);
 const line=offers.find(x=>x.p.line===50.5).p;assert.equal(line.overOdds,105);assert.equal(line.overBook,'Book B');assert.equal(line.underOdds,-105);assert.equal(line.underBook,'Book A');assert.equal(line.offers.length,2);
});

test('Book-added team abbreviations do not prevent player matching',t=>{
 const {api:a}=setup(t),history={profiles:{p:{id:'p',name:'Bam Knight',team:'ARI',last_game:'2026-01-01',stats:{atd:{status:'ready',family:'poisson',lambda:.2,mean:.2,sd:.4,n:8}}}}};
 const index=a.buildProfileIndex(history);a.BET.history=history;
 const quote=a.attachProjection({player:'Bam Knight (ARI)',eventTeams:['ARI','SEA'],market:'atd',line:.5},index);
 assert.equal(quote.profileId,'p');
});
test('Betting navigation promotes GOING SCORE and nests specialist tools',t=>{
  const {api:a,w}=setup(t);a.wireBetting();a.renderBetting();
  assert.deepEqual([...w.document.querySelectorAll('#btTabGroup button')].map(b=>b.textContent),['Today','GOING SCORE','Markets','Games','Signals','Parlays']);
  w.document.querySelector('#btTabGroup [data-section="opportunities"]').click();
  assert.deepEqual([...w.document.querySelectorAll('#btToolGroup button')].map(b=>b.textContent),['All Bets','Model Board','First TD']);
  w.document.querySelector('#btToolGroup [data-tab="firsttd"]').click();assert.equal(a.BET.tab,'firsttd');
  assert.match(w.location.search,/tab=firsttd/);assert.equal(w.document.querySelector('#btFirstTdPanel').hidden,false);
});
test('GOING SCORE renders an auditable score apart from probability',t=>{
 const {api:a,w}=setup(t),kickoff=future();a.BET.tab='score';a.BET.games=[{id:'g',sport:'nfl',home:'B',away:'A',homeCode:'B',awayCode:'A',kickoff,source:'schedule'}];
 a.BET.history={generated_at:'2026-09-09T10:00:00Z',profiles:{p:{id:'p',name:'Runner One',team:'A',position:'RB',last_game:'2026-09-01',stats:{atd:{family:'poisson',status:'ready',mean:.7,lambda:.7,n:12}}}},features:{nfl:{players:{'A|p':{goal_line_carries:8,inside_ten_carries:12,red_zone_carries:20,end_zone_targets:2,inside_ten_targets:3,red_zone_targets:5}}}}};
 a.BET.context={season:2026,scopes:{'2026':{players:{p:{player_id:'p',team:'A',games:1,rush_attempts:12,targets:3}},teams:{A:{games:1,dropbacks:30}}}}};
 a.renderBetting();const text=w.document.querySelector('#btScorePanel').textContent;
 assert.match(text,/Runner One/);assert.match(text,/GOING SCORE/);assert.match(text,/Score anchor \/ model/);assert.match(text,/50\.3%/);assert.match(text,/score is not a probability/i);assert.match(text,/No priced line/);
 assert.equal(w.document.querySelectorAll('#scoreMarket button').length,5);
});
test('Any TD calibration shrinks short windows and rejects a disputed sportsbook market',t=>{
 const {api:a}=setup(t),profile={position:'RB'},model={n:12};
 const disputed=a.scoreAtdAnchor(profile,model,.713,{books:8,marketImplied:.706,marketLow:.357,marketHigh:.726},1);
 assert.equal(disputed.marketUsable,false);assert.ok(disputed.scoreProbability>.48&&disputed.scoreProbability<.51);assert.match(disputed.evidence,/guardrail withheld/);
 const aligned=a.scoreAtdAnchor(profile,model,.45,{books:5,marketImplied:.41,marketLow:.38,marketHigh:.44},4);
 assert.equal(aligned.marketUsable,true);assert.ok(aligned.scoreProbability>.38&&aligned.scoreProbability<.43);assert.match(aligned.evidence,/blended 80\/20/);
});
test('Betting view preferences preserve the research context',t=>{
 const {api:a,w}=setup(t);Object.assign(a.BET,{sport:'ncaa',tab:'best',period:'1H',market:'total',sort:'time',book:'Pinnacle',matchup:'A @ B'});a.persistBettingView();
 assert.deepEqual(JSON.parse(w.localStorage.getItem('goinglong.betting.view.v1')),{sport:'ncaa',tab:'best',period:'1H',market:'total',sort:'time',book:'Pinnacle',matchup:'A @ B'});
});
test('Sport switch isolates game records and missing spreads stay unpriced',t=>{
  const {api:a,w}=setup(t);a.wireBetting();
  a.BET.games=[{id:'nfl',sport:'nfl',home:'BUF',away:'MIA',kickoff:future(),source:'manual'},
    {id:'ncaa',sport:'ncaa',home:'Alabama',away:'Georgia',kickoff:future(),source:'manual'}];
  w.document.querySelector('[data-sport="ncaa"]').click();
  assert.equal(w.document.querySelector('[data-tab="props"]').hidden,true);
  assert.doesNotMatch(w.document.getElementById('btGamesList').textContent,/Alabama/);
  w.document.querySelector('[data-coverage="all"]').click();
  assert.match(w.document.getElementById('btGamesList').textContent,/Alabama/);
  assert.doesNotMatch(w.document.getElementById('btGamesList').textContent,/BUF/);
  assert.equal(a.gameQuotes({source:'manual',spread:null,homeSpreadOdds:-110,model:{margin_mean:0,margin_sd:10}}).length,0);
});
test('Pagination bounds DOM and stale renders do not overwrite a newer filter',async t=>{
  const {api:a,w}=setup(t);
  a.BET.props=Array.from({length:10000},(_,i)=>({id:String(i),player:'Player '+i,market:'atd',source:'manual',manual:true,projMean:.5,overOdds:200}));
  const first=a.renderPropsTable();a.BET.query='Player 9999';await a.renderPropsTable();await first;
  assert.equal(w.document.querySelectorAll('#btPropsTable .bt-row').length,1);
  a.BET.query='';await a.renderPropsTable();assert.equal(w.document.querySelectorAll('#btPropsTable .bt-row').length,50);
});
test('Debounced projection edits preserve focus and calculate after typing',async t=>{
  const {api:a,w}=setup(t);a.wireBetting();
  a.BET.props=[{id:'edit',player:'Test Player',market:'atd',source:'manual',manual:true,projMean:.5,overOdds:200}];
  await a.renderPropsTable();const input=w.document.querySelector('.bt-projinput');input.focus();
  input.value='0.8';input.dispatchEvent(new w.Event('input',{bubbles:true}));
  input.value='0.9';input.dispatchEvent(new w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,300));assert.equal(w.document.activeElement,input);
  assert.equal(a.BET.props[0].projMean,.9);assert.match(w.document.getElementById('btPageNote').textContent,/override applied/);
});
test('Background loader parses real snapshots and connects shared history',async t=>{
  const {api:a,w}=setup(t), blobs=new Map();let serial=0;
  w.Blob=class {constructor(parts){this.source=parts.join('');}};
  w.URL.createObjectURL=blob=>{const id='blob:'+serial++;blobs.set(id,blob.source);return id;};
  w.URL.revokeObjectURL=id=>blobs.delete(id);
  w.Worker=class {
    constructor(id){this.code=blobs.get(id);}
    postMessage(data){
      const worker=this;
      const workerContext=vm.createContext({AbortSignal,fetch:async url=>{
        assert.ok(new URL(url).pathname.startsWith('/api/snapshot'),'Startup reads the live nightly snapshot before the packaged fallback');
        const filename=new URL(url).searchParams.get('file');
        return {ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(__dirname,'../data',filename),'utf8'))};
      },postMessage:result=>worker.onmessage({data:result})});
      vm.runInContext(this.code,workerContext);
      workerContext.onmessage({data}).catch(error=>worker.onerror(error));
    }
    terminate(){}
  };
  await a.loadBettingData();
  assert.equal(a.BET.loading,false);
  assert.ok(Object.keys(a.BET.history.profiles).length>0);
  assert.ok(a.BET.games.some(g=>g.sport==='nfl'));
  assert.ok(a.BET.games.some(g=>g.sport==='ncaa'));
  assert.equal(blobs.size,0);
  assert.doesNotMatch(w.document.getElementById('btDataNote').textContent,/unavailable/i);
});

test('Parlay cards join Rams profiles and games despite LA/LAR naming',async t=>{
  const {api:a,w}=setup(t);const kickoff=future();
  a.BET.history={team_names:{'Los Angeles Rams':'LAR','San Francisco 49ers':'SF'},profiles:{p:{id:'p',name:'Puka Nacua',team:'LA',stats:{rec_yds:{family:'lognormal',status:'ready',n:12,mean:90,sd:30,mu_log:4.4,sigma_log:.3}}}},games:{nfl:[{home:'LA',away:'SF',kickoff,model:{margin_mean:4,total_mean:48,margin_sd:13,total_sd:13}}]}};
  a.BET.props=await a.propsFromRealData({props:[{player:'Puka Nacua',homeName:'Los Angeles Rams',awayName:'San Francisco 49ers',market:'rec_yds',line:85.5,overOdds:-110,underOdds:105,source:'parlay',kickoff,updatedAt:new Date().toISOString()}]});
  assert.equal(a.BET.props[0].projMean,90);await a.renderPropsTable();
  const card=w.document.querySelector('.bt-row[data-prop-id]');assert.match(card.textContent,/90\.0/);assert.match(card.textContent,/-110/);assert.match(card.textContent,/\+105/);
  const games=a.gamesFromParlay({games_raw:[{id:'e',home_team:'Los Angeles Rams',away_team:'San Francisco 49ers',commence_time:kickoff,bookmakers:[{key:'a',markets:[]}]}]},'nfl');
  assert.equal(games[0].model.margin_mean,4);
});

test('Refresh requests the live endpoint and preserves manual edits by quote identity',async t=>{
  const {api:a,w}=setup(t);const urls=[];const quote={quoteKey:'stable',player:'Josh Allen',market:'atd',line:.5,source:'parlay',overOdds:200,kickoff:future(),updatedAt:new Date().toISOString()};
  a.BET.props=[{...quote,manual:true,projMean:.9,projSd:1}];
  w.URL.createObjectURL=()=> 'blob:fixture';w.URL.revokeObjectURL=()=>{};
  w.Worker=class{postMessage(url){urls.push(url);queueMicrotask(()=>this.onmessage({data:{body:{provider:'parlay',generated_at:new Date().toISOString(),props:[quote],games_raw:[]}}}));}terminate(){}};
  await a.refreshLiveOdds('nfl');
  assert.match(urls[0],/\/api\/odds\?sport=nfl$/);assert.equal(a.BET.props.length,1);assert.equal(a.BET.props[0].projMean,.9);
  assert.equal(w.document.querySelector('#btLoadRealProps').disabled,false);assert.match(w.document.querySelector('#btDataNote').textContent,/Parlay connected/);
  // Failed refresh keeps existing quotes and does not freshen their timestamps.
  w.Worker=class{postMessage(){queueMicrotask(()=>this.onmessage({data:{error:'HTTP 502'}}));}terminate(){}};
  await a.refreshLiveOdds('nfl');assert.equal(a.BET.props[0].updatedAt,quote.updatedAt);assert.equal(a.BET.props[0].projMean,.9);
  assert.match(w.document.querySelector('#btLoadPropsNote').textContent,/saved NFL prices/);
});

test('Opportunity research stays dated and cannot support an Under or a different team',t=>{
 const {api:a}=setup(t),today=new Date(Date.now()-86400000).toISOString().slice(0,10);
 const p={profileId:'p',team:'A',position:'WR',market:'rec_yds',side:'Over',kind:'prop'};
 const player={team:'A',position:'WR',season:2025,share:.9,position_average:.6,opportunity_flag:true,catches_short:3,catch_model_targets:25,pass_snaps:108,charting_coverage:.9,share_type:'passing_snap_proxy',last_game:today};
 a.BET.context={season:2026,scopes:{2025:{season:2025,players:{p:player},teams:{A:{games:6,charted_dropbacks:120}}},2026:{season:2026,players:{p:{...player,season:2026}},teams:{A:{games:1,charted_dropbacks:120}}}}};
 assert.equal(a.signalFlags(p,[],{}).find(f=>f.id==='opportunity').family,'audit');
 assert.match(a.footballOpportunityMarkup(p),/2025 research/);assert.equal(a.footballOpportunity({...p,team:'B'}),null);
 a.BET.context.scopes[2026].teams.A.games=3;
 assert.equal(a.signalFlags(p,[],{}).find(f=>f.id==='opportunity').family,'role');
 assert.equal(a.signalFlags({...p,side:'Under'},[],{}).find(f=>f.id==='opportunity').family,'audit');
 assert.equal(a.signalFlags({...p,market:'first_td'},[],{}).find(f=>f.id==='opportunity').family,'audit');
});

test('Partial live refresh keeps failed categories dated while successful quotes replace matching snapshots',t=>{
 const {api:a}=setup(t),old={props:[{quoteKey:'q',updatedAt:'old',overOdds:100},{quoteKey:'r',updatedAt:'older'}],games_raw:[{id:'saved'}]};
 const merged=a.mergePartialLive(old,{props_status:'unavailable',odds_status:'unavailable',props:[{quoteKey:'q',updatedAt:'new',overOdds:120}],games_raw:[]});
 assert.equal(merged.props.length,2);assert.equal(merged.props[0].updatedAt,'new');assert.equal(merged.props[1].updatedAt,'older');assert.equal(merged.games_raw[0].id,'saved');
});


test('Weekly best plays retain saved-line research while value requires fresh aligned prices',t=>{
 const {api:a}=setup(t),now=Date.parse('2026-09-12T18:00:00Z');
 const base={sport:'ncaa',kind:'game',event:'one',contract:'one|total|48.5|Over',market:'total',side:'Over',line:48.5,kickoff:'2026-09-12T19:00:00Z',updatedAt:new Date(now).toISOString(),flags:[],push:0,n:12,prob:.8,ev:-.04,book:'betmgm',dec:1.2};
 const low={...base,event:'two',contract:'two',prob:.5,dec:2.2,ev:.1,reference:{win:.5}};
 const sharp={...low,book:'pinnacle',reference:{win:.5},dec:2};
 let r=a.rankBestPlays([base,low],[low,sharp],'ncaa','all',now);
 assert.equal(r.chance[0].event,'one');assert.equal(r.value[0].event,'two');
 assert.ok(Math.abs(r.value[0].ev-.078)<1e-8);assert.equal(r.value[0].referenceBooks.length,1);
 assert.equal(a.rankBestPlays([low],[low,{...sharp,updatedAt:new Date(now-61000).toISOString()}],'ncaa','all',now).value.length,0);
 assert.equal(a.rankBestPlays([{...base,updatedAt:new Date(now-300001).toISOString()}],[],'ncaa','all',now).chance[0].savedPrice,true);
 assert.equal(a.rankBestPlays([{...base,kickoff:'2026-09-13T19:00:00Z'}],[],'ncaa','all',now).chance.length,1);
 assert.equal(a.rankBestPlays([{...base,kickoff:'2026-09-21T19:00:00Z'}],[],'ncaa','all',now).chance.length,0);
 assert.equal(a.rankBestPlays([{...base,updatedAt:new Date(now-86400001).toISOString()}],[],'ncaa','all',now).chance.length,0);
 assert.equal(a.rankBestPlays([{...low,push:.01}],[{...low,push:.01},sharp],'ncaa','all',now).value.length,0);
});

test('Opportunity pool reports every exclusion without changing canonical eligibility',t=>{
 const {api:a}=setup(t),now=Date.now(),current=new Date(now+86400000).toISOString(),fresh=new Date(now-60000).toISOString();
 const base={sport:'nfl',kind:'prop',home:'A',away:'B',kickoff:current,updatedAt:fresh,profileId:'p',market:'rec_yds',side:'Over',line:50.5};
 const rows=[base,{...base,book:'second'},{...base,sport:'ncaa'},{...base,kickoff:'2026-09-20T17:00:00Z'},{...base,kickoff:new Date(now-1).toISOString()},{...base,updatedAt:new Date(now-25*3600000).toISOString()}];
 const pool=a.opportunityPool(rows,'nfl','all',now);
 assert.equal(pool.eligible.length,2);assert.equal(pool.canonical,1);
 assert.deepEqual({...pool.excluded},{wrong_sport_or_type:1,outside_current_week:1,started_or_invalid:1,quote_over_24_hours:1});
});
test('Best play labels use away spread sign and escape names',t=>{
 const {api:a}=setup(t);const text=a.bestPlayCard({kind:'game',sport:'ncaa',market:'spread',side:'Away',line:-3.5,away:'Away <tag>',home:'Home',team:'',book:'betmgm',odds:-110,prob:.6,push:0,ev:.14,n:12,kickoff:new Date().toISOString(),updatedAt:new Date().toISOString(),flags:[]});
 assert.match(text,/Away &lt;tag&gt; \+3.5 spread/);assert.ok(!text.includes('<tag>'));assert.match(text,/Primary risk/);assert.match(text,/Why GOING likes it/);assert.match(text,/SHOW ME THE DATA/);assert.match(text,/Parlay relevance/);
});

test('Price shortlist needs no historical model and retains both opposing sides',t=>{
 const {api:a}=setup(t),now=Date.now();a.BET.games=[{sport:'ncaa',home:'Home',away:'Away',kickoff:new Date(now+60000).toISOString(),book:'pinnacle',updatedAt:new Date(now).toISOString(),spread:-3.5,homeSpreadOdds:-110,awaySpreadOdds:-110,mlHome:-150,mlAway:130}];
 const rows=a.bestPriceCandidates();assert.equal(rows.length,4);assert.equal(rows.filter(c=>c.market==='spread').length,2);assert.ok(rows.every(c=>c.reference.win>0));
});

test('Promo automatically renders from Fanatics quotes and fails closed on roster loss',async t=>{
 const {api:a,w,context}=setup(t);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../shared/touchdown-promo.js'),'utf8'),context);
 const now=Date.parse('2026-09-13T12:00:00Z');w.Date.now=()=>now;
 w.document.getElementById('promoDate').value='2026-09-13';
 a.BET.tab='promo';
 a.BET.props=['A','B','C','D'].map((id,i)=>({player:'Player '+id,profileId:id,team:id,market:'atd',line:.5,overOdds:200,book:'fanatics',kickoff:'2026-09-13T17:00:00Z',updatedAt:'2026-09-13T11:59:00Z',eventTeams:[id,'Opponent '+id],projMean:.5,projSd:.5,model:{status:'ready',family:'poisson',lambda:.5,mean:.5,sd:.5}}));
 vm.runInContext(`PROMO_AUTO.checked=Date.now();PROMO_AUTO.availability={checkedAt:new Date(Date.now()).toISOString(),teams:BET.props.map(p=>({team:p.team,code:p.team,players:[{key:('player'+p.team).toLowerCase(),availability:'expected'}]}))};`,context);
 await vm.runInContext('renderPromo()',context);
 assert.ok(w.document.querySelectorAll('#promoOptions article').length>0,w.document.getElementById('promoStatus').textContent);
 assert.equal(w.document.getElementById('promoPaste'),null);
 a.BET.props.forEach(p=>p.updatedAt=new Date(now-3600000).toISOString());
 await vm.runInContext('renderPromo()',context);
 assert.match(w.document.getElementById('promoStatus').textContent,/FALLBACK \/ STALE/);
 assert.ok(w.document.querySelectorAll('#promoOptions article').length>0);
 assert.match(w.document.getElementById('promoOptions').textContent,/STALE PRICE RESEARCH/);
 vm.runInContext('PROMO_AUTO.availability.teams=[]',context);
 await vm.runInContext('renderPromo()',context);
 assert.equal(w.document.querySelectorAll('#promoOptions article').length,0);
});

test('Started quotes yield by scanned count instead of pausing once per excluded row',async t=>{
 const {api:a,w}=setup(t);let paints=0;
 w.requestAnimationFrame=cb=>{paints++;setTimeout(cb,0);};
 const rows=Array.from({length:1000},()=>({kickoff:'2020-01-01T00:00:00Z'}));
 assert.equal((await a.propsFromRealData({props:rows})).length,0);
 assert.ok(paints<=5,`Expected at most five frame yields, received ${paints}`);
});

test('Best props accept offseason history without admitting extreme model discrepancies',t=>{
 const {api:a}=setup(t),now=Date.parse('2026-09-13T18:00:00Z');
 const p={sport:'nfl',kind:'prop',event:'g',contract:'p',profileId:'p',profileDate:'2026-01-04',market:'rec_yds',prob:.6,ev:.1,n:12,kickoff:'2026-09-14T00:20:00Z',updatedAt:new Date(now).toISOString(),book:'fanatics',dec:2,flags:[]};
 p.flags=a.signalFlags(p,[],{},now);
 assert.equal(a.rankBestPlays([p],[],'nfl','prop',now).chance.length,1);
 const extreme={...p,ev:.8};extreme.flags=a.signalFlags(extreme,[],{},now);
 assert.equal(a.rankBestPlays([extreme],[],'nfl','prop',now).chance.length,0);
 const games=Array.from({length:6},(_,i)=>({...p,kind:'game',event:'g'+i,contract:'g'+i,prob:.9,flags:[]}));
 assert.ok(a.rankBestPlays([...games,p],[],'nfl','all',now).chance.some(c=>c.kind==='prop'));
});

test('Best plays retain the complete exact-line field and identify alternative line sets',t=>{
 const {api:a}=setup(t),now=Date.parse('2026-09-13T18:00:00Z'),base={sport:'nfl',kind:'prop',event:'g',profileId:'p',market:'rec_yds',side:'Over',prob:.6,ev:.1,n:12,kickoff:'2026-09-14T00:20:00Z',updatedAt:new Date(now).toISOString(),book:'fanatics',dec:2,flags:[]};
 const rows=Array.from({length:12},(_,i)=>({...base,line:20.5+i,contract:`p|${20.5+i}`,canonicalContract:`g|prop|p|rec_yds|${20.5+i}|Over`}));
 const ranked=a.rankBestPlays(rows,[],'nfl','prop',now);
 assert.equal(ranked.chance.length,12);assert.ok(ranked.chance.every(c=>c.altLineSet));
});

test('Today filters support a sportsbook, hide only alternate lines, and enforce minimum odds',t=>{
 const {api:a}=setup(t),now=Date.parse('2026-09-13T18:00:00Z'),base={sport:'nfl',kind:'prop',event:'g',profileId:'p',market:'rec_yds',side:'Over',prob:.6,ev:.1,n:12,kickoff:'2026-09-14T00:20:00Z',updatedAt:new Date(now).toISOString(),flags:[]};
 const rows=[{...base,line:50.5,book:'fanatics',odds:-110,dec:1.91,canonicalContract:'main'},{...base,line:20.5,book:'fanatics',odds:-1000,dec:1.1,canonicalContract:'alt'},{...base,line:50.5,book:'fanduel',odds:-105,dec:1.95,canonicalContract:'main'}];
 const fanatics=a.rankBestPlays(rows,[],'nfl','prop',now,'fanatics').chance;
 assert.equal(fanatics.length,2);assert.equal(fanatics.filter(x=>x.isAltLine).length,1);
 const visible=a.filterBestPlays(fanatics,{book:'fanatics',excludeAlt:true,minOdds:-500});
 assert.equal(visible.length,1);assert.equal(visible[0].line,50.5);assert.equal(visible[0].book,'fanatics');
 assert.equal(a.rankBestPlays(rows,[],'nfl','prop',now,'fanduel').chance.length,1);
});

test('Parlay game selector includes scheduled SNF even without eligible odds',async t=>{
 const {api:a,w,context}=setup(t);w.Date.now=()=>Date.parse('2026-09-13T23:00:00Z');
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../shared/football-parlays.js'),'utf8'),context);
 a.BET.tab='parlays';a.BET.sport='nfl';a.BET.props=[];a.BET.games=[];
 a.BET.history={games:{nfl:[{home:'NYG',away:'DAL',kickoff:'2026-09-14T00:20:00Z'},{home:'KC',away:'DEN',kickoff:'2026-09-15T00:15:00Z'}]}};
 await vm.runInContext('renderFootballParlays()',context);
 const text=w.document.getElementById('parlayGames').textContent;
 assert.match(text,/DAL @ NYG/);assert.match(text,/DEN @ KC/);assert.match(text,/Waiting for supported/);
 assert.equal(w.document.querySelectorAll('#parlayGames input').length,2);
});

test('First TD predictor renders historical game outcomes without inventing quote prices',t=>{
 const {api:a,w,context}=setup(t);w.Date.now=()=>Date.parse('2026-09-13T23:00:00Z');
 const outcomes=Object.fromEntries(Array.from({length:10},(_,i)=>['p'+i,{player_id:'p'+i,name:i===9?'Tenth Player':'Test Player '+i,team:'DAL',probability:.1-i*.005,fair_odds:900+i*10}]));
 a.BET.props=[];a.BET.history={derivatives:{first_td:{g:{status:'ready',home:'NYG',away:'DAL',kickoff:'2026-09-14T00:20:00Z',outcomes}}}};
 vm.runInContext('renderFirstTdPredictor()',context);const text=w.document.getElementById('firstTdPredictions').textContent;
 assert.match(text,/Test Player 0/);assert.match(text,/Tenth Player/);assert.match(text,/10 eligible scorers/);assert.match(text,/10.0%/);assert.match(text,/No matching sportsbook quote/);assert.doesNotMatch(text,/Top eight/);
});


test('Extreme model-price disagreement remains visible without a suggested stake',t=>{
 const {w,context}=setup(t);
 const result=vm.runInContext(`(()=>{const row={prob:.341,ev:4.111,odds:1400,side:'Yes',kelly:.02};return {trust:footballTrust(row),markup:metricMarkup(row)};})()`,context);
 assert.equal(result.trust.state,'review_required');assert.equal(result.trust.canSuggestStake,false);
 assert.match(result.markup,/411.1%/);assert.match(result.markup,/Needs review/);assert.doesNotMatch(result.markup,/2.0%/);
});
test('Trust policy distinguishes historical research from model-price review',t=>{
 const {context}=setup(t);
 const result=vm.runInContext(`(()=>{const now=Date.parse('2026-09-14T12:00:00Z');return [footballTrust({prob:.6,ev:.1,profileDate:'2026-01-01'},now),footballTrust({prob:.6,ev:.5,profileDate:'2026-01-01'},now)];})()`,context);
 assert.equal(result[0].historical,true);assert.equal(result[0].review,false);assert.equal(result[1].review,true);
});
