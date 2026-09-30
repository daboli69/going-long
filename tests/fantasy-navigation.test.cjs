const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

test('Fantasy opens its overview and all dedicated sections preserve their controls',async()=>{
  const {JSDOM}=await import('jsdom');
  const html=fs.readFileSync('index.html','utf8');
  const dom=new JSDOM(html,{url:'https://going-long.vercel.app/long/?mode=fantasy',runScripts:'outside-only'});
  const {window:w}=dom;
  const scripts=[...w.document.querySelectorAll('script:not([src])')];
  const boot=scripts.find(s=>s.textContent.includes('var requestedMode'));
  const navigation=scripts.find(s=>s.textContent.includes('function setView(name)'));
  w.eval(boot.textContent);w.eval(navigation.textContent);
  assert.equal(w.document.querySelector('.gl-view.active').id,'view-fantasy');
  for(const section of ['leagues','rankings','waivers','trade','draft','fantasy']){
    w.document.querySelector(`#fantasyNav [data-view="${section}"]`).click();
    assert.equal(w.document.querySelector('.gl-view.active').id,`view-${section}`);
    assert.equal(w.document.querySelectorAll('.gl-view.active').length,1);
    assert.equal(w.document.body.classList.contains('fantasy-area'),true);
  }
  assert.ok(w.document.querySelector('#view-leagues #chopUsername'));
  assert.ok(w.document.querySelector('#view-rankings #chopWeeklyFile'));
  assert.equal(w.document.querySelectorAll('#chopWeeklyFile').length,1);
  assert.equal(w.document.querySelector('#clockBar').hidden,true);
  dom.window.close();
});
