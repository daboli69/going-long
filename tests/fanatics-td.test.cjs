const {test}=require('node:test'),assert=require('node:assert/strict');
const F=require('../shared/fanatics-td.js');
const NOW=Date.parse('2026-10-11T12:00:00Z'),KICK='2026-10-11T17:00:00Z',FRESH='2026-10-11T11:55:00Z';
const leg=(id,american=300,p=.3,event='g'+id,over={})=>{
 const value={playerId:id,player:'Player '+id,team:'T'+id,opp:'O'+id,eventTeams:['T'+event,'O'+event],gameLabel:event,kickoff:KICK,probability:p,availability:'active',eligibility:{actionable:true,state:'active',label:'Active'},price:{american,source:'feed',book:'fanatics',updatedAt:FRESH},...over};
 value.event=F.gameIdentity(value);if(value.price)value.price={...value.price,contract:F.contract(id,value.event)};return value;
};
const run=(legs,terms={},more={})=>F.select(legs,{now:NOW,terms,...more});

test('malformed extreme feed prices cannot produce infinite or unserializable slips',()=>{
 assert.equal(run([leg('A',Number.MAX_VALUE),leg('B',Number.MAX_VALUE),leg('C',Number.MAX_VALUE)]).options.length,0);
 assert.equal(run([leg('A',1e308),leg('B',100),leg('C',100)]).options.length,0);
});
test('offer controls cannot weaken the +2000 floor; alternatives default to five and cap at fifty',()=>{
 for(const floor of [100,1999,-200])assert.throws(()=>F.validateTerms({minCombinedAmerican:floor}),/2000 or longer/);
 assert.equal(F.validateTerms({minCombinedAmerican:2500}).minCombinedAmerican,2500);
 assert.equal(run(Array.from({length:8},(_,i)=>leg(String(i)))).options.length,5);
 assert.equal(run(Array.from({length:8},(_,i)=>leg(String(i))),{optionCount:20}).options.length,20);
 assert.equal(run(Array.from({length:12},(_,i)=>leg(String(i))),{optionCount:500}).options.length,50);
});

test('American to decimal and back are exact',()=>{
 assert.equal(F.decimal(2000),21);assert.equal(F.decimal(-200),1.5);assert.equal(F.decimal(100),2);assert.equal(F.decimal(-100),2);
 assert.equal(F.decimal(0),null);assert.equal(F.decimal(50),null);assert.equal(F.decimal(NaN),null);
 assert.ok(Math.abs(F.american(21)-2000)<1e-9);assert.ok(Math.abs(F.american(1.5)+200)<1e-9);assert.equal(F.american(1),null);
});
test('a slip qualifies only when the full-precision decimal product is at least 21.00, never by its rounded display',()=>{
 const exactly=run([leg('A',200),leg('B',200),leg('C',250)]);// 3 x 3 x 3.5 = 31.5
 assert.equal(exactly.options.length,1);
 const boundary=run([leg('A',200),leg('B',200),leg('C',133.33333333333334)]);// 3 x 3 x 2.3333.. = 21.0000000000000 (within float noise)
 assert.equal(boundary.options.length,1);
 const below=run([leg('A',200),leg('B',200),leg('C',133)]);// 3 x 3 x 2.33 = 20.97 -> displays as +1997, not +2000
 assert.equal(below.options.length,0);
 const shy=run([leg('A',200),leg('B',200),leg('C',133.3)]);// 20.997 would display as +2000 when rounded
 assert.equal(shy.options.length,0);assert.equal(F.roundAmerican(F.american(3*3*(1+1.333)))>=1999,true);
});
test('exactly three distinct players from three different games',()=>{
 const r=run([leg('A'),leg('B'),leg('C'),leg('D')]);
 for(const o of r.options){assert.equal(o.legs.length,3);assert.equal(new Set(o.legs.map(l=>l.playerId)).size,3);assert.equal(new Set(o.legs.map(l=>l.event)).size,3);}
 assert.equal(r.options.length,4);// C(4,3)
 const sameGame=run([leg('A',300,.3,'x'),leg('B',300,.3,'x'),leg('C',300,.3,'y'),leg('D',300,.3,'y')]);
 assert.equal(sameGame.options.length,0);assert.match(sameGame.reasons.join(' '),/2 games/);
});
test('the same player listed twice is collapsed to the freshest price and cannot appear twice',()=>{
 const older=leg('A',300,.3,'gA',{price:{american:900,source:'feed',book:'fanatics',updatedAt:'2026-10-11T11:50:00Z'}});
 const r=run([older,leg('A',300),leg('B'),leg('C')]);
 assert.equal(r.eligiblePlayers,3);assert.equal(r.options.length,1);assert.equal(r.options[0].legs.find(l=>l.playerId==='A').price.american,300);
});
test('ranking is by joint probability, then lower payout, deterministically; independence product is exact',()=>{
 const legs=[leg('A',300,.6),leg('B',300,.5),leg('C',300,.4),leg('D',300,.1),leg('E',300,.05)];
 const r=run(legs);
 assert.deepEqual(r.options.map(o=>o.key),['A~B~C','A~B~D','A~C~D','B~C~D','A~B~E']);
 assert.ok(Math.abs(r.options[0].probability-.12)<1e-12);
 for(let i=1;i<r.options.length;i++)assert.ok(r.options[i-1].probability>=r.options[i].probability);
});
test('branch-and-bound search equals brute force on random pools',()=>{
 let seed=7;const rnd=()=>(seed=(seed*1664525+1013904223)%4294967296)/4294967296;
 for(let round=0;round<30;round++){
  const legs=[];for(let i=0;i<24;i++)legs.push(leg('P'+i,Math.round(150+rnd()*900),.03+rnd()*.56,'g'+Math.floor(rnd()*7)));
  const r=run(legs),n=legs.length,all=[];
  for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)for(let k=j+1;k<n;k++){
   const a=legs[i],b=legs[j],c=legs[k];if(new Set([a.event,b.event,c.event]).size<3)continue;
   const dec=F.decimal(a.price.american)*F.decimal(b.price.american)*F.decimal(c.price.american);if(dec+1e-9<21)continue;
   all.push({key:[a,b,c].map(l=>l.playerId).sort().join('~'),probability:a.probability*b.probability*c.probability,decimal:dec});
  }
  all.sort((x,y)=>y.probability-x.probability||x.decimal-y.decimal||(x.key<y.key?-1:1));
  assert.deepEqual(r.options.map(o=>o.key),all.slice(0,5).map(o=>o.key),'round '+round);
 }
});
test('fewer than five valid slips are shown as is with an explanation, never padded',()=>{
 const r=run([leg('A',300),leg('B',300),leg('C',300)]);
 assert.equal(r.options.length,1);assert.match(r.reasons.join(' '),/Only 1 distinct slip/);
 assert.equal(run([]).options.length,0);assert.match(run([]).reasons.join(' '),/No leg has a usable Fanatics price/);
 assert.match(run([leg('A'),leg('B')]).reasons.join(' '),/Only 2 eligible players/);
 const lowPayout=run([leg('A',-300),leg('B',-300),leg('C',-300)]);assert.equal(lowPayout.options.length,0);
});
test('missing, other-book, stale, expired-manual and invalid prices are never used',()=>{
 const base=[leg('B'),leg('C')];
 const cases={'No Fanatics price':leg('A',300,.3,'g',{price:null}),'Other sportsbook price':leg('A',300,.3,'g',{price:{american:300,source:'feed',book:'fanduel',updatedAt:FRESH}}),
  'Price needs refreshing':leg('A',300,.3,'g',{price:{american:300,source:'feed',book:'fanatics',updatedAt:'2026-10-11T11:30:00Z'}}),
  'Entered price expired':leg('A',300,.3,'g',{price:{american:300,source:'manual',book:'fanatics',updatedAt:'2026-10-11T09:00:00Z'}}),
  'Invalid price':leg('A',50,.3,'g',{price:{american:50,source:'feed',book:'fanatics',updatedAt:FRESH}})};
 for(const [why,bad] of Object.entries(cases)){const r=run([bad,...base]);assert.equal(r.excluded[why],1,why);assert.equal(r.eligiblePlayers,2,why);assert.equal(r.options.length,0,why);}
 const future=run([leg('A',300,.3,'g',{price:{american:300,source:'feed',book:'fanatics',updatedAt:'2026-10-11T13:00:00Z'}}),...base]);assert.equal(future.excluded['Price needs refreshing'],1);
 const manualFresh=run([leg('A',300,.3,'g',{price:{american:300,source:'manual',book:'fanatics',updatedAt:'2026-10-11T10:30:00Z'}}),...base]);assert.equal(manualFresh.options.length,1);
});
test('unavailable, unknown, bye and unverified players cannot be recommended; missing eligibility fails safe',()=>{
 const base=[leg('B'),leg('C')];
 const decisions={'Not eligible: Reserve / injured list':{actionable:false,state:'reserve',label:'Reserve / injured list'},'Not eligible: Team on bye':{actionable:false,state:'bye',label:'Team on bye'},
  'Not eligible: Availability unverified':{actionable:false,state:'unverified',label:'Availability unverified'},'Not eligible: Ruled out':{actionable:false,state:'out',label:'Ruled out'},
  'Not eligible: Practice squad':{actionable:false,state:'practice_squad',label:'Practice squad'},'Not eligible: Availability unconfirmed':{actionable:false,state:'unknown',label:'Availability unconfirmed'}};
 for(const [why,eligibility] of Object.entries(decisions)){const r=run([leg('A',300,.3,'g',{eligibility}),...base]);assert.equal(r.excluded[why],1,why);assert.equal(r.options.length,0,why);}
 assert.equal(run([leg('A',300,.3,'g',{eligibility:null}),...base]).excluded['Eligibility not verified'],1);
 assert.equal(run([leg('A',300,.3,'g',{eligibility:{state:'active'}}),...base]).options.length,0);// actionable must be exactly true
 for(const availability of ['questionable','unavailable','unknown',undefined])assert.equal(run([leg('A',300,.3,'g',{availability}),...base]).options.length,0,String(availability));
 assert.equal(run([leg('A',300,.3,'g',{availability:'expected'}),...base]).options.length,1);
});
test('started games, invalid model inputs and extreme estimates are excluded',()=>{
 const base=[leg('B'),leg('C')];
 assert.equal(run([leg('A',300,.3,'g',{kickoff:'2026-10-11T11:00:00Z'}),...base]).excluded['Game started or time unavailable'],1);
 assert.equal(run([leg('A',300,.3,'g',{kickoff:'garbage'}),...base]).options.length,0);
 for(const p of [0,1,-.1,1.2,NaN,null,'0.3'])assert.equal(run([leg('A',300,p),...base]).options.length,0,String(p));
 assert.equal(run([leg('A',300,.9),...base]).options.length,1);
 assert.equal(run([leg('A',300,.9),...base],{maxLegProbability:.6}).excluded['Above configured probability cap'],1);
 assert.equal(run([{...leg('A'),playerId:null},...base]).excluded['Missing player or game identity'],1);
 assert.equal(run([null,undefined,...base]).options.length,0);
});
test('terms are validated; individual-leg minimum and excluded players are honoured',()=>{
 assert.throws(()=>F.validateTerms({legs:4}),/exactly three/);assert.throws(()=>F.validateTerms({minCombinedAmerican:50}),/2000 or longer/);assert.throws(()=>F.validateTerms({minimumLegAmerican:10}),/Individual/);
 assert.throws(()=>F.validateTerms({quoteMaxAgeMinutes:0}),/age limits/);
 const r=run([leg('A',200),leg('B',300),leg('C',400)],{minimumLegAmerican:250});assert.equal(r.options.length,0);assert.equal(r.excluded['Below individual-leg minimum'],1);
 const x=run([leg('A'),leg('B'),leg('C')],{},{excludedPlayers:['A']});assert.equal(x.options.length,0);assert.equal(x.excluded['Excluded by you'],1);
 assert.equal(F.validateTerms({optionCount:99}).optionCount,50);assert.equal(F.validateTerms({}).optionCount,5);
 assert.throws(()=>F.validateTerms({maxPlayerAppearances:0}),/repeat limit/);
});
test('combined odds shown are the product of the three prices, with the combined American derived from it',()=>{
 const r=run([leg('A',250),leg('B',300),leg('C',400)]);const o=r.options[0];
 assert.ok(Math.abs(o.decimal-3.5*4*5)<1e-9);// 70.0 -> +6900
 assert.equal(F.roundAmerican(o.american),6900);assert.equal(F.fmtAmerican(o.american),'+6900');assert.equal(F.fmtAmerican(null),'n/a');
});
test('optional diversification caps how often one player repeats, but is off by default',()=>{
 const legs=[leg('A',300,.6),leg('B',300,.5),leg('C',300,.45),leg('D',300,.44),leg('E',300,.43),leg('F',300,.42),leg('G',300,.41)];
 const pure=run(legs);assert.ok(pure.options.filter(o=>o.legs.some(l=>l.playerId==='A')).length===5);
 const div=run(legs,{diversify:true,maxPlayerAppearances:3});assert.ok(Object.values(div.exposure).every(v=>v<=3));assert.equal(div.options.length,5);
});
test('manual Fanatics price entry matches players exactly and reports anything it cannot read',()=>{
 const pool=[{playerId:'1',player:'Josh Allen'},{playerId:'2',player:'Josh Allen'},{playerId:'3',player:'Amon-Ra St. Brown'},{playerId:'4',player:'José Ramírez'}];
 for(const p of pool)p.contract=F.contract(p.playerId,'game');
 const r=F.parseManualPrices('Amon-Ra St. Brown +120\nJose Ramirez, -150\nJosh Allen +300\nNobody Here +500\nbad line\nAmon-Ra St. Brown +10',pool,NOW);
 assert.deepEqual(r.entries.map(e=>[e.playerId,e.american]),[['3',120],['4',-150]]);
 assert.equal(r.errors.length,4);assert.match(r.errors.join(' '),/more than one player/);assert.match(r.errors.join(' '),/does not match/);assert.match(r.errors.join(' '),/Could not read/);assert.match(r.errors.join(' '),/invalid American/);
 assert.equal(F.parseManualPrices('',pool).entries.length,0);assert.equal(F.parseManualPrices(null,null).errors.length,0);
});
test('the terms file separates verified, user-supplied and unverified rules and never claims official verification',()=>{
 const cfg=require('../shared/fanatics-td-terms.js'),d=F.describeTerms(cfg);
 assert.ok(d.userSupplied.some(t=>t.key==='state'));assert.ok(d.unverified.length>=4);
 for(const t of Object.values(cfg.terms))assert.ok(['verified-secondary','user-supplied','conflicting','unverified'].includes(t.status),t.status);
 assert.ok(!Object.values(cfg.terms).some(t=>t.status==='verified'),'no term may be marked officially verified');
 assert.match(cfg.read_me,/could not be retrieved/);
});

test('a pool larger than the cap is truncated to the most likely scorers and says so',()=>{
 const legs=[];for(let i=0;i<650;i++)legs.push(leg('P'+i,300+i%50,.05+(i%50)/100,'g'+(i%9)));
 const r=run(legs);assert.equal(r.eligiblePlayers,600);assert.match(r.reasons.join(' '),/capped at the 600/);assert.equal(r.options.length,5);
});
test('a fresh typed price is used even when a newer-looking but stale feed quote exists (UI precedence is in buildLegs)',()=>{
 const stale=leg('A',300,.3,'g1',{price:{american:300,source:'feed',book:'fanatics',updatedAt:'2026-10-11T10:00:00Z'}});
 assert.equal(run([stale,leg('B'),leg('C')]).options.length,0);
});

test('exact integer +2000 boundaries qualify in every multiplication order without a below-floor tolerance',()=>{
 for(const prices of [[-150,180,350],[180,200,150]]){
  for(const order of [prices,[prices[1],prices[0],prices[2]],[prices[2],prices[1],prices[0]]]){
   assert.equal(run(order.map((price,i)=>leg(String(i),price,.5-i*.1))).options.length,1);
  }
  const below=prices.slice();below[1]-=1;
  assert.equal(run(below.map((price,i)=>leg(String(i),price))).options.length,0);
 }
});

test('strict clocks reject malformed dates, offsets, naive and future prices',()=>{
 for(const t of ['2026-02-30T12:00:00Z','2026-10-11T24:00:00Z','2026-10-11T11:59:00+00:60','2026-10-11T11:59:00+24:00','2026-10-11T11:59:00','bad'])assert.equal(F.timestampMs(t),null,t);
 for(const t of ['2026-10-11T12:00:00.001Z','2026-10-11T11:59:00','2026-10-11T11:59:00+00:60']){const a=leg('A');a.price.updatedAt=t;assert.equal(run([a,leg('B'),leg('C')]).options.length,0,t);}
 assert.equal(F.timestampMs('2026-10-11T13:00:00-04:00'),F.timestampMs(KICK));
});
test('canonical game identity rejects duplicate games, mixed Sundays and wrong selected date',()=>{
 const a=leg('A',300,.3,'same'),b=leg('B',300,.3,'same',{kickoff:'2026-10-11T13:00:00-04:00'});
 assert.equal(run([a,b,leg('C')]).options.length,0);
 assert.equal(run([leg('A'),leg('B'),leg('C',300,.3,'gC',{kickoff:'2026-10-18T17:00:00Z'})]).options.length,0);
 assert.equal(run([leg('A'),leg('B'),leg('C')],{},{slateDate:'2026-10-18'}).options.length,0);
 assert.equal(run([leg('A'),leg('B'),leg('C',300,.3,'gC',{kickoff:'2026-10-12T17:00:00Z'})]).options.length,0);
});
test('prices require explicit Fanatics source and matching player-game contract',()=>{
 for(const mutate of [a=>delete a.price.book,a=>delete a.price.source,a=>a.price.source='unknown',a=>delete a.price.contract,a=>a.price.contract=leg('OTHER').price.contract]){const a=leg('A');mutate(a);assert.equal(run([a,leg('B'),leg('C')]).options.length,0);}
 assert.equal(run([leg('A'),leg('A',300,.3,'other'),leg('B'),leg('C')]).options.length,0);
});
test('a below-floor price never qualifies inside an epsilon and caps are explicit only',()=>{
 const a=leg('A',200),b=leg('B',200),c=leg('C',133.333333330);
 assert.ok(F.decimal(a.price.american)*F.decimal(b.price.american)*F.decimal(c.price.american)<21);
 assert.equal(run([a,b,c]).options.length,0);
 assert.equal(F.DEFAULT_TERMS.maxLegProbability,null);
 assert.equal(run([leg('A',300,.9),leg('B'),leg('C')]).options.length,1);
});

// Independent reference: enumerate every valid slip, rank, then apply locks and the repeat cap greedily.
function reference(legs,{count=5,cap=null,locks=[],exclude=[]}={}){
 const ok=legs.filter(l=>!exclude.includes(l.playerId)||locks.includes(l.playerId)),all=[];
 for(let i=0;i<ok.length;i++)for(let j=i+1;j<ok.length;j++)for(let k=j+1;k<ok.length;k++){
  const t=[ok[i],ok[j],ok[k]];if(new Set(t.map(l=>l.event)).size<3)continue;if(!locks.every(id=>t.some(l=>l.playerId===id)))continue;
  const d=t.reduce((a,l)=>a*F.decimal(l.price.american),1);if(d<21-1e-9)continue;
  all.push({key:t.map(l=>l.playerId).sort().join('~'),p:t.reduce((a,l)=>a*l.probability,1),d});
 }
 all.sort((a,b)=>b.p-a.p||a.d-b.d||(a.key<b.key?-1:1));
 const seen={},out=[];for(const o of all){const ids=o.key.split('~');if(cap!=null&&ids.some(id=>!locks.includes(id)&&(seen[id]||0)>=cap))continue;out.push(o.key);ids.forEach(id=>seen[id]=(seen[id]||0)+1);if(out.length===count)break;}
 return out;
}
test('locked players build slips around them; at most three locks from different, usable games',()=>{
 const legs=[leg('A',300,.6),leg('B',300,.5),leg('C',300,.45),leg('D',300,.44),leg('E',300,.43),leg('F',300,.42)];
 const one=run(legs,{optionCount:10},{lockedPlayers:['E']});
 assert.equal(one.options.length,10);assert.ok(one.options.every(o=>o.legs.some(l=>l.playerId==='E')));assert.deepEqual(one.locked,['E']);
 const two=run(legs,{optionCount:10},{lockedPlayers:['E','F']});assert.equal(two.options.length,4);assert.ok(two.options.every(o=>['E','F'].every(id=>o.legs.some(l=>l.playerId===id))));
 const three=run(legs,{},{lockedPlayers:['D','E','F']});assert.deepEqual(three.options.map(o=>o.key),['D~E~F']);
 assert.match(run(legs,{},{lockedPlayers:['A','B','C','D']}).reasons.join(' '),/at most 3/);
 assert.match(run(legs,{},{lockedPlayers:['ZZ']}).reasons.join(' '),/not currently usable/);
 assert.equal(run(legs,{},{lockedPlayers:['ZZ']}).options.length,0);
 const same=[leg('A',300,.6,'x'),leg('B',300,.5,'x'),leg('C',300,.4),leg('D',300,.3)];
 assert.match(run(same,{},{lockedPlayers:['A','B']}).reasons.join(' '),/different games/);
 const lockedButExcluded=run(legs,{},{lockedPlayers:['A'],excludedPlayers:['A','B']});assert.ok(lockedButExcluded.options.every(o=>o.legs.some(l=>l.playerId==='A')&&!o.legs.some(l=>l.playerId==='B')));
 const pool=run(legs,{},{lockedPlayers:['A'],excludedPlayers:['B']}).pool;assert.equal(pool.length,6);assert.equal(pool.find(p=>p.playerId==='A').locked,true);assert.equal(pool.find(p=>p.playerId==='B').excluded,true);
});
test('repeat limit caps every non-locked player and keeps the best slips that fit',()=>{
 const legs=[leg('A',300,.7),leg('B',300,.6),leg('C',300,.5),leg('D',300,.4),leg('E',300,.35),leg('F',300,.3),leg('G',300,.25),leg('H',300,.2)];
 for(const cap of [1,2,3]){const r=run(legs,{optionCount:20,maxPlayerAppearances:cap});assert.ok(Object.values(r.exposure).every(v=>v<=cap),String(cap));assert.deepEqual(r.options.map(o=>o.key),reference(legs,{count:20,cap}));}
 const locked=run(legs,{optionCount:6,maxPlayerAppearances:1},{lockedPlayers:['H']});
 assert.equal(locked.exposure.H,locked.options.length);assert.ok(Object.entries(locked.exposure).every(([id,v])=>id==='H'||v<=1));
 assert.match(run(legs,{optionCount:20,maxPlayerAppearances:1}).reasons.join(' '),/no player more than 1 time/);
});
test('engine matches the independent reference on random pools with locks, exclusions, counts and caps',()=>{
 let seed=7;const rnd=()=>(seed=(seed*16807)%2147483647)/2147483647;
 for(let t=0;t<300;t++){
  const n=4+Math.floor(rnd()*14),legs=[];
  for(let i=0;i<n;i++)legs.push(leg('P'+i,[150,200,250,300,400,600,900,-120][Math.floor(rnd()*8)],Math.round(rnd()*900+50)/1000,'g'+Math.floor(rnd()*6)));
  const ids=legs.map(l=>l.playerId),pickId=()=>ids[Math.floor(rnd()*ids.length)];
  const count=[1,5,10,25][Math.floor(rnd()*4)],cap=[null,1,2,3][Math.floor(rnd()*4)];
  const locks=rnd()<.5?[]:[...new Set(Array.from({length:1+Math.floor(rnd()*2)},pickId))],exclude=rnd()<.3?[pickId()]:[];
  const r=run(legs,{optionCount:count,maxPlayerAppearances:cap},{lockedPlayers:locks,excludedPlayers:exclude});
  if(r.lockError){assert.equal(r.options.length,0);continue;}
  assert.deepEqual(r.options.map(o=>o.key),reference(legs,{count,cap,locks,exclude}),JSON.stringify({t,count,cap,locks,exclude}));
 }
});
