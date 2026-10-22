"""Local manual controls plus saved aggregate FPDS results; never source rows."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
from lab.config import LAB_ROOT,REPORTS_DIR


@st.cache_data(show_spinner=False)
def load_metadata(path,mtime_ns):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def latest(directory,name):
    root=Path(directory)
    files=list(root.glob('run_*/'+name))+list(root.glob(name))
    if not files:return {}
    path=max(files,key=lambda p:(p.parent.name,p.name))
    return load_metadata(str(path),path.stat().st_mtime_ns)


def result_table(rows):
    output=[]
    for r in rows:
        spec=r.get('configuration',{});ci=r.get('corrected_ci95')
        output.append({'Family':spec.get('family'),'Stat':spec.get('stat'),'Variant':spec.get('arm'),
                       'Feature group':spec.get('group'),'Model':spec.get('model'),'Rows':r.get('n'),'Games':r.get('games'),
                       'Control loss':r.get('control_loss'),'New loss':r.get('new_loss'),'Delta':r.get('delta'),
                       'Corrected95% CI':f'[{ci[0]:+.4g}, {ci[1]:+.4g}]' if ci else 'unavailable',
                       'Seasons improving':r.get('seasons_agreeing'),'Discovery gate':r.get('discovery_gate',False),
                       'Run status':r.get('run_status','unknown')})
    return pd.DataFrame(output)


def render(directory=REPORTS_DIR):
    st.title('FPDS Research')
    result=latest(directory,'FPDS_A6_RESULTS.json')
    audit=latest(directory,'FPDS_A6_AUDIT.json')
    timing=latest(directory,'FPDS_A6_TIMING_AUDIT.json')
    qualified=result.get('accepted_shadow_count',0)
    state=f'Saved Amendment 6: {qualified} frozen changes passed its reported discovery/confirmation gates. New manual runs remain separate and exploratory.' if result else 'Completed research results are not saved yet.'
    st.warning(f'Shadow research only. {state} Nothing is promoted. '
               'Historical publication times and revisions are unverified, exports may be capped, and2025 was examined for an older simulator. '
               'Historical prop prices are absent. Forecast-error gains do not establish a tradable price edge. Not betting advice.')
    from app.fpds_controls import render as manual_controls
    local=Path(directory).resolve()==Path(REPORTS_DIR).resolve()
    studying=False
    if local:
        from app.fpds_improvement_view import render as improvements
        studying=improvements()
        from app.fpds_next_view import render as target_simulations
        studying=target_simulations() or studying
        if studying:st.info('The separate improvement study is using the local training worker. Wait for it to finish before another manual run.')
    manual_controls(enabled=local and not studying)
    st.caption('Saved research below is aggregated metadata; source CSV rows are never displayed.')
    if not result and not audit:
        st.info('No saved FPDS audit or research report yet. Run import_fpds.bat to prepare the local metadata audit.')
        return
    tabs=st.tabs(['Coverage','Research results','Limits & weekly use'])
    with tabs[0]:
        tables=audit.get('tables',[])
        if tables:
            cols=st.columns(4)
            cols[0].metric('Tables',len(tables));cols[1].metric('Weekly rows',f"{sum(t.get('valid_rows',0) for t in tables):,}")
            cols[2].metric('Possible export caps',sum(bool(t.get('possible_export_cap')) for t in tables))
            cols[3].metric('Identity / join excluded',f"{sum(t.get('unmatched_rows',0) for t in tables):,}")
            rows=[]
            for t in tables:
                rows.append({'Table':t['table'],'Rows':t.get('valid_rows'),'Usable entity-weeks':t.get('usable_entity_week_rows'),
                    'Unmatched identity':t.get('identity_unmatched_rows'),'Known identity quarantined':t.get('known_identity_quarantined_rows'),
                    'Historical team corrections':t.get('historical_team_corrections',0),'Possible cap':t.get('possible_export_cap'),
                    'Season/week coverage':'; '.join(f"{s}: {','.join(map(str,w))}" for s,w in t.get('coverage',{}).items())})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        if timing:
            count=timing.get('joined_source_references');count=f'{count:,}' if isinstance(count,int) else 'unknown'
            st.caption(f"Joined-source timing audit: {count} references; {timing.get('violations','unknown')} violations. Historical reconstruction does not verify original publication time.")
        st.caption('Week presence is not complete player coverage. Unmatched identities and contradictory joins are excluded; IDs and teams are never guessed.')
    with tabs[1]:
        if not result:
            st.info('Research results are not saved yet. The view stays available while the separate CLI job runs.')
        else:
            st.caption(f"Saved {result.get('created_at','unknown')} · {result.get('trial_count','unknown')} / {result.get('trial_ceiling','unknown')} configurations attempted · {result.get('failed_configurations','unknown')} failed/skipped")
            phase=st.selectbox('Split',['Discovery (2022–24)','Frozen confirmation (2025)','Descriptive (2026)'])
            key={'Discovery (2022–24)':'discovery','Frozen confirmation (2025)':'validation','Descriptive (2026)':'descriptive_2026'}[phase]
            frame=result_table(result.get(key,[]))
            if frame.empty:st.info('No completed rows for this split. Confirmation remains pending unless saved explicitly.')
            else:
                a,b=st.columns(2)
                family=a.selectbox('Family',['All']+sorted(frame.Family.dropna().unique().tolist()))
                stat=b.selectbox('Stat',['All']+sorted(frame.Stat.dropna().unique().tolist()))
                if family!='All':frame=frame[frame.Family.eq(family)]
                if stat!='All':frame=frame[frame.Stat.eq(stat)]
                st.dataframe(frame,hide_index=True,use_container_width=True)
                st.caption('Negative delta means lower forecast loss. Corrected intervals account for the registered family tests. A discovery gate is only a nomination; the frozen confirmation and data limitations still apply.2026 never selects a model.')
    with tabs[2]:
        st.markdown('Drop the same full-history CSV titles with a trailing **week N** into the read-only subscription Inbox, then run **`run_weekly_fpds.bat`** from the lab folder. The command prints a new private revision directory. It stops on failure and keeps earlier forecasts.')
        st.info('Do not upload or commit the private source files, features, models or forecast rows. Historical results below are aggregates; manual output tables show local derived forecasts, never source CSV rows.')
        with st.expander('Interpret the evidence'):
            st.markdown('Historical exports are reconstructed using strictly earlier source weeks after the final kickoff plus24h. Exact GSIS/week roster evidence corrects stale team labels. Capped exports, earlier holdout exposure, unresolved identities and unverified publication times limit inference. Counts and intervals may use labelled distribution approximations; structural members here are analytical proxies. Causal injury/on-off effects and current shadow assignments remain unvalidated. Game closing lines are benchmarks; pseudo prop lines test calibration only. No production model or frozen forecast is changed.')
