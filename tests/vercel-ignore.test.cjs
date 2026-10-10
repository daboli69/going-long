const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {execFileSync,spawnSync}=require('node:child_process');
const script=path.resolve(__dirname,'../scripts/vercel_ignore_build.mjs');

function repo(t){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'going-ignore-'));
 t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const git=(...args)=>execFileSync('git',args,{cwd:dir,encoding:'utf8'}).trim();
 git('init','-q');git('config','user.email','fixture@example.invalid');git('config','user.name','Offline fixture');
 const commit=(file,body)=>{fs.mkdirSync(path.dirname(path.join(dir,file)),{recursive:true});fs.writeFileSync(path.join(dir,file),body);git('add','--',file);git('commit','-qm','fixture');return git('rev-parse','HEAD');};
 const run=previous=>spawnSync(process.execPath,[script],{cwd:dir,encoding:'utf8',env:{...process.env,VERCEL_GIT_PREVIOUS_SHA:previous||''}});
 return {git,commit,run};
}
test('code followed by data still builds relative to the last deployed revision',t=>{
 const r=repo(t),base=r.commit('index.html','old');r.commit('index.html','new');r.commit('data/history.json','{}');
 assert.equal(r.run(base).status,1);
});
test('only live public snapshots since the deployed revision can skip a build',t=>{
 const r=repo(t),base=r.commit('index.html','old');r.commit('data/history.json','{}');r.commit('data/nfl_roster.json','{}');
 assert.equal(r.run(base).status,0);
 r.commit('data/static-only.json','{}');assert.equal(r.run(base).status,1);
});
test('first deployment, missing history and unrelated baseline all continue building',t=>{
 const r=repo(t),base=r.commit('index.html','old');r.commit('data/history.json','{}');
 assert.equal(r.run('').status,1);assert.equal(r.run('a'.repeat(40)).status,1);
 const original=r.git('branch','--show-current');r.git('checkout','--orphan','other');const other=r.commit('unrelated.txt','other');r.git('checkout',original);
 assert.equal(r.run(other).status,1);
});
test('a merge ending in data cannot hide source changes since deployment',t=>{
 const r=repo(t),base=r.commit('index.html','old'),original=r.git('branch','--show-current');
 r.git('checkout','-qb','source');r.commit('index.html','new');r.git('checkout',original);
 r.commit('data/history.json','{}');r.git('merge','--no-ff','source','-m','fixture merge');r.commit('data/nfl_roster.json','{}');
 assert.equal(r.run(base).status,1);
});
test('removed live snapshots must deploy so packaged fallbacks are also removed',t=>{
 const r=repo(t),base=r.commit('data/nfl_roster.json','{}');r.git('rm','data/nfl_roster.json');r.git('commit','-qm','remove snapshot');
 assert.equal(r.run(base).status,1);
});
