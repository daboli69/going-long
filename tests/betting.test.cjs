const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
function setup(t){
  const dom=new JSDOM(html,{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
  t.after(()=>dom.window.close());
  dom.window.localStorage.setItem('goinglong.gateway.mode','fantasy');
  dom.window.requestAnimationFrame=cb=>dom.window.setTimeout(cb,0);
  dom.window.HTMLElement.prototype.scrollIntoView=function(){};
  const context=dom.getInternalVMContext();
  for(const script of dom.window.document.querySelectorAll('script:not([src])')){
    vm.runInContext(script.textContent.replace(/\nboot\(\);/,'\n'),context);
  }
  vm.runInContext(`globalThis.api={BET,americanToDecimal,normalCDF,poissonCDF,lognormalCDF,
    propProbabilities,computePropRow,evPercent,kellyFraction,quoteState,propsFromRealData,
    parsePropsPaste,parseGamesPaste,renderPropsTable,renderBetting,wireBetting,gameQuotes,
    normalMarket,buildProfileIndex,attachProjection,loadBettingData,refreshLiveOdds,gamesFromParlay,collegePropsFromFeed};`,context);
  dom.window.api.BET.liveLoaded={nfl:true,ncaa:true};
  return {api:dom.window.api,w:dom.window,context};
}
const close=(actual,expected,tol=1e-7)=>assert.ok(Math.abs(actual-expected)<tol,`${actual} != ${expected}`);
const future=()=>new Date(Date.now()+86400000).toISOString();
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
test('Sport switch isolates game records and missing spreads stay unpriced',t=>{
  const {api:a,w}=setup(t);a.wireBetting();
  a.BET.games=[{id:'nfl',sport:'nfl',home:'BUF',away:'MIA',kickoff:future(),source:'manual'},
    {id:'ncaa',sport:'ncaa',home:'Alabama',away:'Georgia',kickoff:future(),source:'manual'}];
  w.document.querySelector('[data-sport="ncaa"]').click();
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
      const workerContext=vm.createContext({fetch:async url=>{
        const filename=path.basename(new URL(url).pathname);
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

test('NCAA props display real prices without borrowing NFL player models',async t=>{
  const {api:a,w}=setup(t);a.wireBetting();
  a.BET.history={profiles:{p:{name:'Shared Name',team:'BUF',stats:{receptions:{mean:8,status:'ready'}}}}};
  a.BET.ncaaProps=a.collegePropsFromFeed({props:[{player:'Shared Name',book:'College Book',market:'receptions',line:4.5,overOdds:-110,underOdds:105,source:'parlay',kickoff:future(),updatedAt:new Date().toISOString()}]});
  a.BET.sport='ncaa';a.BET.tab='props';await a.renderPropsTable();
  assert.equal(a.BET.ncaaProps[0].model,null);assert.equal(a.computePropRow(a.BET.ncaaProps[0]).ev,null);
  const card=w.document.querySelector('#btPropsTable .bt-row');assert.match(card.textContent,/Shared Name/);assert.match(card.textContent,/-110/);assert.match(card.textContent,/\+105/);
  a.BET.sport='nfl';await a.renderPropsTable();assert.doesNotMatch(w.document.getElementById('btPropsTable').textContent,/Shared Name/);
});
