const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('Yard price research retains the full pool without suggesting unvalidated stakes',()=>{
 const html=fs.readFileSync('apps/yard/index.html','utf8'),start=html.indexOf('function renderQualified(){'),end=html.indexOf('// ===== TOP PICKS:',start),main={innerHTML:''};
 const candidates=Array.from({length:20},(_,i)=>({name:i===0?'<img src=x>':'Player '+i,propLabel:'Home Run',side:'Over',prob:.2,price:600,ev:i===0?.4:.1,fallback:i===1}));
 const context={document:{getElementById:()=>main},BOARD:{players:[]},getMinEdge:()=>4,allPropEV:()=>candidates,fmtAm:x=>'+'+x,americanFair:()=>400};
 vm.runInNewContext(html.slice(start,end)+'renderQualified();',context);
 assert.equal((main.innerHTML.match(/<article /g)||[]).length,20);
 assert.match(main.innerHTML,/No suggested stake/);assert.match(main.innerHTML,/review required/);
 assert.match(main.innerHTML,/Reference price not verified/);
 assert.match(main.innerHTML,/&lt;img src=x&gt;/);assert.doesNotMatch(main.innerHTML,/Total suggested exposure|½-Kelly|sharp money/);
});
