# Drive-level game simulator: results

Run 2026-10-29. Protocol `067e5583`, power and code `8e3cdb51` (committed before the main run), one look.
`reports/homewin_sim/results.json`, SHA-256 `d0447e14581bb0fa593da16c18c648ced40f0898119aa914d019b2eb1a90be41`.
Reused history. **Gate readings stay provisional until Codex reproduces them.** Nothing is promoted; Elo stays champion.

## Data and checks
- Drives rebuilt from raw plays: 144,198 (2002-2026). Agreement with nflverse `fixed_drive_result` was 99.0% overall,
  98.5% in the lowest season and 98.7-100% by class. 656 drives fell in OTHER and were dropped.
- Leakage: the v2 point checks passed. Simulator perturbation (2024 week 9): outputs were unchanged when post-cutoff
  drives were shuffled, and the 8-day-late negative control was detected.
- Scores, neutral sites and kickoffs are as in v1.

## Results (2012 week 1 to 2026 week 7)

| Family | Comparison | Result | Interval | Verdict |
|---|---|---|---|---|
| D (primary) | drive log loss, model 1.4921 vs baseline 1.6613 | -0.1691 | [-0.1729, -0.1655] 95% | **pass**, but see below |
| G | margin RPS, simulator 7.550 vs v2 normal 7.499 | +0.051 | [-0.015, +0.120] 97.5% | fail |
| G | total CRPS, simulator 7.796 vs league normal 7.827 | -0.031 | [-0.141, +0.079] 97.5% | fail |
| W | win log loss, simulator 0.6401 vs elo 0.6332 | +0.0070 | [+0.0009, +0.0129], DM p = 0.004, 4/15 seasons | fail (significantly worse) |
| W | simulator Platt 0.6388 vs elo | +0.0056 | [+0.0001, +0.0105], DM p = 0.010, 3/15 seasons | fail (significantly worse) |
| S | stack weight on simulator (elo 0.754) | +0.184 | [-0.015, +0.395] 95% | fail |

**What the drive pass means.** The preregistered baseline had only field position and home field. An unplanned,
post-look, descriptive ablation (`reports/homewin_sim/ablation_team_effects.json`) refit the same model without team
effects. The full model was *worse* than that situational model by **+0.0060 nats per drive [+0.0043, +0.0076]**. The
entire primary pass came from clock and score state. The team-strength part, as specified (franchise one-hots, C = 1,
240-day decay over 4 seasons), added noise. That is the most likely reason the simulator lost to Elo on win probability.

## Shape checks (descriptive)
- **Key numbers:** 23.1% of margins were exactly 3 or 7; the simulator predicted 16.9%. Simulating drives did not
  reproduce the key-number spike. Fixed TD = 7 and FG = 3 cover common outcomes, but late-game behavior (playing for a
  field goal, kneeling on a lead) is absent from the drive model.
- **Ties:** 0.37% actual vs 0.40% predicted.
- **PIT:** both are non-uniform (chi-square p < 0.001). Margin values pile up at both ends (bins 1 and 10), so the
  simulated margins are too narrow. Total values are skewed low, so the simulator's totals run slightly high.
- **2026 market (106 games):** the simulator's median margin differs from the market spread by 3.1 points on average
  (total 3.5). Against actual results, the market was closer than the simulator on both margin (MAE 9.47 vs 10.23) and
  total (10.54 vs 10.88).

## Power (from the pilot) and the prospective record
Weeks needed before a prospective verdict: drives 237, win 598, margin 1,623, total 3,624. Only the drive family was
powered on history. 2026 week 8 was frozen before the first kickoff, with full margin and total pmfs (SHA-256 `4e709bcd`,
in `reports/homewin_sim/freeze_ledger.jsonl`).

## Missing data
- Timestamped market: 2026 only.
- Injury and QB information: not used by this model by design.
- Official inactives: none archived.
- No PAT, two-point or clock-management modeling, which caps key-number accuracy.
