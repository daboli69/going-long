# Going Long

A draft war room built on the Late-Round Draft Guide's model. Every player is
priced in expected PPR points per game, valued against your league's actual
replacement level, and scored by what it costs you to wait.

Runs on GitHub Pages. No build step, no server, no API keys.

---

## Setup from scratch

You haven't pushed anything yet, so start here.

**1. Create the repo**

```bash
cd path/to/going-long
git init
git add .
git commit -m "Going Long: draft board"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/going-long.git
git push -u origin main
```

**2. Let Actions write to the repo**

Settings → Actions → General → Workflow permissions → **Read and write
permissions** → Save. The data job commits back to the repo, so it fails
without this.

**3. Turn on Pages**

Settings → Pages → Source: **Deploy from a branch** → branch `main`, folder
`/ (root)` → Save. Your board lands at
`https://YOUR_USERNAME.github.io/going-long/`.

**4. Build the data**

Actions → **Refresh draft data** → Run workflow. Takes about two minutes and
commits `data/players.json` plus nine format files. After that it runs every
morning on its own.

If none of your leagues are 12-team, edit the `FORMATS` list at the top of
`scripts/build_data.py` before running.

**5. Connect your leagues**

Open the page. Enter your Sleeper username → Find my leagues → pick the league
and draft → Add this draft. Repeat for every league you're in; the dropdown in
the header switches between them. Team count, scoring, roster slots and
superflex are all read off Sleeper — nothing to configure by hand.

**6. Load the guide**

Under **Rankings & tiers**, select all five LateRoundQB CSVs at once
(`ppr`, `half-ppr`, `te-premium`, `superflex`, `superflex-te-premium`). Each
one is stored as its own board and tagged by format from its filename, and
every league you add picks up the board matching its shape automatically — a
superflex TE-premium league gets the superflex TE-premium rankings without you
choosing. Pasted cheat sheet rows work too.

Under **Market Score**, paste all four position tables at once. Anything that
doesn't name-match gets a dropdown to fix — usually five or six players.

Both live in browser storage, so they persist without being committed. If you'd
rather keep them in the repo, export from devtools and drop the JSON in
`data/` — nothing in the app cares which.

**7. Optional: profile your league**

```bash
LEAGUE_ID=your_league_id python scripts/manager_profiles.py
```

Walks every draft your league has ever run and writes `data/managers.json` —
who reaches, who waits, who drafts straight off a sheet. Not wired into the
board yet.

---

## Reading the board

**EDGE** is what the current pick buys you over waiting. Not "how good is he" —
if a player you love won't be taken for another twenty picks, waiting is free
and his edge is low. It spikes when someone unlikely to survive is also well
clear of the next man at his position.

**VORP** is points per game above your league's replacement level, which is
derived from your actual starting slots. In a superflex league the QB baseline
slides from QB12 to roughly QB20 and every quarterback's VORP jumps
accordingly — nothing about that is hardcoded.

**MS** is Market Score, converted into points. The model's ranking is compared
to the ADP ranking, and the gap between what those two draft slots have
historically been worth is the edge.

**The survival bar** under the edge number is the chance he lasts to your next
pick. Teal is safe to wait on, red means gone.

**Tags** on the name line:

- `NEED` — the quality supply at that position won't cover what you still have
  to fill by your pick after next.
- `RUSH 8.9` — a top-8 quarterback who ran for that many fantasy points per game
  last year. Four or more is the bucket that hits.
- `POCKET` — a top-8 quarterback under two rushing points per game. Historically
  the worst early-round bet at the position.
- `N-1 9.3` — a top-6 tight end who missed 12 PPR points per game last season.

- `TIER THIN` — fewer players left in that tier than picks before your turn. It
  will not survive.
- `COMES BACK` — the tier is deep enough that someone from it returns to you.
  Take the scarce tier instead.
- `FIRST QB` / `FIRST TE` — nobody has taken one yet. Being first off the board
  at a onesie position risks paying a premium the room was never going to pay.

**The sliders** are Rank (how much the guide's board overrides raw ADP), MS
(how much Market Score divergence counts), and Bench (what a player who doesn't
crack your lineup is still worth). Defaults are .60 / .40 / .30.

The **Tier watch** panel shows every live tier's remaining count against your
pick gap, which is the guide's tiering rule as a running readout.

---

## Data sources

| What | Where | Notes |
|---|---|---|
| Players, drafts, picks, rosters | `api.sleeper.app/v1` | No auth, CORS-friendly, read-only. |
| Consensus ADP + stdev + byes | `fantasyfootballcalculator.com/api/v1/adp` | Pulled server-side in the Action. |
| Market values | `api.fantasycalc.com/values/current` | Carries `sleeperId`, so the join is exact. |
| Expected points, replacement level, tiers, Market Score | The guide | Curves and tables are in `docs/MODEL.md`; rankings you import. |
| Prior-season production | nflverse + DynastyProcess IDs | Weekly stats aggregated to per-game rates, joined on Sleeper ID. |

The board polls Sleeper every 3 seconds while the draft is live and stops when
the tab is hidden. Everything else is a static file.

---

## Not built yet

1. **Lineup optimizer** for the season, once weekly projections are wired in.
2. **Trade finder** — consolidation penalty plus an acceptance filter that ranks
   by `my_gain × their_perceived_gain`.
3. **Playoff odds** via Monte Carlo.
4. **Betting side** — see `docs/DATA.md` for the source plan.

## If something breaks

- **"No data files"** — the Action hasn't run or it failed. The log prints which
  source came back empty.
- **Everything shows "—" for ADP** — FFC may not have your format posted yet.
  The board falls back to market rank and still works.
- **Draft won't connect** — Sleeper doesn't create the draft object until the
  commissioner sets it up. Enter your slot by hand under Overrides meanwhile.
- **Names won't match** — the fixer dropdown writes straight to storage; once
  fixed, it stays fixed.
