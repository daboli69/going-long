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
