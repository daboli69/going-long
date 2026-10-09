# GOING Score v2 (player situation index)

Version `going-score-2.0.0`. Display-only. **A higher score is not a better bet.** It is not a projection, a probability, an edge, or the football-case
GOING Rating (/100). It never feeds picks, stakes or the Champion.

Files: `scripts/going_score_build.py` (builder) -> `data/going_score.json` (schema `going-score-v2`); `config/going_score_weights.json` (frozen weights, rollback
note); `shared/going-score-player.js` (rank / filter / compare helpers); `tests/test_going_score_build.py`, `tests/going-score-player.test.cjs`;
pre-registered experiment `P4-1` in `research/trend-intelligence/LEDGER.md`. Built in `.github/workflows/data.yml` (continue-on-error).

## Definition

For QB/RB/WR/TE, as of week *w* using only games before *w*: how good is the player's underlying opportunity, and which way is it moving. Every component is a
recency-weighted (half-life 5 games, 12-game window, earlier seasons x0.7) mean shrunk toward the position average, z-scored against frozen 2021-2023
statistics, then combined with position-specific weights.

| Component | Meaning |
| --- | --- |
| opportunity | expected fantasy points per game (ffopportunity xFP) |
| team_share | share of the team's xFP |
| efficiency | actual PPR minus xFP per game (shrunk hard; mostly luck) |
| role | offensive snap share |
| availability | share of the team's last 8 games played |
| opp_trend / role_trend | last 3 games minus the preceding six (damped) |
| production | recent PPR/g, shown with weight 0: it is opportunity + efficiency, so weighting it would double count |

Fitted weights (non-negative ridge on next-game PPR, 2021-2023 only, normalised to 1):

| | opportunity | team_share | efficiency | role | availability | opp_trend | role_trend |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QB | .48 | .20 | .20 | 0 | .11 | 0 | 0 |
| RB | .38 | .22 | .11 | .13 | .05 | 0 | .10 |
| WR | .51 | .22 | .11 | .05 | .04 | 0 | .06 |
| TE | .49 | .22 | .05 | .13 | .03 | 0 | .08 |

`score` = percentile (0-100) of the weighted z-score among eligible players at the same position and week. `absolute` = the same value mapped to 0-100 with frozen
2nd/98th percentile anchors, so it is comparable across weeks. Tiers by percentile: Elite >= 90, Strong >= 75, Solid >= 50, Modest >= 25, Low. Eligible = at least 3
prior appearances and a game within the team's last 6. The JSON carries, per player: components (raw, percentile, z, weight, contribution, explanation), an 8-week
point-in-time history, 1- and 3-week deltas, risers/fallers, and flags (ROLE_UP/ROLE_DOWN with the existing 8-point snap rule, injury, roster status, limited sample,
rookie, availability risk). Data are public only (nflverse stats, snap counts, players; ffverse ffopportunity; GOING `nfl_roster.json`). **No licensed Fantasy Points
value is used anywhere.** `data/history.json` is used only to attach sleeper ids and for provenance; the 3 seasons it holds are too short for weekly point-in-time work.

## Validation (P4-1; weights fixed on 2021-2023, scored on 2024 validation and 2025 holdout)

Rows: regular-season appearances with >= 5 prior games (same rows for every model); predictions linearly calibrated on 2021-2023. Next-game MAE gain of the score,
2025 holdout (adjusted player-clustered 99.6% interval for the xFP column; 2024 in parentheses):

| Pos | n | Score MAE / R2 / rank corr | vs shrunk trailing xFP | vs shrunk trailing PPR | vs Champion window |
| --- | --- | --- | --- | --- | --- |
| QB | 508 | 6.34 / .06 / .25 | +0.3% [-1.7, +2.2] (+1.7%) | +0.7% (+1.2%) | +1.6% (+2.1%) |
| RB | 1488 | 4.33 / .47 / .75 | -0.9% [-3.4, +1.7] (+1.1%) | +0.4% (+0.3%) | +0.4% (+2.2%) |
| WR | 2530 | 4.12 / .39 / .67 | +0.9% [-0.5, +2.2] (+1.5%) | +1.4% (+0.9%) | +3.4% (+1.8%) |
| TE | 1570 | 2.99 / .41 / .68 | +2.3% [+0.5, +4.2] (+2.6%) | +3.8% (+3.5%) | +3.7% (+5.0%) |

Next-three-games 2025 gain vs xFP: QB -1.5%, RB -1.4%, WR +1.4%, TE +1.7% (all intervals include 0; 2024 WR and TE exclude it). Against the naive last-6 PPR average the
score wins by 3-8% in every cell. Verdict recorded in the ledger: PROMISING because TE clears the pre-registered bar; WR is non-inferior to xFP; QB and RB are not
distinguishable from shrunk trailing xFP.

**What it does and does not add.** Essentially all of the predictive content is shrunk, recency-weighted expected points. The extra components buy a small, position-dependent gain
(TE clear; WR modest; QB/RB nil) and, mainly, an *explanation*: the breakdown says why a player ranks where he does. Ablation (drop-one, MAE change): dropping opportunity costs 1-2% for RB/WR;
efficiency helps WR about +0.5-1% and RB inconsistently (consistent with Researcher B's half-weighted residual finding, though the fitted weight is smaller, .05-.20); role and role_trend help TE by 0.5-1%;
`team_share` and `opp_trend` add nothing measurable (opp_trend is fitted to 0), so xFP, target share, WOPR and air-yards share are counted once. A v2.1 should prune them and needs a new registration.
It does not use matchup, game script, injuries, or the betting market. Exploratory only: adding the schedule's implied team total moved MAE about -1.5%/-2.8% for QB (2024/2025) and ~0 for RB/WR/TE
(Researcher B reported +1-3% for RB; not reproduced here). It is not in the shipped score.

**Stability and responsiveness (2024-25).** Week-to-week rank correlation of the position percentile is .97-.99 for every model (score .972 QB, .986 RB, .985 TE, .988 WR; trailing xFP is
equal or marginally higher, .967-.992), so the score is not noisier than the baselines. After a +/-15-point two-game snap-share change the score percentile moves about 1.6x as far as trailing xFP/PPR
(RB 6.8 vs 4.4 / 4.1, WR 5.8 vs 4.0 / 3.5, TE 6.9 vs 3.7 / 3.4 percentile points, intervals exclude equality) - partly by construction, since snap share is a component, and this does not by itself
prove the faster move is more accurate; the next-game accuracy table above is the test of that.

## Limits

* Outcomes are conditional on the player playing, so availability's value is understated; injuries and role news that arrive after the last game are only in `flags`.
* R2 is pooled over all appearances including low-usage cameos (RB .47, WR .39). Restricted to regular contributors (shrunk xFP >= 8) it falls to .18 (RB), .08 (WR), .07 (TE) - in line with the
  independent ceiling of roughly .15-.35 per game. Football outcomes are mostly noise; the score reduces error by 1-4%, not 30%.
* QB games are filtered at >= 10 attempts rather than verified starts. Rookies and returners are shrunk toward the position mean and flagged `LIMITED_SAMPLE`.
* MAE/R2 here are scoring-error measures, not betting returns. No odds, prices or outcomes of bets were used; nothing here shows the score identifies profitable bets.
* Weights were fitted once on 2021-2023 and frozen. Any change of weight, half-life, shrinkage or eligibility is a new version and a new pre-registered experiment.

Rollback: see `rollback_note` in `config/going_score_weights.json` (restore the previous revision, rebuild, republish; nothing downstream consumes the score).
