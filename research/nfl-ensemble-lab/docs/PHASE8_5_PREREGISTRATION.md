# Phase 8.5 pre-registration: combined upset angles on new data (overnight run)

**Written 2026-10-18, before any outcome in the new data was examined.** This study is local to the lab only. No model,
challenger or GOING change.

## New data (provenance in `artifacts/phase85/provenance.json`)
- **ASB:** the AusSportsBetting `nfl.xlsx`, downloaded manually by Travis to `data/raw/market/aussportsbetting_nfl.xlsx`. It has
  opening and closing spreads, totals and moneylines. Its timestamp class is T2 for the opening line (time unrecorded) and T3 for
  the closing line.
- **Historical play-by-play:** nflverse files for 1999–2014 in `data/raw/history/`, with SHA-256 hashes recorded. These are kept
  separate so the champion's pipeline cannot read them.
- **Season data:** rest, divisional flag and observed weather from nflverse `games.csv`, for all seasons.

### Data checks (outcome-free, run before the study)
- **Matching:** ASB games are matched to `games.csv` by date and teams.
- **Opening-line coverage:** a season enters the study only if ≥ 90% of its games have an ASB opening spread. The rule is
  fixed now.
- **Agreement with SBR:** for 2016–21, ASB opening spreads are compared with SBR opening spreads. If the median absolute
  difference exceeds 1 point, ASB opening lines are treated as unreliable and Family E is not run.

## Common definitions
- **Line favourite:** the side favoured by the opening spread (pick'em openers excluded; ties in the result excluded).
- **m (movement):** favourite opening spread − favourite closing spread. Positive = moved toward the underdog.
- **p_close:** the no-vig closing moneyline probability for the line favourite. If the closing moneyline is missing,
  Φ(closing spread / 13.5) is used.
- **Outcome:** the line favourite won.
- **Team rating R:** a uniform, simple as-of rating computed identically for every season from play-by-play (not the
  champion's features).
  - Formula: offensive EPA/play − defensive EPA/play allowed, season-to-date, blended with last season's final value:
    (n·current + 4·previous)/(n + 4), with n = games played.
  - Plays counted: runs and passes with EPA, excluding kneels and spikes.
- **Test:** each angle is fitted as logit P(fav won) = a + b·logit(base) + c·angle. It gets a one-sided likelihood-ratio test in
  the stated direction, where "favours the dog" means c < 0. Continuous angles are standardised on the discovery seasons.

## Family E: edge beyond the closing price (base = p_close)
- **Discovery:** 2006–2015. **Confirmation:** 2016–2025.
- **Angles:**

  | ID | Angle | Favours the dog when |
  |---|---|---|
  | E1 | m (movement toward the dog) | m is large |
  | E2 | Key-number crossing: the favourite's spread moved from > 3 to ≤ 3, or from > 7 to ≤ 7 (0/1) | flagged |
  | E3 | Spread/moneyline disagreement: the spread moved toward the dog by ≥ 1, but the favourite's no-vig moneyline probability rose (0/1) | flagged |
  | E4 | Total moved down by ≥ 1.5 points from open to close (0/1) | flagged |
  | E5 | m × 1[favourite opening spread ≥ 7] | positive |
  | E6 | m × 1[week ≤ 4] | positive |
  | E7 | Rest advantage: dog rest − favourite rest, in days | large |
  | E8 | Low closing total ≤ 41 (0/1) | flagged |
  | E9 | Rating disagreement: z(R_dog − R_fav) | the stats like the dog more than the price does |
  | E10 | Recent form: dog's last-3-games EPA margin minus its season-to-date EPA margin, minus the same for the favourite | positive |
  | E11 | Divisional game (0/1) | flagged |
  | E12 | Home underdog (0/1) | flagged |
  | E13 | Wind ≥ 15 mph, from `games.csv` observed wind (0/1) | flagged |

- **E13 caveat:** observed wind is a proxy for the forecast, so E13 is labelled forecast-proxy.

## Family C: champion × market (base = p_close)
- **Discovery:** 2018–2021. **Confirmation:** 2022–2025, the first market-movement data for those seasons.
- **Angles:**

  | ID | Angle | Favours the dog when |
  |---|---|---|
  | C1 | The champion's out-of-fold probability favours the line underdog (0/1) | flagged |
  | C2 | logit(champion p for the line favourite) − logit(p_close) (continuous; negative favours the dog, tested with a positive c) | the champion is more bearish than the close |
  | C3 | m × C1 | positive |

## Replication R1 of Phase 8.4 S2 (pre-declared, single test)
- **Test:** S2 exactly as in Phase 8.4: base = champion probability, angle = z(m), with m standardised using the frozen 2018–21
  scale.
- **Data:** ASB movement for 2022–2025, seasons never used for movement before.
- **Pass:** one-sided p < 0.05.

## Decision rule
- **Discovery:** an angle is carried forward if its nominal one-sided discovery p < 0.10 with the stated sign. Carried angles are
  written to `artifacts/phase85/carried.json` before the confirmation seasons are scored. The code enforces this order.
- **Confirmation:** Holm within each family across the *carried* angles. An angle passes if its adjusted p < 0.05 and it has the
  stated sign in at least half of the confirmation seasons.
- **Descriptive only:** the flat-bet return on the dog at the actual closing moneyline is reported for passing angles, using real
  ASB closing odds only. A permutation p-value (10,000 shuffles of the angle within season) is also reported for every
  confirmation test.
- **Scope:** a passing angle becomes a prospective hypothesis only (ESPN archive, 128 games). Nothing is promoted. Failing angles
  are not re-tried with other thresholds.

## Robustness of 8.4 S2 (descriptive, not decisive)
- Bootstrap 95% CI.
- Breakdowns by favourite size (< 3, 3–6.5, ≥ 7), week group (1–4, 5–12, 13+), season, and with or without key-number crossings.

## Not allowed
- Adding angles or changing thresholds after any discovery result is seen.
- Scoring confirmation seasons for angles that were not carried.
- Using 2026 for anything but prospective evaluation.

## Amendment A (2026-10-18, after outcome-free data checks, before any outcome was computed)

### What the data checks found
- **2006–2013:** ASB has one line per game, stored in the "Open" columns. It matches the nflverse *closing* spread (median absolute
  difference 0.0, against 1.0 for genuine openers), so it is a closing line. **There is no line-movement data before 2014.**
- **2014–2024:** ≥ 96% of games have both opening and closing spreads and moneylines.
- **2025:** 72.6% coverage, so it fails the ≥ 90% rule and is excluded from every movement test.
- **Closing lines:** ASB closing lines agree with nflverse closing lines (median absolute difference 0.0).

### Revised families (the angles themselves are unchanged)
- **p_close definition (all families):** the nflverse closing no-vig moneyline probability, falling back to
  Φ(nflverse closing spread / 13.5). The ASB closing moneyline is used only for flat-bet returns on the movement family.
- **EM (movement): E1–E6.**
  - Line favourite = the ASB opening favourite.
  - Discovery 2014–2018, confirmation 2019–2024.
  - Seasons need ≥ 90% of games with ASB opening and closing lines.
  - The SBR-agreement check still applies.
  - Caveat: the main movement effect was examined on SBR 2016–21 in Phases 8.1 and 8.4.
- **ES (static and football): E7–E13.**
  - Line favourite = the closing favourite (nflverse spread; pick'em excluded).
  - Discovery 2006–2015, confirmation 2016–2025.
  - E8 uses the nflverse closing total.
  - These seasons were never examined for these angles, and 1999–2014 play-by-play supplies E9 and E10 for the old seasons.
- **C (champion × market):** opening-favourite orientation as before. Discovery 2018–2021, confirmation 2022–2024.
- **R1:** S2 replication on 2022–2024 (2025 excluded by the coverage rule).

### Decision rule
Holm applies within each family (EM, ES, C). Everything else in the decision rule is unchanged.
