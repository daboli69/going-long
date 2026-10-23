# NBA official injury-report values: preregistration, 2026-10-23

Committed before any fit or score that uses these features. Builds on the strength study (`docs/STRENGTH_RESULTS.md`), whose passing `all` inputs are the control here. Data: official pregame injury-report PDFs collected by `nba_lab/injury_reports.py` (audit: `docs/INJURY_REPORTS_AUDIT.md`). The original frozen ensemble and the frozen strength shadow stay unchanged.

## Question

The strength shadow knows who played in earlier released games, but not who is ruled out today. Does adding the official pregame report improve it?

## Features (code: `nba_lab/injury_features.py`)

For each team, using the one report per game day published at least 1 hour before that day's first tipoff:

- **Player value**: the same shrunk per-minute Game Score as the strength study (150 replacement minutes at 0.22, last 40 released games).
- **Expected minutes**: the player's minutes over the team's last 10 released games divided by 10. Games he missed count as 0, so someone out for weeks already carries little weight.
- `diff_out_gmsc`: home minus away sum of value × expected minutes for players listed Out or Doubtful.
- `diff_questionable_gmsc`: the same for Questionable.

A team marked NOT YET SUBMITTED is unknown (missing, then imputed with the training median). A team with no rows counts as nobody listed. Unmatched names add nothing. Every report must be published before the decision time, or the build stops.

## Design and gate

- Rows: eligible regular-season games 2021-22 to 2025-26. Train through season-2 (from 2021-22), calibrate on season-1, test 2023-24, 2024-25 and 2025-26 (about 3,690 games).
- Control `strength`: original inputs + margin ratings + travel + recent roster. Candidate `strength_injury`: control + the two features above. Same six fixed members, calibration and earlier-fold stacking as before. 36 base fits and 36 calibrators.
- One comparison. Primary metric: stacked-ensemble log loss. Paired whole-game bootstrap, 2,000 draws, seed 20261023, 95% interval.
- Pass: the interval lies entirely below zero, all 3 test seasons improve, and Brier is no worse.

A pass may add a separately frozen shadow that reads the current day's report; nothing is promoted. All test seasons have been examined in earlier studies with other inputs, so this is retrospective evidence only.
