# Phase 12 pre-registration: circadian advantage in night games (Smith, Efron, Mah & Malhotra, SLEEP 2013)

**Written 2026-10-26, before any of these numbers was computed.** Local lab only. No model, challenger, scheduler or GOING
change.

## The claim being tested
- **Source:** Smith RS, Efron B, Mah CD, Malhotra A. SLEEP 2013;36(12):1999–2001. doi:10.5665/sleep.3248.
- **Their sample:** 1970–2011, 106 games between Pacific-time and Eastern-time teams kicking off at or after 8 pm ET.
- **Their finding:** the Pacific team beat the closing point spread 70–36, by +5.26 ± 1.33 points per game (t = 3.95). In 293
  matching 1 pm ET day games there was no edge (+0.16 ± 0.80).
- **Proposed mechanism:** at an 8 pm ET kickoff, the Pacific team's body clock reads 5 pm, near its daily performance peak.

## Data
- **Source:** nflverse `games.csv`, 2012–2025, regular season and playoffs, using the closing `spread_line`.
- **Sample:** every season is after the paper's sample. 2014 onward is after publication, when the market could have learned
  of it.
- **Exclusions:**
  - neutral-site games;
  - games with no spread;
  - pushes against the spread (reported, then excluded).

## Definitions (fixed now)
- **Pacific (WC) teams:** home stadium in the Pacific time zone that season: SF, SEA, LV/OAK, LAC/SD, and LA from 2016 (the
  Rams were in St. Louis, Central time, through 2015).
- **Eastern (EC) teams:** home stadium in the Eastern time zone: ATL, BAL, BUF, CAR, CIN, CLE, DET, IND, JAX, MIA, NE, NYG, NYJ,
  PHI, PIT, TB and WAS.
- **Arizona** (Mountain time, no daylight saving) is excluded, as in the paper.
- **Night game:** kickoff at or after 20:00 ET (`gametime`). **Day control:** kickoff at or before 13:05 ET.
- **x** = WC points − EC points + WC handicap, where the handicap is the closing spread from the WC team's side (positive when
  the WC team is the underdog). x > 0 means the WC team beat the spread.

## Primary test R (single look)
- **Sample:** WC-vs-EC night games, 2012–2025.
- **Test:** one-sided t-test that mean x > 0, plus a one-sided Wilcoxon signed-rank test as a check. The paper's own method.
- **Passes if** the t-test p < 0.05 **and** mean x > 0 in both halves (2012–18 and 2019–25).
- **Reported:**
  - mean x and its SE;
  - the WC against-the-spread record;
  - results for the post-publication subset (2014–25);
  - the day-control mean x, and a night-vs-day χ² as in the paper.

## Secondary (reported, not decisive)
- **B1, beyond the champion (2018–25):** in WC-vs-EC night games, a logistic regression of WC-won on logit(champion's
  out-of-fold WC probability), testing the intercept for WC > 0. This checks whether the champion already captures it. It does
  not use the Phase 3 body-clock features.
- **B2, generalised time-zone gap:** all night games between teams whose home time zones differ, with the angle = time-zone
  hours the west team is behind (1–3). Test whether x rises with the gap (one-sided slope > 0). Arizona is counted as Mountain
  time.

## If R passes
- Register prospectively: 2026+ WC-vs-EC night games are scored live. The sample is small, about 5–7 a season, so this is
  a multi-season track.
- Separately pre-register a shadow challenger: the champion plus the existing Phase 3 body-clock features, restricted to
  this interaction. No promotion without prospective evidence and Travis's approval.

## If R fails
Recorded as rejected for the current market, meaning the effect is gone or priced in. It will not be re-tested with other
time cut-offs or team definitions.
