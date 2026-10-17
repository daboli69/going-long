# Phase 6: live football intelligence and prospective learning (2026-10-17)

## Live sources implemented (`lab/live.py`)
| Source | Endpoint (free, no login) | Role | Notes |
|---|---|---|---|
| Official NFL injury report + practice participation | nflverse `injuries_{season}.parquet` | **Model input** (the only availability source the models were trained on) | Re-checked about every 20 minutes on game days; every changed version archived with download time |
| Depth charts (projected starters) | nflverse `depth_charts_{season}` (daily ESPN snapshots) | Monitoring | QB1 changes logged |
| ESPN injuries (incl. IR, PUP, *inactive / coach's decision*) | `site.api.espn.com/.../nfl/injuries` | Monitoring | Archived only when content changes |
| ESPN transactions (IR placements/activations, practice-squad elevations, signings, releases, trades) | `site.api.espn.com/.../nfl/transactions` | Monitoring | Append-only, de-duplicated, classified |
| ESPN scoreboard (live kickoff time, status) | `site.api.espn.com/.../nfl/scoreboard` | Scheduling | Moves stage events when kickoffs change; skips postponed games |
| Schedule, lines, listed QBs | nfldata `games.csv` | Schedule + benchmark | Lines stored at snapshot time (timestamped) |

- **No untrained distributions:** monitoring sources never change model features. They drive the
  readiness labels, conflict warnings, the debate timeline and the snapshot's `live_context_monitoring_only`.
- **Official game-day inactive lists:** no free machine-readable source exists. ESPN-reported inactives
  are captured and labelled *partial*.
- **Starting QB "confirmation":** no free source exists. The lab reports whether its projection, ESPN's
  depth-chart QB1, nfldata's listed QB and ESPN status agree ("consistent", not "confirmed").
- **Changes log** (`data/raw/archive/live/changes.jsonl`): every status change in the official report,
  ESPN injuries and depth-chart QB1, with detection time.
- **Missing data:** missing information is never read as "healthy". Failed sources keep their last
  valid copy and show their age.

## Schedule (`lab/scheduler.py`, America/New_York, DST-aware)
| Kind | Times | Action | Run window before "missed" |
|---|---|---|---|
| Daily | 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 ET | full incremental refresh | 3 h |
| Game day | every :00/:30 from first kickoff − 3 h to last kickoff | live refresh (+ light rebuild only if a model input changed) | 30 min |
| early_week | Tuesday 12:00 ET of game week (≥ 30 h before kickoff) | refresh + snapshot | until the next stage |
| friday | Friday 18:00 ET before kickoff (not Thursday games) | refresh + snapshot | until the next stage |
| t24h | kickoff − 24 h | snapshot | until the next stage |
| t3h | kickoff − 3 h | live refresh | until t90 |
| t90 | kickoff − 90 min | live refresh (inactives) + snapshot | until t60 |
| t60 | kickoff − 60 min | live refresh + snapshot | until final |
| final | kickoff − 30 min | live refresh + final snapshot | until kickoff − 5 min |

- **Windows task:** the existing task "NFL Ensemble Lab - Data Refresh" (no new task) now runs
  `pythonw -m lab.scheduler tick`.
  - Triggers: every 5 minutes all day, plus at logon.
  - Settings: start-when-available after sleep/restart; a second copy never starts while one is
    running; 30-minute time limit.
  - The scheduler keeps its own lock file (with stale-process recovery) and runs at below-normal priority.
- **Execution:** each tick runs any due events once. Several due events merge into one refresh and one
  snapshot pass.
- **Missed events:** recorded with a reason, e.g. "no scheduler run while the event window was open (PC
  off or asleep?)" or "scheduler ran but the event did not complete". Nothing is back-filled after kickoff.
- **Moved kickoffs:** a kickoff moved per ESPN marks the old-time stage events `superseded` and plans new ones.
- **Load:**
  - A tick with nothing due takes about 1 second.
  - A live refresh takes about 4 seconds; the light feature rebuild about 55 seconds, and it is skipped
    when no model input changed (the player model is cached until new plays exist).
  - A full refresh takes about 2–2.5 minutes.

## Snapshots and readiness
- **Stage snapshots:** one per (game, stage), exclusive-create and read-only. Each is written only if
  completed more than 5 minutes before the current kickoff. It carries the stage label, scheduled time,
  six model probabilities and margins, champion, challengers (with per-model probabilities), QB and
  injury availability, the market line at snapshot time, the live context and the data-cutoff timestamps.
- **Readiness (Live Readiness & Schedule page):** shows per game the latest full and live refresh, injury
  report (complete / incomplete), each QB (consistent / uncertain / changed / unavailable), each lineup
  (current / stale), inactives (not yet expected / ESPN-reported partial / unavailable), player-model
  staleness, missing or stale sources, the next refresh, the next snapshot (stage) and time to kickoff.
  These are labels only; there are no confidence scores.

## Prospective evaluation
`prospective.score()` runs after every refresh and never edits snapshots. Per stage it reports:
- log loss, Brier, ECE, calibration, accuracy and margin MAE (vs the spread at snapshot);
- favorites vs underdogs and injury completeness;
- paired log-loss differences on identical games: each of the six models, the Phase 5 hypothesis
  challenger, experimental adjustments and the market line vs the champion, plus each stage vs final.

The 10 frozen upset hypotheses are evaluated only on final-stage games archived after their
registration. Promotion rules are unchanged (≥ 128 games, paired CI below zero, never automatic).

## Debate
- **Tab 6:** players, matchups and uncertainty.
- **New Timeline section:** each archived stage's six model probabilities, margin, QB flags and injury
  loads, plus detected changes and transactions for both teams since the first snapshot.

## First real run (2026-10-17 02:38 UTC)
- The 21:00 ET daily refresh ran, and 13 Friday-stage snapshots were archived (inside their window).
- 25 earlier events were marked missed ("before scheduler tracking started").
- The Windows task has run the tick every 5 minutes since, with 0 errors.
- Live readiness flagged BAL's QB as **uncertain**: the lab's rule projects last game's starter (Tyler
  Huntley), while ESPN's depth chart and nfldata list Lamar Jackson.

## Limitations and manual setup
- **No manual setup** is needed beyond staying logged in. The task runs only while you are logged in to
  Windows; sleeping or powering off causes missed stages, which are reported.
- **Inactives:** official lists are not available. Partial ESPN-reported inactives are monitoring only.
- **nflverse refresh cadence:** the official-report file is refreshed upstream on nflverse's schedule.
  The lab can only be as fresh as that file (its age is shown).
- **2026 player ratings** stay stale until nflverse publishes 2026 participation data.
- **Champion unchanged:** v20261016_212540.
