"""Weekly folder workflow. Source CSVs are read-only; outputs stay private."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pandas as pd

from .fpds_sources import HISTORY_FOLDER,managed_folder,select_sources
from .fpds_research.common import ROOT,SOURCE,LAB_ROOT,now,stamp,read,sha,atomic,write_once
from .fpds_research.protocol import title

STATE=ROOT/'weekly_workflow'


class DropError(ValueError):
    """Safe operational messages; vendor values never enter console errors."""


def workflow_active():
    import psutil
    path=STATE/'ACTIVE.json'
    if not path.exists():return False
    try:
        saved=read(path);process=psutil.Process(saved['pid'])
        return abs(process.create_time()-saved['process_created'])<1
    except psutil.NoSuchProcess:return False
    except FileNotFoundError:return False
    except (OSError,ValueError,KeyError):
        # A competing process may still be writing its exclusive lock file.
        return pd.Timestamp.now(tz='UTC').timestamp()-path.stat().st_mtime<60
    except psutil.AccessDenied:return True


@contextmanager
def workflow_lock():
    import psutil
    STATE.mkdir(parents=True,exist_ok=True);path=STATE/'ACTIVE.json'
    if path.exists():
        if workflow_active():raise DropError('A weekly/injury folder update is already running')
        path.unlink()  # Stale operational lock only, never an archive.
    try:
        with path.open('x',encoding='utf-8') as handle:
            json.dump({'pid':os.getpid(),'process_created':psutil.Process().create_time()},handle)
    except FileExistsError:raise DropError('Another folder update acquired the lock; retry later')
    try:yield
    finally:path.unlink(missing_ok=True)


@contextmanager
def scope_week(week):
    previous=os.environ.get('NFL_FPDS_TARGET_WEEK')
    os.environ['NFL_FPDS_TARGET_WEEK']=str(week)
    try:yield
    finally:
        if previous is None:os.environ.pop('NFL_FPDS_TARGET_WEEK',None)
        else:os.environ['NFL_FPDS_TARGET_WEEK']=previous


def target_week(week=None):
    if week is None:
        from .data_pipeline import FEATURE_STORE
        from .fpds_weekly_guard import next_week
        g=pd.read_parquet(FEATURE_STORE)
        g['kickoff_utc']=pd.to_datetime(g.kickoff_utc,utc=True)
        week=next_week(g,pd.Timestamp.now(tz='UTC'))
    if not 7<=int(week)<=18:raise DropError('This folder workflow supports forecast weeks 7 through 18 of 2026')
    return int(week)


def drop_folder(week,source=SOURCE):
    """Forecast-week folder. For the real Inbox this is the private converted copy of the week-1 drop."""
    return managed_folder(source)/f'Week {week}'


def inspect_drop(week,source=SOURCE,parse=None):
    """Metadata only. Empty future folders never supersede current sources."""
    from .fpds_research.ingest import parsed
    parse=parse or parsed
    authority=Path(source)/HISTORY_FOLDER
    expected={title(p)[0] for p in authority.glob('*.csv')}
    if not expected:raise DropError('Authoritative historical CSVs are missing')
    folder=drop_folder(week,source)
    files=list(folder.glob('*.csv'));tables={title(p)[0] for p in files}
    unknown=tables-expected
    if unknown:raise DropError('Unrecognized table names in weekly folder; use the original export titles')
    missing=sorted(expected-tables)
    # Travis 2026-10-29: run without absent tables (their authority history stays in use); report them instead.
    if week>7 and missing:
        print('Weekly folder is missing tables (authority history used for these): '+', '.join(missing))
    for p in files:
        _,meta=parse(p)
        # Single-week drops cover only the prior week; earlier weeks come from the authority and earlier drops.
        if week>7 and (week-1) not in meta['coverage'].get('2026',[]):
            raise DropError('A weekly export lacks completed 2026 weeks; the drop must contain the prior week')
    with scope_week(week):selected=select_sources(source,parse=parse,week=week)
    return {'forecast_week':week,'statistics_through_week':week-1,'folder':str(folder),'files':len(files),
            'required_tables':len(expected),'present_tables':len(tables),'missing_tables':missing,
            'baseline_bootstrap':week==7,'selected_versions':len(selected)}


def validate_completed_week(games,week,asof=None):
    from .props.ensemble.production import completed_cutoff
    asof=pd.Timestamp.now(tz='UTC') if asof is None else pd.Timestamp(asof)
    cutoff=completed_cutoff(games,now=asof)
    prior=games[games.season.eq(2026)&games.week.eq(week-1)&games.game_type.eq('REG')]
    if cutoff['training_last_completed_week']!=week-1 or prior.empty:
        raise DropError('The prior forecast week is not fully completed; stop before refitting')
    ready=pd.to_datetime(prior.kickoff_utc,utc=True).max()+pd.Timedelta(hours=24)
    if asof<=ready:raise DropError('Prior-week statistics are not available under the final-kickoff-plus-24h rule; retry later Tuesday night')
    return cutoff


def archive_injuries(week,source=SOURCE,games=None):
    """Current status context only: never feed target-week stats into a frozen fit."""
    from . import fpds_ingest as old
    from .fpds_research.ingest import key_index
    folder=drop_folder(week,source)
    files=[p for p in folder.glob('*.csv') if title(p)[0]=='injury_reports']
    if not files:raise DropError('No injury-reports CSV in the selected Week folder')
    # Same-week newer save wins. Earlier snapshots remain immutable in ignored raw storage.
    path=max(files,key=lambda p:(p.stat().st_mtime_ns,p.name))
    expected_hash=sha(path)
    data,meta=old.parse(path)
    baseline=next(iter((Path(source)/HISTORY_FOLDER).glob('injury-reports*.csv')),None)
    if baseline is None:
        baseline=next((p for p in (Path(source)/HISTORY_FOLDER).glob('*.csv') if title(p)[0]=='injury_reports'),None)
    if baseline is None:raise DropError('Original injury schema is missing')
    _,original=old.parse(baseline)
    if meta['header']!=original['header'] or meta.get('group_header')!=original.get('group_header'):
        raise DropError('Injury CSV schema changed; review before import')
    six,wix=key_index(meta,'season'),key_index(meta,'week')
    if six is None or wix is None:raise DropError('Injury CSV needs season and week columns')
    current=data[pd.to_numeric(data.iloc[:,six],errors='coerce').eq(2026)&pd.to_numeric(data.iloc[:,wix],errors='coerce').eq(week)].copy()
    status_ix=next((i for i,h in enumerate(meta['header']) if h.strip().upper()=='STATUS'),None)
    if status_ix is None:raise DropError('Injury CSV needs a STATUS column')
    created=pd.Timestamp.now(tz='UTC');checksum=sha(path)
    if checksum!=expected_hash:raise DropError('Injury source changed during parsing; retry the import')
    raw=LAB_ROOT/'data/raw/fpds/injury_context'/checksum
    raw.mkdir(parents=True,exist_ok=True)
    copied=raw/'source.csv'
    if not copied.exists():
        with path.open('rb') as src,copied.open('xb') as dst:shutil.copyfileobj(src,dst)
    if sha(copied)!=checksum or sha(path)!=checksum:raise DropError('Injury source changed during import; retry')
    if not (raw/'SOURCE.json').exists():
        write_once(raw/'SOURCE.json',{'sha256':checksum,'source_path':str(path),'first_observed_at':created.isoformat(),
                                    'original_modified_at':pd.Timestamp(path.stat().st_mtime,unit='s',tz='UTC').isoformat()})
    destination=STATE/'injuries'/f'2026_w{week:02d}_{stamp()}';destination.mkdir(parents=True,exist_ok=False)
    from .config import RAW_DIR
    roster_path=RAW_DIR/'roster_weekly_2026.parquet'
    roster=pd.read_parquet(roster_path) if roster_path.exists() else pd.DataFrame()
    from .props.lines import normalized_name
    identities={}
    if len(roster):
        roster=roster[roster.week.eq(week)].copy()
        roster['normal']=roster.full_name.map(normalized_name);roster['canonical_team']=roster.team.map(old.canonical_team)
        for key,z in roster.groupby(['canonical_team','normal']):
            ids=z.gsis_id.dropna().unique()
            if len(ids)==1:identities[key]=ids[0]
    if games is None:
        from .data_pipeline import FEATURE_STORE
        games=pd.read_parquet(FEATURE_STORE)
    games=games[games.season.eq(2026)&games.week.eq(week)]
    kickoffs={t:pd.Timestamp(r.kickoff_utc) for r in games.itertuples() for t in (r.home_team,r.away_team)}
    nix,tix=key_index(meta,'name'),key_index(meta,'team')
    if nix is None or tix is None:raise DropError('Injury CSV needs player and team columns')
    records=[]
    for _,row in current.iterrows():
        team=old.canonical_team(row.iloc[tix]);pid=identities.get((team,normalized_name(row.iloc[nix])))
        from .fpds_injury_confirmation import normalize_status
        status=normalize_status(row.iloc[status_ix])
        kickoff=kickoffs.get(team)
        if kickoff is not None and kickoff.tzinfo is None:kickoff=kickoff.tz_localize('UTC')
        records.append({'pid':pid,'team':team,'status':status,'observed_at':created.isoformat(),
                        'pregame':bool(kickoff is not None and created<kickoff)})
    contexts=pd.DataFrame(records,columns=['pid','team','status','observed_at','pregame'])
    contexts.to_parquet(destination/'CONTEXT_PRIVATE.parquet',index=False)
    result={'created_at':created.isoformat(),'forecast_week':week,'source_sha256':checksum,'source_modified_at':read(raw/'SOURCE.json')['original_modified_at'],
            'source_first_observed_at':read(raw/'SOURCE.json')['first_observed_at'],'vendor_publication_time':'unverified',
            'path':str(destination),'current_week_rows':len(contexts),'unmatched_rows':int(contexts.pid.isna().sum()),
            'pregame_matched_rows':int((contexts.pregame&contexts.pid.notna()).sum()),
            'status_counts':contexts.status.value_counts().to_dict(),'model_input':False,
            'warning':'Status context only. Frozen forecasts are unchanged; same-week game-stat columns are excluded. Unknown identities/statuses stay unknown.'}
    write_once(destination/'SUMMARY.json',result)
    atomic(STATE/f'INJURIES_W{week:02d}.json',result)
    atomic(STATE/'LATEST_INJURIES.json',result)
    return result


def frozen_inventory():
    records={}
    for p in (ROOT/'weekly').glob('2026_w*_r*/FORECAST.json'):
        d=read(p)
        for name,expected in d['files'].items():
            f=p.parent/name
            if sha(f)!=expected:raise DropError('An existing frozen forecast changed; stop')
            records[str(f)]=expected
        records[str(p)]=sha(p)
    return records


def frozen_schema_check():
    """Preserve the existing weekly admission's committed schema contract."""
    from .fpds_weekly_guard import validate_headers
    frozen_path=LAB_ROOT/'docs/FPDS_AMENDMENT6_FROZEN.json'
    if not frozen_path.exists():raise DropError('The committed frozen configuration is missing')
    frozen=read(frozen_path);job=read(Path(frozen['research_path'])/'JOB.json')
    imported=read(Path(job['feature_metadata']['import_manifest_path'])/'MANIFEST.json')
    return validate_headers(select_sources(),{m['table']:m for m in imported['working_tables']})


def previous_results(destination,week,observations,games):
    """Score frozen revisions separately. No model selection or tuning."""
    from .fpds_research import models as M
    rows=[];prior=week-1
    completed=games[games.season.eq(2026)&games.week.eq(prior)&games.completed.fillna(False)]
    actual=pd.read_parquet(observations)
    for p in sorted((ROOT/'weekly').glob(f'2026_w{prior:02d}_r*/FORECAST.json')):
        manifest=read(p);created=pd.Timestamp(manifest['created_at'])
        for filename,keys in [('projections.csv',['game_id','pid']),('game_projections.csv',['game_id'])]:
            frame=pd.read_csv(p.parent/filename)
            for (stat,arm),z in frame.groupby(['stat','arm']):
                target='home_win' if stat=='win' else stat
                source=completed if len(keys)==1 else actual[actual.game_id.isin(completed.game_id)]
                if target not in source:continue
                outcomes=source[keys+[target]].drop_duplicates()
                outcomes=outcomes[~outcomes.duplicated(keys,False)]
                z=z.merge(outcomes,on=keys,validate='one_to_one').dropna(subset=[target,'mean'])
                kickoff=completed.set_index('game_id').kickoff_utc
                z=z[z.game_id.map(kickoff).map(lambda t:pd.notna(t) and created<pd.Timestamp(t))]
                if z.empty:continue
                loss=M.loss(stat,z[target],z['mean'])
                rows.append({'revision':p.parent.name,'stat':stat,'arm':arm,'n':len(z),'games':z.game_id.nunique(),
                             'metric':'Brier' if M.binary(stat) else 'Poisson deviance' if stat in ('rec','pass_tds') else 'MAE',
                             'loss':float(loss.mean())})
    report={'created_at':now(),'week':prior,'purpose':'Descriptive results only; no tuning/selection; revisions scored separately',
            'completed_games':len(completed),'rows':rows}
    write_once(destination/'PREVIOUS_WEEK_RESULTS.json',report)
    lines=[f'# Week {prior} frozen forecast results','',report['purpose'],'',
           '|Revision|Stat|Arm|n|Games|Metric|Loss|','|---|---|---|---:|---:|---|---:|']
    lines += [f"|{r['revision']}|{r['stat']}|{r['arm']}|{r['n']}|{r['games']}|{r['metric']}|{r['loss']:.5f}|" for r in rows]
    if not rows:lines+=['','No matched completed outcomes for saved FPDS weekly forecasts. No values invented.']
    (destination/'PREVIOUS_WEEK_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report


def run_weekly(week,deadline=None,threads=None):
    from .fpds_manual import jobs
    if jobs.active():raise DropError('A manual FPDS job is active; wait for it to finish')
    with scope_week(week):
        admitted=inspect_drop(week)
        from .data_pipeline import FEATURE_STORE
        from .fpds_weekly_guard import check
        g=pd.read_parquet(FEATURE_STORE);g['kickoff_utc']=pd.to_datetime(g.kickoff_utc,utc=True)
        check(g,week,pd.Timestamp.now(tz='UTC'))
        inventory=frozen_inventory()
        destination=STATE/'weekly'/f'2026_w{week:02d}_{stamp()}';destination.mkdir(parents=True,exist_ok=False)
        write_once(destination/'STARTED.json',{'created_at':now(),**admitted,'protected_forecast_files':len(inventory)})
        try:
            from .fpds_worker import install
            install()
            frozen_schema_check()
            from .fpds_research.weekly import run
            end=min(pd.Timestamp(deadline) if deadline else pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=2),pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=2))
            forecast=run(SimpleNamespace(week=week,deadline=end.isoformat(),threads=threads or max(1,(os.cpu_count() or 2)-2),strict_drop=True))
            directory=Path(forecast['path'])
            g=pd.read_parquet(FEATURE_STORE);g['kickoff_utc']=pd.to_datetime(g.kickoff_utc,utc=True)
            results=previous_results(destination,week,directory/'base/observations_production.parquet',g)
            from .prospective import score
            score(progress=lambda _:None)
            from .fpds_sheets import run as sheets
            presentation=sheets(directory)
            from .fpds_clv import run as tracking
            tracking()
            injury_files=[p for p in drop_folder(week).glob('*.csv') if title(p)[0]=='injury_reports']
            injury=archive_injuries(week,games=g) if injury_files else None
            if injury is not None:
                from .fpds_injury_confirmation import update_week
                update_week(week,state=STATE,games=g)
            if any(sha(Path(p))!=h for p,h in inventory.items()):raise DropError('A protected forecast changed; stop')
            result={'created_at':now(),'forecast_week':week,'statistics_through_week':week-1,'path':str(destination),
                    'forecast':forecast,'presentation':presentation,'previous_results':str(destination/'PREVIOUS_WEEK_RESULTS.json'),
                    'previous_results_rows':len(results['rows']),'injury_context':injury,'source_folder':str(drop_folder(week)),
                    'protected_forecast_files':len(inventory),'old_forecasts_unchanged':True}
            write_once(destination/'COMPLETE.json',result);atomic(STATE/'LATEST_WEEKLY.json',result)
            return result
        except Exception:
            write_once(destination/'FAILED.json',{'created_at':now(),'status':'Stopped; private diagnostic retained; no downstream success assumed'})
            raise


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('action',choices=['weekly','injuries','plan']);p.add_argument('--week',type=int)
    p.add_argument('--deadline');p.add_argument('--threads',type=int)
    a=p.parse_args()
    try:
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=LAB_ROOT,text=True).strip()
        if branch!='codex/projections-20261019':raise DropError('Use branch codex/projections-20261019 for this workflow')
        week=target_week(a.week)
        if a.action=='plan':
            result=inspect_drop(week)
            print(json.dumps(result,indent=2));return 0
        with workflow_lock():
            if a.action=='injuries':
                has_csv=any(title(f)[0]=='injury_reports' for f in drop_folder(week).glob('*.csv'))
                # Keep original feeds even when a post-week subscription CSV is absent.
                from .live import refresh_live,record_live_refresh
                refresh=refresh_live(progress=lambda _:None)
                record_live_refresh(refresh)
                if has_csv:
                    result=archive_injuries(week)
                else:
                    from .nflmeta_injuries import refresh as refresh_nflmeta
                    fallback=refresh_nflmeta(2026,week)
                    print('No injury CSV: original feeds retained; NFL Meta fallback: '+fallback['state']+'.')
                    if fallback.get('possibly_truncated'):
                        print('NFL Meta coverage may be partial (100-row cap); missing players are not confirmed healthy.')
                from .fpds_injury_confirmation import update_week
                confirmation=update_week(week,state=STATE,use_csv=has_csv)
                if has_csv:
                    print(f"Week {week} injury context imported: {result['current_week_rows']} rows; {result['unmatched_rows']} unmatched. Frozen projections unchanged.")
                else:
                    print(f'Week {week} live injury comparison updated. Frozen projections unchanged.')
                print(f"Source comparison: {confirmation['confirmed']} confirmed, {confirmation['conflicts']} conflicts, {confirmation['fpds_only']} CSV-only. Original-feed refresh failures: {len(refresh.get('failed',{}))}.")
            else:
                result=run_weekly(week,a.deadline,a.threads)
                print(f'Week {week} ready. Private sheets: '+result['presentation']['path'])
                print('Previous-week report: '+str(Path(result['path'])/'PREVIOUS_WEEK_RESULTS.md'))
        print('Open START_HERE.bat > Dashboard > Research > FPDS Research.')
        return 0
    except Exception as error:
        from .fpds_research.common import private_error
        private_error('weekly_folder_'+a.action)
        print('STOP: '+(str(error) if isinstance(error,DropError) else 'Workflow failed; see private weekly_folder diagnostic.'))
        return 1


if __name__=='__main__':raise SystemExit(main())
