/* Point-in-time-safe touchdown OPPORTUNITY profile built from GOING's public player role data (history profile `scoring_role`, `role_trend`,
 * `role_evidence`). The role block is built only from games strictly before its own `as_of` date. This module adds no probability: it states what
 * the opportunity data says, how fresh it is, what is missing, and refuses to treat a missing observation as a zero.
 * Licensed FantasyPoints exports (routes, end-zone targets) are private and are NOT read here; they can only arrive through the owner-authenticated
 * private pipeline, never through this public module. */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const DAY=86400000;
// key, label, unit; the unit decides formatting only.
const FIELDS=[
 ['xtd_pg_l6','Expected touchdowns per game, last 6','td'],['xtd_pg_l12','Expected touchdowns per game, last 12','td'],
 ['snap_pct_l3','Offensive snap share, last 3','pct'],['snap_pct_l6','Offensive snap share, last 6','pct'],
 ['rz_tgt_pg_l12','Red-zone targets per game, last 12','count'],['gl_carry_pg_l12','Goal-line carries per game, last 12','count'],
 ['inside5_touch_pg_l12','Inside-5 touches per game, last 12','count'],['td_pg_l12','Touchdowns per game, last 12','td'],['td_luck_l12','Touchdowns minus expected per game, last 12','signed']
];
// Descriptive display cutoffs for "role changing"; they label a change, they do not enter any probability.
const CHANGE={snap:.10,xtd:.05};
const MAX_AGE_DAYS=21,MIN_GAMES=6;

const seasonOf=ms=>{const d=new Date(ms);return d.getUTCMonth()>=7?d.getUTCFullYear():d.getUTCFullYear()-1;};
const fmt=(v,unit)=>unit==='pct'?Math.round(v*100)+'%':unit==='signed'?(v>0?'+':'')+v.toFixed(2):unit==='td'?v.toFixed(2):v.toFixed(1);

/* profile: history profile object. ctx: {now, kickoff}. Returns a plain object; never throws on missing data. */
function describe(profile,ctx={}){
 const now=finite(ctx.now)?ctx.now:Date.now(),kick=Date.parse(ctx.kickoff),sr=profile?.scoring_role;
 const out={status:'missing',reasons:[],asOf:null,ageDays:null,games:null,tier:null,confidence:null,metrics:{},missing:[],roleChange:null,flags:[],lines:[]};
 if(!sr||typeof sr!=='object'){out.reasons.push('No scoring-role data for this player.');return out;}
 for(const [key,label,unit] of FIELDS){
  const v=sr[key],observed=finite(v);
  out.metrics[key]={label,unit,observed,value:observed?v:null};
  if(!observed)out.missing.push(key);          // absent or null is MISSING, a recorded 0 is a real zero
 }
 out.tier=typeof sr.tier==='string'?sr.tier:null;out.confidence=sr.confidence??null;out.games=finite(sr.n)?sr.n:null;
 const asOf=Date.parse(sr.as_of);
 if(!Number.isFinite(asOf)){out.status='invalid';out.reasons.push('Role data has no valid as-of date.');return out;}
 out.asOf=sr.as_of;out.ageDays=Math.floor((now-asOf)/DAY);
 // Point in time: the data must predate the game it is used for and must not be from the future.
 if(asOf>now||(Number.isFinite(kick)&&asOf>=kick)){out.status='invalid';out.reasons.push('Role data is dated at or after the game; it is not usable as a pregame input.');return out;}
 const last=profile?.role_trend?.last_game,season=Number.isFinite(kick)?seasonOf(kick):seasonOf(now);
 if(last&&Number.isFinite(last.season)&&last.season<season){out.status='stale';out.reasons.push(`Most recent game in this role data is from the ${last.season} season (no ${season} games).`);}
 else if(out.ageDays>MAX_AGE_DAYS){out.status='stale';out.reasons.push(`Role data is ${out.ageDays} days old (limit ${MAX_AGE_DAYS}).`);}
 else if(sr.confidence==='low'||(out.games!=null&&out.games<MIN_GAMES)){out.status='low_sample';out.reasons.push(`Only ${out.games??'few'} games of role data; treat as a rough guide.`);}
 else out.status='ok';
 const t=sr.trend||{},dSnap=finite(t.d_snap36)?t.d_snap36:null,dXtd=finite(t.d_xtd36)?t.d_xtd36:null;
 if(dSnap!=null||dXtd!=null){
  const drivers=[];let up=false,down=false;
  if(dSnap!=null&&Math.abs(dSnap)>=CHANGE.snap){drivers.push(`snap share ${dSnap>0?'+':''}${Math.round(dSnap*100)} pts`);dSnap>0?up=true:down=true;}
  if(dXtd!=null&&Math.abs(dXtd)>=CHANGE.xtd){drivers.push(`expected touchdowns ${dXtd>0?'+':''}${dXtd.toFixed(2)} per game`);dXtd>0?up=true:down=true;}
  out.roleChange={direction:up&&!down?'up':down&&!up?'down':up&&down?'mixed':'steady',snapChangePts:dSnap!=null?Math.round(dSnap*100):null,xtdChange:dXtd,drivers};
 }
 const m=k=>out.metrics[k];
 const bits=[];
 if(m('xtd_pg_l6').observed)bits.push(`${fmt(m('xtd_pg_l6').value,'td')} expected touchdowns per game over the last 6${m('xtd_pg_l12').observed?` (${fmt(m('xtd_pg_l12').value,'td')} over 12)`:''}`);
 if(m('snap_pct_l3').observed)bits.push(`${fmt(m('snap_pct_l3').value,'pct')} of offensive snaps in the last 3${out.roleChange?.snapChangePts!=null&&out.roleChange.snapChangePts!==0?`, ${out.roleChange.snapChangePts>0?'up':'down'} ${Math.abs(out.roleChange.snapChangePts)} points from the last 6`:''}`);
 const zone=[];
 if(m('rz_tgt_pg_l12').observed)zone.push(`${fmt(m('rz_tgt_pg_l12').value,'count')} red-zone targets`);
 if(m('gl_carry_pg_l12').observed)zone.push(`${fmt(m('gl_carry_pg_l12').value,'count')} goal-line carries`);
 if(m('inside5_touch_pg_l12').observed)zone.push(`${fmt(m('inside5_touch_pg_l12').value,'count')} inside-5 touches`);
 if(zone.length)bits.push(zone.join(', ')+' per game (last 12)');
 out.lines=bits;
 if(out.roleChange&&out.roleChange.direction!=='steady')out.flags.push(out.roleChange.direction==='mixed'?`Role signals disagree (${out.roleChange.drivers.join('; ')}; last 3 games vs last 6).`:`Role trending ${out.roleChange.direction}: ${out.roleChange.drivers.join('; ')} (last 3 games vs last 6).`);
 if(m('td_luck_l12').observed&&Math.abs(m('td_luck_l12').value)>=.1)out.flags.push(`Scored ${m('td_luck_l12').value>0?'more':'fewer'} touchdowns than expected over 12 games (${fmt(m('td_luck_l12').value,'signed')} per game); that gap is not a skill estimate.`);
 if(out.missing.length&&out.status!=='missing')out.flags.push(`Not available: ${out.missing.map(k=>m(k).label.toLowerCase()).join('; ')}.`);
 return out;
}

/* Descriptive ordering by expected touchdowns per game (last 6, then 12). Only profiles whose data is ok or low_sample and whose value was OBSERVED are ranked.
 * items: [{opportunity, ...}] where opportunity = describe(...). Not a probability and not a validated score. */
function rankByOpportunity(items){
 const usable=x=>x&&x.opportunity&&['ok','low_sample'].includes(x.opportunity.status)&&x.opportunity.metrics.xtd_pg_l6.observed;
 return items.filter(usable).sort((a,b)=>{
  const A=a.opportunity.metrics,B=b.opportunity.metrics,d=B.xtd_pg_l6.value-A.xtd_pg_l6.value;
  if(d)return d;
  const l=(B.xtd_pg_l12.observed?B.xtd_pg_l12.value:-1)-(A.xtd_pg_l12.observed?A.xtd_pg_l12.value:-1);
  return l||String(a.id||a.player||'').localeCompare(String(b.id||b.player||''));
 });
}

const api={FIELDS,CHANGE,MAX_AGE_DAYS,MIN_GAMES,describe,rankByOpportunity,seasonOf};
root.GoingTDOpportunity=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
