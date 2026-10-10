'use strict';
// Headless Classic DFS pipeline on the FROZEN 2026-10-04 pregame inputs (tests/fixtures/dfs-pregame-20261004.json.gz) and a salary CSV you supply.
// It reuses the production inline model (attachProjection from index.html, read-only) exactly as tests/dfs-team-evidence.test.cjs does. Read-only: no network, no writes
// except the JSON you ask for with --out. Never run against private files that must not leave your machine without checking --out.
//   node scripts/dfs_headless.cjs --csv "C:/path/DKSalaries (2).csv" --out pool.json [--own classic_ownership_model.json] [--modes best,measured,tournament]
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto'),vm=require('node:vm');
const arg=name=>{const i=process.argv.indexOf('--'+name);return i>=0?process.argv[i+1]:null;};
const root=path.resolve(__dirname,'..');
const csvPath=arg('csv'),outPath=arg('out'),fieldPath=arg('field');
if(!csvPath){console.error('--csv is required');process.exit(2);}
const frozen=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root,'tests/fixtures/dfs-pregame-20261004.json.gz'))));
const values={};for(const [name,entry] of Object.entries(frozen.files)){if(crypto.createHash('sha256').update(entry.raw).digest('hex')!==entry.sha256)throw Error('fixture hash mismatch');values[name]=JSON.parse(entry.raw);}
const h=values.history.betting,c=values.football_context,roster=values.nfl_roster,inj=values.injury_context;
const inputTimes=[values.dfs_team_touchdowns.generatedAt,h.generated_at,c.generated_at,roster.generated_at,inj.generated_at].map(Date.parse);
const liveNow=Math.max(...inputTimes)+60000;
const availability=require('../shared/dfs-availability.js'),classic=require('../shared/dfs-classic.js'),evidence=require('../shared/dfs-evidence.js'),sim=require('../shared/dfs-sim.js'),field=require('../shared/dfs-classic-field.js'),football=require('../shared/football-dfs.js');
const injuryContext=availability.createContext(roster,h.profiles,liveNow,inj);
const source=require('../research/today-ranking/collect.cjs').openSource(root,new Date(liveNow).toISOString());
source.w.dfsFixture={history:h,context:c,injuryContext};
vm.runInContext("BET.history=dfsFixture.history;BET.context=dfsFixture.context;BET.injuryContext=dfsFixture.injuryContext;globalThis.dfsInlineModel=(profile,market,salary)=>attachProjection({player:profile.name,team:profile.team,market,kickoff:salary.kickoff,eventTeams:[salary.team,salary.opponent],source:'projection'},buildProfileIndex(BET.history));",source.context);
const text=fs.readFileSync(csvPath,'utf8');
if(arg('showdown')!==null&&process.argv.includes('--showdown')){showdown();process.exit(0);}
const parsed=classic.parseCsv(text);
if(parsed.errors.length){console.error(parsed.errors.join('\n'));process.exit(1);}
const ownPath=arg('own');if(ownPath){const r=field.load(fs.readFileSync(ownPath,'utf8'));if(!r.ok)throw Error(r.reason);}
const pool=evidence.buildPool(parsed.players,{profiles:h.profiles,context:c,injuryContext,generatedAt:h.generated_at,now:liveNow,injuries:availability,makeModel:source.w.dfsInlineModel,
 bonusProbability:(row,line)=>row?source.w.propProbabilities({...row,line})?.over:null,points:football.projectedPoints});
sim.assignRoles(pool);if(field.ready())field.annotate(pool);
const slim=p=>({id:p.id,name:p.name,position:p.position,team:p.team,opponent:p.opponent,salary:p.salary,projection:p.projection,matched:p.matched,unavailable:!!p.unavailable,sd:p.distribution?.sd??null,p90:p.distribution?.p90??null,boom:p.distribution?.boom??null,tdMean:p.tdMean,ownership:p.ownership??null,role:p.dfsRole??null,avgPointsPerGame:p.avgPointsPerGame});
const result={liveNow:new Date(liveNow).toISOString(),rows:parsed.players.length,usable:pool.filter(p=>!p.unavailable&&p.projection>0).length,pool:pool.map(slim)};
const modes=(arg('modes')||'').split(',').filter(Boolean);
result.lineups={};
for(const mode of modes){const r=classic.optimize(pool,{mode,now:new Date(liveNow).toISOString()});
 if(!r.lineup.length){result.lineups[mode]={reason:r.reason};continue;}
 const dst=r.lineup.find(p=>p.position==='DST'),moments=classic.measuredMoments(r.lineup),own=field.ready()?field.lineupOwnership(r.lineup):null;
 result.lineups[mode]={ids:r.lineup.map(p=>p.id),players:r.lineup.map(p=>p.name+' ('+p.position+' '+p.team+')'),projection:+r.projection.toFixed(2),salary:r.salaryUsed,sd:+moments.sd.toFixed(2),p90:+(moments.mean+1.2816*moments.sd).toFixed(2),
  dstVsOwnOffence:r.lineup.filter(p=>p.position!=='DST'&&p.team===dst?.opponent).length,qbStack:r.lineup.filter(p=>['WR','TE'].includes(p.position)&&p.team===r.lineup[0].team).length,vsBest:r.vsBest||null,ownership:own&&{raw:+own.total.toFixed(1),expected:own.expected?+own.expected.toFixed(1):null,fieldTypical:own.fieldTypical?+own.fieldTypical.toFixed(1):null}};}
source.dom.window.close();
if(outPath)fs.writeFileSync(outPath,JSON.stringify(result));else console.log(JSON.stringify({liveNow:result.liveNow,rows:result.rows,usable:result.usable,lineups:result.lineups},null,1));
process.exit(0);

// --showdown: single-game CSV (CPT + FLEX rows). Projections for QB/RB/WR/TE come from the same evidence pool; D/ST and K use the platform average (D/ST sd = realised 5.8).
// --field showdown_models.json (private, read-only) enables ownership/duplication. Prints one line per style so identical rosters are visible.
function showdown(){
 const rows=football.parseSalaryCsv(text).players;if(!rows.length)throw Error('no Showdown rows');
 const flex=rows.filter(r=>r.showdownRole==='FLEX');
 const evid=evidence.buildPool(flex.map(r=>({...r,avgPointsPerGame:r.siteProjection??0,kickoff:r.kickoff})),{profiles:h.profiles,context:c,injuryContext,generatedAt:h.generated_at,now:liveNow,injuries:availability,makeModel:source.w.dfsInlineModel,bonusProbability:(row,line)=>row?source.w.propProbabilities({...row,line})?.over:null,points:football.projectedPoints});
 const info=new Map(evid.map(p=>[p.name+'|'+p.team,p]));
 const players=rows.flatMap(r=>{const e=info.get(r.name+'|'+r.team);let projection=null,sd=null;
  if(r.position==='DST'||r.position==='K'){projection=r.siteProjection>0?r.siteProjection:null;sd=r.position==='DST'?sim.DST_SD:3.5;}
  else if(e&&e.matched&&!e.unavailable&&e.projection>0){projection=e.projection;sd=e.distribution?.sd??Math.max(2.5,projection*.42);}
  return projection?[{...r,projection,sd,distribution:r.position==='DST'||r.position==='K'?undefined:e.distribution,game:r.game}]:[];});
 const fl=players.filter(r=>r.showdownRole==='FLEX');sim.assignRoles(fl);const role=new Map(fl.map(r=>[r.name+'|'+r.team,r.dfsRole]));players.forEach(r=>{r.dfsRole=role.get(r.name+'|'+r.team);});
 const showdownField=require('../shared/dfs-field.js');if(fieldPath){const r=showdownField.load(fs.readFileSync(fieldPath,'utf8'));if(!r.ok)throw Error(r.reason);showdownField.annotate(players);}
 const out={};
 for(const mode of ['balanced','floor','measured','ceiling','best','lowdup','leverage']){
  const res=football.optimize(players,{site:'draftkings',contest:'showdown',mode,count:5,minUnique:2,now:liveNow,entries:30000});
  const L=res.lineups[0];out[mode]=res.lineups.map(l=>l.players.map(p=>p.name.split(' ').pop()+(p.slot==='CPT'?'*':'')).join(','));
  console.log(mode.padEnd(9),L?`proj ${L.projection.toFixed(1)} sal ${L.salary} own ${L.ownership?Math.round(L.ownership.captain)+'/'+Math.round(L.ownership.flexTotal):'-'} dupDecile ${L.duplication?.decile??'-'} | ${out[mode][0]} | ${res.reason||''}`:'NO LINEUP '+res.reason);
 }
 const modes=Object.keys(out),uniq=new Set(modes.map(m=>out[m].join('/')));console.log('distinct 5-lineup portfolios:',uniq.size,'of',modes.length,'| distinct top lineups:',new Set(modes.map(m=>out[m][0])).size);
 source.dom.window.close();
}
