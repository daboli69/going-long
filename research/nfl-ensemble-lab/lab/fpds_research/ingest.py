"""Hashed append-only imports; never emits subscription rows or identities."""
from __future__ import annotations
import re
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
from .. import fpds_ingest as old
from ..config import RAW_DIR
from ..props.lines import normalized_name, player_map
from .common import ROOT, RAW, SOURCE, VERSION, now, stamp, digest, read, atomic, write_once, sha
from .protocol import title, family

IDENTITY = {'rank','ranking','season','year','sea','week','wk','player','name','receiver','defender','team','tm',
            'off','def','pos','position','opponent','opp','player_id','game_id','g','gp','men','unit','coach'}
FORBIDDEN = re.compile(r'fantasy|(^|_)(fp|xfp|fpg|fppg|fpts|ppr|dkpts|fdpts)($|_)|salary|ownership|projection|projected|draftkings|fanduel|(^|_)rank($|_)|odds|moneyline|spread|betting|implied|vegas|closing_line',re.I)
_EXACT = None
_KNOWN = None
_HIST_TEAM = None
_HIST_POSITION = None
_SCHEDULE = None


def key_index(meta, kind):
    headers = meta['header']
    aliases = {'season':('SEASON','SEA','YEAR','Season','Year'), 'week':('WEEK','WK','Week','week'),
               'name':('Name','Player','Receiver','NAME','PLAYER'),
               'team':('TEAM','Team','OFF','TM','team'), 'position':('POS','Position','pos'),
               'native_id':('player_id','PlayerId'), 'game_id':('game_id','GameId')}
    for alias in aliases[kind]:
        if alias in headers: return headers.index(alias)
    return None


def parsed(path):
    d,m = old.parse(path)
    table, marker = title(Path(path)); m['table'] = table
    from ..fpds_sources import folder_week
    forecast_week=folder_week(path)
    if forecast_week is not None:
        marker=forecast_week-1
        m['drop_forecast_week']=forecast_week
    if marker is None:
        hit = re.search(r'week\s*(\d+)\s*$', str(Path(path).parent), re.I)
        marker = int(hit.group(1)) if hit else None
    m['export_through_week'] = marker
    m['selected_keys'] = {}
    for kind in ('season','week','name','team','position','native_id','game_id'):
        ix = key_index(m,kind)
        m['selected_keys'][kind] = m['qualified_header'][ix] if ix is not None else None
        if ix is not None: d['_'+kind] = d.iloc[:,ix]
    for col in ('season','week'):
        d['_'+col] = pd.to_numeric(d.get('_'+col,pd.Series(np.nan,index=d.index)),errors='coerce')
    m['selector_conflicts'] = 0
    for i,h in enumerate(m['header']):
        if old.slug(h) in {'season','sea','year'} and m['qualified_header'][i] != m['selected_keys']['season']:
            other = pd.to_numeric(d.iloc[:,i],errors='coerce')
            m['selector_conflicts'] += int((other.notna() & d._season.notna() & other.ne(d._season)).sum())
    valid = d._season.between(2021,2026) & d._week.between(1,18)
    if forecast_week is not None and table!='injury_reports' and ((d._season==2026)&d._week.ge(forecast_week)).any():
        raise ValueError('Weekly statistics contain forecast-week or later outcomes; stop before fitting')
    valid &= ~((d._season == 2026) & (d._week > (marker or 6)))
    m['invalid_calendar_rows'] = int((~valid).sum())
    d = d[valid].copy()
    d['_season'] = d._season.astype(int); d['_week'] = d._week.astype(int)
    m['valid_rows'] = len(d)
    m['valid_rows_games_gt_one']=int(pd.to_numeric(d.get('_games',pd.Series(dtype=float)),errors='coerce').gt(1).sum())
    m['coverage'] = {str(int(s)):sorted(int(w) for w in z._week.unique()) for s,z in d.groupby('_season')}
    m['coverage_counts'] = {f'{s}:{w}':int(n) for (s,w),n in d.groupby(['_season','_week']).size().items()}
    m['possible_export_cap'] = len(d)>0 and (len(d)%100 == 0 or len(d)%1000 == 0)
    return d,m


def column_class(header, qualified):
    slug = old.slug(header)
    if str(header).strip()=='#':return 'outcome-contaminated','excluded ranking/index column'
    if slug in IDENTITY or slug.endswith('_id'): return 'pregame-valid', 'identifier; never an outcome feature'
    if FORBIDDEN.search(qualified): return 'outcome-contaminated', 'excluded fantasy/market/ranking/projection field'
    if re.search(r'season.to.date|cumulative|ytd|std', qualified,re.I): return 'unknown', 'cumulative: excluded unless units can be verified'
    if slug in {'injury','practice','status','rate','record','w','l','t','win_pct'}:
        return 'unknown', 'publication/units unverified; historical lag only where numeric and unambiguous'
    return 'outcome-contaminated', 'completed-week observation; numeric values permitted only after strict lag'


def roster_index():
    global _EXACT,_KNOWN,_HIST_TEAM,_HIST_POSITION,_SCHEDULE
    parts=[]
    for season in range(2021,2027):
        p=RAW_DIR/f'roster_weekly_{season}.parquet'
        if p.exists():
            r=pd.read_parquet(p,columns=['season','week','gsis_id','full_name','team','position'])
            parts.append(r)
    r=pd.concat(parts,ignore_index=True).dropna(subset=['gsis_id'])
    r['team']=r.team.map(old.canonical_team)
    r['normal']=r.full_name.map(normalized_name)
    r=r.drop_duplicates(['season','week','team','gsis_id'])
    _EXACT=r.groupby(['season','week','team','normal']).gsis_id.agg(lambda x:next(iter(set(x))) if len(set(x))==1 else None)
    _KNOWN=set(map(tuple,r[['season','week','team','gsis_id']].to_numpy()))
    weekly=r.groupby(['season','week','gsis_id'])
    _HIST_TEAM=weekly.team.first().where(weekly.team.nunique().eq(1))
    _HIST_POSITION=weekly.position.first().where(weekly.position.nunique().eq(1))
    from ..data_pipeline import FEATURE_STORE
    games=pd.read_parquet(FEATURE_STORE,columns=['game_id','season','week','game_type','home_team','away_team'])
    games=games[games.game_type.eq('REG')]
    sides=pd.concat([games.rename(columns={'home_team':'team','away_team':'opponent'}),games.rename(columns={'away_team':'team','home_team':'opponent'})],ignore_index=True)
    sides=sides[~sides.duplicated(['season','week','team'],False)]
    _SCHEDULE={(x.season,x.week,x.team):(x.game_id,x.opponent) for x in sides.itertuples()}
    return r


def resolve(d,m,roster,mapping):
    d=d.copy(); d['season']=d._season;d['week']=d._week
    d['team']=d.get('_team',pd.Series('',index=d.index)).map(old.canonical_team)
    d['source_team']=d.team
    name=d.get('_name',pd.Series('',index=d.index)).map(normalized_name)
    d['pid']=name.map(mapping)
    team_table=m['table'] in {'pace','coverage_matrix','team_offense','team_defense','playcaller_stats','coach_records'} or m['table'].startswith('fantasy_points_allowed') or m['table'].startswith('lineup_combos')
    if team_table and d.team.isna().all() and '_name' in d:
        d['team']=d.get('_name',pd.Series('',index=d.index)).map(old.canonical_team)
    is_player=m['selected_keys']['name'] is not None and not team_table
    # Verify team by the actual completed source week, including trades. No target-week roster features.
    if is_player:
        exact=_EXACT
        if exact is None:exact=roster.groupby(['season','week','team','normal']).gsis_id.agg(lambda x:next(iter(set(x))) if len(set(x))==1 else None)
        keys=pd.MultiIndex.from_arrays([d.season,d.week,d.team,name])
        local=pd.Series(exact.reindex(keys).to_numpy(),index=d.index)
        d['pid']=local.combine_first(d.pid)
        if '_native_id' in d:
            # Recognition is exact membership in the GSIS roster, not an assumed ID family.
            recognized=d._native_id.where(d._native_id.isin(set(roster.gsis_id)))
            d['pid']=recognized.combine_first(d.pid)
            m['recognized_native_gsis_rows']=int(recognized.notna().sum())
        historical=_HIST_TEAM
        if historical is None:
            historical=roster.groupby(['season','week','gsis_id']).team.agg(lambda x:next(iter(set(x.dropna()))) if x.dropna().nunique()==1 else None)
        sourcekeys=pd.MultiIndex.from_arrays([d.season,d.week,d.pid])
        verified_team=pd.Series(historical.reindex(sourcekeys).to_numpy(),index=d.index)
        m['historical_team_corrections']=int((verified_team.notna()&verified_team.ne(d.team)).sum())
        d['team']=verified_team.combine_first(d.team)
        if _HIST_POSITION is not None:
            d['position_asof']=pd.Series(_HIST_POSITION.reindex(sourcekeys).to_numpy(),index=d.index)
        known=_KNOWN
        if known is None:known=set(map(tuple,roster[['season','week','team','gsis_id']].to_numpy()))
        verified=pd.Series([tuple(x) in known for x in d[['season','week','team','pid']].to_numpy()],index=d.index)
        verified &= verified_team.notna()
        d.loc[~verified,'pid']=None
    else:
        d['pid']=None
    if 'Defender' in m['header'] and 'DEF' in m['header']:
        defender=d.iloc[:,m['header'].index('Defender')].map(normalized_name)
        defense=d.iloc[:,m['header'].index('DEF')].map(old.canonical_team)
        d['defender_team']=defense;d['defender_pid']=defender.map(mapping)
        if _HIST_TEAM is not None:
            sourcekeys=pd.MultiIndex.from_arrays([d.season,d.week,d.defender_pid])
            verified_defense=pd.Series(_HIST_TEAM.reindex(sourcekeys).to_numpy(),index=d.index)
            m['historical_defender_team_corrections']=int((verified_defense.notna()&verified_defense.ne(defense)).sum())
            d['defender_team']=verified_defense.combine_first(defense)
        known=_KNOWN or set(map(tuple,roster[['season','week','team','gsis_id']].to_numpy()))
        valid=[(s,w,t,p) in known for s,w,t,p in zip(d.season,d.week,d.defender_team,d.defender_pid)]
        if _HIST_TEAM is not None:valid=np.asarray(valid)&verified_defense.notna().to_numpy()
        d.loc[~pd.Series(valid,index=d.index),'defender_pid']=None
        m['defender_unmatched_rows']=int(d.defender_pid.isna().sum())
        m['defender_unmatched_distinct_labels']=int(defender[d.defender_pid.isna()].nunique())
    d['entity']=d.pid if is_player else d.team
    if _SCHEDULE is not None:
        joined=[_SCHEDULE.get((s,w,t)) for s,w,t in zip(d.season,d.week,d.team)]
        d['game_id_asof']=[x[0] if x else None for x in joined]
        d['opponent_asof']=[x[1] if x else None for x in joined]
        m['rows_without_schedule_game']=int(d.game_id_asof.isna().sum())
        d.loc[d.game_id_asof.isna(),'entity']=None
        if 'OPP' in m['header']:
            ix=m['header'].index('OPP')
            opponent=d.iloc[:,ix].astype(str).str.replace(r'^(?:@|vs\.?\s*)','',regex=True).str.strip().map(old.canonical_team)
            conflict=opponent.notna()&d.opponent_asof.notna()&opponent.ne(d.opponent_asof)
            m['opponent_conflict_rows']=int(conflict.sum())
            d.loc[conflict,'entity']=None
        if 'defender_team' in d:
            conflict=d.defender_pid.notna()&d.opponent_asof.notna()&d.defender_team.ne(d.opponent_asof)
            m['shadow_matchup_conflict_rows']=int(conflict.sum())
            d.loc[conflict,'entity']=None
    m['entity_kind']='player' if is_player else 'team'
    m['unmatched_rows']=int(d.entity.isna().sum())
    m['unmatched_distinct_labels']=int(name[d.entity.isna()].nunique()) if is_player else int(d.loc[d.entity.isna(),'_team'].nunique()) if '_team' in d else len(d)
    m['mapped_rows']=int(d.entity.notna().sum())
    m['defense_label_rows']=int(name.eq('defense').sum())
    # Never assign the synthetic Defense label to a GSIS player.
    if is_player:
        d.loc[name.eq('defense'),['pid','entity']]=None
    # Repeated split rows are retained in raw snapshots, but ambiguous entity/week groups cannot be joined.
    keys=['season','week','entity']
    duplicates=d[d.entity.notna()].duplicated(keys,keep=False)
    m['ambiguous_entity_week_rows']=int(duplicates.sum())
    usable=d[d.entity.notna()].drop_duplicates().copy()
    ambiguous=usable.duplicated(keys,keep=False)
    usable=usable[~ambiguous].copy()
    return d,usable


def schema(d,m):
    columns=[]
    for h,c in zip(m['header'],m['qualified_header']):
        s=d[c].astype(str).str.strip()
        numeric=s.map(lambda v:old.number(v,False))
        present=~s.str.lower().isin(['','nan','-','--','n/a','null','none'])
        fraction=float(numeric.notna().sum()/max(1,present.sum()))
        cls,rule=column_class(h,c)
        if cls=='outcome-contaminated' and fraction<.8:
            cls,rule='unknown','unverified text/units; excluded from numeric model features'
        selected=cls=='outcome-contaminated' and str(h).strip()!='#' and not FORBIDDEN.search(c) and fraction>=.8
        coverage={f'{int(season)}:{int(week)}':int(n) for (season,week),n in present.groupby([d._season,d._week]).sum().items()}
        columns.append({'header':h,'column':c,'type':'numeric' if fraction>=.8 else 'text',
                        'missing_fraction':float((~present).mean()) if len(s) else 1.,
                        'numeric_fraction':fraction,'validity':cls,'rule':rule,
                        'laggable_numeric':bool(selected),'nonmissing_by_season_week':coverage,
                        'definition_guess':h.strip()+' (header inference; vendor definition unverified)'})
    return columns


def revision(previous,current,m):
    if previous is None:return {'overlap_rows':0,'status':'first comparable snapshot; revisions not estimable','columns':[]}
    keys=['season','week','entity'];a=previous.dropna(subset=['entity']);b=current.dropna(subset=['entity'])
    a=a[~a.duplicated(keys,False)];b=b[~b.duplicated(keys,False)]
    columns=[c['column'] for c in m['columns'] if c['column'] in a and c['column'] in b]
    j=a[keys+columns].merge(b[keys+columns],on=keys,suffixes=('_old','_new'))
    results=[]
    for c in columns:
        x=j[c+'_old'].fillna('').astype(str);y=j[c+'_new'].fillna('').astype(str)
        changed=x.ne(y)
        xn=x.map(old.number);yn=y.map(old.number);delta=(yn-xn).abs()
        results.append({'column':c,'changed_values':int(changed.sum()),'overlap_values':len(j),
                        'mean_absolute_revision':float(delta.mean()) if delta.notna().any() else None,
                        'max_absolute_revision':float(delta.max()) if delta.notna().any() else None})
    akeys=set(map(tuple,a[keys].to_numpy()));bkeys=set(map(tuple,b[keys].to_numpy()))
    return {'overlap_rows':len(j),'added_entity_weeks':len(bkeys-akeys),'removed_entity_weeks':len(akeys-bkeys),
            'status':'comparable','columns':results,
            'changed_values':sum(x['changed_values'] for x in results)}


def source_files(source=SOURCE):
    from ..fpds_sources import select_sources
    return select_sources(source)


def overlay_weeks(versions):
    """Newest whole source-week wins; absent historical weeks remain intact."""
    frames=[]
    for order,frame in versions:
        z=frame.copy();z['_drop_order']=order;frames.append(z)
    combined=pd.concat(frames,ignore_index=True)
    newest=combined.groupby(['season','week'])['_drop_order'].transform('max')
    return combined[combined._drop_order.eq(newest)].drop(columns='_drop_order').reset_index(drop=True)


def weekly_working(inventory,working,target):
    for table in list(working):
        versions=[m for m in inventory if m['table']==table]
        if not any(m.get('drop_forecast_week') for m in versions):continue
        versions=sorted(versions,key=lambda m:(m.get('drop_forecast_week',0),m['export_through_week'] or 0,m['modified_ns'],m['sha256']))
        d=overlay_weeks([(i,pd.read_parquet(m['private_path'])) for i,m in enumerate(versions)])
        m=versions[-1].copy()
        private=target/(table+'__working.parquet')
        if private.exists():
            if not pd.read_parquet(private).equals(d):raise ValueError('Existing import working rows differ; refuse overwrite')
        else:d.to_parquet(private,index=False)
        eligible=d[d.entity.notna()].drop_duplicates()
        ambiguous=eligible.duplicated(['season','week','entity'],False)
        usable=eligible[~ambiguous]
        upath=target/(table+'__working_usable.parquet')
        if upath.exists():
            if not pd.read_parquet(upath).equals(usable):raise ValueError('Existing import usable rows differ; refuse overwrite')
        else:usable.to_parquet(upath,index=False)
        m.update(private_path=str(private),usable_path=str(upath),valid_rows=len(d),usable_entity_week_rows=len(usable),
                 unmatched_rows=int(d.entity.isna().sum()),ambiguous_entity_week_rows=int(ambiguous.sum()),
                 mapped_rows=int(d.entity.notna().sum()),
                 possible_export_cap=any(x['possible_export_cap'] for x in versions),
                 valid_rows_games_gt_one=max(x.get('valid_rows_games_gt_one',0) for x in versions),
                 unmatched_distinct_labels=int(d.loc[d.entity.isna(),'_name'].nunique()) if '_name' in d else int(d.entity.isna().sum()),
                 coverage={str(int(s)):sorted(int(w) for w in z.week.unique()) for s,z in d.groupby('season')},
                 coverage_counts={f'{int(s)}:{int(w)}':int(n) for (s,w),n in d.groupby(['season','week']).size().items()},
                 columns=schema(d,m),working_hash=digest([x['sha256'] for x in versions]),
                 components=[{'sha256':x['sha256'],'source_path':x['source_path']} for x in versions],
                 first_observed_at=max(x['first_observed_at'] for x in versions))
        working[table]=m
    return working


def run(source=SOURCE):
    files=source_files(source)
    if not files:raise FileNotFoundError('No explicitly weekly full-history FPDS exports')
    fingerprint=digest({'schema':VERSION,'implementation':sha(Path(__file__)),'files':[(str(p),sha(p)) for p in files],
                        'rosters':[(s,sha(RAW_DIR/f'roster_weekly_{s}.parquet')) for s in range(2021,2027) if (RAW_DIR/f'roster_weekly_{s}.parquet').exists()]})
    target=ROOT/'imports'/fingerprint[:20]
    if (target/'MANIFEST.json').exists():
        atomic(ROOT/'LATEST_IMPORT.json',{'path':str(target),'fingerprint':fingerprint})
        return read(target/'MANIFEST.json')
    target.mkdir(parents=True,exist_ok=True)
    roster=roster_index();mapping=player_map()
    # Extend only globally unambiguous exact roster names; no fuzzy identity matching.
    for name,g in roster.groupby('normal'):
        ids=g.gsis_id.unique()
        if len(ids)==1:mapping.setdefault(name,ids[0])
    previous={}
    if (ROOT/'LATEST_IMPORT.json').exists():
        prior=read(read(ROOT/'LATEST_IMPORT.json')['path']+'/MANIFEST.json')
        previous={x['table']:x for x in prior['working_tables']}
    inventory=[];working={}
    for path in files:
        d,m=parsed(path);m.update(imported_at=now(),source_path=str(path),family=family(m['table']))
        dest=RAW/m['table']/f"{m['sha256']}.csv";dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with path.open('rb') as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst)
        if sha(dest)!=m['sha256']:raise ValueError('Raw snapshot hash mismatch')
        m['raw_path']=str(dest)
        sidecar=dest.with_suffix('.json')
        m['first_observed_at']=read(sidecar).get('first_observed_at',read(sidecar)['imported_at']) if sidecar.exists() else m['imported_at']
        complete,usable=resolve(d,m,roster,mapping);m['columns']=schema(d,m)
        private=target/(m['table']+'__'+m['sha256'][:12]+'.parquet')
        if not private.exists():complete.to_parquet(private,index=False)
        usable_path=private.with_name(private.stem+'__usable.parquet')
        if not usable_path.exists():usable.to_parquet(usable_path,index=False)
        m['private_path']=str(private);m['usable_path']=str(usable_path)
        if m['selected_keys']['native_id'] is not None:
            anchors=complete[complete.pid.notna()][['season','week','team','pid','_native_id']].drop_duplicates()
            crosswalk=private.with_name(private.stem+'__crosswalk.parquet')
            if not crosswalk.exists():anchors.to_parquet(crosswalk,index=False)
            m['verified_native_id_anchors']=int(anchors._native_id.nunique())
        m['usable_entity_week_rows']=len(usable)
        inventory.append(m)
        existing=working.get(m['table'])
        order=(m['export_through_week'] or 0,m['modified_ns'],m['sha256'])
        if existing is None or order>(existing['export_through_week'] or 0,existing['modified_ns'],existing['sha256']):working[m['table']]=m
        meta=sidecar
        if not meta.exists():write_once(meta,m)
    revisions=[]
    anchors=[]
    for m in inventory:
        if m['selected_keys']['native_id'] is not None:
            a=pd.read_parquet(m['private_path'],columns=['_native_id','pid']).dropna()
            a=a[a._native_id.astype(str).str.fullmatch(r'[1-9][0-9]*')]
            anchors.append(a)
    if anchors:
        cross=pd.concat(anchors,ignore_index=True).drop_duplicates()
        counts=cross.groupby('_native_id').pid.nunique()
        unambiguous=set(counts[counts.eq(1)].index)
        native=cross[cross._native_id.isin(unambiguous)].drop_duplicates('_native_id').set_index('_native_id').pid.to_dict()
        cross.to_parquet(target/'NATIVE_GSIS_ANCHORS.parquet',index=False)
        for m in inventory:
            if m['selected_keys']['native_id'] is None or m['entity_kind']!='player':continue
            d=pd.read_parquet(m['private_path']);missing=d.pid.isna()
            candidate=d._native_id.map(native)
            verified=np.array([(s,w,t,p) in _KNOWN for s,w,t,p in zip(d.season,d.week,d.team,candidate)])
            fill=missing&verified&d.get('_name',pd.Series('',index=d.index)).map(normalized_name).ne('defense')
            # Identity anchors are static; source-week roster/team evidence still required.
            if fill.any():
                d.loc[fill,'pid']=candidate[fill];d.loc[fill,'entity']=candidate[fill]
                resolved=target/(m['table']+'__'+m['sha256'][:12]+'__resolved.parquet')
                if not resolved.exists():d.to_parquet(resolved,index=False)
                usable=d[d.entity.notna()].drop_duplicates();usable=usable[~usable.duplicated(['season','week','entity'],False)]
                upath=resolved.with_name(resolved.stem+'__usable.parquet')
                if not upath.exists():usable.to_parquet(upath,index=False)
                m['private_path']=str(resolved);m['usable_path']=str(upath)
                m['native_id_resolved_rows']=int(fill.sum());m['unmatched_rows']=int(d.entity.isna().sum())
                m['mapped_rows']=int(d.entity.notna().sum());m['usable_entity_week_rows']=len(usable)
                m['unmatched_distinct_labels']=int(d.loc[d.entity.isna(),'_name'].map(normalized_name).nunique())
    working=weekly_working(inventory,working,target)
    for table,m in sorted(working.items()):
        oldm=previous.get(table)
        oldhash=oldm.get('working_hash',oldm['sha256']) if oldm else None
        newhash=m.get('working_hash',m['sha256'])
        oldframe=pd.read_parquet(oldm['private_path']) if oldm and oldhash!=newhash else None
        rev=revision(oldframe,pd.read_parquet(m['private_path']),m)
        if oldm and oldhash==newhash:rev={'status':'unchanged hash','overlap_rows':m['valid_rows'],'columns':[]}
        revisions.append(dict(table=table,previous_hash=oldhash,new_hash=newhash,**rev))
    result={'schema':VERSION,'created_at':now(),'fingerprint':fingerprint,'path':str(target),
            'files':inventory,'working_tables':list(working.values()),'revisions':revisions,
            'privacy':'All subscription rows, identities, models and derivatives remain in ignored local data directories.'}
    if any(sha(Path(x['source_path']))!=x['sha256'] for x in inventory):raise ValueError('Source changed during import; retry the append-only import')
    write_once(target/'MANIFEST.json',result)
    write_once(target/'REVISION_LOG.json',revisions)
    atomic(ROOT/'LATEST_IMPORT.json',{'path':str(target),'fingerprint':fingerprint})
    return result
