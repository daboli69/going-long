const {test}=require('node:test'),assert=require('node:assert/strict');
const {markup}=require('../shared/slate-breaker.js');
test('Slate Breaker renders the complete field with result, why, data, and confidence',()=>{
 const game={id:'g',away:'PHI',home:'TEN',median_first_td_seconds_given_td:420};
 const selections=Array.from({length:30},(_,i)=>({id:'p'+i,name:i===29?'<unsafe>':'Player '+i,team:'PHI',position:'WR',kind:'player',game_id:'g',game:'PHI-TEN',slate_breaker_probability:.01,first_td_probability:.02,confidence:{label:'Moderate',reason:'12 games'},evidence:['Structured evidence'],feature_snapshot:{first_td_by_5m_given_td:.3,first_td_model:'existing',median_first_td_seconds_given_td:420,total:44,total_source:'pregame_total',first_td_profile_games:12,active_roster_status:'ACT'}}));
 const html=markup({slate:{games:[game],selections,model:{time_method:'empirical'},validation:{method:'walk forward',selected:'empirical',models:{empirical:{n:400,log_loss:3,brier:.2}}},eligibility_note:'Check inactives'},results:[]});
 assert.equal((html.match(/<tr>/g)||[]).length,31);
 assert.match(html,/SIMPLE RESULT/);assert.match(html,/Slate Breaker %/);assert.match(html,/First TD %/);
 assert.match(html,/Estimate Confidence/);assert.match(html,/Why/);assert.match(html,/Show me the data/);
 assert.match(html,/does not rerank First TD/);assert.match(html,/&lt;unsafe&gt;/);
});
