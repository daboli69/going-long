# Phase 15 results: how much of the QB signal was hindsight

- **Pre-registration:** `docs/PHASE15_PREREGISTRATION.md` (ec12b3b2).
- **Analysis code:** committed before any result (a0541daa). A type bug that crashed the first historical run before any
  output was fixed in 6dce757e. The vault ran from 6dce757e.
- **Results:** `artifacts/phase15/`. Wayback captures are in `data/raw/wayback15/` (both local only).

## A. Point-in-time re-run, 2018 to 2024 (355 QB-change games, one look)
Each QB change counts as public only once the previous starter appeared Out, Doubtful, on injured reserve or suspended. The
evidence is a Wayback capture of ESPN's injury page or an official injury-report row with its modified time.

| Test | With hindsight | Public at the open only | One-sided p (Holm) | Hindsight share (95% CI) |
|---|---|---|---|---|
| A1 closing line value | 0.40 | **0.19** | 0.0004 | 52% (34% to 77%) |
| A2 open-to-close line move | 0.31 | **0.15** | 0.005 | 52% (11% to 88%) |
| A3 market QB adjustment at the open | 0.27 | **0.09** | 0.044 | 66% (21% to 100%) |

- **The tests pass,** but about half of Phase 14's signal was hindsight.
- **The surviving signal is small** and comes mostly from news that became public before midweek. Where the change was
  visible between the open and Wednesday, the hindsight model's correlation with the line move was 0.60 (41 games). Where
  no public record exists, it was 0.20 (242 games).
- **The 0.40 here differs from Phase 14's 0.54** because Phase 14 measured 2021 to 2024 only.

**Coverage:**
- Usable ESPN captures existed for about 52% of the open and midweek windows.
- Of the 387 changed starting QBs, 267 were "not visible": benchings, coach's decisions, or no capture near the time.
- The rule counts a change as public only with a timestamped record, so the hindsight shares are upper bounds. Some of
  those changes were probably public earlier.
- Captures are thin in 2018 and 2019 (87 and 139 usable hourly captures a season) and dense in 2020 to 2024 (261 to 566).

## B. Market-implied QB values and scale, fitted on 2015 to 2024 (494 QB-change games)
- **Label:** the closing market QB adjustment, meaning the closing spread minus what market power ratings expected.
- **Correlation with the performance model:** 0.42.
- **Deming (errors-in-variables) scale:** c = 1.06, 95% CI 0.88 to 1.26. Allowing for noise in both measures, the
  performance model's size matches the closing market on 2015 to 2024. Phase 14's "too large by about 2×" came from comparing
  against the opening line, before QB news was priced.
- **Market-implied residuals:** 169 QBs, prior variance 8. The in-sample correlation of the combined estimate with the label
  was 0.56; that's fitted, not evidence.
- **FiveThirtyEight's QB adjustments match the closing market better:** 0.65, against 0.50 for the combined estimate and
  0.48 for the performance model.

## C. Sealed 2025 vault (unblinded once, commit 6dce757e, 45 QB-change games with lines)
- **V1 fails, narrowly.**
  - The combined estimate correlates 0.52 with the 2025 closing QB adjustment (Holm p = 0.0003).
  - But the scale slope's 95% CI is 0.26 to 0.70 and excludes 1. In 2025 the model overstated QB changes by roughly 2×,
    the opposite of what 2015 to 2024 suggested.
  - The pre-registered rule needed both conditions.
- **V2 couldn't be evaluated.**
  - 2025 has only 100 usable ESPN captures and no official-report timestamps, so all 48 changes were "not visible" and the
    open-time estimate was zero.
  - This is a data-coverage failure, not evidence either way.
- **FiveThirtyEight's adjustments correlated 0.71 with the 2025 market,** against 0.29 for the combined estimate (40 games).

## D and E. Prospective stage and discipline
- **Point-in-time forecasts:** `python -m lab.phase15 freeze` writes them, each with the line at freeze time, for monitor M7.
  The first freeze covered 1 game: ESPN's archive only holds the current week's lines.
- **Futility bounds:** every monitor now reports a futility bound. Two cautions:
  - The pre-registered bound assumes evidence can be as spread out as ±1, which is very conservative. Futility will only
    trigger after thousands of games.
  - Nothing has been scored since registration, so all monitors read "no evidence, not futile".
- **Program stopping rule:** recorded in the ledger. If no monitor reaches e ≥ 20 by the end of 2026 week 18, the QB and
  late-news program pauses.

## What this means
1. **The QB signal is real but small.** About half of what looked like early-information skill was hindsight. What survives
   point-in-time is r ≈ 0.15 to 0.19, coming from news published before midweek.
2. **The scale isn't stable.** It matched the market on 2015 to 2024 but ran about 2× too large in 2025. Any live use needs
   a scale estimated from recent seasons, or from the market itself.
3. **FiveThirtyEight-style QB adjustments track the market better than this model in every check.** The cheapest
   improvement would be to adopt a public, transparent QB-value method of that kind as a prior. That's a new idea for the
   ledger, not something tested here.
4. **Historical timing can't be rebuilt reliably from free archives.** The lab's own 2026 archive (5-minute lines,
   timestamped injury reports) is the only clean evidence going forward, which the stopping rule already protects.
