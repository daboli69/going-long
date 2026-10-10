# Public passing-yards reproduction — October 10, 2026

The fixed refit has lower point error than the raw baseline in this matched public cohort, but its probabilities do not establish improvement over either the internal baselines or the sportsbook market. No model was fitted, changed or promoted. No profitability claim follows from these results.

This is a **retrospective reproduction of publicly published inputs**, distinct from the earlier 119-QB-game cache-based report. The earlier report's quoted-price extraction was defective and its figures remain unverified until independently regenerated on valid source receipts. The 2026 outcomes were previously inspected; neither split below is an untouched holdout.

## Frozen inputs and execution

`CONTINUATION_PROTOCOL.json` was written before evaluation. Its SHA-256 is `fe818b48746adb2fe03343c79cecec888c6bcad07995e514fc704baa3ea3b774`; Git ancestry is fixed at `c9cccd68619fac73a5c0c5c11fbff08f5b0be532`. The protocol hashes the production function, both fixed policy files, the public identity/schedule source and public outcomes. The result records the executed research-code hashes plus 131 quoted-snapshot and 70 consulted historical-snapshot receipts with full revisions, commit times and SHA-256 hashes.

Reproduce from the repository root without network calls or private files:

```powershell
& 'C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/.venv/Scripts/python.exe' research/prop-lines/public_passyds_replay.py --output research/prop-lines/out/public_passyds_replay.json
```

The standalone extractor can also export permitted public quotes to an explicit temporary directory:

```powershell
& 'C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/.venv/Scripts/python.exe' research/prop-lines/extract_git_props.py '<public-temporary-output-directory>' --revision c9cccd6 --market pass_yds
```

The replay reads only committed `data/nfl_betting.json`, committed `data/history.json`, frozen public `data/results.json` and the identified production/configuration code. It does not read `FantasyPoints/`, `StatApi/`, `private/`, credentials or licensed caches. The legacy cache-dependent scripts are not required by this execution path. Full Git objects and the exact hashed public files must remain available; changed inputs are rejected rather than silently substituted.

## Contracts and selection

These are actual prices recorded in public sportsbook snapshots, **not synthetic ladder lines**. Both prices come from one intact source row. Vendor update and repository receipt must precede kickoff; vendor time cannot follow the receipt. Exact canonical home/away teams and kickoff match the frozen completed NFL game. Player matching requires one exact normalized QB identity on those opponents.

Each model uses the newest public history committed by that quote's receipt, with a valid generation timestamp no more than 36 hours old. Only verified prior starts, strictly before the target game date, enter the last-12/730-day window. When public appearance rows omit a starter that the published model's sample count requires, the contract is excluded. That restriction prevents pretending that an incomplete window is the original model input.

Raw 80/20, superseded probability shrink, current fixed refit and equal-weight trailing models are recomputed on identical recovered histories. Their probabilities and market prices are averaged across matching books for a game/player/line. The main threshold is chosen by closeness of the no-vig market probability to .5, preferring two-or-more-book thresholds, **before** push or model/outcome exclusions. Pushes do not cause a substitute alternate to become the main line. No did-not-play outcome is imputed as zero.

## Cohort and attrition

70,954 passing-yards observations -> 35,325 non-DFS priced observations -> 34,183 proven pregame observations -> 7,153 distinct intact book contracts. The remainder includes future games and unpaired quotes, not just settled evaluation candidates.

| Exclusion/diagnostic | Book contracts |
|---|---:|
| No exact completed game at the frozen cutoff | 1,326 |
| Not a valid intact two-sided American quote | 1,632 |
| Invalid overround | 152 |
| No unique QB identity for the exact game | 337 |
| Incomplete recoverable public start window | 2,570 |
| Fewer than five verified prior starts | 101 |

Before model/outcome exclusions, matched markets contain 127 player-games and 127 market-selected main thresholds. There are 1,104 ineligible game/player/line groups. The final matched cohort contains **24 main thresholds across 24 QB-games, 24 players and 16 NFL games**, plus **373 alternate thresholds across 25 QB-games and the same 16 NFL games**. No pushes remain in the eligible cohort.

The registered early-week diagnostic (weeks 1–3) has zero fully reconstructable matched public windows. The later-week replication (weeks 4–5) contains the 24 eligible main thresholds. A missing early cohort cannot establish robustness across weeks or seasons.

## Main-threshold results

Each row contributes one matched QB-game. Point errors below compare the model distribution's median with observed passing yards; the posted main threshold is only an approximate market median. Shrink changes probabilities and retains the raw point estimate.

| Fixed method | Brier | Log loss | Median MAE, yards | Prediction minus actual, yards | Logit calibration slope |
|---|---:|---:|---:|---:|---:|
| Raw 80/20 | .2990 | .8095 | 68.87 | -28.40 | -.17 |
| Superseded shrink | .2918 | .7923 | 68.87 | -28.40 | -.26 |
| Fixed refit | .2745 | .7440 | 61.22 | -27.34 | -.99 |
| Equal-weight trailing | .2850 | .7698 | 61.88 | -28.43 | -.34 |
| Actual de-vigged market | .2500 | .6932 | 57.38 | -18.79 | Unidentified: nearly constant .5 prices |

The negative model calibration slopes are small-cohort diagnostics, not stable population estimates or new calibration parameters. Suppressing an unidentifiable market slope avoids the earlier report's misleading large-magnitude slope for virtually constant probabilities.

Paired differences are **refit minus comparator**, with negative losses favoring the refit. These 95% intervals resample complete NFL games (16 clusters), using the frozen seed and 2,000 draws; the JSON also includes a separate player-cluster sensitivity.

| Comparator | Brier difference [95% game-cluster CI] | Log-loss difference [95% game-cluster CI] |
|---|---|---|
| Raw | -.02443 [-.09782, +.04769] | -.06550 [-.24279, +.08866] |
| Superseded shrink | -.01728 [-.08585, +.04599] | -.04831 [-.21321, +.09058] |
| Trailing | -.01045 [-.04982, +.02424] | -.02575 [-.11156, +.04511] |
| Market | +.02452 [-.00232, +.05114] | +.05086 [-.00696, +.10551] |

All intervals cross zero. The refit's median MAE is 7.65 yards lower than raw in this cohort, but the probability comparisons do not meet the frozen improvement criterion. Market probabilities have lower observed losses. No incremental information beyond the market is established.

## Alternate-threshold diagnostics

These are **contract-weighted** results: QB-games with more posted alternate thresholds receive more weight. The 373 thresholds are not 373 independent outcomes. Game/player bootstrap preserves within-cluster dependence, but does not change that estimand into an equal-player-game assessment.

| Fixed method | Brier | Log loss | Logit calibration slope |
|---|---:|---:|---:|
| Raw | .2839 | .7735 | .24 |
| Superseded shrink | .2768 | .7567 | .23 |
| Fixed refit | .2503 | .6902 | .72 |
| Trailing | .2642 | .7238 | .46 |
| Market | .2308 | .6496 | 1.33 |

Refit-minus-market Brier is +.01946, game-cluster 95% CI [-.00663, +.04542]; log-loss difference is +.04054 [-.01288, +.09467]. The JSON's alternate model point MAEs inherit the contract weighting and must not be presented as general projection accuracy. Market point MAE is deliberately absent for alternates: a posted alternate threshold is not a forecast median.

## Remaining evidence requirements

The public route establishes a smaller matched forecasting cohort, not the earlier cache cohort or an executable betting strategy. A larger strict replay needs public, decision-time receipts containing all prior verified QB starts, including starts hidden behind relief appearances; precise source versions and historical availability receipts; and immutable real quote capture clocks. The existing point-in-time Git profiles can be extended prospectively without fitting anything. Revised current nflverse data could support a separately labelled retrospective-statistics sensitivity, but cannot replace missing historical availability/receipt evidence.

No wager execution, closing-price joins, stake sizes, settlement pushes/voids for actual bets, or all-season robustness are established. No ROI, CLV, profitability or production promotion is claimed.

Verification: nine new synthetic replay tests pass, including exact game identity, ambiguous QB exclusion, starter-window completeness, production-refit parity, outcome-independent main selection, constant-price calibration and complete-cluster bootstrap. The result JSON is the quantitative artifact; parent release validation owns the final tested commit.
