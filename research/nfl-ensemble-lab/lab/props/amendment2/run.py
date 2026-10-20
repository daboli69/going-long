"""Local eight-hour controller. No sends, odds requests, promotion or eval path."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import pandas as pd
import psutil
from ...config import LAB_ROOT, REPORTS_DIR
from ...data_pipeline import GAMES_TABLE
from ...longrun import active_job
from .revision import ROOT,REV,games,refresh_sheet,exclusive_json
from .sheets import leans,export

STATUS=REPORTS_DIR/"run_20261020"/"STATUS.md"
BRANCH="codex/projections-20261019"
HARD_STOP=pd.Timestamp("2026-10-20T17:34:55-04:00")


def note(message):
    timestamp=pd.Timestamp.now(tz="America/New_York").isoformat()
    print(timestamp+" "+message,flush=True)
    with STATUS.open("a",encoding="utf-8") as f:
        f.write(f"- {timestamp}: {message}\n")


def command(args,log,timeout=120):
    with log.open("w",encoding="utf-8") as f:
        result=subprocess.run(args,cwd=LAB_ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    if result.returncode:
        note(f"FAILED {args[:4]} exit={result.returncode}; skipped; log={log.name}")
    return result.returncode


def commit_status():
    current=subprocess.check_output(["git","branch","--show-current"],cwd=LAB_ROOT,text=True).strip()
    if current!=BRANCH:
        raise RuntimeError("Branch changed; no automatic commit/push outside authorized branch")
    rel=STATUS.relative_to(LAB_ROOT).as_posix()
    subprocess.run(["git","add","-f",rel],cwd=LAB_ROOT,check=True,capture_output=True)
    diff=subprocess.run(["git","diff","--cached","--quiet","--",rel],cwd=LAB_ROOT)
    if diff.returncode==1:
        subprocess.run(["git","commit","--only",rel,"-m","Phase 10 Amendment 2: timed run checkpoint"],cwd=LAB_ROOT,check=True,capture_output=True)
        subprocess.run(["git","push","origin",f"HEAD:refs/heads/{BRANCH}"],cwd=LAB_ROOT,check=True,capture_output=True)


def diagnostic_maps(directory):
    result=[]
    for filename,column in (("stability_summary.csv","stability_flag"),("scenario_summary.csv","scenario_sensitivity")):
        path=directory/"simulations"/filename
        if not path.exists():
            result.append({});continue
        d=pd.read_csv(path).fillna({"pid":""})
        d=d[d["mode"].eq("sim_independent")]
        result.append({(r.game_id,str(r.pid),r.stat):getattr(r,column) for r in d.itertuples()})
    return result


def refresh(directory,label):
    now=pd.Timestamp.now(tz="UTC")
    snapshot=directory/"refreshes"/(now.strftime("%Y%m%dT%H%M%S%fZ")+"_"+label)
    snapshot.mkdir(parents=True,exist_ok=False)
    errors=[]
    for args,name,timeout in ((["git","fetch","origin","main"],"fetch.log",90),
        ([sys.executable,"-m","lab.phase10_archive","--remote-main"],"archive.log",180)):
        try:
            if command(args,snapshot/name,timeout):
                errors.append(name)
        except Exception as exc:
            errors.append(repr(exc));note(f"FAILED refresh {name}: {exc}; skipped")
    try:
        from ...prospective import fetch_weather
        from ...inactives10 import collect
        target=games()
        source=pd.read_parquet(GAMES_TABLE)
        missing=[c for c in ("stadium_id","stadium") if c not in target]
        if missing:
            target=target.merge(source[["game_id"]+missing],on="game_id",how="left",validate="one_to_one")
        weather=fetch_weather(target)
        inactives=collect(target)
        exclusive_json(snapshot/"context.json",{"retrieved_at":now.isoformat(),"weather":weather,"inactives":inactives,"context_only":True})
    except Exception as exc:
        errors.append(repr(exc));note(f"FAILED context refresh: {exc}; skipped")
    try:
        frame,ct,stem=refresh_sheet()
        stable,scenarios=diagnostic_maps(directory)
        ranked=leans(frame,stable,scenarios)
        lean_stem=REPORTS_DIR/("leans_2026_w07_"+now.strftime("%Y%m%dT%H%M%S%fZ"))
        export(ranked,lean_stem,heading="Week 7: leans to investigate",context=
            f"Comparison created {now.isoformat()}; training cutoff 2026-10-19 / week 6. Tiers: {ranked.confidence_tier.value_counts().to_dict()}. This ranks research questions, not bets. Seed/scenario evidence covers the structural member, not independent proof of ensemble accuracy. Missing uncertainty evidence stays unknown.")
        exclusive_json(snapshot/"comparison.json",{"created_at":now.isoformat(),"projection_sheet":str(stem),"leans_sheet":str(lean_stem),
            "rows":len(ranked),"games":ranked.game_id.nunique(),"tiers":ranked.confidence_tier.value_counts().to_dict(),"errors":errors})
        note(f"Refresh {label}: {ranked.game_id.nunique()} games; tiers={ranked.confidence_tier.value_counts().to_dict()}; errors={len(errors)}; fixed forecasts unchanged")
        return lean_stem
    except Exception as exc:
        errors.append(repr(exc));exclusive_json(snapshot/"errors.json",errors)
        note(f"FAILED comparison refresh: {exc}; skipped")
        return None


def finalize_research():
    from .research import DEST
    path=DEST/"multiplicity.json"
    if path.exists():
        return json.loads(path.read_text())
    tests=[]
    bench=json.loads((DEST/"benchmarks2022.json").read_text()) if (DEST/"benchmarks2022.json").exists() else {}
    for stat in ("pass_yds","pass_tds","anytime_td","rec","rec_yds","rush_yds"):
        row=next((r for r in bench.get("results",[]) if r.get("stat")==stat and r.get("method")=="equal"),{})
        for baseline in ("sim_mean","base_mean"):
            c=row.get("vs_"+baseline)
            tests.append({"id":stat+" vs "+baseline,"p":c["p_improvement_one_sided"] if c else 1.,"available":c is not None})
    ablation=json.loads((DEST/"market_feature2022.json").read_text()) if (DEST/"market_feature2022.json").exists() else {}
    for stat in ("pass_yds","pass_tds","anytime_td","rec","rec_yds","rush_yds"):
        row=next((r for r in ablation.get("results",[]) if r["stat"]==stat),{})
        tests.append({"id":stat+" closing feature","p":row.get("difference",{}).get("p_improvement_one_sided",1.),"available":bool(row)})
    blends=json.loads((DEST/"game_blends.json").read_text()) if (DEST/"game_blends.json").exists() else []
    for stat in ("margin","total"):
        row=next((r for r in blends if r["stat"]==stat),{})
        for metric in ("mae","crps"):
            tests.append({"id":stat+" blend "+metric,"p":row.get("metrics",{}).get(metric,{}).get("p_improvement_one_sided",1.),"available":bool(row)})
    assert len(tests)==22
    maximum=0.
    for rank,index in enumerate(sorted(range(22),key=lambda i:tests[i]["p"])):
        maximum=max(maximum,min(1.,tests[index]["p"]*(22-rank)))
        tests[index]["holm_p"]=maximum
        tests[index]["passes_multiplicity"]=maximum<.05
    lookup={t["id"]:t for t in tests}
    decisions=[]
    for stat in ("pass_yds","pass_tds","anytime_td","rec","rec_yds","rush_yds"):
        row=next((r for r in bench.get("results",[]) if r.get("stat")==stat and r.get("method")=="equal"),{})
        passed=bool(row) and row.get("games",0)>=100 and all(row.get("vs_"+b,{}).get("ci95",[0,1])[1]<0 and lookup[stat+" vs "+b]["passes_multiplicity"] for b in ("sim_mean","base_mean"))
        decisions.append({"experiment":"benchmark "+stat,"status":"Challenger; development gate only, no promotion" if passed else "Rejected/blocked under preregistered gate","passes":passed})
        r=next((r for r in ablation.get("results",[]) if r["stat"]==stat),{})
        passed=bool(r) and r.get("games",0)>=100 and r["difference"]["ci95"][1]<0 and lookup[stat+" closing feature"]["passes_multiplicity"] and r.get("log_loss_difference",0)<=0
        decisions.append({"experiment":"closing feature "+stat,"status":"Challenger; retrospective development only" if passed else "Rejected","passes":bool(passed)})
    for stat in ("margin","total"):
        r=next((r for r in blends if r["stat"]==stat),{})
        passed=bool(r) and all(r["metrics"][m]["ci95"][1]<0 and lookup[stat+" blend "+m]["passes_multiplicity"] for m in ("mae","crps"))
        decisions.append({"experiment":"convex blend "+stat,"status":"Challenger; DEV only" if passed else "Rejected","passes":bool(passed)})
    result={"family":22,"tests":tests,"decisions":decisions,"decision":"No automatic selection or promotion; frozen equal reference remains unchanged."}
    exclusive_json(path,result)
    return result


def final_report(directory,partial=False):
    from .research import DEST
    results=[]
    def delta(c):
        return f"{c['difference']:+.4f} [{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}]"
    for name in ("benchmarks2022.json","market_feature2022.json","game_blends.json"):
        if not (DEST/name).exists():
            results.append(f"| {name} | unavailable | unavailable | blocked/failed; see STATUS |")
            continue
        data=json.loads((DEST/name).read_text())
        if name.startswith("benchmarks"):
            for row in data["results"]:
                if row.get("method")=="equal":
                    results.append(f"| Props {row['stat']} vs v1 / B | 2022; {row['n']} / {row['games']} games | {delta(row['vs_sim_mean'])} / {delta(row['vs_base_mean'])} | shadow; matched retrospective eligibility |")
        elif name.startswith("market"):
            for row in data["results"]:
                results.append(f"| Closing-feature {row['stat']} | 2022; {row['n']} | {delta(row['difference'])} | no independent-default change |")
        else:
            for row in data:
                results.append(f"| {row['stat']} convex blend | DEV; {row['metrics']['mae']['n']} | MAE {delta(row['metrics']['mae'])}; CRPS {delta(row['metrics']['crps'])} | descriptive; no promotion |")
    plan=json.loads((directory/"plan.json").read_text()) if (directory/"plan.json").exists() else {}
    summary=json.loads((directory/"simulations"/"summary.json").read_text()) if (directory/"simulations"/"summary.json").exists() else {}
    lines=["# Phase 10 Amendment 2 — 2026-10-20", "", "**Completed:** week-6 MNF refresh; frozen recency-weighted fit through October 19 / completed week 6; append-only week-7 revision 2, quote-consensus/coherence diagnostics and investigation sheets. Original forecasts, champion and v1 defaults preserved. $0; no sends, deployment, database writes or original eval call.","",
        "**Model research:** paired game-cluster 95% CIs (2,000 draws, seed 20261020); negative loss differences favor experimental predictions. Holm family 22; missing comparisons p=1. Closing lines have retrospective information.","",
        "| Hypothesis | Split / n | Difference vs comparison [95% CI] | Decision |","|---|---|---|---|"]+results+[
        "",f"**Prospective run:** {'PARTIAL' if partial else 'eight-hour'} window {plan.get('start_at','unavailable')} to {plan.get('end_at','unavailable')}; structural diagnostics {summary}. No 2026 outcome selection or accuracy claim.","",
        "**Concerns:** original v1/B support four markets, not passing TD or ATD, and use retrospective QB/roster eligibility; exact intersections are reported, not a fictitious full 8,576-row comparison. Eligible-player sums may omit volume. ATD sums count distinct scorers, not TD count. First-TD contract settlement is unverified; no price gaps. Scenarios redistribute roles with efficiencies/anchors held fixed except script; they do not capture all QB/injury effects. Missing seed/scenario/quote evidence cannot qualify for Tier A. Defense remains a non-player label, never assigned an ID.","",
        "**Next:** frozen 2023–25 single look not started: estimated weekly full refits exceed the remaining Part-1 budget (>1 hour required is necessary, not sufficient). Untouched later evidence is still required before acceptance. Improve historical eligibility and scenario efficiency modelling without tuning on 2026.","",
        "**Needs Travis:** manual scheduler/release review only; no Windows tasks created. Review source completeness, unresolved identities and any flagged coherence/stability/lineup issues before interpreting the ranked research list. Nothing here is a bet recommendation or stake.","",
        "**Checks:** see STATUS.md and final_tests.log; all operational failures are retained there. Full metrics, matched rows, per-seed/scenario outputs and immutable comparison refreshes remain local under artifacts/props/phase10/amendment2."]
    path=REPORTS_DIR/"run_20261020"/"REPORT.md"
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return path


def planned_window(start):
    start=pd.Timestamp(start)
    end=start+pd.Timedelta(hours=8);wrap=end-pd.Timedelta(minutes=45)
    if end>HARD_STOP:
        raise ValueError("Eight-hour run cannot finish before hard stop; no new run started")
    return end,wrap


def run_eight_hours():
    start=pd.Timestamp.now(tz="UTC");end,wrap=planned_window(start)
    directory=ROOT/"part2"/start.strftime("%Y%m%dT%H%M%S%fZ")
    directory.mkdir(parents=True,exist_ok=False)
    exclusive_json(directory/"plan.json",{"start_at":start.isoformat(),"end_at":end.isoformat(),"wrap_at":wrap.isoformat(),"hard_stop":HARD_STOP.isoformat(),"duration_hours":8,"revision":str(REV),"training_cutoff_date":"2026-10-19"})
    note(f"Part 2 START {start.tz_convert('America/New_York').isoformat()}; END {end.tz_convert('America/New_York').isoformat()}; wrap {wrap.tz_convert('America/New_York').isoformat()}; directory={directory}")
    commit_status()
    last_lean=refresh(directory,"start")
    log=(directory/"simulations.log").open("w")
    sim=subprocess.Popen([sys.executable,"-u","-m","lab.props.amendment2.run","simulation","--directory",str(directory/"simulations"),"--deadline",wrap.isoformat()],cwd=LAB_ROOT,stdout=log,stderr=subprocess.STDOUT)
    next_refresh=start+pd.Timedelta(hours=2);next_commit=start+pd.Timedelta(minutes=45)
    longrun_id=None;longrun_checked=False;analyzed=False;finalized=False;partial=False
    while pd.Timestamp.now(tz="UTC")<end:
        now=pd.Timestamp.now(tz="UTC")
        if (directory/"STOP_AFTER_CURRENT.json").exists():
            partial=True
            if sim.poll() is None:
                time.sleep(15);continue
            note("Authorized stop-after-current request observed; wrapping partial run");break
        if now>=next_refresh and now<wrap:
            last_lean=refresh(directory,"scheduled") or last_lean
            next_refresh+=pd.Timedelta(hours=2)
        if sim.poll() is not None and not longrun_checked and now<wrap-pd.Timedelta(minutes=30):
            longrun_checked=True;log.close();note(f"Stability/scenario child finished exit={sim.returncode}")
            if sim.returncode:
                note("FAILED prospective simulation child; retain partial files, no retry")
            last_lean=refresh(directory,"diagnostics_complete") or last_lean
            budget=(wrap-pd.Timedelta(minutes=20)-now).total_seconds()/3600
            if sim.returncode==0 and active_job() is None and budget>.25 and psutil.cpu_percent(interval=.25)<50:
                old_aff=psutil.Process().cpu_affinity();psutil.Process().cpu_affinity(list(range(7)))
                try:
                    command([sys.executable,"-m","lab.longrun","start","--hours",str(budget),"--threads","7","--dev-only"],directory/"longrun_start.log",180)
                    text=(directory/"longrun_start.log").read_text()
                    matches=re.findall(r"lr\d{8}_\d{6}",text)
                    longrun_id=matches[-1] if matches else active_job()
                    note(f"Optional DEV-only longrun started {longrun_id}; seven cores; no final validation or promotion")
                finally:
                    psutil.Process().cpu_affinity(old_aff)
            else:
                note("Optional game longrun skipped: CPU/job/time availability condition not met")
        if longrun_id and not analyzed and active_job()!=longrun_id and now<wrap:
            analyzed=True
            command([sys.executable,"-m","lab.analyze_longrun",longrun_id,"--no-record","--max-candidates","2"],directory/"longrun_analysis.log",900)
            note("DEV-only longrun analysis finished; no prospective registry update")
        if now>=next_commit:
            note(f"Timed checkpoint: simulation_exit={sim.poll()}; active_own_longrun={bool(longrun_id and active_job()==longrun_id)}; elapsed_hours={(now-start).total_seconds()/3600:.2f}")
            try:commit_status()
            except Exception as exc:note(f"FAILED checkpoint commit/push: {exc}; skipped")
            next_commit+=pd.Timedelta(minutes=45)
        if now>=wrap and not finalized:
            finalized=True
            note("Final 45-minute wrap-up: no new experiments")
            if longrun_id and active_job()==longrun_id:
                command([sys.executable,"-m","lab.longrun","stop",longrun_id],directory/"longrun_stop.log",60)
            last_lean=refresh(directory,"final") or last_lean
            command([sys.executable,"-m","pytest","tests","-q"],REPORTS_DIR/"run_20261020"/"final_tests.log",1800)
            finalize_research();final_report(directory)
            note("Wrap-up report/test outputs saved; holding original eight-hour end time")
        time.sleep(min(30,max(1,(end-pd.Timestamp.now(tz="UTC")).total_seconds())))
    if sim.poll() is None:
        sim.terminate();sim.wait(timeout=30);note("FAILED simulation exceeded run boundary; process stopped and partial files retained")
    if not finalized:
        finalize_research();final_report(directory,partial=partial)
    if last_lean:
        for suffix in (".csv",".md"):
            target=REPORTS_DIR/("leans_2026_w07"+suffix)
            if target.exists():
                raise FileExistsError("Refuse to replace an earlier delivered leans sheet")
            shutil.copy2(last_lean.with_suffix(suffix),target)
    exclusive_json(directory/"completion.json",{"finished_at":pd.Timestamp.now(tz="UTC").isoformat(),"partial":partial,"final_lean":str(last_lean),"planned_end":end.isoformat()})
    note("Part 2 complete; final deliverables ready for review, commit and branch push")
    return directory


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=["part2","simulation"]);p.add_argument("--directory",type=Path);p.add_argument("--deadline");a=p.parse_args()
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS);psutil.Process().cpu_affinity(list(range(14)))
    os.environ.update(OMP_NUM_THREADS="14",MKL_NUM_THREADS="14")
    if a.command=="simulation":
        from .simulation import run
        print(json.dumps(run(a.directory,deadline=a.deadline),indent=2))
    else:
        print(run_eight_hours())
