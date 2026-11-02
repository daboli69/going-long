# Referee trends: pre-registration (2026-11-02)

Written and hashed before any referee statistic is computed. The only things seen so far: the column list of `data/raw/games.csv`, `data/raw/officials.parquet` and `data/raw/play_by_play_*.parquet`, and referee coverage by season. The tweet that prompted this (Shawn Smith, head official for Monday night: home teams 26-8-2 against the spread since 2024, home favorites up to -4 6-0, 30 more penalties on away teams in 2025) is a claim to check, not a result.

## Sources

- Referee, closing spread (`spread_line`, home margin expected, positive when home is favored), final `result` (home minus away), `total` and `total_line`: `data/raw/games.csv` (nflverse schedule). Regular season only, seasons 2015 to 2026, completed games with a referee name.
- Crew by position: `data/raw/officials.parquet` (nflverse officials table). Used to cross-check the `Referee` name in `games.csv`. Only the head referee is analyzed; umpire, line judge and the rest are not analyzed because there is no sample large enough per crew.
- Penalties: nflverse play-by-play, plays with `penalty` = 1 and a `penalty_team`, one per play (a play with two fouls counts once; that undercount is stated, not corrected). Exposure is all offensive plays in the game (run and pass plays).
- Open and close spreads: `data/raw/market/sbr_lines.parquet`, for the seasons it covers. It has no timestamp at the moment a referee is announced (Thursday or Friday), so open to close is a proxy for "the market reacts to the assignment" and is labeled as one.
- Official gamebooks are not used: they are PDFs on NFL.com, their terms were not checked and nothing is scraped. A reconciliation against them is listed as not done.

## Measures

`home_ats`: home team covers (result > spread_line); pushes dropped. `home_fav_ats`: same, only games with 0 < spread_line <= 4. `over`: total > total_line, pushes dropped. `pen_home`, `pen_away`, `pen_gap` (home minus away penalties).

## Estimates

- Raw record with exact Clopper-Pearson 95% interval.
- Shrunken rate: (wins + m x league rate) / (games + m), with m from the method of moments on the between-referee variance of raw rates in the discovery seasons, clipped to 5 to 1000.
- Penalties: Poisson regression with a log link, ridge penalty, on one row per team per game, with the log of plays as an offset (done as rate with play weights). Terms: home, the team's own closing line, the team's mean score differential in the game (game state), a referee term and a referee x home term. Ridge on the referee terms is the stand-in for a random effect; the other terms are left almost unpenalized. This replaces the negative binomial: overdispersion (Pearson) is reported, and inference uses permutation, which does not depend on the count distribution. The referee x home coefficient is the referee's extra home-side penalty rate, as a percent.

## Tests

- Discovery seasons 2015 to 2023, confirmation seasons 2024 to 2026.
- ATS and over measures: exact two-sided binomial test of each referee (at least 20 games, 10 for home favorites) against the league rate in the same window. Holm correction across every referee x measure test in the window.
- Penalties: 200 permutations, seed 11, shuffling referee labels across games within each season and week, refitting the model each time; a referee's p is the share of permuted fits with an absolute referee x home coefficient at least as large; Holm across referees.
- The tweet's claim: Smith's record since 2024 is tested exactly, and a permutation (1,000 draws, seed 12, shuffling referees within week) asks how often the most extreme referee with at least 20 games shows a home ATS rate as far from the league as Smith's does, because Smith was picked as the extreme case after the fact.
- Year to year: for every referee with at least 12 games in two consecutive seasons, the Pearson correlation between the two seasons' home ATS rate, and between the two seasons' mean penalty gap, with a 95% interval from resampling referees (2,000 draws, seed 13).
- Market: with `sbr_lines` seasons, each game gets a belief from the referee's earlier games only (shrunken home cover rate minus the league rate, at least 20 earlier games, else zero). Report the correlation of belief with the close minus open home spread move, and the log score of a cover probability of league rate plus belief against the constant league rate on the same games, with a game-bootstrap 95% range (2,000 draws, seed 14).

## Pass rule

A referee effect on a measure is claimed only if all hold: (1) the discovery Holm p is below 0.05; (2) in the confirmation seasons the referee's rate is on the same side of the league and the one-sided exact p is below 0.05, with at least the minimum games; (3) the year-to-year correlation for that measure has a 95% interval above zero. Otherwise the report says no real referee effect was found. A referee with too few discovery games cannot be claimed, whatever the tweet says, and Smith's 2024-onward record is not an independent test of anything. Subgroup and rate language stays descriptive. No bet suggestions, no staking, no sizing.

## Prospective record

`freeze_week(week)` writes, once, before kickoff, a hashed file of the week's known referee assignments with the tab numbers shown for them (shrunken home cover rate, shrunken extra home-side penalty percent). Games without an assigned referee are not written. A scoring step reports, after the games, the cover and penalty-gap result against the league-average baseline. A second call never rebuilds the file and a changed file fails its hash.

## Amendment 1 (2026-11-02, before any referee statistic)

The penalty test above says per-referee permutation p-values with Holm. With 200 permutations the smallest possible p is 1/201 = 0.005, and with 10 or more referees Holm would need p below 0.005 times the count, so nothing could ever pass. Replaced by the max-statistic permutation: a referee's adjusted p is the share of the 200 permuted fits in which the largest absolute referee x home coefficient across all referees (at least 20 games each in the window) is at least as large as this referee's observed coefficient. That controls the chance of any false claim across all referees at once and needs no Holm step. The confirmation check for penalties uses the per-referee share of permuted fits with a coefficient at least as large in the same direction (one-sided), referees at least 20 games. The ridge penalty is a fixed constant of 0.002 on the referee terms and 0.002/900 on the control terms; it was not tuned on outcomes.

## Amendment 2 (2026-11-02, solver scaling only)

The first run returned a referee x home coefficient of exactly zero for every referee. Cause: the control columns (home, closing line, score differential) were scaled by 30 with the raw line and differential, which left the optimizer stuck at its starting point. Fixed by scaling the line and differential by 1/6 and the control columns by 10, so the control penalty is 0.002/100, and by tightening the solver tolerance to 1e-12. The ridge constant 0.002 on the referee terms, the permutation counts and seeds, and every pass condition are unchanged. This amendment was written after the zero result was seen; it changes numerical scaling only and no threshold.
