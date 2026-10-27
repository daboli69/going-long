# Player simulation engine: frozen test plan, 2026-10-27

Committed before any engine component is fitted or scored. Read with `docs/ENGINE_AUDIT.md`. The engine is built one stage at a time. Each stage has to pass its own gate before the next stage builds on it. Travis approves any promotion to a default.

## Seasons and timing

- Test seasons (ending year): **2024, 2025, 2026**, regular season only. Each test season trains only on earlier seasons: rates and usage from 2016 on, anything that uses injury reports from 2022 on.
- Decision time: the day's first tipoff minus 1 hour. Results are usable 12 hours after tipoff (36 hours in any Tuesday comparison against Codex's simulator).
- 2027 (the current season) is never used to fit or choose anything. It's prospective only.

## Stages, inputs and gates

Each gate is a paired bootstrap that resamples whole game nights (2,000 draws, seed 20261027). Pass means the 95% interval for the improvement excludes zero in the right direction, the improvement holds in at least 2 of 3 test seasons, and no secondary metric gets meaningfully worse (more than 1% relative).

| Stage | What it adds | Primary metric | Baseline it must beat |
|---|---|---|---|
| 1. Availability | P(plays) for every rostered player, from injury status, status history over recent days, games missed and return timing | Log loss of plays/doesn't play on rostered players | Status-only lookup: historical play rate by official status, 0 for unlisted inactive players |
| 2. Minutes | Two-part minutes (plays × minutes-if-plays) with a full distribution from quantile models, starters, vacated minutes, and blowout risk from the engine's own pregame spread | CRPS of minutes | `reports/minutes_v1` learned model (normal around its mean and SD) |
| 3. Possessions and usage | Team possessions per 48 from both teams' pace; each player's share of team shots, free throws and turnovers from on-court possession data | CRPS of team possessions; log loss of per-player shot share | Season-to-date pace average; season-to-date box usage |
| 4. Rates | Per-possession scoring, rebounding and assist rates with partial pooling by position, age band and role (empirical-Bayes conjugate first; a full PyMC/NumPyro model only if it beats that) | CRPS of PTS, REB, AST given actual minutes and possessions | Raw season-to-date per-minute rates |
| 5. Joint simulation | Team-consistent simulation: shots allocated by usage, rebounds from missed shots, assists from teammates' makes, shared pace, overtime, blowout-dependent minutes | Nightly leader log score | Stage 4 rates combined independently (no team constraints) |

## Outputs graded once the engine is assembled

- **Nightly PRA leader**, every game night of the three test seasons (about 490 nights): mean log of the probability on the actual leader(s), reliability of leader probabilities in bins, and top-pick hit rate. On Tuesdays only, it's also compared against rotation-minutes KOTC through Codex's unchanged simulator. That rerun covers every Tuesday of the three seasons Codex's history can supply.
- **Props** (PTS, REB, AST, PRA, every player who played): CRPS, PIT histograms with a KS uniformity statistic, coverage of the 80/90/98% intervals, and how often outcomes exceed the predicted 90th, 95th and 99th percentiles (targets 10/5/1%). Baseline: season-to-date per-minute rate × rotation minutes, with Poisson noise.
- **Games:** margin and total CRPS and MAE, home-win log loss and Brier, compared on identical games against the frozen Ridge score model and the winner ensemble's stacked probability. Consistency check: mean simulated team points minus mean of summed player points must be within 0.5.
- **Closing lines:** if the Internet Archive copy of the 2021-22 Sportsbook Review game file is retrievable, record the engine's MAE against the closing spread/total and against final results, alongside the market's own MAE. 2021-22 is outside the test seasons, so this comparison is descriptive. No prop closing lines exist for free; that comparison is reported as unavailable.

## Rules

- One stage changes at a time; every stage keeps its predecessor's outputs for comparison.
- Raw files are archived with SHA256 and source URL. The possession archive's lineup source (`pbp_fallback` versus `quarter_box`) is kept per row.
- No market prices are model inputs. No invented results, odds or selection counts. $0 spend. Codex's package stays byte-identical.
- A failed gate is recorded, and the stage is either dropped or replaced under a new committed plan, never re-tuned against the same test seasons.
