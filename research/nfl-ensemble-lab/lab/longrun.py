"""Phase 4 long-run model research: extended, resumable, CPU-friendly optimisation of
the six model families. Runs as its own process (survives dashboard restarts).

  python -m lab.longrun start --hours 8          (or --minutes, --max-trials)
  python -m lab.longrun resume [JOB]
  python -m lab.longrun pause|continue|stop [JOB]
  python -m lab.longrun status

Honest evaluation design
  * Objective = mean log loss over walk-forward DEVELOPMENT folds 2019-2022
    (train on seasons < s, predict s). Feature filtering and calibration are fit inside
    each fold on earlier data only. Validation (2023-24) is NEVER used during search.
  * When a job finishes, the best configuration per family is checked ONCE on 2023-24
    (and 2025 diagnostic). Every such look is logged in validation_ledger.jsonl and the
    required significance level is divided by the number of looks so far (repeated
    looks at the same seasons are not treated as fresh evidence).
  * A family-best that passes (validation improvement vs the champion's version of that
    family, Holm across families at the look-adjusted level, 2025 not worse by > 0.005)
    can only become a SHADOW challenger; promotion needs prospective evidence (Phase 3).
  * Longer search is not assumed to help: the report shows dev vs validation gaps.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR, LAB_ROOT, RANDOM_SEED

LR_DIR = ARTIFACTS_DIR / "longrun"
LR_DIR.mkdir(parents=True, exist_ok=True)
LOCK = LR_DIR / "ACTIVE.lock"
VAL_LEDGER = LR_DIR / "validation_ledger.jsonl"
FAMILIES = ("logreg", "xgboost", "decision_tree", "random_forest", "mlp", "single_layer")
DEV_FOLDS = (2019, 2020, 2021, 2022)
VAL_SEASONS, DIAG_SEASONS = (2023, 2024), (2025,)
MIN_SHARE = 0.10            # every family gets at least ~10% of trials
MIN_FREE_MEM_GB = 2.0


def _atomic_write(path, text: str, tries: int = 25) -> None:
    """Write via temp file + replace, retrying when Windows/OneDrive briefly locks the target."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    for i in range(tries):
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.2 * (i + 1))
    path.write_text(text, encoding="utf-8")   # last resort: direct write


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hardware() -> dict:
    import psutil
    phys = psutil.cpu_count(logical=False) or 2
    return {"logical_cpus": psutil.cpu_count(), "physical_cpus": phys, "memory_gb": round(psutil.virtual_memory().total / 1e9, 1),
            "default_threads": max(1, min(phys - 2, 8))}


# --------------------------------------------------------------------------- estimators

def make_estimator(key: str, p: dict, n_threads: int = 1):
    """Pipeline for a long-run configuration (preprocessing inside the pipeline)."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from xgboost import XGBClassifier

    from .models import TorchClassifier, _imputed, _scaled
    if key == "logreg":
        return _scaled(LogisticRegression(C=p["C"], penalty=p.get("penalty", "l2"),
                                          solver="liblinear" if p.get("penalty") == "l1" else "lbfgs", max_iter=5000))
    if key == "xgboost":
        return _imputed(XGBClassifier(n_estimators=p["n_estimators"], max_depth=p["max_depth"], learning_rate=p["learning_rate"],
                                      subsample=p["subsample"], colsample_bytree=p["colsample_bytree"], min_child_weight=p["min_child_weight"],
                                      reg_lambda=p["reg_lambda"], gamma=p.get("gamma", 0.0), eval_metric="logloss",
                                      random_state=RANDOM_SEED, n_jobs=n_threads, tree_method="hist"))
    if key == "decision_tree":
        return _imputed(DecisionTreeClassifier(max_depth=p["max_depth"], min_samples_leaf=p["min_samples_leaf"], ccp_alpha=p["ccp_alpha"],
                                               criterion=p.get("criterion", "gini"), random_state=RANDOM_SEED))
    if key == "random_forest":
        return _imputed(RandomForestClassifier(n_estimators=p["n_estimators"], max_depth=p["max_depth"], min_samples_leaf=p["min_samples_leaf"],
                                               max_features=p["rf_max_features"], random_state=RANDOM_SEED, n_jobs=n_threads))
    if key == "mlp":
        widths = tuple(max(4, int(p["width"] / (2 ** i))) for i in range(p["n_layers"]))
        return _scaled(TorchClassifier(hidden=widths, dropout=p["dropout"], weight_decay=p["weight_decay"], lr=p["lr"],
                                       batch_size=p["batch_size"]))
    if key == "single_layer":
        return _scaled(TorchClassifier(hidden=(), dropout=0.0, weight_decay=p["weight_decay"], lr=p["lr"]))
    raise KeyError(key)


def suggest(trial, key: str, group_names: list[str]) -> dict:
    p = {"groups": [g for g in group_names if g == "Opponent-adjusted ratings" or trial.suggest_categorical(f"g::{g}", [True, False])],
         "max_features": trial.suggest_categorical("max_features", [0, 20, 40, 80]),
         "calibration": trial.suggest_categorical("calibration", ["none", "platt"])}
    if key == "logreg":
        p |= {"C": trial.suggest_float("C", 1e-4, 1.0, log=True), "penalty": trial.suggest_categorical("penalty", ["l2", "l1"])}
    elif key == "xgboost":
        p |= {"n_estimators": trial.suggest_int("n_estimators", 50, 800, log=True), "max_depth": trial.suggest_int("max_depth", 1, 5),
              "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.2, log=True), "subsample": trial.suggest_float("subsample", 0.5, 1.0),
              "colsample_bytree": trial.suggest_float("colsample_bytree", 0.2, 1.0),
              "min_child_weight": trial.suggest_float("min_child_weight", 1, 60, log=True),
              "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 50, log=True), "gamma": trial.suggest_float("gamma", 0.0, 5.0)}
    elif key == "decision_tree":
        p |= {"max_depth": trial.suggest_int("max_depth", 2, 8), "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 250, log=True),
              "ccp_alpha": trial.suggest_float("ccp_alpha", 0.0, 0.01), "criterion": trial.suggest_categorical("criterion", ["gini", "entropy"])}
    elif key == "random_forest":
        p |= {"n_estimators": trial.suggest_int("n_estimators", 100, 600, step=100), "max_depth": trial.suggest_int("max_depth", 3, 14),
              "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 120, log=True), "rf_max_features": trial.suggest_float("rf_max_features", 0.05, 0.6)}
    elif key == "mlp":
        p |= {"n_layers": trial.suggest_int("n_layers", 1, 3), "width": trial.suggest_int("width", 8, 128, log=True),
              "dropout": trial.suggest_float("dropout", 0.0, 0.5), "weight_decay": trial.suggest_float("weight_decay", 1e-5, 1e-1, log=True),
              "lr": trial.suggest_float("lr", 1e-4, 1e-2, log=True), "batch_size": trial.suggest_categorical("batch_size", [32, 64, 128, 256])}
    elif key == "single_layer":
        p |= {"weight_decay": trial.suggest_float("weight_decay", 1e-4, 1.0, log=True), "lr": trial.suggest_float("lr", 1e-4, 1e-2, log=True)}
    return p


# --------------------------------------------------------------------------- leak-free fold evaluation

def _select(train: pd.DataFrame, cols: list[str], k: int) -> list[str]:
    """Univariate filter fit on the TRAINING fold only."""
    if not k or k >= len(cols):
        return cols
    X = train[cols].astype(float)
    y = train["home_win"].astype(float)
    corr = X.apply(lambda c: abs(c.corr(y)) if c.notna().sum() > 30 else 0.0).fillna(0.0)
    return list(corr.sort_values(ascending=False).index[:k])


def _platt(p_hist, y_hist, p_new):
    from sklearn.linear_model import LogisticRegression
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    m = LogisticRegression(C=100.0, max_iter=1000).fit(lg(np.asarray(p_hist))[:, None], y_hist)
    return m.predict_proba(lg(np.asarray(p_new))[:, None])[:, 1]


def evaluate_config(data: pd.DataFrame, key: str, p: dict, all_groups: dict, eval_seasons, n_threads=1,
                    report=None, history_seasons=DEV_FOLDS) -> dict:
    """Walk-forward predictions for eval_seasons (train < s). Calibration for season s is fit on
    this configuration's own walk-forward predictions of earlier seasons in `history_seasons`."""
    from . import metrics as M
    cols = sorted({c for g in p["groups"] for c in all_groups.get(g, [])})
    seasons = sorted(set(history_seasons) | set(eval_seasons)) if p["calibration"] == "platt" else sorted(eval_seasons)
    preds = {}
    losses = []
    for i, s in enumerate(seasons):
        tr, te = data[data["season"] < s], data[data["season"] == s]
        use = _select(tr, cols, p["max_features"])
        est = make_estimator(key, p, n_threads).fit(tr[use].astype(float).to_numpy(), tr["home_win"].to_numpy())
        raw = est.predict_proba(te[use].astype(float).to_numpy())[:, 1]
        prior = [x for x in seasons if x < s and x in preds]
        if p["calibration"] == "platt" and prior:
            ph = np.concatenate([preds[x]["raw"] for x in prior])
            yh = np.concatenate([preds[x]["y"] for x in prior])
            cal = _platt(ph, yh, raw)
        else:
            cal = raw
        preds[s] = {"raw": raw, "p": cal, "y": te["home_win"].to_numpy(), "game_id": te["game_id"].to_numpy()}
        if s in eval_seasons:
            losses.append(M.log_loss(preds[s]["y"], cal))
            if report:
                report(len(losses), float(np.mean(losses)))
    return {"seasons": list(eval_seasons), "per_season": dict(zip(eval_seasons, losses)), "mean_log_loss": float(np.mean(losses)),
            "preds": {s: preds[s] for s in eval_seasons}, "n_features_pool": len(cols)}


# --------------------------------------------------------------------------- job management

class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.dir = LR_DIR / job_id
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def meta(self) -> dict:
        f = self.dir / "job.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def save_meta(self, m: dict):
        _atomic_write(self.dir / "job.json", json.dumps(m, indent=2, default=str))

    def control(self) -> str:
        f = self.dir / "control.json"
        return json.loads(f.read_text())["command"] if f.exists() else "run"

    def set_control(self, cmd: str):
        (self.dir / "control.json").write_text(json.dumps({"command": cmd, "at": _now()}), encoding="utf-8")

    def log(self, msg: str):
        with open(self.dir / "log.txt", "a", encoding="utf-8") as fh:
            fh.write(f"{_now()} {msg}\n")

    def status(self) -> dict:
        f = self.dir / "status.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def write_status(self, s: dict):
        try:
            _atomic_write(self.dir / "status.json", json.dumps(s, indent=2, default=str))
        except OSError as exc:   # status is informational; never let it kill the research
            self.log(f"status write skipped: {exc}")


def list_jobs() -> list[dict]:
    out = []
    for d in sorted(LR_DIR.glob("lr*"), reverse=True):
        j = Job(d.name)
        m, s = j.meta, j.status()
        out.append({"job": d.name, "state": s.get("state", m.get("state")), "created": m.get("created_at"),
                    "budget_hours": round(m.get("budget_seconds", 0) / 3600, 2), "elapsed_hours": round(s.get("elapsed_seconds", 0) / 3600, 2),
                    "trials": s.get("trials_total", 0), "finalized": (j.dir / "final.json").exists()})
    return out


def active_job() -> str | None:
    if not LOCK.exists():
        return None
    import psutil
    info = json.loads(LOCK.read_text())
    if psutil.pid_exists(info["pid"]):
        return info["job"]
    LOCK.unlink(missing_ok=True)   # stale lock from a crashed / killed process
    return None


def _lower_priority():
    try:
        import psutil
        p = psutil.Process()
        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
    except Exception:
        pass


def _prepare_data():
    from .data_pipeline import load_feature_store
    from .features import feature_groups
    fs = load_feature_store()
    data = fs[(fs["season"] >= 2016) & fs["completed"] & fs["home_win"].notna()].sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    groups = {k: v for k, v in feature_groups(fs.columns).items() if v}
    return data, groups


def _pick_family(counts: dict, best_hist: dict, total: int, rng) -> str:
    """Guarantee every family >= MIN_SHARE of trials; otherwise favour families whose best
    score improved recently (more trials to promising approaches)."""
    need = [f for f in FAMILIES if counts[f] < max(3, MIN_SHARE * (total + 1))]
    if need:
        return min(need, key=lambda f: counts[f])
    gains = {}
    for f in FAMILIES:
        h = best_hist[f]
        gains[f] = (h[-11] - h[-1]) if len(h) > 11 else (h[0] - h[-1] if len(h) > 1 else 0.01)
    w = np.array([max(gains[f], 0) + 1e-4 for f in FAMILIES])
    return FAMILIES[rng.choice(len(FAMILIES), p=w / w.sum())]


def run_job(job_id: str, progress=print) -> dict:
    import optuna
    import psutil
    import torch
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    job = Job(job_id)
    meta = job.meta
    if active_job() and active_job() != job_id:
        raise RuntimeError(f"Another research job is running: {active_job()}")
    LOCK.write_text(json.dumps({"job": job_id, "pid": os.getpid(), "since": _now()}))
    _lower_priority()
    threads = meta["threads"]
    torch.set_num_threads(threads)
    os.environ["OMP_NUM_THREADS"] = str(threads)
    job.set_control("run")
    meta["state"] = "running"
    meta["resumes"] = meta.get("resumes", -1) + 1
    job.save_meta(meta)
    job.log(f"started (resume #{meta['resumes']}) with {threads} threads, budget {meta['budget_seconds']}s, used {meta.get('used_seconds', 0):.0f}s")
    data, groups = _prepare_data()
    group_names = sorted(groups)
    storage = f"sqlite:///{(job.dir / 'optuna.db').as_posix()}"
    studies = {f: optuna.create_study(study_name=f, storage=storage, direction="minimize", load_if_exists=True,
                                      sampler=optuna.samplers.TPESampler(seed=meta["seed"] + i * 1000 + meta["resumes"], n_startup_trials=8),
                                      pruner=optuna.pruners.MedianPruner(n_startup_trials=6, n_warmup_steps=1))
               for i, f in enumerate(FAMILIES)}
    rng = np.random.default_rng(meta["seed"] + meta["resumes"])
    counts = {f: len(studies[f].trials) for f in FAMILIES}
    best_hist = {f: [t.value for t in studies[f].trials if t.value is not None and t.state.name == "COMPLETE"] or [0.70] for f in FAMILIES}
    for f in FAMILIES:
        best_hist[f] = list(np.minimum.accumulate(best_hist[f]))
    t_start = time.time()
    used0 = meta.get("used_seconds", 0.0)
    state, errors, trial_times = "running", 0, []
    proc = psutil.Process()
    proc.cpu_percent(None)
    try:
        while True:
            elapsed = used0 + (time.time() - t_start)
            cmd = job.control()
            total = sum(counts.values())
            if cmd == "stop":
                state = "stopped"
                break
            if cmd == "pause":
                state = "paused"
                job.write_status(_status(job, meta, studies, counts, elapsed, "paused", proc, trial_times, errors))
                pause_t = time.time()
                while job.control() == "pause":
                    time.sleep(3)
                t_start += time.time() - pause_t            # paused time does not consume the budget
                state = "running"
                continue
            if elapsed >= meta["budget_seconds"] or (meta.get("max_trials") and total >= meta["max_trials"]):
                state = "completed"
                break
            if psutil.virtual_memory().available / 1e9 < MIN_FREE_MEM_GB:
                job.log("low free memory: waiting 30 s before the next trial")
                time.sleep(30)
                continue
            fam = _pick_family(counts, best_hist, total, rng)
            study = studies[fam]
            trial = study.ask()
            t0 = time.time()
            try:
                p = suggest(trial, fam, group_names)
                def report(step, value):
                    trial.report(value, step)
                    if trial.should_prune():
                        raise optuna.TrialPruned()
                r = evaluate_config(data, fam, p, groups, DEV_FOLDS, threads, report=report)
                study.tell(trial, r["mean_log_loss"])
                trial_state = "complete"
            except optuna.TrialPruned:
                study.tell(trial, state=optuna.trial.TrialState.PRUNED)
                trial_state = "pruned"
            except Exception as exc:
                errors += 1
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
                job.log(f"trial error ({fam}): {exc!r}")
                trial_state = "failed"
            trial_times.append(time.time() - t0)
            counts[fam] += 1
            done_vals = [t.value for t in study.trials if t.value is not None and t.state.name == "COMPLETE"]
            best_hist[fam].append(min(done_vals) if done_vals else best_hist[fam][-1])
            meta["used_seconds"] = used0 + (time.time() - t_start)
            job.save_meta(meta)
            st = _status(job, meta, studies, counts, meta["used_seconds"], "running", proc, trial_times, errors)
            st["last_trial"] = {"family": fam, "state": trial_state, "seconds": round(trial_times[-1], 1)}
            job.write_status(st)
    except Exception:
        state = "crashed"
        job.log("CRASH " + traceback.format_exc())
    finally:
        meta["used_seconds"] = used0 + (time.time() - t_start)
        meta["state"] = state
        job.save_meta(meta)
        job.write_status(_status(job, meta, studies, counts, meta["used_seconds"], state, proc, trial_times, errors))
        export_trials(job, studies)
        LOCK.unlink(missing_ok=True)
        job.log(f"ended: {state}")
    if state in ("completed", "stopped") and meta.get("finalize", True):
        try:
            finalize(job_id, progress=progress)
        except Exception:
            job.log("FINALIZE ERROR " + traceback.format_exc())
    return job.status()


def _status(job, meta, studies, counts, elapsed, state, proc, trial_times, errors) -> dict:
    import psutil
    best = {}
    for f, s in studies.items():
        done = [t for t in s.trials if t.value is not None and t.state.name == "COMPLETE"]
        if done:
            b = min(done, key=lambda t: t.value)
            best[f] = {"dev_log_loss": round(b.value, 5), "trial": b.number, "params": b.params}
    per = {f: {"trials": counts[f], "complete": sum(t.state.name == "COMPLETE" for t in studies[f].trials),
               "pruned": sum(t.state.name == "PRUNED" for t in studies[f].trials),
               "failed": sum(t.state.name == "FAIL" for t in studies[f].trials)} for f in studies}
    remaining = max(meta["budget_seconds"] - elapsed, 0)
    avg = float(np.mean(trial_times[-20:])) if trial_times else None
    return {"job": job.id, "state": state, "updated_at": _now(), "elapsed_seconds": round(elapsed), "budget_seconds": meta["budget_seconds"],
            "remaining_seconds": round(remaining), "trials_total": sum(counts.values()), "per_family": per, "best": best,
            "avg_trial_seconds": round(avg, 1) if avg else None,
            "est_remaining_trials": (max(meta["max_trials"] - sum(counts.values()), 0) if meta.get("max_trials")
                                     else int(remaining / avg) if avg else None),
            "cpu_percent_process": proc.cpu_percent(None), "cpu_percent_system": psutil.cpu_percent(None),
            "memory_process_gb": round(proc.memory_info().rss / 1e9, 2), "memory_available_gb": round(psutil.virtual_memory().available / 1e9, 1),
            "threads": meta["threads"], "errors": errors}


def export_trials(job: Job, studies) -> None:
    rows = []
    for f, s in studies.items():
        for t in s.trials:
            rows.append({"family": f, "trial": t.number, "state": t.state.name,
                         # pruned trials only carry a partial (early-fold) score: never compare it to full scores
                         "dev_log_loss": t.value if t.state.name == "COMPLETE" else None,
                         "partial_score_when_pruned": t.value if t.state.name == "PRUNED" else None,
                         "seconds": (t.datetime_complete - t.datetime_start).total_seconds() if t.datetime_complete and t.datetime_start else None,
                         **{f"param_{k}": v for k, v in t.params.items()}})
    pd.DataFrame(rows).to_csv(job.dir / "trials.csv", index=False)


def create_job(hours: float | None = None, minutes: float | None = None, max_trials: int | None = None, threads: int | None = None,
               seed: int = RANDOM_SEED, finalize_after: bool = True) -> str:
    if active_job():
        raise RuntimeError(f"A research job is already running ({active_job()}). Stop it first.")
    budget = (hours or 0) * 3600 + (minutes or 0) * 60
    if budget <= 0 and not max_trials:
        raise ValueError("Give a duration or a trial limit.")
    job_id = datetime.now(timezone.utc).strftime("lr%Y%m%d_%H%M%S")
    job = Job(job_id)
    hw = hardware()
    job.save_meta({"job": job_id, "created_at": _now(), "budget_seconds": budget if budget > 0 else 10 ** 9, "max_trials": max_trials,
                   "threads": threads or hw["default_threads"], "seed": seed, "hardware": hw, "state": "created", "used_seconds": 0.0,
                   "finalize": finalize_after, "dev_folds": DEV_FOLDS, "validation_seasons": VAL_SEASONS, "diagnostic": DIAG_SEASONS,
                   "protocol": __doc__.split("Honest evaluation design")[1].strip()})
    return job_id


def launch_detached(job_id: str, resume: bool = False) -> int:
    """Start the job in its own background process (independent of Streamlit)."""
    py = sys.executable
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000  # CREATE_NO_WINDOW
    out = open(LR_DIR / job_id / "process.log", "a")
    p = subprocess.Popen([py, "-W", "ignore", "-m", "lab.longrun", "resume" if resume else "run", job_id], cwd=str(LAB_ROOT),
                         stdout=out, stderr=out, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    return p.pid


# --------------------------------------------------------------------------- finalisation (one validation look)

def champion_family_config(key: str) -> dict:
    """The production champion's version of a family, expressed in long-run terms."""
    from .features import DEFAULT_GROUPS
    from .training import load_run
    s = load_run()["summary"]
    prm = dict(s["params"]["clf"][key])
    cal = s["calibration"][key]
    base = {"groups": list(DEFAULT_GROUPS), "max_features": 0, "calibration": "platt" if cal == "platt" else "none"}
    if key == "logreg":
        return base | {"C": prm["C"], "penalty": "l2"}
    if key == "xgboost":
        return base | prm | {"subsample": 0.8, "colsample_bytree": 0.6, "min_child_weight": 5, "reg_lambda": 5.0, "gamma": 0.0}
    if key == "decision_tree":
        return base | prm | {"criterion": "gini"}
    if key == "random_forest":
        return base | prm | {"n_estimators": 300, "rf_max_features": 0.3}
    if key == "mlp":
        h = list(prm["hidden"])
        return base | {"n_layers": len(h), "width": h[0], "dropout": prm.get("dropout", 0.3), "weight_decay": prm["weight_decay"],
                       "lr": 1e-3, "batch_size": 128}
    return base | {"weight_decay": prm["weight_decay"], "lr": 1e-3}


def finalize(job_id: str, progress=print) -> dict:
    import optuna
    from .discovery import holm
    job = Job(job_id)
    data, groups = _prepare_data()
    looks = len([1 for _ in open(VAL_LEDGER, encoding="utf-8")]) + 1 if VAL_LEDGER.exists() else 1
    alpha = 0.05 / looks
    storage = f"sqlite:///{(job.dir / 'optuna.db').as_posix()}"
    rows, cfgs = [], {}
    threads = job.meta["threads"]
    rng = np.random.default_rng(0)
    for f in FAMILIES:
        st = optuna.load_study(study_name=f, storage=storage)
        done = [t for t in st.trials if t.value is not None and t.state.name == "COMPLETE"]
        if not done:
            rows.append({"family": f, "status": "no completed trials"})
            continue
        bt = min(done, key=lambda t: t.value)
        p = {k: v for k, v in bt.params.items() if not k.startswith("g::")}
        p["groups"] = sorted({g for g in groups if g == "Opponent-adjusted ratings" or bt.params.get(f"g::{g}", False)})
        if f == "logreg":
            p.setdefault("penalty", "l2")
        champ = champion_family_config(f)
        progress(f"finalize {f}: validation look #{looks}")
        out = {}
        for name, cfg in (("challenger", p), ("champion", champ)):
            dev = evaluate_config(data, f, cfg, groups, DEV_FOLDS, threads)
            val = evaluate_config(data, f, cfg, groups, VAL_SEASONS + DIAG_SEASONS, threads, history_seasons=DEV_FOLDS)
            out[name] = {"dev": dev["mean_log_loss"], "val": float(np.mean([val["per_season"][s] for s in VAL_SEASONS])),
                         "diag": float(np.mean([val["per_season"][s] for s in DIAG_SEASONS])), "preds": val["preds"]}
        y = np.concatenate([out["champion"]["preds"][s]["y"] for s in VAL_SEASONS])
        pc = np.concatenate([out["challenger"]["preds"][s]["p"] for s in VAL_SEASONS])
        pb = np.concatenate([out["champion"]["preds"][s]["p"] for s in VAL_SEASONS])
        ll = lambda p_: -(y * np.log(np.clip(p_, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p_, 1e-6, 1)))
        d = ll(pc) - ll(pb)
        boots = d[rng.integers(0, len(d), (4000, len(d)))].mean(axis=1)
        cfgs[f] = p
        rows.append({"family": f, "trials": len(st.trials), "best_trial": bt.number, "n_groups": len(p["groups"]),
                     "challenger_dev": out["challenger"]["dev"], "champion_dev": out["champion"]["dev"],
                     "challenger_val": out["challenger"]["val"], "champion_val": out["champion"]["val"],
                     "val_delta": float(d.mean()), "val_delta_ci": (float(np.quantile(boots, .025)), float(np.quantile(boots, .975))),
                     "p_one_sided": float((boots >= 0).mean()),
                     "challenger_diag_2025": out["challenger"]["diag"], "champion_diag_2025": out["champion"]["diag"],
                     "dev_to_val_gap": out["challenger"]["val"] - out["challenger"]["dev"]})
    df = pd.DataFrame(rows)
    ok = df["p_one_sided"].notna()
    df.loc[ok, "p_holm"] = holm(df.loc[ok, "p_one_sided"].to_numpy())
    df["passes"] = ok & (df["val_delta"] < 0) & (df["p_holm"] < alpha) & \
        ((df["challenger_diag_2025"] - df["champion_diag_2025"]) <= 0.005)
    df["status"] = np.where(df["passes"], "candidate for shadow tracking", np.where(ok, "not better than champion version", df.get("status")))
    result = {"job": job_id, "finalized_at": _now(), "validation_look": looks, "alpha_after_look_adjustment": alpha,
              "results": json.loads(df.to_json(orient="records")), "best_configs": cfgs,
              "note": "Dev scores were optimised during search (optimistic); validation is the honest comparison, "
                      "and it has been looked at before (look count above)."}
    (job.dir / "final.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    with open(VAL_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"job": job_id, "at": _now(), "look": looks, "families": int(ok.sum())}) + "\n")
    job.log(f"finalized: {int(df['passes'].sum())} family candidates pass (alpha {alpha:.4f})")
    return result


def load_final(job_id: str) -> dict:
    f = LR_DIR / job_id / "final.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(prog="lab.longrun")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--hours", type=float)
    s.add_argument("--minutes", type=float)
    s.add_argument("--max-trials", type=int)
    s.add_argument("--threads", type=int)
    s.add_argument("--foreground", action="store_true")
    for c in ("run", "resume", "pause", "continue", "stop", "finalize"):
        x = sub.add_parser(c)
        x.add_argument("job", nargs="?")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "start":
        jid = create_job(a.hours, a.minutes, a.max_trials, a.threads)
        if a.foreground:
            print(json.dumps(run_job(jid), indent=2, default=str))
        else:
            print(f"Started research job {jid} (pid {launch_detached(jid)}). Watch it on the Long-Run Research page.")
        return
    if a.cmd == "status":
        print(json.dumps(list_jobs(), indent=2, default=str))
        return
    if a.cmd in ("pause", "continue", "stop") and not a.job and not active_job():
        print("No research job is running right now.")
        return
    jid = a.job or active_job() or (list_jobs()[0]["job"] if list_jobs() else None)
    if not jid:
        raise SystemExit("No research job found.")
    if a.cmd in ("run", "resume"):
        run_job(jid)
    elif a.cmd == "pause":
        Job(jid).set_control("pause")
    elif a.cmd == "continue":
        Job(jid).set_control("run")
    elif a.cmd == "stop":
        Job(jid).set_control("stop")
        print(f"Stop requested for {jid}; it finishes the current trial, then runs its validation check.")
    elif a.cmd == "finalize":
        print(json.dumps(finalize(jid)["results"], indent=2, default=str))


if __name__ == "__main__":
    main()
