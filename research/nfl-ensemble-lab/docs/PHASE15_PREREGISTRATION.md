# Phase 15 pre-registration: point-in-time QB knowledge, market-implied QB values, sealed vault, program discipline

Written 2026-10-26, before any point-in-time data was built or any result computed. Local lab only. No change to the
champion, the challengers, the scheduler, the Windows task or GOING. Commits stay local.

**Motivation (Phase 14).** Historically, the QB model was told who actually started. Its closing-line-value signal (r = 0.54)
may partly be hindsight about timing. Its scale was also too large: QB changes averaged 4.6 points against the market's 2.5.

## Sources (free; coverage is reported, not assumed)
- **Wayback Machine captures of `espn.com/nfl/injuries`.** These carry third-party capture timestamps. Coverage check: 310
  of 365 days in 2021. Raw captures are stored in `data/raw/wayback15/` (git-ignored), fetched politely at about one request
  every 2 seconds.
- **nflverse official injury-report rows with `date_modified`,** 2018 to 2024. The 2025 file has no timestamps.
- **Coverage only, not used for decisions:**
  - ESPN team depth-chart pages (about 24 captured days a year);
  - VegasInsider and Covers odds pages (about 85 and 59 days a year). Too sparse to time historical lines.

## Windows (US Eastern time)
For a game on date d:
- **T_open:** 20:00 on the last Sunday at or before d minus 2 days. Assumed: lines open Sunday night for the next week.
- **T_mid:** 12:00 on the last Wednesday at or before d minus 1 day, before the week's first practice report.
- **T_kick:** kickoff.

## When a QB change counts as public
A QB change counts as public at time T if the previous starter is listed Out, Doubtful, Injured Reserve or Suspended either:
- in the latest ESPN injuries capture taken in the 72 hours before T; or
- in an official report row with `date_modified` at or before T.

Notes:
- A capture time is only an upper bound on when the news became public, so this classification is conservative.
- Changes that never appear in these sources (benchings, coach's decisions) are "not visible". They count as public only at
  kickoff.
- **Point-in-time QB change:** Δ_w = Δ (the Phase 14 margin change) if the change was public at T_w, otherwise 0. A model at
  T_w would still assume the previous starter.

## A. Historical re-run with point-in-time knowledge (2018 to 2024 QB-change games with opening and closing lines; one look; Holm across A1 to A3)
| Test | Measure | Phase 14 value (with hindsight) |
|---|---|---|
| **A1** | CLV correlation using Δ_open | 0.54 |
| **A2** | correlation of Δ_open with the opening-to-closing move | 0.33 |
| **A3** | correlation of Δ_open with the market QB adjustment at the open | 0.22 |

- Each test is one-sided for a correlation above 0.
- **Hindsight share** = 1 minus (point-in-time correlation ÷ Phase 14 correlation), with bootstrap intervals.
- Everything is also reported by visibility class: public by the open, public between open and midweek, public after
  midweek, and not visible.

## B. Market-implied QB values and scale (fitted on 2015 to 2024 only)
- **Label:** the closing market QB adjustment, meaning the closing margin minus the market-rating expectation from Phase 14.
  It is signed by team for each QB-change game.
- **Scale c:** fitted by Deming (errors-in-variables) regression of the label on the Phase 14 performance change.
  - Error-variance ratio = market noise variance (from residuals in non-QB-change games) ÷ performance-change error
    variance (from the posterior variances of θ, multiplied by D²).
- **Hierarchical market-implied values:** label = Σ sign × (v_new − v_old) + noise, with v_qb ~ N(c × performance value,
  s_v²). s_v is chosen by marginal likelihood on 2015 to 2024. Δ_comb is the posterior mean of the change. QBs never seen in
  a market move fall back to c × performance.
- **Public comparison:** correlation with FiveThirtyEight's net QB adjustment (via nfelo) on the same games, 2015 to 2024.

## C. Sealed vault: 2025 season
- 2025 QB-change games are not read by any fitting or development code.
- `python -m lab.phase15 vault` runs once and only after the analysis code is committed. The output records that commit's
  hash, and the command refuses to run again.
- **V1 (primary):** in 2025 QB-change games, the correlation of Δ_comb (at kickoff) with the closing market QB adjustment is
  above 0 (one-sided), **and** the Deming slope's 95% interval includes 1.
- **V2:** the correlation of the point-in-time Δ_comb at the open with the opening-to-closing move is above 0.
- Holm across V1 and V2. FiveThirtyEight and nfelo agreement in 2025 is reported.

## D. Where the model may be first (prospective, 2026 onward)
- Forecasts are frozen at T_open and T_mid, using only information public at that time.
- **Evidence for each game:** x = sign(forecast minus line at freeze time) × (closing line minus line at freeze time) ÷ 3,
  clipped to [−1, 1].
- Scored by a new e-process monitor, **M7**.

## E. Program discipline
- **Futility bound for every monitor:** a Robbins normal-mixture confidence sequence for bounded x in [−1, 1]
  (sub-Gaussian, σ = 1; ρ set for n = 100; α = 0.05). A monitor stops for futility once the upper bound falls below its
  minimum meaningful effect:
  - 0.005 for the log-loss monitors (M1 to M4 and M6);
  - 0.02 for M5;
  - 0.02 for M7.
- **Program stopping rule:** if no monitor has reached e ≥ 20 by the end of the 2026 regular season (week 18), the QB and
  late-news program is marked "paused: no prospective evidence" in the ledger, and effort moves to the next ranked item.
  Futility stops are recorded in the ledger when they happen.

## Not allowed
- Changing windows, the public-knowledge rule, the label, c, s_v or the vault rules after any result is seen.
- Touching 2025 before the vault command.
- Promoting anything without prospective evidence and Travis's approval.
