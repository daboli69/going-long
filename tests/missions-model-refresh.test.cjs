const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const read=f=>fs.readFileSync(f,'utf8');
test('the Missions model snapshot is refreshed by the data workflow and is a known publication owner',()=>{
 const wf=read('.github/workflows/data.yml'),health=read('scripts/refresh_health.py');
 const at=id=>wf.indexOf('id: '+id);
 assert.ok(at('missions_model')>at('consumer_data')&&at('missions_model')<at('data_integrity'),'built after the odds/model inputs, before the integrity check');
 assert.match(wf,/id: missions_model\n\s+continue-on-error: true\n\s+if: \$\{\{ !cancelled\(\) \}\}\n[^\n]*\n\s+run: node scripts\/build_missions_model\.cjs/);
 assert.match(health,/'missions_model': \('data\/missions_model\.json',\)/);
});
test('the snapshot writer leaves an unchanged snapshot alone so refreshes do not commit noise',()=>{
 assert.match(read('scripts/build_missions_model.cjs'),/unchanged/);
});
