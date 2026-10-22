# Phase 9: GOING NFL Intelligence integration (the local lab is preserved)

Two interfaces share the same research:
1. **Local NFL Ensemble Lab** (unchanged): Streamlit dashboard, Windows launchers, the pinned scheduler release, the models,
   research and archives.
2. **GOING website**: a new **NFL Intelligence** section under Football → Betting, next to Games. It sits alongside GOING's own
   predictions, which are unchanged.

## Architecture
```
Windows PC (lab)                                     GitHub (public repo)                   GOING on Vercel
  pinned scheduler -> immutable stage snapshots
  scripts\launchers\publish_going.bat [--push]
    going_feed.build()  (read-only, sanitised)
    validate()  -> publish/nfl_lab_feed.json
    --push: git plumbing commit -------------------> branch nfl-lab-feed   <------- api/nfl-lab.mjs (8 s timeout,
            (checkout, index and branches untouched)  /nfl_lab_feed.json              validates schema 1.x, CDN 120 s)
                                                                                  -> shared/nfl-intel.js renders it
```

- **Website independent of the PC:** GOING reads the **last published commit** from GitHub, so it keeps working when the PC is
  off. The UI shows the feed's age, and marks it stale after 36 h.
- **No live connection:** there is no endpoint on the PC, no inbound access and no credentials in the website. The repository is
  already public, so the feed is published only after sanitisation, and the same validator runs before every write.
- **No new infrastructure or cost:** it reuses GOING's existing pattern (`api/snapshot.mjs` already reads raw GitHub files).
- **Publication never blocks forecasting:** the publisher is a separate command and is **not** part of the scheduler or the pinned
  release. A failure is logged to `publish/history.jsonl` and shown in the dashboard; it never raises into anything else.
- **Fallback:** if a deployment ever packages `data/nfl_lab.json`, the API falls back to it. None is packaged by default, which
  avoids shipping an outdated forecast inside a deploy. With nothing published, the section says the lab feed isn't available,
  and every other GOING tab is unaffected.

## What the website shows (only fields that exist in the artifacts)
- **Overview:** champion probability bar, pick, predicted margin, six-model vote, forecast stage and archive time, and game status
  (with the final score only after the game).
- **Six-model debate:** each model's probability and margin, plus the spread between them, with the explicit note that the six
  models are highly correlated (about 1.2 effective models).
- **Player intelligence:**
  - the QB each side's champion forecast assumed, and the live monitoring projection (a mismatch is flagged);
  - the verified-report status;
  - projected starter absences with play probabilities, and offensive-line availability.

  Lineup analysis is labelled as analysis, not a model input.
- **Game simulation (experimental):** simulated margin and total, with 80% ranges, and a note that historical totals were weak.
- **Market comparison (benchmark):** the price at the forecast's data refresh, plus the latest DraftKings opening and current
  prices with their timestamps. It shows champion minus market at forecast time, and warns that this is not a proven edge and
  that later prices are not directly comparable.
- **Challengers and forecast history:** registered challengers (research) and each archived stage.
- **Model performance:**
  - **Prospective:** archived pregame forecasts only, counted against 128 required games.
  - **Historical:** champion walk-forward results, labelled as research-exposed.

  The two are kept separate.

## One-time setup (needs Travis)
1. **First publication:** run `scripts\launchers\publish_going.bat --push` in the lab folder. It uses your existing git credentials and creates
   branch `nfl-lab-feed` containing only `nfl_lab_feed.json`. This publishes the sanitised forecasts in a public repository, so it
   was **not** run automatically.
2. **Deployment:** merge or deploy this branch through the normal GOING process. The NFL Intelligence section appears once deployed.
   Not done; it needs your approval.
3. **Automatic updates (optional):** either
   - add a separate Windows task that runs `scripts\launchers\publish_going.bat --push` (for example every 30 minutes on game days, or hourly), or
   - include the publisher in a future pinned release.

   **Neither is active.** Until one is set up, the website shows the last published feed and marks it stale after 36 h.

## How the two stay in sync
- The lab writes forecasts on its schedule.
- Each publish takes the latest archived pregame snapshot per game and commits it to `nfl-lab-feed`.
- GOING fetches that commit (CDN-cached for 2 minutes).
- Freshness is visible in both places:
  - **website:** "Published …" and the stale banner;
  - **lab dashboard:** Live Readiness → Operations → Website feed, showing the last local forecast, last publication, last
    attempt and any errors.

## Verification
| Check | Result |
|---|---|
| GOING `npm test` | 167/167, plus 6 new tests: rendering, stale, missing and invalid feeds, HTML escaping, the API route, wiring, QB-name suffixes |
| Lab `pytest` (full) | see the commit message. New: contract validation, git-branch publication (separate branch, checkout untouched, identical content not re-committed) and failure logging |
| Browser (built site, real feed copied into the disposable build folder only) | desktop and phone: 14 games render; no horizontal overflow; QB mismatch flagged only for the genuine case (CHI); Markets and other tabs unchanged |
| Pinned scheduler | still `lab-v8.1.0-ec56eb3` via `releases/run_tick.pyw` |
| Models, archives, registry, GOING predictions | unchanged: no snapshot, model, registry or GOING prediction file was modified |

**Bugs found and fixed during the work:**
- ESPN team codes (LAR, WSH) are now mapped at read time.
- A Windows CRLF problem corrupted git tree entries.
- The temp-file lock was fixed.
- The QB-name suffix false positive on the website was fixed.

**An existing GOING test changed:** the navigation test's expected tab list now includes "NFL Intelligence", because the new
section is deliberate.
