"""Prospective precision and explicitly labelled structural role scenarios."""
from __future__ import annotations
import copy
import json
import numpy as np
import pandas as pd
from ...config import RAW_DIR
from .. import game as G, models as M, players as PL, sim as S
from ..independent import IndependentAnchor
from ..ensemble import structural as structural
from .revision import REV, relocated, exclusive_json, games

SEEDS=(20261020,20261021,20261022)
STATS=("pass_yds","pass_tds","rush_yds","rec_yds","rec","anytime_td")
SCENARIOS=("home_qb_out","away_qb_out","home_rb_out","away_rb_out","home_wr1_out","away_wr1_out","script_high","script_low")


def tolerance(stat):
    return 1. if stat in ("margin","total","rec","pass_tds") else .03 if stat in ("anytime_td","first_td") else 5.


def backup(available,a,excluded):
    ids=available.loc[available.position.eq("QB")&~available.pid.isin(excluded),"pid"]
    prior=a.reindex(ids).dropna(subset=["qb_mean"])
    if prior.empty:
        return None
    return prior.sort_values("qb_size",ascending=False).index[0]


def summarize(result,cols,team_for,gid,mode,seed,case,all_ids):
    rows=[]
    for stat in ("margin","total"):
        x=result["points"][:,0]-result["points"][:,1] if stat=="margin" else result["points"].sum(1)
        rows.append({"game_id":gid,"pid":"","team":None,"stat":stat,"mode":mode,"seed":seed,"scenario":case,
                     "mean":float(x.mean()),"q10":float(np.quantile(x,.1)),"q50":float(np.quantile(x,.5)),"q90":float(np.quantile(x,.9))})
    for pid in sorted(all_ids|set(cols)):
        for stat in STATS+("first_td",):
            if stat=="first_td":
                x=(result["first_td_col"]==cols[pid]).astype(float) if pid in cols else np.zeros(len(result["points"]))
            else:
                x=result["stats"][stat][:,cols[pid]] if pid in cols else np.zeros(len(result["points"]))
            q=np.maximum(np.quantile(x,[.1,.5,.9]),0)
            rows.append({"game_id":gid,"pid":pid,"team":team_for.get(pid),"stat":stat,"mode":mode,"seed":seed,"scenario":case,
                "mean":float(x.mean()),"q10":float(q[0]),"q50":float(q[1]),"q90":float(q[2])})
    p=float((result["first_td_col"]==-1).mean())
    rows.append({"game_id":gid,"pid":"no_offensive_td","team":None,"stat":"first_td","mode":mode,"seed":seed,"scenario":case,
                 "mean":p,"q10":None,"q50":None,"q90":None})
    return rows


def anonymous_replacement(available, team, position):
    """Existing neutral/position priors, never a fabricated GSIS identity."""
    result={t:v.copy() for t,v in available.items()}
    pid=f"assumption:{position}:{team}"
    result[team]=pd.concat([result[team],pd.DataFrame([{"pid":pid,"position":position}])],ignore_index=True)
    return result,pid


def run(directory,log=print,deadline=None,*,revision_directory=REV,season=2026,week=7,n_sims=10000,assumption_replacements=False):
    if season != 2026:
        raise ValueError("This diagnostic runner is prospective 2026 only")
    directory.mkdir(parents=True,exist_ok=True)
    frame=pd.read_parquet(revision_directory/"features_production.parquet")
    fs=games(season,week)
    fit=json.loads((revision_directory/"production_fit.json").read_text())
    plan_path=directory.parent/"plan.json"
    implementation=json.loads(plan_path.read_text()).get("implementation_revision") if plan_path.exists() else None
    with relocated(revision_directory):
        table=structural.tables(log,production=True)
    p=M.load_pbp([2025,2026])
    if assumption_replacements:
        from ...data_pipeline import FEATURE_STORE
        observed=pd.read_parquet(FEATURE_STORE)
        known=observed[observed.season.eq(season)&observed.completed&observed.week.lt(week)&observed.kickoff_utc.lt(pd.Timestamp.now(tz="UTC"))]
        p=p[p.season.lt(season)|p.game_id.isin(known.game_id)]
    else:
        p=p[p.season.lt(2026)|(p.week.le(fit["training_last_completed_week"]))]
    panel=PL.panel(p,table)
    del p
    anchor=IndependentAnchor().fit(pd.read_parquet(__import__("lab.data_pipeline",fromlist=["FEATURE_STORE"]).FEATURE_STORE))
    market=structural.local_game_lines(fs,pd.Timestamp.now(tz="UTC"))
    # Only this forecast week's report, observed before this run, can exclude a
    # player. Never carry an old week's Out designation into a later matchup.
    injury_path=RAW_DIR/"injuries_2026.parquet"
    injury=pd.read_parquet(injury_path,columns=["season","week","gsis_id","report_status"])
    injury=injury[injury.season.eq(season)&injury.week.eq(week)]
    outs=set(injury.loc[injury.report_status.astype(str).str.lower().isin(["out","ir","injured reserve"]),"gsis_id"].dropna())
    injury_observed=pd.Timestamp(injury_path.stat().st_mtime,unit="s",tz="UTC")
    if injury_observed>pd.Timestamp.now(tz="UTC"):
        raise ValueError("Injury observation timestamp is in the future")
    errors=[]
    for game in fs.sort_values("game_id").itertuples():
        if (directory.parent/"STOP_AFTER_CURRENT.json").exists():
            log("stop-after-current request observed after previous game; no new simulation started")
            break
        if deadline and pd.Timestamp.now(tz="UTC")>=pd.Timestamp(deadline)-pd.Timedelta(minutes=10):
            log("simulation deadline reached; no further cases started")
            break
        path=directory/f"{game.game_id}.parquet"
        if path.exists():
            continue
        try:
            base_teams,players,cols,info,a=structural.build_inputs(frame,panel,season,game)
            candidates=frame[frame.game_id.eq(game.game_id)].drop_duplicates("pid")
            team_for=candidates.set_index("pid").team.to_dict()
            available={team:candidates[candidates.team.eq(team)&~candidates.pid.isin(outs)][["pid","position"]] for team in (game.home_team,game.away_team)}
            qbs={t:qb for t,qb,_ in info}
            hist={}
            for team in available:
                z=panel[panel.posteam.eq(team)]
                hist[team]=(z[z.season.eq(season)&z.week.lt(week)].drop_duplicates("game_id"),z[z.season.eq(season-1)].drop_duplicates("game_id"))
                if qbs[team] in outs:
                    qbs[team]=backup(available[team],a,outs)
                    if qbs[team] is None:
                        raise ValueError("Verified expected QB out; no prior eligible replacement")
            base_teams,players,cols,info=G.build(a,available,hist,week,qbs,[game.home_team,game.away_team])
            diagnostic_ids=set(cols)|set(candidates.loc[candidates.position.isin(["QB","RB","FB","WR","TE"]),"pid"])
            independent=anchor.predict(pd.DataFrame([game._asdict()])).iloc[0]
            modes={"sim_independent":[independent.home_points,independent.away_points]}
            if game.game_id in market and {"margin","total"}<=market[game.game_id].keys():
                m=market[game.game_id];modes["market_anchored"]=[(m["total"]+m["margin"])/2,(m["total"]-m["margin"])/2]
            else:
                errors.append({"game_id":game.game_id,"case":"market_anchored","error":"no verified market anchor"})
            rows=[];assumptions=[]
            for mode,points in modes.items():
                calibrate=S.calibrate_v2 if mode=="sim_independent" else S.calibrate
                for seed in SEEDS:
                    if deadline and pd.Timestamp.now(tz="UTC")>=pd.Timestamp(deadline)-pd.Timedelta(seconds=60):
                        errors.append({"game_id":game.game_id,"case":"expected","seed":seed,"error":"insufficient time before deadline"})
                        break
                    rng=np.random.default_rng(seed)
                    efficiency,_=calibrate(table,base_teams,players,points,rng)
                    r=S.simulate(table,base_teams,players,n_sims,efficiency,rng,record_td=True)
                    rows+=summarize(r,cols,team_for,game.game_id,mode,seed,"expected",diagnostic_ids)
                    log(f"stability {game.game_id} {mode} seed={seed}")
                for case in SCENARIOS:
                    if deadline and pd.Timestamp.now(tz="UTC")>=pd.Timestamp(deadline)-pd.Timedelta(seconds=60):
                        errors.append({"game_id":game.game_id,"case":case,"error":"deadline"});break
                    try:
                        av={t:v.copy() for t,v in available.items()};qb=dict(qbs);pt=list(points)
                        if case.startswith("script"):
                            shift=3.5 if case=="script_high" else -3.5
                            pt=[max(.1,pt[0]+shift),max(.1,pt[1]-shift)]
                        else:
                            team=game.home_team if case.startswith("home") else game.away_team
                            if "qb_out" in case:
                                removed=qb[team]
                                qb[team]=backup(av[team],a,{removed})
                                if qb[team] is None:
                                    if not assumption_replacements:
                                        raise ValueError("no roster QB with prior passing history; replacement not guessed")
                                    av,pid=anonymous_replacement(av,team,"QB");qb[team]=pid;team_for[pid]=team
                                    assumptions.append({"mode":mode,"scenario":case,"team":team,"role":pid,"real_replacement":"unknown","basis":"existing position-share and neutral no-history efficiency priors; no QB-specific efficiency model"})
                            else:
                                kind,pos=("rush","RB") if "rb_out" in case else ("recv","WR")
                                ti=next(ti for t,_,ti in info if t==team)
                                eligible_ids=set(av[team].loc[av[team].position.eq(pos),"pid"])
                                pool=ti[kind][ti[kind].index.isin(eligible_ids)]
                                if pool.empty:
                                    raise ValueError("no prior eligible "+pos)
                                removed=pool.share.idxmax()
                            av[team]=av[team][~av[team].pid.eq(removed)]
                            if assumption_replacements and "qb_out" not in case and not av[team].position.eq(pos).any():
                                av,pid=anonymous_replacement(av,team,pos);team_for[pid]=team
                                assumptions.append({"mode":mode,"scenario":case,"team":team,"role":pid,"real_replacement":"unknown","basis":"existing position-share and neutral no-history efficiency priors"})
                        tm,pl,cl,_=G.build(a,av,hist,week,qb,[game.home_team,game.away_team])
                        if any(not len(t["recv_cols"]) or not len(t["rush_cols"]) for t in tm):
                            raise ValueError("scenario removes an entire receiver/rusher pool")
                        rng=np.random.default_rng(SEEDS[0]);efficiency,_=calibrate(table,tm,pl,pt,rng)
                        r=S.simulate(table,tm,pl,n_sims,efficiency,rng,record_td=True)
                        case_rows=summarize(r,cl,team_for,game.game_id,mode,SEEDS[0],case,diagnostic_ids)
                        assumed=any(v["mode"]==mode and v["scenario"]==case for v in assumptions)
                        rows += [v|{"assumption_based":assumed,"scenario_scope":"scenario, not forecast","real_replacement_status":"unknown" if assumed else "prior-role intervention"} for v in case_rows]
                        log(f"scenario {game.game_id} {mode} {case}")
                    except Exception as exc:
                        errors.append({"game_id":game.game_id,"mode":mode,"case":case,"error":repr(exc)})
                        log(f"FAILED scenario {game.game_id} {case}: {exc}; skipped")
            pd.DataFrame(rows).to_parquet(path,index=False)
            exclusive_json(path.with_suffix(".json"),{"created_at":pd.Timestamp.now(tz="UTC").isoformat(),"game_id":game.game_id,"training_cutoff_date":fit["training_cutoff_date"],
                "implementation_revision":implementation,
                "training_last_completed_week":fit["training_last_completed_week"],"frozen_config_sha256":fit["frozen_config_sha256"],"sims":n_sims,"seeds":list(SEEDS),"scenario_names":list(SCENARIOS),"assumptions":assumptions,
                "expected_out_ids":sorted(outs & set(candidates.pid)),"injury_report_week":week,"injury_report_rows":len(injury),"injury_observed_at":injury_observed.isoformat(),
                "limitations":"Structural role interventions only; team anchors held fixed except +/-7 script. QB efficiency/learned-member means not refitted. Final inactives unavailable outside T-90. No scenario is a forecast."})
        except Exception as exc:
            errors.append({"game_id":game.game_id,"case":"game","error":repr(exc)})
            log(f"FAILED simulation {game.game_id}: {exc}; skipped")
    exclusive_json(directory/"errors.json",errors)
    return analyze(directory,season=season,week=week)


def analyze(directory,season=2026,week=7):
    files=list(directory.glob(f"{season}_{week:02d}_*.parquet"))
    if not files:
        raise ValueError("No completed prospective simulation games")
    d=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
    expected=d[d.scenario.eq("expected")].copy()
    groups=["game_id","pid","stat","mode"]
    stable=[]
    for key,z in expected.groupby(groups,dropna=False):
        stat=key[2]; values=z["mean"] if stat in ("margin","total","anytime_td","first_td") else z.q50
        spread=float(values.max()-values.min())
        stable.append(dict(zip(groups,key))|{"n_seeds":z.seed.nunique(),"range":spread,"tolerance":tolerance(stat),
            "stability_flag":"stable" if z.seed.nunique()==3 and spread<=tolerance(stat) else "unstable" if z.seed.nunique()==3 else "unknown"})
    stability=pd.DataFrame(stable)
    baseline=expected[expected.seed.eq(SEEDS[0])][groups+["mean"]].rename(columns={"mean":"baseline_mean"})
    scenarios=d[~d.scenario.eq("expected")].merge(baseline,on=groups,validate="many_to_one",how="left")
    anonymous=scenarios.pid.astype(str).str.startswith("assumption:")
    scenarios.loc[anonymous,"baseline_mean"]=scenarios.loc[anonymous,"baseline_mean"].fillna(0.)
    scenarios["change"]=scenarios["mean"]-scenarios.baseline_mean
    flags=[]
    for key,z in scenarios.groupby(groups,dropna=False):
        stat=key[2];floor=5 if stat.endswith("yds") else .5
        limits=np.full(len(z),3.) if stat in ("margin","total") else np.full(len(z),.10) if stat in ("anytime_td","first_td") else .2*np.maximum(abs(z.baseline_mean),floor)
        complete=z.scenario.nunique()==len(SCENARIOS)
        assumed="assumption_based" in z and z.assumption_based.fillna(False).astype(bool).any()
        flag="unknown: assumption-based replacement" if assumed else "unknown: incomplete scenarios" if not complete or z.baseline_mean.isna().any() else "sensitive" if (abs(z.change)>limits).any() else "robust"
        flags.append(dict(zip(groups,key))|{"scenario_count":z.scenario.nunique(),"max_absolute_change":float(abs(z.change).max()),"scenario_sensitivity":flag})
    stability.to_csv(directory/"stability_summary.csv",index=False)
    pd.DataFrame(flags).to_csv(directory/"scenario_summary.csv",index=False)
    scenarios.to_parquet(directory/"scenario_changes.parquet",index=False)
    result={"games":d.game_id.nunique(),"rows":len(d),"stability_counts":stability.stability_flag.value_counts().to_dict(),
            "scope":"Prospective structural precision/role diagnostics, not accuracy or validated ensemble confidence; no 2026 outcome scoring"}
    exclusive_json(directory/"summary.json",result)
    return result
