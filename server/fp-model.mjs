// A private, prospective Challenger. Never a production probability or bet.
import {createHash} from 'node:crypto';
import matchupCsv from '../shared/dfs-matchup-csv.js';
import {awareTime} from './fp-input-store.mjs';
const {team}=matchupCsv;
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const count=x=>finite(x)&&Number.isInteger(x)&&x>=0;
const norm=x=>typeof x==='string'?x.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,''):'';
const value=(row,columns,key)=>{const matches=columns.filter(k=>k.toLowerCase()===key.toLowerCase());return matches.length===1?row[matches[0]]:undefined;};
const identity=(r,d)=>[norm(value(r,d.columns,'Player Details.Name')),team(value(r,d.columns,'Player Details.Team')),value(r,d.columns,'Player Details.POS')].join('|');
function sources(datasets,table,season,week,now){
 return datasets.filter(d=>d.table===table&&d.season===season&&d.scope==='season_to_date'&&d.status==='accepted'&&d.for_week===week&&/^[a-f0-9]{64}$/.test(d.sha256||'')&&Number.isFinite(awareTime(d.known_at))&&Number.isFinite(awareTime(d.exported_at))&&awareTime(d.known_at)<=now&&awareTime(d.exported_at)<=now&&now-awareTime(d.exported_at)<=8*86400000);
}
function unique(entries){
 // Multiple source/filter variants cannot silently become first-file wins.
 return entries.length===1?entries[0]:null;
}
export function buildFpModel(datasets,{season,week,now=Date.now(),games=[],profiles={}}){
 const forecasts=[],excluded=[], families=[...new Set(datasets.map(d=>d.table))].sort();
 const sourceTables=['receiving_advanced','receiving_man_vs_zone','coverage_matrix'];
 const available=Object.fromEntries(sourceTables.map(t=>[t,sources(datasets,t,season,week,now)]));
 const receiverRows=new Map();
 for(const d of available.receiving_advanced)for(const r of d.records){const id=identity(r,d);if(!receiverRows.has(id))receiverRows.set(id,[]);receiverRows.get(id).push({r,d});}
 const profileRows=Object.values(profiles||{}).filter(p=>p&&typeof p==='object'), future=(Array.isArray(games)?games:[]).filter(g=>g&&g.season===season&&g.week===week&&awareTime(g.kickoff)>now);
 for(const [id,entries] of receiverRows){
  const first=entries[0],name=value(first.r,first.d.columns,'Player Details.Name'),own=team(value(first.r,first.d.columns,'Player Details.Team')),position=value(first.r,first.d.columns,'Player Details.POS');
  const fail=reason=>excluded.push({name,team:own,position,reason});
  if(!own||!norm(name)||!['RB','WR','TE'].includes(position))continue;
  const receiver=unique(entries),game=unique(future.filter(g=>[team(g.home),team(g.away)].includes(own)));
  if(!receiver||!game){fail('Ambiguous receiver export or missing exact future matchup');continue;}
  const opponent=team(game.home)===own?team(game.away):team(game.home);
  const split=unique(available.receiving_man_vs_zone.flatMap(d=>d.records.filter(r=>identity(r,d)===id).map(r=>({r,d}))));
  const defense=unique(available.coverage_matrix.flatMap(d=>d.records.filter(r=>team(value(r,d.columns,'Team Details.Name'))===opponent).map(r=>({r,d}))));
  const profile=unique(profileRows.filter(p=>norm(p.name)===norm(name)&&team(p.team)===own&&p.position===position));
  if(!split||!defense||!profile){fail('Missing or ambiguous coverage, opponent or public cohort');continue;}
  const get=(x,k)=>value(x.r,x.d.columns,k),n=get(receiver,'Player Details.G'),routes=get(receiver,'Receiving.RTE'),yards=get(receiver,'Receiving.YDS');
  const mr=get(split,'Man.RTE'),zr=get(split,'Zone.RTE'),my=get(split,'Man.YPRR'),zy=get(split,'Zone.YPRR'),man=get(defense,'Man/Zone.MAN %'),zone=get(defense,'Man/Zone.ZONE %');
  if(!count(n)||n<1||n>week-1||get(split,'Player Details.G')!==n||get(split,'Overall.RTE')!==routes||!count(routes)||routes<1||!finite(yards)||!count(mr)||!count(zr)||mr<1||zr<1||mr+zr>routes||!finite(my)||!finite(zy)){
   fail('Incomplete, inconsistent or one-sided player exposure');continue;
  }
  // Vendor YPRR is rounded to two decimals. Exhaustive conditional exposure
  // must reconcile with the independently matched receiving-yard total.
  if(mr+zr===routes&&Math.abs(mr*my+zr*zy-yards)>.005*routes+.01){fail('Conditional yardage rates do not reconcile with the verified cohort');continue;}
  if(!finite(man)||!finite(zone)||man<0||zone<0||man>100||zone>100||man+zone>100.1||man+zone<=0){fail('Coverage shares are missing or invalid percent units');continue;}
  const current=(Array.isArray(profile.games)?profile.games:[]).filter(g=>g&&g.season===season&&g.week<week);
  if(current.length!==n||current.some(g=>g.team!==own||g.completed!==true||!g.game_id||!Number.isFinite(awareTime(g.kickoff))||awareTime(g.kickoff)>=now||!finite(g.rec_yds))||new Set(current.map(g=>g.game_id)).size!==n||Math.abs(current.reduce((s,g)=>s+g.rec_yds,0)-yards)>.01){
   fail('Player export is not verified against the exact current-team appearance cohort');continue;
  }
  // Do not redistribute unclassified coverage onto man/zone. Keep its rate at
  // the player's overall mean; this neutral imputation is an explicit assumption.
  const total=Math.max(100,man+zone),unknown=Math.max(0,100-man-zone);
  const mean=routes/n*(man*my+zone*zy+unknown*yards/routes)/total,baseline=yards/n,champion=profile.stats?.rec_yds?.mean;
  if(!finite(mean)||!finite(champion)){fail('Finite Challenger and actual Champion means required');continue;}
  const used=[receiver.d,split.d,defense.d];
  const hashes=used.map(d=>d.sha256);
  const receipt=createHash('sha256').update(JSON.stringify({id,season,week,opponent,kickoff:game.kickoff,hashes,mean,baseline,champion,version:'fp-coverage-yards-v2'})).digest('hex');
  forecasts.push({name,team:own,position,opponent,market:'rec_yds',season,week,kickoff:game.kickoff,mean,baseline,champion,delta:mean-baseline,games:n,status:'prospective_research_not_promoted',conditionalCohort:mr+zr===routes?'Exhaustive rates reconcile within export rounding':'Partial conditional exposure; residual yardage cannot independently validate the split rates',sourceHashes:hashes,knownAt:used.map(d=>d.known_at).sort((a,b)=>awareTime(a)-awareTime(b)).at(-1),receipt});
 }
 return {schema:'going-fp-numeric-challenger-v2',season,week,forecasts,excluded,inputFamilies:families,numericallyUsedFamilies:sourceTables,unfittedFamilies:families.filter(t=>!sourceTables.includes(t)),status:'Research-only numeric forecasts; accuracy improvement unvalidated; no probabilities or recommendations; unclassified coverage uses the overall player rate'};
}
