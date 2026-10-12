const test=require('node:test'),assert=require('node:assert/strict');
const T=require('../shared/teammate-context.js');
const now=Date.parse('2026-10-12T20:00:00Z');
const candidate={sport:'nfl',kind:'prop',profileId:'a',team:'LA',player:'Adams',market:'rec_yds',kickoff:'2026-10-13T00:15:00Z'};
const game=(id,yards,pid='a')=>({game_id:`2026_0${id}_LA_BUF`,player_id:pid,team:'LA',kickoff:`2026-09-${String(id*6).padStart(2,'0')}T17:00:00Z`,offense_snaps:30,targets:id===1?6:9,receiving_yards:yards});
function context(){return {season:2026,scopes:{2026:{players:{p:{name:'Puka'}}}},picks_evidence:{season:2026,generated_at:'2026-10-12T18:00:00Z',provenance:{inputs:Object.fromEntries(['pbp','snap_counts','rosters','injury_reports'].map(k=>[k,{status:'loaded'}]))},recent_player_games:{'LA|a':{player_id:'a',team:'LA',position:'WR',games_log:[game(1,26),game(2,195),game(3,137),game(4,32)]},'LA|p':{player_id:'p',team:'LA',position:'WR',games_log:[game(1,74,'p'),game(4,125,'p')]}},teammate_out_games:{}}};}
test('coappearance reproduces Adams/Puka and leaves missing appearances unknown',()=>{
 const result=T.compare(context(),candidate,now),p=result.pairs[0];assert.equal(p.with.n,2);assert.equal(p.with.receiving_yards,29);assert.equal(p.with.targets,7.5);assert.equal(p.without.n,0);assert.equal(p.unknown,2);assert.equal(result.all.receiving_yards,97.5);
});
test('OUT needs explicit retrospective receipt; contradictory snaps remain unknown',()=>{
 const c=context();c.picks_evidence.teammate_out_games['LA|a|p']=[{game_id:'2026_02_LA_BUF',team:'LA',player_id:'p',report_status:'Out',report_timing:'retrospective'},{game_id:'2026_01_LA_BUF',team:'LA',player_id:'p',report_status:'Out',report_timing:'retrospective'}];const p=T.compare(c,candidate,now).pairs[0];assert.equal(p.without.n,1);assert.equal(p.with.n,1);assert.equal(p.unknown,2);
 c.picks_evidence.provenance.inputs.injury_reports.status='unavailable';assert.equal(T.compare(c,candidate,now).pairs[0].without.n,0);
});
test('source failures, stale/future stamps, duplicate logs and future appearances fail closed',()=>{
 for(const status of ['unavailable','stale']){const c=context();c.picks_evidence.provenance.inputs.snap_counts.status=status;assert.equal(T.compare(c,candidate,now).pairs.length,0);}
 for(const stamp of ['2026-10-10T18:00:00Z','2026-10-13T18:00:00Z']){const c=context();c.picks_evidence.generated_at=stamp;assert.equal(T.compare(c,candidate,now).pairs.length,0);}
 const c=context();c.picks_evidence.recent_player_games['LA|a'].games_log.push(game(1,26));assert.equal(T.compare(c,candidate,now).pairs.length,0);
 const future=context();future.picks_evidence.recent_player_games['LA|p'].games_log.forEach(g=>g.kickoff='2026-10-14T17:00:00Z');assert.equal(T.compare(future,candidate,now).pairs.length,0);
});
test('malformed calendar dates, hour24, offsets and naive timestamps cannot validate freshness',()=>{
 for(const stamp of ['2026-10-11T24:00:00Z','2026-02-30T18:00:00Z','2026-10-12T18:00:00+24:00','2026-10-12T18:00:00']){
  const c=context();c.picks_evidence.generated_at=stamp;assert.equal(T.compare(c,candidate,now).pairs.length,0);
 }
 const c=context();c.picks_evidence.recent_player_games['LA|p'].games_log.forEach(g=>g.kickoff='2026-09-06T24:00:00Z');assert.equal(T.compare(c,candidate,now).pairs.length,0);
});
test('identity, team and season mismatches do not create coappearances',()=>{
 for(const field of ['player_id','team','game_id']){const c=context();c.picks_evidence.recent_player_games['LA|p'].games_log.forEach(g=>g[field]='wrong');assert.equal(T.compare(c,candidate,now).pairs.length,0);}
});
test('malformed teammate records cannot crash the board or manufacture absences',()=>{
 for(const record of [null,{player_id:'p',team:'LA',position:'WR',games_log:[null]},{player_id:'p',team:'LA',position:'WR',games_log:{}}]){
  const c=context();c.picks_evidence.recent_player_games['LA|p']=record;
  assert.doesNotThrow(()=>T.panel(c,candidate,now,'p',0));assert.equal(T.compare(c,candidate,now).pairs.length,0);
 }
 const c=context();c.picks_evidence.current_roster={players:{}};c.picks_evidence.teammate_out_games['LA|a|p']={};assert.equal(T.compare(c,candidate,now).pairs[0].without.n,0);
});
test('panels escape player names, label uncertainty and never substitute missing reception counts',()=>{
 const c=context();c.scopes[2026].players.p.name='<img onerror=attack>';
 const html=T.panel(c,candidate,now,'p',0);assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img/);assert.match(html,/Receptions\/game: all Unknown/);assert.match(html,/2 game\(s\) have unknown/);assert.match(html,/do not change the projection/);
});
test('actual board integration preserves teammate selection, research disclosure and focus across refresh',()=>{
 const {JSDOM}=require('jsdom'),P=require('../shared/football-picks.js'),Board=require('../shared/tonight-board.js');
 global.GoingTeammateContext=T;
 const c={...candidate,home:'LA',away:'BUF',updatedAt:new Date(now-60000).toISOString(),book:'DraftKings',odds:-110,line:60.5,side:'Over',projMean:80,n:12};
 const e={key:'adams',gameKey:P.gameKey(c),eligible:true,interesting:true,family:'Receiving',rating:48,components:[],facts:[],price:P.quote(c,now)};
 const dom=new JSDOM('<div id="board"></div>'),host=dom.window.document.getElementById('board'),options={board:{picks:[{candidate:c,evidence:e,offers:[]}]},context:context(),schedule:[c],now};
 Board.render(host,options);const detail=host.querySelector('[data-tonight-detail]');detail.open=true;detail.ontoggle();
 const select=host.querySelector('[data-tonight-teammate]');select.value='p';select.focus();select.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
 Board.render(host,options);
 assert.equal(host.querySelector('[data-tonight-teammate]').value,'p');assert.equal(host.querySelector('[data-tonight-detail]').open,true);
 assert.equal(dom.window.document.activeElement.dataset.tonightTeammate,'0');assert.match(host.textContent,/29.0/);assert.equal(e.rating,48);assert.equal(c.projMean,80);
 delete global.GoingTeammateContext;
});
