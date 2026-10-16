const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const O=require('../shared/td-opportunity.js');
const NOW=Date.parse('2026-10-17T12:00:00Z'),KICK='2026-10-18T17:00:00Z';
const sr=(o={})=>({version:1,as_of:'2026-10-11',n:12,confidence:'ok',xtd_pg_l12:.4,xtd_pg_l6:.5,snap_pct_l3:.7,snap_pct_l6:.65,inside5_touch_pg_l12:.5,rz_tgt_pg_l12:1.2,gl_carry_pg_l12:0,td_pg_l12:.4,td_luck_l12:0,tier:'PRIMARY',trend:{d_xtd36:0,d_snap36:0},...o});
const prof=(s,extra={})=>({id:'p',name:'P',scoring_role:s,role_trend:{last_game:{season:2026,week:5}},...extra});
const d=(s,extra,ctx)=>O.describe(prof(s,extra),{now:NOW,kickoff:KICK,...ctx});

test('a recorded zero is a real zero; a missing value is missing and never rendered as zero',()=>{
 const x=d(sr({gl_carry_pg_l12:0,rz_tgt_pg_l12:null}));
 assert.equal(x.metrics.gl_carry_pg_l12.observed,true);assert.equal(x.metrics.gl_carry_pg_l12.value,0);
 assert.equal(x.metrics.rz_tgt_pg_l12.observed,false);assert.equal(x.metrics.rz_tgt_pg_l12.value,null);
 assert.ok(x.missing.includes('rz_tgt_pg_l12')&&!x.missing.includes('gl_carry_pg_l12'));
 assert.match(x.lines.join(' '),/0\.0 goal-line carries/);assert.doesNotMatch(x.lines.join(' '),/red-zone/);
 assert.match(x.flags.join(' '),/Not available: red-zone targets per game/i);
 const absent=d(sr({}),{});delete absent.x;assert.equal(O.describe({id:'q'},{now:NOW,kickoff:KICK}).status,'missing');
 const dropped=sr({});delete dropped.xtd_pg_l6;assert.equal(d(dropped).metrics.xtd_pg_l6.observed,false);
});
test('point in time: future-dated or post-game role data is invalid, stale data is labelled, small samples are flagged',()=>{
 assert.equal(d(sr({as_of:'2026-10-18'}),{},{kickoff:'2026-10-18T00:00:00Z'}).status,'invalid');
 assert.equal(d(sr({as_of:'2026-10-25'})).status,'invalid');
 assert.equal(d(sr({as_of:'not a date'})).status,'invalid');
 assert.equal(d(sr()).status,'ok');
 const old=d(sr({as_of:'2026-09-01'}));assert.equal(old.status,'stale');assert.match(old.reasons[0],/days old/);
 const lastSeason=O.describe({scoring_role:sr({as_of:'2026-01-04'}),role_trend:{last_game:{season:2025,week:18}}},{now:NOW,kickoff:KICK});
 assert.equal(lastSeason.status,'stale');assert.match(lastSeason.reasons[0],/2025 season/);
 assert.equal(d(sr({confidence:'low'})).status,'low_sample');assert.equal(d(sr({n:4})).status,'low_sample');
});
test('role change names its drivers and ignores noise below the descriptive cutoffs',()=>{
 const up=d(sr({trend:{d_snap36:.12,d_xtd36:0}})).roleChange;assert.equal(up.direction,'up');assert.match(up.drivers[0],/snap share \+12 pts/);
 assert.equal(d(sr({trend:{d_snap36:.04,d_xtd36:.02}})).roleChange.direction,'steady');
 assert.equal(d(sr({trend:{d_snap36:-.15,d_xtd36:0}})).roleChange.direction,'down');
 assert.equal(d(sr({trend:{d_snap36:.15,d_xtd36:-.06}})).roleChange.direction,'mixed');
 assert.match(d(sr({trend:{d_snap36:.12}})).flags.join(' '),/trending up: snap share \+12 pts \(last 3 games vs last 6\)/);
 assert.equal(d(sr({trend:null})).roleChange,null);
});
test('the touchdown-luck note states it is not a skill estimate',()=>{
 assert.match(d(sr({td_luck_l12:.31})).flags.join(' '),/more touchdowns than expected.*not a skill estimate/);
 assert.equal(d(sr({td_luck_l12:.03})).flags.filter(f=>/expected over 12/.test(f)).length,0);
});
test('ranking is by expected touchdowns per game, drops unusable profiles and is deterministic',()=>{
 const item=(id,s,extra,ctx)=>({id,player:id,opportunity:d(s,extra,ctx)});
 const rows=[item('b',sr({xtd_pg_l6:.4,xtd_pg_l12:.3})),item('a',sr({xtd_pg_l6:.4,xtd_pg_l12:.3})),item('top',sr({xtd_pg_l6:.9})),item('stale',sr({xtd_pg_l6:2,as_of:'2026-08-01'})),
  item('future',sr({xtd_pg_l6:3,as_of:'2026-10-25'})),item('unobserved',(()=>{const x=sr();delete x.xtd_pg_l6;return x;})()),item('small',sr({xtd_pg_l6:.6,n:3,confidence:'low'}))];
 assert.deepEqual(O.rankByOpportunity(rows).map(r=>r.id),['top','small','a','b']);
 assert.deepEqual(O.rankByOpportunity([...rows].reverse()).map(r=>r.id),['top','small','a','b']);
});
test('real snapshot: no profile described as usable is stale, future-dated or built from another season',()=>{
 const profiles=Object.values(JSON.parse(fs.readFileSync('data/history.json','utf8')).betting.profiles),seen={};
 for(const p of profiles){const x=O.describe(p,{now:Date.parse('2026-10-17T12:00:00Z'),kickoff:KICK});seen[x.status]=(seen[x.status]||0)+1;
  if(['ok','low_sample'].includes(x.status)){assert.ok(x.ageDays<=O.MAX_AGE_DAYS&&x.ageDays>=0);assert.ok((p.role_trend?.last_game?.season??2026)>=2026);assert.ok(Date.parse(x.asOf)<Date.parse(KICK));}
 }
 assert.ok(seen.ok>0);
});
