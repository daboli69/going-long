"""Improvement protocol Step 6: prospective pipeline check and the code-hash gate (PROTOCOL2.md). Read-only: registers nothing."""
import glob, shutil, subprocess, tempfile
from common import *

res = header("i6_pipeline")


def task_names():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-ScheduledTask | Select-Object -ExpandProperty TaskName) -join '|'"], capture_output=True, text=True).stdout.strip()
    return sorted(out.split("|"))


before = task_names()
lab_tasks = subprocess.run(["powershell", "-NoProfile", "-Command",
    "Get-ScheduledTask | Where-Object { ($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -match 'nfl-ensemble|GOING' } | ForEach-Object { $_.TaskName }"], capture_output=True, text=True).stdout.split("\n")
res["scheduler_query"] = {"tasks_scanned": len(before), "lab_related_tasks": sorted(t.strip() for t in lab_tasks if t.strip())}
entry = {"winner_variants_freeze": "scripts/home_win_deep.py", "joint_model_freeze": "scripts/forecast_study.py", "props_freeze": "scripts/props_kalshi_collect.py", "scoring": "scripts/home_win_deep.py", "hash_and_order_check": "scripts/verify_results.py"}
res["entry_points_exist"] = {k: (ROOT / v).is_file() for k, v in entry.items()}
sched = (ROOT / "lab" / "scheduler.py").read_text(encoding="utf-8", errors="ignore")
res["scheduler_mentions_freeze_or_score"] = any(w in sched for w in ("freeze", "forecast_study", "props_kalshi_collect", "score_freezes", "home_win_deep"))
res["freeze_scheduled"] = res["scheduler_mentions_freeze_or_score"] or any("Freeze" in t for t in res["scheduler_query"]["lab_related_tasks"])
res["archives"] = {k: len(glob.glob(str(ROOT / "data/raw/archive" / k / "*.json"))) for k in ("homewin_deep", "forecast_games", "props_kalshi")}
res["task_definitions_written"] = (SRC / "PIPELINE_TASKS.md").is_file()

# (d) code-hash gate
files = sorted(OUT.glob("rehearsal_step*.json")) + [OUT / "i3_rehearsal.json", OUT / "i4_rehearsal.json"]
extras = {"i3_rehearsal.json": ("i3_screen.py",), "i4_rehearsal.json": ("i4_blend.py",)}
have, accepted = {}, {}
for f in files:
    have[f.name] = bool(json.load(open(f)).get("code_sha256")) and bool(json.load(open(f))["PASS"])
    try:
        gate(f.name, extras.get(f.name, ())); accepted[f.name] = True
    except AssertionError as e:
        accepted[f.name] = str(e)
res["rehearsals_have_hash_and_pass"] = have
res["gate_accepts_current_code"] = accepted
tmp = Path(tempfile.mkdtemp(prefix="gate_stale_"))
stale = json.load(open(OUT / "rehearsal_step3.json")); k0 = next(iter(stale["code_sha256"])); stale["code_sha256"][k0] = "0" * 64
(tmp / "rehearsal_step3.json").write_text(json.dumps(stale))
import common
old = common.OUT; common.OUT = tmp
try:
    common.gate("rehearsal_step3.json"); refused = False
except AssertionError as e:
    refused = True; refusal = str(e)
finally:
    common.OUT = old
res["planted_stale_hash"] = {"gate_refused": refused, "message": refusal if refused else None}
after = task_names()
res["tasks_registered_by_this_step"] = sorted(set(after) - set(before))
res["checks"] = {"a_scheduler_queried": len(before) > 0, "b_entry_points_located_and_schedule_status_stated": all(res["entry_points_exist"].values()),
                 "c_definitions_written_nothing_registered": res["task_definitions_written"] and not res["tasks_registered_by_this_step"],
                 "d_all_rehearsals_pass_with_hash": all(have.values()), "d_gate_accepts_all_current": all(v is True for v in accepted.values()), "d_stale_hash_refused": refused}
res["PASS"] = bool(all(res["checks"].values()))
write("i6_pipeline.json", res)
print("I6", "PASS" if res["PASS"] else "FAIL", json.dumps(res["checks"])); print(res["scheduler_query"]["lab_related_tasks"], res["archives"], "freeze scheduled:", res["freeze_scheduled"])
