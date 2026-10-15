const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),React=require('react');
test('historical archive UI loads private receipts, filters, pages and erases them on logout',async()=>{
 const {JSDOM}=require('jsdom'),{transformWithOxc}=await import('vite');
 const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost/validation/'}),saved={window:global.window,document:global.document,fetch:global.fetch,IS_REACT_ACT_ENVIRONMENT:global.IS_REACT_ACT_ENVIRONMENT};
 global.window=dom.window;global.document=dom.window.document;global.IS_REACT_ACT_ENVIRONMENT=true;
 const source=fs.readFileSync(require.resolve('../apps/validation/odds-history.jsx'),'utf8').replace(/^import .*;\r?\n/gm,'').replace('export function','function');
 const code=(await transformWithOxc(source,'history.jsx',{jsx:{runtime:'classic'}})).code;
 const Component=Function('React','useEffect','useRef','useState',code+';return HistoricalOdds;')(React,React.useEffect,React.useRef,React.useState);
 const {createRoot}=require('react-dom/client'),root=createRoot(document.getElementById('root')),session={access_token:'fixture',user:{id:'owner'}};
 const calls=[];let lateResolve;
 const game={id:'event',home:'Home',away:'Away',kickoff:'2025-10-12T17:00:00Z'};
 global.fetch=async(url,options)=>{assert.equal(options.headers.Authorization,'Bearer fixture');assert.equal(options.cache,'no-store');calls.push(url);return {ok:true,json:async()=>url.includes('event=')?{quotes:[{id:'q',snapshot_at:game.kickoff,quote_at:game.kickoff,player:'Historical QB',side:'Over',line:250.5,price:-110,book:'pinnacle',market:'player_pass_yds'}],total:750,offset:Number(new URL(url,'http://localhost').searchParams.get('offset')||0),markets:['player_pass_yds'],books:['pinnacle']}:{events:[game],quotes:750,credits:30}};};
 const click=async label=>React.act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===label).click());
 const select=async(index,value)=>React.act(async()=>{const el=document.querySelectorAll('select')[index];el.value=value;el.dispatchEvent(new dom.window.Event('change',{bubbles:true}));});
 try{
  await React.act(async()=>root.render(React.createElement(Component,{session:null})));assert.match(document.body.textContent,/Sign in through Personal journal/);assert.equal(calls.length,0);
  await React.act(async()=>root.render(React.createElement(Component,{session})));
  await click('Load saved historical odds');await select(0,'event');assert.match(document.body.textContent,/Historical QB/);
  await select(1,'player_pass_yds');await select(2,'pinnacle');assert.match(calls.at(-1),/market=player_pass_yds&book=pinnacle/);
  await click('More prices');assert.match(calls.at(-1),/offset=500/);assert.match(document.body.textContent,/501–501 of 750/);
  global.fetch=()=>new Promise(resolve=>{lateResolve=resolve;});
  await React.act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Previous prices').click();});
  await React.act(async()=>root.render(React.createElement(Component,{session:null})));
  await React.act(async()=>lateResolve({ok:true,json:async()=>({quotes:[{player:'Must not return'}]})}));
  assert.doesNotMatch(document.body.textContent,/Historical QB|Must not return/);assert.match(document.body.textContent,/Sign in through Personal journal/);
 }finally{await React.act(async()=>root.unmount());Object.assign(global,saved);dom.window.close();}
});
