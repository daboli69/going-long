"""Local NBA-only dashboard (port8502). No NFL state or models."""
from pathlib import Path
import subprocess
import sys
import pandas as pd
import streamlit as st
from nba_lab.config import ROOT,CACHE,DATA,MODELS,REPORTS,ARCHIVES,KEYS,NAMES,read
from nba_lab import engine
from nba_lab import codex_research as CR

st.set_page_config(page_title='NBA Ensemble',page_icon='🏀',layout='wide')
st.title('NBA Ensemble')
st.caption('Separate local NBA winners lab. Six statistical models, not six independent opinions.')
st.warning('Shadow research. Current injury/lineup changes are not modeled in v1. Historical results use revised reconstructed data. No demonstrated advantage over betting markets; no market prices are used.')
page=st.sidebar.radio('Page',['Today','Model Debate','King of the Court','Research & Calibration','Data & Sources'])
if (REPORTS/'CONFIRMATION.json').exists():
    st.caption('Evaluation status: '+read(REPORTS/'CONFIRMATION.json')['decision'])


def run_action(action,date=None):
    command=[sys.executable,'-m','nba_lab.cli',*action.split()]
    if date:command+=['--date',str(date)]
    with st.status('Running locally: '+action,expanded=True) as state:
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        st.code(result.stdout[-5000:] or 'No output')
        if result.returncode:
            state.update(label='Stopped; see message above',state='error');return False
        state.update(label='Completed',state='complete')
    return True


SOURCES={'Original six-model ensemble (frozen)':'forecasts','Strength shadow':'strength_forecasts','Injury shadow (official report)':'injury_forecasts',
         'Codex winner research (6 different voters)':'codex'}


def saved(folder,date):
    """Latest saved pregame revision per game for this date."""
    paths=sorted((ARCHIVES/folder).glob(str(date)+'_*/predictions.parquet'))
    if not paths:return pd.DataFrame()
    frame=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
    return frame.sort_values('created_at').drop_duplicates('game_id',keep='last')


def board(date,live,source):
    """One row per game: what each model leans, the vote and the combined probability."""
    codex=SOURCES[source]=='codex'
    frame=CR.saved(date) if codex else saved(SOURCES[source],date)
    models=CR.VOTERS if codex else {k:NAMES[k] for k in KEYS}
    if source.startswith('Original') and not live.empty:
        frame=pd.concat([frame[~frame.game_id.isin(live.game_id)] if len(frame) else frame,live],ignore_index=True)
    if frame.empty:return None
    frame=frame.sort_values(['tipoff','game_id']).reset_index(drop=True)
    scores=saved('score_forecasts',date)
    margin=scores.set_index('game_id').margin_p50 if len(scores) else pd.Series(dtype=float)
    started=pd.to_datetime(frame.tipoff,utc=True).le(pd.Timestamp.now(tz='UTC'))
    rows=[]
    for i,r in frame.iterrows():
        p=[float(r[k]) for k in models]
        lean=lambda x:f'{r.home} {x:.0%}' if x>.5 else f'{r.away} {1-x:.0%}' if x<.5 else 'even 50%'
        home_votes=sum(x>.5 for x in p);away_votes=sum(x<.5 for x in p)
        vote=f'{max(home_votes,away_votes)}-{min(home_votes,away_votes)}'+(' tie' if home_votes==away_votes else '')
        majority=r.home if home_votes>away_votes else r.away if away_votes>home_votes else 'tie'
        warnings=[]
        if started[i]:warnings.append('tipoff passed: last saved pregame forecast')
        if 'diff_out_gmsc' in r and pd.isna(r.diff_out_gmsc):warnings.append('injury report not yet submitted for a team; treated as unknown')
        if r.game_id not in margin.index:warnings.append('no saved score projection')
        if codex and r.codex_flags:warnings.append('Codex flags: '+r.codex_flags)
        rows.append({'game':f'{r.away} @ {r.home}','tipoff':pd.Timestamp(r.tipoff).tz_convert('America/New_York').strftime('%I:%M %p'),
            **{models[k]:lean(x) for k,x in zip(models,p)},'vote':vote,'majority':majority,
            'ensemble winner':r.home if r.p_home>.5 else r.away if r.p_home<.5 else 'coin flip','P(home)':float(r.p_home),
            'home margin':float(margin.get(r.game_id,float('nan'))),'disagreement':max(p)-min(p),'warnings':'; '.join(warnings)})
    return pd.DataFrame(rows)


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
            if page=='Today':
                source=st.radio('Forecast',list(SOURCES),horizontal=True)
                table=board(date,predictions,source)
                if table is None and SOURCES[source]=='codex':
                    status=CR.latest_status()
                    st.info('No Codex forecast saved for this date. Its predict command only covers games in the next 24 hours, and needs at least 5 completed current-season games per team.'
                            +(f" Last run {status['origin']}: {status['forecasts']} forecast, excluded {status['excluded']}." if status else ''))
                    if st.button('Run Codex winner forecast now'):run_action('codex-forecast')
                elif table is None:st.info('No forecast for this date from this source. Unstarted games appear after a refresh; started games show only if a pregame forecast was saved.')
                else:
                    st.dataframe(table,hide_index=True,use_container_width=True,height=min(38*len(table)+40,640),
                        column_config={'P(home)':st.column_config.ProgressColumn('P(home)',format='%.3f',min_value=0,max_value=1),
                                       'home margin':st.column_config.NumberColumn(format='%+.1f'),'disagreement':st.column_config.NumberColumn(format='%.2f')})
                    st.caption("Each model column shows the team it leans toward and that team's win probability. A 3-3 vote is a tie. P(home) comes from the combination method, not the vote. Home margin is the separate score model's median projection, not a sportsbook line. Disagreement is the gap between the highest and lowest model.")
            if predictions.empty:
                if page!='Today':st.info('No unstarted NBA regular-season games on this date. Started/final games are not regenerated as pregame predictions.')
            elif page=='Today':
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
        with st.expander('Injury shadow · strength shadow + official pregame injury report',expanded=True):
            saved_injury=sorted((ARCHIVES/'injury_forecasts').glob(str(date)+'_*/META.json'),reverse=True)
            if saved_injury:
                meta=read(saved_injury[0]);injury_view=pd.read_parquet(saved_injury[0].parent/'predictions.parquet')
                st.caption('Passed a fixed retrospective gate on 2023-24 to 2025-26 (log loss 0.6182 to 0.6101, all three seasons better). Shadow only; nothing above is replaced. One official report per day, so later scratches are not seen.')
                if not meta.get('injury_report_url'):st.warning('No official report was published yet when this was saved. Injury inputs are unknown, not healthy. Refresh closer to tipoff.')
                else:st.caption(f"Report {meta['injury_report_url']} · published {meta['injury_report_published_at']} · unmatched rows {meta['unmatched_rows']} · teams not yet submitted {meta['not_yet_submitted_teams']}")
                st.dataframe(injury_view[['away','home','p_home','winner','home_votes','away_votes','diff_out_gmsc','listed_out']],hide_index=True,use_container_width=True)
                st.download_button('Download injury shadow',injury_view.to_csv(index=False).encode(),'nba_injury_shadow_'+str(date)+'.csv')
            else:st.info('No saved injury shadow for this date; daily refresh or shadow-forecast appends it.')
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
elif page=='King of the Court':
    from nba_lab import kotc
    st.subheader('King of the Court: highest points + rebounds + assists on the Tuesday slate')
    today=pd.Timestamp.now(tz='America/New_York').date()
    default=today+pd.Timedelta(days=(1-today.weekday())%7)
    day=st.date_input('Tuesday (Eastern)',default)
    if pd.Timestamp(day).weekday()!=1:st.warning('King of the Court runs on Tuesdays only.')
    mode=st.radio('Minutes model',['rotation','codex'],horizontal=True,format_func=lambda m:{'rotation':'Rotation minutes (default by owner choice; failed the strict gate)','codex':"Codex's own minutes (the gate's fallback)"}[m])
    if mode=='rotation':st.caption('Rotation minutes scored better on 17 of 21 backtest Tuesdays, but the 95% interval for the gain touched zero, so the preregistered gate failed. Travis chose it as the default anyway on 2026-10-27.')
    if mode=='codex':st.caption("Codex's minutes use only this season's current-team games plus a prior, so early in the season stars can be projected far below their real minutes. Compare both before relying on either.")
    runs=sorted((ARCHIVES/'kotc').glob(str(day)+f'_*_{mode}/META.json'),reverse=True)
    if pd.Timestamp(day).weekday()==1 and st.button('Build full slate + simulate (about 1 minute)',type='primary'):
        run_action('kotc --minutes '+mode,day)
    if not runs:st.info('No simulation saved for this Tuesday with this minutes model. Build one before the first game starts.')
    else:
        meta=read(runs[0]);folder=runs[0].parent
        players=pd.read_csv(folder/'players.csv');field=pd.read_csv(folder/'field.csv')
        source=meta['availability_source']
        st.caption(f"Saved {meta['created_at']} · {meta['games']} games · {meta['players']} players · {meta['draws']:,} simulated slates · "
                   f"official injury report {source.get('official_report_published_at') or 'not yet published'}")
        if source.get('teams_not_submitted'):st.warning('Teams that had not submitted an injury report: '+', '.join(source['teams_not_submitted']))
        st.warning("Research simulation, not a recommendation. Codex's module keeps it blocked: its settings were not chosen on registered pregame slates, and the backtest below is the only accuracy evidence.")
        view=players[players.availability.eq('available')].head(25)[['name','team','minutes','pts','reb','ast','pra','pra_p10','pra_p50','pra_p90','sole_leader','tied_leader','inclusive_leader','tie_credit']]
        st.dataframe(view,hide_index=True,use_container_width=True,column_config={
            **{k:st.column_config.NumberColumn(format='%.1f') for k in ('minutes','pts','reb','ast','pra')},
            **{k:st.column_config.NumberColumn(format='%d') for k in ('pra_p10','pra_p50','pra_p90')},
            'sole_leader':st.column_config.NumberColumn('P(sole leader)',format='percent'),'tied_leader':st.column_config.NumberColumn('P(tied leader)',format='percent'),
            'inclusive_leader':st.column_config.NumberColumn('P(leader incl. ties)',format='percent'),
            'tie_credit':st.column_config.ProgressColumn('Leader share',format='%.3f',min_value=0,max_value=float(view.tie_credit.max()))})
        st.caption('PRA p10/p50/p90: 80% of simulated outcomes fall between p10 and p90. Leader share splits ties evenly and sums to 1 across the slate; "incl. ties" can sum above 1.')
        st.markdown('**Expected prize share (hypothetical crowd)**')
        c=st.columns(3)
        pool=c[0].number_input('Pool, bonus-bet face value ($)',min_value=1000,value=1_000_000,step=100_000)
        entrants=c[1].number_input('Other qualifying entries (guess)',min_value=0,value=100_000,step=10_000)
        scenario=c[2].selectbox('How the crowd picks',['Follows these leader odds','Piles onto the top 5 by projected PRA','Even across the top 15 by projected PRA'])
        ids,pra=kotc.samples(meta['receipt'])
        ranked=players[players.availability.eq('available')].sort_values('pra',ascending=False)
        if scenario.startswith('Follows'):own=dict(zip(players.player_id,players.tie_credit.fillna(0)))
        else:
            top=ranked.head(5 if 'top 5' in scenario else 15).player_id
            own={p:1/len(top) for p in top}
        shares=kotc.prize_share(ids,pra,own,entrants,pool).merge(players[['player_id','name','team','pra']],on='player_id')
        shares['crowd_share']=shares.player_id.map(own).fillna(0)
        shares=shares.sort_values('expected_share',ascending=False).head(15)[['name','team','pra','leader_probability','crowd_share','share_if_leader','expected_share']]
        st.dataframe(shares,hide_index=True,use_container_width=True,column_config={'pra':st.column_config.NumberColumn('Projected PRA',format='%.1f'),
            'leader_probability':st.column_config.NumberColumn('P(leads or ties)',format='percent'),'crowd_share':st.column_config.NumberColumn('Crowd on him',format='percent'),
            'share_if_leader':st.column_config.NumberColumn('Your share if he leads',format='dollar'),'expected_share':st.column_config.NumberColumn('Expected share',format='dollar')})
        st.caption('Expected share = pool × P(he leads) × average of 1 / (1 + other entries on every tied leader). The crowd split and entry count are guesses: real selection counts are not public. Values are bonus-bet face value, not cash, and ignore the qualifying wager itself.')
        out=field[field.availability.eq('out')]
        if len(out):
            with st.expander(f'{len(out)} players ruled out (official report Out/Doubtful)'):
                st.dataframe(out[['name','team','official_status','espn_injury']],hide_index=True,use_container_width=True)
        with st.expander('Full field and sources'):
            st.dataframe(field,hide_index=True,use_container_width=True)
            st.json(meta)
    backtest=REPORTS/'kotc_backtest_v1'/'SUMMARY.json'
    if backtest.exists():
        with st.expander('Backtest: 21 Tuesdays of 2025-26',expanded=True):
            result=read(backtest)
            st.dataframe(pd.DataFrame(result['configs']).T,use_container_width=True)
            st.caption(result['verdict'])
elif page=='Research & Calibration':
    with st.expander('Codex research package (installed 2026-10-27) · separate code, research only'):
        check=CR.verify()
        if not check['installed']:st.info('Package not installed under updates/.')
        else:
            st.write(f"Files verified: {check['files']} · problems: {len(check['problems'])} · research environment: {'present' if check['environment'] else 'missing'}")
            if check['problems']:st.warning('; '.join(check['problems'][:10]))
            st.caption('Codex code runs in its own environment as a separate process. Its six voters (Elo, logistic, gradient boosting, random forest, naive Bayes, ridge margin) differ from the six in this app. King of the Court stays blocked research-only; the FGA repair stays inactive; the participation/minutes study is not implemented.')
            if st.button('Run Codex package tests'):run_action('codex-tests')
            dev=CR.development()
            if dev is not None:
                st.caption('Codex development replay, 2022-23 to 2024-25, reproduced locally. Not a holdout test; the ensemble does not beat every member.')
                st.dataframe(dev,hide_index=True,use_container_width=True)
            audit=CR.kotc_audit()
            if audit:
                st.caption('King of the Court data audit (not a prediction): accepted games by season and exclusions.')
                st.json({'games_by_season':audit['games_by_season'],'exclusions':audit['exclusions'],'reconciliation_failures':len(audit['reconciliation_failures'])})
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
