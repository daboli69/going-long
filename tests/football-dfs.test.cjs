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

test('DraftKings Showdown CPT and FLEX rows keep distinct IDs, exact salaries and one athlete per lineup',()=>{
 const athletes=[
  {name:'Josh Allen',position:'QB',team:'BUF',salary:8000,projection:27},
  {name:'James Cook',position:'RB',team:'BUF',salary:6500,projection:18},
  {name:'Khalil Shakir',position:'WR',team:'BUF',salary:5500,projection:16},
  {name:'Tua Tagovailoa',position:'QB',team:'MIA',salary:7500,projection:22},
  {name:'De\'Von Achane',position:'RB',team:'MIA',salary:6000,projection:17},
  {name:'Tyreek Hill',position:'WR',team:'MIA',salary:8500,projection:20},
 ];
 const rows=['Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame'];
 for(const athlete of athletes)for(const role of ['CPT','FLEX']){
  const id=`${athlete.name.replace(/[^A-Za-z]/g,'').toLowerCase()}-${role.toLowerCase()}`,salary=athlete.salary*(role==='CPT'?1.5:1);
  rows.push(`${athlete.position},"${athlete.name} (${id})","${athlete.name}",${id},${role},${salary},"BUF@MIA 10/04/2026 01:00PM ET",${athlete.team},${athlete.projection}`);
 }
 const parsed=dfs.parseSalaryCsv(rows.join('\n'));
 assert.equal(parsed.site,'draftkings');assert.equal(parsed.players.length,12);assert.deepEqual(parsed.errors,[]);
 const allenCaptain=parsed.players.find(player=>player.name==='Josh Allen'&&player.showdownRole==='CPT');
 const allenFlex=parsed.players.find(player=>player.name==='Josh Allen'&&player.showdownRole==='FLEX');
 assert.notEqual(allenCaptain.id,allenFlex.id);assert.equal(allenCaptain.salary,12000);assert.equal(allenFlex.salary,8000);
 const players=parsed.players.map(player=>({...player,projection:athletes.find(athlete=>athlete.name===player.name).projection,sd:3}));
 const result=dfs.optimize(players,{site:'draftkings',contest:'showdown',captainId:allenCaptain.id,lockedIds:[allenCaptain.id],now:Date.parse('2026-10-03T17:00:00Z'),count:1,minUnique:1});
 assert.equal(result.lineups.length,1,result.reason);const lineup=result.lineups[0],captain=lineup.players[0];
 assert.equal(captain.id,allenCaptain.id);assert.equal(captain.slot,'CPT');assert.equal(captain.salary,12000);assert.equal(captain.multiplier,1.5);
 assert.equal(lineup.salary,46000);assert.equal(lineup.projection,133.5);
 assert.equal(new Set(lineup.players.map(player=>`${dfs.norm(player.name)}|${player.team}`)).size,6);
 assert.ok(lineup.players.slice(1).every(player=>player.showdownRole==='FLEX'&&player.multiplier===1));
 assert.ok(lineup.players.every(player=>player.id.endsWith(player.showdownRole.toLowerCase())));
});

test('single-game optimizer rejects a pool containing multiple games',()=>{
 const players=[{id:'a',name:'Player A',position:'QB',salary:5000,projection:20,team:'A',opponent:'B',game:'A@B'},
  {id:'b',name:'Player B',position:'QB',salary:5000,projection:19,team:'B',opponent:'A',game:'A@B'},
  {id:'c',name:'Player C',position:'QB',salary:5000,projection:18,team:'C',opponent:'D',game:'C@D'}];
 const result=dfs.optimize(players,{site:'draftkings',contest:'showdown'});
 assert.equal(result.lineups.length,0);assert.match(result.reason,/one game/i);
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

test('projection-only mode needs neither salary nor DST and does not claim a capped lineup',()=>{
 const players=[],add=(position,count,start,teams)=>{for(let i=0;i<count;i++)players.push({id:position+i,name:position+i,position,team:teams[i%teams.length],opponent:teams[(i+1)%teams.length],projection:start-i*.3,sd:4});};
 add('QB',3,24,['A','B','C']);add('RB',7,20,['A','B','C','D']);add('WR',9,19,['A','B','C','D']);add('TE',4,15,['A','B','C','D']);
 const result=dfs.optimize(players,{site:'draftkings',count:2,minUnique:2,projectionOnly:true});
 assert.equal(result.projectionOnly,true);assert.equal(result.lineups.length,2);assert.deepEqual(result.rule.slots,['QB','RB','RB','WR','WR','WR','TE','FLEX']);
 for(const lineup of result.lineups){assert.equal(lineup.players.length,8);assert.equal(lineup.salary,0);assert.ok(lineup.players.every(player=>player.salary==null));}
});

test('single-game mode assigns one 1.5x Captain or MVP and includes both teams',()=>{
 const players=Array.from({length:10},(_,i)=>({id:String(i),name:'Player '+i,position:i<2?'QB':i<5?'RB':'WR',salary:5000,team:i<6?'A':'B',opponent:i<6?'B':'A',projection:22-i,sd:4}));
 for(const site of ['draftkings','fanduel']){
  const result=dfs.optimize(players,{site,contest:'showdown',count:1});assert.equal(result.lineups.length,1);const lineup=result.lineups[0],multiplier=site==='fanduel'?'MVP':'CPT';
  assert.deepEqual(lineup.players.map(player=>player.slot),[multiplier,'FLEX','FLEX','FLEX','FLEX','FLEX']);assert.equal(lineup.players[0].multiplier,1.5);assert.ok(lineup.players.slice(1).every(player=>player.multiplier===1));assert.equal(lineup.players.length,6);assert.equal(new Set(lineup.players.map(player=>player.name)).size,6);assert.equal(Object.keys(lineup.teams).length,2);assert.equal(lineup.salary,32500);assert.equal(lineup.projection,lineup.players.reduce((sum,player)=>sum+player.projection*player.multiplier,0));
 }
});

test('optimizer includes every user-selected player in every generated roster',()=>{
 const players=[],add=(position,count,start,teams)=>{for(let i=0;i<count;i++)players.push({id:position+i,name:position+i,position,team:teams[i%teams.length],opponent:teams[(i+1)%teams.length],projection:start-i*.3,sd:4});};
 add('QB',3,24,['A','B','C']);add('RB',7,20,['A','B','C','D']);add('WR',9,19,['A','B','C','D']);add('TE',4,15,['A','B','C','D']);
 const lockedIds=['QB2','RB6','WR8','TE3'],result=dfs.optimize(players,{site:'draftkings',count:3,minUnique:1,projectionOnly:true,lockedIds});
 assert.equal(result.lineups.length,3);
 for(const lineup of result.lineups){const ids=new Set(lineup.players.map(player=>player.id));for(const id of lockedIds)assert.ok(ids.has(id),`${id} was not locked`);assert.deepEqual(lineup.players.map(player=>player.slot),['QB','RB','RB','WR','WR','WR','TE','FLEX']);}
});

test('single-game Captain lock occupies the multiplier slot and unavailable locks fail clearly',()=>{
 const players=Array.from({length:10},(_,i)=>({id:String(i),name:'Player '+i,position:i<2?'QB':i<5?'RB':'WR',salary:5000,team:i<6?'A':'B',opponent:i<6?'B':'A',projection:22-i,sd:4}));
 const result=dfs.optimize(players,{site:'draftkings',contest:'showdown',count:2,lockedIds:['8'],captainId:'7'});
 assert.equal(result.lineups.length,2);for(const lineup of result.lineups){assert.equal(lineup.players[0].id,'7');assert.equal(lineup.players[0].slot,'CPT');assert.equal(lineup.players[0].multiplier,1.5);assert.ok(lineup.ids.has('8'));}
 const invalid=dfs.optimize(players,{site:'draftkings',contest:'showdown',lockedIds:['missing']});assert.equal(invalid.lineups.length,0);assert.match(invalid.reason,/selected player is unavailable/i);
});

test('classic search retains affordable players below position score cutoffs',()=>{
 const players=[],add=(position,count,salary,projection)=>{for(let i=0;i<count;i++)players.push({id:position+i,name:position+i,position,salary,projection:projection-i*.01,team:i%2?'A':'B',opponent:i%2?'B':'A'});};
 add('QB',61,25000,35);add('RB',65,25000,30);add('WR',95,25000,25);add('TE',61,25000,20);add('DST',61,25000,10);
 for(const [position,count]of [['QB',1],['RB',3],['WR',4],['TE',1],['DST',1]])for(let i=0;i<count;i++)players.push({id:'cheap'+position+i,name:'Cheap '+position+i,position,salary:3000,projection:1,team:i%2?'A':'B',opponent:i%2?'B':'A'});
 const result=dfs.optimize(players,{count:1,beamWidth:40});
 assert.equal(result.lineups.length,1,result.reason);const lineup=result.lineups[0];
 assert.equal(lineup.players.length,9);assert.ok(lineup.salary<=50000);assert.equal(lineup.ids.size,9);assert.ok(Object.keys(lineup.teams).length>=2);
});

test('salary-diverse beam keeps a feasible lower-scoring partial roster',()=>{
 const teams=['A','B','C'],players=[],add=(position,count,salary,projection)=>{for(let i=0;i<count;i++)players.push({id:position+i,name:position+i,position,salary,projection:projection-i*.1,team:teams[i%3],opponent:teams[(i+1)%3]});};
 add('QB',3,14000,40);add('RB',4,9000,30);add('WR',5,9000,25);add('TE',2,7000,20);add('DST',2,3000,10);
 for(const [position,count]of [['QB',1],['RB',3],['WR',4],['TE',1]])for(let i=0;i<count;i++)players.push({id:'value'+position+i,name:'Value '+position+i,position,salary:3000,projection:3,team:teams[i%3],opponent:teams[(i+1)%3]});
 for(const site of ['draftkings','fanduel']){
  const result=dfs.optimize(players,{site,count:1,beamWidth:20,lockedIds:['valueWR3']});
  assert.equal(result.lineups.length,1,result.reason);assert.ok(result.lineups[0].salary<=dfs.RULES[site].cap);assert.ok(result.lineups[0].ids.has('valueWR3'));
  assert.ok(Object.values(result.lineups[0].teams).every(count=>count<=dfs.RULES[site].maxTeam));
 }
});

test('affordability pruning still rejects genuinely over-budget Classic and Captain locks',()=>{
 const players=[],positions=['QB','RB','RB','RB','WR','WR','WR','WR','TE','DST'];
 positions.forEach((position,i)=>players.push({id:String(i),name:'Player '+i,position,salary:10000,projection:20,team:['A','B','C'][i%3],opponent:['A','B','C'][(i+1)%3]}));
 for(const site of ['draftkings','fanduel']){const result=dfs.optimize(players,{site,count:1});assert.equal(result.lineups.length,0);assert.match(result.reason,/salary cap/);}
 const showdown=dfs.optimize(players,{contest:'showdown',captainId:'0',count:1});assert.equal(showdown.lineups.length,0);assert.match(showdown.reason,/salary cap/);
});

test('affordable showdown candidates survive score cutoff with multiplier lock',()=>{
 const players=Array.from({length:95},(_,i)=>({id:'exp'+i,name:'Expensive '+i,position:'WR',salary:30000,projection:50-i*.1,team:i%2?'A':'B',opponent:i%2?'B':'A'}));
 for(let i=0;i<7;i++)players.push({id:'value'+i,name:'Value '+i,position:'WR',salary:4000,projection:2,team:i%2?'A':'B',opponent:i%2?'B':'A'});
 for(const site of ['draftkings','fanduel']){
  const result=dfs.optimize(players,{site,contest:'showdown',count:1,beamWidth:8,captainId:'value0'});
  assert.equal(result.lineups.length,1,result.reason);assert.equal(result.lineups[0].players[0].id,'value0');assert.ok(result.lineups[0].salary<=dfs.RULES[site].cap);
 }
});


test('tournament build excludes object OUT/roster codes and started players without fake uncertainty fallback',()=>{
 const players=[];for(let i=0;i<9;i++)players.push({id:'t'+i,name:'Fixture '+i,position:i===0?'QB':'WR',team:i<5?'BUF':'MIA',opponent:i<5?'MIA':'BUF',game:'BUF@MIA',salary:4000,projection:20-i,kickoff:'2026-10-05T23:30:00Z'});
 players[8].upside={value:100,source:'observed-partial-fantasy-residual-v1',n:12,currentGames:4,asOf:'2026-10-05T22:00:00Z'};
 const opts={contest:'showdown',mode:'tournament',count:1,now:Date.parse('2026-10-05T23:00:00Z')};
 const result=dfs.optimize(players,opts);assert.equal(result.lineups.length,1);assert.ok(result.lineups[0].players.some(p=>p.id==='t8'));
 for(const injury of [{state:'out'},'INA','RES']){players[8].injury=injury;assert.ok(!dfs.optimize(players,opts).lineups[0].players.some(p=>p.id==='t8'));}delete players[8].injury;
 assert.equal(dfs.optimize(players,{...opts,now:Date.parse('2026-10-06T00:00:00Z')}).lineups.length,0);
});
