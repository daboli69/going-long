# Referee trends: results

Rule and hashes: `docs/REFS_PREREG.md` (committed before any referee statistic, then two dated amendments), `docs/refs_rule.json`, `docs/refs_prereg_ledger.jsonl`. Raw numbers: `docs/refs_results.json`. Code: `lab/refs.py`, `scripts/refs_run.py`. Screen: the Refs tab.

## Sources and coverage

- Referee, closing spread, result, total: `data/raw/games.csv` (nflverse schedule). Every completed regular-season game from 2015 to 2025 has a referee except one in 2021. For 2026, 65 of 120 completed games have one (weeks 1 to 5 only), because the file's referee column was last filled in early. That is why Smith shows 34 games since 2024, not the 36 or 37 the tweet implies.
- Penalties: nflverse play-by-play, one flagged penalty per play (a play with two fouls counts once). Crew by position: `data/raw/officials.parquet`.
- Not used: the official gamebooks. They are PDFs on NFL.com, their terms were not checked, nothing was scraped. A reconciliation against them is not done.
- Crew check: `games.csv` referee against the officials table's Referee, 2,910 games in both. 17 disagree on the last name (15 are the same crew swapped between two games, 2 are one referee misspelled). Many more differ only in spelling (Ron and Ronald Torbert), so four spelling variants were merged (Brad and Bradley Rogers, Ron and Ronald Torbert, John Perry to John Parry, Adrian Hall to Adrian Hill). Only the head referee is analyzed.

## The tweet, rebuilt

| Claim since 2024 | Tweet | Rebuilt |
| --- | --- | --- |
| Smith home ATS | 26-8-2 | 27-7-0 (34 games) |
| Home favorites up to 4 | 6-0 | 6-0 |
| Away minus home penalties, 2025 | 30 | 27, first of 17 referees |

The difference in home ATS is the two pushes and one game: the tweet used lines that make two games pushes, and the schedule file here has 34 games with a referee, not 36. The pattern is real in the data. Exact test against the league rate: p = 0.0008. Because he was picked as the extreme case, the check that matters is how often the most extreme of the 17 referees with 20 or more games sits this far from the league by luck alone: 1% of 1,000 shuffles.

It is still not a claim. His home teams went 35-52 against the spread in 2018 to 2023 (92 games), then 27-7 from 2024. A referee effect would not flip like that. The record since 2024 is the same window the tweet chose, so it is not independent evidence.

## Tests

- Discovery (2015 to 2023): 78 referee-by-measure ATS and over tests, Holm corrected. The best, Clay Martin with home favorites (2 of 18), has an adjusted p of 0.14. Nothing passes.
- Penalties: Poisson ridge model with plays as exposure, closing line, game state and a referee-by-home term; max-statistic permutation. The smallest adjusted p is 0.43. Nothing passes. Counts are only slightly overdispersed (variance 1.16 times the mean).
- Confirmation (2024 to 2026): Smith's home ATS is the only result that clears the corrected test (adjusted p 0.036), and it fails the rule because it does not appear in discovery. Clete Blakeman and Shawn Hochuli show about 4% extra home-side penalties (one-sided p 0.025 and 0.05), also with nothing in discovery.
- Year to year: a referee's home ATS rate correlates 0.05 with the next season's (95% range -0.14 to +0.25, 157 pairs, 26 referees). The penalty gap correlates -0.10 (-0.24 to +0.05).
- Market: using each referee's earlier home-cover tendency as a belief, 1,439 games in 2016 to 2021, the belief does not predict the open to close move (correlation -0.03) and scores worse than the league rate (log score gain -0.008, range -0.015 to -0.001). The data holds open and close lines only, not the line at the assignment announcement, so the announcement test is not possible here.

## Pass rule: no real referee effect found

No referee-measure pair passed discovery, so none can be claimed, including Smith. The year-to-year correlations are indistinguishable from zero.

## Concerns

- The negative binomial named in the request is replaced by Poisson ridge plus permutation (Amendment 1); the ridge constant is fixed, not tuned.
- The first model run returned zeros for every referee (a scaling bug), fixed and documented as Amendment 2. The fix was made after seeing that result.
- Name merging and the 2026 referee gap were found after seeing coverage; the merges do not change any conclusion.
- Counts are one flagged penalty per play, so double fouls and offsetting penalties are undercounted, and declined penalties are not separated.
- The tweet's numbers were not available in source form, only as quoted.
- No assignment for next week's games is in the schedule file yet, so the hashed prospective file for Monday night cannot be written today.
