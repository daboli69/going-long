"""Pinned scheduler releases (lab/release.py): export, launcher, activation, rollback and the snapshot guard.
Uses a throwaway git repo inside the temporary lab root; never touches the real Windows task."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from lab import release as R


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A tiny git repo shaped like GOING: research/nfl-ensemble-lab/lab/... with a scheduler stub."""
    root = tmp_path / "going"
    lab_root = root / "research" / "nfl-ensemble-lab"
    (lab_root / "lab").mkdir(parents=True)
    (lab_root / "lab" / "__init__.py").write_text("")
    (lab_root / "lab" / "cache73.py").write_text(
        "import os\nfrom pathlib import Path\nDIR = Path(os.environ.get('NFL_LAB_CACHE73_DIR', 'shared'))\n")
    (lab_root / "lab" / "config.py").write_text(
        "import os\nfrom pathlib import Path\nLAB_ROOT = Path(os.environ['NFL_LAB_ROOT'])\n")
    (lab_root / "lab" / "scheduler.py").write_text(
        "import json, os, sys\nfrom pathlib import Path\n"
        "if __name__ == '__main__':\n"
        "    out = Path(os.environ['NFL_LAB_ROOT']) / 'tick_ran.json'\n"
        "    out.write_text(json.dumps({'file': __file__, 'argv': sys.argv[1:], 'cache': os.environ['NFL_LAB_CACHE73_DIR'],\n"
        "                               'version': 'v1'}))\n")
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)
    git("init", "-q")
    git("-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "v1")
    git("tag", "lab-v1")
    monkeypatch.setattr(R, "LAB_ROOT", lab_root)
    monkeypatch.setattr(R, "RELEASES_DIR", lab_root / "releases")
    monkeypatch.setattr(R, "CURRENT", lab_root / "releases" / "CURRENT.json")
    monkeypatch.setattr(R, "HISTORY", lab_root / "releases" / "history.jsonl")
    monkeypatch.setattr(R, "LAUNCHER", lab_root / "releases" / "run_tick.pyw")
    monkeypatch.setattr(R, "CACHE_ROOT", lab_root / "data" / "cache" / "phase73_releases")
    return root, lab_root, git


def _commit_v2(root, lab_root, git):
    p = lab_root / "lab" / "scheduler.py"
    p.write_text(p.read_text().replace("'v1'", "'v2'"))
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "v2")
    git("tag", "lab-v2")


def _pass(label):
    R._update_meta(label, tests={"passed": True, "summary": "ok"}, prewarm={"ok": True})


def test_build_exports_commit_not_working_tree(repo):
    root, lab_root, git = repo
    (lab_root / "lab" / "scheduler.py").write_text("BROKEN uncommitted edit")
    label = R.build("lab-v1", progress=lambda m: None)
    rel = R.release_dir(label)
    assert label.startswith("lab-v1-")
    assert "BROKEN" not in (rel / "lab" / "scheduler.py").read_text()
    m = R.meta(label)
    assert m["own_cache_slot"] and m["tags"] == ["lab-v1"] and m["tests"] is None
    assert not os.access(rel / "lab" / "scheduler.py", os.W_OK)          # frozen
    assert R.build("lab-v1", progress=lambda m: None) == label              # idempotent


def test_activate_requires_tests_and_prewarm(repo):
    label = R.build("lab-v1", progress=lambda m: None)
    with pytest.raises(RuntimeError):
        R.activate(label, progress=lambda m: None)
    _pass(label)
    cur = R.activate(label, progress=lambda m: None)
    assert cur["release"] == label and cur["previous"] is None
    assert R.LAUNCHER.exists() and json.loads(R.CURRENT.read_text())["cache_dir"].endswith(label)


def test_launcher_runs_release_code_with_shared_root_and_own_cache(repo):
    root, lab_root, git = repo
    label = R.build("lab-v1", progress=lambda m: None)
    _pass(label)
    R.activate(label, progress=lambda m: None)
    (lab_root / "lab" / "scheduler.py").write_text("raise SystemExit('dev code must not run')")
    env = {k: v for k, v in os.environ.items() if not k.startswith("NFL_LAB")}
    r = subprocess.run([sys.executable, str(R.LAUNCHER)], cwd=str(root), env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    ran = json.loads((lab_root / "tick_ran.json").read_text())
    assert Path(ran["file"]).resolve().is_relative_to(R.release_dir(label).resolve())
    assert ran["argv"] == ["tick"] and ran["cache"] == str(R.cache_dir(label)) and ran["version"] == "v1"
    stamp = json.loads((lab_root / "artifacts" / "scheduler" / "code_version.json").read_text())
    assert stamp["release"] == label


def test_rollback_returns_to_previous_release(repo):
    root, lab_root, git = repo
    v1 = R.build("lab-v1", progress=lambda m: None)
    _pass(v1)
    R.activate(v1, progress=lambda m: None)
    _commit_v2(root, lab_root, git)
    v2 = R.build("lab-v2", progress=lambda m: None)
    _pass(v2)
    R.activate(v2, progress=lambda m: None)
    assert R.current()["previous"] == v1
    cur = R.rollback(progress=lambda m: None)
    assert cur["release"] == v1 and cur["previous"] == v2
    hist = [json.loads(x) for x in R.HISTORY.read_text().splitlines()]
    assert [h["action"] for h in hist] == ["activate", "activate", "rollback"]


def test_rollback_refuses_untested_release(repo):
    label = R.build("lab-v1", progress=lambda m: None)
    with pytest.raises(RuntimeError):
        R.rollback(label, progress=lambda m: None)


def test_release_dry_run_changes_nothing_live(repo, monkeypatch):
    label = R.build("lab-v1", progress=lambda m: None)
    _pass(label)
    monkeypatch.setattr(R, "snapshot_conflict", lambda: pd.DataFrame())
    monkeypatch.setattr(R, "prewarm", lambda lbl, progress: {"ok": True})
    held = []
    from lab import scheduler
    monkeypatch.setattr(scheduler, "acquire_lock", lambda: held.append(1) or True)
    monkeypatch.setattr(scheduler, "release_lock", lambda: held.append(0))
    out = R.release("lab-v1", dry_run=True, progress=lambda m: None)
    assert out == {"label": label, "dry_run": True} and held == [1, 0]
    assert not R.CURRENT.exists()


def test_release_blocked_by_imminent_snapshot(repo, monkeypatch):
    label = R.build("lab-v1", progress=lambda m: None)
    _pass(label)
    monkeypatch.setattr(R, "snapshot_conflict", lambda: pd.DataFrame({"event_id": ["2026_06_X_Y|t60"]}))
    with pytest.raises(RuntimeError, match="snapshot due"):
        R.release("lab-v1", progress=lambda m: None)


def test_snapshot_conflict_window(monkeypatch):
    from lab import scheduler
    now = pd.Timestamp("2026-10-18 16:00", tz="UTC")
    plan = pd.DataFrame({"event_id": ["a", "b", "c", "d"], "action": ["snapshot", "snapshot", "live", "snapshot"],
                         "status": ["pending", "pending", "pending", "done"],
                         "time_utc": [now + pd.Timedelta(minutes=10), now + pd.Timedelta(hours=1), now, now],
                         "deadline_utc": [now + pd.Timedelta(minutes=40)] * 4})
    monkeypatch.setattr(scheduler, "upcoming_events", lambda hours, now: plan)
    assert list(R.snapshot_conflict(now)["event_id"]) == ["a"]


def test_task_mode_and_commands():
    assert R.task_mode({"Arguments": '-W ignore "C:\\x\\releases\\run_tick.pyw"'}) == "pinned"
    assert R.task_mode({"Arguments": "-W ignore -m lab.scheduler tick"}) == "development"
    cmds = R.task_commands()
    assert "run_tick.pyw" in cmds["to_release"] and "lab.scheduler tick" in cmds["to_development"]
    assert all(R.TASK_NAME in c for c in cmds.values())


def test_switch_task_cli_requires_confirm():
    with pytest.raises(SystemExit) as e:
        R.main(["switch-task", "release"])
    assert "confirm" in str(e.value)


def test_cache73_respects_release_slot(tmp_path):
    env = dict(os.environ, NFL_LAB_CACHE73_DIR=str(tmp_path / "slot"))
    r = subprocess.run([sys.executable, "-c", "from lab import cache73; print(cache73.DIR)"], env=env,
                       cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True)
    assert Path(r.stdout.strip()) == tmp_path / "slot"
