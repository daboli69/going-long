"""Step 1: hash every input and the code that reads it (PROTOCOL.md)."""
import datetime as dt, glob, hashlib, json
from common import *

REL = ["data/cache/games.parquet", "data/cache/homewin_deep/kalshi_history.parquet", "data/cache/homewin_deep/walk_forward.parquet",
       "data/cache/homewin_deep/forecast_wf.parquet", "data/cache/homewin_deep/features.parquet", "data/cache/homewin_deep/going_quotes.parquet",
       "data/cache/props_kalshi/quotes.parquet", "data/cache/props_kalshi/scored_ladders.parquet", "data/cache/props_kalshi/scored_thresholds.parquet",
       "data/cache/props_kalshi_scope.parquet", "data/cache/injury_rows_pregame.parquet", "data/cache/team_game_stats.parquet",
       "lab/forecast_core.py", "lab/kalshi.py", "lab/homewin_deep.py", "lab/homewin_eval.py", "lab/props_kalshi.py", "scripts/props_kalshi.py"]
GROUPS = {"pbp_agg_parquets": "data/cache/homewin_deep/pbp_agg_*.parquet", "espn_injury_snapshots": "data/raw/archive/espn_injuries_*.json",
          "forecast_freeze_archive": "data/raw/archive/forecast_games/*.json", "props_freeze_archive": "data/raw/archive/props_kalshi/*.json",
          "fantasypoints_manifests": "../../FantasyPoints/manifests/*"}

def group_hash(files):
    h = hashlib.sha256()
    for f in sorted(files):
        p = Path(f)
        if p.is_file(): h.update(p.name.encode()); h.update(sha(p).encode())
    return h.hexdigest()

res = header("step1"); res["inputs"] = {}; missing = []
ref = (OUT / "q1_winner_ceiling.json").stat().st_mtime if (OUT / "q1_winner_ceiling.json").exists() else None
prev = json.loads((OUT / "step1_inputs.json").read_text())["inputs"] if (OUT / "step1_inputs.json").exists() else {}
for rel in REL:
    p = ROOT / rel
    if not p.is_file(): missing.append(rel); continue
    st = p.stat(); res["inputs"][rel] = {"sha256": sha(p), "bytes": st.st_size, "modified_utc": dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat()}
for name, pat in GROUPS.items():
    files = glob.glob(str(ROOT / pat))
    if not files: missing.append(pat); continue
    res["inputs"][name] = {"sha256": group_hash(files), "files": len(files), "pattern": pat,
                           "latest_modified_utc": dt.datetime.fromtimestamp(max(Path(f).stat().st_mtime for f in files), dt.timezone.utc).isoformat()}
res["missing"] = missing
res["changed_vs_previous_manifest"] = [k for k, v in res["inputs"].items() if k in prev and prev[k]["sha256"] != v["sha256"]] if prev else "no previous manifest (this is the first)"
if ref:
    cut = dt.datetime.fromtimestamp(ref, dt.timezone.utc).isoformat()
    res["earlier_run_time_utc"] = cut
    res["modified_after_earlier_winner_ceiling_run"] = [k for k, v in res["inputs"].items() if v.get("modified_utc", v.get("latest_modified_utc")) > cut]
res["PASS"] = (not missing)
write("step1_inputs.json", res)
print("PASS" if res["PASS"] else "FAIL", "missing:", missing); print("modified after earlier run:", res.get("modified_after_earlier_winner_ceiling_run"))
print(len(res["inputs"]), "inputs hashed")
