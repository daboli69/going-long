# QB availability at a fixed decision time

Completed 2026-10-27 using the frozen 2026-10-26 23:31:41 UTC evidence packet. Protocol committed before calculation: 9717da6b. One configuration registered; zero fitted; zero challenger forecasts. Verdict: **inconclusive**. This does not establish that QB availability is useless or that a challenger improves predictions.

## What the originals support

There are 161 ledger records covering 27 games in weeks 6-7. All 27 have a champion snapshot before kickoff minus 90 minutes; 26 identify both QBs actually represented by the champion. The raw evidence includes 207 ESPN injury versions, 21 nflverse injury revisions, 22 phase7 source versions and 243 market files. Thirteen team/game sides have injury rows matching the champion's QB ID. Useful injury observations exist.

The strict registered feature requires affirmative starting availability for both teams and an identified replacement when the champion-assumed QB is unavailable. Structured injury status, active-roster status and depth rank do not establish that confirmation. Narrative reports have not been independently converted into verified starter announcements. **Zero fully evidenced challenger rows were established**, not zero usable injury rows. The current depth file has 703,227 dated rows but no archived original depth-file versions proving historical local availability. No older frozen-champion prospective forecast archive was found. The champion manifest records creation on October 16 and seasons 2016-2026, but no explicit last training-outcome timestamp; this audit preserves that limitation rather than inferring an exact training cutoff. The existing observations are also prohibited from fitting/selecting a challenger under the 2026 descriptive-only rule.

At the decision time, the selected champion snapshots were **1,349.04-1,349.93 minutes old**, about 22.5 hours. They were created around kickoff minus 24 hours. Later kickoff-minus-60-minute forecasts cannot be used at the earlier 90-minute cutoff. This is an important forecast-age mismatch with the market comparator, not evidence that a refreshed champion would have the same error.

## Descriptive benchmark, not a challenger test

The primary comparison has 23 completed games, using a two-sided DraftKings quote observed within 60 minutes before the decision. All selected market records use retrieval-time proxies; independent quote publication times are unavailable. No new odds requests were made. Lower loss is better.

| Metric | Frozen champion | Available market | Champion minus market |
|---|---:|---:|---:|
| Log loss, n=23 | 0.810985 | 0.731530 | +0.079455; paired game 95% CI [-0.002409, +0.158668] |
| Brier, n=23 | 0.302740 | 0.262083 | +0.040657 |
| Accuracy, n=23 | 52.17% | 56.52% | -4.35 percentage points |

The registered 30-minute sensitivity retains 16 games: log-loss gap +0.132965 [0.037517, 0.226379]. The 120-minute sensitivity retains 26: +0.076201 [0.002325, 0.146561]. These change sample composition; they are not interchangeable evidence or a choice of the best result. Only two weeks are represented, so week-level dependence cannot be estimated reliably. Five-bin reliability tables are in RESULT.json. There is no challenger column because no challenger was fitted.

## Error attribution and power

On 23 common games, the arithmetic gap to the last archived pre-kickoff market is +0.081444 log loss: +0.079455 champion-versus-decision-market plus +0.001989 decision-market-versus-later-market. The last observed quote is not proven to be the actual closing quote. These terms do not identify causal shares of model weakness and delayed news; forecast age, unknown quote updates, other injuries and simultaneous news remain confounded. The current game table's retrospective closing probability is retained separately per row, never an input or proof of decision-time knowledge.

Winner inference uses fitted classifiers; the neural-network training path switches to evaluation mode. This study does not use the props Monte Carlo simulator. No same-input, repeated-seed forecasts were archived, so numerical simulation variance was not estimated. More simulations would not repair missing information timestamps.

The declared useful improvement is 0.010 log loss. A utility threshold cannot be derived from statistical power alone. At assumed paired-loss SD 0.10 / 0.20 / 0.40, approximate 80% power requires **785 / 3,140 / 12,559 games**. At n=23, detectable differences are approximately 0.058 / 0.117 / 0.234. These are planning scenarios, not measured challenger effects, and dependence can worsen them. Even perfect reconstruction of these 27 games would not establish a small improvement. The existing week-18 review remains the stop point; no automatic extension.

## Exact evidence still needed

1. An original champion snapshot at the chosen decision time, with the actual QB IDs/inputs, training cutoff and immutable configuration hashes. Retain its age explicitly.
2. Original source evidence establishing starting availability or replacement identity, stable IDs, publication time when known, retrieval time and full-file hash. Preserve conflicts and missingness. An absent injury row is not affirmative evidence of health or starting status.
3. A same-book, two-sided market observation near that decision, with source quote time when available. Preserve observations even when prices are unchanged, so deduplication does not hide freshness. This is a proposed archive improvement, not a scheduler change made here.
4. An authorized chronological training cohort and later untouched evaluation cohort large enough for the registered effect. Current 2026 data remain descriptive; spent historical holdouts were not reopened.

The single registered candidate is a shrunk, one-coefficient adjustment to champion log odds for a verified home-versus-away QB downgrade. It addresses a mismatch between the QB encoded by the champion and the QB confirmed available. It does not claim to solve receiver injuries, overall team strength, props or simulation design. Forecast creation is blocked until evidence and fitting requirements are met; no replay was backdated as prospective.

## Reproduction and verification

Packet: `artifacts/qb_asof_audit/20261026T233141896293Z/`. It contains SAMPLE.json, SELECTED_SNAPSHOTS.json, QUOTES.json, INJURY_TIMELINE.json, STRUCTURED_QB_SOURCES.json, frozen games_at_audit.parquet, RESULT.json and a 528-file SOURCE_MANIFEST.json. Full-file hashes cover provenance omitted by the original forecast's selective content hash. Hashes computed now establish present byte identity, not original publication time. Mutable cache files may change afterward; the frozen outcome copy is authoritative for this packet.

An independent reviewer rebuilt all 27 snapshot selections from the original ledger's frozen prefix, verified selected quotes against 11 original source files and independently reproduced log loss, Brier and the 2,000-draw bootstrap to 1e-14. See REVIEW.json and independent_reproduce_v2.py. The reproduction script is in the packet and runs with the lab Python. It reads frozen outcomes, not today's results. The first reviewer script's Windows path-separator assertion was corrected in a separate version and retained. The initial audit run was stopped for repeated timestamp-parsing overhead before metrics were emitted; ABORTED.json records it. Neither event involved fitting or changing thresholds.

To create a new, separately dated descriptive packet: `.venv\Scripts\python.exe -m lab.qb_asof_audit`. This reads local sources and writes only a new artifact directory; it does not fit or fetch. To reproduce this packet: `.venv\Scripts\python.exe artifacts\qb_asof_audit\20261026T233141896293Z\independent_reproduce_v2.py` (rerunning verifies the calculations and preserves the existing REVIEW.json).

Champion manifest/bundle and pinned release hashes still match the frozen manifest. Existing archives, forecasts, scheduler and champion remain unchanged. No network calls, paid services, props eval, promotion, push or deployment were performed for this study.

Validation: full local suite 536 passed, 1 existing skip, 524 warnings; seven new audit tests passed. Warnings originate in existing modules and dependencies. Compilation and diff checks passed. Thirty protected original forecast/model/release files retain their frozen SHA-256 values.
