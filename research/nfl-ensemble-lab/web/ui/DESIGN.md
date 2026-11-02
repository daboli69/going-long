# Game Center design direction

**Direction: a broadcast scorebug set like a printed ledger.** The app is read the way a bettor or fan reads a stat sheet: scan for one big number, then drop into dense rows. So the screen has one dominant figure per view and ruled rows beneath it, not a wall of equal boxes.

**Palette (three tones).**
- Charcoal ground: `bg #16181b`, raised panel `#1f2226`, deepest well `#0e0f11`.
- Off-white type: `#f2f2f0`, with `muted #a9adb3` for labels (7:1 on the panel).
- One yellow, `#ffcf3f`, for the active state, focus and warnings. Team colours appear only as solid fields on the scorebug.
- Red and green are status, not decoration: the Right and Wrong badges only, always with the word.

**Type.** Bahnschrift (the DIN family that ships with Windows, the only place this local app runs). Hierarchy has four steps: the figure (large, condensed width, bold), the row value (20px bold), body (15px), and labels (13px muted). Numerals are tabular and right-aligned in tables. The figure uses Bahnschrift's width axis to run condensed, as scoreboard digits do.

**Layout.** Sports-data convention: dense tabular rows with hairline rules, one headline figure, definitions in a ledger beside it. No rounded card grids. Surfaces are flat and square and separated by tone steps.

**Motion** (the `motion` package, 160 to 400 ms, ease-out).
- Panel content rises 6px and fades in when a tab opens.
- Live numbers count to their new value rather than jumping.
- Everything respects the reduced-motion setting.

**Checks.** `npm run audit` renders the app headlessly at desktop and phone width, interacts with the tabs, records horizontal overflow, console errors and layout shift, and writes screenshots to `test-results/audit/` for review.
