# NBA strength features: results, 2026-10-23

Protocol `docs/STRENGTH_PREREGISTRATION.md` was committed (c50bf0f6) before any fit. One pass: 264 base fits, 264 calibrators, 338 seconds. No constants changed after results. The original frozen ensemble, models and forecasts are untouched.

## Results (stacked six-model ensemble, pooled test games)

| Candidate vs control | Log loss | Change [corrected 95% CI] | Accuracy | Better seasons | Gate |
|---|---|---|---|---:|---|
| rating (A, 2019-26, n≈8,600) | 0.62521 → 0.62360 | -0.00160 [-0.00321, +0.00008] | 65.3% → 65.5% | 7/8 | Fail (CI touches 0) |
| travel (A) | 0.62521 → 0.62520 | -0.00001 [-0.00130, +0.00134] | 65.3% → 65.2% | 4/8 | Fail |
| rating + travel (A) | 0.62521 → 0.62386 | -0.00134 [-0.00312, +0.00033] | 65.3% → 65.2% | 6/8 | Fail |
| roster (B, 2023-26, n≈4,900) | 0.62470 → 0.62087 | -0.00383 [-0.00747, +0.00008] | 65.0% → 66.0% | 4/4 | Fail (CI touches 0) |
| **all: rating + travel + roster (B)** | **0.62470 → 0.61990** | **-0.00480 [-0.00864, -0.00076]** | **65.0% → 66.1%** | **4/4** | **Pass** |

Brier improved for every candidate except travel. In the passing candidate, all six members improved on their own: XGBoost -0.0095, histogram boosting -0.0113, random forest -0.0072, SVM -0.0047, logistic -0.0034, MLP -0.0024.

## What this means

- **Who played recently matters most.** Roster strength from earlier released box scores gave the largest gain. It picks up trades and long absences that team averages blur.
- **Margin ratings help a little.** They were better in 7 of 8 seasons, but the gain is too small to separate from noise alone.
- **Travel adds nothing measurable** beyond the rest and back-to-back inputs already in the model.
- **Caveats.** Study B's control trains on 2021 onward only, so it scores worse than plain Elo (0.6247 vs 0.6222). The passing candidate beats Elo by only 0.0023. Seasons 2024-26 were already examined in earlier studies. The relative gain is 0.77%, under the original 1% bar, which this protocol reported but didn't require. All of this is retrospective evidence, not fresh confirmation.

## What changed

- `nba_lab/strength.py` builds the features; `tests/test_strength.py` adds outcome, 24-hour and calendar leakage checks.
- `docs/STRENGTH_SHADOW_CONFIG.json` freezes the passing `all` candidate with code hashes. `nba_lab/strength_shadow.py` fits the six members on 2021-onward games (last 300 for calibration) and stacks them with the study's out-of-fold stacker.
- Daily refresh (launcher option 2) and `python -m nba_lab.cli shadow-forecast` now append strength-shadow forecasts. The Today page shows them in a new expander. First archive: eight 2026-10-24 games.

## Other findings

- The 2020 Orlando restart games aren't flagged neutral in the source data, so the original features give a false home edge to about 88 bubble games. The new travel features treat them as neutral; the original features weren't changed.
- The MLP is the weakest member in every study (log loss about 0.67) and keeps hitting its iteration cap. The `mlp_small` shadow already addresses it.
- Next data step: the official NBA injury-report PDFs (`https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HHPM.pdf`) are public, need no login and go back to at least January 2022. They are the timestamped pregame availability source this project has been missing. Parsing needs a PDF library such as `pdfplumber` in a dedicated NBA environment.
