const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('../shared/going-charts.js');
test('scatter draws labelled points, a fit and escapes names',()=>{
 const rows=[1,2,3,4,5].map(i=>({id:i,label:i===1?'<b>x</b>':'P'+i,x:i,y:2*i+1,href:'/players/?player='+i}));
 const html=C.scatter(rows,{identity:true,fit:true,xLabel:'Expected',yLabel:'Actual'});
 assert.match(html,/Fitted line: slope 2\.00, r² 1\.00, n 5/);assert.match(html,/&lt;b&gt;x&lt;\/b&gt;/);assert.doesNotMatch(html,/<b>x<\/b>/);assert.equal((html.match(/<circle/g)||[]).length,5);
 assert.match(C.scatter([],{}),/No data/);assert.match(C.scatter([{label:'n',x:NaN,y:1}]),/No data/);
});
test('regression needs 3 points and non-constant x; bars, lines and reliability tolerate gaps',()=>{
 assert.equal(C.regression([{x:1,y:1},{x:2,y:2}]),null);assert.equal(C.regression([{x:1,y:1},{x:1,y:2},{x:1,y:3}]),null);
 assert.match(C.bars([{label:'A',value:3},{label:'B',value:-2},{label:'C',value:NaN}]),/<rect/);
 assert.match(C.lines([{name:'s',points:[{x:1,y:.2},{x:2,y:null},{x:3,y:.4}]}],{percent:true}),/20%/);
 assert.match(C.reliability([{p:.1,observed:.12,n:50},{p:.5,observed:.45,n:80}]),/Predicted 10%/);assert.equal(C.sparkline([1]),'');
});
