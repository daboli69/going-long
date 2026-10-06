'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
const source=html.slice(html.indexOf('function exportDfsReceipts(){'),html.indexOf('function wireDfs(){'));
function run(saved,{storageError=false,downloadError=false}={}){
 const result={clicks:0,revoked:[],renders:0,reads:0};
 const context={DFS_STATE:{status:''},GoingDfsJournal:{read(){result.reads++;if(storageError)throw Error('Storage blocked');return saved;}},
  localStorage:{setItem(){throw Error('Export must never rewrite records');}},Blob,
  URL:{createObjectURL(blob){result.blob=blob;return 'blob:receipt';},revokeObjectURL(url){result.revoked.push(url);}},
  document:{createElement(){const link={click(){if(downloadError)throw Error('Download blocked');result.clicks++;}};result.link=link;return link;}},
  renderDfs(){result.renders++;}};
 vm.runInNewContext(source+';exportDfsReceipts();',context);
 return {...result,status:context.DFS_STATE.status};
}
test('Captain workflow downloads all preserved receipts without rewriting them',async()=>{
 const receipts=[{id:'captain',contest:'showdown',players:[{salary:6000}]},{id:'classic',contest:'classic'}],before=JSON.stringify(receipts);
 const r=run({ok:true,receipts});assert.deepEqual(JSON.parse(await r.blob.text()),receipts);assert.equal(JSON.stringify(receipts),before);
 assert.equal(r.link.download,'going-dfs-frozen-lineups.json');assert.equal(r.clicks,1);assert.deepEqual(r.revoked,['blob:receipt']);assert.equal(r.renders,1);assert.match(r.status,/2 frozen DFS lineups exported/);
 assert.match(html,/id="dfsExportReceipts"/);assert.match(html,/\$\('dfsExportReceipts'\).onclick=exportDfsReceipts/);
});
test('empty and failed journal reads never download fake or incomplete records',()=>{
 for(const [saved,options,message] of [[{ok:true,receipts:[]},{},/No frozen/],[{ok:false,error:'Integrity failed'},{},/Integrity failed/],[null,{storageError:true},/Storage blocked/]]){
  const r=run(saved,options);assert.equal(r.clicks,0);assert.equal(r.blob,undefined);assert.equal(r.renders,1);assert.match(r.status,message);
 }
});
test('download failures revoke the temporary URL and leave records intact',()=>{
 const r=run({ok:true,receipts:[{id:'saved'}]},{downloadError:true});assert.equal(r.clicks,0);assert.deepEqual(r.revoked,['blob:receipt']);assert.equal(r.renders,1);assert.match(r.status,/Download blocked/);
});

test('no-salary Captain rendering preserves actionable export status',()=>{
 assert.match(html,/\$\('dfsStatus'\).textContent=DFS_STATE.status\|\|'Load an official/);
});
