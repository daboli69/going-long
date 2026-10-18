"""Overnight research batch (started by Travis; never scheduled automatically).

1. Reproduce every completed pre-registered study (8.4, 8.5, 8.6, 8.7) and flag any headline number that changed.
   A study is only re-run if its results already exist, so this can never take a study's first (single) look.
2. Refresh every prospective (post-registration) evaluation: the only source of new evidence.
3. Write artifacts/overnight/<timestamp>/summary.md and latest.json.

Run: python -m lab.overnight            (about 5-10 minutes; nothing external, no model or GOING change)
"""
from __future__ import annotations

import importlib
import json
import time
import traceback

import pandas as pd

from .config import ARTIFACTS_DIR

ROOT = ARTIFACTS_DIR / "overnight"

# (phase, module, results file, run kwargs, headline paths) - headline = dotted keys compared before/after
STUDIES = [
    ("8.4", "lab.upsets84", "phase84/results.json", {}, ["V.p_one_sided", "S2.p_one_sided", "S2.coef_per_sd", "holm.S2"]),
    ("8.5", "lab.upsets85", "phase85/results.json", {"n_perm": 10_000, "log": lambda m: None},
     ["R1.p_one_sided", "R1.coef_per_sd", "carried"]),
    ("8.6", "lab.tracking86", "phase86/results.json", {}, ["T1_beyond_champion.p_one_sided", "P1_ngs_proxy.pearson_r"]),
    ("8.7", "lab.ngs87", "phase87/results.json", {}, []),
]
PROSPECTIVE = [
    ("8.4 S2P line-movement flag", "lab.upsets84", "prospective_eval", {}),
    ("8.2 P1-P3 blind-spot hypotheses", "lab.blindspots82", "prospective_eval", {}),
    ("Discovery hypotheses", "lab.discovery", "evaluate_prospective_hypotheses", {}),
]
TOL = 1e-6


def _get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def compare(before: dict, after: dict, paths: list) -> list:
    """Headline keys whose value changed (numbers beyond TOL, anything else by equality)."""
    out = []
    for p in paths:
        a, b = _get(before, p), _get(after, p)
        same = (abs(a - b) <= TOL) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else a == b
        if not same:
            out.append({"key": p, "before": a, "after": b})
    return out


def _records(x):
    if isinstance(x, pd.DataFrame):
        return x.to_dict("records")
    return x


def run(log=print) -> dict:
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = {"started_at": stamp, "studies": [], "prospective": []}
    for phase, mod, rel, kw, heads in STUDIES:
        f = ARTIFACTS_DIR / rel
        row = {"phase": phase}
        if not f.exists():
            row["status"] = "skipped: no completed results yet (its single look has not been taken)"
            rep["studies"].append(row)
            continue
        t0 = time.time()
        try:
            before = json.loads(f.read_text())
            log(f"reproducing {phase}")
            importlib.import_module(mod).run(**kw)
            after = json.loads(f.read_text())
            diff = compare(before, after, heads)
            row |= {"status": "reproduced" if not diff else "CHANGED", "changes": diff, "seconds": round(time.time() - t0)}
        except Exception as e:
            row |= {"status": "error", "error": repr(e), "trace": traceback.format_exc()[-1500:]}
        rep["studies"].append(row)
    for name, mod, fn, kw in PROSPECTIVE:
        try:
            log(f"prospective: {name}")
            rep["prospective"].append({"name": name, "result": _records(getattr(importlib.import_module(mod), fn)(**kw))})
        except Exception as e:
            rep["prospective"].append({"name": name, "error": repr(e)})
    rep["finished_at"] = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%SZ")
    (out_dir / "report.json").write_text(json.dumps(rep, indent=2, default=str))
    (out_dir / "summary.md").write_text(summary_md(rep), encoding="utf-8")
    (ROOT / "latest.json").write_text(json.dumps({"dir": stamp, **rep}, indent=2, default=str))
    return rep


def summary_md(rep: dict) -> str:
    lines = [f"# Overnight research {rep['started_at']} -> {rep.get('finished_at')}", "", "## Completed studies (reproduction)"]
    for s in rep["studies"]:
        extra = ""
        if s.get("changes"):
            extra = "; " + ", ".join(f"{c['key']}: {c['before']} -> {c['after']}" for c in s["changes"])
        elif s.get("error"):
            extra = f"; {s['error']}"
        lines.append(f"- **{s['phase']}**: {s['status']}{extra}")
    lines += ["", "## Prospective evaluations (new evidence only)"]
    for p in rep["prospective"]:
        if "error" in p:
            lines.append(f"- **{p['name']}**: error {p['error']}")
            continue
        r = p["result"]
        rows = r if isinstance(r, list) else [r]
        for x in rows:
            if isinstance(x, dict):
                games = x.get("games", x.get("n", "?"))
                need = x.get("min_games", "")
                lines.append(f"- **{p['name']}** {x.get('id', x.get('hypothesis', ''))}: {games}/{need} games - {x.get('status', '')}")
    lines += ["", "A CHANGED study means its inputs moved (e.g. an nflverse correction); the original committed result stands "
              "until the change is explained. Nothing here changes a model."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    log_file = ARTIFACTS_DIR / "overnight_run.log"
    with open(log_file, "a", encoding="utf-8") as fh:
        def log(m):
            fh.write(f"{pd.Timestamp.now(tz='UTC').isoformat()} {m}\n")
            fh.flush()
        r = run(log)
    print((ROOT / r["started_at"] / "summary.md").read_text(encoding="utf-8"))
