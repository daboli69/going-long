# Net-of-kickoff EPA and capped play values: rules fixed before the code ran

Written 2026-11-09. Descriptive tooling only. Nothing here feeds the forecast, the simulation or any freeze.

## Part 1. nflfastR PR 618 (approximation)

[nflfastR PR 618](https://github.com/nflverse/nflfastR/pull/618) is open and unmerged. It values a touchdown as `6 + xp - V`, a field goal as `3 - V` and a safety as `2 + W`, where `V` is the EP of 1st and 10 after the kickoff that follows. The published nflverse play-by-play still uses 7/3/2. This machine has no R and the EP model files are not local, so the real branch cannot run here.

What `lab/epnet.py` does instead, using only columns already in the local play-by-play:

- The next-score probabilities (`td_prob`, `fg_prob`, `safety_prob`, `opp_*`) stay as published. Only the point values change.
- `V` is measured from the data: the mean `ep` of the first scrimmage play after a kickoff, by seconds left in the half (bins fixed below) and kickoff era. `W = V + 0.05 * (kickoff spot - 61)` yards, the PR's own shortcut and free-kick spot.
- `xp` is the PR's values: 0.99 through 2014, 0.94 for 2015 to 2022, 0.96 since.
- `ep_new` replaces the point values; `epa_new` is the new after-state minus `ep_new` of the play.

It is an approximation, named as one everywhere it appears. It does not use the overtime rules, the home-field handling or the model-based `W` of the PR.

Bins for seconds left in the half: 0-60, 60-180, 180-420, 420-900, 900+. Kickoff spot by season: 80 through 2015, 75 for 2016-2023, 70 for 2024, 69 from 2025.

### Check against the PR's own reported effects (known before this rule)

The approximation is called consistent only if all hold on 2026 so far:

1. Mean `ep` is lower than the published `ep` by 0.25 to 0.55 (PR: 0.40).
2. Mean value of a touchdown is between 5.6 and 6.1 (PR: 5.87).
3. Mean value of a made field goal is between 1.8 and 2.3 (PR: 2.05).
4. EPA per pass for passers with 100 or more attempts moves by at most 0.10 for every passer, and the Spearman rank correlation with the published EPA per pass is at least 0.98 (PR: at most 0.06, 0.996).

If any fails, the module is reported as not reproducing the PR and stays unused by the app.

## Part 2. Capped play values (one play or game should not torch a number)

Fixed now, not tuned:

- Per-play passing yards are capped at 40 and per-play EPA is clipped to [-3, 3] before any mean, share or yards-per-route is formed. Counting statistics (targets, routes, explosive completions of 20+ yards) are untouched.
- `covcard.build(robust=True)` and the receiver and QB numbers in `covgame` use the capped values; default stays uncapped so the live Coverage tab does not change unless a caller asks.
- `onoff.game_level` adds the per-game median next to the mean.

### Sensitivity (reported, not a test)

Re-run the Week 9 coverage retro with the caps on and report the three Spearman correlations beside the uncapped ones. The Week 9 reading rule is not changed, and a capped pass does not upgrade the earlier result.

## Results (run 2026-11-09)

### Part 1. Net-of-kickoff approximation: does not reproduce the PR, stays unused

`scripts/epnet_check.py`, numbers in `docs/epnet_check.json`, 2026 so far.

| Check | Ours | PR | Result |
|---|---:|---:|---|
| 1. Mean ep change | -0.64 | -0.40 | Fails (range -0.55 to -0.25) |
| 2. Mean touchdown value | 5.60 | 5.87 | Passes, at the bottom of the range |
| 3. Mean made field goal value | 1.76 | 2.05 | Fails (range 1.8 to 2.3) |
| 4. Passer EPA per pass shift, Spearman | max 0.109, rho 0.985 | max 0.06, rho 0.996 | Fails on the 0.10 cap, rank part passes |

Reading: the direction and size are right, but the measured `V` (about 1.4 for the first play after a modern kickoff, taken from the file's own `ep`) is higher than the value the PR's numbers imply (about 1.1), so every score is discounted too much. The cap was not loosened after seeing this. Also, the stored `ep` does not equal the probability-weighted 7/3/2 sum on 9% of rows, so the shortcut is not exact. Real answer needs the R package and the EP model files (R is not installed here). `lab/epnet.py` is kept as a documented attempt; nothing imports it.

### Part 2. Capped play values: sensitivity on the Week 9 retro

Reported beside the original; the Week 9 reading rule is unchanged (`--robust` run writes `docs/coverage_retro_w9_robust.json`).

| Prediction | Uncapped Spearman (p) | Capped Spearman (p) |
|---|---:|---:|
| Receiver edge | -0.14 (0.17) | -0.14 (0.17), identical: FantasyPoints man and zone yards per route are aggregates and cannot be capped |
| Position share | +0.30 (0.008) | +0.30 (0.008), identical: target counts are not capped |
| Quarterback EPA per pass | +0.32 (0.115) | +0.24 (0.25) |

Only the quarterback numbers move, and they get weaker, so the earlier right-direction reading for quarterbacks leaned partly on a few large plays. Nothing changes the earlier verdict: receiver and quarterback calls do not pass, position share stays a lead.

### Part 3. The real PR 618 code (run 2026-11-09)

R 4.6.2 was installed for the current user and the PR 618 build of nflfastR plus `fastrmodels` were installed from GitHub into `data/cache/rlib` (`scripts/ep_pr618/`, runner `scripts/ep_pr618.py`). The package's `add_ep_variables()` was run on a copy of each local season (2022 to 2026); nothing in `data/raw` was changed. The nflverse files do not carry every column the package builds itself, so the runner derives the model inputs with the package's own `make_model_mutations()`, adds the scoring flags from `field_goal_result`, `extra_point_result` and `two_point_conv_result`, and reads blanks as NA. A first attempt that left blanks as text gave nonsense EPA and was fixed before any result was read.

The same four checks as Part 1, 2026 so far: it reproduces the PR's reported effects.

| Check | Real PR code | PR reports |
|---|---:|---:|
| Mean ep change | -0.408 | -0.40 |
| Mean touchdown value | 5.88 | 5.87 |
| Mean made field goal value | 2.04 | 2.05 |
| Largest passer EPA-per-pass shift (35 passers) | 0.049 | at most 0.06 |
| Passer rank correlation | 0.993 | 0.996 |

The mean ep change is also -0.33 to -0.41 in 2022 to 2025. This confirms the run is the PR's calculation, not that the PR is right; it is an unmerged proposal.

Use in the lab: `covcard.build(pr618=True)` swaps in the PR's EPA for the quarterback and defense EPA numbers (`covcard_retro.py --pr618`, file `docs/coverage_retro_w9_pr618.json`). The Week 9 outcomes still use the published EPA. Quarterback EPA correlation: +0.32 (p 0.115) published, +0.25 (p 0.23) with the PR's EPA. Receiver edge and position share do not use EPA and are identical. Default stays the published EPA, so nothing in the app changes; this is a sensitivity result only.
