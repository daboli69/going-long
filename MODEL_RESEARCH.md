# Model research

Takeover baseline: `3f2651e`, 2026-10-10. Champion stays unchanged. Research claims require decision-time data, chronological validation, paired market comparison, uncertainty, and an untouched holdout before promotion.

| Hypothesis / audit | Evidence | Test | Result | Status |
| --- | --- | --- | --- | --- |
| Passing-yards refit adds information beyond market | Existing `research/prop-lines/out/passyds_lines.txt`, n=119 QB-games | Source/aggregate inspection; original historical inputs unavailable | Inherited main Brier .2627 refit vs .3055 raw and .2500 market; MAE 61.6 vs 73.6 raw and 59.2 line. Extraction defects require regeneration; not reproduced Codex performance | Empirical validation blocked; no promotion |
| Historical quote reconstruction is point-in-time and two-sided | `research/prop-lines/build_quotes.py` | 10 offline regressions: asynchronous sides, late observations, ambiguous identity, market/date eligibility | Confirmed groupby.last fabricated mixed-observation pairs and receipt cutoff missing. Fixed intact observations with both clocks before kickoff, reject ambiguous IDs/non-REG dates | Engineering repair verified at 52c5b79; aggregates unverified |
| First-TD normalization/outcome refer to the same game | `scripts/first_td_quote_summary.py`, `research/prop-lines/td_live_and_firsttd.py` | Five isolated tests: concurrent games, team order, partial runners | Exact scheduled game, same-game scorer and per-game coverage/overround replace date aggregation | Engineering repair verified; first/last-TD predictive validity unproven |

Do not access or publish excluded private/licensed inputs, invent missing prices or treat synthetic regression fixtures as performance evidence.

Before any next fit, freeze dataset hashes, exact game/player/market/book/line/side contracts, decision-time availability, push/void/nonparticipant policy, chronological folds and untouched later holdout, same-sample Champion/market/simple baselines, clustered uncertainty and acceptance thresholds. General historical joins need exact event/team/player provenance, not dates/names alone. No repeated holdout tuning. CLV/ROI require real matched timestamped prices and settlements. Failed hypotheses belong here. Champion and ABBEYS remain unchanged.


Continuation 2026-10-10: frozen public reproduction protocol and report in `research/prop-lines/PUBLIC_REPRODUCTION.md`. No fitting or production parameters changed. Parent rerun matched result SHA256 `a6441f719f3a31aaa84662bfbc771fb9a608988aeef252900bd000b6a5872768`.

| Hypothesis | Evidence / matched sample | Result | Status |
| --- | --- | --- | --- |
| Fixed refit improves raw/trailing probability losses | Public pregame Git receipts, complete prior-start histories; 24 main QB-games / 16 games; 2,000 paired game-cluster bootstrap draws | Brier raw .2990, refit .2745, trailing .2850; refit-raw -.02443 CI [-.09782,+.04769], refit-trailing -.01045 [-.04982,+.02424]. Median MAE refit61.22/raw68.87/trailing61.88 yards | Descriptive point-error gain; probability superiority unestablished |
| Fixed refit adds information beyond actual market | Same intact two-sided posted prices, proportional de-vig, same eligible sample | Market Brier .2500; refit-market +.02452 CI [-.00232,+.05114]. Alternates373 contract-weighted thresholds: refit .2503 / market .2308, delta+.01946 [-.00663,+.04542] | No supported edge, no promotion |
| Earlier 119-game result survives corrected extraction | Private excluded source cohort unavailable; public cohort excludes incomplete historical windows | Qualitative lower refit-v-raw error/no market edge persists; numeric before/after not same sample. Early weeks have zero complete recoverable windows; no untouched holdout or robustness | Prior numbers remain unverified; larger cohort blocked |

These are retrospective public-source results, not synthetic line tests or bet execution. Alternate contracts are dependent and menu-weighted. Do not turn unstable/negative small-sample calibration slopes into fitted parameters. Keep Champion/ABBEYS fixed; collect complete prospective input/availability/price receipts and preserve untouched later outcomes before another model gate.

### Fanatics Sunday filter audit — 2026-10-10
Independent code review rejected default exclusion of all TD probabilities above60%: calibration slope near0.7 alone does not support that threshold. Removed only the unsupported product candidate filter; Champion probabilities/calibration unchanged, no model promotion. Joint ranking retains independence/uncalibrated uncertainty warnings. Engine exhaustive checks1000seeded pools matched; this validates arithmetic, not predictive performance or betting edge. Existing corrected24-QB public replay and market comparison remain unchanged. Actual113Fanatics quotes are receptions only; zeroATD, no synthetic-price profitability evidence.

### Saturday isolated research — 2026-10-10

Full active-model inventory, all requested feature availability/duplication/missingness/target checks and ranked next experiments: [complete Saturday inventory and research report](docs/SATURDAY_MODEL_RESEARCH.md). Baseline `c8164da`; separate research branch, protocols committed before their evaluations (`c28960c`, `a7a7bd1`). Production/Champions/frozen Week5 unchanged.

| Hypothesis / evidence | Test / result | Decision |
|---|---|---|
| Existing public passing replay reproduces | Independent rerun byte-identical SHA256 `a6441f719f3a31aaa84662bfbc771fb9a608988aeef252900bd000b6a5872768`;24QB-games/16games, refit Brier.2745 vs actual market.2500; intervals cross0 | No market advantage/new promotion;119-game claim still unverified |
| Fixed Beta(1,1) ATD scoring-frequency challenger improves current policy | New public pregame Git-receipt rolling histories:1243player-games/63games;frequency Brier.14126 vs reconstructed fixed current.13836, delta+.00290[-.00048,+.00621];logloss improves, mean probability.234 vs scoring rate.180 | Fails dual-loss/calibration gate;research-only,no fit/promotion |
| Existing v2 ATD policy improves older published v1 | Identical public histories:current Brier.13836 vs published.14299, delta-.00463[-.00767,-.00210]. Current was not deployed at those historical decisions. Matched actual two-sided market775/57games Brier.14251 vs current.15266;current-market delta+.01015[+.00480,+.01572] | Supports inherited direction only;no new live accuracy/edge claim.334current zeros include22scorers:role-conditioned prior next hypothesis |
| Five-slip at-least-one objective handles overlap | Exact inclusion-exclusion and finite joint-law evaluator;independent truth-table oracle plus five-entry exhaustive check;explicit player-independence assumption | Synthetic mathematical validation only;current Fanatics ranking retained,no real portfolio probability recommendation |

Current2026context has0charted dropbacks/personnel observations;all985pooled route fields null. Prior-season charting is not current coverage. No private/licensed raw study rerun, paid calls, holdout re-fit, alerts or deployment. Future availability/input/price receipts and sealed later outcomes required for calibration/model gate. Research artifact arithmetic independently checked with stdlib implementation;parent owns final integration/release validation.

Release repairs correct FirstTD arithmetic and suppress unverified availability/settlement outputs; they do not change TD/passing Champion coefficients or promote research. Research artifacts remain on `codex/saturday-model-research` at `030dd62`; parent independently verified metrics and 26 focused tests. Repaired production source hashes intentionally differ: original today-ranking v3 generator registration stays immutable and new capture fails until a separately registered version is approved.

### User-requested DFS current-season baseline — October 11

Scope hypothesis: every production DFS score/spread should depend only on completed2026games. Strict means of available core player stats and observed DK bonuses (n>=2); observed spread proxy(n>=3); partial current-season D/ST scoring(n>=3). Prior-year fits, sportsbook blends, injury multipliers and covariance removed from these DFS paths only. Actual587-row slate supports241players/22defenses; all samples2–4games. Prior-year/FPPG mutation invariance and438profile arithmetic identity pass; **these are scope/math checks, not predictive validation**. No new holdout fitting or betting Champion/ABBEYS promotion. Accuracy/correlation/matchup improvements remain research-only pending frozen chronological out-of-sample evidence. Supplied overall/outside/slot defense exports have4games and incomplete season metadata; no licensed rows published or arbitrary multiplier applied. Rollback: revert scoped DFS repair.
