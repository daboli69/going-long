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

## Public PBP features and proxy sensitivity

`build_pipeline.py` embeds `betting.features` in `history.json`. NFL PBP and
participation come from nflreadpy. College game features use the cfbfastR
release through `sportsdataverse.cfb.load_cfb_pbp_r`; there are no NCAA player
projections. The build fetches three seasons and uses each offense's last
12 games. Dates on or after the build's UTC date are excluded.

Every feature uses pre-snap offensive WP inclusively between .20 and .80.
No-play, kneel, spike and overtime snaps are excluded. First-15 numbering is
assigned before the WP filter. Pace measures adjacent neutral offensive snaps
within a drive and quarter, retaining clock gaps of 1–60 seconds. It is game
clock pace, not wall-clock time. Q1/H1 exports contain neutral opportunities,
production and pace; their totals are not full-period projections.

Participation proxies use `offense_players` on charted dropbacks (including
sacks/scrambles). Both semicolon strings and arrays are supported. Pass-snap
participation and targets per pass snap use the SAME charted exposure set.
Missing charting is excluded, not treated as absence. Coverage percentage and
last charting date are exported. These proxies are explicitly not routes run
or true TPRR. A heuristic expansion flag requires 50 pass snaps, target rate
at least 25%, and participation below 70%; it is not a validated prediction.

Pressure rates use non-null boolean `was_pressure`, with separate observed
numerators and denominators for offense and defense. For upcoming NFL matchups,
the adverse pressure-rate difference is halved, shrunk by n/(n+100), then
multiplied by the offense's observed pressured-versus-clean yardage difference.
Minimum samples are 100 charted dropbacks on both sides and 30 in each offensive
pressure bucket. QB passing mean/SD can decrease at most 15%; QB rushing can
increase at most 25%. Lognormal parameters are rescaled consistently. These
are bounded observational sensitivities, not causal estimates or calibrated
betting improvements. Historical baselines remain intact. Defense samples are
restricted to the retained opposing-offense windows; sample counts are exposed.

Receiver man/zone and single/two-high yards-per-target splits are exported;
20 targets are required for an observed split label. Mixed or unknown shells
are not assigned to single/two-high. Air yards/aDOT, red-zone/goal-line carry
and target shares, end-zone targets (air yards reach the goal line), and
opening-play usage are included. Slot alignment and cross-team OC identity
remain inactive. PROE and neutral pace remain team-level features.

First-TD and Q1/H1 prop aliases are distinct from full-game/anytime markets.
The server and nightly adapters also fetch Parlay's dedicated period endpoint;
its failure does not erase full-game odds. Period rows retain event, book,
period, side, team and alternate-line identity. In-play rows are displayed
separately and never receive a pregame model's EV. First-TD and period markets use the baseline engine described below. They are
not empirically calibrated; in-play quotes and pick’em payout comparisons remain
unpriced for straight-bet EV.

Sources: [nflverse participation dictionary](https://nflreadr.nflverse.com/articles/dictionary_participation.html),
[cfbfastR data loader](https://cfbfastr.sportsdataverse.org/reference/load_cfb_pbp.html),
[Parlay API documentation](https://parlay-api.com/docs).


## First TD and early-period baseline engine

The First TD engine integrates two competing-risk stages: opening scripted
plays and the remainder of the game. For stage k, total hazard L is the sum of
all player, other-offense and DST hazards. Each outcome receives
S × (1 − exp(−L)) × hazard_i/L; surviving no-TD mass becomes S × exp(−L).
The final survival probability is the no-touchdown outcome. This produces one
multinomial pool per fixture with sum exactly one, independent of bookmaker
lists. The implementation does not equate game-win probability with scoring
first: projected team scoring supplies the relative team strength instead.

Explicit, uncalibrated priors: offensive TD drives account for 75% of projected
points at seven points per drive; DST has 6% of total TD hazard; other offensive
players retain 5% of offensive hazard. Rush conversion weights are .40 inside
five, .15 from six through ten, and .04 from eleven through twenty yards.
End-zone target weight is .30. These weighted opportunities per game combine
with half of the historical expected-TD prior. Opening-stage player allocation
blends 65% scoring opportunity share with 35% scripted carry/target share,
weighted by the team's opening run/pass mix. The opening-stage hazard fraction
is shrunk toward .25 and bounded to .15–.40. Player participation is assumed;
these estimates are not injury/starting-lineup forecasts or measured accuracy.
All public opportunity features retain the neutral WP filter.

Fair American odds come directly from each unconditional probability. EV is
P × decimal payout − 1 for First TD, with no push assumed. Book-specific vig
comparison divides each listed implied probability by that book's listed sum.
It is labelled conditional on the listed pool, with modeled coverage displayed;
missing DST/no-TD/unlisted-player prices never masquerade as a complete market.
EV does not use this partial-pool renormalization.

1H player means use .49 of full-game means; yardage SD uses sqrt(.50) of full
SD. Q1 uses .22 and sqrt(.25). The early/full clock pace ratio is shrunk by
n/(n+100), capped within .90–1.10, and applied to exposure. Yardage distributions
are moment-matched lognormals; counts use thinned Poisson means. These are
baseline assumptions, not empirically estimated period distributions.
1H game total/margin use .52/.50; Q1 uses .22/.25. Total variance scales with
scoring exposure, margin variance with the period fraction. Team-total variance
uses zero covariance between margin and total. Two-way moneyline ties push;
three-way feeds treat a draw as its own outcome. In-play and unknown-start
quotes never use these pregame models.

The live audit observed `player_1h_pass_yards`, `player_1h_rush_yards`,
`player_1h_rec_yards` and Q1 equivalents. `/v1/markets` also lists
`player_1st_td`. Team-only and first-drive touchdown markets are excluded from
the game-first-TD aliases. A separate NFL derivative request prevents the broad
10,000-row cap from suppressing these markets. Current half-player availability
may be pick’em only: those lines retain projections but no fabricated payout,
EV or Kelly. NCAA remains game markets only.
