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
else:
    st.subheader('Free sources and actual usage')
    st.dataframe(pd.DataFrame([
        ['hoopR','Shared SportsDataverse ESPN datasets','Active via the same public schedule/team-box exports'],
        ['sportsdataverse-py','Same ESPN datasets','Active dataset transport; no separate second source vote'],
        ['nba_api','NBA Stats endpoints','Optional audit connector; separate IDs, availability not guaranteed'],
        ['pbpstats package','NBA PBP parser','Future possession/lineup features; not installed or active in v1'],
        ['PBP Stats site/API','Derived possession statistics','Optional archived context; not historical model features']
    ],columns=['Source','Origin','Current status']),hide_index=True,use_container_width=True)
    for filename,title in [('HEALTH.json','Source coverage/errors'),('FEATURE_AUDIT.json','Feature/leakage audit')]:
        path=DATA/filename
        if path.exists():
            with st.expander(title):st.json(read(path))
    if (CACHE/'features.parquet').exists():
        with st.expander('Historical box-score feature coverage'):
            coverage=pd.read_parquet(CACHE/'features.parquet',columns=['season','home_box_history','away_box_history'])
            st.dataframe(coverage.groupby('season').agg(games=('season','size'),home_prior_boxes=('home_box_history','mean'),away_prior_boxes=('away_box_history','mean')),use_container_width=True)
            st.caption('Prior boxes are counts out of the last20 eligible games. Missing boxes remain unknown; train-only median imputation is used. The2017–18 export has substantial missing box detail.')
    st.info('Missing current lineup information is a material NBA limitation. Seeing injury news elsewhere does not mean the winner model used it.')
