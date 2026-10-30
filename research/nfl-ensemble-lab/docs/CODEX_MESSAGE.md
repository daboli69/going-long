Message for Codex (paste as is). Written 2026-10-30; branch head at writing: a8e04c68.

---

Hi Codex. Travis asks you to independently check seven studies that Claude built and ran, plus one code change. You cannot see Travis's PC, so everything below is on GitHub.

**Where.** Repo `daboli69/going-long`, branch `codex/projections-20261019` (full clone, not shallow: one study reads quote history from git). Lab folder: `research/nfl-ensemble-lab`. Python 3.12, `pip install -r requirements.txt`. Everything is $0, read-only, football only. Kalshi data is public and needs no key. Do not touch main. Put your work on a new branch `codex/repro-20261030`.

**Task 1: reproduce, then compare.**
1. Read only the protocol documents first (the `*_PREREGISTRATION.md` files in `docs/`; the table in `docs/CODEX_REPRODUCTION_REQUEST.md` lists the protocol commit, code commit and run command for each of the seven studies). Do NOT open the `*_RESULTS.md` files or the last column of that table yet.
2. Rebuild each study from its protocol and code commit, using the run commands in that table. Compute your own numbers.
3. Then compare with the last column of the table. Tolerance: deterministic fits to 4 decimals; simulation metrics within 3 Monte Carlo standard errors (state yours).
4. Known data limits. `data/` and most `reports/` are git-ignored, so caches must be rebuilt: nflverse files download automatically through `lab.sources`. `api.nfldata.org` is a parked domain, so the code falls back to the lab's `games.csv`. Kalshi pulls take hours (about 63,000 candle requests). The GOING quote history comes from the git log of `data/nfl_betting.json`. ESPN injury snapshots from 2026-10-16 exist only on Travis's PC, so Experiment B (events) cannot be rebuilt by you; say so.
5. If you cannot run something, say which step and why, and do a code and protocol audit instead: does the code do exactly what the protocol says, and are there leakage paths (anything using data after the decision time)?

**Where I most want a second opinion.**
- Study 5: does the walk-forward 500-threshold minimum explain why only 6 of 20 weeks were scorable? Is the Kalshi spread/total median interpolation sound?
- Study 6: the closed-form Gaussian team-strength model and the ladder-shift correction.
- Study 7: the usage arms in `scripts/usage_study.py` (roster status ACT as the oracle, the 5% prior-share threshold, `date_modified` before kickoff as the availability rule); the Experiment B bug that was fixed after the first run (next game was defined by today's played status).
- Two honest corrections already made: the earlier props "stack pass" was in-sample; Amendment 1 changed the usage arm after a pilot on 2018 to 2020.

**Task 2: review one change.** Commit `a8e04c68` treats Doubtful players as unavailable in `lab/props/injury_adjusted.py` (the manual shadow path), based on a preregistered test on 2021 to 2024 (Amendment 3 in `docs/MARKET_NEWS_PREREGISTRATION.md`; targets +0.0071 nats, carries +0.0121). It also adds an optional `out_statuses` argument to `lab/props/weekly.py::availability` with the default unchanged, and replaces one test. The preregistered prospective archive was NOT changed. Please check the logic and tests, and tell Travis whether you think the prospective archive should adopt the same rule (that needs him to amend `docs/PROPS_V2_PREREGISTRATION.md`).

**Report.** Create `docs/CODEX_REPRODUCTION_REPORT.md` on your branch: one row per study (matched yes or no, your numbers, tolerance, notes), then any bugs or protocol mismatches, then your view on Task 2. Please do not edit Claude's result files; report disagreements instead. No paid APIs, no deployments, no migrations, no force pushes.

Thanks.
