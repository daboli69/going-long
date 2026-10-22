# Target, role and simulation research (Amendment10)

Open `launch_lab.bat` → Research → FPDS Research → **Targets, roles & simulations — Amendment10**. This is one view-only expander within the existing page, not another sidebar destination. It displays aggregate metrics only. The champion, simulator v1, default forecasts and old archives remain unchanged.

Manual commands from the lab directory:

```bat
run_fpds_simulation.bat status
run_fpds_simulation.bat audit
run_fpds_simulation.bat research --hours 2
run_fpds_simulation.bat resume --run EXACT_RUN_ID --hours 2
run_fpds_simulation.bat project --season 2026 --week 7 --sims 2000
```

Research uses the committed fixed trial budget and previously examined2022–2024 discovery. A completed run cannot be resumed or overwritten. Do not repeat a study as new evidence. Interrupted runs retain immutable blocks; resume requires the exact source/code/library fingerprints. Failed blocks remain skipped and disqualify the family. No2025/2026 model selection or spent evaluation command occurs. Commands set Idle priority and use cores minus two. A separate worker does the fitting; the app never fits on render. Stop with Ctrl+C to retain completed checkpoints. Models and row-level outputs stay ignored under `data/cache/fpds/amendment6/simulation10/`.

The explicit `project` command uses the predeclared frozen experimental parameters, without promoting them or replacing weekly defaults. It fits the role-enhanced shadow model using known outcomes through the last fully completed2026 week and earlier source-week final kickoff+24h, capped at actual creation time. It may read2025/2026 only for that frozen fit, never scoring or choosing a configuration from those years. Every new output records creation time, training cutoff, config/source hashes and source feature age. It fails if the requested future week has no prepared pregame candidate snapshot. Prepare future rosters/features through the existing weekly pipeline first; never guess future rosters. Cached A7 FPDS features are a dated source snapshot, not a live feed. Newly downloaded Inbox files require a new prepared source snapshot and preregistered source update before this study can use them.

`shadow_players_*.csv`, `shadow_games_*.csv`, fitted models and `SCENARIOS_PRIVATE.json` remain in the new private run directory. No raw FPDS columns are exported. Player output contains original point forecasts, simulation means/medians/ranges and a calibration warning; game output contains coherent discrete score-derived winner, margin and total values, with tie mass separate. Default residual intervals use earlier discovery OOF errors and are labelled unvalidated for transfer to2026; no in-sample residual interval is silently used. If unavailable, the output says calibration unavailable. Scenarios have unknown occurrence probabilities, and replacement mass stays in other players. Zero usage does not imply a bookmaker void or settlement rule.

Target reconstruction includes OT, kneels, spikes, explicit rushing/receiving scorer IDs and identifiable lateral yards. Only PBP participation or a unique PFR-to-GSIS roster mapping with positive offensive snaps establishes known zero outcomes. Ambiguous mappings, wrong-team context and incomplete lateral games remain unknown. Negative net rushing outcomes are legitimate; they are retained, not floored. This is not independent official box-score certification: no separate official player-stat table was found locally. Primary provenance: [nflfastR stat calculation](https://github.com/nflverse/nflfastR/blob/master/R/calculate_stats.R), [nflfastR field definitions](https://nflverse.r-universe.dev/nflfastR/doc/manual.html).

The six paths are corrected targets; empirical workload scenarios; a shared game-residual copula; a discrete opponent-adjusted drive model; explicit earlier role-change features; and position/role-specific interval checks. The copula is a statistical joint prototype, not one physically reconciled play-by-play model. It does not force player arithmetic into team totals. The drive model separately reconciles source scoreboard increments and includes defensive/special-teams score events. Unknown drive attribution or mismatched scoreboard games are quarantined. All historical comparisons use identical corrected known-label cohorts; their loss values cannot be compared directly with the older regulation/roster-zero cohorts.

Read `docs/FPDS_A10_PROTOCOL.json` for formulas, metrics and acceptance thresholds. An exploratory historical nominee still requires a separately frozen future test. No projection gap is a proven price edge; no staking or betting-return claim is made.

Method references: the [energy-score paper by Gneiting and Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) supports scoring full multivariate forecast distributions. [Ledoit and Wolf](https://www.ledoit.net/Well-conditioned2004.pdf) establish covariance shrinkage toward an identity target; this experiment uses a predeclared50% blend, not their fitted optimal shrinkage estimator. Neither reference establishes an NFL forecasting improvement.
