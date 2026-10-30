# Codex reproduction report: seven NFL studies and the Doubtful change

**Status: source/protocol audit completed; numerical reproduction blocked. None of the seven studies is independently matched by this review.** A blocked reproduction is not an observed numerical mismatch.

Review branch: `codex/repro-20261030`, created from `codex/projections-20261019` at `752f3aa41a4aecdc3323dc74f6f2e903ff656a83`. Scope: football, $0, read-only source/data investigation; the only repository change is this report. No model, protocol, Claude result file, prospective archive, scheduler or main branch was changed. No deployment, migration, trading operation or paid API was used.

## Execution and blinding record

1. Read the seven preregistrations at their named protocol/amendment revisions before reading implementation. The reproduction-request table was processed with its final column removed. Root AGENTS.md was also read.
2. Read the listed scripts and their dependencies at the specified code commits. Where a corrected/current implementation is discussed, its separate revision is identified below.
3. The managed execution environment never became usable and ultimately reported: **“failed to query executor configuration capabilities for environment”** `ccarenv_b64_Y2NhcmVudl83MTk3YmEwNWZhZWM4MTkxYTBjMDEyNGJmMjU0ZGM0OA`. Shell calls returned **“No usable execution environment is available.”** Consequently there was no full clone, Python process, package installation, cache rebuild, Kalshi pull, empirical fit or pytest execution. GitHub connector reads remained available; the branch and this report were created through that connector.
4. Recorded the execution block, source findings and independent arithmetic counterexamples before revealing the seven-study table's last column. Then read that column for the comparison table below.
5. **Blinding exception:** fetching the Task 2 commit diff also returned the added Amendment 3 section of MARKET_NEWS_RESULTS.md and doubtful.json. Thus the detailed Doubtful results were exposed before any independent computation, beyond the rounded numbers already supplied in the request. No other *_RESULTS.md file was intentionally opened. This exception is disclosed rather than calling the entire review blinded.

The small calculations below were evaluated independently in the tool's JavaScript runtime from the inspected formulas. They are **analytical/code counterexamples, not execution of the Python implementation or reproduction of historical study results**. No test suite is represented as passing.

## Study-by-study numerical comparison

“Not run” means no empirical match decision is possible. Reported targets below are Claude's table values, not numbers independently obtained here. Deterministic tolerance is agreement after rounding to four decimals; simulation tolerance requires a metric-specific Monte Carlo SE, not a sampling/bootstrap CI.

| Study and code revision | Matched? | Our empirical numbers | Reported comparison targets | Tolerance and audit notes |
| --- | --- | --- | --- | --- |
| **1. Deep home-win**, `555d5317`; protocol `741a13e7` | **No — blocked, not tested** | Not computed | 3,756 games; LL Elo .6332, deep .6354, margin-Platt .6397; four gate failures | Four decimals. Weekly feature/refit and past-prediction Platt structure inspected. Cold-start schedule fallback at this exact commit differs from the current branch; ESPN/PBP/injury inputs and full quote history were not rebuilt. |
| **2. Home-win v2**, `7fa8c37b`; protocol `18e98172` + `98519f2f` | **No — blocked, not tested** | H1–H4 and power not computed | H1 margin-Platt +.00669; H2 deep +.00124; H3 weights .367/.411; Friday CLV −.0012; N_LL 1,126, N_CLV 7 | Four decimals for LL/CLV. Earlier-season EP fitting, as-of feature builder and weekly point refits inspected. Coefficient intervals alone do not prove out-of-sample stacking improvement. |
| **3. Drive simulator**, `8e3cdb51`; protocol `067e5583` | **No — blocked, not tested** | Drive rebuild, fits, pilot and simulation metrics not computed; empirical MCSE unavailable | Drive LL −.16911; margin RPS +.0509; win LL .6401 vs .6332; stack .184; drive agreement 99.0% | Fits: four decimals; simulated metrics: three metric-specific MCSEs. Requires Study 2 feature/prediction caches in addition to raw PBP. Clock and OT limitations noted below. |
| **4. Kalshi props**, `60b72455`; protocol `31af0b08` | **No — blocked, not tested** | Pilot/pulls/replay/scoring not run; empirical MCSE unavailable | 1,242 ladders / 6,654 thresholds; K/base/market CRPS 1.0286/1.0707/.9978; K−base −.0421; settlement agreement 99.91% | Four decimals for deterministic scoring conditional on identical forecasts; three MCSEs for simulation-dependent metrics. Public GET code needs no Kalshi key. Untimestamped ACT roster and descriptive closing-line arm remain limitations. |
| **5. Market-anchored props**, `6ff6e5bc`; protocol `7964284b` + `4909f1ba` | **No — blocked, not tested** | Actual per-stat eligibility counts, b fits, deltas and placebo not computed | 762 ladders / six weeks; M1 +.0007 [−.0037,+.0051]; placebo .119; M2 −.0434 | Four decimals conditional on the same scored-threshold cache. The 500-row rule is implemented per stat and by earlier week; six weeks cannot be verified without that cache. Twenty-week power does not automatically characterize the six-week fitted cohort. |
| **6. Joint score**, `cc41214a`; protocol `94e455cc` + `db086e43` | **No — blocked, not tested** | Tau tuning, L/K/T metrics and lean correlation not computed | Tau 4/3; margin CRPS 7.507 vs 7.475; delta +.0323 [−.0296,+.0941]; K1 b=0; K2 +.0044; total lean Spearman −.168 | Four decimals for deterministic fits/scoring with fixed inputs. Gaussian final-iterate inconsistency and precision normalization require attention; ladder-shift direction is correct but its tails and interpolation are approximations. |
| **7. Usage / market news**, usage code inherited by `5bb093a1`, primary usage-result commit `d7c047c9` | **No — blocked, not tested** | C pilot/primary/2024 confirmation and A not computed. **B cannot be rebuilt: Travis-only ESPN snapshots are absent**, independently of executor failure | Target/carry gain +.0441/+.0513; 2024 +.0555/+.0585; kappa_K winner/spread/total +.010/.000/−.023; kappa_P winner/total +.111/+.223; 29 events | Four decimals for deterministic quantities with frozen inputs. A contains a probability-scale bug; C's oracle participates in cohort selection. Original B next-game bug is fixed on the reviewed branch, but other B mismatches remain. No empirical MCSE or new event count was obtained. |

### Monte Carlo tolerance

For 10,000 simulated binary outcomes, the maximum single-game win-probability MCSE is `sqrt(.25/10000)=.0050`. Three such SEs is .0150. Comparing two independent 10,000-path estimates gives a maximum difference SE of .007071 and a three-SE bound of .021213. These are **probability bounds only**, not RPS, log-loss, quantile or calibration tolerances.

For an empirical-CDF RPS, with true-outcome indicator H_k, a delta-method path contribution is `2 sum_k (F_k-H_k)(1[X<=k]-F_k)`; its path variance divided by N estimates the squared MCSE. Aggregate-game MCSEs require the appropriate weighted variance aggregation, or independent full-seed reruns. Props calibration and quantile extraction also need their simulation variability carried through. No empirical metric-specific MCSE was measured here. A fixed seed reproduces a draw; it is not an estimate of its uncertainty.

## Bugs and protocol mismatches

### 1. Study 7 A: winner logits are inserted into the spread probability ladder — substantive bug

[market_news_study.py, original lines 135–164](https://github.com/daboli69/going-long/blob/5bb093a1/research/nfl-ensemble-lab/scripts/market_news_study.py#L135) builds `wprice` as **logit** of normalized winner mids. That is appropriate for the winner-target regression. The same object is passed to `kalshi_value`, which inserts its value at margin .5 as though it were a **survival probability**, then applies probability isotonic regression. This persists in [the reviewed branch](https://github.com/daboli69/going-long/blob/752f3aa41a4aecdc3323dc74f6f2e903ff656a83/research/nfl-ensemble-lab/scripts/market_news_study.py#L135).

Independent counterexample: use margin strikes `[-7.5,-3.5,.5,3.5,7.5]` and survival probabilities `[.85,.70,.60,.40,.20]`. Their interpolated median is **+2.0000 points**. Replacing only the .60 winner probability with `logit(.60)=.4054651081` gives **−.7839 points**. Both sequences are already monotone, so isotonic fitting does not repair the mistake. Probabilities above about .731 also produce logits above 1, which then get clipped/pooled.

Keep separate raw winner-probability and winner-logit series, or invert the logit before inserting the winner point. Rebuild the panel, A power, placebo and A results under an explicitly recorded correction. The reported A spread coefficient is not independently validated by this audit.

There is a second literal-commit obstacle: original `5bb093a1` calls `.to_numpy()` on the result of `logit()`, which already returns a NumPy array. That expression would raise AttributeError. The reviewed branch removes `.to_numpy()`, but leaves the scale bug. Thus the original code revision and the branch used for a successful A run must be distinguished.

### 2. Study 6: Gaussian equations are conditional/empirical Bayes, and the last iterate is inconsistent

[forecast_core.py::_gauss](https://github.com/daboli69/going-long/blob/cc41214a/research/nfl-ensemble-lab/lab/forecast_core.py#L71) uses the correct conditional Gaussian form:

`A = X' W X / sigma² + prior_precision; C = A^-1; beta = C X' W y / sigma²`.

But each of three iterations updates sigma² **after** computing beta and C; it returns that updated sigma² with the **previous** beta/C. Prediction combines those different iterates. Recompute beta/C after the last update, preferably using a documented convergence rule. Do not silently change the frozen study and continue calling its old numbers reproduced.

Independent 2-parameter example: X rows `(1,−1),(1,1),(1,−1),(1,1)`, y `[0,10,2,12]`, raw weights `[.125,.25,.5,1]`, prior precision `[1e−6,1]`. Following the three inspected iterations gives final returned sigma² **24.4633899748**, but C[0,0] **6.1982288861**, computed at sigma² **24.4051414942**. Recomputing at the returned variance gives **6.2128201983**. This is an analytical demonstration, not a measured discrepancy on NFL games.

Additional specification qualifications:
- `w /= w.mean()` changes the absolute precision relative to fixed team-strength priors. The protocol specifies `w_i=0.5^(age/365)`; it does not state this normalization. It is not innocuous when tau is fixed.
- h/a receive precision 1e−6 rather than being literally unpenalized. This is a small stabilizer, but should be declared.
- The posterior is Gaussian **conditional on fitted variance and chosen tau**. Plug-in variance estimation and a residual rho do not constitute full Bayesian uncertainty over variance/correlation, nor the joint posterior of a single correlated-error multivariate regression.
- Training cutoffs and pilot-only tau selection are structurally chronological. Their empirical outputs were not run here.

### 3. Study 7 C: ACT belongs in the oracle, but must not select predictive-arm rows

[usage_study.py lines 127–164](https://github.com/daboli69/going-long/blob/5bb093a1/research/nfl-ensemble-lab/scripts/usage_study.py#L127) constructs A1b from the naive historical prior and pre-kickoff report weights. Current-week ACT enters A2/A2b, as disclosed for the oracle. However, the code skips a row if **any** of A0/A1/A2/A1b/A2b has no probability vector. An empty/missing current ACT roster, or one with no surviving historical candidate, can therefore remove a row from A0-versus-A1b based on oracle information.

This is an outcome/availability-dependent common-cohort restriction, even though current ACT is not a direct A1b feature. Establish A0/A1b eligibility without current ACT; score the oracle separately where it exists and report exclusions. Until counts are rebuilt, the size of any empirical effect from this issue is unknown.

ACT also does not necessarily mean the player actually takes a snap. An ACT-based oracle is an idealized roster-status comparator, not a guaranteed attainable forecast or a mathematically optimal ceiling.

Other C details:
- **Undeclared cohort gate:** at least three of the prior six team games must be in the current season (`MIN_SAME_SEASON=3`). The written candidate rule does not state this restriction. It removes early-season cases and needs explicit disclosure.
- **5% threshold:** `s0[i] >= .05` controls the descriptive news subgroup only. It does **not** select the candidates or filter the all-game A1b estimate. The predicate includes any reduced availability weight, including Doubtful/IR; “reported-out” should not be mistaken for Out-only.
- **Timestamp semantics:** `date_modified < kickoff`, then latest row per player, is correctly implemented for the chosen timestamp. It is evidence of a provider-reported modification time, not proof that an immutable record was available to the forecaster then. A retrospective latest-row file cannot recover overwritten earlier reports. Revised PBP/rosters have the same historical-vintage caveat.
- **Other bucket:** the union of all players with events in the last six games accounts for every historical event, making its historical noncandidate share zero by construction. The code then floors it to .005, not stated in the protocol. This changes absolute likelihoods; its common term cancels from paired gains on otherwise identical rows.
- Gain is event-count weighted, while reported mean LL fields are ordinary team-game means. They need not subtract to the reported gain. The bootstrap should state its estimand and, for a per-event ratio, recompute the event denominator in each resample.

Amendment 1 openly changes A1 to A1b after the 2018–2020 pilot. That is acceptable as a development amendment if committed before the 2021–2023 primary run. It does not convert the pilot into validation. The 2024 confirmation remains separate for the original C question; it is reused history for the later Doubtful question.

### 4. Study 7 B: the known next-game fix is correct; reproduction and remaining checks are separate

Original [5bb093a1::espn_events](https://github.com/daboli69/going-long/blob/5bb093a1/research/nfl-ensemble-lab/scripts/market_news_study.py#L299) restricts the “next game after the event” search to games still unplayed **at the time of replay**. Historical events can consequently attach to a later future game after their actual next game has finished. The reviewed [branch version](https://github.com/daboli69/going-long/blob/752f3aa41a4aecdc3323dc74f6f2e903ff656a83/research/nfl-ensemble-lab/scripts/market_news_study.py#L331) removes that filter and chooses the earliest kickoff after the event. That is the correct temporal fix.

It does not restore the absent 245 historical ESPN snapshots. Fresh pulls cannot recreate them. **Experiment B is not reproducible here**, and no 29-event count or reaction result is independently confirmed.

Remaining code/protocol discrepancies:
- The run filters events at least **seven** hours before kickoff, while the protocol says **six**. Specify and count the excluded 6–7 hour cases.
- Key-player selection uses 2026 snap rows with week less than the next game's week. It does not explicitly join completed games available before the event, and lacks the stated prior-season fallback for week 1. It should be audited against event timestamps, including in-game reports.
- The Benjamini–Hochberg implementation tests each sorted p-value against its own threshold, rather than applying the step-up rejection set. Example sorted p-values `[.01,.04,.041]`, m=3: standard BH at .05 rejects all three; this code flags the first and third only.
- Amendment 2 reduces B to a direction test, but mean-magnitude summaries and associated power/placebo still appear in the runner. Keep these descriptive; event-count power for a mean is not automatically power for a sign test.

### 5. Study 5: 500 earlier thresholds can explain six weeks, but does not prove that count

[props_market_model.py::walk_forward](https://github.com/daboli69/going-long/blob/6ff6e5bc/research/nfl-ensemble-lab/scripts/props_market_model.py#L46) requires **500 earlier thresholds of the same stat**, excludes all current-week rows from training and returns only rows where a correction was fitted. That implements the stated walk-forward minimum. The stack is pooled and refit on earlier rows.

Independent eligibility examples, 20 weeks and a single stat:
- 26 thresholds/week: **zero** eligible weeks;
- 36/week: first fit in week 15, **six** eligible weeks;
- 100/week: first fit in week 6, **15** eligible weeks.

Therefore six of twenty is plausible, but validating it requires the actual season/week/stat cumulative counts, surviving ladders and source exclusions. Rebuild and publish that attrition table. The 20-week power proxy cannot simply be applied to the six-week fitted cohort. The scoring code also recalculates SESOI on that cohort; reconcile this with the pre-fit power document's fixed .00998 benchmark before assigning materiality labels. All history remains descriptive.

### 6. Kalshi spread/total medians and the Study 6 ladder shift

[props_kalshi.py::game_environment / median_from_cdf](https://github.com/daboli69/going-long/blob/60b72455/research/nfl-ensemble-lab/lab/props_kalshi.py#L125) correctly orients home and away spread prices for **half-integer strikes**, fits a monotone CDF and interpolates a .5 crossing only when bracketed. This is a reasonable, explicitly preregistered market-summary convention. It is not a uniquely identified continuous median or mean of the underlying integer score distribution.

Check the strike semantics on raw markets: for integer strikes, complementing `P(M < −x)` gives `P(M >= −x)`, not `P(M > −x)`; ties/key-number mass then matters. The props environment also does not apply the full liquid-threshold filter to every environmental market, and winner mids may be older than ladder mids. Those choices and quote-age diagnostics should be exposed rather than described as equally liquid simultaneous observations.

[forecast_core.py::shifted](https://github.com/daboli69/going-long/blob/cc41214a/research/nfl-ensemble-lab/lab/forecast_core.py#L189) implements the correct sign: a positive delta evaluates survival at `c−delta`, raising exceedance probability. Translation preserves monotonicity. Linear interpolation smooths discrete atoms/key numbers, and endpoint clamping is a declared finite-ladder approximation, not a complete proper tail distribution.

Additional source issues:
- Duplicate strikes in forecast_core are collapsed by an **unweighted** mean of prices, then assigned summed weights. Exact weighted-isotonic aggregation would use the weighted mean.
- `fit_b` has a zero-denominator case when all d are zero; it should return zero in that no-disagreement case.
- Main conformal output pools seasons; it does not establish the initially stated “within two percentage points in every season group” condition. Amendment 1/power later makes coverage descriptive.
- The “one joint model” does not validate joint correlations of player props: the T-family still evaluates the existing K-arm simulator and does not infer its joint law from the new Gaussian score posterior.

### 7. Studies 1–4: chronological structure, limits and cold-start prerequisites

**Study 1:** weekly feature filters, earlier-season ridge priors, earlier-game fits and Platt calibration on earlier walk-forward predictions match the main design. Supplied nflverse EPA is itself a fitted historical product; Study 2 explicitly addresses this limit. The QB “first 250 career dropbacks” prior includes the entire boundary-crossing game, rather than truncating precisely at dropback 250. The inactive exclusion helper also pools all earlier inactive records for a team without restricting to the target game/week; harmless with the disclosed empty historical inactive archive, but unsuitable once such records accumulate.

**Study 2:** EP models use previous seasons only, and result features use P−4h while injuries use P. Forecast fits are batched at the week's earliest point. State that batching explicitly; it is less frequent fitting than a fresh per-game refit. Historical point checks perturb aggregate inputs; they do not independently prove contemporaneous raw-release availability. The full-sample stack coefficients/intervals are association checks on out-of-fold base predictions. The earlier props “stack pass” is in-sample at the meta-model level; it must not be promoted as an out-of-sample stack-performance pass. The corrected later study refits the meta-model walk-forward.

**Study 3:** field/team multinomial features, decay weights, whole-week cutoffs, OPP_TD retained possession and identity-based seeds match the intended design. In the simulator, points are credited **before** sampled duration is compared with remaining time. A scoring drive can overrun the horn but still score; inspect this with a short-clock synthetic test. Its OT first-possession TD rule follows the frozen old rule, not the changed 2025 regular-season rules. These are model limitations separate from numerical matching.

**Study 4:** K uses dated market environments; A explicitly uses undated games.csv lines and stays descriptive. Both arms use historical ACT roster information without publication receipts; “as-of replay” is conditional on this disclosed roster oracle. Scoring excludes nonbinary settlements and uses Kalshi's binary result. The .9991 agreement is not verified here; final revised official stats and exchange settlement-vintage stats need not coincide. The actual CDF estimate from 99 quantiles is an approximation and requires Monte Carlo/quantile sensitivity.

Cold-start issues visible from code:
- At exact Study 1 revision `555d5317`, [fetch_season](https://github.com/daboli69/going-long/blob/555d5317/research/nfl-ensemble-lab/scripts/xgb_home_win.py) has cache fallback only. The reviewed branch adds the games.csv fallback and catches non-JSON ValueError. Do not assume that newer fallback exists in every frozen code worktree. Apply any transport-only backport explicitly and retain its diff/provenance.
- Study 3 reads Study 2's `features_t90.parquet` / `wf_t90.parquet`; it does not build them itself.
- Study 4 reads the earlier Kalshi player inventory, winner-history cache and step-0 report. Its listed commands alone do not create all of these on a fresh clone. Study 5 needs scored_thresholds and replay outputs; Study 6 needs those plus its pilot artifacts; C directly reads PBP/roster/injury parquet files.
- Keep a full Git clone for GOING quote extraction. GitHub file reads used here are not a substitute for that history.
- These loaders use live/mutable upstream files and current-season/latest-played-game logic. Matching the old cohort and four-decimal metrics requires original cutoff/cohort and input-vintage hashes, not just code commits. Do not silently include newly finished games or reuse derived caches produced by different code. Sharing immutable raw downloads is different from sharing derived EP/model caches.

## Task 2: review of a8e04c68

**Source-level logic: consistent with the authorized manual-shadow change. Runtime/test status: not run. Empirical Amendment 3 gains: not independently reproduced.**

The [manual shadow](https://github.com/daboli69/going-long/blob/a8e04c68/research/nfl-ensemble-lab/lab/props/injury_adjusted.py#L21) adds lowercase `doubtful` to its exclusion set, retains Questionable/unknown, uses existing within-position redistribution and refuses an excluded/unverified starting QB instead of inventing a replacement. Its result metadata records `availability_rule`. Existing snapshot/freshness/conflict gates and write-once result behavior remain.

[weekly.availability](https://github.com/daboli69/going-long/blob/a8e04c68/research/nfl-ensemble-lab/lab/props/weekly.py#L59) adds `out_statuses=("Out",)`; the ordinary archive caller does not pass a different value. Default behavior is therefore unchanged on source inspection. Once INA rows exist, the ACT branch remains authoritative, regardless of this optional parameter.

The [changed test](https://github.com/daboli69/going-long/blob/a8e04c68/research/nfl-ensemble-lab/tests/test_injury_adjusted.py#L43) now checks Doubtful removal and retains the Questionable/unknown cases. Replacing the old contrary Doubtful expectation is appropriate. Existing tests inspect redistribution, missing QB, stale/conflicting evidence and immutable originals. None was executed here. Missing targeted coverage should include:
1. weekly default retains Doubtful, while the explicit optional tuple removes it before the INA branch;
2. prior-week fallback and official ACT/INA precedence under that tuple;
3. a Doubtful starting QB blocks the shadow;
4. every successful revision records the rule, and the prospective stream retains its original rule/bytes.

One metadata issue for future adoption: the weekly rule strings still say “minus injury-report Out” even when a caller supplies Out plus Doubtful. A new procedure must record the effective statuses and rule/version accurately.

Amendment 3's registered decision is specifically about the manual shadow, and its source code implements the stated pooled-positive-CI and positive-split conditions. The quoted target/carry gains +.0071/+.0121 are **reported**, not confirmed by this review. C's cohort/availability caveats apply, and zero versus .05 was not directly established as an optimal weight merely because both beat weight 1.

### Should the prospective archive adopt the same rule?

**Support a separately versioned prospective challenger after an explicit amendment; do not silently change the ongoing v2 test.** The current [PROPS_V2 preregistration](https://github.com/daboli69/going-long/blob/a8e04c68/research/nfl-ensemble-lab/docs/PROPS_V2_PREREGISTRATION.md) explicitly keeps Doubtful/Questionable in before official inactives. Its archived evidence must remain under that procedure.

Before adopting a new epoch, Travis should amend that document to specify the effective date, Out/Doubtful weights, official-inactive precedence, timestamp/freshness policy, missing/replacement-QB handling, metadata and the future comparison. Retain old forecasts and score the epochs separately, or run both rules on the same future games. Check distribution CRPS/coverage and the Doubtful-present subgroup; improved historical target/carry allocation LL does not itself prove improved yardage/reception distributions. Resolve the source/cohort issues and obtain an executable independent reproduction before treating the reported historical gains as verified.

## Required continuation when execution is restored

Clone the full repository; use isolated worktrees at the table's code revisions, Python 3.12 and the pinned requirements. Rebuild prerequisites, pin the original observation window and record all raw hashes. Run each protocol command with outputs/logs saved before comparison; estimate simulation-specific MCSEs. Retain literal-code outputs separately from corrected-source sensitivity runs. Experiment B still requires the original ESPN snapshot archive: current API data cannot replace it.

The report does not authorize code fixes, model promotion, a new prospective rule, spending or a rerun on Travis's PC. It records the completed fallback audit and the specific reasons numerical validation remains open.
