"""Explicit local job controls and local derived forecasts; never source rows."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
from lab.fpds_manual import jobs
from lab.fpds_manual.engine import GAME_STATS


def weeks():
    from lab.data_pipeline import FEATURE_STORE
    try:
        g=pd.read_parquet(FEATURE_STORE,columns=['season','week','kickoff_utc','completed'])
        now=pd.Timestamp.now(tz='UTC');g['kickoff_utc']=pd.to_datetime(g.kickoff_utc,utc=True)
        g=g[g.season.eq(2026)&g.week.between(1,18)&~g.completed&g.kickoff_utc.gt(now)]
        return [int(w) for w in g.groupby('week').kickoff_utc.min().sort_values().index]
    except (OSError,KeyError):return []


@st.cache_data(show_spinner=False)
def projections(path,mtime):
    return pd.read_csv(path)


def results(job):
    path=jobs.directory(job);summary=path/'SUMMARY.json'
    if not summary.exists():st.info('Outputs will appear after the job finishes. Refresh status manually.');return
    m=json.loads(summary.read_text(encoding='utf-8'))
    if m['action']=='compare':
        st.caption('Matched development comparison: already-examined 2022–24. Negative delta favors FPDS. No new 2025 pass or production promotion.')
        rows=[]
        for r in m.get('rows',[]):
            ci=r.get('corrected_ci95')
            rows.append({'Stat':r['stat'],'Model':r['method'],'Metric':r['primary_metric'],'Rows':r['n'],'Games':r['games'],
                         'NFL only':r['control_loss'],'NFL + FPDS':r['fpds_loss'],'Delta':r['delta'],
                         'Corrected 95% CI':str(ci),'Seasons improving':r['seasons_agreeing'],'Discovery nomination':r['discovery_nomination']})
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        st.caption(f"Unique configurations attempted: {len(m.get('trials',{}).get('configurations',[]))}; fit calls: {m.get('trials',{}).get('fit_calls',0)}. Nominations still require future confirmation.")
        if m.get('first_td_secondary'):
            st.markdown('**First offensive TD — secondary diagnostics**')
            st.dataframe(pd.DataFrame(m['first_td_secondary'])[['metric','n','games','delta','ci95','decision']],hide_index=True,use_container_width=True)
    elif m['action']=='prepare':st.success('Authoritative files and matched as-of histories are prepared. Start a comparison or projections when ready.')
    else:
        output=Path(m['path'])
        if not output.resolve().is_relative_to(path.resolve()):st.error('Output path is outside this private job.');return
        csv=output/'projections.csv'
        d=projections(str(csv),csv.stat().st_mtime_ns)
        st.caption(f"Week {m['week']} · {m['games']} games · training through completed week {m['training_last_completed_week']} ({m['training_cutoff_date']}) · {m['sims']:,} draws · seed {m['seed']}. Full eligible history from 2021; recent seasons carry the lab's higher weights.")
        st.info('Early future-week projections use information available when created. Future results, weather and lineup changes are unknown. All rows are tier C; residual warm-up intervals are unvalidated. This is distribution sampling, not play-by-play simulation.')
        g=d[d.stat.isin(GAME_STATS)].copy()
        if len(g):
            from lab.props.independent import spread_label
            keys=['game_id','away_team','home_team','arm']
            wide=g.pivot_table(index=keys,columns='stat',values='mean').reset_index()
            wide['Game']=wide.away_team+' @ '+wide.home_team
            if 'margin' in wide:wide['Our spread']=[spread_label(h,a,v) for h,a,v in zip(wide.home_team,wide.away_team,wide.margin)]
            market=g.pivot_table(index=keys,columns='stat',values='consensus_line').rename(columns=lambda x:'Market '+x).reset_index()
            wide=wide.merge(market,on=keys,how='left')
            if 'Market margin' in wide:wide['Market spread']=[spread_label(h,a,v) for h,a,v in zip(wide.home_team,wide.away_team,wide['Market margin'])]
            cols=[c for c in ('Game','arm','Market spread','Our spread','Market total','total','win') if c in wide]
            st.markdown('**Game ensembles** — `win` is P(home wins); the spread and total are independent of market lines.')
            st.dataframe(wide[cols],hide_index=True,use_container_width=True)
        p=d[~d.stat.isin(GAME_STATS)].copy()
        if len(p):
            st.markdown('**Player props and first TD**')
            a,b=st.columns(2)
            team=a.selectbox('Player team',['All']+sorted(p.team.dropna().unique().tolist()),key='manual_team')
            stat=b.selectbox('Player stat',['All']+sorted(p.stat.unique().tolist()),key='manual_stat')
            if team!='All':p=p[p.team.eq(team)]
            if stat!='All':p=p[p.stat.eq(stat)]
            columns=['name','team','stat','arm','consensus_line','mean','median','q10','q50','q90','p_over','p_under','member_min','member_max','line_status','interval_method']
            st.dataframe(p[[c for c in columns if c in p]],hide_index=True,use_container_width=True)
            st.caption('Anytime/first TD count offensive rushing/receiving scorers only; passing, defensive and special-teams scorers are excluded. Book settlement scope is unverified. OTHER_PLAYERS and NO_OFFENSIVE_TD retain explicit first-TD probability mass.')
            st.caption('For anytime TD, mean is the scorer probability. Outcome quantiles are not confidence intervals around that probability. Run Compare FPDS first to make matching earlier out-of-fold calibration/residuals available; otherwise warm-up intervals remain labelled and unvalidated.')
        st.code(str(output),language=None)
        st.caption('Derived subscription forecasts stay local. Do not upload or commit these files.')


def render(enabled=True):
    st.subheader('Manual FPDS runs')
    st.caption('Authoritative source: Inbox / All historical data from 2021–2026 week 6. Week 7–18 subfolders name the forecast week; completed prior-week exports may contain 2026 only. Earlier history is retained.')
    if not enabled:st.caption('Manual controls are available on the local lab page; this fixture/report view is read-only.');return
    available=weeks();active=jobs.active();history=jobs.list_jobs()
    c1,c2=st.columns(2)
    week=c1.selectbox('Forecast week',available) if available else None
    label=c2.selectbox('Targets',['Games + props','Games','Player props'])
    scope={'Games + props':'all','Games':'games','Player props':'props'}[label]
    with st.expander('Simulation settings'):
        sims=st.number_input('Simulation draws',min_value=1000,max_value=100000,value=10000,step=1000)
        seed=st.number_input('Simulation seed',min_value=0,max_value=2147483647,value=17)
        hours=st.number_input('Maximum runtime (hours)',min_value=.5,max_value=6.,value=2.,step=.5)
        refresh=st.checkbox('Refresh free NFL data and import latest exports',value=True)
        st.caption('Game runs use the six existing game-model families; props use four. Both arms use identical parameters and history windows. Projection runtime is capped at 2h; the seed changes sampling only, not model parameters.')
    a,b,c=st.columns(3)
    action=None
    if a.button('Run projections',disabled=bool(active) or not available,type='primary'):action='project'
    if b.button('Compare FPDS',disabled=bool(active)):action='compare'
    if c.button('Prepare data',disabled=bool(active)):action='prepare'
    if action:
        try:
            job=jobs.launch(action,week=week,scope=scope,sims=int(sims),seed=int(seed),hours=float(hours),refresh=refresh)
            st.session_state['fpds_manual_job']=job;st.success('Local job started. Refresh status to see progress; this page does not poll or launch work automatically.')
        except Exception as error:st.error(str(error))
    st.caption('Compare FPDS uses fixed 2022–24 walk-forward development, not the future week selector. No 2025 confirmation or 2026 model selection is available here.')
    st.button('Refresh status')
    if active:st.info('One manual job is active. It checkpoints between blocks; other starts are disabled.')
    if history:
        ids=[r['job'] for r in history];last=st.session_state.get('fpds_manual_job')
        selected=st.selectbox('Saved manual run',ids,index=ids.index(last) if last in ids else 0,
                              format_func=lambda v:next(f"{x['created_at'][:16]} · {x['action']} · {x['scope']} · {x['phase']}" for x in history if x['job']==v))
        row=next(x for x in history if x['job']==selected)
        st.write('Status: '+row['phase']+' · '+row.get('step',row.get('message','')))
        if row['phase'] in ('checkpoint','failed') and not active:
            if st.button('Resume exact job'):
                try:jobs.launch('compare',resume=selected,hours=float(hours));st.success('Exact checkpoint resume requested')
                except Exception as error:st.error(str(error))
        if active and active.get('job')==selected:
            if st.button('Stop after current block'):jobs.stop(selected);st.info('Stop requested; current block will finish and checkpoint')
        if row['phase']=='complete':results(selected)
