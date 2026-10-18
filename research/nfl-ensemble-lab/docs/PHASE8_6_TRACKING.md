# Phase 8.6: Big Data Bowl 2026 tracking (2023), local lab only

- **Pre-registration:** `docs/PHASE8_6_PREREGISTRATION.md` (419f3e1), pushed before any metric was computed.
- **Code:** `lab/tracking86.py`. **Results:** `artifacts/phase86/`.
- **Dashboard:** Blind-spot research → "Tracking: Big Data Bowl 2023 (8.6)".
- **Data:**
  - The Kaggle analytics and prediction zips, downloaded manually by Travis and extracted to `data/raw/kaggle/` (git-ignored).
  - Hashes are in `provenance.json`. The competition rules forbid redistribution, so nothing is committed or published.
  - The two zips' training files are identical (matching CRCs).
  - The prediction zip's Kaggle evaluation code was not extracted or run.

## Metric
- **Arrival separation:** the distance from the targeted receiver to the nearest tracked defender at the moment the ball arrives.
- **Sample:** 12,966 targeted passes in 2023, median 2.39 yards.
- **Team edge:** the as-of difference between the separation a team's offense creates and the separation its defense allows,
  requiring ≥ 3 earlier games.
- **Range:** separation allowed runs from 2.74 yards (ATL, best) to 3.46 yards (MIN, worst). Man-coverage rates range from 12% to
  47% (team median 30%).

## Results (one look; 224 games, 2023 weeks 4–18)
| Test | Effect: upset chance for a 65% favourite, baseline → +1 SD toward the dog | One-sided p | Verdict |
|---|---|---|---|
| T1 beyond the champion (primary) | 36.8% → 39.2% | 0.23 | **Not significant** (direction as predicted) |
| T2 beyond the closing price | 35.5% → 36.1% | 0.43 | Nothing beyond the market |
| P1 NGS proxy check | r = 0.58 across 534 team-weeks | < 1e-49 | **Adequate proxy** (threshold 0.5) |

## What this means
- **On its own,** one season of tracking is too small to show that separation predicts upsets. The direction matched the
  prediction, but 224 games can only detect a large effect. This is "not shown", not "no effect".
- **The useful result is P1.** NGS `avg_separation`, which is public every week from 2016 and already in the lab, tracks the BDB
  measure well enough to stand in for it. A separation-edge test can therefore run on about 2,500 games over 2016–2025 instead of
  224, and be followed live every week.
- **That would be a new, separately pre-registered study.** T1's single look on 2023 is used up, so 2023 would be excluded or
  labelled as already examined.
- **No model, challenger or GOING change.**
