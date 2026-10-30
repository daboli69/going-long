# One joint score model for winners, spreads, totals and props: pre-registration

Written 2026-10-29, after the five earlier studies and before any model in this study was fit. Local only, $0, read-only
Kalshi data, no trading or order code, no new sports. Nothing is promoted. No scheduled task is added without Travis's approval.
**No undated closing line is used** (Travis has not approved that).

**Question.** Does one consistent score model, anchored to the market where a liquid market exists, give more accurate and
better-calibrated projections and leans for game winners, spreads, totals and player props than the market and simple baselines?

**Reuse disclosure.** The Kalshi window (2025 week 5 to 2026 week 8) and the 20 scored prop weeks were seen in earlier studies. Every
history result is **descriptive**. Only prospective freezes can pass.

## Deviations from the request (stated up front)
- **Tools.** PyMC, NumPyro, MAPIE and scoringrules are not installed, and adding JAX or PyTensor would change the Codex-pinned
  environment. The team-strength model below is the **exact Gaussian conjugate posterior** (what PyMC would sample for this
  model), computed in closed form. Split conformal prediction and CRPS are implemented directly. Travis can approve an
  MCMC install later.
- **Sharpest book.** GOING quotes cover 2026 only (Pinnacle: 133 games). That comparison is descriptive.

## 0. Targets, baselines and metrics

| Target | Baseline 1 | Baseline 2 | Primary metric |
|---|---|---|---|
| Winner | Kalshi winner price at T-90 | Elo | log loss (secondary to the margin metrics) |
| Spread (margin) | Kalshi spread ladder at T-90 (isotonic) | Elo-normal | ladder CRPS; continuous CRPS in the long history |
| Total | Kalshi total ladder at T-90 | naive 3-season mean | same |
| Liquid props | Kalshi player ladder at T-90 | naive recent average | ladder CRPS |
| Thin props | naive recent average | none | quantile-loss CRPS and 80% interval coverage |

T-90 = kickoff minus 90 minutes. Ladder CRPS = sum over a game's liquid thresholds (step-0 filter) of (p - y)^2, where
y = 1[outcome > threshold]. Margin thresholds come from both teams' KXNFLSPREAD markets ("team wins by more than x": home gives P(M > x), away
gives P(M > -x) = 1 - price) and the Kalshi winner price at 0.5. Total thresholds are KXNFLTOTAL strikes. Isotonic
regression (non-increasing, weights 1/spread) makes each game's ladder monotone. **Elo-normal:** margin ~ N(13.5 * z, 13.5^2) with
z = inverse normal CDF of the Elo home-win probability. **Naive:** weighted mean and SD of margin or total over the previous
3 seasons.

## 1. Rawest data, collected prospectively
Kalshi trade prints and order books near kickoff (`scripts/props_kalshi_collect.py snapshot`), official inactives at T-90,
timestamped injury reports, the lab's archived weather and referee data. These feed the prospective freezes only, since none
was timestamped historically. Report what could not be collected.

## 2. The joint score model (closed-form Gaussian posterior)
Margin M = S_home - S_away and total T = S_home + S_away are modeled as two Gaussian regressions plus their residual correlation:
- **Margin:** M = h * (1 - neutral) + n_home - n_away + e, with net team strength n_t ~ N(0, tau_n^2).
- **Total:** T = a + s_home + s_away + e, with scoring level s_t ~ N(0, tau_s^2).
- h and a are unpenalized. Observation precision is 0.5^(age in days / 365). Training = played games of the current and the two
  previous seasons that kicked off before R = the week's earliest kickoff minus 90 minutes minus 4 hours.
- Noise variance by iterated weighted least squares with a degrees-of-freedom correction.
- **Predictive** N(x'b, sigma^2 + x' Cov(b) x). The residual correlation rho is the weighted correlation of the two models'
  training residuals. P(win) = P(M >= 1) + 0.5 P(M = 0) under the normal with continuity correction.
- tau_n and tau_s are chosen **once**, by grid {2, 3, 4, 5} on mean CRPS over 2008 to 2011 weeks (training from 2003), then
  frozen. Nothing from 2012 onward is used for selection. Pilot predictions for 2009 to 2011 also supply the variance
  structure for the power analysis.

## 3. Learn only what the market misses (Kalshi window)
For margin and for total, separately: mu_K = median of the isotonic Kalshi ladder; d = mu_model - mu_K; e = outcome - mu_K.
`b = clip( sum(d * e) / (sum(d^2) + 50 * mean(d^2)), 0, 1 )` fit on earlier-week games of the window (minimum 100 games, else b = 0).
The **corrected forecast** shifts the Kalshi ladder itself by delta = b * d, so P'(Y > c) = S_K(c - delta), with S_K linearly
interpolated and clamped at the ends. Key-number structure is kept. Comparators: the Kalshi ladder (primary), the model alone,
the Kalshi-normal fit (descriptive). Availability changes, weather and referee crew are logged with the freezes and cannot
be used in a fit until a protocol amendment preregisters them.

## 4. Leans and uncertainty
- **Lean** z = d / s, with s = SD of d over earlier games. The model **abstains** (forecast = market) when |z| < 0.5.
- **Reliability table** by |z| bin ([0, 0.5), [0.5, 1), [1, 1.5), 1.5+): mean lean in points, mean realized signed deviation,
  mean ladder-CRPS gain of the corrected forecast, n.
- **Trend test:** Spearman rank correlation between |z| and per-game CRPS gain, week-cluster bootstrap.
- **Split conformal intervals (80%):** nonconformity |y - mu| / sigma for margin and total; for props, CQR scores
  max(q10 - y, y - q90) per stat. Calibration = all earlier weeks, minimum 200, level ceil((n + 1) * 0.8) / n. Report coverage for the raw and the conformal
  intervals: margin and total over 2012 to 2026; props by group (liquid ladder, thin ladder, no market).

## 5. Thin-market props
Over all eligible player-stats in the 179 replayed games (K arm, v2 and naive base): quantile-loss CRPS = 2 * mean over the 99
levels of the pinball loss, full-game actual stats (overtime included, per Kalshi's terms). Groups: **liquid** (at least 3 liquid
thresholds at T-90), **thin** (a ladder exists but fails the filter), **none** (no Kalshi market). Paired difference
v2 minus base, week-cluster bootstrap.

## Families, Bonferroni and pass rules
- **L (long history, 2012 week 1 to 2026 week 8, all played games):** L1 margin vs Elo-normal, L2 margin vs naive, L3 total vs naive, L4 winner log loss vs Elo. alpha = 0.05 / 4.
- **K (Kalshi window, scored weeks after b is fitted):** K1 corrected margin ladder vs Kalshi, K2 corrected total ladder vs Kalshi, K3 corrected winner log loss
  vs Kalshi. alpha = 0.05 / 3.
- **T (thin props):** T1 v2 vs base on thin, T2 on none, T3 on liquid. alpha = 0.05 / 3.
- **Pass:** *improves* if the CI upper bound is below 0; *material* if also the point estimate is at or below -SESOI. SESOI is 1% of the
  baseline's mean metric (log loss 0.005). Coverage passes if the conformal 80% interval's coverage is within 2 points of 80% in every season group.
- Descriptive only: Pinnacle comparison (2026), Kalshi-normal, coherence, abstention and all history results.
- **Placebo:** shuffle the model's mu_model across games within each week and refit b. K1 and K2 are credible only if the real delta is below the
  placebo distribution's 5th percentile (200 permutations, seed 0).

## Power (first, by week-resampling simulation, committed before the main run)
Whole weeks are resampled with replacement, a known improvement is injected into the paired differences, and the same week-cluster
bootstrap test runs (500 draws, 300 resamples, seed 0). MDE(W) = smallest improvement with power 0.80 at W weeks. Reported for the available
weeks and for W = 40, 90, 150, 400. N_weeks = smallest W with MDE at most SESOI.
**Decidable now** = MDE(available weeks) <= SESOI. **Prospective only** = N_weeks <= 150. Otherwise **not decidable**. Variance proxies:
L: the 2009 to 2011 pilot predictions. K: Elo-normal-implied margin shifted at b = 0.2, and the naive total shifted likewise. T: the replayed
v2 and base quantiles. No verdict before N_weeks of frozen data.

## Proof
Realized outcomes and Kalshi settlements. The Kalshi close and, where available, Pinnacle (2026) as benchmarks on the same
games with the same cutoff. ESPN FPI captured at freeze time. Sealed weekly freezes (`scripts/forecast_study.py freeze`) with
the Kalshi winner, spread and total ladders at the same instant, SHA-256 in the pushed ledger. Codex's independent rebuild of this and the five earlier
studies (`docs/CODEX_REPRODUCTION_REQUEST.md`) before any gate is read. Results and freezes on the Streamlit page.

## Amendment 1 (2026-10-29, after the first pilot power run, before any main run)
The first pilot pooled yardage and reception counts in raw units for family T. Yardage dominated the variance, and two of the three
groups hit the power search's upper bound (MDE reported as 0.5). **Change:** family T uses the **per-stat scaled** paired difference
(`loss_v2 - loss_base`) / (mean `loss_base` of that stat over the replayed sample), with SESOI = 0.01 (1% of the baseline). Everything
else is unchanged. The L and K pilot numbers from the first run are kept and are reproduced by the rerun.

## Power results (2026-10-29, after Amendment 1, before the main run)
`reports/forecast/power.json`, SHA-256 `8a95152ab98ddad67974672eb6c35691c4a90676532d5e7cca2eab4ec9abf7da`; tuning
`reports/forecast/tuning.json`: **tau_n = 4.0 and tau_s = 3.0** (frozen). Pilot: 768 games, 51 weeks (2009 to 2011).

| Comparison | MDE at available weeks | SESOI | Weeks needed | Class |
|---|---:|---:|---:|---|
| L1 margin vs Elo-normal (CRPS) | 0.0713 (250 weeks) | 0.0799 | 250 | **decidable now** |
| L2 margin vs naive | 0.1875 (250) | 0.0873 | 1,154 | not decidable |
| L3 total vs naive | 0.0869 (250) | 0.0767 | 321 | not decidable |
| L4 winner log loss vs Elo | 0.0076 (250) | 0.0050 | 573 | not decidable |
| K1 margin ladder vs Kalshi | 0.0444 (21 weeks) | 0.0279 | 54 | prospective only |
| K2 total ladder vs Kalshi | 0.0249 (21) | 0.0189 | 37 | prospective only |
| K3 winner log loss vs Kalshi | 0.0054 (21) | 0.0050 | 25 | prospective only |
| T1 thin props v2 vs base (scaled) | 0.0352 (20) | 0.0100 | 248 | not decidable |
| T2 no-market props | 0.0898 (19) | 0.0100 | 1,534 | not decidable |
| T3 liquid props | 0.0659 (20) | 0.0100 | 870 | not decidable |

**Consequences fixed now.** Only **L1** can produce a verdict from history. The K family can be judged only on prospective freezes after the weeks
shown (about 14 games a week; 25, 37 and 54 weeks). Every other comparison, and every history number in the K and T families, is descriptive with no
pass or fail. Calibration (conformal coverage) and the lean reliability table are descriptive in all cases.
Caveat: the K proxies shift Elo-normal and naive forecasts toward Kalshi at b = 0.2, which is far from a good model, so the K variance
may be overstated (conservative).
