# Phase 8.7 results: multi-season separation edge (NGS avg_separation), one look

Pre-registration: `docs/PHASE8_7_PREREGISTRATION.md` (commit 5bfe5f1, pushed before any result). Code: `lab/ngs87.py`.
Artifacts (local, gitignored): `artifacts/phase87/results.json`, `confirmation_quintiles.csv`, `team_edges.csv`.
Run once on 2026-10-18. Nothing changed in the champion, the challengers or GOING.

## Verdict: **FAIL.** The separation edge adds nothing that holds up beyond the champion or the close.

| Test | Base | Seasons | Games | Coef per SD | One-sided p | Seasons negative | Pass |
|---|---|---|---|---|---|---|---|
| Primary, discovery | champion OOF | 2018–20 | 585 | +0.009 | 0.54 | 2 / 3 | (not decisive) |
| **Primary, confirmation** | champion OOF | 2021, 22, 24, 25 | 862 | −0.081 | **0.15** | 2 / 4 | **no** |
| Secondary, discovery | no-vig close | 2016–20 | 1,016 | +0.042 | 0.73 | 3 / 5 | (reference) |
| Secondary, confirmation | no-vig close | 2021, 22, 24, 25 | 862 | −0.057 | 0.23 | 2 / 4 | no |

- The confirmation coefficient points the predicted way (upset probability at a 65% favourite: 34.1% → 35.9% per +1 SD of
  angle), but p 0.15 misses the 0.05 bar. The sign criterion (≥ 2 of 4) was met, so the p-value alone decides the fail.
- Discovery points the wrong way (+0.009). Across 1,447 champion-base games in seven seasons there is no consistent signal.
- Beyond the close it is weaker still, matching Phases 8.3–8.5.

## Coverage
- About 75–80% of games per season have an angle. Weeks 1–4 need 3 earlier games per team. NGS lists only qualifying
  receivers, so some team-weeks are missing.
- 2016–17 have no champion OOF, so they appear only in the secondary test.
- Angle scale (discovery, frozen): mean −0.054, SD 0.562 yd.

## Descriptive (confirmation, not tested)
Upset rate by angle quintile:

| Angle quintile | Games | Champion-implied | Observed |
|---|---|---|---|
| Favours favourite most | 173 | 33.9% | 32.4% |
| Favours favourite | 172 | 33.9% | 33.1% |
| Mid | 172 | 36.1% | 33.7% |
| Favours underdog | 172 | 36.4% | 32.0% |
| Favours underdog most | 173 | 37.4% | 41.6% |

- Only the top quintile sits above the implied rate (+4 points on 173 games, about 1.1 binomial SE). The other four sit at
  or below it, so the pattern is not monotone.
- This was not a pre-registered test and must not be turned into one after the fact (for example "top quintile only").

## Reading
- Together with 8.6 (2023, p 0.23), the separation edge has now pointed the predicted way in the 2023 and 2021–25
  confirmation samples, but never significantly, and the wrong way in 2018–20. NGS is a proxy (r 0.58 with BDB arrival
  separation), so a real but small tracking effect could be diluted. That is a reason a failure here does not prove tracking is
  useless, not a reason to re-test variants.
- No prospective hypothesis is registered. No model, challenger or GOING change.
