(function(root){
'use strict';
const SOURCE='observed-current-season-fantasy-residual-v2';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
// Joint game rows, not independent component draws. This is a dispersion
// assumption for research ordering, NOT a forecast 90th percentile.
function observed(profile,projection,{site='draftkings',now=Date.now(),kickoff,points}={}){
 if(!finite(projection)||projection<=0||typeof points!=='function')return null;
 const engine=root.GoingDfsCurrentSeason||(typeof require==='function'?require('./dfs-current-season.js'):null);
 if(!engine)return null;
 const {season,rows:games}=engine.sample(profile,{now,kickoff});
 if(games.length<3)return null;
 const scores=games.map(g=>points({...g,pass_300_probability:g.pass_yds>=300?1:0,rush_100_probability:g.rush_yds>=100?1:0,rec_100_probability:g.rec_yds>=100?1:0},site)).sort((a,b)=>a-b);
 if(!scores.every(finite))return null;
 const mean=scores.reduce((a,b)=>a+b,0)/scores.length,q90=scores[Math.ceil(.9*scores.length)-1],spread=Math.max(0,q90-mean);
 return {value:projection+spread,source:SOURCE,season,n:scores.length,currentGames:scores.length,asOf:new Date(now).toISOString(),observedMean:mean,observedQ90:q90,spread,site,label:'Current-season scoring-spread proxy; small sample, not a predicted ceiling'};
}
root.GoingDfsUpside={SOURCE,observed};if(typeof module!=='undefined')module.exports=root.GoingDfsUpside;
})(globalThis);
