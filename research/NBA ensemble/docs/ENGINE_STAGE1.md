# Engine stage 1: availability (details fixed before scoring)

Code: `nba_lab/engine_availability.py`. These details fill in stage 1 of `docs/ENGINE_PLAN.md` and are committed before any score is computed.

**Population.** For each team in each completed regular-season game, 2021-22 to 2025-26: players whose latest released team is this one and who played for it in its last 82 games, plus anyone on any version of that game's official injury report published before the decision. This is the closest free stand-in for a historical roster. Players with no NBA minutes who never appear on a report are missing from it, and that limit is stated.

**Target.** Played at all (minutes above 0) in that game.

**Information.** Every official report version published strictly before the decision (first tipoff of the Eastern day minus one hour). The latest version gives the status. A team marked "not yet submitted" with the player unlisted counts as its own category. Box-score history uses games whose result is at least 12 hours old.

**Inputs:**
- Status at decision and the first status he had that day.
- Number of status changes and versions seen before the decision.
- Reason category: injury, G League/two-way, rest, personal, protocol, suspension or other.
- Listed Out/Doubtful in the team's previous game, and in how many of its last 5.
- Consecutive team games missed and days since he last played.
- Share of the last 10 games played, average minutes over them, started last game.
- Career games (capped at 82), team games this season, back-to-back.

**Baseline (clarifies the plan's wording).** Each status category's play rate in the training seasons, with "not listed" and "not yet submitted" as categories of their own. The plan's "0 for unlisted inactive players" is read as this not-listed rate. A literal 0 would give infinite log loss whenever an unlisted player plays, so it can't be the intended baseline.

**Model.** Gradient-boosted classifier with the same fixed settings as the minutes model; no tuning.

**Splits.** Test 2023-24 (train 2021-22 to 2022-23), 2024-25 (train through 2023-24) and 2025-26 (train through 2024-25).

**Gate (from the plan).** Primary: log loss on pooled test rows. Paired bootstrap over game nights (2,000 draws, seed 20261027). Pass if the 95% interval for the change is below zero, log loss improves in at least 2 of 3 seasons, and Brier is no more than 1% worse. Also reported: results by status, and how often a player listed as available at decision didn't play.
