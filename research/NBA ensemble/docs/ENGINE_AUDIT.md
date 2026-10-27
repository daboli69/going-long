# Player simulation engine: data and assumptions audit, 2026-10-27

Scope: one player-level engine whose simulations produce King of the Court (KOTC) leader odds, player-prop distributions and game margins/totals. This audit covers what raw data exists for free, what's missing, and which assumptions the engine must make. Nothing here has been fitted or scored.

## Raw sources checked

| Source | What it is | Coverage | Access | Status |
|---|---|---|---|---|
| SportsDataverse `nba_stats_possessions_{S}` | Every possession with the 10 players on court, shot/FT/rebound/turnover counts, points, start/end clock | 2015-16 to 2026-27 (all checked years return 200); 2025-26: 278,341 rows, 1,400 games | Free GitHub release, no login | Usable. 99.6% of 2025-26 rows have lineups inferred from play-by-play (`pbp_fallback`); 0.4% from quarter boxes. Lineups are the producer's reconstruction, not official stint logs. |
| SportsDataverse `nba_stats_game_lineups_{S}` | On-court fives at each play-by-play action | Same | Free | Usable as a cross-check of the possession file. |
| SportsDataverse `nba_stats_pbp_{S}` | Raw NBA play-by-play events, substitutions included | Same | Free | Usable for substitution timing and assist/rebound attribution. |
| SportsDataverse `nba_crosswalk` | NBA person/game IDs ↔ ESPN IDs | Same | Free | Required: possession files use NBA IDs, while boxes and injury reports use ESPN IDs. Exact-ID joins only. |
| ESPN player and team boxes (already cached) | Official minutes, starters, DNP flags | 2020-21 to 2026-27 | Free | In use. Exactly 5 starters per team-game in every season. |
| Official NBA injury-report PDFs (already cached) | Status by player, timestamped | One version per game day, 2021-22 to 2025-26 (816 days) | Free | In use. **Not every version:** we kept only the latest report before each day's first tipoff minus 1 hour. Reports were hourly until 2025-12-21 and every 15 minutes after, so the full history is roughly 15,000 PDFs (about 600 MB). |
| PBPStats API (`api.pbpstats.com`) | Derived possession/lineup stats | Responds (HTTP 200) | Free | A cross-check only; it shares the same NBA upstream. |
| NBA CDN live JSON (`cdn.nba.com`) | Official live play-by-play/box | HTTP 403 to plain requests | Blocked | **Not used.** Getting around the block would mean spoofing browser headers, which I won't do. |
| ESPN athlete API | Position, current age | Current only | Free | No birth date, so historical age is current age minus elapsed seasons, ±1 year. Position comes from the roster. |

## Closing lines (grading only)

- **Player props:** no free, no-login historical archive exists. The Odds API covers props from May 2023 on paid plans only, BigDataBall and The Odds Gap sell them, and Kaggle needs an account. **Prop closing-line value will not be measured,** and nothing will stand in for it.
- **Game spreads/totals:** the old Sportsbook Review season files (2007-08 to 2022-23, the last one partial) survive only as Internet Archive captures, with no stated license. If they can be retrieved, they cover 2021-22 and part of 2022-23, which is enough to grade game projections against closing lines for one season. That is a lead, not yet verified. No free source was found for 2023-24 onward.
- **KOTC selection counts:** not public. Prize-share outputs stay scenarios.

## Assumptions the engine has to make

1. **Information time.** Decisions happen one hour before the day's first tipoff. A game's result is usable 12 hours after its tipoff; official boxes are final by then. Codex's KOTC simulator uses 36 hours, so any Tuesday comparison against it reruns the engine with 36 hours.
2. **Injury report.** Until every version is collected, availability uses one report per day. Late scratches after it are invisible, and that error is counted, not hidden.
3. **Lineups are inferred.** Per-possession usage and rates come from producer-inferred fives. Possessions whose reconstructed minutes disagree with official box minutes by more than 2 minutes per player-game are flagged and excluded from rate fitting, and the share is reported.
4. **Age** is approximate (±1 year). Position comes from ESPN's roster (G/F/C).
5. **Team consistency.** Simulated player points must sum to team points, and player minutes to 5 × game length. Rebounds can't exceed simulated missed shots, and assists can't exceed made field goals by teammates.
6. **Blowouts.** Starters' minutes depend on the simulated margin. The pregame spread comes from the engine itself, not the market.
7. **Overtime.** Drawn from the historical rate, with possessions and minutes scaled up.
8. **Every night counts as a slate.** All regular-season game days are graded, not only Tuesdays. Codex's simulator refuses non-Tuesdays by design, so comparisons against it are Tuesday-only.

## What is already in place

- Box scores and starters (2020-21 to 2026-27), parsed injury reports (one per day, 2021-22 to 2025-26), team schedules and results (2014-15 on).
- Baselines to beat: rotation-minutes KOTC (Codex simulator), the learned minutes model (`reports/minutes_v1`), the frozen Ridge score model for margins/totals, and the six-model winner ensemble with its strength and injury shadows.
- No player-prop model exists yet. The baseline is defined in the plan.
