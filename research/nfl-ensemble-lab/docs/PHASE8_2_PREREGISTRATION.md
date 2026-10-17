# Phase 8.2: prospective blind-spot hypotheses (registered 2026-10-17, before any future game is evaluated)

**What these are:** monitoring hypotheses about the frozen champion, judged **only on games archived after this registration**
(stage snapshots from 2026-10-17 20:15 UTC onward).

**Why prospective only:** every historical season is research-exposed, so the historical numbers below are the exploratory
evidence that motivated each hypothesis, not tests.

**What a result can and can't do:**
- No hypothesis changes any model, and none can register a challenger.
- A supported hypothesis only justifies designing a targeted correction, which would then need its own pre-registration.

Machine-readable copy: `artifacts/phase82/prospective_hypotheses.json`. Evaluator: `lab.blindspots82.prospective_eval()`.

## P1: early-season overconfidence (football-only)
- **Definition:** games in weeks 1–4, using the champion's *final-stage* archived forecast.
- **Metric:** signed miscalibration from the favourite's side, mean(y_fav − p_fav). Its weeks 5+ value is reported alongside.
- **Exploratory evidence (2018–25, 503 games):** favourites won 61.6% vs 63.8% predicted (−0.022, about 1 SE). This is weak.
- **Sample:** 256 future week-1–4 games (two seasons).
- **Supported if** the 95% bootstrap CI of the weeks 1–4 miscalibration lies below 0.
- **Rejected if** the CI includes 0 at 256 games.
- **Interim looks:** none count before 256 games.

## P2: offensive-line disruption (football-only, with a market-informed companion)
- **Definition:** a team has ≥ 2 regular OL starters (≥ 60% snap share over the last 4 games) confirmed out (Out, or reserve on the
  previous week's roster). This is computable before kickoff (`p72_OL_starters_confirmed_out`).
- **Metric (football-only):** excess log loss (LL − H(p)) in these games minus the excess in all other games.
- **Companion (market-informed, reported separately):** the T1 market's log-loss advantage over the champion in these games,
  minus its advantage elsewhere.
- **Exploratory evidence (2018–25, 112 games):** excess difference +0.027 (CI −0.04 to +0.10). Market advantage 0.043 vs 0.020
  elsewhere (CI includes 0).
- **Sample:** 150 future games (roughly 1.5 seasons, given ~14% frequency).
- **Supported if** the excess-difference CI lies above 0.
- **Rejected if** it includes 0 at 150 games.

## P3: information timing of the market's advantage (market-informed)
- **Definition:** for each archived stage forecast (Friday, t24h, t90, t60, final), take the T1 ESPN/DraftKings no-vig
  probability most recently archived before that stage's archive time. Compare it with the champion's probability at the same
  stage, on identical games.
- **Metric:** the paired log-loss difference (market − champion) by stage, and its trend from Friday to final.
- **Exploratory evidence:** the opening line was level with the champion historically (0.630 vs 0.628). The closing line beat
  it (0.609 vs 0.630). On 77 games in 2026 the 24 h market was slightly better (−0.010, CI −0.059 to +0.038).
- **Sample:** 128 games with both a Friday and a final-stage pair.
- **Supported if** the market's advantage at final minus its advantage at Friday is > 0, with CI excluding 0. That would mean
  the market's edge is late information.
- **Rejected otherwise** at 128 games.
- **Not inferred:** the reason for any movement (betting volume, "sharp" action, or causation).

## Multiple comparisons
These are three hypotheses, each with one primary metric, evaluated once at their pre-set sample sizes, using Holm across the
three. Nothing else from the Phase 8.2 screen is tested prospectively.
