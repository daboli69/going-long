"""View-only aggregate Amendment8 results; no source or player rows."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from lab.fpds_improve.storage import ROOT


def combine_saved_studies(path,data):
    parent=data.get('repair_parent')
    if not parent:return data
    source=path.parent/parent/'SUMMARY.json'
    if not source.exists():return data
    previous=json.loads(source.read_text(encoding='utf-8'))
    result=dict(data)
    result['rows']=[r for r in previous.get('rows',[]) if r['family']!='opportunity']+data.get('rows',[])
    result['original_failed_blocks']=len(previous.get('failures',[]))
    result['original_output_count']=len(previous.get('trials',{}).get('output_configurations',[]))
    return result


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
            try:data=combine_saved_studies(path,json.loads(summary.read_text(encoding='utf-8')))
            except (OSError,ValueError):st.info('Saved aggregate report is temporarily unavailable.');return active
            rows=[]
            for r in data.get('rows',[]):
                ci=r.get('corrected_ci95')
                rows.append({'Family':r['family'],'Stat':r['stat'],'Inputs':r['arm'],'Variant':r['kind'],
                             'Rows':r['n'],'Games':r['games'],'Reference':r['reference'],
                             'Reference loss':r['control_loss'],'Challenger loss':r['new_loss'],
                             'Change %':-100*r['relative_reduction'],
                             '80% coverage (%)':100*r['diagnostics']['coverage80'] if 'coverage80' in r.get('diagnostics',{}) else None,
                             'Corrected 95% CI':str(ci),'Nominee':r['discovery_nomination']})
            frame=pd.DataFrame(rows)
            if len(frame):
                family=st.selectbox('Improvement family',['All']+sorted(frame.Family.unique().tolist()))
                if family!='All':frame=frame[frame.Family.eq(family)]
                st.dataframe(frame,hide_index=True,use_container_width=True)
            trials=data.get('trials',{})
            quantile=[r for r in data.get('rows',[]) if r['kind']=='quantile' and 'coverage80' in r.get('diagnostics',{})]
            if quantile:
                st.caption('Direct quantile range coverage (nominal target 80%): '+', '.join(f"{r['stat']} {r['diagnostics']['coverage80']:.1%}" for r in quantile)+'. Better median error does not establish calibrated intervals.')
            if data.get('repair_parent'):
                st.caption(f"Combined view: original non-opportunity results plus the separate opportunity repair. Original {data.get('original_failed_blocks',0)} failed blocks remain recorded; original nominations are unchanged. {data.get('original_output_count',0)} original outputs plus {len(trials.get('output_configurations',[]))} repaired output versions.")
            st.caption(f"{len(trials.get('output_configurations',[]))} outputs; {len(trials.get('fit_configurations',[]))} internal fit configurations; {trials.get('fit_calls',0)} fit calls; {len(data.get('failures',[]))} failed blocks. Negative change means lower loss. A nominee still needs genuinely future confirmation.")
        else:st.info('Results appear after the fixed study finishes. This page never launches or repeats fitting.')
    return active
