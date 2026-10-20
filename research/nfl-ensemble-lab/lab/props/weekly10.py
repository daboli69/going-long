"""One-click, append-only frozen shadow pipeline. No promotion or spent eval."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import pandas as pd
from ..config import LAB_ROOT, REPORTS_DIR
from ..data_pipeline import FEATURE_STORE, GAMES_TABLE
from .ensemble.data import OUT as BASE

ROOT = BASE/"weekly"


def exclusive(path, value):
    with Path(path).open("x",encoding="utf-8") as f:
        json.dump(value,f,indent=2,default=str,allow_nan=False)


def execute(phases, directory, deadline):
    """Fail closed. A failed phase can never run a downstream fit/publication."""
    completed=[]
    for index,(name,budget,action) in enumerate(phases,1):
        try:
            remaining=(pd.Timestamp(deadline)-pd.Timestamp.now(tz="UTC")).total_seconds()
            if remaining<budget:
                raise TimeoutError(f"{name} needs its {budget}s bound; only {remaining:.0f}s remain")
            print(f"{pd.Timestamp.now(tz='UTC').isoformat()} {name}",flush=True)
            result=action()
            if pd.Timestamp.now(tz="UTC")>pd.Timestamp(deadline):
                raise TimeoutError(f"{name} exceeded pipeline deadline; no downstream phase allowed")
            if isinstance(result,dict) and result.get("errors"):
                raise RuntimeError(f"{name}: errors reported; see phase log/partial artifacts")
            exclusive(directory/f"phase_{index:02d}_{name}.json",{"completed_at":pd.Timestamp.now(tz="UTC").isoformat(),"result":result})
            completed.append(name)
        except Exception as exc:
            exclusive(directory/"FAILURE.json",{"failed_phase":name,"error":repr(exc),"completed":completed,"created_at":pd.Timestamp.now(tz="UTC").isoformat(),"scope":"Partial new revision retained; earlier forecasts unchanged; no downstream phase executed"})
            raise RuntimeError(f"STOPPED at {name}: {exc}. Partial revision: {directory}") from exc
    return completed


def command(args, timeout=600):
    import psutil
    process=subprocess.Popen(args,cwd=LAB_ROOT)
    try:
        code=process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        for child in reversed(psutil.Process(process.pid).children(recursive=True)):
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        process.terminate();process.wait(timeout=15)
        raise
    if code:
        raise RuntimeError(f"Command failed, exit {code}: {' '.join(args[:4])}")
    return {"exit":code}


@contextmanager
def outputs(destination):
    from .ensemble import data,production,structural
    from . import projections10
    modules=(data,production,structural,projections10)
    previous=[m.OUT for m in modules];reports=projections10.REPORTS_DIR
    try:
        for m in modules:m.OUT=destination
        projections10.REPORTS_DIR=destination/"reports"
        projections10.REPORTS_DIR.mkdir(exist_ok=True)
        yield
    finally:
        for m,value in zip(modules,previous):m.OUT=value
        projections10.REPORTS_DIR=reports


def next_revision(season,week):
    pattern=re.compile(rf"(?:projections_)?{season}_w0?{week}_r(\d+)(?:_|$)")
    names=[p.stem for p in REPORTS_DIR.glob("projections_*.csv")]
    names += [p.name for p in ROOT.glob(f"{season}_w*")]
    values=[int(m.group(1)) for name in names for m in [pattern.match(name)] if m]
    return max(values,default=0)+1


def select_slate(frame,season,week,now=None):
    from .ensemble.production import completed_cutoff
    now=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if season!=2026:
        raise ValueError("The frozen Phase 10 configuration is scoped to 2026")
    cutoff=completed_cutoff(frame,now)
    target=int(week or cutoff["training_last_completed_week"]+1)
    if not 1<=target<=18:
        raise ValueError("Only regular-season weeks 1-18 are supported")
    games=frame[frame.season.eq(season)&frame.week.eq(target)&frame.game_type.eq("REG")&~frame.completed&frame.kickoff_utc.gt(now)].copy()
    if games.empty:
        raise ValueError("No unplayed games in the requested week")
    return target,games,cutoff


def run(season=2026,week=None,max_minutes=150,sims=1000,plan_only=False):
    from .ensemble.frozen import load
    from .ensemble import production,structural
    from . import projections10 as P
    from .amendment2 import revision as R,simulation as D
    from .amendment2.sheets import leans,export,KEY
    from .amendment3.research import reconcile
    from ..prospective import fetch_weather
    from ..inactives10 import collect
    frozen=load()
    target,games,cutoff=select_slate(pd.read_parquet(FEATURE_STORE),season,week)
    revision=next_revision(season,target)
    now=pd.Timestamp.now(tz="UTC");stamp=now.strftime('%Y%m%dT%H%M%S%fZ')
    deadline=min(now+pd.Timedelta(minutes=max_minutes),games.kickoff_utc.min()-pd.Timedelta(minutes=1))
    plan={"created_at":now.isoformat(),"season":season,"week":target,"forecast_revision":revision,"training_cutoff":cutoff,"frozen_config_sha256":frozen['config_sha256'],"sims":sims,"seeds":list(D.SEEDS),"deadline":deadline.isoformat(),"shadow_only":True}
    if plan_only:
        print(json.dumps(plan,indent=2,default=str));return plan
    if max_minutes<=0 or sims<100:
        raise ValueError("Positive runtime and >=100 simulations required")
    ROOT.mkdir(parents=True,exist_ok=True)
    import psutil
    lock=ROOT/"RUNNING.json"
    if lock.exists():
        owner=json.loads(lock.read_text())
        if psutil.pid_exists(owner['pid']) and abs(psutil.Process(owner['pid']).create_time()-owner['process_created'])<1:
            raise RuntimeError(f"Another weekly pipeline owns {lock}; no second job started")
        lock.unlink()  # stale local process lock only, never an archive
    exclusive(lock,{"pid":os.getpid(),"process_created":psutil.Process().create_time()})
    destination=ROOT/f"{season}_w{target:02d}_r{revision:02d}_{stamp}"
    destination.mkdir(exist_ok=False)
    state={}
    try:
        originals={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.glob('**/forecasts2026/*.json') if destination not in p.parents}
        plan['preserved_forecast_hashes']=originals
        plan['implementation_revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=LAB_ROOT,text=True).strip()
        exclusive(destination/'plan.json',plan)
        def refresh():
            return command([sys.executable,'-m','lab.cli','refresh'],600)
        def archives():
            command(['git','fetch','origin','main'],90)
            return command([sys.executable,'-m','lab.phase10_archive','--remote-main'],180)
        def context():
            target2,latest,new_cutoff=select_slate(pd.read_parquet(FEATURE_STORE),season,target)
            state.update(games=latest,cutoff=new_cutoff)
            source=pd.read_parquet(GAMES_TABLE)
            missing=[c for c in ('stadium_id','stadium') if c not in latest]
            weather_games=latest.merge(source[['game_id']+missing],on='game_id',how='left',validate='one_to_one') if missing else latest
            inactive=collect(latest)
            if not inactive.get('ok'):raise RuntimeError('Inactive collector failed')
            return {'weather':fetch_weather(weather_games),'inactives':inactive,'context_only':True,'training_cutoff':new_cutoff}
        def fit():
            status=production.fit(threads=max(1,psutil.cpu_count()-2),prospective_week=target,log=lambda s:print(s,flush=True))
            if len(status['models'])!=6 or any(z.get('error') or z.get('errors') or len(z.get('members',[]))!=4 for z in status['models'].values()):
                raise RuntimeError('Frozen production fit has missing/failed members')
            shutil.copy2(BASE/'dev_predictions.parquet',destination/'dev_predictions.parquet')
            state['fit']=status
            return status
        def structural_forecasts():
            result=structural.run(season,target,sims,production=True,deadline=deadline.isoformat(),log=lambda s:print(s,flush=True))
            if result.get('files')!=len(state['games']):raise RuntimeError('Structural game coverage incomplete')
            return result
        def forecast():
            samples=[]
            def capture(row,values):samples.append({k:row[k] for k in KEY}|{'samples':values.astype('float32').tolist()})
            result=P.forecast(target,season,log=lambda s:print(s,flush=True),distribution_sink=capture,source_revision=plan['implementation_revision'])
            if set(result.get('archived',[]))!=set(state['games'].game_id):raise RuntimeError('Forecast game coverage incomplete')
            data=pd.DataFrame(samples).drop_duplicates(KEY)
            data.to_parquet(destination/'distributions.parquet',index=False)
            exclusive(destination/'distributions.json',{'created_at':pd.Timestamp.now(tz='UTC').isoformat(),'forecast_revision':revision,'training_cutoff_date':state['fit']['training_cutoff_date'],'frozen_config_sha256':frozen['config_sha256'],'parquet_sha256':hashlib.sha256((destination/'distributions.parquet').read_bytes()).hexdigest()})
            return result
        def diagnostics():
            result=D.run(destination/'simulations',revision_directory=destination,season=season,week=target,n_sims=sims,assumption_replacements=True,deadline=deadline.isoformat(),log=lambda s:print(s,flush=True))
            errors=json.loads((destination/'simulations/errors.json').read_text())
            actual=[e for e in errors if e.get('case')!='market_anchored']
            if actual:raise RuntimeError(f'{len(actual)} diagnostic cases failed; prior files retained')
            if result['games']!=len(state['games']):raise RuntimeError('Diagnostic game coverage incomplete')
            return result|{'unavailable_market_anchors':len(errors)}
        def sheets():
            if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=value for p,value in originals.items()):
                raise AssertionError('An earlier forecast changed; no new sheet published')
            base,distributions,totals=R.fixed(destination,season,target)
            player=base[base.row_type.eq('player')].rename(columns={'projection':'equal'})
            raw=pd.concat([pd.read_parquet(p) for p in (destination/'structural_prospective2026_recent').glob('*.parquet')],ignore_index=True)
            raw=raw[raw.member.eq('sim_independent')]
            reconciled,others,errors=reconcile(player,raw,totals)
            if errors:raise RuntimeError(f'{len(errors)} shadow accounting groups unavailable')
            extras=reconciled[KEY+['reconciled']].rename(columns={'reconciled':'reconciled_projection'})
            extras=extras.merge(others[['game_id','team','stat','other_players_projection']].merge(player[KEY+['team']],on=['game_id','team','stat'],validate='one_to_many')[KEY+['other_players_projection']],on=KEY,validate='one_to_one')
            frame,coherence,projection=R.refresh_sheet(stamp,revision_directory=destination,season=season,week=target,revision=revision,shadow_columns=extras)
            stable=pd.read_csv(destination/'simulations/stability_summary.csv').fillna({'pid':''})
            sensitivity=pd.read_csv(destination/'simulations/scenario_summary.csv').fillna({'pid':''})
            def mapping(d,column):return {(r.game_id,str(r.pid),r.stat):getattr(r,column) for r in d[d['mode'].eq('sim_independent')].itertuples()}
            ranked=leans(frame,mapping(stable,'stability_flag'),mapping(sensitivity,'scenario_sensitivity'))
            lean=REPORTS_DIR/f'leans_{season}_w{target:02d}_r{revision:02d}_{stamp}'
            if lean.with_suffix('.csv').exists() or lean.with_suffix('.md').exists():raise FileExistsError('Leans revision already exists')
            export(ranked,lean,heading=f'Week {target} shadow leans to investigate',context=f'Unvalidated shadow output; no model promotion. Trained through {state["fit"]["training_cutoff_date"]}; created {pd.Timestamp.now(tz="UTC").isoformat()}. Simulation precision is not accuracy. Original/reconciled values remain separate. Assumption-based replacements retain unknown real identities; confidence tiers are investigation readiness, never win probabilities.')
            for stem in (projection,lean):
                others.to_csv(stem.with_name(stem.name+'_reconciliation').with_suffix('.csv'),index=False)
                pd.read_parquet(destination/'simulations/scenario_changes.parquet').to_csv(stem.with_name(stem.name+'_scenarios').with_suffix('.csv'),index=False)
            return {'projection':str(projection),'leans':str(lean),'coherence':str(projection.with_name(projection.name+'_coherence.csv')),'tiers':ranked.confidence_tier.value_counts().to_dict(),'unknown_real_replacements':True}
        with outputs(destination):
            phases=[('refresh',600,refresh),('archives',180,archives),('context',120,context),('fit',900,fit),('structural',600,structural_forecasts),('forecast',900,forecast),('diagnostics',3600,diagnostics),('sheets',180,sheets)]
            completed=execute(phases,destination,deadline)
        manifest=plan|{'completed_at':pd.Timestamp.now(tz='UTC').isoformat(),'training_cutoff':state['cutoff'],'completed_phases':completed,'sheets':json.loads((destination/'phase_08_sheets.json').read_text())['result']}
        manifest['files']=[{'path':str(p.relative_to(destination)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in destination.rglob('*') if p.is_file()]
        exclusive(destination/'MANIFEST.json',manifest)
        print(json.dumps({'manifest':str(destination/'MANIFEST.json'),'sheets':manifest['sheets']},indent=2),flush=True)
        return manifest
    finally:
        if lock.exists() and json.loads(lock.read_text()).get('pid')==os.getpid():lock.unlink()


def main():
    import psutil
    n=max(1,psutil.cpu_count()-2);psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS);psutil.Process().cpu_affinity(list(range(n)))
    os.environ.update(OMP_NUM_THREADS=str(n),MKL_NUM_THREADS=str(n))
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int);p.add_argument('--max-minutes',type=float,default=150);p.add_argument('--sims',type=int,default=1000);p.add_argument('--plan',action='store_true');a=p.parse_args()
    try:run(a.season,a.week,a.max_minutes,a.sims,a.plan)
    except Exception as exc:print(f'ERROR: {exc}',file=sys.stderr);return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
