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
