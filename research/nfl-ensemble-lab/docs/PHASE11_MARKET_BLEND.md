# Phase 11: market-blend shadow challenger

- **Pre-registration:** `docs/PHASE11_MARKET_BLEND_PREREGISTRATION.md`, commit 9eea727 (2026-10-26 20:12 UTC), pushed before any
  code was committed or any score was computed.
- **Code:** `lab/market_blend11.py` (refresh with `python -m lab.market_blend11`); tests in `tests/test_phase11.py`.
- **Results:** `artifacts/phase11/results.json` and `scored.csv` (local, gitignored).
- **Dashboard:** "Market-blend shadow (11)" tab in the Blind-spot research section.
- **Unchanged:** the champion, both challengers, the snapshots, the ESPN archive, the pinned scheduler release and the Windows task.

## Frozen weights
p = σ(−0.1319 + 0.2569 · logit(champion) + 0.8165 · logit(DraftKings opener, no-vig))

`run()` refits on the 2018–21 data each time as a check. The refit matches the frozen weights exactly (1,083 games, maximum
difference 0.0).

## Primary test: not started
**0 of 128** counted final-stage games. Only final snapshots made after 2026-10-26 20:12 UTC count, so the first counted
games are in week 8. There is no conclusion yet.

## 2026 weeks 6–7: descriptive only (26 final-stage games, all made before registration)
Every one of the 26 final-stage forecasts had an archived opener, so none fell back.

| Forecast | Log loss | Brier | Accuracy |
|---|---|---|---|
| Challenger | 0.726 | 0.264 | 50.0% |
| Champion | 0.774 | 0.286 | 53.8% |
| DraftKings opener alone | 0.737 | 0.268 | 57.7% |
| DraftKings closing line | **0.696** | 0.247 | 61.5% |

- **Challenger minus champion:** −0.048, 95% CI −0.140 to +0.041. Not distinguishable from zero.
- **Challenger minus closing line:** +0.030, CI −0.054 to +0.117. The closing line was still better.
- **Other stages:** the early and early-week stages all fell back to the champion, because the archive starts on Oct 17.
  At the friday stage, 13 of 25 fell back; at t24h, 8 of 26. From t90 on, none did.
- Weeks 6–7 motivated this phase, so these numbers are not evidence for it.

## Frozen weights on 2022–25 openers: descriptive, not a gate
These seasons were exposed in Phase 8 (closing-line work), so this is a consistency check, not a holdout.

| Season | Games | Challenger | Champion | Opener alone |
|---|---|---|---|---|
| 2022 | 282 | 0.6285 | **0.6281** | 0.6288 |
| 2023 | 285 | 0.6431 | 0.6539 | **0.6398** |
| 2024 | 285 | **0.5969** | 0.6091 | 0.5997 |
| 2025 | 284 | **0.6215** | 0.6354 | 0.6228 |
| **All** | 1,136 | **0.6225** | 0.6316 | 0.6228 |

- **Against the champion:** −0.0092, CI −0.0182 to +0.0003. Better in three of four seasons, but the interval just
  reaches zero.
- **Against the opener alone:** −0.0003, CI −0.0048 to +0.0041. Here the challenger is the opening line with a small
  champion tilt. The 2019–21 complementarity (H5 secondary) did not show up as a measurable gain over the opener in
  2022–25.

## What this means
- The challenger mostly tracks the opening line. Any gain over the champion comes from the market, so it is **not
  independent football intelligence**.
- The prospective test asks whether a forecast anchored to the opener beats the champion by the final stage. It does not
  test whether the champion adds anything to the market. On 2022–25 history, it added nothing measurable to the opener.
- **Risks carried forward:** the champion weight is unstable (0.09–0.45 across left-out seasons). The fitted intercept
  favours away teams. DraftKings lookahead openers may be staler than the 2018–21 openers the weights were fitted on.

## Next
- Re-run `python -m lab.market_blend11` after each week. The single primary evaluation happens at the 128th counted game,
  about half a season away.
- Even if it passes, promotion needs Travis's approval.
