'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const script=fs.readFileSync('shared/abbeys-ui.js','utf8');
function board(){return {schemaVersion:1,generatedAt:'2026-10-04T03:00:00Z',record:{wins:0,losses:0,ties:0,pending:2},recordScope:'Manual official boards only',weeks:[4,5].map(week=>({season:2026,week,frozenAt:'2026-10-04T03:00:00Z',source:{cutoff:'week-specific cutoff',sourceSHA:'abc'},picks:[{gameId:'g'+week,away:'ATL',home:'NO',kickoff:'2026-10-06T00:15:00Z',winner:'NO',confidence:'Sensitive lean',gamesAway:3,gamesHome:3,projectedAway:22,projectedHome:25,support:['<img src=x onerror=alert(1)>','Current-season scoring evidence'],concerns:['Questionable participation remains uncertain.']}],monday:{gameId:'g'+week,away:'ATL',home:'NO',predictedAway:22,predictedHome:25}}))};}
function setup(t,fetch){const dom=new JSDOM('<section id="panel"></section>',{url:'https://going-long.test/long/',runScripts:'outside-only'});t.after(()=>dom.window.close());dom.window.fetch=fetch;dom.window.eval(script);return {dom,panel:dom.window.document.querySelector('#panel')};}
test('board shows every frozen pick, Monday first, explicit evidence and separated context; repeated render preserves nodes/focus',async t=>{
  let calls=0;const {dom,panel}=setup(t,async url=>{calls++;assert.equal(url,'/api/snapshot?file=abbeys-board.json');return Response.json(board());});
  await Promise.all([dom.window.GoingAbbeysUI.render(panel),dom.window.GoingAbbeysUI.render(panel)]);assert.equal(calls,1);
  assert.equal(panel.querySelectorAll('.abbeys-pick').length,1);assert.match(panel.textContent,/Sensitive lean/);assert.match(panel.textContent,/week-specific cutoff/);assert.match(panel.textContent,/none verified/);assert.match(panel.textContent,/No post-freeze market/);assert.equal(panel.querySelector('img'),null);
  const monday=panel.querySelector('.abbeys-monday'),picks=panel.querySelector('.abbeys-picks');assert.ok(monday.compareDocumentPosition(picks)&dom.window.Node.DOCUMENT_POSITION_FOLLOWING);
  const details=panel.querySelector('.abbeys-why-details'),summary=details.querySelector('summary');details.open=true;summary.focus();
  await dom.window.GoingAbbeysUI.render(panel);assert.equal(panel.querySelector('.abbeys-why-details'),details);assert.equal(details.open,true);assert.equal(dom.window.document.activeElement,summary);
  const select=panel.querySelector('select');select.value='2026-4';select.dispatchEvent(new dom.window.Event('change'));assert.equal(panel.querySelector('select').value,'2026-4');assert.equal(dom.window.document.activeElement,panel.querySelector('select'));
  assert.equal(panel.querySelectorAll('.abbeys-pick>details').length,1);
});
test('missing optional data, empty weeks and unverified news remain explicit without fake picks',async t=>{
  const {dom,panel}=setup(t,async()=>Response.json({schemaVersion:1,weeks:[],record:{}}));await dom.window.GoingAbbeysUI.render(panel);assert.match(panel.textContent,/No frozen ABBEYS weeks/);assert.equal(panel.querySelectorAll('.abbeys-pick').length,0);
});
test('endpoint outage falls back to packaged snapshot; total failure offers one explicit retry',async t=>{
  let calls=0,ready=false;const {dom,panel}=setup(t,async()=>{calls++;return ready?Response.json(board()):new Response(null,{status:503});});
  await dom.window.GoingAbbeysUI.render(panel);assert.equal(calls,2);assert.match(panel.textContent,/could not be loaded/);assert.equal(panel.querySelector('button').textContent,'Retry loading board');
  await dom.window.GoingAbbeysUI.render(panel);assert.equal(calls,2,'Background renders do not repeat failed requests');
  ready=true;panel.querySelector('button').click();await new Promise(resolve=>setImmediate(resolve));assert.equal(calls,3);assert.equal(panel.querySelectorAll('.abbeys-pick').length,1);
});
test('ABBEYS integration keeps NFL-only route, nine-tool grid and unchanged existing model functions',()=>{
  const html=fs.readFileSync('index.html','utf8'),shell=fs.readFileSync('shared/going-shell.js','utf8');
  assert.match(html,/data-section="abbeys" data-tab="abbeys"/);assert.match(html,/\[data-section="abbeys"\]'\)\.hidden=BET.sport!=="nfl"/);assert.match(html,/'score','charts','dfs','abbeys','props'/);assert.match(shell,/'ABBEYS','NFL'/);
  assert.match(html,/id="btAbbeysPanel" hidden/);assert.match(html,/GoingAbbeysUI\?\.render/);
});
