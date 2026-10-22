"""View-only aggregate target/role/simulation results, within FPDS Research."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from lab.fpds_next.storage import ROOT


@st.cache_data(show_spinner=False)
def metadata(path,mtime_ns):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def render(root=ROOT):
    root=Path(root);statuses=sorted(root.glob('*/STATUS.json'),reverse=True)
    if not statuses:return False
    latest=statuses[0];state=metadata(str(latest),latest.stat().st_mtime_ns)
    active=state.get('phase') in ('preparing','running')
    with st.expander('Targets, roles & simulations — Amendment 10',expanded=active):
        st.caption('Shadow research; reconstructed targets are not independently certified official box scores. Existing forecasts and champion remain unchanged.')
        st.write('Status: '+state.get('phase','unknown')+' · '+state.get('step',''))
        completed=sorted(root.glob('*/SUMMARY.json'),reverse=True)
        if not completed:
            st.info('No completed study yet. The separate local worker writes checkpoints; this view never fits models.')
            return active
        file=completed[0];data=metadata(str(file),file.stat().st_mtime_ns)
        st.warning(data.get('limitations','Previously examined discovery only. No promotion or validated price edge.'))
        rows=[]
        for r in data.get('rows',[]):
            rows.append({'Family':r['family'],'Stat':r['stat'],'Metric':r['metric'],'Rows':r['n'],'Games':r['games'],
                         'Control loss':r['control_loss'],'New loss':r['new_loss'],
                         'Change %':-100*r['relative_reduction'],'Corrected 95% CI':str(r['corrected_ci95']),
                         'Exploratory nominee':r['nomination']})
        frame=pd.DataFrame(rows)
        if len(frame):
            family=st.selectbox('Target/simulation family',['All']+sorted(frame.Family.unique()),key='a10_family')
            if family!='All':frame=frame[frame.Family.eq(family)]
            st.dataframe(frame,hide_index=True,use_container_width=True)
        audit=data.get('audit',{})
        st.caption('Unknown candidate labels by stat: '+str(audit.get('unknown_candidate_labels',{}))+'. Unknowns were excluded identically, never replaced with zeros.')
        group_file=file.parent/'GROUP_INTERVAL_DIAGNOSTICS.json'
        if group_file.exists() and st.checkbox('Show interval coverage by position and role',key='a10_coverage'):
            groups=metadata(str(group_file),group_file.stat().st_mtime_ns).get('rows',[])
            if groups:
                table=pd.DataFrame(groups)
                table['coverage80']=100*table.coverage80
                st.dataframe(table.rename(columns={'coverage80':'Coverage % (target 80)','role_changed':'Earlier role change'}),hide_index=True,use_container_width=True)
            st.caption('Overall coverage can hide weak groups. These are descriptive subgroup checks; small samples and widening alone do not establish improved projections.')
        trials=data.get('trials',{})
        st.caption(f"{len(trials.get('outputs',[]))} output configurations; {trials.get('fit_calls',0)} fit calls; {len(data.get('failures',[]))} failed blocks. Scenario occurrence probabilities remain unknown. Manual commands: docs/FPDS_TARGET_ROLE_SIMULATION.md.")
    return active
