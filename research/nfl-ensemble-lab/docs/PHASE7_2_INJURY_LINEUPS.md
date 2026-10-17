# Phase 7.2: injury-adjusted expected lineups and independent football information

- **Branch:** `codex/nfl-ensemble-lab`, building on f90c3a2.
- **Unchanged:** the champion, the registered challengers, the registry's tracked versions and every archive.
- **Development-only work used** 2016–2022. 2023–25 were used only in the descriptive tables marked as such.

## 1. How injuries and players are used today
| Version | Official report | QB | Non-QB injuries | Player values |
|---|---|---|---|---|
| Champion v20261016_212540 | Only through the QB-out rule | v1 (previous starter) | **Ignored**: no injury group among its 6 feature groups | none |
| Phase 5 challenger | Out/Doubtful removed from a last-4-game lineup | v1 | Out/Doubtful only; Questionable = plays; IR not handled | RAPM (play participation through 2025) |
| Phase 7 challenger | Same as Phase 5 | v1 + v2 | Same as Phase 5 | Phase 5 RAPM + 2026 snap model |

**Already reflected in team ratings:** absences that have already lasted several games. Recent form (last 3/5) and the opponent-adjusted ratings were produced without those players.

**Genuinely missing:**
- New absences (the player was in the recent lineup but is out now).
- Questionable players' real participation odds.
- Starters who are absent without being on the report: in 2016–24 these were **5.0% of regular-starter games**, and prior-week reserve/IR status explains only 13% of them.

In 2016–24, **40% of team-games** had at least one regular non-QB starter confirmed out: OL 18%, DB 17%, WR/TE/RB 10%, LB 7.5%, DL 3%. The comparable figure for QBs is 3.9%. The champion sees none of the non-QB absences.

## 2. Injury data availability
- **NFL.com vs nflverse (week 6, 2026):**
  - nflverse had only 6 game statuses at Friday 17:03 ET and all 159 at Saturday 06:00 ET.
  - NFL.com, first fetched Saturday 09:56 ET, had all 159.
  - From now on, `extra_sources.source_lag()` measures, per week, when each source first carried the game statuses. `status_changes()` lists every change in practice or game status across the week. In week 6, 213 changes were recorded, for example "Budda Baker: no designation, full practice → Questionable, did not practice".
- **Source priority** (`extra_sources.PRIORITY_NOTE`):
  - The newest official report wins; NFL.com and nflverse carry the same league report.
  - Reserve/IR comes from the weekly roster or an ESPN "Injured Reserve" status.
  - A verified inactive exists only once rosters or ESPN mark the player inactive.
  - Practice participation is kept separate from game status.
  - A team without a report is **unknown, never healthy**.
- **Game days:** Thursday, Saturday, Sunday and Monday games use the report of their own week. The light refresh (3.1 s including the new sources) runs at every scheduled refresh.
- **Historical recovery (`lab/recover72.py`).** Each recovered record's availability time is a *third-party* timestamp; our retrieval time is never used.

  | Route | Timestamp | Coverage (regular-season games with game statuses captured before kickoff) |
  |---|---|---|
  | Internet Archive captures of nfl.com/injuries | capture time | **2025: 103 of 272 (38%)**, weeks 2, 3, 6 and 14–17 (plus 1 in week 5) |
  | GOING git history of `data/injury_context.json` (read-only) | CI commit time | **2026:** weeks 3–6 nearly complete, 1 game in week 2. GOING history starts Aug 2026, so it can't reach 2025 |

  - Where names match nflverse, the recovered 2025 statuses agree with it 92% of the time (week-3 check).
  - The rows are stored in `data/cache/recovered_injury_rows.parquet` and are **not used by any model**. Coverage is too sparse and uneven to train on, and the champion stays frozen.

## 3. Expected lineups (`lab/lineup72.py`, strictly as-of)
- **Normal lineup:** each player's average snap share over the team's last 4 games (verified PFR snap counts; 99.8%+ matched to player IDs).
- **Availability:** P(the player takes an offensive or defensive snap) given his game status and last practice status, estimated **only from seasons before the target season**. 2016 uses Out/Doubtful = 0, everything else = 1.
- **Confirmed absences:** Out; reserve/IR/PUP/suspended on the *previous* week's roster; no longer on the team's roster.
- **Accuracy for reported players** (Brier score, lower is better):

  | Seasons | As-of rates | Deterministic rule |
  |---|---|---|
  | 2017–24 | 0.111–0.130 | 0.164–0.190 |

  That is about 30% better than the deterministic rule.
- **Starter role matters** (2016–22, played rate):

  | Status | Starters | Others |
  |---|---|---|
  | Listed, no game status, full practice | 98.7% | 78.7% |
  | Questionable, full practice | 94% | 69% |
  | Questionable, limited practice | 78% | 55% |
  | Questionable, did not practice | 48% | 30% |

  The **tested features used pooled rates**, which understate starters' availability. This was discovered after the experiment, so it is left as a pre-declarable next step, not a post-hoc redesign. The live player table uses role-conditioned as-of rates and says so.
- **Features (32 + 3 matchups), as changes versus the normal lineup** (no double counting with ratings):
  - per unit (QB, OL, skill, DL, LB, DB): value change, expected missing snaps, starters expected out, starters confirmed out, and availability variance;
  - OL expected continuity, and OL same as last game;
  - matchups: trenches (own OL change + opposing DL change), passing, and total.
- **Player values** are Phase 7 snap-model ratings from that week's as-of fit (shrunk). Replacement = the unit's available bench at its own rated value. No arbitrary point values are assigned.
- **Bug found and fixed before commit:** "starters confirmed out" first required availability exactly 0, but the as-of rate for Out is 0.0001, so only reserve players were counted. After the fix, the identical pre-declared experiment was re-run once; both runs are reported and give the same verdict.

## 4–5. Independence from the shared ratings (`study72.independence`, development 2018–22, descriptive)
| Group | Mean R² explained by the champion's 85 features | Mean / max correlation of the unexplained part with the champion's margin error |
|---|---|---|
| Phase 5 player model | 0.70 | 0.02 / 0.08 |
| Phase 7 snap model | 0.66 | 0.01 / 0.04 |
| **Phase 7.2 lineup changes** | **0.13** | −0.02 / 0.065 |
| Phase 7.2 matchups | 0.21 | 0.01 / 0.01 |

**Most credible position signals** (95% CIs exclude zero):

| Feature | Correlation |
|---|---|
| QB snaps expected missing | −0.083 |
| Skill-position starters confirmed out | −0.064 |
| OL expected continuity | +0.065 |
| OL snaps missing | −0.06 (re-run 1) |

The signs make football sense: the champion overrates a team that is missing these players. The effects are small, and about 60 features were examined, so a few nominal hits are expected by chance.

The value-weighted unit deltas and matchup features carry much less signal than the simple availability counts. Player values from game-level snaps are too noisy to price individual absences reliably.

## 6. Pre-declared development-only experiment (`study72.experiment`)
**Declared in the module docstring before running:**
- **Candidates:** A = champion + lineup; B = A + matchups; C = player features + lineup + matchups, compared against player features alone.
- **Settings:** champion hyperparameters and an equal-weight six-model ensemble.
- **Rule:** gain on 2019–21 > 0, 2022 ≥ 0, and Holm-adjusted p < 0.05.

**Results (after the fix):**

| Candidate | Gain 2019–21 | Gain 2022 | Pooled gain 2019–22 (95% CI) | Holm p | Qualifies |
|---|---|---|---|---|---|
| A lineup | +0.0012 | +0.0017 | +0.0013 (−0.0017, +0.0044) | 0.43 | no |
| B lineup + matchups | +0.0002 | +0.0009 | +0.0003 (−0.0027, +0.0036) | 0.43 | no |
| C beyond player features | +0.0017 | +0.0019 | +0.0017 (−0.0014, +0.0047) | 0.43 | no |

- **Other metrics:** Brier and calibration improve slightly. Accuracy is unchanged for A, and +1.4 points for C versus its baseline. Effective model count is 1.26 vs 1.22, which is barely more diverse. Per family, the gains are mixed.
- **Verdict: no candidate met the standard, so no challenger was registered.** The registry still tracks exactly two challengers, and the candidates are recorded under `considered`.
- **Note on Phase 7:** under its weaker rule (no significance test), all three would have "qualified". The Phase 7 challenger was registered under that rule and stays frozen. Its prospective test will decide.

## 7. Live intelligence
The Model Debate page has a new section, "Expected lineups and injuries", for each team:
- starters expected out;
- confirmed absences;
- uncertain starters with their probabilities;
- OL availability;
- a per-player table: usual share, availability, basis (status and practice, or reserve), confirmed vs projected, expected share and player value.

It is labelled analysis that is **not** an input of the champion or the registered challengers, so it never explains their probabilities. The Advanced Football Intelligence page has a Phase 7.2 tab with the independence and experiment results.

## 8. Prospective tracking and operations
- The scheduler and archives are healthy: all 13 audit checks are OK.
- The feature rebuild before each stage now takes about 134 s (snap model + lineups), so final-stage forecasts archive about 27 minutes before kickoff. The tick runs every 5 minutes, and the lock is held for up to 40 minutes.
- No archived game had finished at commit time, so no prospective result exists.

## Limitations
- Availability means taking an offensive or defensive snap; special-teams-only appearances count as absences.
- 2025 has no verified report for 62% of its games.
- Player values are approximate.
- Any lineup features would only become usable by a model through a new pre-declared test plus prospective evidence.
