const test=require('node:test');const assert=require('node:assert/strict');
function client(rows){
 const calls=[];
 return {calls,from(table){
  const filters=[];let limit=Infinity;const q={
   select(){return q},eq(k,v){filters.push([k,v]);return q},gte(){return q},lte(){return q},order(){return q},limit(n){limit=n;return q},
   in(k,v){filters.push([k,v]);return q},or(){throw Error('Unexpected extra page')},
   then(resolve,reject){calls.push({table,filters});const field=(r,k)=>k.startsWith('payload->>')?String(r.payload[k.slice(10)]):r[k];const data=rows.filter(r=>r.table===table&&filters.every(([k,v])=>Array.isArray(v)?v.includes(field(r,k)):field(r,k)===v)).slice(0,limit);return Promise.resolve({data,error:null}).then(resolve,reject)}
  };return q;
 }};
}
test('No eligible bets: load bounded checks without scanning closing history',async()=>{
 const {loadJournal}=await import('../apps/validation/load-journal.mjs');
 const c=client(Array.from({length:300},(_,i)=>({table:'market_journal',owner_id:'owner',kind:'prediction',id:String(i),payload:{actionable:false}})));
 const result=await loadJournal(c,'owner','2026-01-01','2026-09-12');
 assert.equal(result.records.length,100);assert.ok(c.calls.every(q=>q.filters.some(([k,v])=>k==='owner_id'&&v==='owner')));
 assert.ok(!c.calls.some(q=>q.filters.some(([k,v])=>k==='kind'&&['closing','settlement'].includes(v))));
});
test('Only outcomes linked to eligible predictions enter performance loading',async()=>{
 const {loadJournal}=await import('../apps/validation/load-journal.mjs');
 const row=(kind,id,payload)=>({table:'market_journal',owner_id:'owner',kind,id,payload});
 const c=client([row('prediction','p',{actionable:true}),row('settlement','s',{prediction_id:'p'}),row('closing','c',{prediction_id:'p'}),row('closing','unrelated',{prediction_id:'blocked'})]);
 const result=await loadJournal(c,'owner','2026-01-01','2026-09-12');
 assert.deepEqual(new Set(result.records.map(r=>r.id)),new Set(['p','s','c']));
});
