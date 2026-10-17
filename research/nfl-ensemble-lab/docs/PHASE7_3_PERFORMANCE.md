# Phase 7.3: live forecast performance, reliability and data freshness

- **Branch:** `codex/nfl-ensemble-lab`, building on 7457cf0.
- **Unchanged:** every model and archive. Predictions are verified identical (section 6).
- **Scope:** operational changes only, no modelling experiment.

## 1. Baseline profile (`lab/perf.py`, frozen copy of the inputs)
**Feature rebuild: 144.5 s** (the 134 s reported in 7.2 was measured with warmer OS file caches).

| Step | Seconds | Cause |
|---|---|---|
| Phase 7.2 expected lineups | 51.9 | refit the whole snap model (duplicate), per-player loop over every game since 2016, role rates (12 s) |
| Feature-store assembly | 33.0 | `roster_team_games` (~18 s) and QB v2 (~8 s) loops over every historical game |
| Phase 7 snap model | 28.0 | full weekly as-of fit, 232 weeks |
| Phase 5 player model | 27.8 | rebuilt the 1.5M-play table and looped over every historical game |
| Everything else | 3.6 | |

- **Forecast records for a 13-game slate: 14.9 s.** 18 s of profiled time was `role_asof` recomputing the same rolling table 26 times. Each team's live QB view re-read the official report, Sleeper and rosters.
- **Root cause:** every rebuild recomputed every season since 2016, although a live update only changes 2026. The snap model was also fitted twice.

## 2. Caching and incremental processing (`lab/cache73.py`)
- **Season caches** for the five builders (Phase 5 lineups, snap features, 7.2 lineups, QB v2, roster features). The key for season *s* is H(key(s−1), hash of every input row of season *s*, feature-code hash, parameters). Because the hashes chain, any change in season *s* invalidates *s* and every later season, so nothing is reused across a changed historical cutoff. Any change to a feature-building module invalidates everything.
- **Exact-key artifact caches:**
  - snap-model fits, shared by the snap features and the lineups (which removes the duplicate fit);
  - the Phase 5 play table;
  - the 7.2 role rates.
- **RAPM cache key:** it now uses the **number of plays before each weekly cutoff** instead of the cutoff time. A moved future kickoff, with no new plays, no longer forces a 100 s refit. This was verified on frozen data: moving week-12 kickoffs reused the fits, and every feature for earlier games was bit-identical.
- **In-process memoisation:** snap shares (read three times before), `role_asof` states, model bundles (keyed by file time) and the live QB sources (loaded once per batch).
- **Leakage gate:** it runs **without caches** (`cache73.disabled()`), so it still recomputes everything from raw inputs. It also confirms that the uncached recomputation matches the stored, cached store.

## 3. Snapshot timing
**Each new stage snapshot carries a `timing` block:**
- the scheduled time and the deadline;
- the processing start (tick start), the time inputs were ready, and the archive time;
- compute seconds, minutes before kickoff, and timeliness.

`timing` is excluded from the content hash.

| Status | Rule |
|---|---|
| on time | archived within one scheduler interval (5 min) of the scheduled stage time |
| late but valid | archived later than that, but before kickoff |
| missed | no forecast before the stage deadline; recorded and never back-filled |
| unavailable | the game, model or data could not produce a forecast |
| after kickoff | refused: never archived |

- **Ordering:** when a stage snapshot and the daily full refresh are due in the same tick, the light refresh and snapshot run **first** and the full refresh afterwards. A full-refresh failure no longer marks the snapshot as stale.
- **Existing archives:** they are classified from their recorded times: Friday 13 late but valid (279 min, the catch-up at install), HOU–JAX t24h on time. No existing file was modified.
- **First live test (17:00 UTC today):** 7 t24h forecasts were archived at 17:00:48, **46 s after the tick started** (30.3 s rebuild, about 12 s of forecasting). All were on time, and the champion and both challengers were saved together in every one.
- **A bug in my new timing field:** those 7 files record `compute_seconds` ≈ 12 s instead of 46 s, because the scheduler runs as `__main__` and the tick-start value was set in the wrong module object. It's fixed for future snapshots; those 7 archives stay unedited, and the tick log has the true time.

## 4. Injury and QB freshness (`lab/freshness73.py`)
**Propagation per archived report version:** retrieval → first feature build containing it (build ledger) → first archived forecast whose injury source names it.

Example: the 13:00 UTC nflverse version reached its first forecast 30.9 min later, because the next stage was at 13:30. The 10:00 version was superseded before any stage ran.

**Source lead:**
- **Week 6:** nflverse had only 6 game statuses at Friday 17:03 ET and all 159 at Saturday 06:00 ET.
- **NFL.com** collection began Saturday 09:56 ET, so its true lead can only be measured from week 7.
- **Live monitoring** now uses whichever copy of the official report is newer (currently NFL.com). Model inputs still use nflverse, the data the frozen models were built on.

**Cadence:**
- a 5-minute tick plus about 40 s of processing means new information is reflected within about 6 minutes;
- inactives (about 90 minutes before kickoff) reach the 90-, 60- and 30-minute stages on the next tick.

5 minutes is sufficient for these stages. A QB scratch announced inside the last 5 minutes before the final stage's tick would be missed, which is inherent to any polling interval.

## 5. Resilience
| Risk | Handling |
|---|---|
| Interrupted refresh | feature store, games table, validated injuries and status are now written atomically (temp file + replace, bounded retries for OneDrive/antivirus locks) |
| Corrupt caches | an unreadable cache, RAPM fit file or feature store is rebuilt, never trusted |
| Source timeouts and partial downloads | bounded retries, parquet validation before replacing a file, failures logged per source |
| A failed optional source | does not block a snapshot; a failed refresh produces a snapshot marked stale, with the reason |
| Concurrency | the tick lock (with PID check, 40 min staleness); Windows task `IgnoreNew` |
| Sleep/wake | `StartWhenAvailable`; stages whose window passed while asleep are recorded as missed |
| CPU and memory | the tick runs at below-normal priority; peak memory about 1.0–1.5 GB during a stage |

## 6. Predictions unchanged (frozen copy of identical inputs)
**Original Phase 7.2 code** (git worktree of 7457cf0) vs **new code, cold and warm**:
- **Features:** all 1,383 feature columns are identical. Only the `features_built_at` timestamp differs.
- **Predictions:** all 12,012 match within 1e-12: every model's probability and margin, the ensemble, and the champion plus both challengers, for all 2026 games and 2024 week 10. The maximum difference is 7.1e-15.
- **Why 1e-12 is the tolerance:** predicting twice from the *same* input already differs by up to 5e-15 (Random Forest parallel tree averaging), so exact equality isn't achievable even for the old code.
- **Other checks:** the leakage gate passes, and historical training cutoffs are unchanged. No archive was modified; the snapshot hash and read-only checks pass.

## 7. Benchmarks (frozen inputs; `artifacts/phase73/benchmark.csv`)
| Scenario | Before | After |
|---|---|---|
| Feature rebuild, cold caches (code or history changed) | 144.5 s | 134.5 s |
| Feature rebuild, warm, no season affected | 144.5 s | **15.5 s** |
| Feature rebuild, warm, 2026 data changed (typical live update) | 144.5 s | **30.6 s** |
| Rebuild skipped (no input changed) | 0.1 s | 0.1 s |
| Forecast records, full 13-game slate | 14.9 s | **2.7 s** |
| End-to-end stage: light refresh, rebuild, 13 archived forecasts | about 162 s (sum of the components above) | **38.7 s** (13 of 13 on time) |
| Full daily refresh (data already fresh) | n/a | 18.1 s |
| Production, 17:00 UTC t24h stage | n/a | **46 s from tick to archive** |

## 8–9. Dashboard and prospective tracking
- **Operations panel** on Live Readiness:
  - last scheduler run, processing state and last feature build;
  - on-time, late, missed and pending stages;
  - scheduled vs actual archive times and processing durations;
  - injury propagation and the NFL.com/nflverse lead;
  - source failures, cache health, the integrity audit and the next scheduled forecasts.
- **Prospective tracking:** all three versions archive together. No archived game has finished yet, so no results exist; scoring runs automatically after each refresh.
- **Unchanged:** the 128-game rule, the Holm correction and the 10 upset hypotheses (hash checked).

## Remaining risks
- **The scheduler runs from the development checkout.** A syntax error I introduced while editing broke one tick (16:40 UTC, nothing due). Running the scheduler from a pinned release copy would remove this risk.
- **A cold rebuild still takes about 135 s,** and can reach about 235 s if the RAPM must also refit. That happens only after a feature-code change or a change to historical data. Pre-warming after any code change (as done today at 16:54) avoids slow stages.
- **Memory:** a stage peaks at about 1.5 GB of RAM.
- **NFL.com's lead over nflverse is unmeasured until week 7.**
