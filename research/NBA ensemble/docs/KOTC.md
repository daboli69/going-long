# King of the Court: live slate and backtest

King of the Court is the Tuesday promotion that pays the player with the most points + rebounds + assists (PRA) on the whole NBA slate. This app builds the full slate from free sources and runs Codex's unchanged simulator (`updates/.../scripts/king_court`) through `nba_lab/kotc.py`.

## Live slate (`python -m nba_lab.cli kotc --date YYYY-MM-DD`)

- **Games:** ESPN scoreboard for that Tuesday. The run refuses once the first game has started.
- **Field:** every player on each team's ESPN roster. Position and experience come from the same response. Debut season = current season - experience years + 1 (ESPN lists rookies as 0). An earlier NBA box score overrides that.
- **Availability:** the latest official NBA injury report published by the earlier of now and one hour before the first tipoff. Out or Doubtful counts as out. Questionable plays. If a team hasn't submitted, ESPN's own Out flag is used.
- **Minutes:** the team's current-season games (a missed game counts as 0) blended with the player's last 15 played games, worth 3 games. Someone with no minutes in 2+ current-team games is outside the rotation. Codex's simulator then scales each team to 240 minutes.
- **History:** Codex's fetch of the current season plus three prior, rebuilt when it's over 12 hours old.
- **Parameters:** a fixed grid member (season decay 0.65, 30-day half-life, 15 prior games). It is labelled unselected because no registered prospective selection exists yet.
- **Raw responses** are saved under `data/raw/archive/kotc`, and each run under `artifacts/kotc/<date>_<time>`.

**Prize share.** For one entry on player i: pool × P(i leads) × E[1 / (1 + other entries on every tied leader)]. Other entries are spread by an ownership scenario you choose on the page. Real selection counts aren't public, so every scenario is hypothetical. Results are bonus-bet face value, not cash.

## Backtest plan (committed before any run)

- **Slates:** every 2025-26 Tuesday once all teams have 3 released games: 21 slates, 2025-11-04 to 2026-04-07.
- **Field:** everyone with minutes for the team in a released 2025-26 game, plus anyone on that day's official report. Results count as released 36 hours after tipoff, matching Codex's retrospective mode. A real leader missing from this field counts against the model.
- **Configurations,** same slates and same parameters, 4,000 draws:
  - `codex_minutes`: Codex's own minutes estimate.
  - `rotation_minutes`: the explicit minutes scenario above.
- **Primary metric:** log of the probability (fractional tie credit) given to the actual leader(s), floored at 0.0001.
- **Also reported:** top-pick hit rate, against a naive "highest season-average PRA" pick, mean PRA error and inclusive-leader Brier.
- **Gate for `rotation_minutes`:** paired whole-slate bootstrap (2,000 draws). The 95% interval for the log-score gain must be above 0, and it must be better on at least 60% of slates. If it fails, the live page falls back to `codex_minutes`.

Limits: retrospective fields are reconstructions, not archived pregame rosters. Players returning after missing the whole season so far can be absent. 21 slates is a small sample for a rare event. The season was partly seen in earlier work.

**Deviation, recorded before final results.** The first run stopped on 2025-12-16: a player traded mid-season appeared on both of his teams. The fix assigns each player to the team on that day's official report, otherwise the last team he played for. Six earlier slates had been scored by then, and their partial log was seen. All 21 slates were rerun from scratch with the fix. No model setting, metric or gate changed.

## Backtest results (21 Tuesdays, 2025-26)

| | Codex minutes | Rotation minutes |
|---|---:|---:|
| Average probability given to the actual leader | 4.1% | 8.9% |
| Mean log score (higher is better) | -3.31 | -2.90 |
| Top pick was the leader | 2 of 21 | 3 of 21 |
| Naive pick (highest season-average PRA) was the leader | 5 of 21 | 5 of 21 |
| Average PRA error per player | 7.1 | 6.1 |
| Actual leader missing from the field | 0 | 0 |

Rotation minutes scored better on 17 of 21 slates, with a log-score gain of +0.41, 95% interval [-0.03, +0.74]. The interval touches zero, so **the gate failed**. Under the plan, Codex minutes would have stayed the default; see the owner override below. For scale, an even split across a typical 250-player field scores about -5.5, so both models carry real information. Neither model's top pick beat the naive pick, though. The leader is a rare, noisy event, and 21 slates is a small sample.

**Owner override, 2026-10-27.** After seeing these results, Travis chose to make rotation minutes the default on the page and the CLI (`--minutes rotation`), overriding the failed gate. The gate result above stands as recorded: this is a judgment call, not a passed test. Codex minutes remain available as the alternative.

The page offers both minutes models. Early in a season, Codex minutes can project stars far too low: on 2026-10-27 it gave Luka Doncic 18.7 minutes against 29.3 with rotation minutes.

**Codex simulator bug (not edited).** `capped_minutes` in `scripts/king_court/simulation.py` can't converge when 6 or more players on one team each draw more than a full game in the same simulated night: 6 × 48 exceeds 240. It happened once in 20,000 draws on 2026-10-27. `kotc.simulate` retries with one fewer draw, which changes the random stream, and records the retry in the run's `META.json`. Codex should fix this at the source.

## Learned minutes study (plan committed before any scoring)

**Model** (`nba_lab/minutes_model.py`): two parts. A classifier gives P(plays), a regressor gives minutes if he plays, and the scenario mean is their product. The SD comes from both parts, using the regressor's residual SD on games it didn't train on. Both are gradient-boosted trees with fixed settings, no tuning.

**Inputs,** all from games released before the decision time (first tipoff of the Eastern day minus one hour; results released 36 hours after tipoff):
- Current-team minutes over the last 1, 3 and 10 games, with missed games as 0.
- Started last game, and share of starts in the last 5.
- Share of the last 10 team games played.
- Recent played minutes on any team, and last season's minutes per game.
- Days since he last played, back-to-back, and whether he's a rookie.
- His status on that day's official report (Questionable, or Probable/Available).
- Recent minutes of teammates ruled Out/Doubtful (vacated minutes), his share and rank of the team's available recent minutes.

**Pool:** players whose latest released team is this one and who played for it in its last 82 games, plus anyone on that day's report for the team. Out and Doubtful players are excluded and their minutes count as vacated.

**Splits:** train 2021-22 to 2023-24 and measure residual SD on 2024-25, then train 2021-22 to 2024-25 and score 2025-26. The minute-level comparison against the rotation rule uses the same 2025-26 player-games.

**Gate, to replace rotation minutes as the default:** rerun the same 21 backtest Tuesdays with learned minutes. Field players with no learned row fall back to rotation minutes, and that count is reported. Primary metric: the same log score of the actual leader. Pass if the paired bootstrap 95% interval for the log-score gain over rotation minutes is above 0, it's better on at least 60% of slates, and minute MAE on 2025-26 is lower. A pass makes learned minutes the default. A fail leaves rotation minutes in place, and the minute-level results are still reported.
