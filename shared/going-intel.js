(function(root){
'use strict';
// Shared football intelligence primitives. One definition of each fact, interpreted per product (Best Plays, Jackpot, DFS, player card),
// so two pages never compute conflicting versions of the same thing.
// Role trend source: the daily build (scripts/build_pipeline.py role_trend): free public nflverse snap share and share of team targets/carries,
// last 6 games vs last 3. Descriptive; the free role signals were validated for next-game VOLUME (research P3-4), not for prices or ratings.
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const RULE={snap:8,target:.03,carry:.05};// L3 minus L6, in snap-share points / share of team targets / share of team carries (same constants as the build)

// Which role metrics matter for which market. QBs have no snap/target/carry-share role in the passing markets, so no role badge there.
function relevantMetrics(position,market){
 const pos=String(position||'').toUpperCase();
 if(pos==='QB'||!pos)return [];
 if(['rec_yds','receptions','rec_tds'].includes(market))return ['snap_share','target_share'];
 if(['rush_yds','rush_tds'].includes(market))return ['snap_share','carry_share'];
 if(['atd','first_td','last_td'].includes(market))return pos==='RB'?['snap_share','carry_share','target_share']:['snap_share','target_share'];
 return [];
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
 const text=parts.map(p=>`${p.label} ${p.from} → ${p.to}`).join(' · ');
 return {state,parts,text,games:trend.games,badge:state==='up'?'ROLE ↑':state==='down'?'ROLE ↓':null,
  sentence:state==='up'?'Role has expanded over the last three games versus the last six.':state==='down'?'Role has shrunk over the last three games versus the last six.':'No meaningful role change.'};
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
root.GoingIntel={RULE,relevantMetrics,roleTrend,thesisKey};
if(typeof module!=='undefined')module.exports=root.GoingIntel;
})(globalThis);
