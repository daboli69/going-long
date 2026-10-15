const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const read=f=>fs.readFileSync(path.join(__dirname,'..',f),'utf8');
const links=[['home','/'],['long','/long/'],['missions','/missions/'],['yard','/yard/'],['roster','/players/'],['results','/results/']];
test('every route keeps its own icon when Missions sits in the middle of the navigation',()=>{
 const dom=new JSDOM(`<!doctype html><body data-going-workspace="missions"><header id="going-shell"><div class="going-shell-inner"><a class="going-wordmark" href="/">GOING</a><nav class="going-global-nav">${links.map(([k,u])=>`<a href="${u}" data-nav="${k}">${k}</a>`).join('')}</nav></div></header></body>`,{runScripts:'outside-only',pretendToBeVisual:true});
 dom.window.eval(read('shared/visual-system.js'));
 const icons=[...dom.window.document.querySelectorAll('.going-global-nav a')].map(a=>a.querySelector('path').getAttribute('d'));
 assert.equal(new Set(icons).size,links.length,'six distinct icons');
 const {icon}=dom.window.GoingVisual,d=n=>new dom.window.DOMParser().parseFromString(icon(n),'text/html').querySelector('path').getAttribute('d');
 assert.deepEqual(icons,['home','football','market','baseball','people','bars'].map(d));
 dom.window.close();
});
test('shell publishes the Missions route and the home page links to it',()=>{
 assert.match(read('shared/going-shell.js'),/\['missions','Missions','\/missions\/'\]/);
 assert.match(read('hub/index.html'),/href="\/missions\/"/);
 assert.ok(fs.existsSync(path.join(__dirname,'../apps/missions/index.html')));
 assert.match(read('scripts/build_vercel.mjs'),/'missions'/);
});
