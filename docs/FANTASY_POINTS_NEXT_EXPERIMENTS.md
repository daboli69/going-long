# Next FantasyPoints experiments (drafts for the local session; not frozen)

These are hypotheses, designs and gates written without the data in view. A protocol is frozen only when the local session commits the spec
and its hash **before** running it (E13/E14 were registered and run in one command; do not repeat that).

## Season-level vs weekly player-prop forecasting
E1-E6, E13 and E14 predict a season's per-game average from the previous season. They say little about forecasting one player's next game.
Weekly forecasts need per-game features known before kickoff, built only from earlier weeks (P3-2/P3-3 did this for receiving and rushing role).

## Do historical weekly exports support TD, pace and in-season experiments?
From `config/fantasy_points_tables.json` and the local inventory in the handoff (by-game panels for 2021-2025; confirm locally):

| Question | Historical weekly support | Verdict |
| --- | --- | --- |
| Receiving TD role | `receiving_advanced_weekly` has end-zone targets, end-zone TDs, inside-20 targets, deep targets, XFP per game | **Testable** on 2021-2025 with rolling prior weeks; compare against the free-data scoring-role blocks (JP-2/3/4) |
| Rushing TD / goal-line role | `rushing_bell_cow_weekly`: snap, carry and XFP shares; **no inside-5/10 carries**. `offense_snaps` inside 5/10/20 exists for 2026 only (through week 4) | Development blocked for goal-line carries; **prospective capture only** |
| Team pace, pass tendency, scoring environment | `run_pass_report_weekly` (team-game snaps, pass/rush by half, score state, red zone); **missing for 2024** | Testable on 2021-2023 and 2025; the 2024 gap shrinks the sample and must be reported |
| In-season receiving/rushing role | weekly routes, bell cow, advanced | Already done (P3-2/P3-3): free role signals beat the baseline; FantasyPoints role fields added at most +0.2% |
| Separation, QB pressure, coverage matchups in-season | season-to-date snapshots only, or 2026 through week 4 | Not point-in-time historically; **prospective** |

Four weeks of 2026 data limits current-season validation. It does not prevent historical development on the 2021-2025 weekly panels or
prospective shadow collection.

## Candidate experiments, in priority order
1. **TD scoring-role with weekly end-zone/inside-20 targets (P5-1).** Hypothesis: adding prior-week end-zone targets, end-zone TDs and inside-20 targets to the JP-2 anytime-TD blocks improves Brier/log loss over the free-data blocks. Unit: player-game; features from weeks strictly before the target week of the same season plus labelled prior-season priors. Split: development 2021-2023, validation 2024, holdout 2025 (already examined by P3-x/JP-x: disclose it; 2026 Weeks 6+ is the only untouched set). Baselines: Champion v2 anytime rate, JP-2 free-data model. Metrics: Brier, log loss, calibration slope, game- and player-clustered intervals, by position. Acceptance fixed in advance before any outcome is read.
2. **Pace/total environment against matched pregame prices (P5-2).** Hypothesis: prior-week team snaps per game and pass tendency improve the forecast of the game total beyond the market-anchored baseline. Needs the actual historical pregame total from the odds archive for the same games (2024-2026 only; the 2024 pace gap applies). Compare the model's P(over L) with the de-vigged pregame P(over) from the same book, line and snapshot using `scripts/missions_history_export.py` and `scripts/missions_backtest.cjs --model` (see below). This answers "does football data add information beyond the available price?", not CLV.
3. **Prospective shadow evaluation.** The weekly folders already ingest automatically. For 2026 Weeks 6-10 record, before kickoff, immutable forecasts for the receiving Challenger, the TD blocks and the pace model, with the matched pregame price, and score them once after the games. This is the only untouched holdout.
4. **Re-test E14 properly if wanted:** more QB seasons are not available, so a weekly or pooled (pressure x offensive-line) formulation, registered first, or leave it as inconclusive.

## Matched pregame-price comparison (what is and is not claimed)
Pregame odds need not be closing prices. A fair comparison requires the same book, game, market, selection, line and snapshot, an actual game
(verified schedule), the snapshot strictly before the actual kickoff, both sides of a two-way market, pushes and voids removed from the outcome,
and a model forecast whose `asOf` is not later than the snapshot. `scripts/missions_backtest.cjs --model forecasts.json` enforces the last point:
forecasts keyed `"<gameId>|<market>|<line>"` with `{p, asOf}` where `p` is the probability that side A (home, over or home moneyline) wins; a forecast
dated after the board is refused and counted. The report scores the model and the equal-weight market on the **same records** with a paired cluster bootstrap by game. CLV claims
need verified closing observations, which this archive does not provide, so none are made.

Player-prop comparisons need the exporter extended to prop markets (player identity, line and side matching); it currently exports game lines only.

## Asks of the local session
* Run the experiments above only after committing the frozen specs and acceptance rules.
* Count unique files (198), not copies (341), in any coverage claim.
* Keep licensed data, archive contents and credentials out of Git.
