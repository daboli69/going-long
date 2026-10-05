(function(root){
'use strict';
const SOURCE='observed-partial-fantasy-residual-v1';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
// Joint game rows, not independent component draws. This is a dispersion
// assumption for research ordering, NOT a forecast 90th percentile.
function observed(profile,projection,{site='draftkings',now=Date.now(),points}={}){
 if(!finite(projection)||projection<=0||typeof points!=='function')return null;
 const d=new Date(now),season=d.getUTCFullYear()-(d.getUTCMonth()<2?1:0);
 const keys=['pass_yds','pass_tds','rush_yds','rush_tds','rec_yds','rec_tds','receptions'];
 const games=(profile?.games||[]).filter(g=>Number(g.season)>=season-1&&Number(g.season)<=season&&Date.parse(g.date)+86400000<=now&&keys.every(k=>finite(g[k])&&g[k]>=0));
 if(games.length<8)return null;
 const scores=games.map(g=>points({...g,pass_300_probability:g.pass_yds>=300?1:0,rush_100_probability:g.rush_yds>=100?1:0,rec_100_probability:g.rec_yds>=100?1:0},site)).sort((a,b)=>a-b);
 if(!scores.every(finite))return null;
 const mean=scores.reduce((a,b)=>a+b,0)/scores.length,q90=scores[Math.ceil(.9*scores.length)-1],spread=Math.max(0,q90-mean);
 return {value:projection+spread,source:SOURCE,n:scores.length,currentGames:games.filter(g=>Number(g.season)===season).length,asOf:new Date(now).toISOString(),historicalMean:mean,historicalQ90:q90,spread,site,label:'Historical scoring-spread proxy; not a predicted ceiling'};
}
root.GoingDfsUpside={SOURCE,observed};if(typeof module!=='undefined')module.exports=root.GoingDfsUpside;
})(globalThis);
