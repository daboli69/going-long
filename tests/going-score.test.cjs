const {test}=require('node:test'),assert=require('node:assert/strict');
const {scoreRows,groupByGame,percentile,tier}=require('../shared/going-score.js');

test('GOING SCORE ranks the complete market field from available weighted evidence',()=>{
 const rows=[
  {player:'A',game:'A @ B',sampleGames:12,currentGames:6,components:{projection:{value:10,label:'Projection'},role:{value:8,label:'Role'},environment:{value:45,label:'Game'}}},
  {player:'B',game:'C @ D',sampleGames:6,currentGames:1,components:{projection:{value:5,label:'Projection'},role:{value:4,label:'Role'},environment:{value:40,label:'Game'}}},
  {player:'C',game:'A @ B',sampleGames:12,currentGames:0,components:{projection:{value:1,label:'Projection'},role:{value:2,label:'Role'},environment:{value:35,label:'Game'}}},
 ];
 const scored=scoreRows(rows,'receptions');
 assert.deepEqual(scored.map(row=>row.player),['A','B','C']);
 assert.equal(scored[0].rank,1);assert.equal(scored[0].score,100);assert.equal(scored[2].score,0);
 assert.equal(scored[0].confidence.label,'High');assert.equal(scored[1].confidence.label,'Limited');
 assert.equal(groupByGame(scored).find(group=>group.game==='A @ B').selections.length,2);
});

test('GOING SCORE renormalizes missing components instead of treating missing data as zero',()=>{
 const scored=scoreRows([
  {player:'Complete',sampleGames:12,currentGames:1,components:{projection:{value:10},role:{value:10},matchup:{value:10},environment:{value:10}}},
  {player:'Sparse',sampleGames:12,currentGames:1,components:{projection:{value:20},role:{value:null},matchup:{value:null},environment:{value:null}}},
 ],'pass_yds');
 const sparse=scored.find(row=>row.player==='Sparse');
 assert.equal(sparse.score,100);assert.ok(sparse.componentCoverage<.5);assert.equal(sparse.confidence.label,'Moderate');
});

test('percentiles and tiers are deterministic and score is not a probability field',()=>{
 assert.equal(percentile([1,2,3],2),50);assert.equal(tier(85).label,'Elite');assert.equal(tier(69.9).label,'Watch');
 const [row]=scoreRows([{player:'Only',sampleGames:12,currentGames:0,scoreProbability:.47,components:{projection:{value:.47}}}],'atd');
 assert.ok(row.score>55&&row.score<75);assert.equal(Object.hasOwn(row,'probability'),false);
});

test('Any TD is probability-led and does not force the slate leader toward 100',()=>{
 const rows=scoreRows([
  {player:'Henry-shaped',sampleGames:12,currentGames:1,probability:.713,scoreProbability:.48,components:{projection:{value:.48},role:{value:10},environment:{value:49}}},
  {player:'Lower',sampleGames:12,currentGames:1,probability:.35,scoreProbability:.34,components:{projection:{value:.34},role:{value:4},environment:{value:42}}},
 ],'atd');
 assert.equal(rows[0].player,'Henry-shaped');
 assert.ok(rows[0].score>=60&&rows[0].score<=75,`unexpected inflated score ${rows[0].score}`);
 assert.ok(rows[0].score<90);
 assert.ok(rows[0].score>rows[1].score);
});
