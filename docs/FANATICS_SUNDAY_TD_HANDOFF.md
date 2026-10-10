# Fanatics Sunday TD (Jackpot section): handoff

Owner: Claude (feature engineer). Reviewer/integrator: Codex. Nothing here was pushed, merged or deployed.

## 1. Branch and commit
- Branch `claude/fanatics-sunday-td`, worktree `C:\Users\travi\OneDrive\Documents\ChatGPT\GOING-claude-fanatics-td`.
- Baseline `origin/main` at `3f2651e` (data refresh on top of `6716bc8`). Codex's `codex/going-takeover` (c9cccd6 when inspected, read-only) was not touched; no Codex work was cherry-picked.
- Feature commit: see `git log --oneline -3` on the branch (the commit titled "Fanatics Sunday TD engine and Jackpot view"); the follow-up docs commit records its SHA below.
- Feature commit SHA: FILLED-IN-BY-FOLLOWUP-COMMIT

## 2. Files changed
New (all Claude-owned, standalone):
- `shared/fanatics-td.js`: selection engine (pure logic).
- `shared/fanatics-td-terms.js`: promotion terms with a verification status per rule (served to the browser; `config/` is not deployed).
- `shared/fanatics-td-ui.js`: leg building and presentation (renders into `#promoOptions`, writes `#promoStatus`).
- `shared/fanatics-td.css`: styles (single column, mobile rules).
- `tests/fanatics-td.test.cjs` (engine, 15 tests) and `tests/fanatics-td-ui.test.cjs` (UI and integration, 11 tests).
- `docs/FANATICS_SUNDAY_TD_HANDOFF.md`.
Modified (one shared file, localized): `index.html`
1. one `<link>` and three `<script>` tags added right after `touchdown-promo.js` (line ~539);
2. in `renderPromo()`: the `await PROMO_AUTO.pending` is wrapped so a roster-screen outage no longer aborts the view when the new UI exists, and a single `if(globalThis.GoingFanaticsTDUI){...GoingFanaticsTDUI.render(...);return;}` block is inserted right after `const info=PROMO_AUTO.availability;`.
The previous engine (`shared/touchdown-promo.js`, `GoingTouchdown.optimize`) and the rest of `renderPromo()` are untouched and remain the fallback if the new scripts fail to load.

## 3. Architecture
`renderPromo()` -> `GoingFanaticsTDUI.render(host, ctx)` -> `buildLegs(ctx, manualPrices)` -> `GoingFanaticsTD.select(legs, {terms})` -> cards.
- `ctx` supplied by the page: `now`, `slateDate`, `props` (BET.props), `currentWeekProp`, `probability(p)` (= `propProbabilities(p).over`, the existing model), `availability` (the existing `/api/promo-availability` ESPN roster screen, null when older than 10 minutes), `eligibility(id)` (returns `bettingEligibility().decide(id,{team,lastGame,requireRecentGame:false,hasGame:true})`), `profiles`, `resolveTeam`, `statusEl`, `termsOverride` (from the existing `#promoFloor` / `#promoLegFloor` inputs), `onChange`.
- A player becomes a leg only with: a real Fanatics price (feed quote with `bookKey==='fanatics'`, or a price the user typed from the Fanatics app, kept in this browser only and expiring after 120 minutes), a model probability strictly between 0 and 1 and at most 0.60 (reliability ceiling, see section 6), a game that has not started, a quote younger than 15 minutes (feed), availability `active|expected` from the roster screen, AND `eligibility.actionable===true` from the shared eligibility decision. Missing or null on any of these excludes the player with a counted reason. Both availability checks are required (defence in depth).
- Other sportsbooks' prices are never used. The other-book anytime-TD rows are used only to find players, games and the (book-independent) model probability.

## 4. Verified promotion terms (what could and could not be verified)
Official Fanatics rules could NOT be retrieved: `sportsbook.fanatics.com/promotions` returned HTTP 404 and no official terms page was found. Two public pages were read:
- Fanatics marketing blog (not the rules): "NFL Jackpots": anytime-touchdown-scorer parlay "containing at least three legs at odds of +2000 or longer, with a minimum stake of $5"; automatic entry; jackpot up to $250,000 FanCash shared among qualifying winners; entries before the 1:00 PM ET Sunday deadline. It does not say whether +2000 is the combined or per-leg price, whether legs must be different games, any entry limit, or Ohio.
- Third-party promotions summary (cites no official link): three-leg parlay of different players from three different games, +2000 or longer, $5+ cash, max 5 entries per Sunday, equal split among winning entries, $200k base / $250k on select Sundays, Sundays 2026-09-13 to 2026-10-25, a voided/Fair Play leg disqualifies, 21+ in "an eligible state" (Ohio not named).
`shared/fanatics-td-terms.js` records each rule as `verified-secondary` (stated by those pages; never "official"), `user-supplied`, `conflicting` or `unverified`; the Jackpot view shows this panel and every slip carries "UNVERIFIED OFFER RULES". GOING does not claim the user qualifies.

## 5. Unverified, user-supplied settings
Ohio eligibility; "exactly 3" (the blog says at least three); +2000 as the combined price; entry limit; whether several different slips are allowed; whether a leg from a later game is allowed given the 1:00 PM ET lock; voided-leg handling; whether the promotion runs on the chosen Sunday; whether the user's account is directly offered. All are configurable inputs or displayed warnings, not enforced assumptions.

## 6. Probability methodology
Per-leg probability = the existing GOING anytime-TD model (`propProbabilities(p).over`; Champion v2 blend with the TD mean correction applied at build time). Joint estimate = P(A)xP(B)xP(C), an independence approximation justified only because the default view requires three different games. It is a model estimate, not a hit rate. Known limitation (independent TD validation 2026-10-10): TD probabilities have a calibration slope of about 0.7 (high values overstated, low understated), so the joint estimate of high-probability legs is likely too high. The engine does not add a correction (none was validated for Sunday); it excludes any leg above 0.60 as outside the reliable range (configurable `maxLegProbability`; an independent reviewer found a 28% headline built from 60-70% legs misleading) and words the headline as a likely-overstated model estimate. The highest-probability slip is not the highest-value slip (a likelier slip pays less); no prize value is assumed and no betting edge is claimed.

## 7. Odds methodology
American -> decimal: +A -> 1+A/100; -A -> 1+100/A (valid only when |odds|>=100). Combined decimal = product of the three decimals. A slip qualifies iff combined decimal >= decimal(+2000)=21.00 using full precision (only a 1e-9 float tolerance); the displayed American (rounded) is never used to qualify (tests cover prices that round to +2000 but are 20.997). Combined American = (d-1)x100 for d>=2, else -100/(d-1). Search: legs sorted by probability, branch-and-bound on the best possible third leg (p_i x p_j x p_(j+1)) with a top-K list, exactly equal to brute force (property test over 30 random pools). Results are deterministic (probability desc, lower payout, then key). Fewer than five valid slips are shown as is with a reason; the list is never padded. Optional diversification (cap per player) exists in the engine but is OFF by default so the five shown are the five highest-ranked distinct slips.

## 8. Tests
- `node --test tests/fanatics-td.test.cjs tests/fanatics-td-ui.test.cjs`: 32 tests, all passing: odds conversion, exact 21.00 threshold and rounding trap, exactly three distinct players/games, duplicate players and combinations, ranking order and joint product, brute-force equivalence, insufficient combinations, missing/other-book/stale/expired/invalid prices, unavailable/unknown/bye/unverified eligibility (null eligibility fails safe), started games, invalid model inputs, terms validation, manual price parsing, rendering states (results, no prices, stale, failed eligibility, model error), manual price flow, HTML escaping, terms panel honesty, Jackpot integration hooks, mobile CSS rules.
- Full Node suite in the worktree: 619 passing before the UI tests were added (all existing tests, including the today-ranking hash test, pass; the change touches no hashed function).
- Browser check (local server, real `index.html`, real data): the promo panel shows "NO FANATICS PRICES" because the feed has none; with a stubbed healthy roster screen and typed prices, five valid slips rendered from real model probabilities and the real eligibility engine; no horizontal overflow at 375 px.
- Not run: Python suite (no Python changes), Vercel build.

## 9. Known limitations
- **No Fanatics anytime-TD prices exist in the current feed** (`data/nfl_betting.json` has 113 Fanatics rows, all receptions; the 503 props outage truncates the feed). Until Fanatics TD prices arrive, the view shows an unavailable state and the user must type Fanatics prices (manual entry, clearly labelled "entered by you"). No other book is substituted.
- The roster screen (ESPN) and GOING eligibility are research filters, not official game-day clearance; inactives come about 90 minutes before kickoff.
- The 1:00 PM ET lock and whether later-game legs are allowed are unverified.
- TD probability calibration (slope about 0.7) is not corrected.
- The engine builds exactly three legs; slips with more legs are not generated.
- Manual prices live in localStorage on one device.

## 10. Required integration steps (for Codex)
1. Merge `claude/fanatics-sunday-td` (or cherry-pick the feature commit) into the takeover branch; add the new files; apply the `index.html` hunks above (script tags; `renderPromo` try/catch + hook block).
2. Confirm `bettingEligibility()` still returns an object with `decide(id,{team,lastGame,requireRecentGame,hasGame})` -> `{actionable,state,label,caution}`; if the eligibility engine's contract changes, edit only the `eligibility:` adapter in the hook (one line).
3. Keep `shared/` listed in the Vercel build (it is copied wholesale). No server, workflow or config change is required.
4. Run `node --test tests/fanatics-td.test.cjs tests/fanatics-td-ui.test.cjs` and the full suite.
5. If Codex's feed starts carrying Fanatics `atd` rows (`bookKey: 'fanatics'`, `market: 'atd'`, `overOdds`), slips appear automatically.

## 11. Potential merge conflicts
`index.html` only. Codex's branch changes `index.html` in the eligibility/DFS/score regions (`bettingEligibility`, `markUnavailableProps`, `dfsPlayerPool`, `renderGoingScore`); this feature touches the script-tag line (~539) and `renderPromo()`, which Codex's diff does not touch (checked read-only against c9cccd6). The line-539 `<script>` row is long, so a textual conflict is possible if Codex adds scripts to that same line.

## 12. Dependencies on Codex's unfinished work
Only the documented `GoingEligibility` decision interface through `bettingEligibility()`, and the existing `/api/promo-availability` and `BET.props` shapes. The feature fails safe (no slips) if either is missing. No change to eligibility, refresh, freeze, DFS, deployment or model code was made.

## 13. Independent review (2026-10-10) and what changed
A separate reviewer (own brute force, 400+ random pools, real data, real index.html in a browser) found no invalid combination and no unavailable/bye/unknown player in any generated slip; 100,000 random odds round-trips were exact; the 21.00 boundary held at full precision. Findings fixed in this branch: (P1) typed prices and the open panel were wiped by the page's 60-second re-render and the 2-minute availability refresh blanking `#promoOptions`: the UI now keeps typed text, panel state and parse messages, never rebuilds under a focused textarea, and the hook no longer blanks the panel; (P1) the bold headline overstated the joint chance: reliability ceiling lowered from 0.85 to 0.60 and the wording changed; (P2) a null team resolving equal to another null (guarded), a stale feed quote hiding a fresh typed price (freshest in-limit price now wins), "qualifying"/"clears by N%" wording (now "meeting the combined-price test"), a later-game caveat on slips with a game after 1:00 PM ET (a 1:00 PM kickoff itself is not flagged), the empty-props message, and a 600-leg pool cap (a 2,000-leg pool took 35 s; 300 legs takes ~0.1 s).
