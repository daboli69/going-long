# Quarterback lever challengers: pre-registration

Written 2026-11-09, before any challenger was built or fitted. Champion/Challenger gate of `MODEL_RESEARCH.md`: challengers are research only, nothing is promoted without chronological out-of-sample evidence and Travis's approval, and nothing here touches a freeze or the app.

## Question

The production margin model (`lab/homewin_deep.py`, `MARGIN_X`) uses one quarterback input, `qb_delta_diff`: the expected starter's value (EPA per dropback, shrunk with 250 dropbacks toward the early-career mean) minus the team's dropback-weighted value over the rating window, home minus away. For BUF@MIN, replacing Murray with Wentz moved the predicted margin by 0.24 points while the market moved about 14 points on the news. Does a better-built quarterback input improve out-of-sample game predictions? The answer may be no: the two quarterbacks may simply be rated equal by EPA.

## Champion

Production, unchanged: `qb_delta_diff` as defined above, margin OLS fit on seasons from 2004 (`MARGIN_TRAIN_START`), probability `norm.cdf(pred / sigma)`.

## Challengers (the complete list; no others will be tried)

- **C1 opponent-adjusted value.** Each dropback's EPA is reduced by the opposing defense's mean EPA per dropback allowed that season, with the game itself left out, and only games before the decision time are used. Same shrinkage (250), same early-career prior.
- **C2 recency-weighted value.** Dropbacks are weighted by 0.5 raised to the number of full seasons since the game (half-life one season; this season's games weigh 1). Same shrinkage, applied to the weighted dropback count.
- **C3 both C1 and C2.**
- **C4 change flag.** Champion value plus a second regressor, `qb_change_diff` = home `qb_change` minus away `qb_change`, so a replacement or swapped starter can carry a penalty the value alone does not.

Everything else (team ratings, rest, home field, training window, `sigma` from out-of-sample residuals) is the champion's. Constants above are fixed now, not tuned.

## Data and splits

- Decision-time data only (injury rows and results available before the existing decision cutoff, as the champion does).
- Walk-forward by season: for each season s, fit the margin model on earlier seasons only, with each challenger's input rebuilt as of every earlier week.
- **Development:** 2012 to 2021. Used to catch bugs and to check that no challenger is worse than the champion; no choosing among challengers on it.
- **Holdout:** 2022 to 2025, run once after the development check, with the code and constants frozen in a commit. **2026 is excluded** and no 2026 outcome is looked at.

## Metrics and gate

Paired, game-cluster bootstrap (2,000 draws, seed 20261110), deltas are challenger minus champion.

- Primary: margin squared error, holdout. Holm correction over the four challengers.
- Secondary: log loss of the win probability, and calibration slope of the win probability.
- **A challenger passes only if all hold on the holdout:** margin squared error delta has 95% interval upper bound below 0 after Holm; log loss delta is not above 0; calibration slope stays within 0.9 to 1.1; the development delta is not above 0.
- Also report the change in predicted margin for QB-change games alone (swapped starter, `qb_change` of 1 on either side) and the count of such games; if there are fewer than 100, say the subgroup is underpowered.
- A pass is a "Challenger, recommend review", never a promotion. A fail leaves the champion as is and is reported as a fail.

## What this cannot show

It cannot say whether Wentz is better than Murray, only whether a differently built quarterback input predicts games better in the past. It uses published EPA, not the PR 618 EPA. It does not test whether the market's reaction to a quarterback change was right.

## Results (run 2026-11-09, `scripts/qb_lever_eval.py`, numbers in `docs/qb_lever_results.json`)

Implementation notes fixed while writing the code, before any result: C1 centers the defense adjustment on the league mean allowed per dropback (otherwise every adjusted value shifts), uses the defense's games of that season before the decision time with the game itself left out, and falls back to the league mean when there is none. The champion rebuild matched the production `qb_delta_diff` exactly (max difference 0.0), so the comparison is like for like. The margin model is refit once per season on earlier seasons only, with `sigma` from the training residuals. Holm uses one-sided bootstrap p-values against alpha 0.025 (matching a two-sided 95% interval).

Squared error of the predicted margin, challenger minus champion (lower is better; champion 186.2 in development and 164.8 in the holdout):

| | Dev delta | Holdout delta | Holdout 95% interval | Holdout log loss delta | Holdout calib. slope | Holm | Passes |
|---|---:|---:|---|---:|---:|---|---|
| C1 opponent-adjusted | +0.05 | 0.00 | -0.15 to +0.15 | +0.00002 | 1.01 | no | no |
| C2 recency-weighted | -0.27 | -0.50 | -1.05 to +0.02 | -0.00025 | 1.01 | no (p 0.032 vs 0.008) | no |
| C3 both | -0.18 | -0.51 | -1.16 to +0.14 | -0.00016 | 1.01 | no | no |
| C4 change flag | +0.13 | -0.43 | -1.00 to +0.02 | -0.00058 | 1.02 | no (p 0.031 vs 0.006) | no |

**No challenger passes. The champion stays.**

- **C2 is the only consistent signal.** It improved on the champion in both periods, but by about 0.3% of the squared error, and the holdout interval touches zero before the Holm correction. A lead, not a result.
- **C1 does nothing**: the defense adjustment changes the quarterback values by almost nothing (correlation 0.98 with the champion).
- **C4 helped in the holdout but not in development**, so it fails the rule that development must not be worse.
- **Swapped starters: 10 holdout games and 17 development games.** Underpowered, as warned. The large per-game gains in that subgroup (-16 for C2, -50 for C4 on 10 games) are noise at that size.
- Of note: C2 compresses quarterback values (standard deviation 0.037 against 0.065), because the shrinkage prior stays at 250 while the weighted dropback count falls. A different prior for the weighted version would be a new challenger and a new registration, not a tweak to this run.

Reading: the quarterback input is not the weak spot the BUF@MIN case made it look like. A rebuilt input does not predict games meaningfully better, and swaps are too rare in the record to fit a bigger lever. The market's 14-point move on the Murray news is not something these inputs can reproduce.
