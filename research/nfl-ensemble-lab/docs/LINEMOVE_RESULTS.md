# Closing-line efficiency on 20 years of game lines: results

Run 2026-11-06 against docs/LINEMOVE_PREREG.md (commit 3f6da57d). Football only. No staking or bet sizing.

## Result

No edge found. Two of the four tests could be read, and neither found anything. The other two were too small to read under the rule.

## Data actually available

The file has 5,509 games, but many early seasons lack the open or close fields the tests need. After the registered filters (regular season, open and close present, scores present, no ties) the decide stage (2006 to 2015) kept 511 games and the confirm stage (2016 to 2025) kept 2,422. The 2026 sample has 78 games. Because the decide stage is small, its signs are weak evidence.

## Power gate (before any coefficient was shown)

| Test | Smallest detectable | Size of interest | Verdict |
|---|---|---|---|
| T1 spread drift | 0.057 | 0.06 | informative (just) |
| T2 total drift | 0.059 | 0.06 | informative (just) |
| T3 moneyline against spread | 0.144 | 0.10 | too small, not read |
| T4 dispersion | 0.063 | 0.06 | too small, not read |

## What the readable tests found (confirm stage, 2016 to 2025)

| Test | Decide | Confirm | 95% interval (confirm) | Holm p |
|---|---|---|---|---|
| T1: does a spread move keep going after the close | -0.013 | +0.005 | -0.036 to +0.046 | 1.0 |
| T2: does a total move keep going after the close | -0.006 | +0.027 | -0.013 to +0.070 | 0.71 |

Both are indistinguishable from zero, and the decide and confirm signs disagree. So the closing line is efficient with respect to its own movement at the sample size we have. Descriptive by source: Pinnacle seasons (2016 and 2017, 510 games), bet365 seasons (2018 to 2024, 1,848 games) and betr (2025, 64 games) show nothing consistent. The 64-game betr figures are noise.

Price check: not run, because nothing passed.

## Not read

- T3 (does the moneyline disagree with the spread in a way that predicts the winner) and T4 (does a line that wandered more predict bigger errors) failed the gate by a small margin. Their confirm coefficients were not read.
- The script also printed 2026 descriptive coefficients for all four tests on only 78 games, including T3 and T4. I am not using them: they are noisy and two come from tests that failed the gate.

## Concerns

- Source mix: the open and close come from different books over time (Pinnacle, bet365, betr). The sharp-book era is only two seasons here.
- The open and close times are unknown. "Open" is whenever the source first posted.
- The file's own terms say it may contain errors and is for personal use.
- The decide stage is small because older rows lack odds fields.

## Next

Nothing to build on this. The closing line behaves efficiently here. The more promising places for a gap remain props, which are waiting on the weekly saves, and the sportsbook lag test once more games qualify.
