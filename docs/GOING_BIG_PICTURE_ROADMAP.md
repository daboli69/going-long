# GOING: bigger product direction

Five new specialists, distinct from the weekly audit, researched market intelligence,
player props, customer experience, quantitative architecture and DFS. Public official
competitor material was checked October12,2026; no subscriptions, authenticated
scraping, paid APIs, bets, external alerts or private datasets were used. This is a
concept roadmap, not implemented functionality or a demonstrated forecasting gain.

## Strategic recommendation

Build GOING into a football research workspace connecting game conditions, team
opportunities, individual markets, DFS portfolios and the customer's original reasoning.
The flagship question becomes: **What football story supports this selection, what
could invalidate it, and what changed since I researched it?**

There are three large product lines:

1. **Game Lab:** opponent-adjusted team forecasts, opportunity scenarios and eventually
   one coherent simulation shared by game lines, player props, parlays and DFS.
2. **My Football Playbook:** persistent weekly research, explanatory market history,
   a cross-ticket exposure map and postgame learning from frozen assumptions.
3. **Tournament Studio:** exact-contest portfolios, legitimate Classic late swap,
   Showdown pre-lock contingency planning and point-in-time replay.

These are major workflows and model changes. Changing headings or adding another
confidence score would not implement them.

## Competitor comparison

These are publicly advertised capabilities; we did not audit private implementations
or establish that competitors lack the proposed combinations. Any claim GOING is
better must be demonstrated through user tasks, transparency, accuracy and reliability.

| Public comparator | Advertised capabilities | GOING today | Differentiation to pursue |
|---|---|---|---|
| [Unabated](https://unabated.com/) and [OddsJam](https://oddsjam.com/betting-tools) | Reference lines, odds comparisons, derivatives and movement tools | Private sharp-reference/de-vig scanner exists; public movement view is incomplete | Explain football-evidence changes alongside exact price/line changes; expose disagreements and missing inputs |
| [Outlier](https://www.outlier.bet/) and its [injury research](https://help.outlier.bet/en/articles/7730196-advanced-injury-guidance-and-impact-notifications-april-25th) | Trends, matchup research, with/without-player injury filters | GOING already has role trends and bounded injury scenarios | Whole-team, budget-conserving scenario explorer with explicit assumptions and uncertainty, followed by prospective validation |
| [SaberSim Contest Sims](https://support.sabersim.com/en/articles/12079199-how-contest-sims-work), [RotoGrinders SimLabs](https://rotogrinders.com/simlabs/nfl) | Contest simulations, field/ownership considerations and portfolio controls | Lineup simulations, optional ownership/duplication and construction policies exist | Allocate a portfolio to actual contests; stress-test ownership assumptions; explain shared game-script exposure |
| [Action Network](https://www.actionnetwork.com/app), [Pikkit](https://pikkit.com/bet-tracker) | Tracking/synchronization, analytics, social or expert-following features | GOING already has drafts and public/private journals | Remember the pregame thesis and material changes; explain outcome mechanisms and concentration across betting and DFS |
| [nfelo](https://www.nfeloapp.com/nfl-power-ratings/), [CFBD methodology](https://apinext.collegefootballdata.com/methodology-overview) | Opponent-aware ratings/model methods | NFL descriptive PF/PA leans and NCAA aggregate ratings | Visible pass/rush offense/defense states with uncertainty, strict weekly receipts and separate NCAA schedule-strength treatment |

Automatic sportsbook synchronization is a genuine integration gap, but copying it
first would introduce authentication, privacy and provider dependencies. Import/local
research can deliver the core workflows without assuming new paid services.

## Flagship additions

### 1. Game Lab: one game story across every market

Open SEA–DEN and compare plausible game scripts: competitive game, favorite controls
possession, or underdog chases through the air. Show how each changes scores, passing
attempts, carries, targets, TD opportunities, Captain candidates and compatible bets.
Explain conflicts between a receiver Over, QB Under and a low-total thesis.

GOING already has individual distributions, correlation disclosures, copula DFS
simulation and finite TD-budget research. The major missing capability is a validated
possession/opportunity engine tying these together, not another Monte Carlo button.

Architecture: possessions → play choice → team opportunities → active-player allocation
→ efficiency/scoring → betting and fantasy outcomes. Account for sacks, throwaways,
unmodeled players, reserves and shared scoring events. Keep passing/receiving accounting
coherent; never sum binary anytime-TD probabilities as if only one player can score.

Start with transparent coarse scenarios. A first scenario interface could take2–3
weeks using existing inputs; a research game engine takes4–6 weeks; a broadly validated
joint engine8–12+ weeks. These are rough engineering estimates, not commitments.

Gate: frozen chronological tests against each existing marginal and simple baseline,
CRPS/Brier/log loss, interval and joint-tail coverage, opportunity conservation,
held-out correlations and prospective confirmation. Full SGP probabilities require
that joint validation. A visual scenario alone does not justify higher confidence.

### 2. Injury Opportunity Workbench

Select a team's starter as active, limited or out and see the plausible redistribution
of carries, targets and goal-line work across the entire team, with multiple potential
beneficiaries and unassigned opportunity. See which rushing/receiving/TD markets change
and what evidence supports each shift.

Existing bounded injury boosts already exist (`shared/football-injuries.js`); this is
a customer-controlled counterfactual workspace plus a separately validated allocation
model. [Outlier's injury tools](https://help.outlier.bet/en/articles/7730196-advanced-injury-guidance-and-impact-notifications-april-25th)
establish that an injury filter alone is not a unique product.

Improve the decision workflow by conserving team budgets, showing uncertainty,
retaining missing assignments and distinguishing observed historical splits from
inferred redistribution. Hypothetical “active” status never clears an actually OUT
player for actionable recommendations.

Prototype2–3 weeks; validated challenger4–8 weeks contingent on dated injury episodes.
Historical seasons can train fixed relationships; current-season data supplies the
actual forecast. Gate: next-game volume MAE and prop proper scores versus current
bounded scenarios, chronological availability cohorts and same-sample baselines.

### 3. Opportunity Shift Radar

Answer “Has this player's job changed enough that his average is misleading?” Detect
changes in shares, relevant downs, goal-line opportunities and team volume; show
counterevidence, persistence uncertainty and whether the available market moved.
The user can follow a thesis until it is confirmed, rejected or expires.

GOING already exports role trends, goal-line and expected-opportunity evidence. The
addition is a tested change-point/persistence model and immutable thesis lifecycle.
Expected-minus-actual is not automatically a bounce-back signal. Routes/alignment
remain missing when coverage is unavailable; the [nflverse participation dictionary](https://nflreadr.nflverse.com/articles/dictionary_participation.html)
describes fields, not guaranteed current availability.

Prototype2–3 weeks; validation4–6 weeks. Gate: predict next-game opportunity against
season means/current trend methods, shrink noisy cases, account for multiple testing
and archive all prospective cases—including failures. Initially screen-only; external
notifications require opt-in authorization.

### 4. Market Story and Line Menu

Show what changed between Wednesday research and Sunday: football assumption, price,
line, availability, model version or source failure. Put actual quote observations
beside dated football evidence; a move is not proof of “sharp money.”

Private Pinnacle-led/de-vig/reference logic already exists. Public movement is not a
full explanatory historical workspace (`shared/reference-workspace.js`). [OddsJam](https://oddsjam.com/odds-api)
advertises consensus/movement tooling; the new GOING product should make the reasoning
auditable and accessible, rather than merely reproducing an odds grid.

The Line Menu compares available expressions of a thesis: ordinary Over, alternate
thresholds and other relevant contracts. Show real win/loss/push regions and the extra
outcome needed for extra payout. Identify mathematically dominated exact-rule prices.
Do not invent alternate prices or tail probabilities; do not treat contracts with
different void rules as equivalent.

Research angles: measured role change versus observed market response; consensus
disagreement conditioned on fresh book coverage; nested-threshold/cross-market
consistency. These are hypotheses, not established edges.

Prototype2–4 weeks after quote retention/redistribution rights and history are verified.
Acceptance: exact contract/receipt identity, no plotted synthetic observations, correct
push/payoff tests and understandable explanation within60 seconds. Statistical
movement-based models require separate prospective incremental-value testing.

### 5. My Football Playbook and Monday Film Room

Save a weekly research thesis, its evidence, counterargument and “what would change my
mind.” Return Sunday to a material-change queue showing teammate returns, price changes,
availability or stale sources. Record researching, waiting, verified, passed and expired
decisions. This preserves reasoning across tools, not merely another shortlist.

After the game, separate opportunity forecast errors, efficiency differences,
unexpected participation, changed market and ambiguous ordinary variation. Compare
the original forecast with actual outcomes, simple baseline and recorded prices.
Avoid retrospectively assigning causal explanations to every loss.

Existing journals are a useful foundation. [Action](https://www.actionnetwork.com/app)
and [Pikkit](https://pikkit.com/bet-tracker) advertise tracking/analytics; the target
here is a consumer learning workflow tied to immutable football assumptions.

Playbook2–3 weeks; Film Room2–4 additional weeks after outcome settlement. Start locally
with export/import. Cross-device accounts, sharing or sportsbook sync require approved
privacy/authentication design. Gate: preserved receipts, correct material-change
fixtures, explicit uncertainty, no private notes in public evidence, no small-sample
profitability claims.

### 6. Whole-Sunday Exposure Map

Combine saved singles, parlays and DFS rosters. Reveal that seemingly different choices
all depend on the same quarterback, team or shootout. Show opposing theses and repeated
conditions; compare alternative plans by their scenario exposure.

Current parlay relationship warnings do not provide this cross-ticket/cross-product
view. Initial2–3-week prototype uses descriptive counts and scenario dependencies,
not invented correlations or optimal stake prescriptions. Quantitative joint risk
depends on Game Lab validation. Stakes/private entries stay local by default.

### 7. Tournament Studio

Import the salary slate and actual contest entries/payouts; identify single-entry,
three-max or twenty-max context. Allocate multiple lineups collectively, enforce
exposures and show why a lineup fits a contest. Stress-test across plausible ownership
fields instead of presenting one simulated ROI as certainty.

Competitors already do substantial work here: [SaberSim Contest Sims](https://support.sabersim.com/en/articles/12079199-how-contest-sims-work)
and [RotoGrinders SimLabs](https://rotogrinders.com/simlabs/nfl). GOING's target advantage
is explanations, robust field assumptions and visible portfolio dependence across
the same game engine used for betting—not a claim nobody else simulates football.

Add legitimate Classic late-swap entry planning with locked-slot protection and
reviewable exports. [SaberSim's workflow](https://support.sabersim.com/en/articles/12164106-how-to-late-swap-in-sabersim)
sets an expectation. Standard Showdown locks together: provide pre-lock contingencies,
not implied post-kickoff swaps. Never submit entries through authenticated accounts.

Portfolio prototype4–8 weeks after field/scoring readiness; Classic swap planner3–5
weeks. Gates: exact payout/tie accounting, entry rules, legal exports, locked slots,
exposure constraints and held-out ownership/field checks. Historical licensed raw
lineups stay local unless redistribution is explicitly permitted.

### 8. Point-in-time Tournament Replay

Replay a finished slate with only what was known before lock, then compare actual
lineups and eligible alternatives against the whole field. Separate projection,
construction and ownership error from variance. Mark hindsight-contaminated inputs.

[SaberSim Contest Flashback](https://support.sabersim.com/en/articles/17506366-what-projections-does-contest-flashback-use)
documents timing; GOING should make provenance a first-class customer control.
Existing immutable DFS receipts are a foundation, not a complete replay product.

Prototype3–6 weeks contingent on permitted archives. Exact salary/player/game IDs,
frozen inputs and reconciled outcomes/payouts required; winner-only patterns and
backfilled projections cannot be presented as pregame predictive success.

## Major model changes supporting the products

| Model investment | Concrete change | Validation and source |
|---|---|---|
| Opponent-adjusted evolving team strength | Separate pass/rush offense/defense states from current-season completed plays, conditioned on game situations; pace separated from efficiency; uncertainty reflects exposure | Compare PF/PA, Champion and league baselines; chronological/prospective tests. [nfelo WEPA methodology](https://www.nfeloapp.com/analysis/weighted-EPA-methodology-and-performance/) is a comparator, not GOING performance proof. Prototype4–6 weeks. |
| Team-to-player distribution reconciliation | Coherent dropbacks, attempts, carries and scoring events; distribute to active players with uncertainty/reserves; audit accounting | Compare full distributions/proper scores, not only mean error. [Forecast reconciliation](https://otexts.com/fpp3/reconciliation.html), [distributional reconciliation](https://otexts.com/fpp3/rec-prob.html). Roughly4–8 weeks. |
| Predictive distribution ensemble | Combine defensible model distributions with nonnegative weights learned from chronological out-of-fold scores; preserve disagreement | Must beat strongest constituent/equal mixture without worse calibration. Agreement is not proof; correlated models can share errors. [Predictive stacking research](https://sites.stat.columbia.edu/gelman/research/published/stacking_paper_discussion_rejoinder.pdf).2–4 weeks after reproducible constituents. |
| NCAA schedule-strength engine | Current-season offense/defense states across conference/division schedule graph, explicit weak connectivity/FBS–FCS/neutral venues | Strict through-week receipts, separate NCAA baselines and segment tests. [CFBD methodology](https://apinext.collegefootballdata.com/methodology-overview) provides a comparator; API cost/coverage is not assumed.4–6 weeks if permitted data exists. |

The Matchup Mechanism Lab can then explain how observed target depth/situation matches
a defense's actual weaknesses. Existing context/CSV features overlap, so the new part
is an integrated mechanism explorer with incremental validation. [Outlier opposition
rank](https://help.outlier.bet/en/articles/8575657-understanding-opposition-rank-in-outlier)
is an aggregate comparator; do not fabricate routes, coverage or alignment.

## Recommended investment order

1. **This week:** finish the earlier safety/measurement plan and archive the first
   valid future inputs. Write Game Lab's scenario/accounting specification and test
   one game with existing evidence. Keep the released weeks6–10 experiment unchanged.
2. **First major product,2–3 weeks:** Injury Opportunity Workbench as the initial
   Game Lab experience. It directly uses GOING's football data and creates a useful
   product while the structural model remains a challenger.
3. **Next4–6 weeks, choose one parallel product lane if resources permit:** Playbook/
   Market Story for betting customers, or contest/entry/risk imports for DFS customers.
   Do not attempt all flagship products simultaneously.
4. **Research lane, roughly8–12+ weeks:** team states → reconciled opportunities →
   validated game simulations/ensemble. Exact timelines depend on coverage, compute
   and validation outcomes; unsuccessful models stay research-only.
5. **After evidence:** quantitative SGP dependence, contest portfolio simulation and
   richer matchup effects. Live-game state forecasting is a later option requiring
   permitted timely data; no live-feed access or new spending is assumed.

## How to demonstrate GOING is better

Measure whether customers can explain a change, trace a thesis and compare alternatives
in a minute; whether saved reasoning survives a week; whether uncertainty and missing
sources are understandable; whether exports/replays are correct. Measure predictive
quality against existing methods and market benchmarks on identical available samples.
Measure user decisions to pass as well as selections—not engagement or more wagers alone.

Potential advantages are evidence continuity, football accounting, counterarguments,
cross-product consistency and transparent uncertainty. Validate these against public
competitor workflows without inventing their internal limitations. Do not claim an
accuracy/profitability advantage before measurements support it.

Dependencies to approve before paid or risky implementation: redistribution/retention
rights for quotes, licensed field/coverage data, new account/database architecture,
notification delivery and any metered AI/provider calls. Early import-driven/local
prototypes can use existing data at no new service cost. No basketball development;
NFL/NCAA are primary and MLB is maintained.
