const test=require('node:test'),assert=require('node:assert/strict');
const fixture={schema_version:1,validation_scope:'chronological_week_ahead_score_diagnostic',games:100,seasons:[2023,2026],margin_error_points:14,total_error_points:13,roi:.9,opponent_adjusted:{margin_error_points:13,total_error_points:12,margin_improvement_range_95:[-.2,1.1]}};
test('Historical diagnostics preserve error/uncertainty without fabricating betting ROI',async()=>{
 const {gameDiagnostic,roleDiagnostic}=await import('../apps/validation/backtests.mjs');
 const g=gameDiagnostic(fixture);assert.equal(g.roi,null);assert.deepEqual(g.rows[0].improvementRange,[-.2,1.1]);assert.equal(g.rows[1].improvementRange,null);assert.equal(g.rows[1].challenger,12);
 assert.throws(()=>gameDiagnostic({...fixture,margin_error_points:null}));assert.throws(()=>gameDiagnostic({...fixture,validation_scope:'in_sample'}));assert.throws(()=>gameDiagnostic({...fixture,games:-1}));
 const missing=gameDiagnostic({...fixture,opponent_adjusted:{margin_error_points:'12',margin_improvement_range_95:[2,1]}});assert.equal(missing.rows[0].challenger,null);assert.equal(missing.rows[0].improvementRange,null);
 const r=roleDiagnostic({schema_version:1,validation_scope:'chronological_next_game_diagnostic',season:2025,groups:[{name:'all_eligible',players_games:2,yards_baseline_mae:20,yards_role_adjusted_mae:21},{name:'above_average_role',players_games:1,yards_baseline_mae:null}]});assert.equal(r.roi,null);assert.equal(r.rows[1].baseline,null);assert.equal(r.rows[0].challenger,21);
 assert.throws(()=>roleDiagnostic({schema_version:1,validation_scope:'chronological_next_game_diagnostic',season:2025,groups:[]}));
});
test('Backtests fall back to validated packaged public sources, reject invalid data, and surface errors',async()=>{
 const {loadDiagnostic,gameDiagnostic}=await import('../apps/validation/backtests.mjs');let calls=[];
 const result=await loadDiagnostic('football_game_validation.json',gameDiagnostic,{base:'https://example.test/validation/',stamp:1,fetcher:async url=>{calls.push(url.href);return calls.length===1?{ok:true,json:async()=>({schema_version:0})}:{ok:true,json:async()=>fixture};}});
 assert.equal(result.games,100);assert.equal(calls.length,2);assert.match(calls[0],/api\/snapshot/);assert.match(calls[1],/data\/football_game_validation.json/);
 await assert.rejects(loadDiagnostic('football_game_validation.json',gameDiagnostic,{base:'https://example.test/validation/',fetcher:async()=>({ok:false,status:503})}),/unavailable.*503/);
 await assert.rejects(loadDiagnostic('private.json',gameDiagnostic),/Unknown backtest source/);
});
test('Published historical samples have correct scopes and nonempty baselines',async()=>{
 const {gameDiagnostic,roleDiagnostic}=await import('../apps/validation/backtests.mjs');const g=gameDiagnostic(require('../data/football_game_validation.json')),r=roleDiagnostic(require('../data/football_role_validation.json'));
 assert.ok(g.games>0);assert.ok(r.rows.find(x=>x.name==='all_eligible').games>0);assert.equal(g.roi,null);assert.equal(r.roi,null);
});
