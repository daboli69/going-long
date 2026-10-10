const {test}=require('node:test'),assert=require('node:assert/strict');
const T=require('../shared/going-targets.js');
const NOW=Date.parse('2026-10-10T12:00:00Z'),recent='2026-10-04';
const prof=(id,pos,trend,extra={})=>({id,name:'P'+id,position:pos,team:'AAA',last_game:recent,role_trend:trend,...extra});
const share=(l6,l3)=>({l6,l3,l1:l3});
const rising={snap_share:share(60,75),target_share:share(.15,.24),carry_share:share(0,0),games:6,last6_current_season:6};
const flatT={snap_share:share(70,70),target_share:share(.2,.2),carry_share:share(0,0),games:6,last6_current_season:6};
const falling={snap_share:share(80,60),target_share:share(.25,.15),carry_share:share(0,0),games:6,last6_current_season:6};
const ovpRow=(id,pos,exp,act,g=5)=>({id,name:'P'+id,pos,team:'AAA',g,exp_pg:exp,act_pg:act,trend3:{exp_pg:exp,act_pg:act,res_pg:act-exp,games:[[2,exp,act],[3,exp,act],[4,exp,act]]}});
const inj=(entries,reports={})=>({generated_at:'2026-10-10T00:00:00Z',current_players:Object.fromEntries(Object.entries(entries).map(([id,rs])=>['AAA|'+id,{gsis_id:id,roster_status:rs}])),current_reports:Object.fromEntries(Object.entries(reports).map(([id,r])=>['AAA|'+id,{gsis_id:id,week:5,...r}]))});
const field=(n)=>Array.from({length:n},(_,i)=>ovpRow('f'+i,'WR',6+i,6+i));
const base=(profiles,ovp,injury,score={})=>({profiles,ovp:{players:[...field(10),...ovp]},injury,score:{players:score},week:5,now:NOW});
const ids=(r,c)=>r.categories[c].map(x=>x.id);

test('buy-low needs real opportunity, no shrinking role and a meaningful gap; low-opportunity underperformers are not targets',()=>{
 const profiles={a:prof('a','WR',flatT),b:prof('b','WR',flatT),c:prof('c','WR',falling)};
 const inj1=inj({a:'ACT',b:'ACT',c:'ACT'});
 const r=T.fantasyTargets(base(profiles,[ovpRow('a','WR',15,10),ovpRow('b','WR',3,0),ovpRow('c','WR',15,10)],inj1));
 assert.deepEqual(ids(r,'buy_low'),['a']);// b: low opportunity; c: role shrinking
});
test('emerging requires a growing role and GOING Score; sell-high needs overperformance without opportunity',()=>{
 const profiles={a:prof('a','WR',rising),d:prof('d','WR',flatT)};
 const r=T.fantasyTargets(base(profiles,[ovpRow('a','WR',12,12),ovpRow('d','WR',3,8)],inj({a:'ACT',d:'ACT'}),{a:{score:70,rank:10,of:100},d:{score:20,rank:90,of:100}}));
 assert.deepEqual(ids(r,'emerging'),['a']);assert.deepEqual(ids(r,'sell_high'),['d']);
 const r2=T.fantasyTargets(base(profiles,[ovpRow('a','WR',12,12)],inj({a:'ACT'}),{a:{score:10,rank:90,of:100}}));
 assert.deepEqual(ids(r2,'emerging'),[]);
});
test('reserve, IR, suspended, practice squad, unknown and stale players are never actionable and are listed as unavailable',()=>{
 const profiles={r:prof('r','WR',rising),s:prof('s','WR',rising),u:prof('u','WR',rising),old:prof('old','WR',rising,{last_game:'2026-08-01'}),ok:prof('ok','WR',rising),dv:prof('dv','WR',rising)};
 const sc=k=>({score:80,rank:1,of:10});
 const r=T.fantasyTargets(base(profiles,['r','s','u','old','ok','dv'].map(i=>ovpRow(i,'WR',14,14)),inj({r:'RES',s:'SUS',old:'ACT',ok:'ACT',dv:'DEV'}),{r:sc(),s:sc(),u:sc(),old:sc(),ok:sc(),dv:sc()}));
 assert.deepEqual(ids(r,'emerging'),['ok']);
 const un=Object.fromEntries(r.unavailable.map(x=>[x.id,x.availability.state]));
 assert.equal(un.r,'reserve');assert.equal(un.s,'reserve');assert.equal(un.u,'unknown');assert.equal(un.old,'stale');assert.equal(un.dv,'inactive_roster');
 assert.match(T.availability('r',profiles.r,T.indexInjury(inj({r:'RES'})),NOW).detail,/not automatically season-ending/);
});
test('IR with a published return week is a labelled stash-only state, never actionable',()=>{
 const i=inj({r:'RES'});i.current_players['AAA|r'].expected_return_week=8;
 const a=T.availability('r',prof('r','WR',rising),T.indexInjury(i),NOW);
 assert.equal(a.state,'returning');assert.equal(a.actionable,false);assert.equal(a.stashOnly,true);assert.match(a.detail,/week 8/);
});
test('game status and practice participation: out and doubtful excluded, questionable and DNP kept with a caution',()=>{
 const P=prof('x','WR',rising),f=(rep)=>T.availability('x',P,T.indexInjury(inj({x:'ACT'},{x:rep}),5),NOW);
 assert.equal(f({report_status:'Out'}).actionable,false);assert.equal(f({report_status:'Doubtful'}).actionable,false);
 const q=f({report_status:'Questionable'});assert.equal(q.actionable,true);assert.equal(q.caution,true);
 assert.equal(f({practice_status:'Did Not Participate In Practice'}).caution,true);
 assert.equal(f({practice_status:'Full Participation in Practice'}).state,'active');
 const stale=T.availability('x',P,T.indexInjury(inj({x:'ACT'},{x:{report_status:'Out',week:2}}),5),NOW);assert.equal(stale.state,'active');// an old week's report is ignored
});
test('betting targets: unavailable players excluded; unpriced are research targets; extreme or huge-EV value is withheld',()=>{
 const profiles={a:prof('a','WR',rising),b:prof('b','WR',rising),c:prof('c','WR',rising),d:prof('d','WR',rising)};
 const cand=(id,over={})=>({kind:'prop',profileId:id,player:'P'+id,market:'rec_yds',side:'Over',line:60.5,odds:-110,dec:1.91,prob:.55,ev:.05,calibrated:false,book:'bk',...over});
 const r=T.bettingTargets({profiles,injury:inj({a:'ACT',b:'RES',c:'ACT',d:'ACT'}),week:5,now:NOW},[cand('a'),cand('b'),cand('c',{prob:.93,ev:.6}),]);
 const by=Object.fromEntries(r.targets.filter(x=>x.market==='rec_yds').map(x=>[x.id,x]));
 assert.ok(!by.b);assert.ok(r.excluded.some(x=>x.id==='b'&&/Reserve/.test(x.reason)));
 assert.equal(by.a.status,'Priced research target');assert.equal(by.a.ev,null);assert.equal(by.a.evUnavailable,true);assert.match(by.a.calibration,/Raw model/);
 assert.equal(by.c.ev,null);assert.equal(by.c.evWithheld,true);assert.match(by.c.status,/needs review/);
 assert.equal(by.d.priced,false);assert.equal(by.d.ev,null);assert.match(by.d.status,/no price/);
});
test('betting direction follows the role: shrinking role points to Unders, flat role gives no target',()=>{
 const profiles={f:prof('f','WR',falling),z:prof('z','WR',flatT)};
 const r=T.bettingTargets({profiles,injury:inj({f:'ACT',z:'ACT'}),week:5,now:NOW},[]);
 assert.ok(r.targets.every(t=>t.id!=='z'));assert.equal(r.targets.find(t=>t.id==='f'&&t.market==='rec_yds').direction,'Under');
});
test('betting targets use the main line, not alternate or extreme ladder rungs, and rank without using EV',()=>{
 const profiles={a:prof('a','WR',rising)};
 const mk=(line,odds,dec,prob,ev)=>({kind:'prop',profileId:'a',player:'Pa',market:'rec_yds',side:'Over',line,odds,dec,prob,ev,book:'b'});
 const r=T.bettingTargets({profiles,injury:inj({a:'ACT'}),week:5,now:NOW},[mk(60.5,-110,1.91,.52,.04),mk(65.5,110,2.1,.4,.1),mk(55.5,-130,1.77,.6,.02),mk(174.5,3500,36,.02,.9)]);
 const t=r.targets.find(x=>x.market==='rec_yds');assert.equal(t.line,60.5);assert.equal(t.status,'Priced research target');
 const neg=T.bettingTargets({profiles,injury:inj({a:'ACT'}),week:5,now:NOW},[mk(60.5,-110,1.91,.4,-.2),{...mk(60.5,-110,1.91,.6,.1),side:'Under'}]).targets.find(x=>x.market==='rec_yds');assert.equal(neg.status,'Priced, no value at this price');
});

test('value is shrunk to the de-vigged price: a 60% model on a fair 50/50 market gives about 0.15 weight, not the model EV',()=>{
 const profiles={a:prof('a','WR',rising)};
 const over={kind:'prop',profileId:'a',market:'rec_yds',side:'Over',line:60.5,odds:-110,dec:1.909,prob:.6,ev:.145,book:'b'},under={...over,side:'Under',prob:.4,ev:-.24};
 const t=T.bettingTargets({profiles,injury:inj({a:'ACT'}),week:5,now:NOW},[over,under]).targets.find(x=>x.market==='rec_yds');
 const q=.5+.15*(.6-.5);assert.ok(Math.abs(t.ev-(q*1.909-1))<1e-9);assert.ok(t.ev<t.evModelOnly);
});

test('bye teams, blank statuses and roster-snapshot fallback',()=>{
 const P={...prof('k','TE',rising),team:'KC'},roster={bye_carry_forward_teams:['KC'],players:[{id:'k',team:'KC',roster_status:'ACT'},{id:'z',team:'AAA',roster_status:'ACT',injury:{report_status:'Out',week:5}}]};
 const idx=T.indexInjury(inj({}),5,roster);
 assert.equal(T.availability('k',P,idx,NOW).state,'bye');
 assert.equal(T.availability('z',prof('z','WR',rising),idx,NOW).state,'out');
 assert.equal(T.availability('q',prof('q','WR',rising),T.indexInjury(inj({}),5,{players:[{id:'q',team:'AAA',roster_status:'ACT'}]}),NOW).state,'active');
 const blank=inj({x:'ACT'});blank.current_players['AAA|x'].roster_status='';assert.equal(T.availability('x',prof('x','WR',rising),T.indexInjury(blank,5),NOW).state,'unknown');
 assert.match(T.availability('s',prof('s','WR',rising),T.indexInjury(inj({s:'SUS'}),5),NOW).detail,/Suspended/);
 assert.equal(T.availability('x',prof('x','WR',rising),T.indexInjury(inj({x:'ACT'},{x:{report_status:'Inactive'}}),5),NOW).actionable,false);
 assert.equal(T.availability('x',prof('x','WR',rising),T.indexInjury(inj({x:'ACT'},{x:{report_status:'Game-time decision'}}),5),NOW).caution,true);
});
