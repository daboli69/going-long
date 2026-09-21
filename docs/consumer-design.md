# Shared consumer UI

## Before / after

The audit examined 730 football CSS rules, 2,136 Yard rules and 33 hub rules. It found competing control colors, fonts, radii and shadows. The migration removed 203 redundant appearance declarations; the remaining stylesheet colors, radii and elevation declarations now refer to the shared palette. Layout and sport calculations were preserved.

Before: orange, green and white button variants, including white-on-white Today filters. After: dark ink on a light control surface, teal selection, common 44px minimum height, shared radius/type scale and button shadow. Disabled, hover, active and keyboard-focus states are explicit.

Before: per-bet metric definitions filled the first evidence expansion. After: at most four labeled numeric panels, with full evidence and sources in a second expansion. No chart invents a missing measurement. MLB contact/production strength is never rendered as a probability.

`shared/design-tokens.css` owns the palette, spacing, type, radii, motion and elevation. `consumer-ui.css` owns controls, surfaces, cards, evidence and injury regions. `going-shell.css` owns only shell layout. `scripts/audit_design.cjs` provides a reproducible inventory and one-time mechanical migration. The Pages copy in hr-board uses the same shared assets.

Bounded references: [Sleeper's quick player research](https://sleeper.com/blog/sleepers-app-redesign-whats-new/), [FanDuel's betslip interaction](https://www.fanduel.com/sportsbook-cash-out), and [Venom's public product listing](https://whop.com/venom-analytics-23d5/). No claim is made to have inspected Venom's authenticated proprietary implementation.

## Static data and navigation

`/players/` uses the scheduled `data/nfl_roster.json` export. It includes every position with ACT status in the latest published regular-season roster week, with that week explicitly shown. Weekly ACT status is not a confirmed game-day active list. Exact injury and practice strings are preserved. Rest-only records without an injury designation are omitted. Unspecified locations have no anatomical highlight; paired regions do not assert laterality.

Usage comes from the existing current-season context/history. Missing measured routes are not replaced with passing snaps or zero. Defensive/specialist players remain searchable even when position-specific usage is unavailable. The main search links directly to their profile.

The same opportunity renderer serves Today, player pages and Yard's Opportunities tab. Baseball uses existing HR/contact/HRR scores and HRR projections; no new baseball probability or staking model was introduced. Legacy odds are accepted only for a unique player/matchup on the exact slate day, with a dated quote and exact prop line. Ambiguous doubleheaders are excluded rather than guessed. All matching book offers remain available through book/market/name filters.

The shared comparison slip persists on the same origin across sports. Different-book, same-game and old-price combinations are warned about, not priced as valid tickets. Separate-game price multiplication is labeled indicative; no joint win probability is asserted. Browser storage cannot be shared automatically between GitHub Pages and Vercel origins.

## Sport-neutral signal schema

Each observation has `schema_version`, `id`, `sport`, `event`, `entity`, `signal_family`, `features`, `sample_sizes`, `rank`, `rank_scope`, `strength`, `model_version`, `observed_at`, `source`, `outcome`. Features and outcomes are extensible maps. A future sport supplies an adapter; the core shape does not change.

Yard records retain heat, contact/production scores, vulnerability, square-up measurements, pitch-mix evidence, park factors, badges, underlying metrics and samples. Previously frozen records legitimately missing a feature retain null; present-day features are never inserted into past observations. Rank is within the recorded game, explicitly labeled in the data. The existing final-boxscore grader supplies actual HR, hits and H+R+RBI. First captured pregame features stay immutable when outcomes arrive.

Football imports its existing frozen prediction/settlement ledger without reranking old forecasts. Unknown rank is null rather than reconstructed. `/results/` is a public, static journal with sport/search/outcome filters and progressive rendering. Counts describe observations, not independent games or verified betting returns. No retrospective score tuning occurs.

Daily Actions publish the roster, opportunity feed and journal. Export failures retain dated records and report STALE/FAILED; independent source updates are preserved. No new backend, database, server-side rendering or paid hosting dependency was added.
