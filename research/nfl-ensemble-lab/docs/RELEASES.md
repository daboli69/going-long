# Pinned scheduler releases

**Why:** the Windows task "NFL Ensemble Lab - Data Refresh" used to run `lab.scheduler tick` straight
from this development checkout. An in-progress edit could break or slow live pregame forecasts. That
happened on 2026-10-17 at 16:40 UTC. A code edit also changes the Phase 7.3 cache key, so the next
tick cold-rebuilds for about 135 s. The fix is to have the task run a frozen, tested copy of one commit.

Tool: `lab/release.py` (`release_lab.bat <command>` is the same thing). Nothing here changes model
logic, archives, snapshots or the challenger registry.

## Layout

```
releases/                     (gitignored, under the lab root)
  <tag>-<sha7>/               git archive of research/nfl-ensemble-lab at that commit; lab/*.py read-only
    RELEASE.json              commit, build time, test result, prewarm result
    test.log, prewarm.log
  CURRENT.json                active release, its cache slot, previous release (atomic replace)
  history.jsonl               append-only activate / rollback / task-switch log
  run_tick.pyw                stable launcher the task runs (generated; do not edit)
data/cache/phase73_releases/<label>/   per-release Phase 7.3 cache slot
artifacts/scheduler/code_version.json  written by the launcher on every tick (what actually ran)
```

The release shares `data/`, `models/`, `snapshots/` and `artifacts/` with the checkout through
`NFL_LAB_ROOT`. It also uses the checkout's `.venv`. Each release gets its own cache slot through
`NFL_LAB_CACHE73_DIR`, so dev edits and the dashboard never invalidate the scheduler's caches.
Releases built from commits before this feature share `data/cache/phase73` (`build` warns).

The launcher reads `CURRENT.json` at the start of each tick. Switching or rolling back a release
only rewrites that file and never touches the Windows task. If `CURRENT.json` or the release folder
is missing, the launcher logs to `releases/launcher_errors.log` and exits non-zero. It never falls
back to development code.

## Release procedure

```bat
git tag lab-v7.3.1 <commit>                 :: optional; any ref works, tags give readable labels
release_lab.bat release lab-v7.3.1 --dry-run
release_lab.bat release lab-v7.3.1
release_lab.bat status
```

`release` runs these steps in order and stops at the first failure. Nothing goes live unless every
step passes.
1. **build**: `git archive` of the commit, not of the working tree, so uncommitted edits never ship.
2. **test**: the release's own `pytest tests` from the release folder (about 10 to 15 min). The test
   conftest uses a temporary lab root, so tests never touch real data.
3. **snapshot guard**: refuses when a pending pregame snapshot is due within 20 min (`--force` overrides).
4. **lock + prewarm**: takes the scheduler's own `tick.lock`, so a tick that starts meanwhile exits
   at once. It then runs the live-refresh feature assembly twice with the release's code: a cold
   fill, then a warm pass that must recompute nothing. Only cache files are written.
5. **activate**: writes `CURRENT.json` (previous = the old release) and logs to `history.jsonl`.
   `--dry-run` stops before this step.

## Rollback

```bat
release_lab.bat rollback              :: back to CURRENT.previous (instant; its cache slot is normally warm)
release_lab.bat rollback <label>      :: any release that passed its tests
release_lab.bat rollback --prewarm    :: re-warm under the lock first (if its slot was pruned)
```

Emergency fallback to the old behaviour (the task runs the dev checkout again):
`python -m lab.release switch-task development --confirm`. Alternatively, run the `to_development`
line from `task-commands`.

## Switching the Windows task (one time, Travis approves)

`release_lab.bat task-commands` prints the exact PowerShell for both directions. To apply it:

```bat
.venv\Scripts\python.exe -m lab.release switch-task release --confirm
```

This saves the current action to `releases/task_action_backup_<utc>.json` first. Triggers, the
5-minute repetition and `MultipleInstances=IgnoreNew` are unchanged; only the action changes:
`pythonw.exe -W ignore "<lab>\releases\run_tick.pyw"`, working directory `<lab>\releases`. Later
releases only flip `CURRENT.json`, so the task never needs editing again.

Check after switching: `release_lab.bat status` should show `task_mode: pinned`, and
`last_launcher_tick` should update within 5 min. `.venv\Scripts\python.exe releases\run_tick.pyw --check`
prints which package and cache slot a tick would use, without running one.

## Which code is running

- Dashboard, **Live Readiness & Schedule**: an info line "Scheduler code version". It shows either
  "pinned release X (commit …)" or "development checkout (unpinned)".
- `release_lab.bat status`: JSON with current/previous release, every release's test/prewarm
  result, the live task action and the last launcher stamp.

## Caveats

- The release uses the checkout's `.venv`. A `pip install` there affects the pinned release too, so
  re-run `release` after dependency changes.
- The dashboard's Phase 7.3 cache-health table shows the dev slot (`data/cache/phase73`), not the
  release slot.
- `prune --keep 3` deletes older release folders and cache slots (about 120 MB each). It never
  deletes the current or previous release.
