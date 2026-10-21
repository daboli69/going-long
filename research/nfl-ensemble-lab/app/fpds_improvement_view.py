"""View-only aggregate Amendment8 results; no source or player rows."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from lab.fpds_improve.storage import ROOT


def render(root=ROOT):
    files=sorted(Path(root).glob('*/STATUS.json'),reverse=True)
    if not files:return False
    path=files[0].parent
    try:status=json.loads(files[0].read_text(encoding='utf-8'))
    except (OSError,ValueError):return False
    active=status.get('phase') in ('running','preparing')
    with st.expander('Model improvements — Amendment 8',expanded=active):
        st.caption('Five fixed shadow families; previously examined 2022–2024 development. No 2025 pass, 2026 selection or promotion.')
        st.write('Status: '+status.get('phase','unknown')+' · '+status.get('step',''))
        summary=path/'SUMMARY.json'
        if summary.exists():
            try:data=json.loads(summary.read_text(encoding='utf-8'))
            except (OSError,ValueError):st.info('Saved aggregate report is temporarily unavailable.');return active
            rows=[]
            for r in data.get('rows',[]):
                ci=r.get('corrected_ci95')
                rows.append({'Family':r['family'],'Stat':r['stat'],'Inputs':r['arm'],'Variant':r['kind'],
                             'Rows':r['n'],'Games':r['games'],'Reference':r['reference'],
                             'Reference loss':r['control_loss'],'Challenger loss':r['new_loss'],
                             'Change %':-100*r['relative_reduction'],
                             'Corrected 95% CI':str(ci),'Nominee':r['discovery_nomination']})
            frame=pd.DataFrame(rows)
            if len(frame):
                family=st.selectbox('Improvement family',['All']+sorted(frame.Family.unique().tolist()))
                if family!='All':frame=frame[frame.Family.eq(family)]
                st.dataframe(frame,hide_index=True,use_container_width=True)
            trials=data.get('trials',{})
            st.caption(f"{len(trials.get('output_configurations',[]))} outputs; {len(trials.get('fit_configurations',[]))} internal fit configurations; {trials.get('fit_calls',0)} fit calls; {len(data.get('failures',[]))} failed blocks. Negative change means lower loss. A nominee still needs genuinely future confirmation.")
        else:st.info('Results appear after the fixed study finishes. This page never launches or repeats fitting.')
    return active
