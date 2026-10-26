# Phase 12: circadian night-game advantage (Smith et al., SLEEP 2013) on 2012–2025

- **Pre-registration:** `docs/PHASE12_CIRCADIAN_PREREGISTRATION.md` (e2798112), committed before any result.
- **Code:** `lab/circadian12.py`. **Results:** `artifacts/phase12/`.
- **Look:** one.

## Result: **not replicated**
| Sample | Games (excluding pushes) | West coast against the spread | Mean beat-the-spread margin (x) ± SE | One-sided p |
|---|---|---|---|---|
| Paper, night 1970–2011 | 106 | 70–36 | +5.26 ± 1.33 | < 0.0001 |
| **Night 2012–25 (primary)** | 75 | 42–33 | **+0.77 ± 1.42** | 0.30 (Wilcoxon 0.23) |
| Night 2012–18 / 2019–25 | 25 / 50 | 15–10 / 27–23 | +1.02 / +0.64 | 0.34 / 0.36 |
| Night 2014–25, after publication | 70 | 38–32 | +0.35 ± 1.49 | 0.41 |
| Day-game control 2012–25 | 168 | 95–73 | +1.51 ± 1.02 | 0.07 |

- **Night vs day:** the paper's evening-specific contrast is absent (χ² = 0.006, p = 0.94). West coast teams did no better at
  night than in the day.
- **The paper's effect is ruled out:** the estimate is +0.77 ± 1.42, and a +5.3-point effect lies more than 3 standard errors
  above it.
- **Beyond the champion (B1, 2018–25, 55 games):** west coast teams won 45% of these night games, where the champion gave them
  53%. There is no residual advantage; it leans the other way (p = 0.88).
- **Generalised time-zone gap (B2, 437 night games):** the beat-the-spread margin does not rise with the number of zones
  crossed. It is +1.8 for 1 zone, +1.7 for 2 and +0.7 for 3; slope −0.46, p = 0.73.

## Conclusion
The 1970–2011 effect is not present in 2012–2025: it is gone, or the market and teams have adjusted (sleep scheduling,
travel timing). Under the pre-registration it is rejected and will not be re-tested with other cut-offs. The lab's existing
Phase 3 body-clock features stay unused by the champion. No challenger is registered.
