# NFL data sources

The pybaseball / MLB-StatsAPI equivalent for football is **nflverse**. It isn't
one API — it's a set of nightly-built datasets published as GitHub release
assets, which suits this repo exactly: the Action pulls flat files, commits a
slim version, and the browser never talks to a rate-limited host.

## nflverse — the core

**Python:** `nflreadpy` (returns Polars; `.to_pandas()` if you want pandas).

```python
import nflreadpy as nfl
pbp    = nfl.load_pbp([2024, 2025])      # play-by-play, ~370 columns
stats  = nfl.load_player_stats([2025])   # week-level player stats
teams  = nfl.load_team_stats(seasons=True)
sched  = nfl.load_schedules()
```

There's also `nfl_data_py`, the older Python port, and `nflreadr` if you ever
want R. All three read the same release assets.

**No key, no signup, no rate limit.** Play-by-play goes back to 1999 and updates
nightly in season. Most of it is CC-BY 4.0; the FTN charting data is CC-BY-SA
4.0, so check the per-dataset license if you redistribute.

You can also skip the library entirely and pull the CSV/parquet straight from
`github.com/nflverse/nflverse-data/releases` — which matters here, because
GitHub is already an allowed domain for the Actions runner.

Useful releases: `pbp`, `player_stats`, `stats_player`, `stats_team`,
`schedules`, `rosters`, `depth_charts`, `snap_counts`, `pfr_advstats`,
`injuries`, `contracts`, `draft_picks`, `ff_opportunity`.

`ff_opportunity` is the one to note for the fantasy side — precomputed expected
fantasy points, which is the closest free thing to a projection model and would
plug straight into the lineup optimizer.

## Odds, for the betting half

Free tiers move around, so verify before committing. As of the last check:

| Provider | Free tier | Notes |
|---|---|---|
| The Odds API | 500 credits/month | Most documented. Credits burn fast — a multi-market, multi-region call costs several. ~40 books, no sharp books. Historical odds back to mid-2020. |
| SharpAPI | 12 req/min, 2 books | Far more volume, fewer books, ~60s delay on free. |
| SportsGameOdds | Free tier, paid from $99 | 80+ books including Pinnacle. |
| OddsPapi | Free tier | 350+ books including sharps. Newer, less battle-tested. |

For closing-line value work you want *historical* odds, which is where The Odds
API's archive matters more than its request ceiling. For live line shopping you
want request volume, which is the opposite. Plan on two sources.

## Scores and schedules

`nflreadpy.load_schedules()` covers results, spreads and totals per game going
back decades — enough for most backtesting without touching an odds API at all.
ESPN's undocumented endpoints (`site.api.espn.com/apis/site/v2/sports/football/nfl/...`)
are free and fast for live scores, but unsupported and liable to change.

## What this means for the betting build

The Action structure already in this repo carries over: a Python script pulls
flat files, trims to what the front end needs, commits JSON. Play-by-play is
large, so aggregate server-side (EPA per play, success rate, pace, pass rate
over expectation) and ship only the team-week table.

The honest constraint is the one you already named — early season is thin. EPA
stabilizes somewhere around weeks 4-6, so anything built on team efficiency is
noise until then. Preseason priors have to come from prior-year data regressed
to the mean plus roster turnover, and that's a modeling problem rather than a
data problem.
