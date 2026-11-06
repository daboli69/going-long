# Is the closing game line efficient: movement, cross-market and dispersion tests

Written 2026-11-06, committed before any test was computed. Football only. No staking and no bet sizing anywhere in this document.

## Question

Twenty years of opening and closing sportsbook game lines are in the lab. Does anything in the way a line moved, or in how the moneyline, spread and total agree, predict the result beyond the closing line? Props are not covered here. They wait for the weekly saves.

## 1. Structural reason

The closing line absorbs news from the sharpest bettors, so it is the hardest number to beat. That does not make every feature of its history efficient. Three places where a rational market could still leave something:
- After a big move, some traders may still be reacting at the close (a move that keeps going) or may have overreacted (a move that reverses).
- The moneyline, spread and total are priced as separate markets. They should agree after allowing for key numbers like 3 and 7, but a book can lean on one without the other.
- A line that wandered more during the week signals more disagreement or more news. The mean may be fair while the spread of outcomes is wider, which matters for alternative lines and props, not for the standard line.

These are reasons to look, not evidence. A null on all three is the expected outcome.

## 2. Data: what exists and what does not

Exists: `data/raw/market/aussportsbetting_nfl.xlsx`, 5,509 games from 2006-09-07 to 2026-10-11, with scores and, for each game, the open, minimum, maximum and close of the moneyline, spread, spread odds, total and over and under odds. Its notes say the source changes by period: earlier sources, Pinnacle (2014 to Feb 2018), bet365 (Sep 2018 to Feb 2025), betr (from Sep 2025). Sources differ in sharpness and in vig. This file is downloaded manually, and its terms say it may contain errors.

Missing, and left missing:
- The exact time of the "open" and the "close". Open is whenever the source first posted. This is a limit on every test below.
- Odds history between open and close, beyond the minimum and maximum.
- Anything for props.

## 3. Fixed in advance

Games: regular season only (playoff flag blank), with an open and a close for the spread and total, scores present. Neutral venue games are kept.

Definitions, from the home team's side: expected home margin m = minus the home line. Actual margin = home score minus away score. Error E = actual margin minus m at the close. Total error E_t = total points minus the closing total.

Stages: decide on 2006 to 2015, confirm on 2016 to 2025. The 2026 games (107) are reported as a descriptive sample and never used in a test.

Four tests, all fitted by least squares or logistic regression with variables standardized in the stage:
- T1, spread drift: E on the move in expected margin, m close minus m open. A positive slope means moves keep going after the close, a negative slope means they reverse.
- T2, total drift: E_t on the move in the total, close minus open.
- T3, cross-market: home win on the logit of the spread-implied win probability and on the difference d between the logit of the de-vigged closing moneyline probability and the logit of the spread-implied probability. The spread-implied probability is a probit of m with a scale fitted on the decide stage only. The coefficient on d is tested.
- T4, dispersion: absolute error |E| on the spread's range during the week (maximum minus minimum of the home line), controlling for the closing total.

Decision rule: a test counts only if the decide-stage coefficient has a sign and the confirm-stage coefficient has the same sign with a Holm-adjusted p below 0.05 across the four confirm tests. P-values come from a bootstrap by game (2000 draws), two-sided.

Power gate, before any coefficient is shown: on the confirm stage, the smallest detectable standardized coefficient is 2.8 times its bootstrap standard error. The size of interest is 0.06 for T1, T2 and T4, and 0.10 log-odds per standard deviation for T3. A test whose smallest detectable size is above its size of interest is reported as uninformative and its coefficient is not read. The gate uses only the dispersion of the data, not the sign or size of the coefficient.

## 4. Price check

Only for a test that passes. Take the rule "bet the side the fitted coefficient favors when its prediction is above the median size", fit on the decide stage, applied unchanged to the confirm stage, and report the win rate against the break-even rate implied by the actual closing spread odds. No stake and no sizing. The result is a win rate, not a return.

## 5. Source eras

The confirm stage mixes Pinnacle, bet365 and betr. Results are also reported by era, descriptive only. A result that appears in only one era is treated as a quirk of that book, not a market feature.

## 6. Report order and rule

Completed, Model Research, Concerns, Next, Needs Travis. If no test passes, the result is "no edge found". Nothing in the app changes on this result.
