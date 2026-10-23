"""Local NBA-only dashboard (port8502). No NFL state or models."""
from pathlib import Path
import subprocess
import sys
import pandas as pd
import streamlit as st
from nba_lab.config import ROOT,CACHE,DATA,MODELS,REPORTS,ARCHIVES,KEYS,NAMES,read
from nba_lab import engine

st.set_page_config(page_title='NBA Ensemble',page_icon='🏀',layout='wide')
st.title('NBA Ensemble')
st.caption('Separate local NBA winners lab. Six statistical models, not six independent opinions.')
st.warning('Shadow research. Current injury/lineup changes are not modeled in v1. Historical results use revised reconstructed data. No demonstrated advantage over betting markets; no market prices are used.')
page=st.sidebar.radio('Page',['Today','Model Debate','Research & Calibration','Data & Sources'])
if (REPORTS/'CONFIRMATION.json').exists():
    st.caption('Evaluation status: '+read(REPORTS/'CONFIRMATION.json')['decision'])


def run_action(action,date=None):
    command=[sys.executable,'-m','nba_lab.cli',action]
    if date:command+=['--date',str(date)]
    with st.status('Running locally: '+action,expanded=True) as state:
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        st.code(result.stdout[-5000:] or 'No output')
        if result.returncode:
            state.update(label='Stopped; see message above',state='error');return False
        state.update(label='Completed',state='complete')
    return True


if page in ('Today','Model Debate'):
    date=st.date_input('Game date (Eastern)',pd.Timestamp.now(tz='America/New_York').date())
    if page=='Today':
        c=st.columns(2)
        if c[0].button('Refresh data + refit frozen models + save forecasts',type='primary'):
            if not (ROOT/'docs/FROZEN_CONFIG.json').exists():st.error('Initial chronological research/freeze is required first. See README.')
            else:run_action('daily',date)
        if c[1].button('Save forecasts using current local data'):
            run_action('predict',date)
    if not (MODELS/'CURRENT.json').exists():
        st.info('No trained NBA bundle yet. Run the initial setup/research steps in README. NFL models are not substituted.')
    elif not (CACHE/'features.parquet').exists():st.info('Refresh NBA data first.')
    else:
        try:
            predictions,_=engine.predict(date,save=False)
            bundle=engine.load()
            st.caption(f"Model {bundle['version']} · base training through {bundle['trained_through']} · calibration through {bundle['calibrated_through']} · selected ensemble: {bundle['selected_method']}")
            if bundle['warnings']:
                with st.expander('Model fitting warnings'):
                    st.dataframe(pd.DataFrame(bundle['warnings']),hide_index=True,use_container_width=True)
            if predictions.empty:st.info('No unstarted NBA regular-season games on this date. Started/final games are not regenerated as pregame predictions.')
            elif page=='Today':
                view=predictions[['away','home','tipoff','winner','p_home','home_votes','away_votes','vote','member_min','member_max']].copy()
                view['tipoff']=pd.to_datetime(view.tipoff,utc=True).dt.tz_convert('America/New_York').dt.strftime('%a %I:%M %p ET')
                st.dataframe(view,hide_index=True,use_container_width=True,
                    column_config={k:st.column_config.NumberColumn(format='percent') for k in ['p_home','member_min','member_max']})
                st.caption('A3–3 vote is a tie, never a majority winner. The ensemble probability comes from the frozen combination method; votes are descriptive only.')
                st.download_button('Download this preview CSV',predictions.to_csv(index=False).encode(),'nba_winners_'+str(date)+'.csv')
                with st.expander('All six model probabilities'):
                    st.dataframe(predictions[['away','home',*KEYS]],hide_index=True,use_container_width=True)
                latest=ARCHIVES/'LATEST.json'
                if latest.exists():st.caption('Latest immutable archive: '+read(latest)['path'])
            else:
                choices={f'{r.away} @ {r.home}':r.game_id for r in predictions.itertuples()}
                match=st.selectbox('Game',list(choices));row=predictions[predictions.game_id.eq(choices[match])].iloc[0]
                tabs=st.tabs(['1 · Predictions','2 · Inputs','3 · Disagreement','4 · Vote','5 · Ensemble'])
                with tabs[0]:
                    st.dataframe(pd.DataFrame([{'model':NAMES[k],'winner':row.home if row[k]>.5 else row.away if row[k]<.5 else 'tie','P(home)':row[k]} for k in KEYS]),hide_index=True,use_container_width=True)
                with tabs[1]:
                    st.caption('Actual feature sensitivity: probability change when one input is reset to its training median. This is a model diagnostic, not a causal explanation or independent football-style debate.')
                    if st.button('Calculate feature sensitivities'):
                        source=pd.read_parquet(CACHE/'features.parquet');source=source[source.game_id.eq(row.game_id)]
                        values=engine.sensitivities(bundle,source)
                        values['largest_effect']=values[list(KEYS)].abs().max(axis=1)
                        st.dataframe(values.sort_values('largest_effect',ascending=False).head(12),hide_index=True,use_container_width=True)
                with tabs[2]:
                    st.write(f"Probability range: {row.member_min:.1%}–{row.member_max:.1%}.")
                    st.caption('Random forest and both boosting models share tree-based structure; agreement is correlated. The SVM, logistic and neural members add different biases, not guaranteed independent evidence.')
                with tabs[3]:st.write(f"Home votes: {int(row.home_votes)}; away votes: {int(row.away_votes)}; result: {row.vote}.")
                with tabs[4]:
                    st.metric('P('+row.home+' wins)',f'{row.p_home:.1%}')
                    st.dataframe(pd.DataFrame([{'method':m,'P(home)':row[m]} for m in ('equal','weighted','stacked')]),hide_index=True,use_container_width=True)
                    st.caption('The selected method was frozen using discovery seasons only. No method is promoted automatically.')
                    st.dataframe(pd.DataFrame({'model':[NAMES[k] for k in KEYS],
                        'weighted_average_weight':bundle['weights'],
                        'stacking_logit_coefficient':bundle['stacker'].coef_[0] if bundle['stacker'] is not None else [None]*6}),hide_index=True,use_container_width=True)
                    st.caption('Stacking coefficients operate on calibrated log-odds. They are not vote shares or win probabilities.')
        except Exception as error:st.error(type(error).__name__+': '+str(error)[:300])
    if page=='Today':
        with st.expander('Pregame availability & roster continuity',expanded=True):
            st.caption('Current source context only; injury statuses do not change the model probabilities. Empty reports are unknown, and current roster membership does not confirm who will play.')
            if st.button('Refresh availability + save context research copies'):
                run_action('pregame-refresh',date)
            availability_path=DATA/'AVAILABILITY.json'
            if availability_path.exists() and read(availability_path)['date']==str(date):
                availability=read(availability_path)
                age=(pd.Timestamp.now(tz='UTC')-pd.Timestamp(availability['created_at'])).total_seconds()/60
                st.caption(f"Saved snapshot {availability['created_at']} · age {age:.0f}minutes · lineups not confirmed")
                if age>60:st.warning('Saved availability is over60minutes old. Refresh before treating it as current context.')
                if availability['issues']:st.warning(f"{len(availability['issues'])} source issues. Missing data remains unknown.")
                teams=pd.DataFrame(availability['teams'])
                if not teams.empty:
                    wanted=['team','released_current_season_games','history_games','roster_retained_minutes_share','known_out_last20_minutes_share','continuity_status']
                    st.dataframe(teams[[c for c in wanted if c in teams]],hide_index=True,use_container_width=True,
                        column_config={k:st.column_config.NumberColumn(format='percent') for k in ('roster_retained_minutes_share','known_out_last20_minutes_share')})
                    st.caption('Retained minutes: share of prior20released team-game minutes from players on today’s roster. Known-Out minutes: share belonging to source-listed Out players; newcomers can have zero prior team minutes. Neither is a predicted point loss. Current-season sample is distinct from82total history games.')
                injuries=pd.DataFrame(availability['rows'])
                if not injuries.empty:
                    wanted=['team','player','status','injury_published_at','retrieved_at','conflict','verification']
                    st.dataframe(injuries[[c for c in wanted if c in injuries]],hide_index=True,use_container_width=True)
                else:st.info('No usable injury entries returned. This does not confirm healthy lineups.')
                if st.checkbox('Show report completeness / source errors'):
                    st.dataframe(pd.DataFrame(availability['reports']),hide_index=True,use_container_width=True)
                    if availability['issues']:st.json(availability['issues'])
            else:st.info('No availability snapshot for this date. Refresh to collect prospective context.')
        with st.expander('Season-continuity / shared-possession research copies'):
            contexts=sorted((ARCHIVES/'context_forecasts').glob(str(date)+'_*/META.json'),reverse=True)
            if contexts:
                context=pd.read_parquet(contexts[0].parent/'predictions.parquet')
                if not context.development_gate_passed.any():
                    st.warning('Both context hypotheses failed their development gates. These fixed copies are saved for prospective research; they are not recommended replacements.')
                else:st.info('Prespecified context research copies; development results are not independent validation or promotion.')
                st.dataframe(context[['away','home','method','p_home','development_gate_passed','home_current_season_games','away_current_season_games','home_prior_season_fraction','away_prior_season_fraction']],hide_index=True,use_container_width=True)
            else:st.info('No saved context research copies for this date.')
        with st.expander('Strength shadow · six models + margin ratings, travel, recent roster',expanded=True):
            saved_strength=sorted((ARCHIVES/'strength_forecasts').glob(str(date)+'_*/META.json'),reverse=True)
            if saved_strength:
                strength=pd.read_parquet(saved_strength[0].parent/'predictions.parquet')
                st.caption('Passed a fixed retrospective gate on 2022-23 to 2025-26 (log loss 0.6247 to 0.6199, all four seasons better). Shadow only: the original ensemble above is unchanged. Roster strength uses earlier released box scores, not the current injury report.')
                st.dataframe(strength[['away','home','p_home','winner','home_votes','away_votes','diff_ridge_net','diff_roster_gmsc','diff_absent_gmsc']],hide_index=True,use_container_width=True)
                st.download_button('Download strength shadow',strength.to_csv(index=False).encode(),'nba_strength_shadow_'+str(date)+'.csv')
            else:st.info('No saved strength shadow for this date; daily refresh or shadow-forecast appends it.')
        with st.expander('Experimental individual-model forecasts · three shadow copies'):
            saved_individual=sorted((ARCHIVES/'individual_forecasts').glob(str(date)+'_*/META.json'),reverse=True)
            if saved_individual:
                shadow=pd.read_parquet(saved_individual[0].parent/'predictions.parquet')
                st.caption('P(home) for the three development-qualified modifications. Original six-model ensemble above is unchanged. These have no new independent confirmation or current injury adjustment.')
                st.dataframe(shadow.pivot(index=['away','home'],columns='candidate',values='p_home'),use_container_width=True)
                st.download_button('Download individual shadows',shadow.to_csv(index=False).encode(),'nba_individual_shadows_'+str(date)+'.csv')
            else:st.info('No saved individual shadows for this date; daily refresh appends them after configuration freeze.')
        with st.expander('Experimental spreads & totals · separate score model',expanded=True):
            saved_scores=sorted((ARCHIVES/'score_forecasts').glob(str(date)+'_*/META.json'),reverse=True)
            if not saved_scores:st.info('No saved score projection for this date. Daily refresh saves a new revision after score research is frozen.')
            else:
                meta=read(saved_scores[0]);score_view=pd.read_parquet(saved_scores[0].parent/'predictions.parquet')
                st.caption('Independent projected spread, not a sportsbook line. Development-tested shadow model; no live injury adjustment or market comparison. Its win probability belongs to this score distribution, separate from the six-model winner ensemble.')
                st.dataframe(score_view[['away','home','spread','home_points','away_points','total','margin_p10','margin_p50','margin_p90','total_p10','total_p50','total_p90','p_home_score_model']],hide_index=True,use_container_width=True)
                st.caption(f"Saved {meta['created_at']} · method {meta['method']} · outcomes available through {meta['calibration_available_through']}")
                st.download_button('Download shadow score projections',score_view.to_csv(index=False).encode(),'nba_scores_'+str(date)+'.csv')
        if (DATA/'INJURY_CONTEXT.json').exists():
            injury=read(DATA/'INJURY_CONTEXT.json')
            st.caption('Official index lists report: '+injury['latest_report']['report_time']+' · fetched '+injury['retrieved_at']+' · the index may lag newer releases; statuses do not adjust forecasts.')
            st.link_button('Open official injury report',injury['latest_report']['url'])
    with st.expander('Saved forecast history · originals remain unchanged'):
        archives=sorted((ARCHIVES/'forecasts').glob('*/META.json'),reverse=True)
        if not archives:st.info('No saved NBA forecasts yet.')
        else:
            chosen=st.selectbox('Saved revision',archives,format_func=lambda p:p.parent.name)
            saved=pd.read_parquet(chosen.parent/'predictions.parquet')
            st.caption('Saved pregame forecast, including games that have since started. This is not a live re-prediction.')
            st.dataframe(saved[['away','home','tipoff','winner','p_home','home_votes','away_votes','model_version']],hide_index=True,use_container_width=True)
            st.download_button('Download saved revision',saved.to_csv(index=False).encode(),'nba_'+chosen.parent.name+'.csv')
elif page=='Research & Calibration':
    context_result=REPORTS/'pregame_context_v1/RESULT.json'
    if context_result.exists():
        with st.expander('Agent-reviewed pregame hypotheses · development only'):
            rows=[]
            for r in read(context_result)['results']:
                rows.append({'hypothesis':r['method'],'n':r['candidate']['n'],'control_log_loss':r['control']['log_loss'],
                             'new_log_loss':r['candidate']['log_loss'],'delta':r['delta']['delta'],
                             'corrected_CI_low':r['delta']['ci_low'],'corrected_CI_high':r['delta']['ci_high'],'development_pass':r['accepted_exploratory']})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            st.caption('Two fixed tests; same reused development seasons. No confirmation rerun or automatic promotion. Early-season subset is descriptive only.')
    st.subheader('Individual-model hypotheses and score research')
    tabs=st.tabs(['Winner model changes','Spreads & totals'])
    with tabs[0]:
        path=REPORTS/'individual_v1/RESULT.json'
        if path.exists():
            result=read(path);table=[]
            for r in result['results']:
                table.append({'candidate':r['name'],'n':r['candidate']['n'],'control_log_loss':r['control']['log_loss'],
                              'new_log_loss':r['candidate']['log_loss'],'new_brier':r['candidate']['brier'],'new_accuracy':r['candidate']['accuracy'],
                              'delta':r['delta']['delta'],'corrected_CI_low':r['delta']['ci_low'],'corrected_CI_high':r['delta']['ci_high'],
                              'seasons_improving':r['seasons_improving'],'exploratory_pass':r['accepted_exploratory']})
            st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
            st.caption(result['status']+' Each individual is compared with its original family; stacked is compared with original stacked. A family improvement does not establish that it beats logistic regression.')
        else:st.info('Run START_NBA option5 for the fixed study; completed work is cached.')
    with tabs[1]:
        path=REPORTS/'scores_v1/RESULT.json'
        if path.exists():
            result=read(path);table=[]
            for r in result['results']:
                table.append({k:r[k] for k in ('method','target','n','mae','rmse','crps','bias','coverage_80','accepted_exploratory')}|r['mae_delta'])
            st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
            st.caption('Selected shadow method: '+result['selected_shadow_method']+'. '+result['status']+' Delta compares MAE with the structural rolling-score baseline; nominal10–90coverage is80%.')
        else:st.info('No completed score-distribution research.')
    st.subheader('Bounded combined-probability calibration')
    st.caption('Six fixed tests on saved discovery predictions;20minute cap, ends sooner when complete. No confirmation rerun, base-model refits or changes to saved forecasts. Completed runs return cached results.')
    if st.button('Run / load bounded calibration check'):
        run_action('calibrate')
    calibration=REPORTS/'calibration_v1/RESULT.json'
    if calibration.exists():
        result=read(calibration);st.write(result['decision'])
        st.caption(f"{result['trial_count']} candidates · {result['calibrator_fits']} monthly fits · latest invocation {result['elapsed_seconds']:.1f}s (completed checkpoints included) · reused discovery data, exploratory only")
        table=[]
        for t in result['trials']:
            table.append({'candidate':t['name'],**t['candidate'],
                          'log_loss_delta':t['log_loss_delta']['delta'],
                          'corrected_CI_low':t['log_loss_delta']['ci_low'],'corrected_CI_high':t['log_loss_delta']['ci_high'],
                          'accepted_exploratory':t['accepted_exploratory']})
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
        with st.expander('Calibration reliability · predicted versus observed wins'):
            options={'Existing control':result['control_reliability']}
            options.update({t['name']:t['reliability'] for t in result['trials']})
            view=st.selectbox('Reliability series',list(options))
            st.dataframe(pd.DataFrame(options[view]),hide_index=True,use_container_width=True)
            st.caption('For example, forecasts averaging60% should win about60% over enough games. Small bins fluctuate. Discovery has already been examined; these bins are exploratory.')
    discovery=REPORTS/'DISCOVERY.json';confirmation=REPORTS/'CONFIRMATION.json'
    if discovery.exists():
        d=read(discovery);st.subheader('Discovery ·2024/2025 ending seasons')
        st.dataframe(pd.DataFrame(d['discovery_metrics']),hide_index=True,use_container_width=True)
        st.write('Frozen ensemble: '+d['selected_method'])
    else:st.info('No completed discovery run.')
    if confirmation.exists():
        c=read(confirmation);st.subheader('One-pass confirmation ·2025–26 season')
        st.write(c['decision']);st.dataframe(pd.DataFrame(c['metrics']),hide_index=True,use_container_width=True)
        st.caption('Negative log-loss delta versus Elo is better. Discovery intervals were corrected across9outputs; confirmation selected-method interval is95%. No prices or returns are inferred.')
        path=REPORTS/'research/fold_2026/predictions.parquet'
        if path.exists():
            d=pd.read_parquet(path);selected=d[c['selected_method']]
            bins=pd.cut(selected,[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1],include_lowest=True)
            reliability=pd.DataFrame({'bin':bins.astype(str),'forecast':selected,'outcome':d.home_win}).groupby('bin').agg(n=('outcome','size'),forecast=('forecast','mean'),observed=('outcome','mean'))
            st.subheader('Confirmation reliability');st.dataframe(reliability,use_container_width=True)
    else:st.info('No completed confirmation. It is not silently run by opening this page.')
    st.subheader('Prospective saved-forecast results')
    prospective=REPORTS/'PROSPECTIVE.json'
    if prospective.exists():st.json(read(prospective))
    else:st.info('Daily refresh scores previously archived forecasts after results are available. No retrospective forecasts are inserted.')
    if (REPORTS/'SHADOW_PROSPECTIVE.json').exists():
        with st.expander('Descriptive prospective results · individual and score shadows'):
            st.json(read(REPORTS/'SHADOW_PROSPECTIVE.json'))
else:
    st.subheader('Free sources and actual usage')
    st.dataframe(pd.DataFrame([
        ['hoopR','Shared SportsDataverse ESPN datasets','Active via the same public schedule/team-box exports'],
        ['sportsdataverse-py','Same ESPN datasets','Active dataset transport; no separate second source vote'],
        ['nba_api','NBA Stats endpoints','Optional audit connector; separate IDs, availability not guaranteed'],
        ['pbpstats package','NBA PBP parser','Future possession/lineup features; not installed or active in v1'],
        ['PBP Stats site/API','Derived possession statistics','Optional archived context; not historical model features']
    ],columns=['Source','Origin','Current status']),hide_index=True,use_container_width=True)
    for filename,title in [('HEALTH.json','Source coverage/errors'),('FEATURE_AUDIT.json','Feature/leakage audit'),('EXTRA_DATA.json','Player-box prerequisite coverage and injury-index archive')]:
        path=DATA/filename
        if path.exists():
            with st.expander(title):st.json(read(path))
    if (CACHE/'features.parquet').exists():
        with st.expander('Historical box-score feature coverage'):
            coverage=pd.read_parquet(CACHE/'features.parquet',columns=['season','home_box_history','away_box_history'])
            st.dataframe(coverage.groupby('season').agg(games=('season','size'),home_prior_boxes=('home_box_history','mean'),away_prior_boxes=('away_box_history','mean')),use_container_width=True)
            st.caption('Prior boxes are counts out of the last20 eligible games. Missing boxes remain unknown; train-only median imputation is used. The2017–18 export has substantial missing box detail.')
    st.info('Missing current lineup information is a material NBA limitation. Seeing injury news elsewhere does not mean the winner model used it.')
