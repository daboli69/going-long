const {test}=require('node:test'),assert=require('node:assert/strict');
const E=require('../shared/going-eligibility.js');
const NOW=Date.parse('2026-10-11T12:00:00Z'),fresh='2026-10-11T08:00:00Z',old='2026-10-08T08:00:00Z';
const inj=(entries,reports={},generated_at=fresh)=>({generated_at,current_players:Object.fromEntries(Object.entries(entries).map(([id,rs])=>['T|'+id,{gsis_id:id,roster_status:rs,team:'AAA'}])),current_reports:Object.fromEntries(Object.entries(reports).map(([id,r])=>['T|'+id,{gsis_id:id,week:5,...r}]))});
const roster=(players=[],extra={})=>({generated_at:fresh,week:5,players,bye_carry_forward_teams:[],...extra});
const eng=(i,r=roster(),o={})=>E.create({injury:i,roster:r,week:5,now:NOW,...o});
const d=(e,id,extra={lastGame:'2026-10-04'})=>e.decide(id,extra);

test('every status class is distinguished and non-actionable when confirmed unavailable',()=>{
 const e=eng(inj({r:'RES',i:'INA',p:'PUP',s:'SUS',t:'RET',x:'EXE',c:'CUT',d:'DEV',a:'ACT'}));
 const st=Object.fromEntries(['r','i','p','s','t','x','c','d','a'].map(k=>[k,d(e,k)]));
 assert.deepEqual([st.r.state,st.i.state,st.p.state,st.s.state,st.t.state,st.x.state,st.c.state,st.d.state,st.a.state],['reserve','reserve','reserve','suspended','retired','exempt','released','practice_squad','active']);
 for(const k of ['r','i','p','s','t','x','c','d'])assert.equal(st[k].actionable,false,k);
 assert.equal(st.a.actionable,true);
});
test('stale or missing data fails closed for everyone, but confirmed statuses stay excluded',()=>{
 const staleInj=inj({a:'ACT',r:'RES'},{},old);
 const e=eng(staleInj);assert.equal(e.fresh.ok,false);
 assert.equal(d(e,'a').state,'unverified');assert.equal(d(e,'a').actionable,false);assert.equal(d(e,'r').state,'reserve');
 const missing=eng(null,roster());assert.equal(d(missing,'a').actionable,false);
 const staleRoster=eng(inj({a:'ACT'}),roster([],{generated_at:old}));assert.equal(d(staleRoster,'a').state,'unverified');
 assert.match(d(e,'a').detail,/stale or missing/);
});
test('unknown players are never assumed active; a player with no recent game is not current',()=>{
 const e=eng(inj({a:'ACT'}));
 assert.equal(d(e,'zzz').state,'unknown');assert.equal(d(e,'zzz').actionable,false);
 assert.equal(e.decide('a',{lastGame:'2026-08-01'}).state,'stale');
 assert.equal(e.decide('a',{lastGame:null,requireRecentGame:false}).state,'active');
});
test('bye teams and players with no upcoming game are not opportunities',()=>{
 const e=eng(inj({a:'ACT'}),roster([],{bye_carry_forward_teams:['AAA']}));
 assert.equal(d(e,'a').state,'bye');assert.equal(d(e,'a').actionable,false);
 assert.equal(eng(inj({a:'ACT'})).decide('a',{lastGame:'2026-10-04',hasGame:false}).state,'no_game');
});
test('current-week reports: Out/Inactive/Doubtful excluded, Questionable/DNP/limited kept with caution, old-week reports ignored',()=>{
 const rep=r=>d(eng(inj({a:'ACT'},{a:r})),'a');
 for(const s of ['Out','OUT','Inactive','Injured Reserve'])assert.equal(rep({report_status:s}).actionable,false,s);
 assert.equal(rep({report_status:'Doubtful'}).state,'doubtful');
 const q=rep({report_status:'Questionable'});assert.equal(q.actionable,true);assert.equal(q.caution,true);
 assert.equal(rep({report_status:'Game-time decision'}).caution,true);
 assert.equal(rep({practice_status:'Did Not Participate In Practice'}).caution,true);
 assert.equal(rep({practice_status:'Limited Participation in Practice'}).caution,true);
 assert.equal(rep({report_status:'Out',week:2}).state,'active');
});
test('last-minute inactive arriving in the latest refresh removes a previously active player',()=>{
 const before=d(eng(inj({a:'ACT'})),'a');assert.equal(before.actionable,true);
 const after=d(eng(inj({a:'ACT'},{a:{report_status:'Inactive'}})),'a');assert.equal(after.actionable,false);assert.equal(after.state,'out');
});
test('conflicting sources keep the more severe report; a reserve entry beats an ACT roster row',()=>{
 const r=roster([{id:'a',team:'AAA',roster_status:'ACT',injury:{report_status:'Out',week:5}},{id:'b',team:'AAA',roster_status:'ACT'}]);
 assert.equal(d(eng(inj({a:'ACT',b:'RES'},{a:{report_status:'Questionable'}}),r),'a').state,'out');
 assert.equal(d(eng(inj({a:'ACT',b:'RES'}),r),'b').state,'reserve');
});
test('IR with a published return week is stash-only and never actionable; blank statuses are unknown',()=>{
 const i=inj({a:'RES'});i.current_players['T|a'].expected_return_week=8;
 const x=d(eng(i),'a');assert.equal(x.state,'returning');assert.equal(x.stashOnly,true);assert.equal(x.actionable,false);
 const b=inj({a:'ACT'});b.current_players['T|a'].roster_status='';assert.equal(d(eng(b),'a').state,'unknown');
});
test('roster snapshot fills missing teams; legacy rollback switch cannot bypass freshness',()=>{
 const r=roster([{id:'q',team:'BBB',roster_status:'ACT'}]);
 assert.equal(d(eng(inj({}),r),'q').state,'active');
 globalThis.GOING_ELIGIBILITY_STRICT=false;try{assert.equal(d(eng(inj({a:'ACT'},{},old)),'a').actionable,false);assert.equal(d(eng(inj({a:'RES'},{},old)),'a').actionable,false);}finally{delete globalThis.GOING_ELIGIBILITY_STRICT;}
});

test('unrecognized injury reports cannot clear fresh active players',()=>{
 for(const report_status of ['UNKNOWN','BOGUS','uncertain']){
  assert.equal(d(eng(inj({a:'ACT'},{a:{report_status,week:5}})),'a').actionable,false);
  assert.equal(d(eng(inj({a:'ACT'}),roster([{id:'a',roster_status:'ACT',injury:{report_status,week:5}}])),'a').actionable,false);
 }
});
test('blockedIds includes everyone when data is stale',()=>{
 const e=eng(inj({a:'ACT',r:'RES'},{},old));const b=e.blockedIds({a:{},z:{}});assert.ok(b.has('a')&&b.has('r')&&b.has('z'));
 const f=eng(inj({a:'ACT',r:'RES'}));const c=f.blockedIds({a:{},z:{}});assert.ok(c.has('r')&&!c.has('a')&&c.has('z'));
});

test('unrecognized statuses and contradictory roster rows never clear an active injury row',()=>{
 for(const rs of ['BOGUS','',null,'RES','PS','IR']){
  const e=eng(inj({a:'ACT'}),roster([{id:'a',team:'AAA',roster_status:rs}]));
  assert.equal(d(e,'a').actionable,false,String(rs));
 }
 for(const rs of ['UNKNOWN','123',{},['ACT']])assert.equal(d(eng(inj({a:rs})),'a').actionable,false);
 assert.equal(d(eng(inj({a:' act '})),'a').actionable,true);
});

test('team contradictions, future appearances and unknown profile IDs fail closed',()=>{
 const e=eng(inj({a:'ACT'}),roster([{id:'a',team:'BBB',roster_status:'ACT'}]));
 assert.equal(d(e,'a').actionable,false);
 assert.equal(d(eng(inj({a:'ACT'})),'a',{team:'BBB',lastGame:'2026-10-04'}).actionable,false);
 assert.equal(d(eng(inj({a:'ACT'})),'a',{lastGame:'2026-10-12'}).actionable,false);
 assert.ok(eng(inj({a:'ACT'})).blockedIds({a:{},missing:{}}).has('missing'));
});

test('timestamp-only and malformed collections cannot verify availability or throw',()=>{
 for(const i of [{generated_at:fresh},[],{...inj({a:'ACT'}),current_reports:[]},{...inj({a:'ACT'}),current_players:{bad:null}},{...inj({a:'ACT'}),current_reports:{bad:{gsis_id:'a',report_status:['Out']}}}]){
  const e=eng(i);assert.equal(e.fresh.ok,false);assert.equal(d(e,'a').actionable,false);
 }
 for(const r of [{generated_at:fresh},[],roster('invalid'),roster([null]),roster([],{bye_carry_forward_teams:'AAA'})]){
  const e=eng(inj({a:'ACT'}),r);assert.equal(e.fresh.ok,false);assert.equal(d(e,'a').actionable,false);
 }
 for(const generated_at of [12,'12','2026-10-11','2026-10-11T08:00:00','2026-10-12T08:00:00Z'])assert.equal(d(eng(inj({a:'ACT'},{},generated_at)),'a').actionable,false);
});

test('whitespace statuses, old string weeks and duplicate rows retain conservative decisions',()=>{
 assert.equal(d(eng(inj({a:'ACT'},{a:{report_status:' Out '}})),'a').actionable,false);
 assert.equal(d(eng(inj({a:'ACT'},{a:{report_status:'Out',week:'2'}})),'a').actionable,true);
 const i=inj({a:'ACT'});i.current_players.duplicate={gsis_id:'a',roster_status:'RES',team:'AAA'};
 assert.equal(d(eng(i),'a').actionable,false);
 const r=roster([{id:'a',team:'AAA',roster_status:'RES'},{id:'a',team:'AAA',roster_status:'ACT'}]);
 assert.equal(d(eng(inj({}),r),'a').actionable,false);
});
