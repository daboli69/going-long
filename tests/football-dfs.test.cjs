const {test}=require('node:test');
const assert=require('node:assert/strict');
const dfs=require('../shared/football-dfs.js');

test('DraftKings salary CSV preserves the actual slate, salaries and IDs',()=>{
 const csv='Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame\nQB,"Josh Allen (1)",Josh Allen,1,QB,8000,BUF@MIA 09/20/2026 01:00PM ET,BUF,24.5\nDST,"Bills (2)",Bills,2,DST,3200,BUF@MIA 09/20/2026 01:00PM ET,BUF,7.1';
 const parsed=dfs.parseSalaryCsv(csv);
 assert.equal(parsed.site,'draftkings');assert.equal(parsed.players.length,2);
 assert.deepEqual(
  Object.fromEntries(['id','name','position','salary','team','opponent','siteProjection'].map(key=>[key,parsed.players[0][key]])),
  {id:'1',name:'Josh Allen',position:'QB',salary:8000,team:'BUF',opponent:'MIA',siteProjection:24.5}
 );
 assert.equal(parsed.players[1].position,'DST');
});

test('FanDuel salary CSV supports quoted names and half-PPR scoring',()=>{
 const csv='Id,Position,Nickname,Salary,Game,Team,Opponent,FPPG,Injury Indicator\n9,WR,"Smith, Jr.",7200,BUF@MIA,BUF,MIA,14.2,Q';
 const parsed=dfs.parseSalaryCsv(csv);
 assert.equal(parsed.site,'fanduel');assert.equal(parsed.players[0].name,'Smith, Jr.');assert.equal(parsed.players[0].injury,'Q');
 const stats={pass_yds:300,pass_tds:2,rush_yds:100,rush_tds:1,rec_yds:100,rec_tds:1,receptions:8,pass_300_probability:.5,rush_100_probability:.25,rec_100_probability:.25};
 assert.equal(dfs.projectedPoints(stats,'draftkings'),63);
 assert.equal(dfs.projectedPoints(stats,'fanduel'),59);
});

test('optimizer produces legal, salary-capped and diversified classic lineups',()=>{
 const players=[],add=(position,count,start,teams)=>{for(let i=0;i<count;i++)players.push({id:position+i,name:position+i,position,salary:position==='QB'?7000:position==='DST'?3000:5500+(i%3)*300,team:teams[i%teams.length],opponent:teams[(i+1)%teams.length],projection:start-i*.4,sd:4});};
 add('QB',3,24,['A','B','C']);add('RB',7,20,['A','B','C','D']);add('WR',9,19,['A','B','C','D']);add('TE',4,15,['A','B','C','D']);add('DST',4,9,['A','B','C','D']);
 const result=dfs.optimize(players,{site:'draftkings',mode:'ceiling',count:3,minUnique:2});
 assert.equal(result.lineups.length,3);
 for(const lineup of result.lineups){assert.equal(lineup.players.length,9);assert.ok(lineup.salary<=50000);assert.equal(new Set(lineup.players.map(player=>player.id)).size,9);assert.ok(Object.keys(lineup.teams).length>=2);assert.deepEqual(lineup.players.map(player=>player.slot),dfs.RULES.draftkings.slots);}
 for(let i=1;i<result.lineups.length;i++)assert.ok(result.lineups[i].players.filter(player=>!result.lineups[0].ids.has(player.id)).length>=2);
});

test('optimizer excludes confirmed outs and reports a missing position',()=>{
 const result=dfs.optimize([{id:'q',name:'Only QB',position:'QB',salary:5000,team:'A',projection:20,injury:'O'}]);
 assert.equal(result.lineups.length,0);assert.match(result.reason,/No eligible/);
});
