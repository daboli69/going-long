# Phase 8.4: which underdogs beat their price? (local lab only)

- **Pre-registration:** `docs/PHASE8_4_PREREGISTRATION.md`, pushed as 4c5af8c before either test was computed.
- **Code:** `lab/upsets84.py`. **Results:** `artifacts/phase84/`.
- **Dashboard:** Prospective Performance → Blind-spot research → "Underdog traits & line movement (8.4)".

## Result: one look, Holm across V and S2
| Test | Games | Upset chance for a 65% favourite: baseline → +1 SD | One-sided p | Holm | Seasons with predicted sign | Verdict |
|---|---|---|---|---|---|---|
| **V** high-variance underdog (2018–25) | 2,219 | 34.9% → 34.3% (*wrong direction*) | 0.73 | 0.73 | 3/8 | **Rejected** |
| **S2** line moved toward the underdog, beyond the champion (2018–21) | 1,046 | 34.7% → 41.5% | 0.0001 | 0.0001 | 3/4 | **Passed** |

Secondary results (reported, not decisive):

| Test | Games | Upset chance: baseline → +1 SD | One-sided p | Seasons with predicted sign | Reading |
|---|---|---|---|---|---|
| V: underdog VI − favourite VI | 2,219 | 34.9% → 36.0% | 0.15 | 5/8 | not significant |
| S1: movement beyond the opening line (2016–21) | 1,556 | 37.6% → 45.6% | < 0.0001 | 6/6 | replicates Phase 8.1 H2b |
| S3: movement beyond the closing line | 1,555 | 35.8% → 33.9% | 0.88 | 2/6 | null, as expected |

Each extra standard deviation of movement is about 2.9 points of spread.

### Lines that moved 1.5+ points toward the underdog (2016–21)
- **Frequency:** 366 games, 23.5% of the total.
- **Underdog win rate:** 44.8%, against what each source implied:

  | Source | Implied underdog win rate |
  |---|---|
  | Opening line | 32.5% |
  | Champion (256 games, 2018–21) | 41.4% |
  | Closing line | 43.0% |

- **Opposite case:** when the line moved 1.5+ toward the favourite (328 games), underdogs won 25.6%, against 32.5% implied by the open.

## What this means
- **Variance style isn't the angle.** Underdogs that throw a lot, hit explosive plays, sack the quarterback and force
  turnovers do not win more often than their price says. Upset rates by variance quintile track the champion's implied rate
  closely.
- **Sharp money is the angle, and it is real.** When the line moves toward the underdog between open and close, that underdog
  wins more often than the champion expects, in 3 of 4 seasons. The market learns something during the week that the champion
  doesn't have: injuries, weather, news, sharp opinion.
- **It is not a betting edge.** The movement is already in the closing price (S3 is null). Betting the underdog at the close
  earns nothing beyond the close. The value is only for someone who bets *before* the move, or as a warning that the champion's
  favourite is weaker than it looks.
- **Caveats:**
  - SBR opening lines have no recorded time (T2) and closing lines are untimestamped (T3).
  - 2018–21 has been examined in earlier market work (8.1). This look is pre-registered, but those seasons are not virgin.

## Prospective test (registered 2026-10-18 04:00 UTC)
- **Hypothesis S2P:** movement from the archived ESPN/DraftKings opening spread to the latest spread archived **at or before** the
  champion's final-stage forecast. It is standardised with the frozen 2018–21 scale (mean +0.17, SD 2.86).
- **Test and sample:** a one-sided test at α = 0.05 after 128 games.
- **Scope:** this is a research flag only. Nothing changes in the champion, the challengers or the GOING site, and no variants
  will be tried.
- **Status:** 0 of 128 games.
- **Coverage gap:** the archive covers only games after 2026-10-17, and only the snapshots the scheduler captures before the final
  stage. Late movement after the final forecast is invisible to this test.
