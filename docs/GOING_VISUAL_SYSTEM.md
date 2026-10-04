# GOING visual system — approved references

## Source of truth
The seven original PNGs in `docs/design-reference/` control appearance. Real application data, calculations, routes, accessibility and controls control functionality. Do not introduce a competing aesthetic or replace the interface with flattened mockups. The references are not evidence of model performance, live prices, supported markets or current player participation.

## Reference measurements and discrepancy inventory
- Five page references (02 NFL Today,03 Home,04 Cheatsheets,05 GOING Score,06 Evidence):852×1846px. Interpret as426×923 CSS pixels at2×; the phone status bar drawn into the mockup is not webpage content. The two overview boards (`example mock.png`,`large app mock.png`) are1536×1024px.
- Today measured reference regions: hero431–726px (~147.5 CSS px); nine-tool grid737–1020px (~141.5 CSS px); five-item global navigation193–300px (~53.5 CSS px). Actual final426px layout:147px hero,142px tool grid,49px navigation,110px complete shared header. Mockup phone chrome accounts for about43px of vertical offset.
- Prior production discrepancies: plain header and small tabs; no atmospheric heroes; different card colors/typography; long controls preceding useful content; oversized role/Score cards; fixed mobile overflow risks. These were addressed with shared primitives and measured overrides.
- Comparison corrections: remove More's extra grid row, remove date/explanation overlap, fix375px header overflow, keep Home nav flex widths, override inherited two-column Score facts, correct inherited Evidence nav letter-spacing, compact matchup and Score actions into their existing native disclosures. Native controls and their listeners are preserved.

## Tokens and typography
Sampled/derived palette: background#030e18, surface#0b1924, raised#122a3a, border#294b60, text#f4f8fc, secondary#b4cbdc, teal#35edcb, blue#25bdf1, coral#ff8185, amber#ffb85c, purple#d269ee. Radius:9px controls/tiles,10–12px cards;5–10px compact gaps. Use restrained active teal glow, not animated decoration.
Titles: locally bundled Archivo Black under SIL OFL (license alongside font), rendered italic for the approved broad display treatment. The exact reference typeface is not established. Body: existing Inter with system sans-serif fallbacks. Score rings remain real CSS conic gradients; metrics remain actual values.

## Shared implementation
`shared/visual-system.css` and `.js`: shared header/search/status/menu; real SVG icons; active global navigation; real NFL/NCAA switch; three-column football tools; page heroes; three summary tiles; fixed mode navigation. Native More and Score tool disclosures remain keyboard operable. Header actions reveal enclosing disclosures before focus. Score context moves existing DOM controls, preserving identity, values and listeners.
`shared/visual-pages.css`: Home football/baseball cards, hero, actual route actions and evidence entry; public research results treatment.
`shared/visual-research-cards.css`: compact role metrics/progress bars, Score rank strips/rings/facts and desktop grids. Existing supported Score markets only.
`apps/validation/style.css` and presentation in`src.jsx`: Evidence hero, model/version/coverage sections and real evidence-view controls; calculations, records, settlement and optional auth unchanged.

## Artwork provenance/performance
Original generic football helmet/player/stadium and baseball artwork generated in this manual session with the included built-in image-generation capability. No player photography, recognizable athlete, league/team marks, fake UI, statistics or names in artwork. Prompts specified subject on right, empty dark left, teal stadium light for football and warm orange light for baseball.1536×1024 source PNGs converted to WebP quality86 without compositing UI. Runtime assets:football-hero.webp165,184bytes; baseball-card.webp156,084bytes. No paid API, secret, new subscription or hosting change.

## Responsive and functional fidelity
Phone checks:320,375,390,393 and426px; desktop1280px. Preserve real search, filters, expanded evidence, routes, date/game selections, NFL/NCAA distinction and fixed Betting/Fantasy/Gateway actions. At desktop, use wider heroes and column layouts rather than stretching a phone card. Decorative work is CSS/SVG; no decorative animation loop. Respect reduced motion and visible keyboard focus.

## Completed presentation migrations
Home; NFL/NCAA Today; Cheatsheets; GOING Score; public Evidence/results; shared football tools (Markets,Games,DFS,Parlays,Jackpot,More). DFS optimizer/data/controls are untouched and inherit the same surfaces, typography and header. Going Yard's calculations/content remain untouched; shared platform header still links to it. Basketball remains informational only.

## Intentional differences and remaining fidelity work
- Publication and final fidelity acceptance are pending. The initial implementation is locally tested; it is not a claim that all reference discrepancies are minor. Evidence still has extra refresh/filter rows above the model controls, and Cheatsheets has more vertical spacing before its first role card. Reduce those through accessible progressive disclosure and measured geometry before final acceptance. Today's summary tiles lack the reference's leading icon treatment, and matchup cards need further density/crop refinement. These are outstanding refinements, not unavoidable constraints.
- Native phone status/battery chrome is not faked. Generic original artwork replaces the mockup's branded athlete imagery; crop/light/composition are comparable, not identical.
- Actual values, available Score markets, evidence text and timestamps replace examples. No fake team records, extra Score markets, validated-edge labels or real-time claims. NCAA retains its existing game-only functionality and fewer supported tools.
-44px minimum action targets, longer real evidence, missing-data states and required freshness warnings can exceed illustrative reference heights. Card actions sit within native disclosures; no information is silently removed. Score's league/tool context is collapsible for compactness.
- Exact typeface and branded shield icons are not assumed licensed; locally licensed display font and real SVG/ existing team badges are used. No99.9% similarity score is claimed: dynamic data and original artwork make a global pixel percentage misleading.
- Continue only measured refinements under this visual contract; never alter probability, Confidence, Score, DFS, Champion/C1/C2 or prospective collection to match mockup values.
