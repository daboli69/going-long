"""Corroborate existing injury feeds with imported FPDS; monitoring only.

Never overwrites source archives, feeds a model, or changes a frozen forecast.
"""
from pathlib import Path
from datetime import datetime
import pandas as pd

from .fpds_research.common import now,stamp,read,write_once,atomic


def normalize_status(value):
    text=str(value).strip().lower().replace('_',' ').replace('-',' ')
    return {'out':'out','doubtful':'doubtful','questionable':'questionable','probable':'probable',
            'active':'active','inactive':'inactive','ir':'ir','injured reserve':'ir','reserve/injured':'ir',
            'pup':'pup','physically unable to perform':'pup'}.get(text,'unknown')


def reconcile(rows,games,asof):
    """Pure, source-preserving reconciliation; no name guesses or absent=healthy."""
    asof=pd.Timestamp(asof)
    kickoffs={team:(r.game_id,pd.Timestamp(r.kickoff_utc)) for r in games.itertuples() for team in (r.home_team,r.away_team)}
    valid=[]
    excluded=0
    for row in rows.to_dict('records'):
        team=row.get('team');pid=row.get('pid');available=pd.to_datetime(row.get('available_at'),utc=True,errors='coerce')
        pair=kickoffs.get(team)
        if pd.isna(pid) or not pid or pair is None or pd.isna(available) or available>=asof or available>=pair[1] or asof>=pair[1]:
            excluded+=1;continue
        valid.append({**row,'available_at':available,'status':normalize_status(row.get('status')),'game_id':pair[0]})
    frame=pd.DataFrame(valid);result=[]
    if frame.empty:return pd.DataFrame(),{'excluded_rows':excluded,'players':0,'confirmed':0,'conflicts':0,'fpds_only':0,'stale_source_rows':0}
    for (game,team,pid),group in frame.groupby(['game_id','team','pid']):
        sources={};ambiguous=False
        for source,z in group.groupby('source'):
            z=z[z.available_at.eq(z.available_at.max())]
            statuses=set(z.status)-{'unknown'}
            status=next(iter(statuses)) if len(statuses)==1 else 'unknown'
            ambiguous|=len(statuses)>1
            sources[source]={'status':status,'available_at':z.available_at.max().isoformat()}
        known={k:v for k,v in sources.items() if v['status']!='unknown'}
        official={k:v for k,v in known.items() if k.startswith('official_')}
        selected=None;status='unknown';reason='no known status'
        if official:
            latest=max(v['available_at'] for v in official.values())
            candidates={k:v for k,v in official.items() if v['available_at']==latest}
            if len({v['status'] for v in candidates.values()})==1:
                selected=sorted(candidates)[0];status=candidates[selected]['status'];reason='latest observed official report'
            else:ambiguous=True;reason='simultaneous official conflict'
        elif known:
            if len({v['status'] for v in known.values()})==1:
                selected='secondary agreement' if len(known)>1 else next(iter(known))
                status=next(iter(known.values()))['status'];reason='provisional secondary context; official unavailable'
            else:reason='secondary-source conflict; unresolved'
        conflict=ambiguous or len({v['status'] for v in known.values()})>1
        fpds=sources.get('fpds',{}).get('status','unknown')
        confirmations=[k for k,v in known.items() if k!='fpds' and fpds!='unknown' and v['status']==fpds]
        result.append({'game_id':game,'team':team,'pid':pid,'effective_status':status,'selected_source':selected,
                       'reason':reason,'conflict':conflict,'fpds_confirmed':bool(confirmations) and not conflict,
                       'fpds_only':set(known)=={'fpds'},'sources':sources,
                       'oldest_source_age_hours':max((asof-pd.Timestamp(v['available_at'])).total_seconds()/3600 for v in sources.values()),
                       'model_input':False})
    d=pd.DataFrame(result)
    return d,{'excluded_rows':excluded,'players':len(d),'confirmed':int(d.fpds_confirmed.sum()),
              'conflicts':int(d.conflict.sum()),'fpds_only':int(d.fpds_only.sum()),
              'stale_source_rows':int((asof-frame.available_at).dt.total_seconds().gt(86400).sum())}


def source_rows(week,summary,games):
    """Read cached existing feeds only. Caller decides whether to refresh them."""
    from . import availability as A,live,extra_sources as X
    from .config import RAW_DIR
    from .fpds_ingest import canonical_team
    from .props.lines import normalized_name
    rows=[];errors=[]
    if summary is not None:
        context=pd.read_parquet(Path(summary['path'])/'CONTEXT_PRIVATE.parquet')
        first=summary.get('source_first_observed_at',summary['created_at'])
        rows += [{'team':r.team,'pid':r.pid,'status':r.status,'available_at':first,'source':'fpds'} for r in context.itertuples()]
    roster_path=RAW_DIR/'roster_weekly_2026.parquet'
    roster=pd.read_parquet(roster_path) if roster_path.exists() else pd.DataFrame()
    mapping={};known=set()
    if len(roster):
        roster=roster[roster.week.eq(week)].copy()
        roster['canonical_team']=roster.team.map(canonical_team);roster['normal']=roster.full_name.map(normalized_name)
        for key,z in roster.groupby(['canonical_team','normal']):
            ids=z.gsis_id.dropna().unique()
            if len(ids)==1:mapping[key]=ids[0]
        known=set(zip(roster.canonical_team,roster.gsis_id))
    asof=pd.Timestamp.now(tz='UTC')
    if summary is None:
        from .nflmeta_injuries import source_rows as nflmeta_rows
        rows += nflmeta_rows(2026,week,mapping,asof=asof)
    try:
        official=A.load_injury_rows([2026])
        if len(official):
            official=official[official.season.eq(2026)&official.week.eq(week)&pd.to_datetime(official.available_at,utc=True).lt(asof)]
            official=A.pregame_injuries(official,games)
            rows += [{'team':r.team,'pid':r.gsis_id if (r.team,r.gsis_id) in known else None,'status':r.report_status,
                      'available_at':r.available_at,'source':'official_nflverse'} for r in official.itertuples()]
    except Exception as e:errors.append('official_nflverse: '+type(e).__name__)
    try:
        official,retrieved=X.nflcom_latest()
        if len(official):
            official=official[official.season.eq(2026)&official.week.eq(week)]
            rows += [{'team':canonical_team(r.team),'pid':mapping.get((canonical_team(r.team),normalized_name(r.full_name))),
                      'status':r.report_status,'available_at':retrieved,'source':'official_nflcom'} for r in official.itertuples()]
    except Exception as e:errors.append('official_nflcom: '+type(e).__name__)
    try:
        espn,retrieved=live.espn_full()
        timestamp=pd.Timestamp(datetime.strptime(retrieved,'%Y%m%dT%H%M%SZ'),tz='UTC') if retrieved else None
        rows += [{'team':canonical_team(r.team),'pid':mapping.get((canonical_team(r.team),normalized_name(r.player))),
                  'status':r.status,'available_at':timestamp,'source':'espn'} for r in espn.itertuples()]
    except Exception as e:errors.append('espn: '+type(e).__name__)
    return pd.DataFrame(rows),errors


def update_week(week,state=None,games=None,use_csv=True):
    from .fpds_drop import STATE
    from .data_pipeline import FEATURE_STORE
    state=Path(state) if state is not None else STATE
    pointer=state/f'INJURIES_W{week:02d}.json'
    summary=read(pointer) if use_csv and pointer.exists() else None
    games=pd.read_parquet(FEATURE_STORE) if games is None else games
    games=games[games.season.eq(2026)&games.week.eq(week)].copy()
    games['kickoff_utc']=pd.to_datetime(games.kickoff_utc,utc=True)
    rows,errors=source_rows(week,summary,games)
    result,counts=reconcile(rows,games,pd.Timestamp.now(tz='UTC'))
    destination=state/'confirmations'/f'2026_w{week:02d}_{stamp()}';destination.mkdir(parents=True,exist_ok=False)
    # Sources are JSON strings in the private row file; only aggregates go to the UI.
    if len(result):
        import json
        result['sources']=result.sources.map(lambda x:json.dumps(x,sort_keys=True))
    result.to_parquet(destination/'CONFIRMATION_PRIVATE.parquet',index=False)
    metadata={'created_at':now(),'forecast_week':week,'path':str(destination),**counts,'source_errors':errors,
              'fpds_source_sha256':summary['source_sha256'] if summary else None,'model_input':False,
              'policy':'Latest observed official status first. FPDS confirms or supplies provisional missing context. Secondary conflicts stay unresolved. Missing report rows never imply healthy; no automatic model override.',
              'by_team':result.groupby('team').agg(players=('pid','size'),confirmed=('fpds_confirmed','sum'),conflicts=('conflict','sum')).reset_index().to_dict('records') if len(result) else []}
    write_once(destination/'SUMMARY.json',metadata)
    from .fpds_worker import retry_atomic
    retry_atomic(atomic,state/f'CONFIRMATION_W{week:02d}.json',metadata)
    retry_atomic(atomic,state/'LATEST_CONFIRMATION.json',metadata)
    return metadata


def update_imported_weeks():
    from .fpds_drop import STATE
    if not STATE.exists():return []
    pointers=list(STATE.glob('INJURIES_W*.json'))
    if not pointers:return []
    from .data_pipeline import FEATURE_STORE
    games=pd.read_parquet(FEATURE_STORE)
    results=[]
    for pointer in pointers:
        week=read(pointer)['forecast_week']
        if ((games.season==2026)&(games.week==week)&pd.to_datetime(games.kickoff_utc,utc=True).gt(pd.Timestamp.now(tz='UTC'))).any():
            result=update_week(week,games=games)
            if result is not None:results.append({k:result[k] for k in ['forecast_week','players','confirmed','conflicts','fpds_only']})
    return results
