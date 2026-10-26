# Phase 14 results: QB value, information arrival, honest weekly monitoring

- **Pre-registration:** `docs/PHASE14_PREREGISTRATION.md`, commit 0d0795db, made before any result.
- **Code:** `lab/phase14.py` and `lab/sequential.py`. **Results:** `artifacts/phase14/` (local).
- **Ledger:** `research_ledger.json` and `docs/LEDGER.md`.
- Nothing was promoted. The champion, scheduler and GOING are unchanged.

## QB value model: single historical look (2021 to 2024)
- **Sample:** 229 QB-change games (games where the starting QB differs from the team's previous game), with γ fitted on 126 games from 2018
  to 2020.
- **The model:** an empirical-Bayes hierarchical model on EPA per dropback. The prior mean depends on draft pick, experience
  and career completion over expected, so backups with few dropbacks fall back to replacement level.
- **Fitted values:** QB skill varies with SD about 0.095 EPA per dropback (τ² = 0.009). Teams average about 39 dropbacks a
  game.

| Test | Result | Holm-adjusted p | Verdict |
|---|---|---|---|
| Q1: model QB change vs the market's QB adjustment at the open | r = 0.22 | 0.0007 | **Passes** (just above the 0.2 kill line) |
| Q2: log loss with the QB adjustment vs the champion | 0.602 vs 0.620 (difference −0.018, CI −0.042 to +0.007) | 0.074 | Fails |

For reference, in the same games the opener scored 0.593 and the close 0.561. The market still does much better.

**Kill rule outcome:** continue as a prospective monitor only (M6). It is not a challenger.

**Also reported:**
- Correlation of the model's QB change with the opening-to-closing line move: 0.33.
- Closing line value correlation: 0.54 with the QB adjustment, against 0.32 for the champion alone.

**Caution.** Historically the model is told who actually started. The market at the open may not have known that yet. Part
of the 0.33 and 0.54 may therefore be hindsight about timing rather than skill. Only frozen prospective forecasts can settle
it.

**The scale is too large.** The model's QB changes average 4.6 points against the market's 2.5 (slope 0.13). It ranks QB
changes reasonably but overstates their size. The fitted γ absorbs this inside the forecast.

**Validation against FiveThirtyEight's QB Elo adjustments** (via nfelo, 314 games):
- the model's QB change correlates 0.45 with FiveThirtyEight's net adjustment;
- the market adjustment correlates 0.47 with FiveThirtyEight.

So FiveThirtyEight's public QB values track the market more closely than this model does.

## Information arrival, 2026 (descriptive, growing weekly)
- **So far:** 2 QB1 depth-chart changes with archived lines (PHI, NYG). Neither moved the line within 24 hours.
- **Not matched yet:** ESPN "QB1 Out or Doubtful" events didn't line up with the depth-chart QB1 names. The archive starts
  on Oct 17.
- **Historical proxy (Phase 13):** QB-change games move 2.2 points from open to close, against 1.2 for others.

## Weekly monitors
- **Status:** every monitor starts at e = 1 (no evidence), because no final-stage game has finished since registration.
- **How to read a monitor:**
  - an e-value of 20 or more means the improvement is real at the 5% level, and it can be checked every week without
    inflating false alarms;
  - an e-value near or below 1 means no evidence.
- **These are additional.** Earlier fixed-sample rules (Phases 3, 8.4 and 11) stay authoritative.

## Frozen 2026 QB values
`artifacts/phase14/prospective/qb_values_20261026T213706Z.parquet` holds starter and backup values for all 32 teams. The
largest drops if the starter is out (in the model's inflated units) are NE −10.0, BUF −9.8, DET −9.4, TB −8.3 and CIN −7.9.

## Weekly loop (Travis runs it; nothing is scheduled)
```
.venv\Scripts\python.exe -m lab.phase14 freeze     before kickoffs (after depth charts and injuries refresh)
.venv\Scripts\python.exe -m lab.phase14 events     any time; adds new QB news events
.venv\Scripts\python.exe -m lab.phase14 monitor    after games; prints each monitor's e-value
.venv\Scripts\python.exe -m lab.phase14 ledger     after editing research_ledger.json
```
New ideas go into `research_ledger.json` with a gap, game share, cost and kill rule before any testing.

## Ranked backlog (from the ledger)
1. QB value (pinned)
2. Phase 11 opener blend
3. Late-news timing
4. Line-movement flag (S2P)
5. The p5 and p7 challengers
6. Practice-participation signal (not yet registered)

Killed: Kalman ratings, circadian, NGS separation, BDB tracking, Phase 8.3 and 8.5 angles, wind, and long tuning runs.
