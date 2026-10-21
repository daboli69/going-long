"""Private, offline FPDS CSV ingestion. CLI output is counts/metadata only.

Raw rows, unmatched identities and feature values must remain under ignored data/.
Never calls a website, moves a source, or overwrites a prior import.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import traceback

import numpy as np
import pandas as pd
from .config import LAB_ROOT, RAW_DIR, CACHE_DIR
from .ingest import normalize_team
from .market81 import NAME_TO_ABBR
from .props.lines import normalized_name, player_map

SOURCE = LAB_ROOT.parents[1] / 'FantasyPoints' / 'Inbox'
RAW = RAW_DIR / 'fpds'
CACHE = CACHE_DIR / 'fpds'
CACHE_SCHEMA = 4
ALIASES = {
    'receiving_advanced':'receiving_advanced','receiving_stats':'receiving_advanced',
    'receiving_routes_run':'receiving_alignment','receiving_alignment':'receiving_alignment',
    'rushing_advanced':'rushing_advanced','rushing_stats':'rushing_advanced',
    'rushing_bell_cow':'bell_cow','bell_cow_report':'bell_cow',
    'efficiency':'efficiency','rb_wr_efficiency':'efficiency',
    'run_pass_report':'run_pass_report','coverage_matrix':'coverage_matrix',
    'receiving_man_vs_zone':'receiving_man_zone','receiving_situation':'receiving_man_zone',
    'receiving_separation_by_alignment':'separation_alignment',
    'receiving_separation_by_breaks':'separation_breaks','receiving_separation_by_role':'separation_breaks',
    'receiving_separation_by_coverage':'separation_coverage','receiving_separation_by_routes':'separation_routes',
    'passing_advanced':'passing_advanced','passing_stats':'passing_advanced',
    'passing_depth':'passing_depth','passing_depth_of_target':'passing_depth',
    'pace':'team_pace',
}
# Header-selected features are fixed in Amendment 4 before fitting.
FEATURE_FIELDS = {
    'receiving_advanced':{'rte','rte_pct','adot','ay_share','tgt_pct','tprr','yprr','yac_rec','mtf_rec','wide_rte_pct','slot_rte_pct','inline_rte_pct','back_rte_pct','i20_tgt','eztgt'},
    'receiving_alignment':{'rte','rte_pct','wide_rte_pct','slot_rte_pct','inline_rte_pct','back_rte_pct','tm_rte_pct','tprr','yprr'},
    'bell_cow':{'snaps','snap_pct','att_pct','rte','rte_pct','tgt_pct'},
    'rushing_advanced':{'exp_run_pct','i5_pct','success_pct','succ_pct','stuff_pct','mtf_att','yaco_att','ybco_att'},
    'efficiency':{'yprr','ypt','yac_rec','mtf_rec','mtf_att','yaco_att','yaco_rec','exp_rec_pct','exp_run_pct','exp_play_pct','yfs_touch','mtf_touch','yaco_touch'},
    'run_pass_report':{'pass_pct','rush_pct'},
}
KEY_FIELDS = {'season':{'season','year'},'week':{'week','wk'},'name':{'name','player','player_name'},
              'team':{'team','tm','team_name'},'position':{'pos','position'},'gsis_id':{'gsis_id','gsis'},'player_id':{'player_id','playerid','id'},
              'game_id':{'game_id','gameid'},'games':{'g','gp','games'}}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slug(value):
    value = re.sub(r'([a-z0-9])([A-Z])',r'\1_\2',str(value))
    return re.sub(r'[^a-z0-9]+','_',value.lower().replace('%',' pct ')).strip('_')


def table_name(path):
    stem = re.sub(r'\s*\(\d+\)$','',Path(path).stem).removesuffix('Export')
    name = slug(stem)
    return ALIASES.get(name,name)


def write_once(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    def clean(v):
        if isinstance(v,dict):return {k:clean(a) for k,a in v.items()}
        if isinstance(v,(list,tuple)):return [clean(a) for a in v]
        if isinstance(v,(float,np.floating)) and not np.isfinite(v):return None
        if isinstance(v,np.generic):return v.item()
        return v
    with path.open('x',encoding='utf-8') as f:
        json.dump(clean(value),f,indent=2,allow_nan=False,default=str)


def number(value,percent=False):
    text=str(value).strip().replace(',','').replace('\u2212','-')
    if not text or text.lower() in {'-','--','nan','n/a','null','none'}:return np.nan
    try:
        result=float(text.removesuffix('%'))
        return result/100 if text.endswith('%') or percent else result
    except (ValueError,OverflowError):return np.nan


def parse(path):
    """Read two-row export headers without emitting any data or exception text."""
    path=Path(path)
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f);top=next(reader,[]);second=next(reader,[])
        second_is_header=any(slug(x) in {'player','team','season','week','year','name','pos','position','coach'} for x in second)
        detail=second if second_is_header else top
        records=list(reader) if second_is_header else [second]+list(reader)
    if not detail or len(detail)!=len(top):raise ValueError('Invalid header shape')
    groups=[];current='';qualified=[];seen={}
    for group,field in zip(top if second_is_header else ['']*len(top),detail):
        current=group.strip() or current
        groups.append(current)
        key='__'.join(x for x in (slug(current),slug(field)) if x) or 'unnamed'
        seen[key]=seen.get(key,0)+1
        qualified.append(key+(f'__{seen[key]}' if seen[key]>1 else ''))
    fields={k:[i for i,h in enumerate(detail) if slug(h) in terms] for k,terms in KEY_FIELDS.items()}
    # Older exports append a two-column metric glossary after a blank line.
    # Recognize it only when every label is an actual column header; do not
    # silently discard arbitrary short/malformed data rows.
    footer_rows=0
    for cut,row in enumerate(records):
        if cut and not any(str(x).strip() for x in row):
            tail=[r for r in records[cut+1:] if any(str(x).strip() for x in r)]
            if tail and all(len(r)==2 and slug(r[0]) in {slug(h) for h in detail} for r in tail):
                footer_rows=len(tail);records=records[:cut];break
    good=[r for r in records if any(str(x).strip() for x in r) and len(r)==len(detail)]
    malformed=sum(bool(any(str(x).strip() for x in r)) and len(r)!=len(detail) for r in records)
    d=pd.DataFrame(good,columns=qualified)
    for key,indices in fields.items():
        if len(indices)==1:d['_'+key]=d.iloc[:,indices[0]]
    for key in ('season','week'):
        if '_'+key in d:d['_'+key]=pd.to_numeric(d['_'+key],errors='coerce')
    g=pd.to_numeric(d.get('_games',pd.Series(dtype=float)),errors='coerce')
    explicit_std=any(re.search(r'\b(?:season.to.date|cumulative|ytd|std)\b',str(h),re.I) for h in detail+groups)
    meta={'name':path.name,'relative_path':None,'table':table_name(path),'bytes':path.stat().st_size,
          'modified_at':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
          'modified_ns':path.stat().st_mtime_ns,'sha256':sha(path),'header_rows':2 if second_is_header else 1,
          'group_header':top if second_is_header else [],'header':detail,'qualified_header':qualified,
          'key_columns':{k:[detail[i] for i in indices] for k,indices in fields.items()},
          'rows':len(good),'malformed_rows':malformed,'footer_glossary_rows':footer_rows,'rows_with_games_gt_one':int(g.gt(1).sum()),
          'season_to_date':not bool(fields['week']) or explicit_std,
          'weekly_cumulative':bool(fields['week']) and (explicit_std or bool(g.gt(1).any()))}
    coverage={}
    if '_season' in d:
        for season,z in d.dropna(subset=['_season']).groupby('_season'):
            if float(season).is_integer() and 2010<=season<=2030:
                weeks=sorted(int(w) for w in z.get('_week',pd.Series(dtype=float)).dropna().unique() if float(w).is_integer() and 1<=w<=22)
                coverage[str(int(season))]=weeks
    meta['coverage']=coverage
    return d,meta


def canonical_team(value):
    known=set(NAME_TO_ABBR.values())
    try:raw=normalize_team(str(value).strip().upper())
    except ValueError:raw=None
    if raw in known:return raw
    aliases={normalized_name(k):v for k,v in NAME_TO_ABBR.items()}
    return aliases.get(normalized_name(value))


def feature_columns(meta):
    selected=[];table=meta['table'];allowed=FEATURE_FIELDS.get(table,set())
    for i,(field,col) in enumerate(zip(meta['header'],meta['qualified_header'])):
        if slug(field) not in allowed:continue
        if table=='run_pass_report' and slug(meta['group_header'][i] if meta['group_header'][i] else next((v for v in reversed(meta['group_header'][:i]) if v),'')) not in {'overall','neutral','leading_by_7','trailing_by_7'}:continue
        selected.append((col,'%' in field))
    return selected


def normalize(frame,meta,mapping,known_ids):
    """Exact map only. Unmatched details are returned for a PRIVATE report."""
    d=frame.copy();d['table']=meta['table'];d['season']=pd.to_numeric(d.get('_season',np.nan),errors='coerce')
    d['week']=pd.to_numeric(d.get('_week',np.nan),errors='coerce')
    d['source_sha256']=meta['sha256'];d['source_name']=meta['name']
    d['observed_at']=meta['imported_at'];d['season_to_date']=meta['season_to_date'];d['weekly_cumulative']=meta['weekly_cumulative']
    player='_gsis_id' in d or ('_position' in d and '_team' in d and '_name' in d)
    if player:
        d['team']=d['_team'].map(canonical_team)
        d['pid']=d.get('_name',pd.Series('',index=d.index)).map(lambda n:mapping.get(normalized_name(n)))
        if '_gsis_id' in d:
            direct=d['_gsis_id'].where(d['_gsis_id'].isin(known_ids))
            conflict=direct.notna()&d.pid.notna()&direct.ne(d.pid)
            d['pid']=direct.fillna(d.pid);d.loc[conflict,'pid']=None
        d['entity_kind']='player'
    else:
        # Coach/team tables stay team data; never assign coach/unit names to players.
        teamcol='_team' if '_team' in d else '_name' if '_name' in d else None
        d['team']=d[teamcol].map(canonical_team) if teamcol else None
        # Old team exports split city/nickname; Name also carries a team code.
        # Use only agreement among exact existing aliases, never fuzzy matching.
        alternatives=[]
        for name in ('_team','_name'):
            if name in d:alternatives.append(d[name].map(canonical_team))
        location=[i for i,h in enumerate(meta['header']) if slug(h)=='location']
        if len(location)==1 and '_team' in d:alternatives.append((d.iloc[:,location[0]].astype(str)+' '+d['_team'].astype(str)).map(canonical_team))
        if alternatives:
            choices=pd.concat(alternatives,axis=1)
            d['team']=choices.bfill(axis=1).iloc[:,0].where(choices.nunique(axis=1)<=1)
        d['pid']='';d['entity_kind']='team'
    missing=d.team.isna() | (d.entity_kind.eq('player') & d.pid.isna())
    private=d.loc[missing,[c for c in ['_name','_team','_player_id','season','week','source_name','entity_kind'] if c in d]].to_dict('records')
    valid=d[~missing & d.season.between(2010,2030)].copy()
    # Exact duplicate rows across repeated downloads; identity conflicts are handled below.
    numeric=[];values={}
    for col,percent in feature_columns(meta):
        dest=f'fp_{meta["table"]}__{col}'
        values[dest]=valid[col].map(lambda x:number(x,percent));numeric.append(dest)
    # Retain other numeric snapshot context privately, without allowing it into
    # the preregistered weekly model feature set.
    selected={c for c,_ in feature_columns(meta)}
    reserved={i for ids in meta['key_columns'].values() for i,h in enumerate(meta['header']) if h in ids}
    for i,(field,col) in enumerate(zip(meta['header'],meta['qualified_header'])):
        if col in selected or i in reserved or slug(field) in {'rank','pos','position','location','coach','role','unit'}:continue
        value=valid[col].map(lambda x:number(x,'%' in field))
        if value.notna().any():
            dest=f'fp_snapshot_{meta["table"]}__{col}';values[dest]=value;numeric.append(dest)
    keep=['season','week','team','pid','entity_kind','observed_at','season_to_date','weekly_cumulative','source_sha256','source_name']+numeric
    valid=pd.concat([valid,pd.DataFrame(values,index=valid.index)],axis=1)
    return valid[keep].copy(),private


def weekly_cache(frame,games):
    """Last-eight-source-game means, available only AFTER the source week.

    Cumulative weekly rows use the latest snapshot instead of an average.
    Season-only rows never enter this historical cache.
    """
    z=frame[frame.week.between(1,18)&~frame.season_to_date].copy()
    feature=[c for c in z if c.startswith('fp_') and not c.startswith('fp_snapshot_')]
    if z.empty or not feature:return pd.DataFrame(),{'duplicate_rows':0,'conflicting_rows':0,'unmatched_game_rows':0}
    keys=['season','week','team','pid']
    # Distinct source SHA is provenance, never an excuse to double count a row.
    z=z.sort_values('observed_at').drop_duplicates(keys+feature,keep='first')
    conflict=z.duplicated(keys,keep=False);conflicts=int(conflict.sum());z=z[~conflict].copy()
    schedule=games[games.game_type.eq('REG')][['season','week','game_id','home_team','away_team','kickoff_utc']].copy()
    schedule['kickoff_utc']=pd.to_datetime(schedule.kickoff_utc,utc=True,format='mixed')
    end=schedule.groupby(['season','week']).kickoff_utc.max()+pd.Timedelta(hours=24)
    teams=pd.concat([schedule.rename(columns={'home_team':'team'}),schedule.rename(columns={'away_team':'team'})])[['season','week','team','game_id']]
    teams['team']=teams.team.map(canonical_team)
    ambiguous=teams.duplicated(['season','week','team'],keep=False);teams=teams[~ambiguous]
    z=z.merge(teams,on=['season','week','team'],how='left',validate='many_to_one')
    unknown=int(z.game_id.isna().sum());z=z[z.game_id.notna()].copy()
    z['available_after_utc']=[end.loc[(s,w)] for s,w in zip(z.season,z.week)]
    z=z.sort_values(keys)
    groups=z.groupby(['season','team','pid'],sort=False)
    for col in feature:
        rolled=groups[col].transform(lambda x:x.rolling(8,min_periods=1).mean())
        z[col]=z[col].where(z.weekly_cumulative,rolled)
    z['source_week']=z.week.astype(int);z['usable_after_week']=z.source_week+1
    return z,{'conflicting_rows':conflicts,'unmatched_game_rows':unknown,'cache_rows':len(z)}


def asof_features(candidates,tables,strict_observation=False):
    """Left join only; FPDS can never change candidate eligibility or row count."""
    out=candidates.copy();out['_fp_order']=np.arange(len(out))
    for table,source in tables.items():
        if source.empty:continue
        features=[c for c in source if c.startswith('fp_') and not c.startswith('fp_snapshot_')]
        pieces=[]
        entity=['team','pid'] if source.entity_kind.eq('player').all() else ['team']
        source=source.copy();source['available_after_utc']=pd.to_datetime(source.available_after_utc,utc=True,format='mixed')
        source['observed_at']=pd.to_datetime(source.observed_at,utc=True,format='mixed')
        for (season,week),target in out.groupby(['season','week'],sort=False):
            cutoff=pd.to_datetime(target.get('decision_time',target.kickoff_utc),utc=True,format='mixed').min()
            prior=source[source.season.eq(season)&source.source_week.lt(week)&source.available_after_utc.lt(cutoff)]
            if strict_observation:prior=prior[prior.observed_at.lt(cutoff)]
            prior=prior.sort_values('source_week').drop_duplicates(entity,keep='last')
            selected=prior[entity+features+['source_week','available_after_utc']].rename(columns={
                'source_week':f'fp_meta_{table}_source_week','available_after_utc':f'fp_meta_{table}_available_after'})
            pieces.append(target.merge(selected,on=entity,how='left',validate='many_to_one'))
        out=pd.concat(pieces,ignore_index=True).sort_values('_fp_order')
    assert len(out)==len(candidates)
    return out.drop(columns='_fp_order').reset_index(drop=True)


def inventory_document(entries,summary,path):
    """Public-safe documentation: headers, counts and coverage; NEVER row values."""
    def esc(v):return str(v).replace('|','/').replace('\n',' ')
    schemas={};lines=['# FPDS local ingestion — metadata only','',
      'Subscription rows, unmatched identities and derived player values stay in ignored local data folders. No website login, scraping or API. Sources are read-only. Copy hashes and full private mapping report live under `data/raw/fpds/` / `data/cache/fpds/`.','',
      f"Inventory: {len(entries)} files; imported unique CSV copies {summary['raw_copies']}; weekly feature tables {len(summary['tables'])}. Import time {summary['created_at']}.",'',
      '## Files','', '| File | Bytes | Modified UTC | Data rows | Table | Schema | Season: explicit weeks | Key columns |','|---|---:|---|---:|---|---|---|---|']
    for m in entries:
        if 'error_type' in m:
            lines.append(f"| {esc(m['relative_path'])} | {m['bytes']} | {m.get('modified_at','')} | unknown | unsupported | — | unknown | {m['error_type']} |");continue
        key=json.dumps([m['group_header'],m['header']],sort_keys=True)
        if key not in schemas:schemas[key]=(f'H{len(schemas)+1:03}',m)
        sid=schemas[key][0]
        cov='; '.join(f"{s}: {','.join(map(str,w)) if w else 'season summary; week unknown'}" for s,w in sorted(m['coverage'].items())) or 'season/week unknown'
        fields='; '.join(k+'='+','.join(v) for k,v in m['key_columns'].items() if v and k not in ['name','games']) or 'no explicit key columns'
        lines.append(f"| {esc(m['relative_path'])} | {m['bytes']} | {m['modified_at']} | {m['rows']} | {m['table']} | {sid} | {cov} | {esc(fields)} |")
    grid={}
    for m in entries:
        for season,weeks in m.get('coverage',{}).items():
            cell=grid.setdefault((m['table'],season),{'weeks':set(),'snapshots':0})
            cell['weeks'].update(weeks);cell['snapshots']+=not bool(weeks)
    lines+=['','## Coverage grid','', '| Table | Season | Explicit weeks | Season-only/snapshot files | Missing regular-season weeks |','|---|---|---|---:|---|']
    for (table,season),c in sorted(grid.items()):
        missing=sorted(set(range(1,19))-c['weeks'])
        lines.append(f"| {table} | {season} | {','.join(map(str,sorted(c['weeks']))) or 'none'} | {c['snapshots']} | {','.join(map(str,missing)) or 'none'} |")
    lines+=['','## Gaps and interpretation','',
      '- Explicit weekly core history starts2021. Run/Pass Report2024 is missing; confirmation is pending, never substitute its2025 file.',
      '- Core2026 explicit weekly exports cover1–4: weeks5–6 are missing as of completed week6; weeks7–18 are future/not yet due. A `Week 6` directory label does not make a season summary into a weekly file.',
      '- Season-only/full-season or season-to-date exports are flagged. No end-of-season summary is used for predictions within that same season. Current snapshot availability is actual import time; historical weekly joins are event-time reconstructions, not proof of historical publication/version timing.',
      '- Injury Database and Cornerbacks/Shadow tables are absent by recognizable filenames/headers; no data or IDs are invented. Team Pace, Playcaller Stats, Coverage Matrix and Separation are present as summaries/snapshots rather than complete explicit weekly series.',
      f"- Missing/ambiguous player/team mapping rows: {summary['unmatched_rows']}; malformed rows: {summary['malformed_rows']}; source files without explicit season: {summary['unknown_season_files']}. Private identity details: `data/cache/fpds/imports/{summary['revision']}/unmatched.json` (never commit or print).",
      '- No GSIS/player/game IDs are guessed. Source-native IDs are kept distinct from GSIS. Team/season/week schedule joins require one exact regular-season game. Conflicting duplicates are excluded, not averaged.',
      '- Weekly features use last8 known source games (rates averaged as rates; not pooled event rates); cumulative weekly snapshots use the latest value. Source-week w enters only later weeks and after the final scheduled kickoff in w plus24h. Explicit observation-aware mode also requires actual import before decision; it is unavailable retrospectively.',
      '- Import command: `import_fpds.bat`. It copies, never moves; existing raw imports/manifests/caches are never overwritten. Exact repeat returns the saved import. Changing source content appends a new cache revision. All model-facing row data remain ignored/local.','',
      '## Header schemas (no data rows)','']
    for sid,m in schemas.values():
        lines += [f"### {sid}", '', 'Group header: '+esc(json.dumps(m['group_header'],ensure_ascii=True)), '', 'Column header: '+esc(json.dumps(m['header'],ensure_ascii=True)), '']
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')


def run(source=SOURCE,raw=RAW,cache=CACHE,players=None,games=None,document=None):
    source,raw,cache=map(Path,(source,raw,cache));started=utc()
    source=source.resolve();raw=raw.resolve();cache=cache.resolve()
    if source==raw or source in raw.parents or source==cache or source in cache.parents:raise ValueError('Outputs must be outside read-only Inbox')
    cache.mkdir(parents=True,exist_ok=True);entries=[];frames={};private=[];copies=set()
    players=pd.read_parquet(RAW_DIR/'players.parquet') if players is None else players
    mapping=player_map(players);known_ids=set(players.gsis_id.dropna())
    if games is None:
        from .data_pipeline import FEATURE_STORE
        games=pd.read_parquet(FEATURE_STORE,columns=['season','week','game_id','game_type','home_team','away_team','kickoff_utc'])
    mapping_hash=hashlib.sha256(json.dumps(sorted(mapping.items())).encode()).hexdigest()
    schedule_hash=hashlib.sha256(pd.util.hash_pandas_object(games[['season','week','game_id','game_type','home_team','away_team','kickoff_utc']].sort_values('game_id'),index=False).values.tobytes()).hexdigest()
    for path in sorted(source.rglob('*')):
        if not path.is_file():continue
        relative=str(path.relative_to(source))
        if path.suffix.lower()!='.csv':
            entries.append({'relative_path':relative,'bytes':path.stat().st_size,'error_type':'unsupported extension'});continue
        try:
            d,meta=parse(path);meta.update(relative_path=relative,source_path=str(path),imported_at=started)
            entries.append(meta)
            if meta['malformed_rows']:
                meta['error_type']='malformed_data_rows';continue
            seasons=list(meta['coverage']);season=seasons[0] if len(seasons)==1 else 'multi' if seasons else 'unknown'
            label=meta['table']+('_snapshot' if meta['season_to_date'] else '')
            dest=raw/season/(label+'.csv');dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and sha(dest)!=meta['sha256']:dest=dest.with_name(label+'__'+meta['sha256'][:16]+'.csv')
            if not dest.exists():
                with path.open('rb') as src,dest.open('xb') as output:shutil.copyfileobj(src,output)
            if sha(dest)!=meta['sha256']:raise ValueError('Copy hash mismatch')
            copies.add(str(dest))
            identifier=meta['sha256']+'_'+hashlib.sha256(relative.encode()).hexdigest()[:12]
            manifest=raw/'manifests'/(identifier+'.json')
            if manifest.exists():
                old=json.loads(manifest.read_text(encoding='utf-8'));meta['imported_at']=old['imported_at']
            else:write_once(manifest,meta|{'copied_to':str(dest),'copied_sha256':sha(dest)})
            norm,unmatched=normalize(d,meta,mapping,known_ids)
            frames.setdefault(meta['table'],[]).append(norm);private+=unmatched
        except Exception as exc:
            # No exception messages/tracebacks: CSV values must never hit the console.
            if entries and entries[-1].get('relative_path')==relative:entries[-1]['error_type']=type(exc).__name__
            else:entries.append({'relative_path':relative,'bytes':path.stat().st_size,'error_type':type(exc).__name__})
    signature=hashlib.sha256(json.dumps([CACHE_SCHEMA,mapping_hash,schedule_hash,[(m['relative_path'],m.get('sha256'),m.get('modified_ns')) for m in entries]],sort_keys=True).encode()).hexdigest()
    revision=signature[:20];destination=cache/'imports'/revision
    if (destination/'REPORT.json').exists():
        summary=json.loads((destination/'REPORT.json').read_text(encoding='utf-8'))
        if document:inventory_document(entries,summary,document)
        return summary
    if destination.exists():
        revision+='_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination=cache/'imports'/revision
    destination.mkdir(parents=True,exist_ok=False)
    stats={};tables={}
    for table,parts in frames.items():
        z=pd.concat(parts,ignore_index=True)
        result,stat=weekly_cache(z,games)
        stats[table]=stat
        if len(result):
            result.to_parquet(destination/(table+'.parquet'),index=False);tables[table]={'rows':len(result),'features':[c for c in result if c.startswith('fp_') and not c.startswith('fp_snapshot_')]}
        # Snapshot rows stay private, explicitly timestamped, and separate.
        snap=z[z.season_to_date]
        if len(snap):snap.to_parquet(destination/(table+'_snapshots.parquet'),index=False)
    write_once(destination/'unmatched.json',{'rows':private,'privacy':'PRIVATE: do not print, commit, push or upload'})
    write_once(destination/'inventory.json',entries)
    summary={'created_at':started,'revision':revision,'source':str(source),'source_files':len(entries),'raw_copies':len(copies),
             'unmatched_rows':len(private),'malformed_rows':sum(m.get('malformed_rows',0) for m in entries),
             'unknown_season_files':sum(not m.get('coverage') for m in entries),'tables':tables,'table_diagnostics':stats,
             'errors':[{'file':m['relative_path'],'error_type':m['error_type']} for m in entries if m.get('error_type')],
             'signature':signature,'directory':str(destination),'asof_rule':'source-week < target-week; source last kickoff+24h < decision; strict observation mode additionally import_time < decision',
             'mapping_sha256':mapping_hash,'schedule_sha256':schedule_hash,'cache_schema':CACHE_SCHEMA,
             'privacy':'All row-level derivatives private/local; public docs contain metadata only'}
    write_once(destination/'REPORT.json',summary)
    if document:inventory_document(entries,summary,document)
    return summary


def latest(cache=CACHE):
    files=list((Path(cache)/'imports').glob('*/REPORT.json'))
    if not files:raise ValueError('No completed local FPDS import')
    reports=[json.loads(p.read_text(encoding='utf-8')) for p in files]
    return max(reports,key=lambda r:r['created_at'])


def main():
    parser=argparse.ArgumentParser(description='Offline private FPDS import; metadata-only stdout')
    parser.add_argument('--source',type=Path,default=SOURCE);args=parser.parse_args()
    try:
        result=run(args.source,document=LAB_ROOT/'docs'/'FPDS_INGEST.md')
        print(json.dumps({k:result[k] for k in ['revision','source_files','raw_copies','unmatched_rows','malformed_rows','unknown_season_files']},indent=2))
        print('Local import complete. Raw rows and unmatched details remain in ignored data/cache/fpds. Metadata: docs/FPDS_INGEST.md')
        return 1 if result['errors'] else 0
    except Exception as exc:
        CACHE.mkdir(parents=True,exist_ok=True)
        # The detailed local error may contain source values: never print/upload it.
        (CACHE/('ERROR_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.txt')).write_text(traceback.format_exc(),encoding='utf-8')
        print('Failure locations: '+', '.join(f'{f.name}:{f.lineno}' for f in traceback.extract_tb(exc.__traceback__)),file=sys.stderr)
        print('FPDS import stopped: '+type(exc).__name__+' (details suppressed to protect subscription rows)',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
