# Handoff to Codex: NFL Ensemble Lab state as of 2026-10-26 (about 18:45 ET)

Written by Claude (reviewer and research sessions) for Codex (primary developer).

**What it covers:**
- what exists locally;
- what is pushed and what isn't;
- what runs live;
- every research result since Phase 8.3;
- what is waiting on Travis.

**Who decides:** Travis approves every push, merge, deployment and promotion.

## 1. Git state (exact)
- **Repository:** `daboli69/going-long`, local checkout `C:\Users\travi\OneDrive\Documents\ChatGPT\GOING`.
- **Current branch:** `codex/projections-20261019`. HEAD is **8a51a2ad**.
- **Pushed head of that branch:** `origin/codex/projections-20261019` = **9eea7271** (Phase 11 pre-registration). Travis
  pushed it himself, knowingly including 7 NBA commits (c50bf0f6 to afb51ab8).
- **11 local commits not pushed** (Travis said "keep local"):

  | Commit | Content |
  |---|---|
  | f0af3f00 | Phase 11 market-blend code, tests, dashboard tab |
  | e2798112 / 600b0ba8 | Phase 12 pre-registration / results |
  | 294685aa / aea1187e | Phase 13 pre-registration / results |
  | 0d0795db / 317ad081 | Phase 14 pre-registration / results |
  | ec12b3b2 / a0541daa / 6dce757e / 8a51a2ad | Phase 15 pre-registration / code / bug fix / results |

  - To publish later, Travis runs: `git push origin 8a51a2ad:codex/projections-20261019`.
  - Claude sessions are blocked from pushing this branch, so pushes go through Travis.
- **`origin/codex/nfl-ensemble-lab`** = **5ca58e80** (props simulator v2 and Player Props page). It is an ancestor of HEAD
  and holds nothing HEAD lacks. HEAD is about 99 lab commits ahead of it, mostly Codex's FPDS and injury-simulation work.
- **Uncommitted changes that are not Claude's** (left untouched):
  - `docs/FPDS_COLUMN_COVERAGE.json`
  - `docs/FPDS_DATA_DICTIONARY.md`
  - `docs/FPDS_FEATURE_COVERAGE.json`
  - `reports/run_20261020/FPDS_A6_AUDIT.json`
  - `tests/test_fpds_research.py`
  - untracked `docs/design-reference/` at the repository root
- **Nothing** has been merged to `main` or deployed.
- **The GOING public feed branch `nfl-lab-feed`** exists. Feed contract `going-nfl-lab-feed` 1.0.0 is in
  `docs/GOING_FEED_CONTRACT.md`. Publishing is manual (`publish_going.bat --push`) and is not scheduled.

## 2. Live system (unchanged by Phases 11 to 15)
- **Windows task:** "NFL Ensemble Lab - Data Refresh" runs every 5 minutes:
  `.venv\Scripts\pythonw.exe -W ignore releases\run_tick.pyw`. The last check was 18:40, with result 0.
- **Pinned release:** `releases/CURRENT.json` = **lab-v8.1.0-ec56eb3** (commit ec56eb35), switched 2026-10-17 19:16 UTC.
  Rollback is lab-v7.3.1-d9a650e. Release history is in `releases/history.jsonl` and `docs/RELEASES.md`.
- **Champion:** `v20261016_212540`, a 6-model weighted average (logistic regression, XGBoost, decision tree, random forest,
  MLP, single layer). It uses 85 features and **excludes** the Phase 3 context group (travel, time zone, body clock).
- **Registered challengers:** `v20261017_021344_p5_player_continuity` and `v20261017_142546_p7_qb_snap`.
- **Live scoring, weeks 6 to 7 (26 games, through 2026-10-26):**

  | Forecast | Log loss | Accuracy |
  |---|---|---|
  | Champion | 0.774 | 53.8% |
  | p5 | 0.753 | |
  | p7 | 0.758 | |
  | Closing market | 0.696 | 61.5% |

  The champion's gap to the market is +0.079 (SE 0.036).
- **Other archives the scheduler writes:**
  - market: ESPN/DraftKings lines (current week only), stored in `data/raw/archive/market/`;
  - injuries: nflverse versions and ESPN snapshots, in `data/raw/archive/`;
  - depth charts: `data/raw/depth_charts_2026.parquet`, which has `dt` timestamps.

## 3. Research results, Phase 8.3 onward
All of these are local-only research. None changed the champion.

| Phase | Question | Verdict | Doc |
|---|---|---|---|
| 8.3 | Nine upset metrics (luck, scheduling spots, referees, 4th-down aggressiveness) | All rejected | PHASE8_3_UPSETS.md |
| 8.4 | High-variance underdogs; line movement toward the underdog | Variance rejected. Line movement **passed** against the champion (Holm p 0.0001), but it is priced into the close. Prospective flag S2P: 26/128 games | PHASE8_4_UNDERDOGS.md |
| 8.5 | 16 combined angles on AusSportsBetting 2006–25 lines and 1999–2014 play-by-play | All rejected beyond the close. S2 replicated on 2022–24 (p 1e-5) | PHASE8_5_COMBINED_ANGLES.md |
| 8.6 | Big Data Bowl 2026 tracking (2023): separation edge | Not significant (p 0.23). NGS proxy r = 0.58 | PHASE8_6_TRACKING.md |
| 8.7 | NGS separation, 2016–25 | Rejected (p 0.15) | PHASE8_7_NGS_SEPARATION.md |
| Props v1 | Play-by-play Monte Carlo player-props simulator (DraftKings-style) | **Passed** the single 2023–25 look: CRPS 13.30 vs 13.96, p 0.0005. Means 4–8% high | PROPS_SIMULATOR.md |
| Props v2 | Fixes tuned on 2022; weekly 2026 archive | Prospective; only DAL–GB archived so far (v1 and baseline only) | PROPS_V2_PREREGISTRATION.md |
| 11 | Champion + opening-line blend shadow (frozen weights) | Prospective, 0/128 | PHASE11_MARKET_BLEND.md |
| 12 | Circadian night-game edge (Smith et al. 2013) on 2012–25 | Not replicated (+0.77 ± 1.42, p 0.30) | PHASE12_CIRCADIAN.md |
| 13 | Error budget; Kalman market-anchored challenger | Champion-to-close gap 0.020: half modelling against the opener, half late information. QB changes triple the gap. Kalman = the opener (fails) | PHASE13_RESULTS.md |
| 14 | Hierarchical QB value model; e-process monitors; ledger | Q1 r = 0.22 (pass), Q2 log loss p 0.074 (fail). Kept as monitor M6 | PHASE14_RESULTS.md |
| 15 | Point-in-time QB knowledge (Wayback); market-implied values; sealed 2025 vault | About half the QB signal was hindsight (point-in-time r ≈ 0.15–0.19). Deming scale 1.06 on 2015–24. Vault V1 failed on scale (2× in 2025). V2 untestable (no 2025 timestamps) | PHASE15_RESULTS.md |

**Also:**
- **Phase 9:** the GOING NFL Intelligence integration (feed, `api/nfl-lab.mjs`, `shared/nfl-intel.js`).
- **Phase 10:** Codex's own data-archive work. See `PHASE10_*.md`.
- **6-hour tuning job** `lr20261018_051602`: no family beat the champion, and most did worse in 2025. It was marked killed
  in the ledger (power analysis: gains under 0.005 are undetectable).

**Recurring lessons:**
- The opening line already contains what score-based ratings know. The closing line sits at the noise floor.
- Detecting a 0.01 log-loss gain needs about 2,400 games. Line-move prediction needs only about 600 games for r = 0.1.
- Free archives can't reconstruct historical news timing. The lab's own 2026 archive is the clean evidence from now on.
- FiveThirtyEight-style QB adjustments track the market better than the lab's QB model in every check (0.65 to 0.71 against
  0.29 to 0.50).

## 4. Prospective tests and weekly commands (all manual; nothing new is scheduled)
Run these from `research/nfl-ensemble-lab` with `.venv\Scripts\python.exe -W ignore -m ...`.

| What | Command | When |
|---|---|---|
| Props archive (v1, v2, baseline) | `lab.props.weekly` / `... preview --week N` / `... score` / `... summary` | After inactives, about 90 minutes before kickoff. Score after the play-by-play refresh |
| QB values freeze | `lab.phase14 freeze` | Before each slate |
| Point-in-time line freeze (M7) | `lab.phase15 freeze` | Sunday night and Wednesday morning |
| QB news event study | `lab.phase14 events` | Any time |
| Monitors M1 to M7 (e-values and futility) | `lab.phase14 monitor` | After games |
| Ledger regeneration | `lab.phase14 ledger` | After editing `research_ledger.json` |
| Phase 11 blend scoring | `lab.market_blend11` | After games |
| Overnight reproduction and prospective refresh | `lab.overnight` | Optional |

**Monitor rules:**
- An e-value of 20 or more is evidence at α = 0.05, valid when checked weekly.
- The futility bound assumes σ = 1 as pre-registered, so it is very conservative.
- The fixed-sample rules from Phases 3, 8.4 and 11 stay authoritative.
- **Program stopping rule:** if no monitor reaches e ≥ 20 by the end of 2026 week 18, the QB and late-news program pauses.
  This is recorded in `research_ledger.json`.

**Known limits:**
- ESPN's odds archive only holds the current week, so freezes cover few games. The first freezes covered 1 game each.
- Props scoring needs the 2026 play-by-play refresh.
- **Monitor M1 isn't wired yet.** `lab/phase14.py` looks for `market_blend11.score()`, but the module only has
  `score_table()`, so M1 currently reports nothing. Small fix for Codex.

## 5. Local-only data (git-ignored; never commit or publish)
| Path | Content | Source and terms |
|---|---|---|
| `data/raw/market/aussportsbetting_nfl.xlsx` | Opening and closing lines. 2006–13 has the closing line only; true openers start in 2014; 2025 covers 73% of games | Manual download by Travis |
| `data/raw/history/` (258 MB) | nflverse play-by-play 1999–2014 | Hashes in `SHA256SUMS.txt` |
| `data/raw/public/` (7.6 MB) | nfelo `nfelo_games.csv` (includes FiveThirtyEight QB adjustments) and spreads; sportsoddshistory win totals 2017–25 | nfelo repository has no license: local comparison only |
| `data/raw/kaggle/` (833 MB) | Big Data Bowl 2026 analytics and prediction (2023 tracking) | Competition rules: no redistribution. The evaluation code was not run |
| `data/raw/wayback15/` (135 MB) | ESPN injury-page captures and CDX indexes, 2018–25 | Wayback Machine |
| `artifacts/` | Every phase's results, props evaluation, prospective archives, longrun jobs | Local |

**Kaggle:** an API token file exists at `%USERPROFILE%\.kaggle\access_token`. A Kaggle key was pasted into chat on
2026-10-18, and Travis was advised to revoke it. Whether he did is unverified. Never print or commit token contents.

## 6. Code map (new since Phase 8.3)
| Area | Files |
|---|---|
| Phase 8.3 to 8.7 studies | `lab/upsets83.py`, `upsets84.py`, `upsets85.py`, `tracking86.py`, `ngs87.py` |
| Kaggle download helper | `lab/kaggle_bdb.py` |
| Overnight batch | `lab/overnight.py` |
| Props simulator | `lab/props/` (`models.py`, `sim.py`, `players.py`, `evaluate.py`, `game.py`, `v2.py`, `tune_v2.py`, `weekly.py`) |
| Phase 11 blend | `lab/market_blend11.py` |
| Phases 12 to 15 | `lab/circadian12.py`, `lab/phase13.py`, `lab/phase14.py`, `lab/phase15.py` |
| Sequential tests | `lab/sequential.py` (e-process, confidence-sequence futility) |
| Ledger | `research_ledger.json`, `docs/LEDGER.md` |
| Dashboard | Blind-spot research tabs for 8.3 to 8.7, props, and Phase 11 (`app/streamlit_app.py`) |
| Tests | `tests/test_phase8x.py`, `test_props.py`, `test_phase11.py` to `test_phase15.py`, `test_overnight.py` |

The last full suite run was **529 passed, 1 skipped**.

## 7. Rules Travis has set
- **Roles (CLAUDE.md):** Codex is the primary developer; Claude is the reviewer and progress reporter.
- **Sports scope:** football first; baseball (Going Yard) is regression-only; basketball needs Travis's authorization (the
  NBA commits on this branch are Codex's).
- **Research method:** pre-register before results, one look per historical test, prospective-only validation, Holm
  correction, and no promotion without prospective evidence plus Travis's approval.
- **Spending:** $0. No paid APIs (never use PARLAY_API_KEY), no paid services.
- **Off limits without asking:**
  - pushes to `main`, merges, deployments, migrations and force pushes;
  - changes to the pinned scheduler release or the Windows task;
  - GOING production changes;
  - running scanners with `--send` or `scripts/smoke_alerts.py`.
- **Commits stay local** unless Travis says otherwise. Travis runs pushes himself.
- **Never disclose** keys, webhook URLs, passwords or `private/` contents.
- **Writing:** prose meant for readers goes through the `clean-user-facing-text` skill. Plain wording, no em dashes.

## 8. Open items and recommended next step
**Waiting on Travis:**
- pushing the 11 local commits;
- any GOING deployment;
- scheduling the weekly commands (that would change the pinned release, so it needs his approval);
- confirming the Kaggle key revocation.

**Next research step** (Travis's latest direction; not started or registered):
1. Put the point-in-time QB signal in money terms: expected closing line value in points against the −110 break-even
   (52.4%), with a paper-only Kelly simulation. Pre-register the minimum edge worth pursuing.
2. Rebuild FiveThirtyEight's published QB value formula from raw per-game box scores and validate it against their
   historical adjustments in nfelo's file. Then pre-register one improvement on top of it.
3. Replace the fixed QB-to-points scale with a rolling or time-varying estimate, with a CUSUM drift alarm. Check whether it
   would have caught 2025's 2× miss.
4. Add a weekly archive-health audit: missing snapshots, stale lines, news-to-line latency, coverage.
5. Record a pre-mortem per hypothesis in the ledger.
6. Validation beyond us: reproduce FiveThirtyEight's numbers, closing line value against the bookmaker's margin, future
   archived games, and an independent rebuild by Codex from the pre-registration.
