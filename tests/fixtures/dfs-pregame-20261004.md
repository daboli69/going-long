# DFS pregame parity fixture

`dfs-pregame-20261004.json.gz` preserves five unmodified public JSON blobs from production commit `3def63b3ba9381b356632ceeaf14dd9b869841ca`: history, football_context, nfl_roster, injury_context and dfs_team_touchdowns. Each raw blob carries its original SHA-256; gzip has deterministic mtime zero.

The parity regression uses the latest original input timestamp plus one minute, before the Sunday afternoon slate. It keeps every future/stale/pregame assertion. Rolling postgame data cannot replace decision-time inputs. This fixture supplies no invented salaries, contest pool, results or performance claims; it is not used by production or prospective ranking collection.
