# Claude handoff: NBA ensemble and King of the Court research
Prepared October 27, 2026. This document describes the delivered work and the user's reported Windows installation. It is a continuation record, not evidence of a validated betting advantage.

## 1. Read this first

The user's project is at:

    C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble

The delivered research is installed separately at:

    C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble\updates\2026-10-27-dca2756e533d

**Files were verified on Windows by the installer. Integration with the existing Windows application has not been verified.** Do not tell the user the research is already connected to their app.

There are three distinct implementations/artifacts:

1. A six-algorithm, regular-season NBA outright-winner research module.
2. A separate King of the Court (KOTC) complete-slate correlated PRA simulator, with historical weighting, data reconciliation, research receipts, and separate popularity/prize scenarios.
3. An isolated distribution-diagnostic package that tested one FGA-pool repair against unchanged KOTC v1. The repair addressed a measured variance discrepancy but did **not** establish better predictive distributions or leader probabilities. Adoption is unsupported; v1 remains unchanged.

The latest proposed next research task is pregame participation and minutes uncertainty. That task was written up, **not implemented**.

The existing Windows app contains app.py, nba_lab, START_NBA.bat and other folders. Its source was not supplied for inspection. The cloud research implementation uses scripts/nba_winners, scripts/king_court and scripts/king_court_diagnostics. These are separate code structures. Inspect the actual Windows app before integrating anything.

The handoff was checked against the delivered ZIP's textual source, configs, registrations, reports and verification records, together with the Windows receipt pasted by the user. It does not claim fresh access to their computer, a new test run, a rerun of the historical experiments, or new independent verification of promotion terms.

## 2. User goals and binding scope

The user initially wanted an NBA winners ensemble resembling their NFL ensemble: six algorithms that present differing winner assessments and an auditable combined pick. Spreads, player props and other markets were future ambitions, not implemented scope.

The user then requested a KOTC simulation for a Tuesday regular-season promotion: identify the player with the largest points + rebounds + assists (PRA) total across the entire eligible slate. They want expected production, distribution intervals, sole/tied leader probabilities, role/opportunity evidence, and a distinction between popular selections and potentially attractive alternatives.

The active research direction is deeper statistical credibility, not a larger feature catalog. Preserve:

- Tuesday NBA regular-season PRA leaders only for the KOTC module.
- Free public data sources.
- Current season plus three immediately preceding seasons for KOTC player/team estimates.
- More per-game weight for newer seasons and more recent evidence; choose decay/shrinkage chronologically, rather than inventing percentages.
- Explicit handling of rookies, second-year players, incomplete histories and current-team role changes.
- Complete-slate leader probabilities, not shortlist-only comparisons.
- Current-team minutes/rotation role separated from transferable production rates.
- Data provenance and missingness; historical data retrieved now does not prove historical pregame knowledge.
- Performance probabilities separated from promotion-specific selection popularity.
- Bonus-bet face value separated from cash value.
- Implementation correctness separated from predictive validity.
- Original NBA winner and KOTC versions preserved while new research is evaluated separately.

The current-season-only instruction earlier in the conversation was explicitly superseded by current season plus three preceding seasons. Do not revert to current-season-only except as a comparison baseline.

No user-requested work here establishes authorization to place wagers, publish live recommendations, deploy a production model, create alerts or schedule jobs. Routine inspection, reversible local integration and necessary verification are within the user's stated project objective. Do not ask the user repeatedly to reauthorize ordinary work.

## 3. Exact Windows installation status

The user ran Install-NBA-Ensemble.cmd and pasted this receipt:

~~~json
{
  "status": "verified_versioned_install",
  "requested_destination": "C:\\Users\\travi\\OneDrive\\Documents\\ChatGPT\\GOING\\research\\NBA ensemble",
  "installed_root": "C:\\Users\\travi\\OneDrive\\Documents\\ChatGPT\\GOING\\research\\NBA ensemble\\updates\\2026-10-27-dca2756e533d",
  "files_verified": 58,
  "files_copied": 0,
  "manifest_sha256": "dca2756e533d0d3d3e4e6103ad2ea44eeb04d27dca41e6021742a8931479e222",
  "existing_conflicts_preserved": [
    ".gitignore",
    "README.md",
    "requirements.txt"
  ],
  "recorded_at": "2026-10-27T20:29:00.053930+00:00",
  "windows_file_copy_verified": true,
  "existing_app_integration_verified": false,
  "onedrive_cloud_sync_verified": false,
  "receipt_path": "C:\\Users\\travi\\OneDrive\\Documents\\ChatGPT\\GOING\\research\\NBA ensemble\\transfer-receipts\\nba-update-20261027T202900Z-082e7691.json"
}
~~~

Interpretation:

- The installer verified 58 payload files, including BUNDLE_CONTENTS.json. The manifest lists 57 other payload files.
- Zero files copied on that invocation means the verified files already existed at the selected versioned destination. It is not a report of a failed installation.
- Existing conflicting root .gitignore, README.md and requirements.txt were preserved. The research snapshot was not overlaid destructively on the app.
- The manifest hash identifies the delivered source-and-reports package. It differs from an earlier larger cloud snapshot.
- The timestamp is October 27, 2026 at 4:29 PM EDT.
- START_NBA.bat and the app were not integrated by this installer.
- OneDrive cloud sync was not verified; this does not prove sync failed.
- This receipt is user-supplied evidence. Claude should read the local receipt and verify the files if it has local access.

The Windows Explorer screenshot showed these existing root entries:

~~~text
.pytest_cache/
.venv/
__pycache__/
artifacts/
data/
docs/
models/
nba_lab/
reports/
tests/
.gitignore
app.py                 approximately 28 KB
README.md              approximately 11 KB
requirements.txt
START_NBA.bat           approximately 2 KB
~~~

The screenshot had hidden file extensions. These sizes/contents identify the preexisting app, not files created by the research transfer.

## 4. Download, repository and package identity

Public repository: https://github.com/daboli69/going-long

Transfer branch: nba-research-transfer-2026-10-27

Download:

https://github.com/daboli69/going-long/raw/refs/heads/nba-research-transfer-2026-10-27/NBA-ensemble-source-and-reports.zip

Branch README:

https://github.com/daboli69/going-long/blob/nba-research-transfer-2026-10-27/README.md

ZIP:

~~~text
Filename: NBA-ensemble-source-and-reports.zip
Bytes: 240435
SHA256: 57000fdd00c51e4903110d766144032564d7e3082270a300e20743424c5b3de9
Payload manifest SHA256:
dca2756e533d0d3d3e4e6103ad2ea44eeb04d27dca41e6021742a8931479e222
Original transfer commit:
f95f85debee48094822cdb1594c5340ca952089a
ZIP Git blob:
a14e971f8312f4b36bb30cc4783097c2f966b509
~~~

**The transfer branch is a download branch, not an application development branch. Do not merge its root tree into main.** Its original tree contained a ZIP, README and checksum file, rather than the normal application source tree. This handoff is an additional document on that branch. Download the package and integrate deliberately into the user's local project.

The source-and-reports ZIP deliberately excludes raw .cache inputs. It includes code, tests, frozen configs, plans, reports, audit summaries, plots, the installation helper and portable workspace instructions. It cannot reproduce every historical comparison offline without recovering the raw data and receipts.

The larger original cloud snapshot was not the package installed on Windows:

~~~text
Original cloud project: /workspace/going-long
Consolidated full snapshot: /workspace/going-long/research/NBA ensemble
Full snapshot: 124 files; 262474893 payload bytes, approximately 250 MB
Full-snapshot manifest SHA256:
f2f330a8337b7177c25849793bdf8c3cba98ac46e98d8549e1dce715f943f324
Full ZIP: NBA-ensemble-updates-2026-10-27-verified.zip
Full ZIP bytes: 74072330
Full ZIP SHA256:
139e7daddcd9b1aed75cd6a547d2bfb93e9cb42fd31682045176c92d9417e45c
~~~

That larger bundle was difficult to access through chat; the smaller GitHub package was created for reliable transfer. Do not claim that the original cache is already on Windows.

The cloud work was developed in /workspace/going-long, on a branch named work. The original research files were not all committed to the main application repository. The transfer ZIP, not main, is the delivered source of truth for this work.

## 5. First actions for Claude with local filesystem access

1. Read applicable local AGENTS.md and CLAUDE.md files at the project root and ancestor directories.
2. Read the user receipt and confirm the versioned installation path.
3. Verify BUNDLE_CONTENTS.json SHA256 against the receipt; then verify every listed payload file's size and SHA256.
4. Inventory the existing app.py, nba_lab modules, START_NBA.bat, dependencies, data/artifact formats and tests. Check git status if this folder is a repository. Preserve unrelated local edits.
5. Read the installed research AGENTS.md, README.md, NEXT_RESEARCH_TASK.md, configs, specification, source audit and distribution report.
6. Run the delivered tests in an isolated environment from the installed research root.
7. Establish what can run with delivered files versus what requires missing caches, fresh source access, exact pregame manifests or unresolved terms.
8. Use a small adapter or subprocess with the correct working directory for integration. Do not overwrite the original app, requirements or frozen research to force imports to work.
9. Keep the FGA candidate experimental/inactive. Do not call the diagnostic grid choice a valid live parameter-selection receipt.
10. Report integration verification separately from research validation. A working import or button is not a calibrated model.

The user does not need to reinstall the ZIP merely to use this handoff.

## 6. Runtime and basic verification

Recorded distribution experiment runtime:

~~~text
Python 3.12.14
NumPy 2.5.4
Polars 1.44.2
Platform Linux
~~~

The portable root requirements are:

~~~text
numpy>=2,<3
scikit-learn>=1.5,<2
polars>=1,<3
pyarrow>=18
requests>=2.31,<3
matplotlib>=3.8,<4
~~~

These are ranges, not a complete reproducibility lock. Windows may resolve different versions. Preserve actual runtime/version receipts. A fresh environment avoids changing the app's existing .venv.

Illustrative PowerShell commands; inspect local policy and Python availability first:

~~~powershell
$NbaRoot = 'C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble'
$ResearchRoot = Join-Path $NbaRoot 'updates\2026-10-27-dca2756e533d'
Set-Location -LiteralPath $ResearchRoot

Get-Content -LiteralPath (Join-Path $NbaRoot 'transfer-receipts\nba-update-20261027T202900Z-082e7691.json')
Get-FileHash -Algorithm SHA256 -LiteralPath '.\BUNDLE_CONTENTS.json'

py -3.12 -m venv .venv-research
$NbaPython = Join-Path $ResearchRoot '.venv-research\Scripts\python.exe'
& $NbaPython -m pip install -r requirements.txt
& $NbaPython -m unittest tests.test_nba_winners tests.test_king_court tests.test_king_court_diagnostics -q
& $NbaPython -m scripts.king_court --help
& $NbaPython -m scripts.nba_winners --help
~~~

Do not modify Windows execution policy unnecessarily. Directly invoking the environment's Python avoids requiring Activate.ps1.

Expected historical verification result: **48 tests passed**: 11 winner, 24 KOTC, 13 diagnostics. That was the recorded cloud result, not a claim that a new local Windows run has already passed.

Research code resolves config/research paths relative to its package root; several .cache paths are relative to the current working directory. The generic package name scripts can collide with another repository's scripts package. The original Going Long repository also has unrelated scripts. Avoid global sys.path changes or copying modules into arbitrary locations. A subprocess with explicit executable and cwd is a reasonable initial boundary while the existing app is inspected.

No installer action installed pip dependencies, migrated app data, integrated the launcher, verified OneDrive, created scheduled tasks, merged Git branches or deployed a model.


## 7. Source map and reading order

Paths below are relative to the installed research root.

### NBA winner module

| Path | Responsibility |
| --- | --- |
| scripts/nba_winners/__main__.py | fetch, ingest, backtest and predict CLI |
| scripts/nba_winners/data.py | canonical schedules/results, source identity, NBA filtering |
| scripts/nba_winners/features.py | earlier-only team/Elo features and result lag |
| scripts/nba_winners/models.py | six algorithms, earlier-OOS weights, debate records |
| scripts/nba_winners/evaluation.py | chronological replay and paired diagnostics |
| config/nba_winners_v1.json | frozen winner protocol |
| docs/NBA_WINNERS.md | winner assumptions, examples, validation and limitations |
| tests/test_nba_winners.py | 11 final recorded tests |
| research/nba-winners/README.md | retained development score table; not a new evaluation |

### KOTC v1

| Path | Responsibility |
| --- | --- |
| scripts/king_court/__main__.py | data, registration, selection, simulation, freeze/settle/evaluate CLI |
| scripts/king_court/common.py | sealing, timestamps, receipts and shared helpers |
| scripts/king_court/data.py | free-source archive intake and schedule/box reconciliation |
| scripts/king_court/history.py | two-level recency, priors, role/rate profiles, team context |
| scripts/king_court/simulation.py | shared conditions, integer pools, leader and prize calculations |
| scripts/king_court/events.py | exact-ID NBA live JSON event/stint reconciliation |
| scripts/king_court/research.py | manifest checks, chronology, selection, settlement and evaluation |
| scripts/king_court/demo.py | anonymous, entirely synthetic example |
| config/king_court_protocol_v1.json | frozen research grid and gates |
| config/king_court_offer_2026-10-27.json | screenshot-derived date-specific rules and unknowns |
| docs/KING_OF_THE_COURT_SPEC.md | research-first preimplementation specification |
| docs/KING_OF_THE_COURT.md | implementation, inputs, commands and limitations |
| tests/test_king_court.py | 24 final recorded tests |
| research/king-court/source-audit.json | real archive coverage and missingness |
| research/king-court/illustrative-output.json | synthetic output, never a real-player recommendation |
| research/king-court/README.md | initial audit/result narrative |

### Distribution experiment

| Path | Responsibility |
| --- | --- |
| scripts/king_court_diagnostics/archive_audit.py | parsed NBA event/lineup/box/possession evidence |
| scripts/king_court_diagnostics/dataset.py | eligible rolling history, complete diagnostic fields |
| scripts/king_court_diagnostics/pools.py | single paired empirical FGA-pool candidate |
| scripts/king_court_diagnostics/simulation.py | instrumented v1-equivalent simulator and explicit hooks |
| scripts/king_court_diagnostics/metrics.py | distributions, tails, leader events, paired uncertainty |
| scripts/king_court_diagnostics/challengers.py | point baselines and whole-game block challenger |
| scripts/king_court_diagnostics/experiment.py | frozen comparison execution |
| scripts/king_court_diagnostics/__main__.py | lock-code and compare CLI |
| docs/KING_COURT_DISTRIBUTION_AUDIT.md | frozen assumption audit |
| research/king-court/distribution-v2/PLAN.md | frozen diagnostic plan |
| research/king-court/distribution-v2/registration.json | actual-time dates, original hashes, seeds and scope |
| research/king-court/distribution-v2/code-lock.json | diagnostic code lock |
| research/king-court/distribution-v2/component-decision.json | single-repair choice |
| research/king-court/distribution-v2/source-evidence.json | fetched source URLs, SHA256s, evidence counts |
| research/king-court/distribution-v2/comparison-summary.json | full retained summary, both seeds, intervals and strata |
| research/king-court/distribution-v2/verification.json | preservation, tests, hashes and adoption verdict |
| research/king-court/distribution-v2/README.md | final experiment evidence report |
| research/king-court/distribution-v2/distribution-diagnostic.png and .svg | retained scientific plot |
| tests/test_king_court_diagnostics.py | 13 final recorded tests |

Portable root files also include requirements.txt, AGENTS.md, README.md, NEXT_RESEARCH_TASK.md, BUNDLE_CONTENTS.json, scripts/__init__.py and tests/__init__.py. The package's installer is install_nba_ensemble.py with Install-NBA-Ensemble.cmd and START-HERE.txt. Use the manifest for the exact payload inventory and hashes rather than assuming every file in an extracted download is a research payload file.

## 8. NBA winner ensemble: what was implemented

Version nba-winners-research-v1; registered October 23, 2026. Target: regular-season outright winner, including overtime. No odds, player, injury, lineup, possession, spread, prop, travel or betting-return model was added to this version.

Six deterministic statistical voters:

| Voter | Specification |
| --- | --- |
| Elo | K = 20; home advantage 65 rating points |
| Logistic regression | standardized inputs; C = 1; max_iter = 1000 |
| Histogram gradient boosting | max_iter = 100; max_leaf_nodes = 7; L2 = 5 |
| Random forest | 150 trees; max_depth = 5; min_samples_leaf = 20; n_jobs = 1 |
| Gaussian naive Bayes | standardized inputs; var_smoothing = .1 |
| Ridge margin | standardized inputs; alpha = 100; predicted margin converted through a Gaussian residual approximation |

Random seed 42. Probabilities clipped to [.01, .99]. Ridge residual standard deviation is fitted from training residuals with a floor of 1; this is not an out-of-sample calibration method.

The 12 features are:

~~~text
elo_difference
season_margin_difference
last5_margin_difference
last10_margin_difference
win_rate_difference
points_for_difference
points_allowed_difference
margin_sd_difference
rest_difference
back_to_back_difference
games_last4days_difference
home_court
~~~

Elo and season team summaries reset at season boundaries. Supervised training uses chronological earlier examples. At least 300 training games and five earlier games per team are required. Refit cadence is 30 days.

Historical completed scores are delayed 36 hours and must be available strictly before the prediction origin. Rest/congestion comes from earlier scheduled tipoffs, without exposing embargoed scores. Daily weighting uses a UTC-midnight boundary. These guards prevent several leakage paths but do not prove historical archives have never been revised.

Combination weights are inverse earlier out-of-sample Brier losses, shrunk toward .25 with 100 pseudo-games; weights normalize to one. Initial weights are equal. The “debate” is an auditable record of the six unchanged forecasts, strongest home/away cases, weights, contributions, vote counts and disagreement. It is not an LLM conversation or six independent data confirmations.

Probability range at least .25 flags large disagreement. A winning-side probability below .55 flags a close game. Exact .5 uses designated home as a disclosed tie-breaker. Agreement is not confidence or proof of calibration.

Canonical game fields are game ID, ending-year season, UTC tipoff, teams, neutral flag, completion status and final scores. Invalid/tied final NBA scores, team ambiguity and conflicting game records fail. Team aliases include GS→GSW, SA→SAS, NY→NYK, NO→NOP, UTAH→UTA and WSH→WAS.

Regular-season filtering explicitly excludes exhibitions/All-Star games, playoffs/play-in, preseason, nonfinal games and the non-counting NBA Cup final. Do not assume an upstream season-type flag alone handles every exhibition. Counted Cup games remain eligible regular-season history.

### Winner evidence actually obtained

Development ending years: 2023, 2024, 2025. Registered holdout ending year: 2026. The winner CLI keeps that holdout locked. Ending-year 2026 was later accessed as KOTC history at the user's request; therefore do not broadly say this season has never been inspected anywhere in the project.

Retained development replay: 3,125 forecast games.

| Model | Brier | Log loss | Accuracy |
| --- | ---: | ---: | ---: |
| Elo | .219406 | .628177 | 64.2560% |
| Logistic | .215709 | .620219 | 65.6320% |
| Gradient boosting | .228911 | .651993 | 62.7520% |
| Random forest | .218028 | .625351 | 64.4160% |
| Naive Bayes | .262637 | .869145 | 64.0640% |
| Ridge margin | .214671 | .617392 | 65.3440% |
| Ensemble | .216804 | .622215 | 64.8320% |
| Equal-weight blend | .217060 | .622828 | 64.7360% |
| Expanding home frequency | .248270 | .689720 | 54.9440% |

These are retained development diagnostics, not a fresh holdout test or proof of profitable picks. The ensemble did not beat every component. Do not hide that logistic/ridge have better displayed development Brier.

Evaluation includes paired losses against equal weighting, Elo and expanding home frequency, whole-UTC-date bootstrap intervals, reliability bins, coverage/exclusions and forecast correlations. The frozen promotion criterion requires later untouched evidence, upper 95% paired Brier delta below zero versus all three baselines, nonworsening log loss, calibration review and explicit promotion approval. No promotion occurred.

Fresh prediction guards include actual retrieval receipts no older than 36 hours, next-24-hour scheduled games and minimum team warmup. Re-ingesting an old file does not certify fresh underlying data. No automated forecasts were scheduled.

## 9. KOTC offer interpretation

The user's two screenshots identify the October 27, 2026 offer EP70GG. The config is a screenshot transcription with incomplete official terms, not a fully verified legal ruleset.

Confirmed in visible screenshot text:

- Pool: $1,000,000 in bonus-bet face value.
- Select the day's highest points + rebounds + assists player.
- One single-use qualifying token per customer, issued after opt-in; select it in the betslip before placement.
- Qualifying wager: pre-match NBA player-prop single, or same-player NBA parlay with all legs involving that player.
- Minimum $5 stake; each leg -200 American odds or longer.
- Funds from cash balance or DK Dollars.
- Token expires at the start of the final October 27 game; each wager separately must be pre-match.
- Customers on any tied leading player share the same overall pool, equally across qualifying customers.
- Award following day/within 24 hours; bonus bets expire seven days after issuance and are nonwithdrawable.
- Excluded: ordinary parlays, SGPx, odds boosts, live, cashed-out or voided bets and legs on ineligible games.
- Screenshot jurisdiction/age language is transcribed in the attached offer config. It was not independently verified.

Not confirmed by complete accessible terms:

- Whether the qualifying prop wager must itself win.
- Exact eligible game/player IDs and how exceptional game exclusions work.
- Explicit overtime, postponement/cancellation and statistical-correction treatment.
- Complete account-specific terms.
- Identical recurrence and prize pool on future Tuesdays.

Visible text does not explicitly require the original prop to win. The config leaves requires_prop_win null; do not silently turn that into a verified false. If a future offer explicitly requires a winning prop, current payout functionality rejects that unsupported joint qualification assumption.

The user expects a Tuesday regular-season recurrence. An operator editorial search result corroborated Tuesday marketing, but the full linked page could not be used to verify account-specific terms. Do not inherit the October 27 offer automatically on later dates, or mix other dates' top-three/smaller-pool promotions into this one.

Source leads:
https://sportsbook.draftkings.com/promos/king-of-the-court
https://dknetwork.draftkings.com/2026/10/27/draftkings-king-of-the-court-value-picks-for-tuesday-10-27-26/

Access/indexing was incomplete; indexed player text was inconsistent and not used as player evidence. The original screenshots were not retained as binary files in the delivered source package; the transcription/config and docs were retained.

The statistical whole-slate cutoff is before the earliest game. The token's later deadline does not permit a pregame model to use already-played games or later news for an earlier whole-slate forecast.

## 10. KOTC history, recency, priors and context

Version king-court-research-v1; registered October 27, 2026.

### Season boundaries and information boundary

Use ending-year convention throughout the canonical data: 2027 means 2026–27. At that target season, use 2024, 2025, 2026 and season-to-date 2027. For a historical target ending in 2026, use 2023–2026. Do not reuse the 2027 window for every historical example.

Some NBA Stats wrapper loader arguments use the season's starting year while released archive filenames/columns use ending year. SportsDataverse ESPN archives use ending year. Explicitly verify these conventions at intake.

All training examples use only earlier information, subject to the 36-hour historical result lag. Source retrieval time, publication/known time and game time are distinct.

### Two levels of recency

Frozen candidate grid:

~~~text
season_decay: .35 or .65
within-season half-life: 30 or 90 days
prior_games: 5 or 15
~~~

There are eight combinations and no silently selected default.

For season s and target season S, the season multiplier is season_decay^(S-s). Within a season, weight decays as 2^(-days / half_life). Current season anchors at prediction origin; prior seasons anchor at their latest eligible observation, avoiding accidental compounding of the same cross-season age twice.

Newest-season observations receive greatest per-game season weight. With a tiny current sample, an older full season can still contribute greater total mass. Disclose both facts; do not promise that total current-season weight is always the largest.

Report effective sample size (sum w)^2 / sum(w^2), per-season contribution, prior contribution and uncertainty. ESS is a weight diagnostic, not the number of independent slate experiments.

### Experience and role

- Verify NBA debut season. The first downloaded row is not a debut.
- Rookies receive a transparent historical NBA rookie cohort prior, not invented prior NBA seasons.
- Second-year players use their rookie season as supporting history; current evidence gets greatest per-game season weight.
- Cohorts use experience, position and five-appearance development-stage bins where at least 20 cohort observations are available, with disclosed broader fallbacks.
- Established experience uses its appropriate cohort; incomplete histories are not zeros.
- Current-team/current-season role minutes are modeled separately from transferable player production rates.
- Actual explicit DNP rows are zero-minute observations; missing/unknown minutes are not.
- The ESPN active flag is not a trustworthy pregame participation record; some positive-minute rows carry false.
- Explicit pregame minute overrides require mean, standard deviation, source and known_at.
- OUT has zero minutes. Uncertain statuses require explicit complete conditional scenarios; no arbitrary “questionable = 50%.”

The implementation supports these priors. The real-data studies did not have verified historical debut metadata and therefore did not empirically validate rookie/second-year performance.

### Team and matchup context

Box possession proxy is the average of each team's FGA − OREB + TOV + .44 × FTA. Pace is normalized to 48 minutes. Weighted/shrunk context includes team and opponent attempt rates, scoring efficiencies, assist/made-field-goal rates and rebound/miss capture rates.

Attempt-rate matchups use symmetric geometric combinations. Efficiency adjustments use a disclosed half-strength opponent logit shift relative to baseline. These are approximations, not experimentally established universal basketball effects.

No fitted five-player lineup interaction model or arbitrary injury/matchup “boost” was added. Lineup/availability affects known field/rotation context; exact contextual effects remain to be validated.

Recent trend descriptions compare current-team last five games with the preceding 15, requiring at least three observations per group. They show minutes, FGA + .44FTA per minute, PRA/minute and shooting. A shooting streak is not automatically a sustained role improvement or an extra model multiplier.


## 11. What the joint PRA simulator does

This is an aggregate correlated simulator, not a possession-by-possession reconstruction of five-player stints.

For each eligible game and Monte Carlo draw:

1. Draw overtime length from the earlier empirical overtime distribution. This historical mixture is not a fitted matchup-specific overtime probability.
2. Draw shared game pace/possessions from a lognormal distribution and scale for simulated game length.
3. Draw available players' positive minutes from lognormal distributions, then normalize/cap the rotation so each team has five times game length in player-minutes, with each player no greater than game length. OUT players remain zero.
4. Original v1 independently draws team FGA and FTA pools from Poisson distributions conditional on shared pace/team context.
5. Allocate integer player opportunities through minute × production-rate weights. FGA/FTA rates have gamma uncertainty. Allocations conserve each team pool.
6. Draw three-point share and conversion probabilities using weak Beta(1,1) numerical priors, then binomial makes. Points respect 2×2PM + 3×3PM + FTM.
7. Allocate competing rebound totals from simulated missed-shot pools, with empirical capture/uncredited fractions.
8. Allocate assists from actual made-field-goal opportunities, excluding the shooter from receiving their own assist.
9. Sum integer points + rebounds + assists and compare **every eligible slate player** in the same draw.

Shared game conditions, common team pools and allocation constraints induce player dependence. That does not establish that all dependence, lineup interactions or high-PRA tails are correct.

Important remaining assumptions:

- Positive-minute lognormals do not include a fitted available-player DNP/participation mixture.
- Rotation normalization constrains totals but is not a learned substitution/closing-lineup model.
- Team FGA/FTA Poisson draws can misrepresent conditional opportunity variance.
- Every missed free throw was treated as part of a rebound proxy pool in v1; nonfinal/technical misses are not all live rebound opportunities.
- Credited assists are not potential assists; no tracking data was manufactured.
- Weak Beta priors and fixed matchup blending are disclosed numerical choices, not chronologically fitted effects.
- The overtime mixture, pace distribution and residual upper-tail behavior remain incompletely verified.
- Simulation intervals do not include every source of parameter, availability or structural uncertainty.

### Output contract

Per player: expected P/R/A and PRA; meaningful quantiles (10th, median, 90th); minute mean/interval; sole-leader, tied-leader and inclusive-leader probabilities; finite Monte Carlo errors; role/opportunity/context evidence; effective sample size; season shares; trend descriptions; missingness and limitations.

Definitions:

- Sole leader: strictly exceeds every other player.
- Tied leader: equals the maximum and at least one other player shares it.
- Inclusive leader: sole or tied leader.
- Fractional tie credit: 1 divided by number of tied players in that draw.

Inclusive probabilities can sum above 1. Fractional tie credits sum to 1 but are **not customer prize shares**. Do not substitute one for the other.

All implemented outputs retain blocked_research_only. Neither synthetic examples nor the historical diagnostic removed the readiness blocks.

### Complete-field and freeze safeguards

Prospective manifests require independent retained field evidence, not a participant list reconstructed from final boxes. Exact game/player identities, field/roster completeness, known times, regular-season schedule and whole-slate Tuesday date must match. Prospective sources must be current, ordinarily no older than 36 hours. Every player needs verified debut metadata. At least five available players are required per team; unknown availability cannot be guessed away.

Store the original field source, content hash and source timestamps. If an unselectable player can still become the statistical PRA leader under actual rules, that player remains in the leader field even though no entry value is offered for them.

freeze uses actual process UTC time and requires a prospective origin before the earliest tipoff. Retrospective work cannot be relabeled as a real historical freeze.

Sealed JSON plus NPZ samples preserve source/code hashes and the frozen complete field. Outputs use new paths rather than overwriting prior receipts.

Settlement requires official completed outcomes for all frozen games/players, including true DNP zeros. Unresolved/postponed/voided cases remain pending. They are not quietly dropped to produce a winner. Resolution of exceptional promotion cases still depends on exact terms.

Evaluation reports distribution scores, interval coverage, leader-event scores and reliability with whole-slate uncertainty. The registered v1 minimum is eight earlier development slates for selection and 20 evaluation slates for an initial evidence gate. Those are minima, not statistical guarantees.

## 12. Popularity and customer-level prize sharing

No measured promotion-specific selection percentages were obtained. Famous-player “chalk,” DFS ownership, general betting popularity and social mentions were not substituted as measured KOTC selection probabilities.

Two separate supported input types:

1. Explicitly hypothetical ownership scenarios: a complete player probability vector summing to one, an integer number of other entrants, clearly labeled assumptions.
2. Actual promotion qualifying-selection counts, if supplied: exact offer/date, known-before-origin source, complete field, and explicit definition that counts concern other qualifying customers.

No such actual counts were supplied in this work.

If i is the selected player and L is the set of tied PRA leaders, the scenario payout in a simulated draw is:

    B × I(i belongs to L) / (1 + sum of N_j for every j in L)

B is the verified date-specific bonus-bet face-value pool. N_j counts OTHER qualifying customers selecting j. The additional 1 is this hypothetical customer's single qualifying entry.

A tie does not split the pool equally by player. It combines qualifying customers on every tied leader. Unknown crowd counts can be sampled as a multinomial under explicit scenarios; expected reciprocal share is not reciprocal expected count.

Separate:

- Probability the chosen player earns a share.
- Conditional size of that bonus-bet face-value share.
- Original wager risk/return and qualification.
- Conversion value of nonwithdrawable, expiring bonus bets.

The module does not estimate cash-equivalent EV or manufacture expected dollars when ownership/entrant totals are unknown. Date-specific terms are mandatory. These functions were kept unchanged during the FGA experiment and were not used to justify a repair.

## 13. Free sources: what was actually used, what remains a lead

User-requested tools/sources:

- hoopR: https://github.com/sportsdataverse/hoopR
- sportsdataverse-py: https://github.com/sportsdataverse/sportsdataverse-py
- nba_api: https://github.com/swar/nba_api
- pbpstats: https://github.com/dblackrun/pbpstats
- PBP Stats: https://www.pbpstats.com/

These are not five independent basketball datasets. Wrappers and derived sites can share NBA/ESPN upstream feeds. Agreement across overlapping copies is not independent confirmation.

Actual data access primarily used free public SportsDataverse GitHub release assets. The sandbox could access GitHub/PyPI; direct NBA/ESPN/PBP Stats access was restricted/unavailable in parts of the work. Do not claim every named library was installed and wired as an active live provider.

ESPN ending-year release URL patterns:

~~~text
https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_schedules/nba_schedule_{S}.parquet
https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_{S}.parquet
https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_team_boxscores/team_box_{S}.parquet
https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_pbp/play_by_play_{S}.parquet
~~~

Additional NBA-derived ending-year 2026 archives accessed for the diagnostic:

~~~text
nba_stats_pbp/nba_play_by_play_2026.parquet
nba_stats_game_lineups/nba_lineups_2026.parquet
nba_stats_possessions/nba_possessions_2026.parquet
nba_stats_player_boxscores/player_boxscores_2026.parquet
nba_crosswalk/nba_schedule_crosswalk_2026.parquet
nba_crosswalk/nba_player_crosswalk_2026.parquet
~~~

Each suffix follows the same SportsDataverse releases/download/ prefix.

These are parsed legacy NBA records and producer-inferred lineups/possessions, not retained native original vendor JSON and not independently observed lineup seeds. Native vendor JSON, pregame availability receipts, verified debut metadata and potential-assist tracking were unavailable in the retained evidence.

Preserve raw bytes where accessible, URL, underlying provider, retrieval time, publication/known time if verifiable, content hashes, schema versions, failures and missing fields. A page being publicly viewable does not prove reliable automated access, historical versions, free redistribution or pregame freshness. Use normal authorized public access; report access failures instead of bypassing controls.

### Initial four-season source audit

Ending-year accepted games:

| Ending year | NBA season | Accepted games |
| --- | --- | ---: |
| 2024 | 2023–24 | 1,229 |
| 2025 | 2024–25 | 1,173 |
| 2026 | 2025–26 | 1,195 |
| 2027 | 2026–27 to retrieval | 51 |
| Total | | 3,648 |

94 regular final games were withheld by reconciliation/missing-data checks. Separate exclusion rows included 283 outside regular NBA field, 11 nonfinal/scheduled, three Cup finals, 18,000 explicit DNP player rows, 103 unknown-minute rows and three invalid team-stat rows. These are different units/categories; do not add them all as independent missing games.

An earlier exploratory 2025 acceptance count was higher before stricter unknown-minute checks. The retained final audit's 1,173 is the relevant count.

Missing evidence: historical pregame rosters and injuries, verified debut metadata, actual potential assists/rebound tracking chances, promotion selection counts and full date-specific terms.

That original v1 audit recorded zero event-reconciled games. The later diagnostic added separate event evidence without rewriting old receipts. Do not interpret the old zero as contradicting the later audit.

### Live JSON reconciliation versus legacy archive audit

Original events.py expects NBA live JSON, exact game/player/team crosswalks, conflict-aware actionNumber handling, and supplied period-start fives for stint reconstruction. Missing lineup seeds prevent a claim of verified court time.

The later archive auditor handles a different schema: parsed legacy action rows, substitution descriptions, inferred lineup snapshots and record order. It uses explicit NBA/ESPN crosswalks, never approximate cross-provider ID/name matching.

Legacy records can share an action number because a producer splits related steal/block actions. order_index identifies unique records in that archive. Treating every shared action number as a duplicate caused false failures in an initial development auditor and was corrected before the comparison lock. Do not copy this identity rule blindly into the separate live-JSON parser.

Assist/substitution descriptions are accepted only with unique consistent within-team resolution. Ambiguous names are failures, not guesses. Legacy substitution person ID denotes the leaving player; an entrant may be parsed from text such as “SUB: Eason FOR Smith Jr.”

Exact NBA minute reconciliation tolerates approximately two seconds; comparison to rounded ESPN minute boxes has a separate approximately 61-second tolerance. A producer-inferred five is still an assumption even if reconstructed totals agree.

### Actual event evidence

Across 1,230 regular-season NBA games:

| Check | Passing games |
| --- | ---: |
| Credited event stats agree with NBA boxes | 1,186 |
| Substitution/lineup reconstruction agrees with exact NBA minutes | 1,097 |
| Both checks | 1,095 |
| Canonical ESPN box agreement with mapped NBA boxes | 1,138 |

The source-evidence receipt reports 1,185 game-crosswalk matches in its audit context. Do not confuse this with the 1,195 accepted games in the separate initial canonical season audit.

Free-throw miss classes:

- 6,327 nonfinal or technical misses: not live rebound chances.
- 6,175 ordinary final misses: potentially reboundable, not observed tracking chances.
- 42 ambiguous or retained-possession sequences.

This identifies a separate v1 rebound-proxy weakness. It was documented, not repaired alongside FGA.

The exact URLs, retrieval timestamps, byte lengths and SHA256s are embedded in the source-evidence appendix below. The audit concerns agreement among representations and accounting, not proof of predictive validity.

## 14. Frozen distribution diagnostic: design and single repair

Audit/plan registration time:

    2026-10-27T17:52:25.912442+00:00

The original KOTC source, offer/protocol and winner source were preserved: 17 baseline files. New candidate code was kept in scripts/king_court_diagnostics so it did not silently alter v1's source receipts.

Before candidate assessment, the plan specified comparisons of PRA distribution accuracy, dispersion, component correlations, upper tails, slate maxima, sole/tied/inclusive leaders, baselines and component ablations.

### Why FGA was selected

Original Poisson team FGA implies conditional variance equal to mean, about 89 attempts squared.

Development box data suggested residual variance around 39–41. That check alone was insufficient because the box possession proxy itself contains FGA. A corroborating earlier-development check used 367 games with reconciled event statistics and producer-counted possession groups:

~~~text
Poisson-implied variance:       88.864 / 89.411
Measured residual variance:    46.505 / 40.821
Residual-to-Poisson ratio:      .5233 / .4565
~~~

The possession grouping remains derived from the same NBA feed. This is corroboration with a different measurement construction, not an independent provider.

The discrepancy was measurable without inventing historical injuries. It was not claimed to be the largest source of PRA error.

### The only repair

Replace independent Poisson FGA draws with recency-weighted paired empirical conditional FGA residual ratios. Sample both teams' earlier residuals jointly, center them to preserve conditional means, stochastically round to nonnegative integer attempts, and report clipping.

Do not change FTA, minutes, availability, allocation, shooting, rebounds, assists or overtime in this experiment. A separate FTA override exists only for an oracle ablation. Candidate random sampling uses a separate reproducible stream (base seed + 101).

Checks require:

- AST equality after stripping the declared instrumentation/pool hooks.
- Exact original/candidate-disabled arrays for identical seeds.
- Integer pool accounting.
- Prior-only eligible residual data and rolling season boundary.
- Original source/protocol/registration hashes unchanged.

An empirical residual distribution has finite observed support. Better conditional variance does not prove correct unseen extreme tails.

### Registered periods and usable cohorts

Retrospective development: eight calendar Tuesdays, October 28–December 16, 2025. Seven usable complete slates / 34 games. December 16 had no regular-season NBA slate.

Retrospective assessment: 12 calendar Tuesdays, January 6–March 24, 2026. Six usable complete slates / 40 games / 1,046 player-games:

~~~text
2026-01-06: 155 player-games
2026-01-27: 184
2026-02-10: 105
2026-03-10: 289
2026-03-17: 210
2026-03-24: 103
~~~

Entire excluded slates:

~~~text
2026-01-13: missing/unreconciled espn:401810423
2026-01-20: missing/unreconciled espn:401810469
2026-02-03: missing/unreconciled espn:401810577
2026-02-17: no completed regular-season games
2026-02-24: missing/unreconciled espn:401810691
2026-03-03: missing/unreconciled espn:401810744
~~~

Four assessment dates / 757 player-games additionally pass event, stint and canonical/NBA box agreement for every game: January 6, March 10, March 17 and March 24.

All these archives had already been inspected. **These are reused posterior-predictive diagnostics conditioned on recorded postgame fields, not untouched pregame forecast replays.**

Historical origins were earliest tipoff minus 12 hours with the 36-hour result lag. The supporting 2023 archive was added so ending-year 2026 targets still use exactly their season-to-date plus three prior seasons.

All 1,046 experience labels are unknown because verified debut metadata was absent. The diagnostic adapter uses a disclosed common-position prior for unknown experience in both comparators. It is not a complete replay of the stricter prospective manifest contract. Rookie, second-year and established strata have zero verified observations.

### Parameter selection and fixed simulation settings

The diagnostic grid choice used earlier development mean-slate PRA CRPS, then MAE and deterministic grid order. Choice:

    season_decay .65; half-life 90 days; prior_games 5

This is separate from v1's registered MAE-based prospective selection. It is not a v1 selection receipt: reused fields, unknown experience and only seven complete development slates cannot pass the eight-slate prospective gate.

Development bootstrap selection frequency: 97% for this grid point, 3% for .35/90/5. This measures conditional selection stability, not posterior probability that parameters are correct.

Selection draws: 1,000. Assessment draws: 5,000. Selection seed: 271026. Assessment seeds: 271026 and 271027. No retuning on assessment outcomes and no favorable-seed selection.

### Future dates actually reserved

Future development: November 3–December 22, 2026, eight Tuesdays.
Future evaluation: December 29, 2026–April 6, 2027, 15 Tuesdays.

Exact dates are preserved in the registration appendix. As of the delivered record there are **zero future outcome records, zero prospective forecasts generated by this registration, and no scheduled task**.

No-game Tuesdays, incomplete data or missing receipts may reduce these counts below minimums. The future 15-date assessment reservation is itself shorter than v1's 20-slate evaluation minimum. Do not claim that completing it automatically satisfies the gate. Never backfill, quietly extend or change frozen dates after seeing outcomes. Register an append-only new experiment/extension before the affected future outcomes if needed.


## 15. Distribution results: retain the negative conclusion

Primary assessment seed, 5,000 draws per complete slate. Table uses equal-slate averaging; lower loss is better.

| Diagnostic | Original v1 engine | FGA candidate |
| --- | ---: | ---: |
| PRA MAE | 6.499959 | 6.504682 |
| PRA CRPS | 4.538557 | 4.540594 |
| 80% interval coverage | .762944 | .758504 |
| Above predicted q90 | .095744 | .097908 |
| Above predicted q95 | .048776 | .048244 |
| Mean PRA variance | 58.936273 | 57.950940 |
| Standardized squared error | 1.150313 | 1.170542 |
| Inclusive-leader Brier | .007903 | .007914 |
| Sole-leader Brier | .004599 | .004596 |
| Tied-leader Brier | .003389 | .003385 |
| Inclusive-leader log loss | .036042 | .036034 |
| Slate-maximum CRPS | 8.991788 | 9.021779 |
| Mean predicted slate maximum | 53.106133 | 52.658367 |
| Mean observed slate maximum | 58.166667 | 58.166667 |

Primary repair-minus-original paired changes, with whole-slate 95% bootstrap intervals:

| Metric | Delta | Interval |
| --- | ---: | --- |
| MAE | +.004722381 | [+.001172663, +.008790863] |
| CRPS | +.002037454 | [−.000426691, +.003895053] |
| 80% coverage | −.004440152 | [−.007182710, −.001587302] |
| Inclusive Brier | +.0000111263 | [−.0000113971, +.0000342059] |
| Sole Brier | −.00000332035 | [−.0000237686, +.0000217140] |
| Tied Brier | −.00000415892 | [−.0000115793, +.0000019450] |
| Inclusive log loss | −.0000084283 | [−.000327497, +.000386409] |

Second prespecified seed:

- CRPS delta −.000529046, interval [−.004902192, +.004852718].
- Inclusive Brier delta +.0000458512, interval [+.0000116750, +.0000812657].
- Inclusive log-loss delta +.000523575, interval [+.0000112957, +.001309742].

The favorable sign of one second-seed distribution delta is not grounds for choosing that seed or adopting the model. Both seeds are retained.

Mechanism check:

~~~text
Mean conditional FGA variance: 88.794591 → 40.537356
Mean FGA:                      88.996170 → 88.989215
Assessment conditioned residual square: 38.488196
Sampled negative-rate clipping: 0
FGA residual effective support: approximately 2836–3327 earlier games
~~~

Residual square includes mean error; it is not automatically the true conditional variance. Mechanically narrowing one over-variable pool slightly narrowed overall PRA variance, while the predicted slate ceiling was already too low. It did not fix the main joint-tail problem.

Strict four-slate/757-player subset:

~~~text
Original CRPS 4.716906; inclusive Brier .00677418; coverage .749114
Candidate CRPS 4.718476; inclusive Brier .00676762; coverage .746193
~~~

This also does not establish improvement.

### Component ablations and challenger

| Variant | PRA CRPS | Inclusive Brier | Mean predicted slate maximum |
| --- | ---: | ---: | ---: |
| Original | 4.538557 | .007903 | 53.106133 |
| Recorded observed minutes | 2.471286 | .007188 | 50.711867 |
| Fixed pace | 4.538089 | .007940 | 52.877533 |
| Recorded FGA/FTA pools | 4.502843 | .007853 | 52.902033 |
| Fixed latent conversion probabilities | 4.538395 | .007924 | 53.022833 |
| Independently shuffled player draws | 4.538557 | .007901 | 53.106967 |
| Empirical whole-game block challenger | 5.394649 | .008032 | 56.397100 |

Observed minutes and observed attempt pools are **oracles using outcome information**, not implementable pregame improvements.

Fixed conversion preserves the original posterior means while removing latent probability variation; it does not fix realized makes. Player shuffling preserves each player's joint P/R/A/minute distribution and deliberately breaks cross-player dependence/accounting; it is a diagnostic, not a production simulator.

The game-block challenger jointly resamples both teams from an earlier complete game, mapping donor positive-minute roles sorted by actual minutes to target prior-minute ranks. It rejects donor blocks with too many roles for target slots and requires at least 30 blocks. Remaining slots are structural simulated nonparticipation, not zero-imputation of missing historical stats. This is explicit role transport, not identity-specific calibrated sampling. Matching slate maxima more closely while worsening individual distributions is not success.

Point baselines use matched player-weighted cohorts, not the equal-slate summary:

- Season-average baseline: 1,043 supported observations; MAE 6.579463 versus original 6.651070 and candidate 6.654450 on the same rows.
- Minutes-times-production baseline: 1,046 observations; MAE 6.693270 versus original 6.663157 and candidate 6.666633.

### Dependence and subgroups

Simulated P–R/P–A/R–A correlations:

~~~text
Original:  .372733 / .285269 / .256319
Candidate: .373928 / .274647 / .256522
Observed component-residual diagnostic:
           .378749 / .267091 / .309159
~~~

Residual correlations include conditional mean errors; they do not identify every player's true conditional covariance.

Teammate/opponent simulated PRA dependence:

~~~text
Original:  −.024637 / .008849
Candidate: −.035734 / .003577
Observed standardized pair products, original scale:
           −.051674 / .005937
~~~

The last line is a standardized pair-product diagnostic, not an unqualified population correlation.

Role groups: eight new-team/no-current-role rows, 49 insufficient-comparison rows, 472 recent-minutes-flat/down and 517 recent-minutes-up. These are descriptive prior-history groups, not verified historical pregame role changes. Experience groups remain unknown; do not relabel them rookies/established.

### Monte Carlo, parameter and predictive uncertainty

Average inclusive-leader Monte Carlo SE was approximately .000644 for original and .000637 for candidate. Average PRA-mean SE was approximately .1061/.1053.

Two-seed average absolute leader-probability differences were approximately .000774/.000695; roughly 96% of nonzero-SE comparisons were within 1.96 combined simulation SE.

Zero observed leader successes in 5,000 draws is not zero real probability. A one-sided 95% upper bound is about .000599. Log loss uses the prespecified finite-sample probability floor .5/N.

Separate finite simulation error from:

- Player/game outcome dispersion.
- Parameter and shrinkage uncertainty.
- Missing or uncertain pregame inputs.
- Structural model error and empirical tail support.

Six reused complete slates are six uncertainty units, not 1,046 independent rare-leader trials. Bootstrap intervals, extensive simulation and clean code cannot compensate for missing pregame receipts or validate leader calibration.

### Final verdicts

- **Measured FGA mechanism discrepancy:** supported by the available development evidence, with proxy/source limitations.
- **Candidate mechanism operating as intended:** supported by mean/variance and accounting checks.
- **Adoption of the FGA candidate:** unsupported. Keep v1 unchanged.
- **Overall pregame predictive credibility:** inconclusive. Genuine complete pregame fields, historical availability and sufficient untouched later slates are missing.

Do not translate “unsupported adoption” into “the original is proven correct.” Neither version was validated as a live KOTC recommendation system.

## 16. Commands and reproducibility boundaries

Run from the installed research root, with that environment's Python. All output paths below must be new. Consult --help and the docs for the complete JSON schemas; do not manufacture missing manifests merely to get a command to run.

### Winner development and fresh research prediction

~~~text
python -m scripts.nba_winners --help
python -m scripts.nba_winners fetch --seasons 2023 2024 2025 --cache .cache/nba-winners/raw --output .cache/nba-winners/new-sources-001.json
python -m scripts.nba_winners ingest --input PATH_TO_ARCHIVE_OR_HOOPR_JSON --output NEW_CANONICAL_SNAPSHOT.json
python -m scripts.nba_winners backtest --input CANONICAL_SNAPSHOT.json --output NEW_DEVELOPMENT_REPORT.json
python -m scripts.nba_winners predict --input FRESH_CANONICAL_SNAPSHOT.json --output NEW_RESEARCH_PREDICTIONS.json
~~~

The winner CLI's holdout lock remains. Do not bypass it to produce a flattering result.

### KOTC fetch, reconcile and synthetic smoke run

~~~text
python -m scripts.king_court --help
python -m scripts.king_court fetch --seasons 2024 2025 2026 2027 --cache .cache/king-court/raw --output .cache/king-court/new-sources-001.json
python -m scripts.king_court ingest --manifest .cache/king-court/new-sources-001.json --output .cache/king-court/new-history-001.json
python -m scripts.king_court audit --history .cache/king-court/new-history-001.json --output .cache/king-court/new-audit-001.json
python -m scripts.king_court demo --draws 20000 --output .cache/king-court/new-synthetic-demo-001.json
~~~

--include-pbp preserves ESPN PBP archive bytes; it does not automatically verify event/stint accounting. Optional ingest --debut-metadata takes independently verified metadata, not inferred debut years.

### Registration, selection, freeze and settlement

~~~text
python -m scripts.king_court register --plan FUTURE_DATES_PLAN.json --output NEW_REGISTRATION.json
python -m scripts.king_court select --history HISTORY.json --experiment REGISTRATION.json --slates ARCHIVED_PROSPECTIVE_SLATES.json --outcomes DEVELOPMENT_OUTCOMES.json --draws 2000 --output NEW_SELECTION.json

python -m scripts.king_court simulate --history HISTORY.json --slate COMPLETE_PREGAME_SLATE.json --selection SELECTION.json --draws 20000 --mode prospective --output NEW_RESEARCH_RUN.json

python -m scripts.king_court freeze --history HISTORY.json --slate COMPLETE_PREGAME_SLATE.json --selection SELECTION.json --draws 20000 --mode prospective --output NEW_ACTUAL_TIME_FREEZE.json

python -m scripts.king_court settle --freeze FREEZE.json --outcomes OFFICIAL_OUTCOMES.json --output NEW_SETTLEMENT.json
python -m scripts.king_court evaluate --settlements SETTLEMENT_1.json SETTLEMENT_2.json --selection SELECTION.json --output NEW_EVALUATION.json
~~~

An explicit --research-parameters JSON grid member can replace --selection for flagged unselected research. It is not a shortcut to validated parameters. Optional --ownership takes an explicit scenario array. Actual-time freeze is prospective only.

Selection requires at least eight complete earlier registered prospective slates, rejects reconstructed postgame fields and records the latest outcome known-time as trained_through. Eight retrospective diagnostic slates are not interchangeable with those inputs.

### Distribution comparison

~~~text
python -m scripts.king_court_diagnostics --help
python -m scripts.king_court_diagnostics compare --history .cache/king-court-deepening/combined-history.json --code-lock research/king-court/distribution-v2/code-lock.json --event-audit .cache/king-court-deepening/event-audit-final.json --output .cache/king-court-deepening/reproduction-001.json
~~~

The delivered Windows ZIP lacks those .cache inputs. This command is a reproduction recipe for recovered exact inputs, not an immediately runnable offline Windows claim.

Do not overwrite the existing code lock or generate a new lock under the same experimental identity after edits. New experiments need new paths/registration. Changed upstream bytes must receive new receipts; do not forge old hashes.

The frozen original code-file hashes, diagnostic hashes, plan hash and comparison/report hashes are preserved in verification.json and appendices below.

## 17. Missing caches and original artifacts

Original cloud paths, not presumed Windows paths:

~~~text
.cache/nba-winners/
  development-final.json
  earlier development-run/development diagnostics
  source schedule archives

.cache/king-court/
  raw/
  four-seasons-manifest.json
  history-v1-final.json
  audit-v1-final.json
  validated-example.json and compressed .npz
  validated-example-outcomes.json
  validated-example-settled.json
  validated-example-pending.json
  validated-example-diagnostic.json

.cache/king-court-deepening/
  baseline-preservation.json
  support-2023-manifest.json
  support-2023-history.json
  combined-history.json
  event-source-manifest.json
  possessions-manifest.json
  event-audit-final.json
  registered-comparison.json
  raw/

.cache/nba-ensemble-transfer/
  full and source-only transfer archives
  installer/checksum material
  transfer-verification.json
~~~

Retained source/report summaries are in the smaller bundle. Raw data/NPZ/full prediction receipts are not. First look for a recoverable original full snapshot; otherwise refetch by documented URLs and compare hashes where possible. Rebuilding now may produce changed archives or later retrieval times. Such a rebuild is a new input receipt and cannot be retroactively called an identical contemporaneous forecast record.

The installed AGENTS.md was carried over from the full portable workspace and contains an old sentence saying current data/original receipts were copied. For this **source-and-reports-only transfer**, BUNDLE_CONTENTS.json, raw_data_cache_included=false, the package README and the actual file inventory govern what was delivered. That sentence does not mean the Windows machine has the missing cache. Do not silently rewrite frozen source; document the packaging distinction.

Full retained experiment source-evidence and summary JSON can be inspected without the caches, but a complete independent rerun needs the actual data bytes and runtime.

## 18. Next research task: participation and minutes, not yet implemented

This is the user's most recent proposed deepening, recorded in NEXT_RESEARCH_TASK.md. It is not a completed model change and must not be conflated with integration of already delivered code.

### Professional work to do beyond another projection

Establish whether information genuinely available before the whole-slate cutoff can support a better joint participation/minutes distribution. Separate the error budget due to missing availability inputs from conditional minutes, rate uncertainty and unexplained upper-tail error.

Start from the rawest accessible free evidence:

- Timestamped, versioned official injury-report PDFs.
- Official team announcements and genuinely confirmed starting lineups.
- Projected lineup states explicitly labeled as projections.
- Exact-minute official boxes, substitutions and period-start lineup evidence for outcomes.
- Source-specific IDs and explicit crosswalks.
- Verified NBA debut/experience metadata.

Promising access leads, **not completed integrations**:

https://official.nba.com/nba-injury-report-2026-27-season/
https://www.nba.com/players/todays-lineups

The injury-report page had public timestamped reports; historical machine-readable coverage/revisions were not established. The NBA lineup page labels projected lineups; do not call them confirmed. A dated PDF retrieved today is not automatically a contemporaneous archived input receipt.

### Specific bounded method

1. Audit access, publication versus retrieval time, version history, completeness and missingness before changing a model.
2. Freeze a diagnostic plan and eligible development/evaluation cohorts before examining their outcomes.
3. Model participation separately from minutes conditional on participation and from per-minute production.
4. Distinguish injury/ruled-out, available-but-coach-DNP and role-dependent rotation uncertainty. Do not impose arbitrary questionable probabilities.
5. Retain the rolling three-prior-plus-current boundary, chronologically selected recency, verified experience priors and current-team role separation.
6. Choose **one** evidence-supported subcomponent correction, preserving all other mechanisms and joint team-minute constraints. Do not stack the unsupported FGA repair on top.
7. Compare unchanged v1, the single candidate and simple minute baselines on identical complete fields.
8. Evaluate participation Brier/calibration, minute zero mass, minute CRPS/coverage; then PRA distributions/tails/maxima and sole/tied/inclusive leader scores.
9. Group paired uncertainty by slate; report valid experience/role strata only where metadata/sample permit.
10. Conclude supported, unsupported or inconclusive, with reproducible receipts and explicit missing evidence.

Potential tools: the existing Python/NumPy/Polars stack, exact-ID joins, PDF retrieval/text extraction after a source audit, chronological cross-validation, a transparent two-part/hurdle participation-plus-positive-minutes model if evidence warrants, constrained joint minute allocation, posterior-predictive checks, CRPS and proper event scores, whole-slate paired bootstrap and ablations. These are methods to select transparently, not claims of already implemented model components.

Independent evidence that would justify success is not another explanation or more draws. It is genuine pre-tipoff frozen complete-slate predictions, reliable later official outcomes and a registered paired improvement in distribution/leader metrics with adequate uncertainty. A significant oracle-minute gain only diagnoses headroom; it does not show that headroom is recoverable pregame.

Deliver source/assumption audit and frozen plan first, then one candidate and evidence report. Do not add UI, markets, more algorithms, broad tracking features, ownership guesses or hypothetical cash returns.

## 19. Integration plan and acceptance criteria

Integrating the delivered research and improving predictive validity are separate work streams. Respect the user's existing app and the current no-new-interface research scope.

For local integration:

- Inventory real app entry points and data contracts first.
- Preserve frozen research under the versioned folder.
- Prefer an app-side adapter or explicit subprocess over editing v1.
- Resolve source schema, ID namespace, date/time and cwd differences explicitly.
- Keep original app dependencies isolated until compatibility is demonstrated.
- Keep research outputs labeled and readiness gates intact.
- Verify that existing NBA winner functionality still runs and that imports do not shadow another scripts/tests package.
- Test the integration boundary meaningfully; do not claim end-to-end success from unit tests alone.
- Record changed files, commands, runtime, outputs, known missing data and whether START_NBA actually invokes the intended code.
- Never replace production outputs with the FGA candidate or unvalidated KOTC recommendations.

Research acceptance:

- Raw provenance and information times remain auditable.
- Full opponent fields and all eligible players remain in each leader comparison.
- Missing seasons/unknown minutes are not zeros.
- No eventual participation is backfilled as historical availability.
- Role/experience assertions are verified or marked unknown.
- Season contribution/ESS and model/input uncertainty remain visible.
- Original and candidate cohorts are identical; no incomplete-slate cherry-picking.
- Previously inspected data is never relabeled untouched.
- Frozen definitions and results remain byte-preserved; new work is append-only.
- Simulation noise is reported separately from predictive evidence.
- Unsupported and inconclusive results are retained rather than reframed as wins.

## 20. Claims Claude must not make

Do not claim:

- The installed research is already integrated with app.py/nba_lab/START_NBA.
- Every source named by the user is an independently verified active provider.
- The complete promotion terms were verified or the prop need not win as an established fact.
- Every Tuesday has the same offer, pool or eligible slate.
- Bonus bets are cash.
- Actual promotion ownership percentages are available.
- The source-only ZIP contains the full historical raw cache.
- Historical postgame participant fields are genuine pregame manifests.
- Current archives establish what was known at an old tipoff.
- Rookie/year-two performance has been validated.
- The FGA repair improved predictive accuracy or should be activated.
- Observed-minute oracle performance is attainable pregame.
- 48 passing tests or more Monte Carlo draws validate basketball probabilities.
- The 2026 winner holdout season was never accessed for any purpose.
- Future reserved dates already have frozen predictions or evaluated outcomes.
- The transfer branch can safely be merged into the application's main tree.

## 21. Suggested opening instruction to Claude

~~~text
Read CLAUDE_HANDOFF.md fully, then inspect my actual local NBA project at:
C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble

Verify the installed research snapshot and transfer receipt under updates\2026-10-27-dca2756e533d. Read applicable local instructions and inspect app.py, nba_lab, START_NBA.bat, requirements and tests before making integration changes. Preserve frozen v1 code/protocols/results and keep the unsupported FGA candidate inactive.

Tell me which delivered pieces are genuinely connected to my existing app, which are only installed research, and which require missing data. Continue within the bounded scope. The proposed participation/minutes research is not implemented yet; deliver its source/assumption audit and frozen plan before any single-component repair. Do not present research probabilities as validated recommendations.
~~~

## 22. Evidence hierarchy and conflict resolution

For original experiment claims, consult the sealed registration, code lock, comparison summary, source-evidence and verification records together. For delivered-file identity, consult the package manifest and Windows receipt. For actual app integration, inspect the real Windows code and run an integration check. For contest eligibility and payout, obtain the exact dated offer's full accessible terms.

An older README can describe the workspace at an earlier stage; an audit can describe a different data acceptance stage than a later diagnostic. Preserve dates and units instead of merging all counts into one narrative. If a claim cannot be established from those artifacts, mark it unknown.

This handoff does not modify frozen models, registrations, selection rules, source hashes or the ZIP. It supplies context and an explicit continuation path.



## Appendix A. Exact delivered configs and experiment records

The following text is copied from delivered artifacts. Keep the original files authoritative; do not copy embedded JSON back over sealed files or reinterpret historical timestamps as new verification. Relative links inside an embedded document refer to its original path.

### config/nba_winners_v1.json

~~~json
{
  "version": "nba-winners-research-v1",
  "status": "research-only",
  "registered_at": "2026-10-23",
  "target": "NBA regular-season outright winner, overtime included",
  "models": ["elo", "logistic", "gradient_boosting", "random_forest", "naive_bayes", "ridge_margin"],
  "development_seasons": [2023, 2024, 2025],
  "untouched_holdout_seasons": [2026],
  "season_convention": "ending year; 2025 means 2024-25",
  "minimum_training_games": 300,
  "minimum_team_games": 5,
  "refit_days": 30,
  "historical_result_lag_hours": 36,
  "elo_k": 20,
  "elo_home_advantage": 65,
  "weight_prior_games": 100,
  "disagreement_range_flag": 0.25,
  "close_probability_flag": 0.55,
  "random_seed": 42,
  "evaluation": {
    "primary": "paired Brier loss versus equal-weight blend, Elo and expanding home-win frequency",
    "secondary": ["log loss", "winner accuracy", "reliability bins", "coverage and exclusions", "model prediction correlation"],
    "uncertainty": "resample complete UTC game dates for paired 95% intervals",
    "promotion_gate": "Freeze code/config/source receipts; evaluate untouched later data once; require paired Brier improvement with upper95% delta below zero versus all three baselines, nonworsening log loss, calibration review and explicit model-promotion approval. No profit claim without recorded actual prices."
  },
  "limitations": [
    "Six algorithms share inputs and upstream feeds; agreement is not independent confirmation or calibrated confidence.",
    "Historical replay assumes final results usable 36 hours after tipoff; downloaded revised archives do not establish historical publication times.",
    "No injury, player, lineup, possession, travel, spread, odds or prop adjustments in v1.",
    "No automatic publication, scheduled jobs or production model replacement."
  ]
}
~~~

### config/king_court_protocol_v1.json

~~~json
{
  "version": "king-court-research-v1",
  "registered_at": "2026-10-27",
  "status": "research_only",
  "history_prior_seasons": 3,
  "season_convention": "ending_year",
  "weekday_timezone": "America/New_York",
  "weekday": "Tuesday",
  "seed": 271026,
  "candidate_grid": {
    "season_decay": [0.35, 0.65],
    "game_half_life_days": [30, 90],
    "prior_games": [5, 15]
  },
  "selection_loss": "mean_complete_slate_PRA_MAE_on_preregistered_earlier_development_folds",
  "selection_tiebreak": "ascending_season_decay_then_half_life_then_prior_games",
  "minimum_selection_slates": 8,
  "minimum_evaluation_slates": 20,
  "minimum_cohort_games": 20,
  "experience_stage_width_appearances": 5,
  "shooting_beta_prior": "one success and one failure; disclosed weak numerical prior, not fitted",
  "simulations": 20000,
  "default_parameters": null,
  "box_possession_fta_coefficient": 0.44,
  "historical_result_lag_hours": 36,
  "readiness": "Block recommendations without complete pregame field/roster/availability, event reconciliation, selected earlier-fold parameters and verified date-specific terms.",
  "holdout": "Declared in experiment manifest before selection. No automatic promotion or publication."
}
~~~

### config/king_court_offer_2026-10-27.json

~~~json
{
  "version": 1,
  "offer_id": "EP70GG",
  "date": "2026-10-27",
  "timezone": "America/New_York",
  "source": "Two account screenshots supplied in this conversation",
  "status": "screenshot_confirmed_complete_terms_unverified",
  "pool_bonus_bet_face_value": 1000000,
  "minimum_stake": 5,
  "minimum_leg_american_odds": -200,
  "one_token_per_customer": true,
  "token_required_before_placement": true,
  "qualifying_markets": "Prematch NBA player-prop single or same-player NBA parlay, all legs on one player",
  "entry_deadline": "Start of final October 27 NBA game; each wager must also be prematch",
  "ties": "One pool shared equally by qualifying customers on any tied PRA leader",
  "cash_or_dk_dollars_required": true,
  "excluded": ["ordinary_parlays", "SGPx", "odds_boosts", "live", "cashed_out", "voided", "ineligible_games"],
  "award_timing": "Within 24 hours/following day",
  "bonus_expiry_days": 7,
  "eligibility_as_shown": {
    "age_21_plus_physically_located": "AR, AZ, CO, CT, IA, IL, IN, KS, LA (select parishes), MA, MD, ME, MI, MO, NC, NJ, NY, OH, OR, PA, TN, VA, VT, WA, WV",
    "age_18_plus_physically_located": "DC, KY, NH, PR (residents only)",
    "status": "Transcribed from the supplied screenshot; not independently verified jurisdiction rules"
  },
  "requires_prop_win": null,
  "overtime_rule": null,
  "postponement_rule": null,
  "stat_correction_rule": null,
  "eligible_game_ids": null,
  "eligible_player_ids": null,
  "recurrence": "Tuesday marketing corroborated by operator editorial search result; verify offer separately each date",
  "full_terms_verified": false
}
~~~

### research/king-court/distribution-v2/registration.json

~~~json
{
  "kind": "distribution_diagnostic_registration",
  "registered_at": "2026-10-27T17:52:25.912442+00:00",
  "audit_sha256": "98fb03c012f7e392a4cf2f940f990bef64a8239a9ba42fe3de6bcf5addc4fa57",
  "plan_sha256": "c71f4e7f4551988062cb8405baa31e21992fa5ff3d6537e13176440ef6a3ffd1",
  "baseline_files": {
    "scripts/king_court/research.py": "cae614533574c3cede534331ab49523c5819f0df9121126a8c71e53221592c0c",
    "scripts/king_court/events.py": "383ab7817be67a0d4639d781f2ecf0e76cdc1cfd0a5dd60ed5dc7e932daf6d2c",
    "scripts/king_court/__init__.py": "903c2182f161722f585927199cf8d32d4929bdf463c2546b0dcb5c4109a6d30c",
    "scripts/king_court/data.py": "9c29a6aa7874dea10cd6b94cc832e1b2b3837084fc662d6f040218d11f9a6bf3",
    "scripts/king_court/simulation.py": "c4fe4becbe3ed4f8191cc1295024fa8b3a09840ea0f2f736783b711819aa72c9",
    "scripts/king_court/demo.py": "870c38acd3bac2ef32df6847f66f773aa18b23a7ef7fb477a3a76bed77793b8a",
    "scripts/king_court/history.py": "d78ebf2229a69402bb8767dcdd7538dc88a419cea808393659ff18a94c8798e4",
    "scripts/king_court/common.py": "57e679ac8af4d6ab0b52b05e124b4ad86a9c6579afcc0102ac59cb6fb44c5664",
    "scripts/king_court/__main__.py": "95b475ccac1029824f860c988503a9fb836607c737d051cd48885c3152199b8f",
    "config/king_court_protocol_v1.json": "d82d599e9e3c61835e8495377bfae4e2d6c310185ff1d3aa455f583da974b3a3",
    "config/king_court_offer_2026-10-27.json": "cbf894fda29840ad9d7776c846507b6a9fd7a09666183e6dde1bc702745db44f",
    "scripts/nba_winners/evaluation.py": "7df735c568610021e2af9e054e72560b696156d326497a6fa9572b2dc76d9639",
    "scripts/nba_winners/__init__.py": "5d71a2e91924e430177117039cf2e9ab744cee2fec979ecd17bbdb0ba0e9fa43",
    "scripts/nba_winners/data.py": "a9aabb071a0f996382982c34c6ceb8d505b88f89bc2d366ec5f0f47a79236f4d",
    "scripts/nba_winners/models.py": "dcc7db013da96506095122ae4ee83b0f8d8ee1980204c4bfbd0de614751609c0",
    "scripts/nba_winners/features.py": "3a9327e268b530147c1bba39d9d777f373c608f40bf6fb28b2eafab36e6a2e6f",
    "scripts/nba_winners/__main__.py": "f62bc00481cfe1713b26d488787186b62595ff22d87294a5ee9870f05c3b416e"
  },
  "retrospective_development": [
    "2025-10-28",
    "2025-11-04",
    "2025-11-11",
    "2025-11-18",
    "2025-11-25",
    "2025-12-02",
    "2025-12-09",
    "2025-12-16"
  ],
  "retrospective_assessment": [
    "2026-01-06",
    "2026-01-13",
    "2026-01-20",
    "2026-01-27",
    "2026-02-03",
    "2026-02-10",
    "2026-02-17",
    "2026-02-24",
    "2026-03-03",
    "2026-03-10",
    "2026-03-17",
    "2026-03-24"
  ],
  "retrospective_evidence_status": "reused_archives_not_untouched_not_pregame_forecasts",
  "prospective_development": [
    "2026-11-03",
    "2026-11-10",
    "2026-11-17",
    "2026-11-24",
    "2026-12-01",
    "2026-12-08",
    "2026-12-15",
    "2026-12-22"
  ],
  "prospective_evaluation": [
    "2026-12-29",
    "2027-01-05",
    "2027-01-12",
    "2027-01-19",
    "2027-01-26",
    "2027-02-02",
    "2027-02-09",
    "2027-02-16",
    "2027-02-23",
    "2027-03-02",
    "2027-03-09",
    "2027-03-16",
    "2027-03-23",
    "2027-03-30",
    "2027-04-06"
  ],
  "future_outcomes_accessed": false,
  "scheduled_task_created": false,
  "selection_draws": 1000,
  "assessment_draws": 5000,
  "selection_seed": 271026,
  "assessment_seeds": [
    271026,
    271027
  ],
  "primary_diagnostic": "complete_slate_PRA_CRPS",
  "single_repair": "paired_empirical_conditional_team_FGA_pool",
  "code_hash_scope": "New diagnostic code hash frozen before first outcome comparison run",
  "sha256": "98618a519da19dd1c6c0248ef016e82a91e7be99594926e9ce1adaba2c0b2738"
}
~~~

### research/king-court/distribution-v2/code-lock.json

~~~json
{
  "kind": "diagnostic_code_lock_before_comparison",
  "recorded_at": "2026-10-27T18:05:27.249757+00:00",
  "registration_sha256": "98618a519da19dd1c6c0248ef016e82a91e7be99594926e9ce1adaba2c0b2738",
  "diagnostic_code_sha256": {
    "scripts/king_court_diagnostics/__init__.py": "f37938927ee7eb84f42425b163c9fdcd5bcee7a9aca5ac955f07b4a2825d6735",
    "scripts/king_court_diagnostics/__main__.py": "0e318c5a2474d3eeedc229f34b91655c4773bb756d58f4609a7e388db983299e",
    "scripts/king_court_diagnostics/archive_audit.py": "e346eaf2e08e82a7e23b244ba8da4343c1253398ba75032f40b12bddca14608a",
    "scripts/king_court_diagnostics/challengers.py": "c509663e2b7446c7a241efca080f54c02e3c1f4078c856426776b398885b633b",
    "scripts/king_court_diagnostics/dataset.py": "f92a482979b473717aaea62e2359ebe5e413e20196574b70a6452f015f874537",
    "scripts/king_court_diagnostics/experiment.py": "b39d51b59490a48471cea06e2fe3d6108374de472709f0e9ae36c19a434e86d1",
    "scripts/king_court_diagnostics/metrics.py": "e40dd6d0e531e58dda8dcde8caed0a4d6acaa89300a3206c4fbedffdf2112c9d",
    "scripts/king_court_diagnostics/pools.py": "19bd7faa4a92f9e400a3750149791e301c704008698d864d25a1512f6850603e",
    "scripts/king_court_diagnostics/simulation.py": "818a8558f440831693558740e8b6f127e90e7d9b5d3f355c6b0668d8b5d1e8ce"
  },
  "baseline_files": {
    "scripts/king_court/research.py": "cae614533574c3cede534331ab49523c5819f0df9121126a8c71e53221592c0c",
    "scripts/king_court/events.py": "383ab7817be67a0d4639d781f2ecf0e76cdc1cfd0a5dd60ed5dc7e932daf6d2c",
    "scripts/king_court/__init__.py": "903c2182f161722f585927199cf8d32d4929bdf463c2546b0dcb5c4109a6d30c",
    "scripts/king_court/data.py": "9c29a6aa7874dea10cd6b94cc832e1b2b3837084fc662d6f040218d11f9a6bf3",
    "scripts/king_court/simulation.py": "c4fe4becbe3ed4f8191cc1295024fa8b3a09840ea0f2f736783b711819aa72c9",
    "scripts/king_court/demo.py": "870c38acd3bac2ef32df6847f66f773aa18b23a7ef7fb477a3a76bed77793b8a",
    "scripts/king_court/history.py": "d78ebf2229a69402bb8767dcdd7538dc88a419cea808393659ff18a94c8798e4",
    "scripts/king_court/common.py": "57e679ac8af4d6ab0b52b05e124b4ad86a9c6579afcc0102ac59cb6fb44c5664",
    "scripts/king_court/__main__.py": "95b475ccac1029824f860c988503a9fb836607c737d051cd48885c3152199b8f",
    "config/king_court_protocol_v1.json": "d82d599e9e3c61835e8495377bfae4e2d6c310185ff1d3aa455f583da974b3a3",
    "config/king_court_offer_2026-10-27.json": "cbf894fda29840ad9d7776c846507b6a9fd7a09666183e6dde1bc702745db44f",
    "scripts/nba_winners/evaluation.py": "7df735c568610021e2af9e054e72560b696156d326497a6fa9572b2dc76d9639",
    "scripts/nba_winners/__init__.py": "5d71a2e91924e430177117039cf2e9ab744cee2fec979ecd17bbdb0ba0e9fa43",
    "scripts/nba_winners/data.py": "a9aabb071a0f996382982c34c6ceb8d505b88f89bc2d366ec5f0f47a79236f4d",
    "scripts/nba_winners/models.py": "dcc7db013da96506095122ae4ee83b0f8d8ee1980204c4bfbd0de614751609c0",
    "scripts/nba_winners/features.py": "3a9327e268b530147c1bba39d9d777f373c608f40bf6fb28b2eafab36e6a2e6f",
    "scripts/nba_winners/__main__.py": "f62bc00481cfe1713b26d488787186b62595ff22d87294a5ee9870f05c3b416e"
  },
  "sha256": "36848acaf7be52acdf4e0718db21dd1d4a9c126ee60498b7af3a21b038777e16"
}
~~~

### research/king-court/distribution-v2/component-decision.json

~~~json
{
  "evidence_kind": "reused_development_component_check_not_PRA_validation",
  "cutoff_exclusive": "2025-12-17",
  "games": 4014,
  "poisson_implied_average_conditional_variance": [
    88.82810164424514,
    88.8423019431988
  ],
  "measured_possession_conditioned_residual_variance": [
    41.04618307982904,
    39.11119639954297
  ],
  "opposing_residual_correlation": -0.047448200041637204,
  "ratio_residual_variance_to_Poisson": [
    0.4620855598627811,
    0.44023168630354326
  ],
  "limitation": "Possessions are box-derived and share FGA algebra; raw-event reconciliation is required before interpreting this as true possession-conditional variance.",
  "sha256": "0b648a0aa531c7d938819bfb6270b2d99d38471dbc57b35fb1efca284c085719"
}
~~~

### research/king-court/distribution-v2/source-evidence.json

~~~json
{
  "kind": "event_evidence_summary_not_predictive_validation",
  "counts": {
    "games": 1230,
    "event_agreement": 1186,
    "stint_agreement": 1097,
    "event_and_stint_agreement": 1095,
    "canonical_espn_box_agreement": 1138
  },
  "free_throw_miss_classification": {
    "missed_ordinary_final_potentially_reboundable": 6175,
    "missed_nonfinal_or_technical_not_a_live_rebound_chance": 6327,
    "missed_ambiguous_sequence_or_retained_possession": 42
  },
  "development_counted_possession_check": {
    "games": 367,
    "mean_implied_Poisson_variance": [
      88.86376021798365,
      89.41144414168937
    ],
    "measured_counted_possession_residual_variance": [
      46.50457835381371,
      40.820730334054204
    ],
    "residual_variance_to_Poisson": [
      0.5233244490187849,
      0.45654927874071716
    ],
    "limitation": "Producer-derived possession grouping, same NBA feed; not an independent provider. Development-only matched games."
  },
  "event_issues": {
    "ambiguous_assist_name": 220
  },
  "stint_issues": {
    "entrant_already_on_floor": 146,
    "ambiguous_or_inconsistent_substitution": 360,
    "invalid_period_lineup_seed": 1
  },
  "stat_mismatch_counts": {
    "ast": 61
  },
  "game_crosswalk_matches": 1185,
  "sources": [
    {
      "kind": "nba_pbp_2026",
      "url": "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_pbp/nba_play_by_play_2026.parquet",
      "status": 200,
      "retrieved_at": "2026-10-27T17:52:41.658412+00:00",
      "sha256": "78524677282ad105b2651d511abcc0a827c1cecdbe826acc487872d1f03836ac",
      "bytes": 19999800
    },
    {
      "kind": "nba_lineups_2026",
      "url": "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_game_lineups/nba_lineups_2026.parquet",
      "status": 200,
      "retrieved_at": "2026-10-27T17:52:42.344117+00:00",
      "sha256": "87450c2edfae85320b317f0c80aa35e962344cef9db52676c9def109c5a8c399",
      "bytes": 1051800
    },
    {
      "kind": "schedule_crosswalk_2026",
      "url": "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_crosswalk/nba_schedule_crosswalk_2026.parquet",
      "status": 200,
      "retrieved_at": "2026-10-27T17:52:43.117279+00:00",
      "sha256": "6169d3b2acdbe92a3ea84af82d999f6481ff723441236d4d8e193509436991d1",
      "bytes": 31867
    },
    {
      "kind": "player_crosswalk_2026",
      "url": "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_crosswalk/nba_player_crosswalk_2026.parquet",
      "status": 200,
      "retrieved_at": "2026-10-27T17:52:43.901731+00:00",
      "sha256": "f8cd2afd9a08a367b7d2d9e4ef012654a952162f9255f37f0a57c20aa1dc5136",
      "bytes": 44383
    },
    {
      "kind": "nba_boxes_2026",
      "url": "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_player_boxscores/player_boxscores_2026.parquet",
      "status": 200,
      "retrieved_at": "2026-10-27T17:52:44.706344+00:00",
      "sha256": "a0b280ebb0c955e501c0e6feab3f6d726bd9f1b7c2d13f5b5c0746049459132e",
      "bytes": 644419
    },
    {
      "kind": "espn_pbp_2026",
      "url": "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_pbp/play_by_play_2026.parquet",
      "status": 200,
      "retrieved_at": "2026-10-27T17:52:46.180637+00:00",
      "sha256": "f7051c5c0c5b605419fcc0e0c13dd90df7803f96dab290554c1ef737433a98b2",
      "bytes": 22274408
    },
    {
      "kind": "nba_possessions_2026",
      "url": "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_possessions/nba_possessions_2026.parquet",
      "status": 200,
      "retrieved_at": "2026-10-27T17:53:48.151243+00:00",
      "sha256": "e79dd79bc892290f2f91cd146e83a4224cabba178fa44048aace8a06a47a3552",
      "bytes": 3804011
    }
  ],
  "audit_sha256": "a2e9e9392b21c5999a542ad37b28e026cf9da58fcee951c550bb997a8887298e",
  "unavailable": [
    "native_original_vendor_JSON",
    "independently_observed_period_lineups",
    "pregame_availability_receipts",
    "verified_NBA_debut_metadata",
    "potential_assists_tracking"
  ],
  "interpretation": "Native vendor JSON unavailable. Available NBA event rows and inferred lineup seeds were audited, not upgraded into independent data providers. Repeated action_number rows can encode related steals/blocks; order_index identifies records.",
  "sha256": "b87264a5435d4e75d4c16d74eba55bae22783c7c9c4091954cf3f0bb0703117f"
}
~~~

### research/king-court/distribution-v2/verification.json

~~~json
{
  "baseline_original_files_preserved": 17,
  "original_files_sha256": {
    "scripts/king_court/research.py": "cae614533574c3cede534331ab49523c5819f0df9121126a8c71e53221592c0c",
    "scripts/king_court/events.py": "383ab7817be67a0d4639d781f2ecf0e76cdc1cfd0a5dd60ed5dc7e932daf6d2c",
    "scripts/king_court/__init__.py": "903c2182f161722f585927199cf8d32d4929bdf463c2546b0dcb5c4109a6d30c",
    "scripts/king_court/data.py": "9c29a6aa7874dea10cd6b94cc832e1b2b3837084fc662d6f040218d11f9a6bf3",
    "scripts/king_court/simulation.py": "c4fe4becbe3ed4f8191cc1295024fa8b3a09840ea0f2f736783b711819aa72c9",
    "scripts/king_court/demo.py": "870c38acd3bac2ef32df6847f66f773aa18b23a7ef7fb477a3a76bed77793b8a",
    "scripts/king_court/history.py": "d78ebf2229a69402bb8767dcdd7538dc88a419cea808393659ff18a94c8798e4",
    "scripts/king_court/common.py": "57e679ac8af4d6ab0b52b05e124b4ad86a9c6579afcc0102ac59cb6fb44c5664",
    "scripts/king_court/__main__.py": "95b475ccac1029824f860c988503a9fb836607c737d051cd48885c3152199b8f",
    "config/king_court_protocol_v1.json": "d82d599e9e3c61835e8495377bfae4e2d6c310185ff1d3aa455f583da974b3a3",
    "config/king_court_offer_2026-10-27.json": "cbf894fda29840ad9d7776c846507b6a9fd7a09666183e6dde1bc702745db44f",
    "scripts/nba_winners/evaluation.py": "7df735c568610021e2af9e054e72560b696156d326497a6fa9572b2dc76d9639",
    "scripts/nba_winners/__init__.py": "5d71a2e91924e430177117039cf2e9ab744cee2fec979ecd17bbdb0ba0e9fa43",
    "scripts/nba_winners/data.py": "a9aabb071a0f996382982c34c6ceb8d505b88f89bc2d366ec5f0f47a79236f4d",
    "scripts/nba_winners/models.py": "dcc7db013da96506095122ae4ee83b0f8d8ee1980204c4bfbd0de614751609c0",
    "scripts/nba_winners/features.py": "3a9327e268b530147c1bba39d9d777f373c608f40bf6fb28b2eafab36e6a2e6f",
    "scripts/nba_winners/__main__.py": "f62bc00481cfe1713b26d488787186b62595ff22d87294a5ee9870f05c3b416e"
  },
  "diagnostic_code_sha256": {
    "scripts/king_court_diagnostics/__init__.py": "f37938927ee7eb84f42425b163c9fdcd5bcee7a9aca5ac955f07b4a2825d6735",
    "scripts/king_court_diagnostics/__main__.py": "0e318c5a2474d3eeedc229f34b91655c4773bb756d58f4609a7e388db983299e",
    "scripts/king_court_diagnostics/archive_audit.py": "e346eaf2e08e82a7e23b244ba8da4343c1253398ba75032f40b12bddca14608a",
    "scripts/king_court_diagnostics/challengers.py": "c509663e2b7446c7a241efca080f54c02e3c1f4078c856426776b398885b633b",
    "scripts/king_court_diagnostics/dataset.py": "f92a482979b473717aaea62e2359ebe5e413e20196574b70a6452f015f874537",
    "scripts/king_court_diagnostics/experiment.py": "b39d51b59490a48471cea06e2fe3d6108374de472709f0e9ae36c19a434e86d1",
    "scripts/king_court_diagnostics/metrics.py": "e40dd6d0e531e58dda8dcde8caed0a4d6acaa89300a3206c4fbedffdf2112c9d",
    "scripts/king_court_diagnostics/pools.py": "19bd7faa4a92f9e400a3750149791e301c704008698d864d25a1512f6850603e",
    "scripts/king_court_diagnostics/simulation.py": "818a8558f440831693558740e8b6f127e90e7d9b5d3f355c6b0668d8b5d1e8ce"
  },
  "plan_hash_unchanged": true,
  "original_and_repair_disabled_samples_identical": true,
  "only_FGA_model_component_changed": true,
  "targeted_tests_passed": 48,
  "comparison_sha256": "2047f27251947a56b39983a5a402f8a0e1709fe5c18491cf291304abf678a9a3",
  "model_adoption": "not_supported_v1_retained",
  "future_outcome_records": 0,
  "automation_created": false,
  "report_sha256": "8f465cb1a75d59ddcd2eea81b6d7072ed37bfbd568129ad4198b967c6567e995",
  "sha256": "8ed3fc2edb4377a3db3907cfc7932b75548ce2b611b35982486b68d02c72a8d5"
}
~~~

## Appendix B. Frozen assumption audit and diagnostic plan

### Original path: docs/KING_COURT_DISTRIBUTION_AUDIT.md

~~~text
# King of the Court distribution audit, before model changes

2026-10-27. This audit concerns the retained v1 source and existing receipts. No v1 model or protocol is changed. Passing arithmetic tests and a synthetic demo are not predictive validation.

| Component | Measured support | Approximation / unresolved assumption | Diagnostic |
| --- | --- | --- | --- |
| Minutes | Weighted current-team appearances; recorded minute variability; optional pregame minute scenarios | Independent positive lognormal draws followed by team normalization; no available-player DNP mixture, explicit foul/blowout state or fitted five-player interaction. Rounded boxes are not exact stints. | Minute coverage/zero mass and PRA changes under observed-minute conditioning |
| Pace | Weighted box-derived pace mean/SD | Lognormal shape; `.44 FTA` possession proxy; shared pace cannot establish measured possession dependence | Raw-event/possession reconciliation where accessible; fixed-pace ablation |
| Attempts | Historical FGA/FTA per possession and per-minute player shares | Independent team Poisson FGA/FTA pools, even after a game pace draw. Variance=mean is not fitted or validated. | Conditional residual variance/covariance and tails; priority candidate for ONE repair |
| Shooting | Weighted makes/attempts and disclosed Beta(1,1) prior | Weighted counts treated as posterior exposures; independent efficiencies; symmetric logit defense adjustment is unfitted | Conversion-only ablation, component covariance and upper-tail checks |
| Rebounds | Integer misses, recorded offensive/defensive capture, player shares | Every missed FT enters a proxy pool; dead balls/non-reboundable misses compensated only through aggregate capture, not event classification | Identify FT sequence/dead-ball evidence; do not relabel proxy as observed chance |
| Assists | Credited assists tied to made field goals, no self-assists | No potential-assist/passing tracking; rate allocation is not measured creation opportunity | PBP credited-assist reconciliation; no inferred potential assists |
| Overtime | Empirical historical OT frequency and period count | Same empirical OT mix for every matchup; not fitted to closeness | Observed OT frequency, fixed-regulation diagnostic; preserve original OT model |
| Dependence | Shared pace, minute constraints, common shot/rebound/assist pools | Within-player and across-player covariance not empirically validated; team attempt coupling conditional on pace is absent | Component correlations; marginal-preserving player shuffle; slate-max distribution |
| Experience/recency | Explicit rookie/second-year prior code; rolling four-season boundary and an earlier-fold selection contract | Real debut metadata and archived complete pregame slates absent; no selected parameters in existing receipts | Do not invent experience; report unknown strata. Separate diagnostic parameter choice from valid prospective calibration |

Priority hypothesis: Poisson field-goal-attempt variation may inflate conditional opportunity variance and distort the joint PRA upper tail. This is a hypothesis from source inspection, not a measured conclusion. Before changing this component, compare its implied variance with eligible historical conditional FGA residuals. If unsupported, report it and do not claim a successful repair.

Existing boxes have already been inspected for intake integrity and are reused research material. No historical season will be called untouched. A comparison conditioned on the recorded box field or observed minutes is a posterior-predictive diagnostic, not a reconstructed pregame forecast. Historical availability, an eligible promotion field and debut season cannot be inferred from eventual participation. Missing genuine pregame receipts block a valid prospective probability-calibration claim.

The frozen diagnostic plan and its actual-time receipt are in `research/king-court/distribution-v2/`. The current source hashes and prior receipts are preserved. New diagnostic/repair code lives outside `scripts/king_court/`, keeping its existing code-hash contract and popularity/prize functions intact.
~~~

### Original path: research/king-court/distribution-v2/PLAN.md

~~~text
# Frozen distribution diagnostic plan

Freeze before new diagnostic values or repair implementation. Scope remains Tuesday regular-season PRA leaders, free data, four rolling seasons per prediction. This is a single-component experiment, not a release or a feature expansion.

## Evidence tracks and calendar

1. **Reused retrospective diagnostic development:** Tuesdays 2025-10-28 through 2025-12-16 inclusive (eight dates), target season ending-year 2026, using only earlier season-to-date plus 2023–2025. Existing inspected archives are reused, never untouched. Acquire the missing 2023 support season without adding out-of-window training data.
2. **Reused retrospective diagnostic assessment:** Tuesdays 2026-01-06 through 2026-03-24 inclusive (twelve dates). Freeze date lists before running comparison; do not tune from assessment outcomes. These dates are later chronologically but are NOT an untouched holdout because their archives were previously inspected. Record no-game, incomplete-box and missing-evidence exclusions for the entire slate, never quietly grade a surviving shortlist.
3. **Genuinely prospective development:** eight Tuesdays 2026-11-03 through 2026-12-22. Actual-time pregame receipts required; future outcomes not accessed now.
4. **Genuinely prospective later evaluation:** Tuesdays 2026-12-29 through 2027-04-06. Do not access outcomes or evaluate early. All-Star/no-regular-game Tuesdays contribute no slate. The remaining season may provide fewer than 20 evaluable dates; report insufficient evidence, not an exception to rare-event validation.

The prospective schedule is a local registration only. It creates no scheduled agent, background process, data publication or betting action. No future prediction is fabricated now.

## Inputs and chronology

Preserve v1 and NBA-winner source/protocol hashes before editing anything. Record raw source URLs, hashes, retrieval/publication times and failures. Prefer raw NBA/ESPN PBP, period lineups, substitutions and official boxes; verify joins with explicit crosswalks. Reconstruct exact stints where supported. Record unmatched IDs, malformed/duplicate events, player/team stat and minute mismatches. Dead-ball/FT sequence fields are evidence, not an invitation to guess event meanings.

Retrospective diagnostics release results only after the existing 36-hour lag, restrict each origin to S−3..S, and disclose that historical source publication times are unknown. A recorded box field may be used only as **explicit postgame conditioning for a mechanism check**, never as pregame availability. An observed-minute ablation is an oracle conditional check and cannot validate minutes forecasts. Missing debut metadata is labeled unknown; do not make up rookie/second-year/established labels.

## Parameter choice and single repair

Retain the existing eight-member season-decay/half-life/prior grid. Choose diagnostic parameters on development dates only, using mean paired-slate PRA CRPS (tie: PRA MAE, then ascending grid tuple); use those same settings for all assessment variants. This choice is explicitly conditional/reused-data research, not a v1 prospective selection receipt. No assessment retuning and no independent parameter optimization for the repair.

Test the v1 implied conditional FGA variance=mean and opposing-team FGA covariance against prior measured residuals. The sole candidate repair is the **team FGA pool distribution**: replace its independent Poisson draw with recency-weighted paired empirical residuals conditional on game possessions, centered using eligible earlier data. Preserve conditional means, integer counts and nonnegativity; report rounding/clipping effects and finite empirical support. Leave FTA, player allocation, minutes, conversion, rebounds, assists and overtime unchanged. Keep v1 as an executable comparator, with an exact-equality test when the repair is disabled. Do not silently patch another discovered issue.

## Comparators and ablations

- Original v1 and the single FGA-pool repair, same field, history, priors, weights, origins and simulation budget.
- Current-season average and minutes-times-production point baselines; compare means on identical supported player/slate cohorts.
- A clearly labeled empirical whole-game block challenger preserving recorded within-game component dependence. Use exact identity support if available; any role transport must be explicit, predeclared, retain complete target field, report unsupported blocks and never claim identity-specific calibration. No missing player outcomes silently become zeros. This is a diagnostic challenger, not another production system.
- Observed-minute conditioning; fixed game pace; fixed opportunity pool diagnostic; fixed conversion probabilities; marginal-preserving independent player shuffling. These isolate assumptions and are not additional simultaneous model repairs. Keep the repaired model separate from ablations.

## Metrics and decision rule

Report per-slate PRA MAE/CRPS, mean/variance, 80% interval coverage, 90th/95th percentile exceedance frequencies, within-player P/R/A correlations, game-level dependence, observed and simulated slate maximum distributions, sole/tied/inclusive leader event Brier/log loss and reliability bins. Report Monte Carlo errors for means/probabilities/tails separately from predictive dispersion and model/parameter uncertainty. Use fixed documented seeds, 1,000 draws for diagnostic selection and 5,000 for assessment, with a second assessment seed for finite-simulation sensitivity. No tuning from that sensitivity run.

Use paired whole-slate 95% bootstrap intervals for original-minus-repaired differences. Preserve slate clustering for component/tail diagnostics and report the number of independent slates. Report verified experience and role-change strata where support exists, otherwise unknown/insufficient. A block bootstrap does not solve rare-leader or long-term serial dependence.

Select the FGA component only if development conditional variance evidence contradicts the original Poisson assumption; otherwise retain the negative result. Call a mechanism improvement supported only if its variance/tail discrepancy improves without a material mean shift. An overall predictive improvement requires genuine later pregame freezes, same-cohort CRPS/Brier evidence and uncertainty excluding no improvement, nonworsening log loss, calibration and subgroup review. Reused postgame-conditioned diagnostics alone require an **inconclusive overall prediction verdict**, even if a component discrepancy improves. Popularity/payout scenarios are preserved and excluded from model selection.
~~~

## Appendix C. Delivered file manifest

This is the source-and-reports manifest. It identifies 57 payload files; the installer additionally verifies this manifest itself for 58 files. The ZIP wrapper/installer is separate from the manifest's research payload. raw_data_cache_included is false. Do not confuse this with the earlier full cloud snapshot.

~~~json
{
  "kind": "nba_ensemble_portable_snapshot",
  "created_at": "2026-10-27T19:58:44.112875+00:00",
  "intended_windows_destination": "C:\\Users\\travi\\OneDrive\\Documents\\ChatGPT\\GOING\\research\\NBA ensemble",
  "windows_destination_accessible_from_cloud": false,
  "windows_sync_verified": false,
  "files": [
    {
      "path": ".gitignore",
      "bytes": 53,
      "sha256": "0a46733feda65fb40b8ea5dfbb3734881e3d080ff2786ce60a66b2526c31fe4f"
    },
    {
      "path": "AGENTS.md",
      "bytes": 793,
      "sha256": "3c9b958cb027f6fd73534c7ff5d2a00a8ff67016af304701866435cbc0ae2a4b"
    },
    {
      "path": "NEXT_RESEARCH_TASK.md",
      "bytes": 2226,
      "sha256": "36153566936ebbc78fa3c3b9d94e798581ae0b7a0ef4f1cb32f3d6fed9bdddec"
    },
    {
      "path": "README.md",
      "bytes": 1391,
      "sha256": "d9099ab36db88b4557376ba083dd70850a78cc9366c70a2ab0bbf1f5b58e2c60"
    },
    {
      "path": "config/king_court_offer_2026-10-27.json",
      "bytes": 1616,
      "sha256": "cbf894fda29840ad9d7776c846507b6a9fd7a09666183e6dde1bc702745db44f"
    },
    {
      "path": "config/king_court_protocol_v1.json",
      "bytes": 1217,
      "sha256": "d82d599e9e3c61835e8495377bfae4e2d6c310185ff1d3aa455f583da974b3a3"
    },
    {
      "path": "config/nba_winners_v1.json",
      "bytes": 1819,
      "sha256": "19662dc96014a994799cb4af414fc3f4863e563c12b479007347dbcc603236d2"
    },
    {
      "path": "docs/KING_COURT_DISTRIBUTION_AUDIT.md",
      "bytes": 4143,
      "sha256": "98fb03c012f7e392a4cf2f940f990bef64a8239a9ba42fe3de6bcf5addc4fa57"
    },
    {
      "path": "docs/KING_OF_THE_COURT.md",
      "bytes": 14513,
      "sha256": "7ea7e593b41e62d139bdd66c9407c300c4806bd335a3c603a27519194c849b6e"
    },
    {
      "path": "docs/KING_OF_THE_COURT_SPEC.md",
      "bytes": 13070,
      "sha256": "c491e2757db2b2b1a7736e9a4fd67759815f426a95fee56fe2beb37f794c493f"
    },
    {
      "path": "docs/NBA_WINNERS.md",
      "bytes": 9954,
      "sha256": "66ad21df43d8feb44b70e618a4d3ff4177ba2c41b0c106983107ff92c60fda7d"
    },
    {
      "path": "requirements.txt",
      "bytes": 95,
      "sha256": "a00bbe8457eea7b61791bc6044f01ea0ecb3cee9e0eb4d99ecdd99a8859fe19a"
    },
    {
      "path": "research/king-court/README.md",
      "bytes": 3911,
      "sha256": "33623141fae21d90334b16017ea317e9b533444380638c5d1c889a821aed27bd"
    },
    {
      "path": "research/king-court/distribution-v2/PLAN.md",
      "bytes": 6657,
      "sha256": "c71f4e7f4551988062cb8405baa31e21992fa5ff3d6537e13176440ef6a3ffd1"
    },
    {
      "path": "research/king-court/distribution-v2/README.md",
      "bytes": 14520,
      "sha256": "8f465cb1a75d59ddcd2eea81b6d7072ed37bfbd568129ad4198b967c6567e995"
    },
    {
      "path": "research/king-court/distribution-v2/code-lock.json",
      "bytes": 3216,
      "sha256": "9472b2f0990cba4ca0c250c46709c112afbae7bf2dc0da0bb889d70ab8aabf20"
    },
    {
      "path": "research/king-court/distribution-v2/comparison-summary.json",
      "bytes": 72830,
      "sha256": "4a509a572b30a8ec9f432f1c293075c66f7bf68458e3fcbe720a4e793ddf95cd"
    },
    {
      "path": "research/king-court/distribution-v2/component-decision.json",
      "bytes": 746,
      "sha256": "1c1151921c561a83e48c1e02f9b12acd0fe4237520c2913050ec1389744590d9"
    },
    {
      "path": "research/king-court/distribution-v2/distribution-diagnostic.png",
      "bytes": 104331,
      "sha256": "942ffb40a5fc892e2ea245207be0ce483a5c0dfa726b45196f5549e4c66d54bc"
    },
    {
      "path": "research/king-court/distribution-v2/distribution-diagnostic.svg",
      "bytes": 62520,
      "sha256": "24dec5263d5507433cd3a7db9695ae4c91c584c013f25f82394019a682670e24"
    },
    {
      "path": "research/king-court/distribution-v2/registration.json",
      "bytes": 3612,
      "sha256": "f5b847ba358c2b82cbc2136926b863a02374b1c8ba6a4046e8b10e353a439286"
    },
    {
      "path": "research/king-court/distribution-v2/source-evidence.json",
      "bytes": 4519,
      "sha256": "2cc2e8ae4f9a4a2081bf82da22a08428f01a70f64946eecec4a4d2238e8601ce"
    },
    {
      "path": "research/king-court/distribution-v2/verification.json",
      "bytes": 3521,
      "sha256": "4177b150aa42c1aa2a9f521c6766e5dd0b685e7e98eb31324c24b72ec8951bc0"
    },
    {
      "path": "research/king-court/illustrative-output.json",
      "bytes": 4347,
      "sha256": "0ee8ef31f15cb5813f34645d9c8d0f891ca917fc32688347c6465a5c6212ce20"
    },
    {
      "path": "research/king-court/source-audit.json",
      "bytes": 7192,
      "sha256": "7322dd72b147afd7166777438abc200a8e155093b65a8b0de1278b4886c21f91"
    },
    {
      "path": "research/nba-winners/README.md",
      "bytes": 771,
      "sha256": "5bb357211ce7aca64e5c8427308f150ac4838bdf99a3f905dfc9b3017f4e9f0e"
    },
    {
      "path": "scripts/__init__.py",
      "bytes": 37,
      "sha256": "b2f3a05ccccfb4df18dfbb3bda1b0afcc9f6d6e29eae4038d01fe64b5a9508af"
    },
    {
      "path": "scripts/king_court/__init__.py",
      "bytes": 82,
      "sha256": "903c2182f161722f585927199cf8d32d4929bdf463c2546b0dcb5c4109a6d30c"
    },
    {
      "path": "scripts/king_court/__main__.py",
      "bytes": 13934,
      "sha256": "95b475ccac1029824f860c988503a9fb836607c737d051cd48885c3152199b8f"
    },
    {
      "path": "scripts/king_court/common.py",
      "bytes": 1738,
      "sha256": "57e679ac8af4d6ab0b52b05e124b4ad86a9c6579afcc0102ac59cb6fb44c5664"
    },
    {
      "path": "scripts/king_court/data.py",
      "bytes": 14046,
      "sha256": "9c29a6aa7874dea10cd6b94cc832e1b2b3837084fc662d6f040218d11f9a6bf3"
    },
    {
      "path": "scripts/king_court/demo.py",
      "bytes": 3449,
      "sha256": "870c38acd3bac2ef32df6847f66f773aa18b23a7ef7fb477a3a76bed77793b8a"
    },
    {
      "path": "scripts/king_court/events.py",
      "bytes": 6545,
      "sha256": "383ab7817be67a0d4639d781f2ecf0e76cdc1cfd0a5dd60ed5dc7e932daf6d2c"
    },
    {
      "path": "scripts/king_court/history.py",
      "bytes": 12022,
      "sha256": "d78ebf2229a69402bb8767dcdd7538dc88a419cea808393659ff18a94c8798e4"
    },
    {
      "path": "scripts/king_court/requirements.txt",
      "bytes": 141,
      "sha256": "233525bb282f887d7c71a7d76f62f92efec4b842e05a8f34e8ca5d09b38a8865"
    },
    {
      "path": "scripts/king_court/research.py",
      "bytes": 15248,
      "sha256": "cae614533574c3cede534331ab49523c5819f0df9121126a8c71e53221592c0c"
    },
    {
      "path": "scripts/king_court/simulation.py",
      "bytes": 14294,
      "sha256": "c4fe4becbe3ed4f8191cc1295024fa8b3a09840ea0f2f736783b711819aa72c9"
    },
    {
      "path": "scripts/king_court_diagnostics/__init__.py",
      "bytes": 84,
      "sha256": "f37938927ee7eb84f42425b163c9fdcd5bcee7a9aca5ac955f07b4a2825d6735"
    },
    {
      "path": "scripts/king_court_diagnostics/__main__.py",
      "bytes": 850,
      "sha256": "0e318c5a2474d3eeedc229f34b91655c4773bb756d58f4609a7e388db983299e"
    },
    {
      "path": "scripts/king_court_diagnostics/archive_audit.py",
      "bytes": 12897,
      "sha256": "e346eaf2e08e82a7e23b244ba8da4343c1253398ba75032f40b12bddca14608a"
    },
    {
      "path": "scripts/king_court_diagnostics/challengers.py",
      "bytes": 4610,
      "sha256": "c509663e2b7446c7a241efca080f54c02e3c1f4078c856426776b398885b633b"
    },
    {
      "path": "scripts/king_court_diagnostics/dataset.py",
      "bytes": 7849,
      "sha256": "f92a482979b473717aaea62e2359ebe5e413e20196574b70a6452f015f874537"
    },
    {
      "path": "scripts/king_court_diagnostics/experiment.py",
      "bytes": 11952,
      "sha256": "b39d51b59490a48471cea06e2fe3d6108374de472709f0e9ae36c19a434e86d1"
    },
    {
      "path": "scripts/king_court_diagnostics/metrics.py",
      "bytes": 10243,
      "sha256": "e40dd6d0e531e58dda8dcde8caed0a4d6acaa89300a3206c4fbedffdf2112c9d"
    },
    {
      "path": "scripts/king_court_diagnostics/pools.py",
      "bytes": 2746,
      "sha256": "19bd7faa4a92f9e400a3750149791e301c704008698d864d25a1512f6850603e"
    },
    {
      "path": "scripts/king_court_diagnostics/simulation.py",
      "bytes": 8142,
      "sha256": "818a8558f440831693558740e8b6f127e90e7d9b5d3f355c6b0668d8b5d1e8ce"
    },
    {
      "path": "scripts/nba_winners/__init__.py",
      "bytes": 83,
      "sha256": "5d71a2e91924e430177117039cf2e9ab744cee2fec979ecd17bbdb0ba0e9fa43"
    },
    {
      "path": "scripts/nba_winners/__main__.py",
      "bytes": 7914,
      "sha256": "f62bc00481cfe1713b26d488787186b62595ff22d87294a5ee9870f05c3b416e"
    },
    {
      "path": "scripts/nba_winners/data.py",
      "bytes": 5316,
      "sha256": "a9aabb071a0f996382982c34c6ceb8d505b88f89bc2d366ec5f0f47a79236f4d"
    },
    {
      "path": "scripts/nba_winners/evaluation.py",
      "bytes": 4901,
      "sha256": "7df735c568610021e2af9e054e72560b696156d326497a6fa9572b2dc76d9639"
    },
    {
      "path": "scripts/nba_winners/features.py",
      "bytes": 4608,
      "sha256": "3a9327e268b530147c1bba39d9d777f373c608f40bf6fb28b2eafab36e6a2e6f"
    },
    {
      "path": "scripts/nba_winners/models.py",
      "bytes": 4588,
      "sha256": "dcc7db013da96506095122ae4ee83b0f8d8ee1980204c4bfbd0de614751609c0"
    },
    {
      "path": "scripts/nba_winners/requirements.txt",
      "bytes": 207,
      "sha256": "8fe498a016230b6f0aa09a31c2d4eb9fa2995fd6af194c56e680853b2d942057"
    },
    {
      "path": "tests/__init__.py",
      "bytes": 36,
      "sha256": "bb18c11c01b69e2295514c73ad83428aec142ab44eba05f6f485d84b2cb82461"
    },
    {
      "path": "tests/test_king_court.py",
      "bytes": 18101,
      "sha256": "38b9f08ab97e9d13da868b9297783bc7be6f0b91b6e376f25e4ebc44e146c759"
    },
    {
      "path": "tests/test_king_court_diagnostics.py",
      "bytes": 10469,
      "sha256": "f621d9261738f25c04f57eab5e0cee24063dfd02b4bdc2bc933a929585aff030"
    },
    {
      "path": "tests/test_nba_winners.py",
      "bytes": 7958,
      "sha256": "ede0e6e1cb3609b34197da690cd2b9d5b1566dc346d22421fc775de9dd595c0c"
    }
  ],
  "total_bytes": 548673,
  "status": "source_and_reports_only_no_local_app_integration_or_Windows_copy_claim",
  "raw_data_cache_included": false
}
~~~

## Appendix D. Exact delivered test method inventory

These names identify implementation checks, not predictive-validation claims. The recorded total is 48 passing tests. Re-run locally to obtain a Windows result.

### tests/test_nba_winners.py (11)

~~~text
test_future_and_own_scores_cannot_change_pregame_features
test_lagged_score_and_unlagged_schedule_are_separate
test_future_season_is_not_a_prior_for_new_teams
test_regular_season_provider_flag_does_not_admit_allstar_or_cup_final
test_conflicts_unknown_venue_naive_times_and_tied_finals_fail
test_only_allowlisted_fields_enter_snapshot_and_source_tampering_fails
test_weight_prior_equal_then_rewards_lower_oos_brier
test_disagreement_is_disclosed_and_probabilities_complement
test_holdout_is_locked_and_reports_are_json_safe
test_all_six_algorithms_fit_and_produce_finite_complementary_forecasts
test_own_outcome_cannot_change_fitted_models_or_debate_weights
~~~

### tests/test_king_court.py (24)

~~~text
test_two_level_decay_and_missing_seasons
test_rookie_prior_never_invents_own_history
test_second_year_and_team_change_keep_skill_separate_from_role
test_future_results_and_late_source_receipts_are_excluded
test_full_field_and_tuesday_eastern_origin
test_source_age_and_unknown_rookie_status_fail
test_missing_historical_season_is_not_silently_ignored
test_integer_pra_pool_and_minutes_accounting
test_out_player_never_receives_allocated_stats
test_allocation_and_caps_reject_impossible_pools
test_ties_are_overlapping_events_not_normalized_win_odds
test_prize_pool_is_shared_by_customers_across_tied_players
test_simulation_does_not_invent_popularity
test_readiness_blocks_unselected_weights_and_missing_evidence
test_ownership_cannot_inherit_a_pool_from_another_date
test_prospective_field_needs_independent_preserved_identity
test_holdout_overlap_and_unregistered_weights_fail
test_source_box_accounting_and_unknown_minutes_fail_closed
test_settlement_requires_the_full_outcome_field_and_reports_cohorts
test_immutable_receipts_detect_changes
test_raw_events_and_five_player_stints_reconcile
test_missing_lineups_are_not_claimed_verified
test_conflicting_events_and_self_assists_fail
test_substitution_batches_reconstruct_minutes
~~~

### tests/test_king_court_diagnostics.py (13)

~~~text
test_only_declared_pool_hooks_differ_from_original_source
test_disabled_repair_reproduces_all_original_samples_exactly
test_paired_pool_center_and_integer_nonnegative_means
test_future_outcomes_cannot_change_fitted_opportunity_pool
test_repaired_simulation_preserves_integer_component_accounting
test_shuffling_preserves_player_joint_components_and_all_marginals
test_unknown_experience_is_not_fabricated
test_whole_game_block_challenger_keeps_recorded_stats_joint
test_metric_comparison_requires_identical_dates_and_field
test_original_sources_and_actual_time_registration_preserved
test_related_action_rows_are_not_false_conflicts_or_lost_credit
test_ambiguous_assist_name_is_not_resolved_by_guessing
test_conflicting_unique_record_id_fails
~~~

## Appendix E. Next-task file, unchanged

~~~text
# Proposed next task — not implemented

Deepen the existing model through pregame participation and minutes uncertainty. Preserve v1 and leave the unsupported FGA candidate inactive. Audit official timestamped NBA injury-report PDFs, team announcements, confirmed/projected lineup states, reconciled substitutions and exact-minute boxes. Verify source access, publication/retrieval times, historical coverage, revisions and game/player IDs before use.

Separate participation, available-player DNPs, minutes conditional on participation and production rates. Retain the rolling three-prior-plus-current-season boundary, chronologically selected recency, verified rookie/second-year priors, current-team role, ESS and season contributions. Unknown experience is not a rookie label. Do not infer pregame availability from eventual participation or use later announcements after the whole-slate cutoff.

Deliver the source-access audit and frozen diagnostic plan before changes. Select one supported subcomponent correction, preserving joint team-minute constraints and all other mechanisms. Do not invent questionable-status probabilities or injury multipliers. Compare the candidate with unchanged v1 and simple minute baselines on earlier development and later untouched complete Tuesday slates. Preserve existing registrations; append new experiments rather than modifying frozen definitions.

Evaluate participation calibration, minute distributions/zero mass/coverage, then paired PRA distributions, tails, maxima and sole/tied/inclusive leader probabilities. Group uncertainty by slate, separate Monte Carlo/parameter/input/predictive uncertainty, and report experience/role groups only when verified and supported. Oracle-minute improvements and passing tests are not predictive validation. Popularity/prize scenarios, interfaces and markets remain outside the change. Deliver one candidate and reproducible evidence with supported/unsupported/inconclusive verdict.

Free-source leads to verify: https://official.nba.com/nba-injury-report-2026-27-season/ and https://www.nba.com/players/todays-lineups . A projected lineup is not a confirmed lineup; public pages do not establish historical or machine-readable access.
~~~

End of handoff. Preserve the negative results, information boundary, complete-field requirement and separation between installation, integration and predictive validation.
