const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

function workflow(){return fs.readFileSync(path.join(__dirname,'../.github/workflows/test.yml'),'utf8');}
function pushPaths(source){
 const block=source.match(/^  push:\r?\n    paths:\r?\n((?:      - '[^']+'\r?\n)+)/m);
 assert.ok(block,'Application push path filter must be readable');
 return [...block[1].matchAll(/      - '([^']+)'/g)].map(match=>match[1]);
}
function triggers(file){return pushPaths(workflow()).some(pattern=>path.matchesGlob(file,pattern));}

test('source-only public football and shared UI edits trigger existing application validation',()=>{
 for(const file of ['index.html','shared/football-cheatsheets.js','shared/football-cheatsheets.css','shared/going-shell.js','hub/index.html','apps/players/index.html','apps/results/index.html','apps/yard/index.html']){
  assert.ok(fs.existsSync(path.join(__dirname,'..',file)),`Fixture is a real production source: ${file}`);
  assert.equal(triggers(file),true,`A push changing only ${file} must validate`);
 }
});

test('CI coverage retains API/model/test inputs, excludes generated snapshots and validates pull requests',()=>{
 for(const file of ['apps/validation/src.jsx','api/snapshot.mjs','server/parlay.mjs','scripts/build_pipeline.py','config/parlay-markets.json','vercel.json','package-lock.json','tests/ci-paths.test.cjs','.github/workflows/test.yml'])assert.equal(triggers(file),true,file);
 for(const file of ['data/nfl_betting.json','data/season_learning.json','docs/DAILY_REVIEW_PIPELINE.md','PROGRESS.md'])assert.equal(triggers(file),false,file);
 assert.match(workflow(),/^  pull_request:\s*$/m,'All pull requests retain validation');
});
