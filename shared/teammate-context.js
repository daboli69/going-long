/* Observed teammate context. No projection, ranking or probability changes. */
(function(root){
'use strict';
const number=x=>typeof x==='number'&&Number.isFinite(x);
function zoned(x){
 if(typeof x!=='string')return false;
 const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|([+-])(\d{2}):(\d{2}))$/.exec(x);
 if(!m)return false;const [y,month,day,hour,minute,second]=m.slice(1,7).map(Number),offsetHour=Number(m[9]||0),offsetMinute=Number(m[10]||0);
 const date=new Date(Date.UTC(y,month-1,day));
 return hour<24&&minute<60&&second<60&&offsetHour<=14&&offsetMinute<60&&(offsetHour<14||offsetMinute===0)&&date.getUTCFullYear()===y&&date.getUTCMonth()===month-1&&date.getUTCDate()===day&&Number.isFinite(Date.parse(x));
}
const team=x=>({LAR:'LA',JAC:'JAX',WSH:'WAS'}[x]||x);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function logs(entry,c,now,season){
 if(!entry||entry.player_id===undefined||team(entry.team)!==team(c.team)||!Array.isArray(entry.games_log))return [];
 const ids=new Set();
 for(const g of entry.games_log){if(!g||typeof g!=='object'||typeof g.game_id!=='string'||ids.has(g.game_id))return [];ids.add(g.game_id);}
 return entry.games_log.filter(g=>g.player_id===entry.player_id&&team(g.team)===team(c.team)&&new RegExp('^'+season+'_\\d{2}_').test(g.game_id)&&number(g.offense_snaps)&&g.offense_snaps>0&&zoned(g.kickoff)&&Date.parse(g.kickoff)<Math.min(now,Date.parse(c.kickoff)));
}
function summarize(games){
 const result={n:games.length,games};
 for(const key of ['targets','receptions','receiving_yards','carries','rushing_yards']){
  const values=games.map(g=>g[key]),counts=['targets','receptions','carries'].includes(key);result[key]=values.length&&values.every(x=>number(x)&&(!counts||(Number.isInteger(x)&&x>=0)))?values.reduce((a,b)=>a+b,0)/values.length:null;
 }
 return result;
}
function compare(context,c,now=Date.now()){
 const e=context?.picks_evidence,season=context?.season??e?.season,stamp=Date.parse(e?.generated_at);
 if(c.sport!=='nfl'||c.kind!=='prop'||!e||e.season!==season||!Number.isInteger(season)||!zoned(c.kickoff)||!zoned(e.generated_at)||stamp>now||now-stamp>86400000)return {reason:'Current teammate evidence unavailable or stale.',pairs:[]};
 const inputs=e.provenance?.inputs;
 if(!['pbp','snap_counts','rosters'].every(k=>inputs?.[k]?.status==='loaded'))return {reason:'Participation sources unavailable.',pairs:[]};
 const entries=e.recent_player_games||{},focal=entries[c.team+'|'+c.profileId]||entries[team(c.team)+'|'+c.profileId];
 const games=focal?.player_id===c.profileId?logs(focal,c,now,season):[];
 if(!games.length)return {reason:'No verified current-season offensive appearances.',pairs:[]};
 const roster=Array.isArray(e.current_roster?.players)?e.current_roster.players.filter(r=>r&&typeof r==='object'):[];
 const pairs=[];
 for(const entry of Object.values(entries)){
  if(!entry||typeof entry!=='object'||!Array.isArray(entry.games_log))continue;
  if(entry.player_id===c.profileId||team(entry.team)!==team(c.team)||!['QB','RB','WR','TE'].includes(entry.position))continue;
  const played=new Set(logs(entry,c,now,season).map(g=>g.game_id));
  // Even an unusable/duplicate log can contradict an OUT receipt. Never turn
  // invalid participation data into an absence cohort.
  const contradictions=new Set(entry.games_log.filter(g=>g&&g.player_id===entry.player_id&&team(g.team)===team(c.team)&&number(g.offense_snaps)&&g.offense_snaps>0).map(g=>g.game_id));
  const out=e.provenance?.inputs?.injury_reports?.status==='loaded'?(e.teammate_out_games?.[team(c.team)+'|'+c.profileId+'|'+entry.player_id]||[]):[];
  const absent=new Set((Array.isArray(out)?out:[]).filter(r=>r?.report_status==='Out'&&r.team===team(c.team)&&r.player_id===entry.player_id&&r.report_timing==='retrospective').map(r=>r.game_id));
  const withGames=games.filter(g=>played.has(g.game_id)&&!absent.has(g.game_id));
  const withoutGames=games.filter(g=>absent.has(g.game_id)&&!contradictions.has(g.game_id));
  if(!withGames.length&&!withoutGames.length)continue;
  const name=roster.find(r=>r.player_id===entry.player_id&&team(r.team)===team(c.team))?.name||context?.scopes?.[String(season)]?.players?.[entry.player_id]?.name;
  if(typeof name!=='string'||!name.trim())continue;
  pairs.push({id:entry.player_id,name,with:summarize(withGames),without:summarize(withoutGames),unknown:games.length-withGames.length-withoutGames.length});
 }
 pairs.sort((a,b)=>a.name.localeCompare(b.name));
 return {season,all:summarize(games),pairs,reason:pairs.length?'':'No verified teammate appearances to compare.'};
}
function panel(context,c,now,selected,index){
 const data=compare(context,c,now);if(!data.pairs.length)return `<p class="teammate-context-empty">${esc(data.reason)}</p>`;
 const p=data.pairs.find(x=>x.id===selected)||data.pairs[0],receiving=['receptions','rec_yds','atd','first_td'].includes(c.market),metric=receiving?'receiving_yards':'rushing_yards';
 const fmt=x=>number(x)?x.toFixed(1):'Unknown';
 const selectedMetric=c.market==='receptions'?'receptions':c.market==='rec_yds'?'receiving_yards':c.market==='rush_yds'?'rushing_yards':null;
 const opposite=selectedMetric&&p.with.n>=2&&number(p.with[selectedMetric])&&number(c.line)&&((c.side==='Over'&&p.with[selectedMetric]<c.line)||(c.side==='Under'&&p.with[selectedMetric]>c.line));
 const rows=[['All observed',data.all],['Teammate played',p.with],['Reported OUT',p.without]];
 return `<section class="teammate-context"><h5>Teammate participation</h5><label>Compare with teammate<select data-tonight-teammate="${index}" aria-label="Compare teammate for ${esc(c.player)}">${data.pairs.map(x=>`<option value="${esc(x.id)}" ${x.id===p.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><p>${data.season} · latest ${data.all.n} verified appearances in the loaded log. ${p.unknown} game(s) have unknown or contradictory teammate participation.</p><table><caption>Targets, carries and yards are averages per game.</caption><thead><tr><th scope="col">Context</th><th scope="col">Games</th><th scope="col">${receiving?'Targets':'Carries'}</th><th scope="col">Yards</th></tr></thead><tbody>${rows.map(([name,s])=>`<tr><th scope="row">${name}</th><td>${s.n}</td><td>${fmt(s[receiving?'targets':'carries'])}</td><td>${fmt(s[metric])}</td></tr>`).join('')}</tbody></table>${opposite?`<p class="tonight-watch">The teammate-played average points against this ${esc(c.side)} line. Only ${p.with.n} observed games; this is counterevidence, not a new forecast.</p>`:""}${receiving?`<p>Receptions/game: all ${fmt(data.all.receptions)} · teammate played ${fmt(p.with.receptions)} · reported OUT ${fmt(p.without.receptions)}. Older snapshots may not contain reception counts.</p>`:''}<details><summary>Individual games with ${esc(p.name)}</summary><ul>${p.with.games.map(g=>`<li>${esc(g.game_id)}: ${fmt(g[metric])} yards · ${fmt(g[receiving?'targets':'carries'])} ${receiving?'targets':'carries'}</li>`).join('')||'<li>No observed games.</li>'}</ul></details><p>${p.with.n<2||p.without.n<2?'Insufficient games for a supported with/without comparison. ':''}Missing snaps do not establish absence. OUT cohorts require explicit weekly reports; undated reports are retrospective. Association only: opponent, game script and other teammates can explain differences. These observations do not change the projection or GOING rating.</p></section>`;
}
const api={compare,summarize,panel};if(typeof module==='object'&&module.exports)module.exports=api;else root.GoingTeammateContext=api;
})(typeof globalThis!=='undefined'?globalThis:this);
