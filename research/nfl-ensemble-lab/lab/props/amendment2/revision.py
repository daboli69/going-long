"""Append-only forecast revision and fixed-distribution quote refreshes."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import shutil
import numpy as np
import pandas as pd
from ...archive10 import ARCHIVE, temporal, freshness
from ...config import REPORTS_DIR
from ...data_pipeline import FEATURE_STORE
from .. import projections10 as P
from ..ensemble import structural as S
from ..ensemble.data import OUT as BASE
from ..lines import archived_lines
from .sheets import consensus, compare, coherence, export, KEY

ROOT = BASE / "amendment2"
REV = ROOT / "revisions" / "r02_20261020"


def exclusive_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)


@contextmanager
def relocated(destination):
    old = (S.OUT, P.OUT, P.REPORTS_DIR)
    S.OUT = P.OUT = destination
    P.REPORTS_DIR = destination / "reports"
    P.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        yield
    finally:
        S.OUT, P.OUT, P.REPORTS_DIR = old


def create(log=print):
    original = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (BASE / "forecasts2026").glob("*.json")}
    REV.mkdir(parents=True, exist_ok=True)
    for name in ("production_fit.json", "features_production.parquet", "dev_predictions.parquet"):
        if not (REV / name).exists():
            shutil.copy2(BASE / name, REV / name)
    fit = json.loads((REV / "production_fit.json").read_text())
    if fit["training_last_completed_week"] != 6:
        raise ValueError("Revision 2 requires completed week 6")
    captured = []
    def capture(row, samples):
        captured.append({"game_id": row["game_id"], "pid": row["pid"], "stat": row["stat"], "samples": np.asarray(samples,np.float32).tolist()})
    with relocated(REV):
        structural = S.run(2026, 7, 1000, production=True, deadline="2026-10-20T13:04:55Z", log=log)
        result = P.forecast(7, distribution_sink=capture, log=log)
    if captured:
        path = REV / "distributions.parquet"
        if path.exists():
            raise FileExistsError("Predictive distributions already archived")
        pd.DataFrame(captured).drop_duplicates(KEY).to_parquet(path,index=False)
    unchanged = all(hashlib.sha256(__import__("pathlib").Path(p).read_bytes()).hexdigest()==h for p,h in original.items())
    if not unchanged:
        raise AssertionError("Revision 1 bytes changed")
    meta = {"revision": 2, "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "training_cutoff_date": fit["training_cutoff_date"], "training_last_completed_week":6,
        "frozen_config_sha256":fit["frozen_config_sha256"], "revision1_sha256": original,
        "revision1_unchanged":unchanged,"structural":structural,"forecasts":result}
    if not (REV / "revision.json").exists():
        exclusive_json(REV / "revision.json",meta)
    return meta


def games():
    d = pd.read_parquet(FEATURE_STORE)
    now = pd.Timestamp.now(tz="UTC")
    return d[d.season.eq(2026)&d.week.eq(7)&~d.completed&(d.kickoff_utc>now)].copy()


def fixed():
    files = sorted((REV/"forecasts2026").glob("*.json"))
    payloads = [json.loads(p.read_text()) for p in files]
    if not payloads:
        raise ValueError("Revision 2 forecasts unavailable")
    frame = pd.DataFrame([r|{"forecast_created_at":p["generated_at"],"frozen_config_sha256":p["frozen_config_sha256"]}
                          for p in payloads for r in p["rows"]])
    frame["pid"] = frame.pid.fillna("")
    frame = frame.drop_duplicates(KEY).copy()
    distributions = {(r.game_id,str(r.pid),r.stat):np.asarray(r.samples) for r in pd.read_parquet(REV/"distributions.parquet").itertuples()}
    totals = {}
    for path in (REV/"structural_prospective2026_recent").glob("2026_07_*.json"):
        meta = json.loads(path.read_text())
        independent = next(r for r in meta["games"] if r["member"]=="sim_independent")
        totals[meta["game_id"]] = independent.get("team_totals",{})
        for stat in ("margin","total"):
            distributions[(meta["game_id"],"",stat)] = np.asarray(independent[stat+"_samples"])
    return frame,distributions,totals


def latest_props(targets, now):
    d = archived_lines(asof=now)
    if d.empty:
        return d
    # Use a complete newest source snapshot. A removed book must not persist
    # forever merely because an earlier archive still contains its quote.
    generated = pd.to_datetime(d.generated_at,utc=True,format="mixed",errors="coerce")
    d = d[generated.eq(generated.max())].copy()
    observed = pd.to_datetime(d.available_at,utc=True,format="mixed",errors="coerce")
    d = d[d.pregame_verified & d.period.eq("FULL") & (observed<=now)]
    rows=[]
    for g in targets.itertuples():
        z=d[d.home.eq(g.home_team)&d.away.eq(g.away_team)]
        delta=(pd.to_datetime(z.kickoff,utc=True,format="mixed")-g.kickoff_utc).abs()
        for r in z[delta<=pd.Timedelta(minutes=15)].to_dict("records"):
            rows.append(r|{"game_id":g.game_id,"pid":r["gsis_id"],"market_line":r["line"],
                "market_archive":r["archive"],"quote_available_at":r["available_at"]})
    return pd.DataFrame(rows)


def latest_games(targets,now):
    snapshots=[]
    for path in (ARCHIVE/"market").glob("going_*.json"):
        d=json.loads(path.read_text())
        d["_archive"]=path.name
        if d.get("generated_at") and d.get("available_at") and pd.Timestamp(d["available_at"])<=now:
            snapshots.append(d)
    if not snapshots:
        return pd.DataFrame()
    snapshot=max(snapshots,key=lambda d:pd.Timestamp(d["generated_at"]))
    rows=[]
    for g in targets.itertuples():
        for r in snapshot["content"]:
            if r.get("home")!=g.home_team or r.get("away")!=g.away_team or r.get("period")!="FULL" or r.get("in_play"):
                continue
            if not temporal(r.get("quote_time"),snapshot["available_at"],r.get("kickoff"))["pregame_verified"]:
                continue
            if abs(pd.Timestamp(r["kickoff"])-g.kickoff_utc)>pd.Timedelta(minutes=15):
                continue
            side=str(r["side"]).lower()
            if r["market"]=="spreads":
                stat="margin"
                value=-float(r["point"]) if side=="home" else float(r["point"])
                pricekey="over_odds" if side=="home" else "under_odds"
            elif r["market"]=="totals":
                stat,value="total",float(r["point"])
                pricekey="over_odds" if side=="over" else "under_odds"
            else:
                continue
            rows.append({"game_id":g.game_id,"pid":"","stat":stat,"book":r["book"],"market_line":value,
                pricekey:r["price"],"quote_time":r["quote_time"],"dfs":False,
                "market_archive":snapshot["_archive"],"quote_available_at":snapshot["available_at"],
                "identity_mapping_source":"exact game teams and kickoff"}|freshness(r["quote_time"],now))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).groupby(["game_id","pid","stat","book","market_line"],dropna=False,as_index=False).first()


def refresh_sheet(stamp=None):
    base,distributions,totals=fixed()
    targets,now=games(),pd.Timestamp.now(tz="UTC")
    props=latest_props(targets,now)
    market=latest_games(targets,now)
    unmatched=props[props.pid.isna()][[c for c in ("game_id","player","stat","book","market_line") if c in props]] if len(props) else props
    props=props[props.pid.notna()] if len(props) else props
    selected=["game_id","pid","stat","book","market_line","over_odds","under_odds","quote_time","line_status","line_age_hours","dfs",
              "market_archive","quote_available_at","identity_mapping_source"]
    pieces=[d.reindex(columns=selected) for d in (props,market) if len(d)]
    quotes=pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame(columns=selected)
    clean=base.drop(columns=[c for c in selected if c not in KEY and c in base]+[c for c in ("gap","gap_units","benchmark_scope_status","market_probability") if c in base])
    d=clean.merge(quotes,on=KEY,how="left",validate="one_to_many")
    d["line_status"]=d.line_status.fillna("unavailable")
    d=compare(consensus(d),distributions)
    gm=d.row_type.eq("game")
    pair=d.loc[gm,["projection","sim_independent_projection"]]
    d.loc[gm,"member_min"],d.loc[gm,"member_max"]=pair.min(axis=1),pair.max(axis=1)
    ft=d.row_type.eq("first_td")
    pair=d.loc[ft,["projection","structural_probability"]]
    d.loc[ft,"member_min"],d.loc[ft,"member_max"]=pair.min(axis=1),pair.max(axis=1)
    d["member_spread_definition"]="named learned/structural means before ensemble calibration"
    d.loc[gm,"member_spread_definition"]="independent ridge mean and independent structural mean; market excluded"
    d.loc[ft,"member_spread_definition"]="structural first-TD probability and ATD-reweighted variant; descriptive variant spread"
    # No nonnegative-stat quantile can be negative in a delivered sheet.
    for col in ("q10","q50","q90","quantile_head_q10","quantile_head_q50","quantile_head_q90"):
        if col in d:
            mask=~d.stat.eq("margin")
            d.loc[mask,col]=pd.to_numeric(d.loc[mask,col],errors="coerce").clip(lower=0)
    d,ct=coherence(d,totals)
    d["comparison_created_at"]=now.isoformat()
    d["forecast_revision"]=2
    d["market"]=d.stat
    d["quote_settlement_scope"]="regulation-only model vs quote settlement unverified"
    stem=REPORTS_DIR/f"projections_2026_w7_r02_{stamp or now.strftime('%Y%m%dT%H%M%S%fZ')}"
    export(d,stem,heading="Week 7 shadow projections, revision 2",context="Frozen model refit cutoff 2026-10-19 / completed week 6. Market prices are benchmarks only; forecast distributions are unchanged by this comparison refresh.")
    ct.to_csv(stem.with_name(stem.name+"_coherence").with_suffix(".csv"),index=False)
    with stem.with_suffix(".md").open("a",encoding="utf-8") as f:
        cols=["game_id","team","coherence_flag","atd_vs_td_count_gap"]
        lines=["\n## Team coherence\n", "| "+" | ".join(cols)+" |", "| "+" | ".join(["---"]*len(cols))+" |"]
        lines += ["| "+" | ".join(str(row[c]).replace("|","/") for c in cols)+" |" for _,row in ct.iterrows()]
        f.write("\n".join(lines)+"\n")
    unmatched.to_csv(stem.with_name(stem.name+"_unmatched").with_suffix(".csv"),index=False)
    return d,ct,stem


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("command",choices=["create","sheet"]);a=p.parse_args()
    print(json.dumps(create() if a.command=="create" else {"sheet":str(refresh_sheet()[2])},indent=2))
