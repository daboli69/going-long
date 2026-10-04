'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process');
const core=require('../shared/abbeys-core.cjs');
const journal=require('../shared/ranking-journal.cjs');
const collector=require('../research/abbeys/collect.cjs');
function fixture() {
  const cutoff='2026-10-04T03:00:00Z',generated_at='2026-10-04T00:00:00Z';
  const games=[],results={};
  for (let week=1;week<=3;week++) {
    for (const [away,home,away_score,home_score] of [['ATL','NO',35,10],['BUF','NE',30,14]]) {
      const game_id=`2026_0${week}_${away}_${home}`,kickoff=`2026-09-${String(6+7*(week-1)).padStart(2,'0')}T17:00:00Z`;
      games.push({game_id,season:2026,week,away,home,kickoff,away_score,home_score});
      results[`nfl|${game_id}`]={id:game_id,sport:'nfl',away,home,kickoff,awayScore:away_score,homeScore:home_score};
    }
  }
  for (const [away,home,kickoff] of [['ATL','BUF','2026-10-04T13:30:00Z'],['NE','NO','2026-10-05T23:00:00Z'],['NO','BUF','2026-10-06T00:15:00Z'],['ATL','NE','2026-10-02T00:15:00Z']]) games.push({game_id:`2026_04_${away}_${home}`,season:2026,week:4,away,home,kickoff});
  return {schedule:{generated_at,season:2026,games},results:{generated_at,games:results},cutoff};
}
const predict=f=>core.predictWeek(core.projectSources(f.schedule,f.results,2026,f.cutoff),4);
test('ABBEYS whitelist excludes all books, historical stats, ratings and player indices',()=>{
  const f=fixture(),expected=predict(f);
  f.schedule.ratings={ATL:999};f.schedule.rating_calibration={slope:999};f.schedule.history={strong:999};
  f.schedule.games.forEach(g=>Object.assign(g,{home_ml:-9999,away_ml:10000,spread:-88,total:125,impliedProbability:.999,goingScore:100,prior_season_epa:999}));
  f.schedule.games.push({game_id:'2025_04_ATL_NO',season:2025,week:4,away:'ATL',home:'NO',kickoff:'2025-09-30T00:00:00Z',home_score:99,away_score:0});
  f.results.games.old={sport:'nfl',id:'2025_04_ATL_NO',home:'NO',away:'ATL',kickoff:'2025-09-30T00:00:00Z',homeScore:99,awayScore:0};
  f.schedule.marketContext={favorite:'BUF'};f.results.historicalTrends={ATL:'10-0'};
  assert.deepEqual(predict(f),expected);
  delete f.schedule.ratings;delete f.schedule.rating_calibration;delete f.results.historicalTrends;delete f.schedule.marketContext;
  assert.deepEqual(predict(f),expected);
});
test('legitimate same-season scoring changes can change a pick; same-week result cannot',()=>{
  const f=fixture(),base=predict(f);
  const g=f.schedule.games.find(g=>g.week===4&&g.away==='ATL'&&g.home==='NE');
  f.results.games.thursday={sport:'nfl',id:g.game_id,away:g.away,home:g.home,kickoff:g.kickoff,awayScore:99,homeScore:0};
  assert.deepEqual(predict(f),base);
  for (const r of Object.values(f.results.games).filter(r=>r.away==='ATL'&&r.home==='NO')) {r.awayScore=0;r.homeScore=80;}
  assert.notEqual(predict(f).picks[0].winner,base.picks[0].winner);
});
test('window includes Sunday international through final Monday, excludes Thursday and early Sunday',()=>{
  const f=fixture();f.schedule.games.push({game_id:'2026_04_KC_LV',season:2026,week:4,away:'KC',home:'LV',kickoff:'2026-10-04T12:00:00Z'});
  const board=predict(f);assert.equal(board.picks.length,3);assert.equal(board.monday.gameId,'2026_04_NO_BUF');
  assert.equal(board.picks[0].kickoff,'2026-10-04T13:30:00Z');
  assert.deepEqual(core.gameWindow(core.projectSources(f.schedule,f.results,2026,f.cutoff),5),[]);
});
test('NFL identifiers, duplicate records, invalid and future sources fail closed',()=>{
  for (const mutate of [f=>f.schedule.games.push({...f.schedule.games[0]}),f=>f.schedule.games[0].game_id='2026_typo',f=>Object.values(f.results.games)[0].id='2026_typo',f=>Object.values(f.results.games)[0].awayScore=null,f=>f.results.generated_at='2026-10-05T00:00:00Z',f=>Object.values(f.results.games)[0].home='KC']) {
    const f=fixture();mutate(f);assert.throws(()=>predict(f));
  }
  const f=fixture();f.cutoff='2026-10-04T13:30:00Z';assert.throws(()=>predict(f),/before its first kickoff/);
});
test('zero and tiny samples never import earlier seasons or invent a calibrated probability',()=>{
  const f=fixture();f.results.games={};const p=predict(f).picks[0];
  assert.equal(p.confidence,'No score evidence');assert.equal(p.projectedAway,null);assert.equal(p.projectedHome,null);assert.ok(['ATL','BUF'].includes(p.winner));assert.equal(p.winProbability,undefined);
  f.results.games={one:Object.values(fixture().results.games)[0]};assert.equal(predict(f).picks[0].confidence,'Limited evidence');
});
test('integer exact score remains nonnegative and consistent with winner at tied rounding',()=>{
  const g={away:'ATL',home:'NO'};
  for (const [away,home,winner] of [[21.2,21.3,'NO'],[21.4,21.1,'ATL'],[0,0,'ATL']]) {
    const p=core.integerScore(g,{away,home},winner);assert.ok(Number.isInteger(p.away)&&p.away>=0);assert.ok(Number.isInteger(p.home)&&p.home>=0);assert.equal(p.home>p.away?'NO':'ATL',winner);assert.notEqual(p.home,p.away);
  }
});
test('settlement identity is exact and ties remain ties rather than guessed wins',()=>{
  const p=predict(fixture()).picks[0],r={...p,awayScore:21,homeScore:21};
  assert.equal(core.settlementFor(p,r,'fixture','2026-10-04T20:00:00Z').outcome,'tie');
  assert.equal(core.settlementFor(p,{...r,gameId:'wrong'},'fixture','2026-10-04T20:00:00Z').state,'unresolved');
  assert.equal(core.settlementFor(p,r,'fixture','2026-10-04T13:00:00Z').state,'unresolved');
});
function temporarySource(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'going-abbeys-'));t.after(()=>{assert.equal(path.dirname(path.resolve(root)),path.resolve(os.tmpdir()));assert.ok(path.basename(root).startsWith('going-abbeys-'));fs.rmSync(root,{recursive:true,force:true});});
  const now=new Date(),season=now.getUTCFullYear(),sunday=new Date(now);sunday.setUTCDate(sunday.getUTCDate()+((7-sunday.getUTCDay())%7||7));sunday.setUTCHours(17,0,0,0);
  const f=fixture(),before=new Date(now.getTime()-3600000).toISOString();
  f.schedule.generated_at=before;f.schedule.season=season;f.results.generated_at=before;
  f.schedule.games=f.schedule.games.filter(g=>g.week<4 || (g.week===4&&g.home==='BUF'&&g.away==='ATL'));
  for (const g of f.schedule.games) {g.season=season;g.game_id=g.game_id.replace('2026',String(season));g.kickoff=(g.week===4?sunday:new Date(now.getTime()-(5-g.week)*7*86400000)).toISOString();}
  f.results.games={};for (const g of f.schedule.games.filter(g=>g.week<4)) f.results.games[g.game_id]={sport:'nfl',id:g.game_id,home:g.home,away:g.away,kickoff:g.kickoff,homeScore:g.home_score,awayScore:g.away_score};
  fs.mkdirSync(path.join(root,'data'),{recursive:true});fs.mkdirSync(path.join(root,'shared'));fs.mkdirSync(path.join(root,'research/abbeys'),{recursive:true});
  fs.writeFileSync(path.join(root,'data/nfl_betting.json'),JSON.stringify(f.schedule));fs.writeFileSync(path.join(root,'data/results.json'),JSON.stringify(f.results));
  fs.writeFileSync(path.join(root,'data/injury_context.json'),JSON.stringify({generated_at:before,season,current_reports:{},effects:{historicalForbidden:999}}));
  for (const file of ['shared/abbeys-core.cjs','research/abbeys/PROTOCOL.md']) fs.copyFileSync(path.resolve(file),path.join(root,file));
  const git=args=>cp.execFileSync('git',args,{cwd:root,encoding:'utf8',stdio:'pipe'});
  git(['init']);git(['config','user.name','Offline fixture']);git(['config','user.email','fixture@example.invalid']);git(['add','data/nfl_betting.json','data/results.json','data/injury_context.json','shared/abbeys-core.cjs','research/abbeys/PROTOCOL.md']);git(['commit','-m','fixture']);return {root,git};
}
test('official freeze is reproducible, immutable, duplicate-protected, anchored to Git, and context cannot change it',t=>{
  const {root,git}=temporarySource(t),captured=collector.capture(root,4,'manual');
  assert.equal(captured.picks,1);assert.deepEqual(collector.verify(root),{records:2,snapshots:1});
  const original=journal.readRecords(path.join(root,collector.JOURNAL))[0];
  assert.throws(()=>collector.capture(root,4,'manual'),/already frozen/);
  collector.materialize(root);assert.equal(journal.readRecords(path.join(root,collector.JOURNAL))[0].hash,original.hash);
  const records=journal.readRecords(path.join(root,collector.JOURNAL));
  git(['add',collector.JOURNAL,collector.BOARD]);git(['commit','-m','anchor']);
  collector.invalidate(root,captured.snapshotHash,'Corrupt input receipt','Public source correction receipt #fixture');
  assert.equal(collector.materialize(root).weeks[0].invalidations.length,1);
  assert.equal(journal.readRecords(path.join(root,collector.JOURNAL))[0].hash,original.hash);
  const tail=fs.readdirSync(path.join(root,collector.JOURNAL)).filter(f=>f.startsWith(String(records.length).padStart(12,'0')))[0];
  const newTail=fs.readdirSync(path.join(root,collector.JOURNAL)).find(f=>f.startsWith('000000000003'));
  fs.unlinkSync(path.join(root,collector.JOURNAL,newTail));fs.unlinkSync(path.join(root,collector.JOURNAL,tail));
  assert.throws(()=>collector.verify(root),/changed\/deleted/);
});
test('journal refuses process overlap, partial observations, and model/protocol reinterpretation',t=>{
  const {root}=temporarySource(t);collector.capture(root,4,'manual');const dir=path.join(root,collector.JOURNAL);
  fs.mkdirSync(path.join(dir,'.lock'));assert.throws(()=>collector.verify(root),/locked/);fs.rmdirSync(path.join(dir,'.lock'));
  fs.writeFileSync(path.join(dir,'.pending-interrupted'),'partial');assert.throws(()=>collector.verify(root),/Unexpected/);fs.unlinkSync(path.join(dir,'.pending-interrupted'));
  fs.appendFileSync(path.join(root,'research/abbeys/PROTOCOL.md'),'changed definitions');assert.throws(()=>collector.verify(root),/version\/input/);
});
test('holdout unlock is after January 16 and requires every scheduled Week18 game final',()=>{
  const schedule=[{gameId:'a',week:18,kickoff:'2027-01-10T18:00:00Z'}];
  assert.equal(collector.holdoutReleased({schedule,results:[{gameId:'a'}]},'2027-01-09T18:00:00Z'),false);
  assert.equal(collector.holdoutReleased({schedule,results:[]},'2027-01-16T18:00:00Z'),false);
  assert.equal(collector.holdoutReleased({schedule,results:[{gameId:'a'}]},'2027-01-16T18:00:00Z'),true);
  const postponed=[{gameId:'a',week:18,kickoff:'2027-01-20T18:00:00Z'}];
  assert.equal(collector.holdoutReleased({schedule:postponed,results:[{gameId:'a'}]},'2027-01-21T18:00:00Z'),false);
  assert.equal(collector.holdoutReleased({schedule:postponed,results:[{gameId:'a'}]},'2027-01-23T18:00:00Z'),true);
});
test('later public final results append without changing the original prediction; conflicting scores stay unresolved',t=>{
  const {root,git}=temporarySource(t),captured=collector.capture(root,4,'manual');
  const initial=journal.readRecords(path.join(root,collector.JOURNAL))[0],pick=initial.payload.prediction.picks[0];
  const later=Date.parse(pick.kickoff)+8*3600000;t.mock.timers.enable({apis:['Date'],now:later});
  const file=path.join(root,'data/results.json'),results=JSON.parse(fs.readFileSync(file));results.generated_at=new Date(later-60000).toISOString();
  results.games[pick.gameId]={sport:'nfl',id:pick.gameId,away:pick.away,home:pick.home,kickoff:pick.kickoff,awayScore:35,homeScore:10};
  fs.writeFileSync(file,JSON.stringify(results));git(['add','data/results.json']);git(['commit','-m','public result fixture']);
  assert.equal(collector.settle(root).appended,1);assert.equal(journal.readRecords(path.join(root,collector.JOURNAL))[0].hash,captured.snapshotHash);
  assert.equal(collector.materialize(root).weeks[0].picks[0].settlement.actualAway,35);
  assert.equal(collector.settle(root).appended,0);
  results.games[pick.gameId].awayScore=34;fs.writeFileSync(file,JSON.stringify(results));git(['add','data/results.json']);git(['commit','-m','corrected evidence fixture']);
  assert.equal(collector.settle(root).conflicts,1);assert.equal(collector.materialize(root).weeks[0].picks[0].settlement,null);
  assert.equal(journal.readRecords(path.join(root,collector.JOURNAL))[0].hash,initial.hash);
});
test('ABBEYS public board uses existing Git-backed snapshot delivery with a strict filename',async()=>{
  const {default:handler}=await import('../api/snapshot.mjs'),before=global.fetch;let calls=0;
  const response=()=>({headers:{},setHeader(k,v){this.headers[k]=v;},end(body){this.body=body;}});
  try {
    global.fetch=async url=>{calls++;assert.equal(String(url),'https://raw.githubusercontent.com/daboli69/going-long/main/data/abbeys-board.json');return Response.json({schemaVersion:1,weeks:[]});};
    const res=response();await handler({method:'GET',url:'/api/snapshot?file=abbeys-board.json'},res);assert.equal(res.statusCode,200);assert.equal(res.headers['X-Snapshot-Source'],'nightly');
    const bad=response();await handler({method:'GET',url:'/api/snapshot?file=abbeys/../../secret'},bad);assert.equal(bad.statusCode,400);assert.equal(calls,1);
  } finally {global.fetch=before;}
});
test('two concurrent collectors cannot create two official snapshots for a week',async t=>{
  const {root}=temporarySource(t),script=path.resolve('research/abbeys/collect.cjs');
  function run(){return new Promise(resolve=>{const child=cp.spawn(process.execPath,[script,'capture',root,'4','manual'],{stdio:'ignore'});child.on('close',resolve);});}
  const exits=await Promise.all([run(),run()]);assert.equal(exits.filter(x=>x===0).length,1);assert.equal(exits.filter(x=>x!==0).length,1);
  assert.equal(collector.verify(root).snapshots,1);
});
test('Monday exact-score grading uses frozen integers and appends actual score errors',t=>{
  const {root,git}=temporarySource(t),file=path.join(root,'data/nfl_betting.json'),schedule=JSON.parse(fs.readFileSync(file));
  const sunday=schedule.games.find(g=>g.week===4),monday={...sunday,game_id:sunday.game_id.replace('ATL_BUF','NE_NO'),away:'NE',home:'NO',kickoff:new Date(Date.parse(sunday.kickoff)+27*3600000).toISOString()};
  schedule.games.push(monday);fs.writeFileSync(file,JSON.stringify(schedule));git(['add','data/nfl_betting.json']);git(['commit','-m','Monday schedule fixture']);
  collector.capture(root,4,'manual');const before=collector.materialize(root).weeks[0].monday;
  const later=Date.parse(monday.kickoff)+8*3600000;t.mock.timers.enable({apis:['Date'],now:later});
  const resultFile=path.join(root,'data/results.json'),results=JSON.parse(fs.readFileSync(resultFile));results.generated_at=new Date(later-60000).toISOString();results.games[monday.game_id]={sport:'nfl',id:monday.game_id,away:monday.away,home:monday.home,kickoff:monday.kickoff,awayScore:17,homeScore:27};
  fs.writeFileSync(resultFile,JSON.stringify(results));git(['add','data/results.json']);git(['commit','-m','Monday final fixture']);collector.settle(root);
  const after=collector.materialize(root).weeks[0].monday;
  assert.equal(after.predictedAway,before.predictedAway);assert.equal(after.predictedHome,before.predictedHome);
  assert.equal(after.settlement.awayAbsoluteError,Math.abs(17-before.predictedAway));assert.equal(after.settlement.homeAbsoluteError,Math.abs(27-before.predictedHome));
});
