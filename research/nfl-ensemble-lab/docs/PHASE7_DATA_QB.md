# Phase 7: 2026 data expansion, QB intelligence and live prediction quality

Branch `codex/nfl-ensemble-lab`. Champion unchanged (**v20261016_212540**). GOING was inspected read-only.

## 1. Inventory (dashboard: **Data Coverage & Gaps**; code: `lab/inventory.py`)
Roles:
- **model:** a historically valid pregame input.
- **model\*:** 2026 coverage is incomplete.
- **monitoring:** shown on dashboards only.

| Source | Seasons | Latest 2026 week | Role | In GOING |
|---|---|---|---|---|
| nflverse play-by-play | 2015–2026 | 6 | model | yes |
| nflverse play participation | 2016–**2025** | none (not published) | model\* | yes (also lacks 2026) |
| PFR snap counts | 2015–2026 | 6 | model (basis of the Phase 7 snap model) | yes |
| Official injury reports (nflverse) | 2015–2026 | 6 | model\* (no verified timing for 2025 or 2026 weeks 1–5) | yes |
| NGS / PFR advanced / FTN | 2016+ / 2018+ / 2022+ | 5–6 | model | partly |
| Depth charts | 2026 | n/a | monitoring (static, ignores injuries) | no |
| **NFL.com injury report** (new) | live | 6 | monitoring (official) | no |
| **nflverse weekly rosters** (new) | 2026 | 6 | monitoring | yes |
| **Sleeper players** (new) | live | n/a | monitoring | yes (ids / ADP) |
| ESPN injuries / scoreboard / transactions, Open-Meteo | live | n/a | monitoring | scoreboard only |

**GOING findings:**
- GOING uses nflreadpy (pbp, participation, snaps, rosters, injuries, NGS, player stats), Sleeper and ESPN.
- Its `football_context.json` also reports 2026 participation as unavailable.
- It has nothing the lab lacks except a paid odds feed (`PARLAY_API_KEY`), which was not used.

**Checked, not available for free:**
- nflverse `stats_player_week_2026`
- nflverse `pbp_participation_2026`
- an official machine-readable game-day inactives list
- current play-calling or scheme data beyond FTN

## 2. New sources (`lab/extra_sources.py`)
Each source is fetched on every light refresh, archived with its retrieval time (a new file only when
the content changes) and logged to `data/source_health.jsonl`.

| Source | URL | First check (2026-10-17 13:56 UTC) |
|---|---|---|
| NFL.com injury report | https://www.nfl.com/injuries/ | 374 rows, 28 teams, week 6, **100% gsis match** via weekly rosters |
| nflverse weekly rosters | https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_2026.parquet | 15,327 rows, through week 6 (ACT/RES/INA/DEV) |
| Sleeper players | https://api.sleeper.app/v1/players/nfl | 2,573 rostered players. Called at most daily, per Sleeper's guidance |

None of the three feeds a model, because none has a historical as-of archive.

## 3. Baltimore QB conflict: resolved
- **The projection was right.** Both the official report (NFL.com and nflverse, weeks 5 and 6) and Sleeper list Lamar Jackson **Out** (ankle, did not practice). Lamar was INA on the week-5 weekly roster, and Sleeper has Huntley at depth 1.
- **The conflict came from static sources.** The ESPN depth chart and the nfldata listing still name Lamar, and the lab's label treated any disagreement as a conflict.
- **Fix (`live._qb_certainty`):** an alternative QB whom the official report lists Out/Doubtful no longer creates a conflict. The explanation is shown instead.
- **Scope:** a report only applies to its own week. Future-week games still show "uncertain" when static sources disagree.

## 4. QB projection v2 (`features.project_starters_v2`, group "Phase 7: QB projection v2")
- **Rule:** project the team's primary starter back (most dropbacks over its last 8 games) when he missed the previous game and this game's verified report **lists him** with a status other than Out/Doubtful.
- **First draft:** "not listed Out" was right only 24–31% of the time on 2016–22, because benched, IR and traded starters never appear on reports.
- **Stricter rule (chosen on 2016–22 starter agreement, not on outcomes):** right 61–65% of the time on 94 flagged games. The old rule was right 28–37% on those games.
- **Agreement:** the share of games where both projected starters started (diagnostic only):

  | Seasons | Old rule | v2 |
  |---|---|---|
  | 2018–22 | 0.812 | 0.822 |
  | 2023–24 | 0.761 | 0.768 |
  | 2025 | 0.757 | 0.764 |
  | 2026 weeks 1–5 | 0.772 | 0.772 |

- **Live example:** Chicago, week 6. The champion assumes Tyson Bagent; v2 expects Caleb Williams back (Questionable, full practice). The dashboard flags the game "uncertain".
- **Champion inputs are unchanged:** v2 adds new columns only.

## 5. Snap-based player model (`lab/snap_model.py`, group "Phase 7: snap-based player model")
- **What it is:** a labelled **substitute** for the 2026 play participation file, which is missing.
- **How it works:** a ridge regression of team-game offensive EPA per play on verified PFR snap shares (offense players vs opposing defense players), weighted by plays.
- **As-of fits:** one per week, using the current season plus prior seasons at weights 0.6 / 0.35. The penalty (λ = 30) was chosen once on 2016–17 → 2018.
- **Lineups and injuries:** the same rules as Phase 5.
- **Limitations:** it is coarser than RAPM. It sees how much each player played per game, not per play, so players who always share the field cannot be separated.
- **Status:** current through 2026 week 5. The Phase 5 model is 2025-only, so it is stale for 2026.
- **Sanity check (dev, descriptive):** the pregame net correlates 0.31–0.46 with the actual margin across 2017–22.

## 6. Development-only challenger test (`lab/study7.py`)
**Declared before results:**
- **Candidates:** the champion's groups plus the new group(s).
- **Settings:** the champion's own hyperparameters with no search, and an equal-weight six-model ensemble.
- **Rule:** gain > 0 on 2019–21 and ≥ 0 on 2022.
- **Seasons used:** none from 2023–2025.

| Candidate | Gain 2019–21 | Gain 2022 | Qualifies |
|---|---|---|---|
| QB v2 | −0.00002 | +0.0021 | no |
| Snap model | +0.0023 | +0.0018 | yes |
| QB v2 + snap model | **+0.0039** | +0.0014 | yes |

- **Registered:** the qualifying candidate with the larger 2019–21 gain, as frozen shadow challenger **v20261017_142546_p7_qb_snap** (trained with the champion's procedure, `set_current=False`).
- **Leakage found and fixed before commit:** the real-data leakage gate (`lab/readiness.py`) flagged the
  first version. Perturbing one 2022 game changed snap-model features for earlier games, because the ridge
  penalty was scaled by the mean play count over *all* games, including future ones.
  - **Fix:** a fixed scale (`PLAY_SCALE = 63`) plus a regression test.
  - **Result:** the gate now passes with 0 leaking columns of 1,242 checked.
  - **Re-test:** the identical pre-declared test was re-run (table above).
  - **Registry:** the leaky challenger (v20261017_140409) was withdrawn and recorded under `withdrawn` in the
    registry; no snapshot ever used it.
- **Holm correction:** now runs across 2 challengers. All three candidates are in the registry's `considered` trail.
- **Caveats:**
  - The gains are small (≈0.3–0.6% of log loss).
  - The 2022 check is not perfectly clean: the QB v2 rule was designed from starter agreement on 2016–22, though not from outcomes.
  - Only 128+ prospective games decide, and nothing is promoted.

## 7. Error analysis (`lab/errors.py`, descriptive)
Based on the champion's walk-forward out-of-sample predictions for 2018–2026.
- **The six models make the same mistakes.** Residual correlations are 0.97–0.999, so the effective number of independent models is **1.02 of 6**. All six are wrong together in 23% of games; the ensemble is wrong in 36%. Agreement between the models is not independent confirmation.
- **Wrong QB projection (post-hoc):** log loss is higher when a projected starter did not start: 0.642 vs 0.625 in development, 0.654 vs 0.629 in 2025, 0.707 vs 0.650 in 2026. It is not higher in 2023–24 (0.613 vs 0.637). The direction is mostly consistent, but the buckets are small.
- **Missing data (the main 2026 gap):**
  - The champion had **no verified injury report for any 2025 game or any 2026 game in weeks 1–5**, because report timing exists only once the lab has archived it. Injury features and the QB-out logic never fired in those games.
  - The lab archive started in October 2026. From week 6, 12 of 14 games have reports for both teams.
  - The Phase 5 player model is over 14 days stale for every 2026 game.
- **Disagreement:** high model disagreement coincided with *lower* log loss, because disagreement is larger in lopsided games. It is not a usable uncertainty signal in its raw form.
- **Over/under-confidence:** no stable pattern. The gaps by confidence band change sign between seasons (2025 60–70%: −0.11; 2023–24 70–80%: −0.08; 2023–24 >80%: +0.11), which is consistent with noise at these sample sizes.

## 8. Live weekend audit (`lab/audit7.py`, run 2026-10-17 ~14:05 UTC; completed work only)
- **Ticks:** 140 scheduler ticks (02:38 → 14:00 UTC) with 0 errors; the longest gap was 5 minutes.
- **Events:** 17 done and 25 missed. Every missed event (13 early-week stages and 12 daily refreshes) was due before the scheduler's first tick. None was back-filled.
- **Snapshots:** 28 snapshots (14 early, 13 Friday, 1 t24h for HOU–JAX). All were made before kickoff, all are read-only, their hashes match the ledger, and there were no overwrites.
- **Models:** every snapshot uses champion v20261016_212540, and the Phase 5 challenger is present in each.
- **Hypotheses:** the 10 upset hypotheses are unchanged (file hash recorded).
- **Scoring:** no archived game has kicked off yet. The Thursday game, SEA–DEN, finished before archiving began. **No prospective result exists yet.**

## Commands
```
python -m lab.cli errors        # rebuild the error analysis
python -m lab.cli audit         # live weekend audit
python -m lab.cli phase7-test   # re-run the development-only challenger test
```
