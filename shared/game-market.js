/* Market-anchored game-line model (market-anchor-v1, 2026-10-09).
 * Evidence (research/calibration/GAME_LINES.md): across 2,575 NFL games 2016-2025 the trailing-points model had NO information beyond the closing
 * line (optimal weight on model-minus-line: totals -0.15 se .07, margin -0.07 se .06; RMSE 13.87 vs 13.21 for totals). The line is the mean;
 * the SD is the residual of actual outcome around the line (fit on 2016-22, checked on 2023-25 at +/-3.5 and +/-7 alternate lines).
 * NCAA: no historical lines available, so the live 2026 sample (102 totals / 97 spreads) sets the SD; this is a weak estimate, labelled as such.
 * Rollback: set globalThis.GOING_GAME_ANCHOR=false (or policy.active=false) to restore the raw trailing-average model.
 */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const POLICY={version:'market-anchor-v1',active:true,nfl:{total_sd:13.3,margin_sd:12.75,evidence:'2016-2022 closing-line residuals (fit), 2023-25 holdout; independent QA reproduced'},ncaa:{total_sd:15,margin_sd:16,evidence:'live 2026 sample only (about 100 games); weak'}};
function active(){return POLICY.active&&root.GOING_GAME_ANCHOR!==false;}
// g: game with posted `spread` (home line, negative when home favoured) and `total`; m: trailing-average model. Returns a model-shaped object.
function anchor(g,m,sport){
 if(!m||!active())return m;
 const s=POLICY[String(sport||g?.sport||'nfl').toLowerCase()==='ncaa'?'ncaa':'nfl'];
 const hasMargin=finite(g?.spread),hasTotal=finite(g?.total);
 if(!hasMargin&&!hasTotal)return m;
 return {...m,margin_mean:hasMargin?-g.spread:m.margin_mean,total_mean:hasTotal?g.total:m.total_mean,margin_sd:hasMargin?s.margin_sd:m.margin_sd,total_sd:hasTotal?s.total_sd:m.total_sd,
  anchored:{version:POLICY.version,raw_margin_mean:m.margin_mean,raw_total_mean:m.total_mean,raw_margin_sd:m.margin_sd,raw_total_sd:m.total_sd,hasMargin,hasTotal}};
}
// Period model derived from the same fractions the pipeline used (sd ratio squared = mean fraction).
function anchorPeriod(g,full,period,sport,opts){
 if(!full||!period||!active())return period;
 const a=anchor(g,full,sport);if(!a||!a.anchored||(opts&&opts.strict&&!(a.anchored.hasMargin&&a.anchored.hasTotal)))return opts&&opts.strict?null:period;
 const rt=finite(period.total_sd)&&finite(full.total_sd)&&full.total_sd>0?period.total_sd/full.total_sd:null,rm=finite(period.margin_sd)&&finite(full.margin_sd)&&full.margin_sd>0?period.margin_sd/full.margin_sd:null;
 return {...period,
  total_mean:a.anchored.hasTotal&&rt?a.total_mean*rt*rt:period.total_mean,total_sd:a.anchored.hasTotal&&rt?a.total_sd*rt:period.total_sd,
  margin_mean:a.anchored.hasMargin&&rm?a.margin_mean*rm*rm:period.margin_mean,margin_sd:a.anchored.hasMargin&&rm?a.margin_sd*rm:period.margin_sd,anchored:a.anchored};
}
// Two-way moneyline from a discretised normal: the integer-margin normal puts ~3% on a tie, but NFL ties are ~0.4% of games (10 of 2,689), so the mass is
// redistributed proportionally and only a 0.4% push (stake returned) is kept. Leaves the input alone when it is not a two-way split.
function moneyline(prob,tie=.004){
 if(!prob||!(prob.over+prob.under>0))return prob;
 const total=prob.over+prob.under;return {over:prob.over/total*(1-tie),under:prob.under/total*(1-tie),push:tie};
}
const api={POLICY,anchor,anchorPeriod,moneyline,active};
root.GoingGameMarket=api;
if(typeof module!=='undefined')module.exports=api;
})(globalThis);
