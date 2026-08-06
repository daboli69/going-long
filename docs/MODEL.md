# The model

Everything resolves to expected PPR points per game. Four layers feed a
projection, the projection feeds VORP and a lineup solver, and those feed the
one number on the board.

---

## Layer 1 — ADP expectation

The guide fits expected PPR points per game against overall ADP by position
using 2014–2025 data. Those curves were re-fit here as

```
PPG = a + b · ln(ADP + c)
```

| Pos | a | b | c | R² | worst residual |
|-----|---|---|---|----|----------------|
| QB | 43.9683 | −5.2690 | 59.75 | 0.9917 | 0.35 |
| RB | 35.2964 | −5.2544 | 22.00 | 0.9985 | 0.26 |
| WR | 49.7475 | −7.6306 | 59.75 | 0.9902 | 0.57 |
| TE | 29.8234 | −4.1146 | 22.00 | 0.9977 | 0.24 |

Fitted to anchor points read off the printed chart, so treat them as ±0.3 PPG.
The shapes are what matter: QB is nearly flat across the whole board while RB
falls off a cliff early. That difference is the entire supply-and-demand
argument, expressed as a function.

Sample output:

| ADP | 1 | 12 | 24 | 36 | 60 | 120 | 180 | 250 |
|-----|---|----|----|----|----|-----|-----|-----|
| QB | 22.3 | 21.5 | 20.6 | 19.9 | 18.8 | 16.6 | 15.1 | 13.7 |
| RB | 18.8 | 16.8 | 15.2 | 14.0 | 12.1 | 9.3 | 7.4 | 5.8 |
| WR | 18.4 | 17.1 | 16.0 | 14.9 | 13.2 | 10.1 | 7.9 | 6.0 |
| TE | 16.9 | 15.3 | 14.1 | 13.1 | 11.7 | 9.4 | 8.0 | 6.8 |

## Layer 2 — the rankings

A ranking is an ordering, not a projection. To put the guide's board on the
same points scale, a player's overall rank is treated as an ADP slot: rank 14
is priced at what pick 14 has historically returned. The slider blends that
against his real ADP:

```
proj = mktPts + wRank · (rankPts − mktPts) + wMS · msEdge
```

At `wRank = 0` the board is pure market. At `1.0` it is pure guide. Default .60.

## Layer 3 — Market Score

Market Score is a 0–100 model of where ADP is wrong, published only for RB/WR
inside the top 120 and QB/TE inside the top 180. To turn a score into points:
re-rank the scored players within their position by Market Score, find the ADP
slot that new rank corresponds to, and take the difference in expected points
between that slot and the player's actual ADP.

A back the model likes far more than the market gets moved up the ADP curve,
and the points he gains in the move are his edge. Players without a score
contribute zero and fall back to plain ADP expectation.

## Layer 4 — replacement level and VORP

Scoring-format-aware baselines come from the guide's "Positional Rank Averages
By Scoring Setting" table (PPG at positional finishes 6 through 72 in PPR, half
and standard), linearly interpolated between steps and extended along the final
slope past 72.

Replacement rank is derived from your league's real starting slots. Dedicated
slots count fully; flex slots are split by how leagues actually use them:

| Slot | Split |
|------|-------|
| FLEX | RB .30 / WR .50 / TE .20 |
| WRRB_FLEX | RB .45 / WR .55 |
| REC_FLEX | WR .70 / TE .30 |
| SUPER_FLEX | QB .70 / RB .10 / WR .15 / TE .05 |

`replacementRank[pos] = round(teams × effectiveStarters[pos])`, and the baseline
is that rank's PPG. QB has no table column, so its baseline is the ADP
expectation of the league's replacement-rank quarterback.

This reproduces the guide's own worked example: a 12-team league starting
1QB/3RB/5WR/2TE lands on WR66 = 7.9 PPG, the exact figure it cites.

`VORP = proj − baseline[pos]`

## The lineup solver

A player is also worth what he adds to your best legal starting lineup. Slots
are filled most-restrictive-first so a flex never steals a player a dedicated
slot needed, and the marginal value is the lineup total with him minus without.

```
adjValue = marginal + wBench · max(0, VORP − marginal)
```

This is what makes superflex work without special-casing it. With an empty
roster a QB fills either QB or SUPER_FLEX and prices enormous; once both are
filled the third QB adds nothing to the lineup and collapses to his bench
fraction. Same code covers TE premium, 3WR vs 2WR, and any other roster shape.

League size then tilts the onesie positions, because in a shallow league you
pick again quickly and the waiver wire is stacked:

```
teams ≤ 10 → QB/TE × 1.08
teams ≥ 14 → QB/TE × 0.92
```

## The draft game

```
edge = (1 − P(survives)) × (adjValue − E[best alternative at his position])
```

`P(survives)` is a normal CDF around consensus ADP using the real pick standard
deviation. `E[best alternative]` walks candidates best-first, weighting each by
the chance he survives times the chance everyone above him did not.

Read the whole thing as: *what does this pick buy me that waiting wouldn't.*

Tier scarcity then adjusts it. With `gap` picks until your next turn and `n`
players left in a tier:

- `n ≤ gap` → the tier will not survive → `× 1.15`
- `n > 2 × gap` → someone comes back to you → `× 0.90`

## Known soft spots

- Curve coefficients come from a printed chart, not the underlying data. ±0.3 PPG.
- The guide's prose says RB36 is "more than two points better" than WR66, but
  its own table gives 9.4 vs 7.9 — a 1.5-point gap. The table is used here.
- Flex splits are judgment calls, not fitted values.
- Market Score is dynamic and moves with ADP through the summer. Re-paste it if
  you refresh close to draft day.
- FFC's `2qb` ADP is the closest free proxy for superflex. It prices QBs
  correctly but is not identical to a true superflex board.

---

## The guide's trend checks

Every "Metric to Watch" in the guide that has a free data source is now a rule.
Each returns a verdict and a small multiplier; the product is capped to
0.85–1.15 so a player who trips several rules is dinged rather than erased. In
practice the spread across a real board runs about 0.89 to 1.11 with a median of
exactly 1.00, and nothing hits the caps.

Two data layers feed them.

**Prior-season production** comes from `scripts/build_history.py` — nflverse
weekly stats joined to Sleeper IDs through the DynastyProcess crosswalk,
regular season weeks 1–17, fantasy points recomputed from components. `n1` is
the most recent season with 8+ games, which is the guide's qualifying bar.
Career year comes from draft year in the same crosswalk.

**Team and teammate scores** need no new data at all. The guide builds Team
Environment Score and Pass-Catcher Score from teammate ADP, and the ADP
expectation curves already convert any ADP into expected points. So each team's
score is just the summed expected PPG of its players drafted inside the top 180.
Teammate-framed scores exclude the player himself, and their terciles are
computed on that same exclusive basis — cutting them against team totals would
make every back look like he had a clear backfield.

| Position | Check | Rule |
|---|---|---|
| QB | Rushing | Top 8: 4+ rush FP/g ×1.06, under 2 ×0.93 |
| QB | TD rate | Top 24, 300+ att: 6%+ ×0.94, under 4% ×1.05 |
| QB | Pts/dropback | QB18–30: 0.45+ ×1.08, under 0.35 ×0.92 |
| QB | Career year | Year 2 inside top 24 ×1.05 |
| RB | Receiving role | Top 18: 8+ rec FP/g ×1.06, under 4 ×0.94 |
| RB | Backfield | RB19–42: middle tercile of teammate RB points ×1.05, top ×0.95 |
| RB | Explosiveness | RB43+, 50+ carries: 12%+ of runs going 10+ ×1.07 |
| RB | Team environment | Top 18: top tercile ×1.04, bottom ×0.94 |
| WR | N-1 scoring | Top 18: 20+ PPR/g ×1.06, under 15 ×0.95 |
| WR | Target share | WR19–42: 25%+ ×1.05, under 18% ×0.95 |
| WR | Target share | WR43+: 18%+ ×1.06, under 13% ×0.93 |
| WR | Depth of target | WR43+: 12+ aDOT ×1.04 |
| WR | Target competition | WR19+: crowded ×0.94, open ×1.05 |
| TE | N-1 scoring | Top 6: under 12 PPR/g ×0.94 |
| TE | TD dependence | Top 12: 0.60+ TD/g ×0.94, under 0.40 ×1.05 |
| TE | Target competition | TE13+: crowded ×0.95 |

Spot checks reproduce the guide's own named examples without being told them:
Jefferson and McMillan fall under the 15 PPG receiver bar, Javonte Williams
fails the receiving-role check, McBride trips TD dependence at 0.69 while
Loveland and Warren clear it at roughly 0.31, Stafford shows a 7.5% touchdown
rate, Shough and Ward come back as Year 2 quarterbacks, Alec Pierce fails both
target share and target competition, and Keaton Mitchell tops the late-round
explosiveness metric.

## What is deliberately missing

Four of the guide's metrics have no free data source and are absent rather than
approximated:

- **Yards per route run** and **first downs per route run** — routes run is
  charting data, not in nflverse. Receiving yards per target is a different
  statistic and substituting it would quietly change what the rule means.
- **Targets per route run** and **slot rate** — same problem, plus alignment.
- **ZAP Score** — a proprietary college prospect model from a separate guide.

The per-player nudge and tag controls exist for exactly these. If you know a
receiver cleared 2.0 YPRR, nudge him and the reason travels with the player.
