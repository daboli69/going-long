# King of the Court research module

Implementation follows the [pre-implementation specification](KING_OF_THE_COURT_SPEC.md). The [registered protocol](../config/king_court_protocol_v1.json) and [October 27 screenshot rule record](../config/king_court_offer_2026-10-27.json) are separate from NBA winner and football models. No interface, scheduled job, wager, alert or deployment is added.

## What works

The local Python module fetches and preserves free raw SportsDataverse/hoopR schedule and box archives, validates their accounting, and produces a correlated complete-slate PRA simulation. It reports minutes, points/rebounds/assists, PRA intervals, sole/tied/inclusive leader probabilities, finite-simulation errors, source/role limitations, two-level recency contributions, effective sample sizes, rookie/second-year priors and descriptive recent opportunity trends. Separate current-season-only and equal-history simulations use the same field and are retained as comparators. No popularity percentage is inferred from a player's name.

NBA live JSON reconciliation supports exact game/player/team crosswalks, points/rebounds/assists agreement, substitutions, supplied period-start fives and reconstructed minutes. Without starting fives it explicitly withholds lineup verification. The free `nba_api` live endpoint can export this JSON outside the restricted environment; pbpstats is a possible upstream parser/cross-check, not a separately verified independent dataset or an automatically configured live integration. ESPN PBP parquet may be preserved using `fetch --include-pbp`; its presence alone does not mark events reconciled. No undocumented event-role inference is used.

The aggregate simulator shares game possessions, samples historical overtime, constrains each team's minutes to five times game length, and allocates integer shot attempts and free throws. Rebounds compete for simulated missed-shot pools; assists can only follow made field goals and cannot go to the shooter. Box-derived possessions and missed-FT opportunity pools are labeled proxies. This is not a full possession/stint simulator. Verified roster membership and expected-minutes scenarios affect allocation; there is no fitted five-player lineup interaction or invented injury multiplier.

There is **no validated model, live recommendation or empirical ownership model yet**. All outputs retain `blocked_research_only`. Current data lacks archived pregame availability/complete promo fields, event/stint reconciliation and full account-specific rules. Selection refuses reconstructed postgame participant lists, so no decay setting is described as learned without the required earlier-fold evidence.

## Quick start

From the repository root, with Python 3.12:

```sh
python -m pip install -r scripts/king_court/requirements.txt
python -m scripts.king_court demo --draws 20000 --output .cache/king-court/demo-001.json
python -m unittest tests.test_king_court -v
```

The demo is fully synthetic: anonymous players, fabricated games and an explicitly hypothetical crowd scenario. It demonstrates accounting and output structure, not NBA accuracy. Its JSON and compressed integer simulation samples are immutable local receipts. Give each later run a new output path.

Fetch current ending-year 2027 and the three preceding seasons:

```sh
python -m scripts.king_court fetch --seasons 2024 2025 2026 2027 --cache .cache/king-court/raw --output .cache/king-court/sources-001.json
python -m scripts.king_court ingest --manifest .cache/king-court/sources-001.json --output .cache/king-court/history-001.json
python -m scripts.king_court audit --history .cache/king-court/history-001.json --output .cache/king-court/audit-001.json
```

Every fetch makes a real request, retains content-addressed raw files, and records retrieval times and source hashes. Failures raise; missing seasons are not silently replaced. Unknown upstream publication times remain unknown. Historical archives retrieved today cannot establish what an earlier predictor knew. Explicit DNP rows are known zero-minute observations; unknown minutes are not converted into zeros. Player/team stat disagreements, future finals, invalid shooting arithmetic and incomplete minutes fail reconciliation.

Optional `ingest --debut-metadata debut.json` accepts `{"source":"...","known_at":"...Z","debut_seasons":{"espn:PLAYER_ID":2026}}`. These must be verified NBA debut ending-years, not the first season present in the download. No debut values were invented for the retained real-data audit. Missing metadata forces a disclosed broader prior for other historical cohort players. Every forecast-field player must have verified debut metadata in the pregame manifest.

## Pregame manifest contract

`simulate` and `freeze` require a complete pregame JSON slate manifest. Essential fields:

- `date`, ending-year `season`, UTC `origin`, `known_at`, `source`, `evidence_kind`, `regular_season`, `field_complete`, `rosters_complete`, `full_terms_verified`.
- `eligible_game_ids`, `eligible_player_ids`, and `games`: exact game ID, teams, tipoff and `status: "scheduled"`.
- Every field player: exact `player_id`, `name`, `position`, `team`, `game_id`, verified `debut_season`, `availability` (`available` or `out`), `selectable`, `known_at` and `source`.
- Optional `expected_minutes`: `mean`, `sd`, `known_at`, `source`. This is an explicit conditional rotation scenario, not a learned injury effect. An uncertain player requires separate complete scenarios; no undocumented probabilities mix them.
- Prospective `field_source_receipt`: preserved source JSON path, SHA256, `known_at`, and `source`. The preserved JSON must independently list the same `date`, `eligible_game_ids`, and `eligible_player_ids`. Its bytes and field identities are checked. The full slate must also match the independently retained schedule. A shortlist cannot pass as a complete field.
- If prize scenarios are requested: an explicit `offer` with matching `date`, source, and `pool_bonus_bet_face_value`; optional exact `offer_id` for measured counts. No future Tuesday automatically inherits October 27's pool. Rules remain conditional unless verified.

Times must precede the decision origin. Prospective roster/slate evidence must be at most 36 hours old; the whole slate freezes before its earliest tipoff, using Tuesday's America/New_York date. Earlier games are never dropped to make a later forecast possible. Every eligible contender remains in the field, including players unavailable for selection if the leader definition includes them. OUT players remain explicitly represented with zero production; unknown availability cannot silently become OUT.

## Recency selection and forecasting

Each target uses only ending-years S−3 through S. Season factors .35/.65 and within-season half-lives 30/90 days form a preregistered eight-member grid with prior strengths 5/15 games. They are candidates, not fitted conclusions. Newer seasons have larger season multipliers; recent games within each season have larger weights. Within-season age uses that season's latest eligible observation; current-season age is measured to the origin. Prior seasons can stabilize a sparse current sample. Their actual total weight shares are displayed; the current season need not contain more total evidence than 82 older games. Minutes/role use only the current team/current season plus a prior; player production rates can transfer across teams.

Rookie and second-year priors match verified NBA experience, position, and five-appearance stage bins when enough historical records exist. Insufficient experience-cohort support falls back to a labeled position/league prior. No missing season is a zero, and no player is called a rookie merely because data is absent. A weak Beta(1,1) shooting prior prevents degenerate tiny-sample efficiencies; it is disclosed separately from fitted recency settings. Player rates, role variation and team context are approximations subject to validation.

First use `register` with a plan containing at least eight `development_dates` and disjoint later `holdout_dates`, all future Tuesdays. It records actual process time and model/protocol hashes; it refuses retrospective registration. `select` then takes that sealed registration, an array of complete archived **prospective** slate manifests, and development outcome receipts. Each outcome receipt has an official `source`, after-game `known_at`, and `values` mapping every field player to integer PRA. It selects on mean complete-slate PRA MAE with deterministic tie breaks. Its effective training cutoff includes when the latest development outcome became known, not just when its game began. Code/protocol hashes must match at selection and when applying it to later predictions.

```sh
python -m scripts.king_court register --plan experiment-plan.json --output experiment.json
python -m scripts.king_court select --history history.json --experiment experiment.json --slates development-slates.json --outcomes development-outcomes.json --output selection-001.json
python -m scripts.king_court simulate --history history.json --slate pregame-slate.json --selection selection-001.json --output simulation-001.json
python -m scripts.king_court freeze --history history.json --slate pregame-slate.json --selection selection-001.json --output freeze-001.json
```

`freeze` uses actual process time and refuses after the earliest game starts. `simulate` is local research, not an official prospective capture. An explicit `--research-parameters parameters.json` can replace `--selection` for experiments; it must contain a grid member and is flagged unselected. There is no silent default weight setting for real forecasts. `--mode retrospective` explicitly relaxes historical source-publication assumptions for diagnostics; it cannot create a prospective freeze or parameter-selection cohort.

## Popularity and prize sharing

Without `--ownership scenarios.json`, observed ownership is null and no prize-share value is fabricated. Supply an array of:

1. `kind: "hypothetical"`, `name`, a complete `ownership` vector summing to one, and `other_entrants`. It samples multinomial selections for other qualifying customers in each trial. The input scenario is not a measurement.
2. `kind: "measured_counts"`, `name`, complete other-customer `counts`, `source_scope: "promotion_qualifying_selections"`, source, `known_at`, exact `offer_date` and `offer_id`, plus `counts_are_other_customers: true`. Dates/offer/decision time are checked. Generic DFS ownership or sportsbook percentages do not satisfy the provenance contract.

For a customer considering player i, each draw pays `pool * I(i is a leader) / (1 + other qualifying customers on any tied leader)`. A different hypothetical choice is evaluated separately; the module does not assume a customer may enter multiple players. Inclusive leader probabilities can sum above 100%; fractional tie credits sum to 100% but do not determine customer prize shares. Unselectable players receive no hypothetical entry value.

Scenario values are **conditional face-value bonus bets**, not cash returns or verified monetary EV. The original wager's result is separate. The complete October 27 terms do not establish its win requirement in the supplied material; that ambiguity is retained. A different offer explicitly requiring the original wager to win is rejected for prize calculations because this module has no joint prop-qualification model.

## Event verification, settlement and evaluation

```sh
python -m scripts.king_court reconcile-pbp --history history.json --pbp nba-live-game.json --crosswalk game-crosswalk.json --output history-with-events.json
python -m scripts.king_court settle --freeze freeze-001.json --outcomes official-outcomes.json --output settlement-001.json
python -m scripts.king_court evaluate --settlements settlement-001.json settlement-002.json --output diagnostic-001.json
```

Crosswalk JSON requires canonical `game_id`, exact `nba_game_id`, `persons` mapping NBA person IDs to canonical player IDs, and `teams` mapping NBA team IDs to team codes. Optional `period_lineups` lists both teams' canonical starting fives separately for each period. It is required for stint verification. Never join NBA and ESPN numeric IDs directly. Reconciliation records raw-file/crosswalk hashes and time, preserves the original history receipt, and produces a new receipt. Possession providers based on the same feed remain one evidence lineage.

Outcome JSON includes official source and `known_at`, exact `completed_game_ids`, optional `unresolved_game_ids`/`voided_game_ids`, and `values` for **every** frozen field player, including confirmed DNP zeros. A missing or unresolved game creates an immutable pending settlement; it does not manufacture a leader or eliminate that game's candidates. The compressed frozen samples are hash-checked before statistical grading. Settlement never claims the sportsbook awarded a particular amount; complete promo settlement rules and actual winning-entry counts remain separate evidence.

Statistical reports include PRA MAE, CRPS, 80% interval coverage, sole/inclusive leader Brier, inclusive event log loss, reliability bins, experience cohorts, and paired whole-slate bootstrap intervals against the season-average/minutes-rate means and current-only/equal-history simulations. Baseline comparisons retain identical player/slate cohorts. A current-only comparator can be explicitly unavailable at season opening. Fewer than 20 settled slates are marked insufficient; 20 is an initial minimum, not proof of adequate rare-event calibration. Cohorts with few rookies remain uncertain. Popularity accuracy requires real observed token counts.

Passing a selection receipt to `evaluate` permits the registered-holdout label only for exact later dates, matching model/selection hashes and genuine prospective freezes. Synthetic demos, reconstructed participants and duplicate slate records cannot become a holdout. There is no automatic promotion.

## Evidence retained in this workspace

The [source audit](../research/king-court/source-audit.json) records the current three-prior-plus-current-season intake and its gaps. The [research report](../research/king-court/README.md) distinguishes engineering verification from predictive validation. Local raw archives/full history, simulation samples and receipts are under ignored `.cache/king-court/`; no private inputs or licensed sources are used.
