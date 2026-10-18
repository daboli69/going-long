# Phase 8.5: combined upset angles on new data (local lab only)

- **Pre-registration:** `docs/PHASE8_5_PREREGISTRATION.md` (9c958fc), plus Amendment A (c5facce). Both were pushed before any
  outcome was computed.
- **Runner:** `lab/upsets85.py` (6193cca). **Results:** `artifacts/phase85/`.
- **Dashboard:** Blind-spot research → "Combined angles, new data (8.5)".
- **Run:** 2026-10-18 03:52 UTC, 52 seconds. The tests are deterministic, so a rerun reproduces identical numbers. It was started
  before Travis asked to start it himself; only this one look exists.

## New data
- **AusSportsBetting `nfl.xlsx`:** 5,428 of 5,431 games matched for 2006–25. SHA-256 is in `provenance.json`; the file is local
  only and never committed.
  - 2006–13 has a single line per game, which is the closing line.
  - Real opening lines run 2014–24 (≥ 95% coverage). 2025 is excluded at 73% coverage.
  - Agreement with SBR openers on 1,543 games: median difference 0.5 points.
- **nflverse play-by-play 1999–2014** (16 files, about 265 MB, hashes recorded). It feeds a uniform as-of team rating (R) and
  recent form for every season.

## Discovery: which angles were carried forward (threshold p < 0.10 in the stated direction)
- **Base:** the closing price.
- **Seasons:** EM 2014–18, ES 2006–15, C 2018–21.

| Family | Angle | Games | One-sided p | Carried |
|---|---|---|---|---|
| EM | E1–E6 (movement, key numbers, spread/moneyline disagreement, total drop, big-favourite and early-season movement) | 1,287 | 0.44–0.94 | none |
| ES | E7 rest advantage | 2,665 | 0.13 | no |
| ES | E8 low total | 2,665 | 0.11 | no |
| ES | E9 stats rate the dog above its price | 2,665 | 0.41 | no |
| ES | E10 recent form | 2,665 | 0.69 | no |
| ES | E11 divisional game | 2,665 | 0.38 | no |
| ES | E12 home underdog | 2,665 | 0.89 | no |
| ES | E13 wind ≥ 15 mph | 2,665 | 0.058 | **yes** |
| C | C1 champion favours the line underdog | 1,051 | 0.29 | no |
| C | C2 champion more bearish than the close | 1,051 | 0.15 | no |
| C | C3 movement toward a dog the champion also likes | 1,051 | 0.008 | **yes** |

## Confirmation: scored once, Holm per family
| Angle | Seasons | Games | One-sided p | Permutation p | Seasons with predicted sign | Flagged dogs: won vs implied by close | Flat-bet return at close | Verdict |
|---|---|---|---|---|---|---|---|---|
| E13 wind | 2016–25 | 2,747 | 0.44 | 0.51 | 5/10 | 32.8% vs 32.7% (204 bets) | +0.2% | **Rejected** |
| C3 movement × champion likes the dog | 2022–24 | 852 | 0.29 | 0.31 | 2/3 | 56.6% vs 51.5% (76 bets) | +3.5% | **Rejected** |

C3 had too few bets to mean anything. Under the rules, neither angle is re-tried.

## R1: Phase 8.4 S2 replication on seasons never used for line movement (2022–24)
- **Result: passed.**
  - 852 games, one-sided p = 0.00001.
  - Coefficient −0.41 per SD (2018–21: −0.29), with the predicted sign in 3 of 3 seasons.
  - For a 65% favourite, a +1 SD move toward the dog raises the upset chance from 31.9% to 41.4%.
- **It is still not a betting edge.** Games moved 1.5+ points toward the dog (195) saw the dog win 44.1%. The closing price
  implied 45.3% and the champion 42.4%. The close already contains the information.
- **The champion is unchanged.** The prospective S2P registration from 8.4 stays as it is.

## S2 robustness (2018–21, descriptive)
- **Bootstrap:** 95% CI for the coefficient is −0.46 to −0.15; 100% of resamples are negative.
- **Every subgroup is negative:**
  - favourite size: < 3, 3–6.5, ≥ 7;
  - with and without key-number crossings;
  - all week groups (weakest weeks 5–12, −0.14).
- **By season:** 2018 is ≈ 0 (+0.06); 2019–21 are −0.30 to −0.44.

## Conclusion
- **Market-free angles:** none of the 13 market-free or static angles identifies upsets beyond the closing price. That covers
  rest, totals, divisional games, home dogs, wind, team-rating disagreement and recent form, across 20 seasons including 10
  never examined before.
- **Movement against the close:** movement-based angles also add nothing beyond the closing price.
- **The one durable finding is now replicated out of sample.** When the line moves toward the underdog, that underdog is more
  dangerous than the **champion** thinks. The champion lacks the late-week information the market absorbs. The fix would be to
  use the market, not a new football metric; that would be a separate, pre-registered model change, and none is made here.
- **For betting:** there is no evidence of an angle that beats the closing line. Value, if any, exists only for bets placed
  before the move.
