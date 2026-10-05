'use strict';
// Offline, actual published inputs. Never fetch odds/provider endpoints.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {openSource}=require('../today-ranking/collect.cjs');
async function audit(root,at=new Date().toISOString()){
 const source=openSource(root,at),{context,w}=source;
 try{
  for(const asset of ['football-confidence','football-picks'])vm.runInContext(fs.readFileSync(path.join(root,'shared',asset+'.js'),'utf8'),context);
  w.inputs=Object.fromEntries(['history','data','football_context','injury_context','season_learning','players','nfl_betting','ncaa_lines','results'].map(k=>[k,JSON.parse(fs.readFileSync(path.join(root,'data',k+'.json'),'utf8'))]));
  await vm.runInContext(`(async()=>{const d=inputs;BET.config=d.data.betting||{};BET.history=d.history.betting;BET.context=d.football_context;BET.learning=d.season_learning;BET.injuryLearning=d.injury_context;BET.roster=d.players;BET.injuryContext=GoingFootballInjuries.createContext(BET.roster,BET.history.profiles,Date.now(),BET.injuryLearning);BET.nflData=d.nfl_betting;BET.ncaaData=d.ncaa_lines;BET.liveLoaded={nfl:true,ncaa:true};BET.props=await propsFromRealData();BET.games=gamesFromRealData();CONFIDENCE_RESULTS=d.results;globalThis.pickPool=goingPicksCandidates();globalThis.pickBoard=GoingFootballPicks.board(pickPool,c=>({...confidenceEvidenceOptions(c),context:BET.context,injuryLearning:BET.injuryLearning}));})()`,context);
  return {at,pool:JSON.parse(vm.runInContext('JSON.stringify(pickPool)',context)),board:JSON.parse(vm.runInContext('JSON.stringify(pickBoard)',context)),codeHashes:source.codeHashes};
 }finally{source.dom.window.close();}
}
module.exports={audit};
if(require.main===module)audit(path.resolve(__dirname,'../..')).then(x=>{const out=process.argv[2];if(out)fs.writeFileSync(out,JSON.stringify(x,null,2));console.log(JSON.stringify({at:x.at,pool:x.pool.length,picks:x.board.picks.length,excluded:x.board.excluded.length,games:[...new Set(x.board.picks.map(x=>x.evidence.gameKey))],leaders:x.board.picks.slice(0,8).map(x=>({bet:[x.candidate.player,x.candidate.side,x.candidate.line,x.candidate.market].join(' '),rating:x.evidence.rating,why:x.evidence.why,concern:x.evidence.concern}))},null,2));}).catch(e=>{console.error(e);process.exitCode=1;});
