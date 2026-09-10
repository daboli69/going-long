# Betting model and operations

The single-file browser application automatically joins bookmaker quotes to
historical NFL player profiles. NFL and NCAA game projections use trailing
team scores and walk-forward error distributions. These are transparent
baselines, not validated profitable strategies or calibrated future probabilities.

## Data contract

`scripts/build_pipeline.py` writes `data/data.json` (configuration) and augments
`data/history.json` with `betting.schema_version = 1`. Existing `history.players`
remains intact for fantasy features. The fantasy history builder also preserves
the betting namespace. An upstream failure leaves the previous file in place;
only a specifically unpublished current NFL season can be skipped. Atomic
replacement is per file. The workflow publishes the resulting files together
in one commit. Source status and timestamps identify the data used.

`history.betting` contains:

- `profiles[gsis_id]`: name, current roster team, last game, trailing raw games,
  and per-market mean, sample standard deviation, sample size and distribution.
- `aliases[event_id|normalized_name]`: audited Odds API description matches,
  including exact/fuzzy/ambiguous/unmatched status and match score.
- `games.nfl` and `games.ncaa`: upcoming fixtures, model means, uncertainty and
  sample counts. NCAA props are outside the existing app's scope.
- `validation`: walk-forward game-margin and total RMSE and sample counts.

Default window is 12 regular-season appearances, minimum 5. This includes week
18, unlike the fantasy scoring analysis. `load_snap_counts` supplies zero-stat
offensive appearances missing from the weekly statistical table; absent/DNP
games are not invented as zeros. Missing numerical fields are omitted from
that market's sample. Postseason games are excluded. Current rosters allow
matching players who changed teams; historical game logs remain their actual
past production. Injury, starting-role and workload changes are not modeled.

Statistical sources are exclusively [nflreadpy](https://nflreadpy.nflverse.com/api/load_functions/)
and [sportsdataverse](https://github.com/sportsdataverse/sportsdataverse-py).
Existing Sleeper/FantasyCalc integrations still support fantasy metadata and
market values; they do not supply the new statistical projections.

## Distributions and settlement

Yardage uses a moment-matched lognormal distribution on **positive** observations:

`sigma_log² = log(1 + sd_positive² / mean_positive²)`

`mu_log = log(mean_positive) - sigma_log² / 2`

The empirical nonpositive outcomes retain their observed probability mass, so
negative rushing yards and zero-yard games are not clipped or dropped. Positive
mass is weighted by the fraction of positive games. A zero-variance positive
component is a point mass. NFL statistics are integer valued: positive yardage
is rounded using half-yard bin boundaries to compute integer-line pushes.
For an integer line L, P(under) = F(L - 0.5), P(over) = 1 - F(L + 0.5).

Receptions and touchdowns use Poisson(lambda = sample mean). Anytime TD uses
P(X >= 1) = 1 - exp(-lambda), including rushing, receiving, special-teams,
defensive and fumble-recovery scores, excluding passing TD credit. Other TD
markets use their respective count. At any line L:

`P(under) = PoissonCDF(ceil(L)-1); P(over) = 1-PoissonCDF(floor(L))`

`P(push) = 1-P(under)-P(over)`

Count variance/mean is exported as a dispersion diagnostic. Poisson assumes
equal mean and variance; the baseline does not correct for overdispersion.
The CDF recurrence is stable through lambda 1000 and supports lines up to
10000; invalid/out-of-range inputs remain unpriced. The normal CDF used by
the lognormal and game models has absolute numerical error below 7.5e-8.
These are numerical evaluations under fitted models, not exact knowledge of
future win probability.

For decimal odds d, win probability p and push probability r:

`EV per unit stake = p*(d-1) - (1-p-r)`

`full Kelly = EV / ((d-1)*(1-r))`

The UI displays EV as a percentage, win probability excluding pushes, and
quarter Kelly, floored at zero and capped at 2% of bankroll **per bet**.
Stakes are not additive portfolio recommendations: alternate quotes and
correlated bets must not each receive the displayed allocation automatically.
The default freshness gate rejects started games, quotes older than 24 hours,
and player profiles older than 400 days (allowing the NFL offseason).
Changing a projection does not refresh its bookmaker quote. Manual imports
are explicitly labeled; the user supplies their price provenance.

## Matching and quote integrity

Normalize Unicode, punctuation, whitespace and suffixes. Pipeline fuzzy
matching uses `thefuzz.ratio`, score >=92 and a >=7-point gap to the next
candidate, constrained to event teams when both are known. Collisions remain
unmatched. Browser matching uses the pipeline's audited aliases or unique exact
normalized names; it never performs an unconstrained guess for a rookie.

Each quote is keyed by event, bookmaker, market, player and line. Over/under
sides at different lines or different books are never combined; Under-only
quotes are retained. The board prices the higher-EV available side. NCAA line
ingestion selects one preferred bookmaker per game and retains only matching
opposite-line prices. It does not silently combine prices across books.

## Game models

Expected home points average the home team's trailing points scored and the
away team's trailing points conceded; away points are the analogous average.
Margin = home points - away points, total = their sum. Uncertainty is the sample
SD of the preceding 1000 walk-forward residuals, with at least 30 residuals
required for pricing. Teams need at least 5 previous games. Fixtures with the
same kickoff are predicted together before any of their outcomes are added.
Margin/total probabilities use a rounded normal approximation; integer lines
have push mass. Moneylines assume two-way settlement with ties refunded.
Books with different tie/void rules require separate treatment.

This score baseline is not opponent-strength adjusted and has no explicit
home-field, injury or neutral-site adjustment. It replaces dependence on the
older fixed rating conversion for betting prices. Historical in-sample team
ratings do not enter these predictions. NFL margin and total RMSE, as built on
2026-09-10, were 13.21 and 13.36 points (462 walk-forward games); NCAA results
were 18.11 and 15.97 (1205). No prop backtest, ROI, closing-line value or
probability calibration claim is made.

The [nflverse schedule convention](https://nflreadr.nflverse.com/articles/dictionary_schedules.html)
has positive `spread_line` for a favored home team; the UI negates it to show
a home betting spread. Kickoff is converted from Eastern time to UTC, including
daylight saving time. Unknown kickoff times are not invented as midnight.

## Running and validation

Install `scripts/requirements.txt` in Python 3.12. Run the fantasy history,
NFL odds, NCAA odds, then projection builders in that order. The daily GitHub
workflow does this automatically and stages `data.json` as well as history.
Set `PARLAY_API_KEY` as a GitHub Actions and hosting secret. It never enters
frontend bundles. The [Parlay API](https://parlay-api.com/docs#sport-keys)
uses `X-API-Key`, `/v1/sports/americanfootball_nfl/props`, and NFL/NCAA `/odds`.
Flat prop rows are normalized by the shared market aliases in
`config/parlay-markets.json`. Book, event, line and both prices remain distinct.
Anytime TD keys can contain 2+ / 3+ alternatives: their thresholds are preserved.
DFS comparison prices are synthetic and cannot produce single-bet EV or Kelly.
Unknown kickoff times keep their quotes visible but suppress recommendations.

The hosted `/api/odds?sport=nfl|ncaa` route refreshes on demand, coalesces
concurrent requests and caches for two minutes. It accepts no arbitrary upstream
URL. Failed refreshes preserve saved data and its timestamps. Parlay caps prop
responses at 10,000 rows; the UI discloses potentially partial coverage.
GitHub Pages supports saved snapshots; live refresh needs the server runtime.
NFL weeks are incorporated only once corresponding snap counts are available,
so zero-stat appearances are not omitted during staggered source publication.

Run `npm ci`, `npm test`, and
`python -m unittest discover -s tests -p 'test_*.py' -v` for regressions.
`npm run build` validates HTML identifiers/JSON and stages only public assets
in `dist/client`, with the secret-free Worker bundle in `dist/server`. JSON fetch/parse runs in a Web Worker, odds transformation and
sorting yield to animation frames, and the props DOM is bounded to 50 quotes
per page. Game rendering is limited to the nearest 100 fixtures. Projection
inputs debounce 250ms and update metrics without replacing the focused input.
An unavailable worker reports a loading error and leaves manual import usable.
Browser visual testing and an authenticated Parlay API run are separate from
these automated checks.
