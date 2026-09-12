# GOING expansion: decisions and evidence

2026-09-11. Football data remain separate from baseball model terminology and scoring. The GOING shell will host /long/ and /yard/ at the existing Vercel origin, with separate fantasy entry points. Baseball stays backed by hr-board’s current published snapshots; its frozen contact model is not retuned.

## Public evidence

- nflverse participation: https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html . From 2023 onward, all-player participation is published after the season. Current 2026 participation and FTN charting returned unavailable; current snap counts returned 187 rows. Passing snaps are not routes. Current badges therefore use offensive snap share, explicitly labeled, with separate historical passing-snap research.
- FTN via nflverse: https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html . Charted drops/catchability and blitz counts exist in the public subset, but 2026 was not published when checked. Missing charting is not zero. Historical personnel, rushers and coverage are contextual facts, not invented current slot/X splits.
- Play-call identity differs from title: Carolina confirmed Brad Idzik takes over for Dave Canales in 2026: https://www.panthers.com/news/dave-canales-offensive-coordinator-brad-idzik-to-call-plays-in-2026 . Current staff source: ESPN Mike Clay guide, updated September 9: https://g.espncdn.com/s/ffldraftkit/26/NFLDK2026_CS_ClayProjections2026.pdf . Current staff labels must not be attached to a different caller’s past offense as personal history.
- Formation and play-call context can predict run/pass choice; predicting a play is not proof of a betting advantage. Model study: https://arxiv.org/abs/2003.10791 . Use measured tendencies, shrink thin rates toward their position/league reference, and do not assert causal edges.
- Existing prospective scoring rules and price-movement discipline remain in SIGNALS_PLAN.md. New weeks refresh evidence and results automatically; model changes require forward evaluation, not automatic optimization of a few winning bets.

## Implemented design targets

Opportunity without payoff: compare WR with WR and TE with TE. Minimum games, snaps, targets and peer counts are disclosed. Separate high playing-time share from a shortfall in catches relative to the public completion model; do not call every incompletion bad luck. Passing-snap share is the preferred historical proxy; current offensive snap share is a weaker fallback that includes blocking.

Defensive context: receiving yards allowed by position, adjusted against the targeted players’ production against other defenses and shrunk toward zero. Report targets, games and date range. This is not PFF grading and not a slot/perimeter classification. Run defense uses measured yards per carry and success allowed; outside-run location is not the outside-zone blocking scheme.

Coaching: current verified staff and actual measured team-year passing tendency, first-15 play calls, pace, personnel and RB/TE target usage. Head-coach meetings use observed W/L and performance against the closing spread, with a minimum meeting count; no personality narrative or claim the coach caused it.

NFL notes: deterministic sentences from those fields plus actual spread, total and recent yardage/catch/carry logs. No LLM-generated facts or manually seeded player recommendations. Stadium roof may be described when the schedule supplies it; no weather-based adjustment.

Baseball: add a same-slate, matched-player model-rank versus bookmaker-rank explorer, keeping rank disagreement separate from win probability. Free-keyless baseball sources remain those already in the real pipeline. Fantasy entry initially provides actual player research and saved watchlists; it does not claim a league connection that does not exist.
