# Annotation: early October 11, 2026 freeze

`data/freezes/2026-10-11.json` is an immutable write-once record and is intentionally left unchanged. This note records how it was created.

- **When it was written.** `frozen_at` is `2026-10-11T01:06:24Z` (Saturday, 9:06 PM Eastern). A scheduled `data.yml` run on `50b0574` wrote it. That run still used the old `sunday_freeze.py "$(date -u +%F)"` call, which treated the UTC date as the slate day. The intended Sunday pregame window starts at 04:20 Eastern.
- **What its inputs were.** The run's `nfl_betting.json` reported `feed_status: FALLBACK`, with props and derivatives `STALE` because of the upstream HTTP 503 outage. Its `availability.ok: true` came from the old check, which judged freshness by build time. Injury and roster files then carried no source-content clocks, and nflverse report rows had no dated report times.
- **How to read it.** Treat it as an early Saturday-night snapshot. It is not a verified Sunday-morning pregame freeze. Do not use it as evidence of fresh props or verified game-day availability.
- **What it affects.** No page, recommendation or model reads `data/freezes/`. The file affects neither current recommendations nor later data publication.
- **What prevents a repeat.** The release that merges `claude/nflmeta-availability` takes the slate day from the America/New_York clock and refuses before Sunday 04:20 Eastern. It also refuses unless sources are fresh and verified, including FRESH props and derivatives. Write-once behaviour is unchanged. Later October 11 runs therefore report "already frozen" and leave this file as it is.
