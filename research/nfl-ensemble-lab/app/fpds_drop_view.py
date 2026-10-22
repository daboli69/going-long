"""Weekly workflow metadata and local derived forecasts; no source CSV display."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
from lab.fpds_drop import STATE


@st.cache_data(show_spinner=False)
def metadata(path,mtime):return json.loads(Path(path).read_text(encoding='utf-8'))


@st.cache_data(show_spinner=False)
def sheet(path,mtime):return pd.read_csv(path)


def render(root=None):
    root=Path(root) if root is not None else STATE
    with st.expander('Weekly folders and injury updates',expanded=True):
        st.caption('Week 8 means predict Week 8 using completed Week 7 statistics. START_HERE: 3 = Tuesday refresh; 6 = injury-only import. Source CSVs are never modified.')
        weekly=root/'LATEST_WEEKLY.json';injury=root/'LATEST_INJURIES.json'
        if weekly.exists():
            saved=metadata(str(weekly),weekly.stat().st_mtime_ns)
            forecast=saved['forecast'];week=saved['forecast_week']
            st.success(f"Week {week} weekly workflow completed at {saved['created_at']}. Training through week {forecast['training_last_completed_week']}.")
            presentation=Path(saved['presentation']['path'])
            # Pointers may reference only the private weekly archive.
            from lab.fpds_research.common import ROOT
            if presentation.resolve().is_relative_to((ROOT/'weekly').resolve()):
                csv=presentation/'projections.csv'
                if csv.exists():
                    d=sheet(str(csv),csv.stat().st_mtime_ns)
                    game=d[d.stat.isin(['win','margin','total'])]
                    columns=[c for c in ['name','stat','arm','consensus_line','mean','median','q10','q50','q90','line_status'] if c in game]
                    st.markdown('**Latest frozen weekly game forecasts** — win = P(home wins); margin = home points minus away points.')
                    st.dataframe(game[columns],hide_index=True,use_container_width=True)
                    players=d[~d.stat.isin(['win','margin','total'])].copy()
                    if len(players):
                        st.markdown('**Latest frozen weekly player forecasts**')
                        a,b=st.columns(2)
                        team=a.selectbox('Weekly team',['All']+sorted(players.team.dropna().unique()),key='drop_team')
                        stat=b.selectbox('Weekly stat',['All']+sorted(players.stat.dropna().unique()),key='drop_stat')
                        if team!='All':players=players[players.team.eq(team)]
                        if stat!='All':players=players[players.stat.eq(stat)]
                        cols=[c for c in ['name','team','stat','arm','consensus_line','mean','median','q10','q50','q90','p_over','p_under','line_status'] if c in players]
                        st.dataframe(players[cols],hide_index=True,use_container_width=True)
                    st.caption('Leans and full sheets are in the private folder below. Both control and frozen research arms remain shadow; no market edge is established.')
                    st.code(str(presentation),language=None)
            result_path=Path(saved['previous_results'])
            if result_path.resolve().is_relative_to(root.resolve()) and result_path.exists():
                results=metadata(str(result_path),result_path.stat().st_mtime_ns)
                st.markdown(f"**Week {results['week']} frozen forecast results** — descriptive only; revisions shown separately.")
                if results['rows']:st.dataframe(pd.DataFrame(results['rows']),hide_index=True,use_container_width=True)
                else:st.info('No matched completed results available yet.')
        else:st.info('No completed Tuesday folder workflow yet. Existing forecasts elsewhere in the app remain available.')
        if injury.exists():
            saved=metadata(str(injury),injury.stat().st_mtime_ns)
            st.caption(f"Latest injury import: Week {saved['forecast_week']} at {saved['created_at']}; current-week rows {saved['current_week_rows']}, pregame matched {saved['pregame_matched_rows']}, unmatched {saved['unmatched_rows']}.")
            st.caption(f"Source file modified: {saved.get('source_modified_at','unknown')}. First observed: {saved.get('source_first_observed_at','unknown')}. Vendor publication time is unverified; importing again does not establish fresh information.")
            if not saved['current_week_rows']:st.warning('The supplied injury file has no rows for the forecast week; current injuries remain unavailable.')
            st.warning(saved['warning'])
        else:st.info('No injury-only folder import yet. Add injury-reports.csv to the appropriate Week folder, then choose START_HERE option 6.')
        confirmation=root/'LATEST_CONFIRMATION.json'
        if confirmation.exists():
            saved=metadata(str(confirmation),confirmation.stat().st_mtime_ns)
            st.markdown('**Original feeds + FPDS confirmation**')
            st.caption(f"Week {saved['forecast_week']} · checked {saved['created_at']} · {saved['confirmed']} confirmed · {saved['conflicts']} conflicts · {saved['fpds_only']} CSV-only · {saved['excluded_rows']} excluded/unmatched/postkickoff source rows.")
            st.caption(f"Source rows older than 24h: {saved.get('stale_source_rows',0)}. Agreement alone does not establish freshness.")
            st.caption(saved['policy']+' Agreement does not prove independent confirmation; providers may share information.')
            if saved.get('by_team'):st.dataframe(pd.DataFrame(saved['by_team']),hide_index=True,use_container_width=True)
            if saved.get('conflicts'):st.warning('Injury sources disagree. Official status stays preferred; secondary conflicts remain unresolved. Review before interpreting forecasts.')
            if saved.get('source_errors'):st.warning('Some cached comparison feeds were unavailable: '+', '.join(saved['source_errors']))
