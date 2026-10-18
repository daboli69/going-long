# Phase 8.3 pre-registration: upset identifiers the champion hasn't seen

**Written 2026-10-18, before any of these metrics was computed.** This study is local to the lab only. Nothing is added to any model,
challenger or the GOING site.

**Question:** do any of these pregame metrics predict that the champion's favourite loses, *beyond the champion's own probability*?

## Definitions
- **Favourite:** the side the champion gives ≥ 50% (out-of-fold walk-forward probability `p_weighted_average`).
- **p_fav:** the champion's probability for that favourite.
- **Upset:** the favourite lost (ties excluded).
- **"As of":** every metric uses only completed games with kickoff before the target game. Season-to-date unless stated.
- **Sign convention:** every metric is signed so that **positive means expected to favour the underdog**. "fav − dog" means the
  favourite's value minus the underdog's.

## The nine metrics (fixed now)
| ID | Metric | Construction |
|---|---|---|
| M1 | Pythagorean luck | (win% − Pythagorean win%, exponent 2.37, points for and against) fav − dog. Requires ≥ 3 games for both teams, otherwise missing |
| M2 | One-score-game luck | shrunk one-score (≤ 8 points) win rate (wins + 1)/(games + 2), fav − dog |
| M3 | Fumble-recovery luck | share of all fumbles in a team's games recovered by that team, shrunk toward 0.5 with k = 10 fumbles, fav − dog |
| M4 | Turnover-margin regression | season-to-date turnover margin per game, shrunk toward 0 with k = 3 games, fav − dog |
| M5 | Letdown spot | favourite won its previous game by ≥ 17 points (0/1) |
| M6 | Lookahead spot | favourite's *next* game is against a division rival, and this game is not divisional (0/1). The schedule is known in advance |
| M7 | Road fatigue | favourite is playing its 3rd or later consecutive road game (0/1) |
| M8 | Officiating crew | the referee's mean accepted penalties per game in all his earlier games (≥ 8 games, otherwise missing). Positive = more penalties, i.e. more variance |
| M9 | Coaching aggressiveness | go-for-it rate on 4th and ≤ 3 inside the opponent's 60 (a run or pass attempted), dog − fav. Current season blended with the previous season at k = 10 attempts |

## Single historical check (one look only)
- **Window:** 2018–2025 out-of-fold games. These seasons are research-exposed, but none of these nine metrics has been examined
  before.
- **Per metric:** a logistic regression of favourite-won on logit(p_fav) and the metric (standardised). The **pre-declared
  direction is a negative coefficient** (a positive metric means the favourite wins less than its probability says).
- **Test:** a one-sided likelihood-ratio p-value, with **Holm correction across all nine**.
- **Reported:**
  - the coefficient;
  - the change in upset probability at +1 SD for a 65% favourite;
  - the sign in each season (consistency);
  - the number of games;
  - a walk-forward check (fitted on earlier seasons, scored on later ones), descriptive only.

## Decision rule
- **A metric passes** only if its Holm-adjusted one-sided p < 0.05 **and** the coefficient has the pre-declared sign in at least 5
  of 8 seasons.
- **A passing metric** becomes a frozen prospective upset hypothesis, judged only on games archived after registration. It
  requires 256 qualifying future games, and Holm applies across all passers. It never changes the champion.
- **A failing metric** is recorded as rejected, and is **not** re-tried with other thresholds or definitions.
- **If none passes,** the result is reported as a negative finding.

## Not allowed
- Changing any definition, threshold or direction after seeing results.
- Testing additional variants.
- Using 2026 weeks 1–6, or any future season, for anything but prospective evaluation.
