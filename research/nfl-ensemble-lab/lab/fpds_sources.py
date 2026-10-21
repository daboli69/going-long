"""Authoritative full-history source policy. Inbox files are read only."""
from pathlib import Path

HISTORY_FOLDER='All historical data from 2021-2026 week 6'
POLICY='full-history-authority-v1'


def select_sources(source=None,parse=None):
    from .fpds_research.common import SOURCE
    from .fpds_research.protocol import title
    root=Path(source) if source is not None else SOURCE
    folder=root/HISTORY_FOLDER
    base={}
    for p in sorted(folder.glob('*.csv')):
        table,week=title(p)
        rank=(week or 6,p.stat().st_mtime_ns,str(p))
        if table not in base or rank>base[table][0]:base[table]=(rank,p)
    if not base:raise FileNotFoundError('Authoritative FPDS full-history folder is missing or empty; loose Inbox files are not a fallback')
    selected={table:p for table,(_,p) in base.items()}
    candidates={}
    for p in root.rglob('*.csv'):
        if p.parent==folder:continue
        table,week=title(p)
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
    return sorted(set(p for _,p in base.values())|set(selected.values()))


def install():
    from .fpds_research import ingest
    ingest.source_files=select_sources
