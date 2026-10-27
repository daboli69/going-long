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
