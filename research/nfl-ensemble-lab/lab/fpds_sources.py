"""Authoritative full-history source policy. Inbox files are read only."""
from pathlib import Path
import os
import re

HISTORY_FOLDER='All historical data from 2021-2026 week 6'
POLICY='full-history-authority-v1'


def folder_week(path):
    """Managed folders name the FORECAST week, not the final statistics week."""
    p=Path(path)
    hit=re.fullmatch(r'Week (\d+)',p.parent.name,re.I)
    return int(hit[1]) if hit and p.parent.parent.name==HISTORY_FOLDER and 7<=int(hit[1])<=18 else None


def prediction_week():
    value=os.environ.get('NFL_FPDS_TARGET_WEEK')
    if value:
        week=int(value)
        if not 7<=week<=18:raise ValueError('Forecast week must be 7 through 18')
        return week
    from .data_pipeline import FEATURE_STORE
    if FEATURE_STORE.exists():
        import pandas as pd
        g=pd.read_parquet(FEATURE_STORE)
        upcoming=g[g.season.eq(2026)&g.week.between(7,18)&pd.to_datetime(g.kickoff_utc,utc=True).gt(pd.Timestamp.now(tz='UTC'))&~g.completed.fillna(False)]
        if len(upcoming):return int(upcoming.sort_values('kickoff_utc').iloc[0].week)
    return None


def select_sources(source=None,parse=None,week=None):
    from .fpds_research.common import SOURCE
    from .fpds_research.protocol import title
    root=Path(source) if source is not None else SOURCE
    folder=root/HISTORY_FOLDER
    base={}
    for p in sorted(folder.glob('*.csv')):
        table,marker=title(p)
        rank=(marker or 6,p.stat().st_mtime_ns,str(p))
        if table not in base or rank>base[table][0]:base[table]=(rank,p)
    if not base:raise FileNotFoundError('Authoritative FPDS full-history folder is missing or empty; loose Inbox files are not a fallback')
    target=week if week is not None else prediction_week()
    selected={table:p for table,(_,p) in base.items()}
    candidates={}
    for p in root.rglob('*.csv'):
        if p.parent==folder:continue
        managed=folder_week(p)
        if managed is not None:continue
        table,week=title(p)
        if target is not None and week is not None and week>=target:continue
        if table in base and week is not None and week>base[table][0][0]:
            candidates.setdefault(table,[]).append((week,p.stat().st_mtime_ns,str(p),p))
    if candidates:
        if parse is None:
            from .fpds_research.ingest import parsed
            parse=parsed
        for table,options in candidates.items():
            original=parse(base[table][1])[1]
            chosen=max(options)[-1];meta=parse(chosen)[1]
            if meta['header']!=original['header'] or meta.get('group_header')!=original.get('group_header'):
                raise ValueError('A newer FPDS export changed schema; review it before replacement')
            if any(not set(weeks).issubset(meta['coverage'].get(season,[])) for season,weeks in original['coverage'].items()):
                raise ValueError('A newer loose FPDS export is incomplete; full historical season/week coverage is required')
            selected[table]=chosen
    result=set(p for _,p in base.values())|set(selected.values())
    # Managed weekly exports may contain 2026 only. The importer overlays source
    # weeks onto the authority instead of throwing away 2021-25 history.
    for p in folder.glob('Week */*.csv'):
        managed=folder_week(p)
        if managed is None or target is None or managed>target:continue
        table,marker=title(p)
        if table not in base:raise ValueError('An unrecognized weekly table requires schema review')
        if marker is not None and marker>=managed and table!='injury_reports':
            raise ValueError('Weekly statistics filename reaches the forecast week; use completed prior-week data')
        if parse is None:
            from .fpds_research.ingest import parsed
            parse=parsed
        original=parse(base[table][1])[1];meta=parse(p)[1]
        if meta['header']!=original['header'] or meta.get('group_header')!=original.get('group_header'):
            raise ValueError('A weekly FPDS export changed schema; review it before replacement')
        result.add(p)
    return sorted(result)


def install():
    from .fpds_research import ingest
    ingest.source_files=select_sources
