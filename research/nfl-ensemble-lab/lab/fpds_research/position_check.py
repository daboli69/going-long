"""Stop the weekly run when a position enters or leaves an FPDS table.

A model trained on weeks without a position in a table and asked to predict
from a week that has it sees columns that were empty in training. That is the
2026 Week 9 running-back change in the receiving tables. The check reads
position counts only; no subscription values leave the private import.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from .common import LAB_ROOT

ACK=LAB_ROOT/'docs'/'fpds_position_ack.json'
MIN_HISTORY=4   # weeks a table must exist before a new position counts as a change
MIN_ROWS=10     # ignore a handful of oddly labelled players
MIN_SHARE=0.05  # ...and positions under this share of the table rows that week


class PositionShift(ValueError):
    pass


def counts(manifest):
    """Rows by table, season, week and position for every table that has one."""
    out=[]
    for t in manifest['working_tables']:
        if '_position' not in pq.read_schema(t['private_path']).names:continue
        d=pd.read_parquet(t['private_path'],columns=['season','week','_position']).dropna()
        d=d.groupby(['season','week','_position']).size().rename('rows').reset_index()
        out.append(d.rename(columns={'_position':'position'}).assign(table=t['table']))
    cols=['table','season','week','position','rows']
    return pd.concat(out,ignore_index=True)[cols] if out else pd.DataFrame(columns=cols)


def shifts(frame,min_history=MIN_HISTORY,min_rows=MIN_ROWS,min_share=MIN_SHARE):
    """Positions that appear after a table's early weeks, or vanish before its latest week.

    Only shifts dated in the table's latest season are returned: older ones are
    already in the training rows and no weekly action can change them.
    """
    found=[]
    for table,d in frame.groupby('table'):
        d=d.assign(key=d.season.astype(int)*100+d.week.astype(int))
        weeks=sorted(d.key.unique())
        if len(weeks)<=min_history:continue
        total=d.groupby('key').rows.sum()
        d=d[(d.rows>=min_rows)&(d.rows/d.key.map(total)>=min_share)]
        for position,p in d.groupby('position'):
            first,last=int(p.key.min()),int(p.key.max())
            base={'table':table,'position':position}
            if first>weeks[min_history-1]:
                found.append({**base,'kind':'appeared','season':first//100,'week':first%100,
                              'weeks_without':weeks.index(first),'rows':int(p[p.key.eq(first)].rows.sum())})
            present=p.key.nunique()
            if last<weeks[-1] and present>=min_history and present>=0.5*(weeks.index(last)+1):
                gone=weeks[weeks.index(last)+1]
                found.append({**base,'kind':'vanished','season':gone//100,'week':gone%100,
                              'weeks_without':len(weeks)-1-weeks.index(last),'rows':0})
    latest=frame.groupby('table').season.max().astype(int)
    found=[f for f in found if f['season']==latest[f['table']]]
    return sorted(found,key=lambda f:(f['table'],f['position'],f['kind']))


def acknowledged(path=None):
    path=Path(path or ACK)
    if not path.exists():return set()
    return {(a['table'],a['position'],a['kind'],int(a['season']),int(a['week']))
            for a in json.loads(path.read_text(encoding='utf-8'))['acknowledged']}


def check(manifest,ack_path=None):
    """Raise PositionShift on any shift not listed in the acknowledgement file."""
    found=shifts(counts(manifest));known=acknowledged(ack_path)
    new=[f for f in found if (f['table'],f['position'],f['kind'],f['season'],f['week']) not in known]
    if new:
        lines=[f"{f['table']}: {f['position']} {f['kind']} in {f['season']} Week {f['week']} "
               f"({f['weeks_without']} weeks without it, {f['rows']} rows)" for f in new]
        raise PositionShift('FPDS position coverage changed; training and prediction rows no longer match.\n'
                            +'\n'.join(lines)+f'\nRe-import history with the position, or list each line in {ACK.name} '
                            'with table, position, kind, season and week to accept it.')
    return found


if __name__=='__main__':
    from .audit import latest
    for f in shifts(counts(latest())):print(f)
