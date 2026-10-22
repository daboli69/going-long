"""Manual local injury-adjusted simulator controls, never an automatic promotion."""
import pandas as pd
import streamlit as st
from pathlib import Path
from lab.props import injury_adjusted as I


def current_backend():
    """An open Streamlit session may retain the pre-update module object.

    This module only defines helpers; live simulations run in separate processes.
    Refresh this one stale import instead of requiring another simulation.
    """
    if not callable(getattr(I,'latest_completed',None)):
        import importlib
        importlib.invalidate_caches()
        importlib.reload(I)
    return I


def render(root=None,show_results=True):
    current_backend()
    root=I.ROOT if root is None else Path(root)
    with st.expander('Rerun simulations with refreshed injuries',expanded=True):
        st.caption('Refresh injuries with START_HERE option 6 first. Then select one unstarted game and run. '
                   'This creates a separate v1/v2 injury-adjusted shadow revision; original forecasts remain saved. '
                   'Existing within-position redistribution is an assumption, not a validated improvement. '
                   'Baseline B, winner ensemble, independent game projections and Phase10 sheets are not injury-adjusted here.')
        try:
            games=I.W.load_games()
            now=pd.Timestamp.now(tz='UTC')
            games=games[games.season.eq(now.year)&games.home_score.isna()].copy()
            games=games[[I.W.kickoff(r.gameday,r.gametime)>now for r in games.itertuples()]]
            choices=games.game_id.tolist()
        except (OSError,ValueError,KeyError):choices=[]
        if not choices:st.info('No unstarted games available. Refresh local NFL data first.')
        else:
            selected=st.selectbox('Game to update',choices,key='injury_sim_game')
            if st.button('Run injury-adjusted simulation',key='injury_sim_run'):
                try:
                    request=I.launch(selected,root=root)
                    st.success('Started locally in the background. Click Refresh simulation status to check progress.')
                except Exception as error:
                    st.error(str(error) if isinstance(error,ValueError) else 'Could not start; original forecasts unchanged.')
        st.button('Refresh simulation status',key='injury_sim_status',help='Checks the saved job. To start a new simulation, use Run injury-adjusted simulation.')
        pointer=root/'LATEST_JOB.json'
        if not pointer.exists():
            st.info('No injury-adjusted simulation has been run yet.')
            return
        request=I.read(pointer);job=Path(request['path']);status=I.read(job/'STATUS.json')
        st.caption(f"Game: {request['game_id']} · started: {request['created_at']} · status: {status['state']}")
        if status['state']=='failed':st.error(status.get('error','Simulation failed.'));return
        if status['state']!='complete':st.info(status.get('note','Queued locally. Refresh status for progress.'));return
        if not show_results:
            st.success('Completed. The main game table below now displays this injury-adjusted revision. Originals are inside its archive expander.')
            return
        st.warning(status['warning'])
        st.caption('Training cutoff: '+status['training_cutoff'])
        if status['excluded']:
            st.markdown('**Unavailable players excluded from this revision**')
            excluded=pd.DataFrame(status['excluded'])
            try:
                roster=pd.read_parquet(I.W.RAW_DIR/f"roster_weekly_{request['game_id'].split('_')[0]}.parquet",
                                       columns=['gsis_id','full_name']).drop_duplicates('gsis_id',keep='last')
                excluded=excluded.merge(roster,left_on='pid',right_on='gsis_id',how='left')
            except (OSError,KeyError):pass
            st.dataframe(excluded,hide_index=True,use_container_width=True)
        path=Path(status['projection_path']);table=pd.read_csv(path)
        st.markdown('**New injury-adjusted player simulations**')
        show_workload(status)
        st.dataframe(table,hide_index=True,use_container_width=True)
        st.download_button('Download injury-adjusted projections',path.read_bytes(),file_name='injury_adjusted_'+request['game_id']+'.csv',key='injury_sim_download')


def show_workload(status):
    if status.get('workload_path'):
        roles=pd.read_csv(status['workload_path'])
        st.markdown('**Modeled backfield workload (includes backups)**')
        st.caption('Shares are model assumptions based on earlier usage, not confirmed coaching plans. Carry share includes quarterback runs. Missing individual history uses the existing position fallback; baseline stays unavailable.')
        st.dataframe(roles[roles.position.isin(['RB','FB','QB'])],hide_index=True,use_container_width=True,
                     column_config={'carry_share':st.column_config.NumberColumn('Share of team carries',format='percent'),
                                    'target_share':st.column_config.NumberColumn('Share of team targets',format='percent')})


def render_game(game,original,scores=None,preview=False,root=None):
    """Default to an explicitly labelled shadow copy, not an obsolete preview."""
    latest=current_backend().latest_completed(root).get(game)
    label=f"{game.split('_')[2]} @ {game.split('_')[3]}"
    if latest:
        st.markdown(f"**{label} · latest injury-adjusted shadow revision**")
        st.caption('Created '+latest['created_at']+' · '+latest['warning'])
        show_workload(latest)
        frame=pd.read_csv(latest['projection_path'])
        provenance=['simulation_revision','decision_at','anchor_mode','simulator_training_through_season',
                    'player_training_through_week','player_training_season','availability_snapshot_sha256']
        st.dataframe(frame.drop(columns=provenance,errors='ignore').round(1),hide_index=True,use_container_width=True)
        st.download_button('Download latest injury-adjusted '+label,Path(latest['projection_path']).read_bytes(),
                           file_name='injury_adjusted_'+game+'.csv',key='injury_game_download_'+game)
        with st.expander('Original saved forecast / preview — not updated for these injuries'):
            st.warning('Historical reference only: may include players now ruled out.')
            st.dataframe(I.W.projection_table(original,scores).round(1),hide_index=True,use_container_width=True)
    else:
        st.markdown(f'**{label}**'+(' · preview — no completed injury-adjusted copy' if preview else ' · original archived pregame'))
        st.dataframe(I.W.projection_table(original,scores).round(1),hide_index=True,use_container_width=True)
