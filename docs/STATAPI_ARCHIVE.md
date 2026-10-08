# stat-api historical DFS archive (private)

The archive lives OUTSIDE the repository (`GOING/StatApi`, plus a second copy in `~/GOING-archive-backup`). It holds licensed data: stat-api's plan allows keeping it for personal research after
cancellation, and forbids publishing it or charts/tables made from it (distribution needs an Enterprise License). Nothing from it is committed, served or shipped to the frontend; derived
ownership/duplication models are research-only until the rights are confirmed.

Tooling (this repo, no data, no key): `scripts/statapi/client.py` (Bearer auth from the STATAPI_KEY environment variable only; byte-for-byte gzip raw archive named by sha256; waits on 429 Retry-After),
`inventory.py` (slates and contests; slate rows cost 1 record each, contest listings are free), `archive.py` (projections, plan, resumable contest downloads, fetch_log), `normalize.py` (parquet plus a
per-contest validation report), `ownership_data.py` and `ownership_baseline.py` (chronological ownership benchmarks).

Cost facts observed: contest download = lineups + player-pool rows; slate projections (including the provider's projected ownership) cost 0 records; slate_players is redundant (salaries are in the projections).
