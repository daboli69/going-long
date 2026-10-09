const {test}=require('node:test'),assert=require('node:assert/strict');
const G=require('../shared/going-score-player.js');

const comp=(contribution,percentile=50)=>({raw:1,percentile,weight:.1,z:1,contribution});
const doc={schema:'going-score-v2',methodology_version:'t',as_of:'2026-10-09',season:2026,week:6,counts:{},weights:{},meaning:'x',players:{
 a:{name:'Alpha',position:'WR',team:'AAA',score:90,absolute:80,tier:{id:'elite',label:'Elite'},delta_1w:2,delta_3w:12,flags:['ROLE_UP'],components:{opportunity:comp(1.2,95),role:comp(-.2,30),efficiency:comp(.1)}},
 b:{name:'Bravo',position:'WR',team:'BBB',score:60,absolute:50,tier:{id:'solid',label:'Solid'},delta_1w:null,delta_3w:-9,flags:['INJURY:Questionable knee'],components:{opportunity:comp(.2,60)}},
 c:{name:'Charlie',position:'RB',team:'AAA',score:75,absolute:70,tier:{id:'strong',label:'Strong'},delta_1w:-1,delta_3w:1,flags:[],components:{}},
}};

test('load rejects other schemas and indexes players by id',()=>{
 assert.equal(G.load({schema:'v1',players:{}}).ok,false);
 const l=G.load(doc);assert.equal(l.ok,true);assert.equal(l.byId.a.name,'Alpha');assert.equal(l.meta.week,6);
});
test('filter combines position, flag prefix and score floor',()=>{
 const {players}=G.load(doc);
 assert.deepEqual(G.filter(players,{position:'WR'}).map(p=>p.id),['a','b']);
 assert.deepEqual(G.filter(players,{flag:'INJURY'}).map(p=>p.id),['b']);
 assert.deepEqual(G.filter(players,{minScore:70,excludeFlag:'ROLE_UP'}).map(p=>p.id),['c']);
 assert.deepEqual(G.filter(players,{search:'brav'}).map(p=>p.id),['b']);
});
test('rank puts missing values last and is stable',()=>{
 const {players}=G.load(doc);
 assert.deepEqual(G.rank(players,'score').map(p=>p.id),['a','c','b']);
 assert.deepEqual(G.rank(players,'delta_1w').map(p=>p.id),['a','c','b']);
 assert.deepEqual(G.rank(players,'delta_1w','asc').map(p=>p.id),['c','a','b']);
});
test('movers apply the minimum change and split risers from fallers',()=>{
 const {players}=G.load(doc);const m=G.movers(players,{minAbsChange:5});
 assert.deepEqual(m.risers.map(p=>p.id),['a']);assert.deepEqual(m.fallers.map(p=>p.id),['b']);
});
test('drivers and compare use stored contributions only',()=>{
 const {byId}=G.load(doc);
 assert.equal(G.drivers(byId.a,1).up[0].key,'opportunity');assert.equal(G.drivers(byId.a,1).down[0].key,'role');
 const c=G.compare(byId.a,byId.b);assert.equal(c.samePosition,true);assert.equal(c.scoreGap,30);
 assert.equal(c.components.find(x=>x.key==='opportunity').edgeContribution,1);
 assert.equal(G.compare(byId.a,byId.c).samePosition,false);assert.equal(G.compare(null,byId.a),null);
});
test('groupByTier orders elite first and summary stays descriptive',()=>{
 const {players,byId}=G.load(doc);
 assert.deepEqual(G.groupByTier(players).map(g=>g.id),['elite','strong','solid']);
 assert.match(G.summary(byId.a),/Elite.*lifted by opportunity.*held back by role/);
});
