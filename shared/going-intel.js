(function(root){
'use strict';
// Shared football intelligence primitives. One definition of each fact, interpreted per product (Best Plays, Jackpot, DFS, player card),
// so two pages never compute conflicting versions of the same thing.
// Role trend source: the daily build (scripts/build_pipeline.py role_trend): free public nflverse snap share and share of team targets/carries,
// last 6 games vs last 3. Descriptive; the free role signals were validated for next-game VOLUME (research P3-4), not for prices or ratings.
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const RULE={snap:8,target:.03,carry:.05};// L3 minus L6, in snap-share points / share of team targets / share of team carries (same constants as the build)

// Which role metrics matter for which market. QBs have no snap/target/carry-share role in the passing markets, so no role badge there.
// One answer per player: the metric set depends on POSITION only, so a player never reads ROLE up on one page and flat on another. (QBs have no snap/target/carry-share role.)
function relevantMetrics(position,market){
 const pos=String(position||'').toUpperCase();
 if(!pos||pos==='QB'||!['RB','WR','TE'].includes(pos))return [];
 if(['pass_yds','pass_tds'].includes(market))return [];
 return pos==='RB'?['snap_share','carry_share','target_share']:['snap_share','target_share'];
}
const LABEL={snap_share:'Snap share',target_share:'Target share',carry_share:'Carry share'};
const THRESHOLD={snap_share:RULE.snap,target_share:RULE.target,carry_share:RULE.carry};
function fmt(metric,x){return metric==='snap_share'?`${Math.round(x)}%`:`${Math.round(x*100)}%`;}
function roleTrend(trend,position,market){
 const metrics=relevantMetrics(position,market);
 if(!trend||!metrics.length)return null;
 const parts=[];let up=0,down=0;
 for(const m of metrics){
  const x=trend[m];if(!x||!finite(x.l6)||!finite(x.l3))continue;
  const change=x.l3-x.l6,limit=THRESHOLD[m];
  // A share that is essentially zero in both windows is not a role (a WR's carry share): skip it.
  if(m!=='snap_share'&&x.l6<.02&&x.l3<.02)continue;
  parts.push({metric:m,label:LABEL[m],from:fmt(m,x.l6),to:fmt(m,x.l3),change,state:change>=limit?'up':change<=-limit?'down':'flat'});
  if(change>=limit)up++;else if(change<=-limit)down++;
 }
 if(!parts.length)return null;
 const state=up&&!down?'up':down&&!up?'down':'flat';
 const spans=finite(trend.last6_current_season)&&trend.last6_current_season<6,text=parts.map(p=>`${p.label} ${p.from} → ${p.to}`).join(' · ')+(spans?` (last 6 includes ${6-trend.last6_current_season} games from last season)`:'');
 return {state,parts,text,games:trend.games,badge:state==='up'?'ROLE ↑':state==='down'?'ROLE ↓':null,
  sentence:state==='up'?'Role has expanded over the last three games versus the last six.':state==='down'?'Role has shrunk over the last three games versus the last six.':'No meaningful role change.'};
}

// Every role metric for a position with the last-6 / last-3 / last-1 values, for charts. Same thresholds as roleTrend.
function roleSeries(trend,position){
 const pos=String(position||'').toUpperCase();if(!trend||!pos||pos==='QB')return [];
 const metrics=pos==='RB'?['snap_share','carry_share','target_share']:['snap_share','target_share'];
 return metrics.map(m=>{const x=trend[m];if(!x||!finite(x.l6)||!finite(x.l3))return null;if(m!=='snap_share'&&x.l6<.02&&x.l3<.02)return null;
  const change=x.l3-x.l6,limit=THRESHOLD[m];return {metric:m,label:LABEL[m],l6:x.l6,l3:x.l3,l1:finite(x.l1)?x.l1:null,change,state:change>=limit?'up':change<=-limit?'down':'flat',fmt:v=>fmt(m,v)};}).filter(Boolean);
}
// Scoring role (build: scripts/scoring_role.py, public nflverse play-by-play, games before the build date). Research JP-1..5: expected TDs per game by field zone, share of team
// expected TDs and snap share predict anytime TD beyond the Champion rate (2025 holdout, log loss -4.2%); tiers separate anytime rates monotonically (PRIMARY .47 ... FRINGE .07).
// First/last/longest-TD probabilities from it are still SHADOW; trends are not used (rejected).
// A profile is current when the player appeared within 21 days and the roster does not list him reserve/injured/suspended/retired. Stale profiles must not read as current form.
const OUT_STATUS=new Set(['RES','INA','PUP','IR','SUS','RET','EXE']);
const unavailableIds=cache=>{const s=new Set();for(const v of Object.values(cache||{}))if(v?.gsis_id&&OUT_STATUS.has(String(v.roster_status||'').toUpperCase()))s.add(v.gsis_id);return s;};
function activeProfile(profile,out=null,now=Date.now()){
 const t=Date.parse(profile?.last_game);if(!Number.isFinite(t)||now-t>21*86400000||t>now+86400000)return false;
 return !(out&&profile.id&&out.has(profile.id));
}
const TIER_TEXT={PRIMARY:'primary scoring role',SECONDARY:'secondary scoring role',TERTIARY:'tertiary scoring role',FRINGE:'fringe scoring role'};
function scoringRole(sr,position,market){
 if(!sr||sr.confidence==='low'||!TIER_TEXT[sr.tier]||!finite(sr.xtd_pg_l12)||!finite(sr.xtd_share_l6))return null;
 const pos=String(position||'').toUpperCase(),badges=[];
 if(sr.tier==='PRIMARY')badges.push('SCORING ROLE');
 if(['RB','QB'].includes(pos)&&finite(sr.gl_carry_pg_l12)&&sr.gl_carry_pg_l12>=.5)badges.push('GOAL LINE');
 if(['WR','TE','RB'].includes(pos)&&finite(sr.rz_tgt_pg_l12)&&sr.rz_tgt_pg_l12>=1)badges.push('RED ZONE');
 const luck=finite(sr.td_luck_l12)?sr.td_luck_l12:null,state=luck===null?null:luck>=.25?'above':luck<=-.25?'below':'even';
 const tierText=TIER_TEXT[sr.tier][0].toUpperCase()+TIER_TEXT[sr.tier].slice(1),text=`${tierText}: ${Math.round(sr.xtd_share_l6*100)}% of his team's expected TDs (last 6 games), ${sr.xtd_pg_l12.toFixed(2)} expected TDs per game${finite(sr.td_pg_l12)?` against ${sr.td_pg_l12.toFixed(2)} scored`:''} over the last ${sr.n} games${finite(sr.snap_pct_l6)?`, ${Math.round(sr.snap_pct_l6*100)}% of offensive snaps`:''}`;
 const luckText=state==='above'?'He has scored more than his opportunity predicts, so his recent touchdown total overstates the role.':state==='below'?'He has scored less than his opportunity predicts: the role is better than his touchdown total.':null;
 return {tier:sr.tier,text,badges,luck:state,luckText,xtd:sr.xtd_pg_l12,share:sr.xtd_share_l6};
}

// Two cards are the same football thesis when they ride on the same player/team outcome in the same direction.
// Receptions and receiving yards over are one thesis (the player gets volume); passing yards and passing TDs over are one (the offense throws a lot).
const GROUP={rec_yds:'receiving',receptions:'receiving',pass_yds:'passing',pass_tds:'passing',rush_yds:'rushing',rush_tds:'rushing-td',rec_tds:'receiving-td',atd:'scoring',first_td:'scoring',last_td:'scoring'};
function thesisKey(c){
 if(c.kind==='game'){
  const side=c.market==='total'?String(c.side||'').toLowerCase():String(c.side==='Home'?c.home:c.side==='Away'?c.away:c.side||'').toLowerCase();
  const family=c.market==='total'?'total':'side';// spread and moneyline on the same team are one thesis
  return ['game',c.away,c.home,family,side].join('|');
 }
 const group=GROUP[c.market];if(!group||!c.profileId)return null;
 return ['prop',c.away,c.home,c.profileId,group,String(c.side||'Over').toLowerCase()].join('|');
}

// How the legs of a same-game ticket relate. Football logic and the signs of the measured fantasy-point correlations (QB-WR1 +.34, QB-WR2 +.25, QB-TE1 +.21); no joint probability is implied.
const NAME={rec_yds:'receiving yards',receptions:'receptions',pass_yds:'passing yards',pass_tds:'passing TDs',rush_yds:'rushing yards',rush_tds:'rushing TDs',rec_tds:'receiving TDs',atd:'anytime TD',total:'game total',spread:'spread',moneyline:'moneyline'};
const legName=l=>l.kind==='prop'?l.player:'Game';
const legText=l=>l.market==='atd'?`${l.player} anytime TD`:l.kind==='prop'?`${l.player} ${String(l.side).toLowerCase()} ${l.line} ${NAME[l.market]||l.market}`:l.market==='total'?`${l.side} ${l.line}`:l.market==='moneyline'?`${l.side==='Home'?l.home:l.away} to win`:`${l.side==='Home'?l.home:l.away} spread`;
const overVolume=l=>l.kind==='prop'&&l.side==='Over'&&['rec_yds','receptions','pass_yds'].includes(l.market);
const scoringProp=l=>l.kind==='prop'&&['atd','rush_tds','rec_tds','pass_tds'].includes(l.market);
const scoringEvent=l=>l.kind==='prop'&&['atd','first_td','last_td','rush_tds','rec_tds'].includes(l.market);
const passer=l=>l.kind==='prop'&&['pass_yds','pass_tds'].includes(l.market);
const catcher=l=>l.kind==='prop'&&['rec_yds','receptions','rec_tds'].includes(l.market);
// A clear favourite only: moneyline of about -200 or shorter, or a spread of 3 points or more. A pick'em or a small favourite says nothing about game script.
// The team this leg BACKS, if that team is a clear favourite. Spread legs on both sides store the HOME line (the label negates it for the away side), so the backed team is
// laying points when (home leg and home line <= -3) or (away leg and home line >= +3).
function favoriteTeam(l){
 if(l.kind!=='game')return null;
 const backed=l.side==='Home'?l.home:l.side==='Away'?l.away:null;if(!backed)return null;
 if(l.market==='moneyline')return l.dec<=1.5?backed:null;
 if(l.market==='spread'){const laying=l.side==='Home'?-l.line:l.line;return laying>=3?backed:null;}
 return null;
}
function legRelations(legs){
 const out=[],list=Array.isArray(legs)?legs.filter(Boolean):[];
 for(let i=0;i<list.length;i++)for(let j=i+1;j<list.length;j++){
  const a=list[i],b=list[j];if(a.event!==b.event)continue;
  const add=(kind,text)=>out.push({kind,legs:[i,j],text});
  const ka=thesisKey(a);
  if(a.profileId&&a.profileId===b.profileId&&scoringEvent(a)&&scoringEvent(b)&&a.side!=='Under'&&b.side!=='Under'){add('same-thesis',`${legText(a)} and ${legText(b)} are nested: one touchdown can settle both, so they are not independent.`);continue;}
  if(ka&&ka===thesisKey(b)){add('same-thesis',`${legText(a)} and ${legText(b)} are one thesis: both win if the same volume shows up. Hitting one makes the other likelier, so they are not two independent edges.`);continue;}
  if(passer(a)!==passer(b)&&(catcher(a)||catcher(b))&&a.team&&a.team===b.team){
   const p=passer(a)?a:b,c=passer(a)?b:a;
   if(p.side==='Over'&&c.side==='Over')add('complement',`${legText(p)} and ${legText(c)} both need the same passing offense to produce; QB and receiver outcomes are positively correlated (measured on fantasy points: about +.2 to +.3 for WR1/WR2/TE1).`);
   else if(p.side==='Under'&&c.side==='Under')add('complement',`${legText(p)} and ${legText(c)} both win in a low-volume passing game for this offense.`);
   else if(p.side==='Over'&&c.side==='Under'||p.side==='Under'&&c.side==='Over')add('conflict',`${legText(p)} and ${legText(c)} pull in opposite directions: a big passing day usually means catches for his receivers.`);
   continue;
  }
  const total=a.market==='total'?a:b.market==='total'?b:null,other=total===a?b:a;
  if(total&&other!==total&&overVolume(other)){
   if(total.side==='Under')add('conflict',`${legText(total)} expects a low-scoring game, which works against ${legText(other)}: fewer possessions mean fewer yards and catches.`);
   else add('complement',`${legText(total)} supports ${legText(other)}: more scoring means more plays and more volume.`);
   continue;
  }
  if(total&&other!==total&&other.kind==='prop'&&other.market==='rush_yds'&&other.side==='Over'&&total.side==='Under'){add('complement',`${legText(total)} and ${legText(other)} fit together: low-scoring games are run-heavy and burn clock.`);continue;}
  if(total&&other!==total&&scoringProp(other)&&other.side!=='Under'){
   if(total.side==='Under')add('conflict',`${legText(total)} works against ${legText(other)}: fewer points means fewer touchdowns to go around.`);
   else add('complement',`${legText(total)} supports ${legText(other)}: more points means more touchdowns.`);
   continue;
  }
  const fav=favoriteTeam(a)||favoriteTeam(b),game=favoriteTeam(a)?a:favoriteTeam(b)?b:null,prop=game===a?b:a;
  if(fav&&prop.kind==='prop'&&prop.team===fav&&prop.market==='rush_yds'&&prop.side==='Over')add('complement',`${fav} winning supports ${legText(prop)}: teams with a lead run more late.`);
  else if(fav&&prop.kind==='prop'&&prop.team&&prop.team!==fav&&prop.market==='rush_yds'&&prop.side==='Over')add('conflict',`${fav} winning works against ${legText(prop)}: a trailing team runs less.`);
  else if(fav&&prop.kind==='prop'&&prop.team===fav&&['rush_tds','atd'].includes(prop.market)&&prop.side!=='Under')add('complement',`${fav} winning supports ${legText(prop)}: leading teams score on the ground late.`);
  else if(fav&&prop.kind==='prop'&&prop.team&&prop.team!==fav&&prop.market==='pass_yds'&&prop.side==='Over')add('complement',`${fav} winning supports ${legText(prop)}: a trailing team throws more.`);
  else if(passer(a)&&passer(b)&&a.team!==b.team&&a.side==='Over'&&b.side==='Over')add('complement',`${legText(a)} and ${legText(b)} both benefit from a shootout, so they tend to hit together.`);
 }
 return out;
}
root.GoingIntel={RULE,relevantMetrics,roleTrend,roleSeries,scoringRole,thesisKey,legRelations,unavailableIds,activeProfile};
if(typeof module!=='undefined')module.exports=root.GoingIntel;
})(globalThis);
