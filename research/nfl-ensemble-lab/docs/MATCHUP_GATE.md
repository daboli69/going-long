# Matchup features against the closing line: gate result

Rule: `docs/MATCHUP_PREREG.md` with Amendment 1. Code: `lab/matchup.py`, `scripts/matchup_run.py gate` and `diagnostic`. Raw numbers: `docs/matchup_gate.json`, `docs/matchup_gate_diagnostic.json`. No challenger-minus-champion result was computed or read.

## Verdict

Neither hypothesis is testable on 2022 to 2025. The planted-effect check fired the pass rule in 24% of runs for H1 (efficiency) and 27% for H2 (turnovers), against the 80% the registration requires. Section 4 of the registration says what to do: report that the pass rule is too strict for this sample, before anything is read. The outcome comparison stays unread.

## Numbers

| | H1 efficiency | H2 turnovers |
|---|---|---|
| Games scored, 2022 to 2025 | 1,084 | 1,084 |
| Placebo spread of the pooled mean difference | 0.00069 | 0.00030 |
| Smallest detectable effect (2.8 x spread) | 0.0019 | 0.0009 |
| Planted gain 0.004: gain recovered | 0.0035 | 0.0035 |
| Planted gain 0.004: pass rule fires | 24% | 27% |
| Testable | no | no |

## What binds

The placebo spread is misleadingly small. With shuffled features the fit shrinks every feature coefficient to about zero, so the placebo runs barely vary. When a real signal is present, the estimated gain varies by about 0.003 from sample to sample (`docs/matchup_gate_diagnostic.json`), four times the placebo spread.

In the diagnostic, the clustered interval is the condition that fails most often. Even at a planted gain of 0.008, which is twice the registered size, the full rule fires in only 47% (H1) and 55% (H2) of runs. The other conditions pass more often: the 0.002 minimum gain 69 to 95%, three of four seasons better 73 to 91%, Brier no worse 86 to 99%.

So 1,084 games over four seasons cannot reliably separate a gain of 0.004 to 0.008 log loss from noise against a closing line. That is a sample-size limit, not a coding problem: the pipeline recovers the planted gain (0.0035 of 0.004).

## Disclosed limits

- Moneyline coverage is complete from 2010 and partial before (2007 has 255 of 256 games, 2008 has 185, 2009 has 242); 2022 to 2025 is complete. Games missing a moneyline are dropped.
- The planted signal uses only the first feature of each hypothesis, so H1 power for its two-feature fit is, if anything, a little overstated.

## Next

The gate failed before any outcome was read, so the design can still change without selection. The cheapest change is a longer test window: score 2012 to 2025 (14 seasons, about 3,800 games) with the same fit-on-earlier-seasons rule, which cuts the interval width by roughly half. That needs an Amendment 2 committed before the gate is rerun. Waiting for the Week 10 onward freezes alone would take years to reach this power.
