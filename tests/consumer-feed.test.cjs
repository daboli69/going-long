const {test}=require('node:test');
const assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const fs=require('node:fs');
const path=require('node:path');

test('consumer cards retain rendered evidence without duplicating research/offer boards',async()=>{
 const {footballCards,compactFootballCard}=await import('../scripts/build_consumer_data.mjs');
 const row={sport:'nfl',kind:'prop',player:'Fixture Player',team:'BUF',home:'BUF',away:'NYJ',
  canonicalContract:'contract',book:'Fixture Book',market:'rec_yds',side:'Over',line:40.5,
  kickoff:'2099-10-20T17:00:00Z',updatedAt:new Date().toISOString(),odds:-110,dec:1.91,
  prob:.6,projMean:50,n:12,ev:.1,profileId:'fixture',flags:[{id:'gap',why:'Recorded role evidence'}],
  injury:{state:'questionable',status:'Questionable',bodyPart:'Knee'},
  offers:Array(50).fill({unboundedInternalEvidence:'x'.repeat(10000)}),
  readiness_snapshot:{canonical:'retained in tracker'},provenance:{inputs:{history:'receipt'}}};
 const [card]=footballCards([row,row]);
 assert.equal(card.id,'contract|Fixture Book');assert.equal(card.injury,row.injury);
 assert.equal(card.prob,row.prob);assert.equal(card.updatedAt,row.updatedAt);
 for(const field of ['offers','readiness_snapshot','provenance'])assert.equal(Object.hasOwn(card,field),false);
 assert.equal(footballCards([row,{...row,book:'Other Book'}]).length,2);
 const dom=new JSDOM('<body></body>',{runScripts:'outside-only',url:'https://fixture.test'});
 for(const file of ['evidence-ui.js','opportunity-ui.js'])dom.window.eval(fs.readFileSync(path.join(__dirname,'../shared',file),'utf8'));
 assert.equal(dom.window.GoingUI.card(card),dom.window.GoingUI.card({...row,...card}));
 assert.deepEqual(compactFootballCard(card),card);
 dom.window.close();
 const many=footballCards(Array.from({length:6000},(_,i)=>({...row,canonicalContract:'contract-'+i})));
 assert.equal(many.length,6000);assert.ok(Buffer.byteLength(JSON.stringify(many))<15*1024*1024);
});
