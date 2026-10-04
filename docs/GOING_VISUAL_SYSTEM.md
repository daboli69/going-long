# GOING visual system — approved references

## Source of truth
All approved PNGs in `docs/design-reference/` control appearance: the seven original images plus the seven October 4 additions (six unique screens). The newest approved reference governs an updated screen; earlier references remain authoritative elsewhere. Real application data, calculations, routes, accessibility and controls control functionality. Do not introduce a competing aesthetic or replace the interface with flattened mockups. The references are not evidence of model performance, live prices, supported markets or current player participation.

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
- Final measured pass: Evidence refresh actions and board/sport/window controls are now native disclosures, its model/policy panel uses two columns and compact coverage/price tiles retain actual metrics. Cheatsheets puts Filters beside the real sheet selector and removes redundant visible search-label spacing. Today has real-value summary icons and compact matchup headers. Evidence includes real Betting/Fantasy/Gateway route links in the shared bottom treatment. Header search now prioritizes the active football query and rejects hidden-view fields. No global numerical similarity claim is made.
- Remaining geometric differences are explicit: football references use varying header/hero treatments; the shared functional header and 44px tool/action targets increase Cheatsheets' vertical offset compared with its illustrative small controls. Score cards retain genuine evidence/market text, actual supported selectors and keyboard disclosures. Evidence keeps a collapsed Filters row, its real Results tab and actual tracked-selection/coverage definitions rather than copying unavailable mockup metrics. Original art and unknown font identity prevent literal pixel equality; further refinements must use measured comparisons, not a new aesthetic.
- Native phone status/battery chrome is not faked. Generic original artwork replaces the mockup's branded athlete imagery; crop/light/composition are comparable, not identical.
- Actual values, available Score markets, evidence text and timestamps replace examples. No fake team records, extra Score markets, validated-edge labels or real-time claims. NCAA retains its existing game-only functionality and fewer supported tools.
-44px minimum action targets, longer real evidence, missing-data states and required freshness warnings can exceed illustrative reference heights. Card actions sit within native disclosures; no information is silently removed. Score's league/tool context is collapsible for compactness.
- Exact typeface and branded shield icons are not assumed licensed; locally licensed display font and real SVG/ existing team badges are used. No99.9% similarity score is claimed: dynamic data and original artwork make a global pixel percentage misleading.
- Continue only measured refinements under this visual contract; never alter probability, Confidence, Score, DFS, Champion/C1/C2 or prospective collection to match mockup values.

## October 4 reference extension

| New approved filename suffix | Screen | Exact comparison viewport |
| --- | --- | --- |
| `10_34_33 AM.png` | NFL Jackpot | 1536×1024 |
| `10_34_46 AM.png` | NFL Parlays | 1536×1024 |
| `10_34_55 AM.png` | NFL Today | 1024×1536 |
| `10_35_04 AM.png` | Best Plays, the existing Today ranking view | 1024×1536 |
| `10_35_28 AM.png` | NFL DFS | 1536×1024 |
| `10_35_45 AM.png` | NFL Games | 1536×1024 |
| `10_35_53 AM.png` | Byte-identical duplicate of Parlays | 1536×1024 |

All seven originals were copied byte-for-byte, with no uncertain page mappings. This extension is scoped to Today/Best Plays, Games, DFS, Parlays and Jackpot. Home, Cheatsheets, GOING Score and Evidence retain their earlier treatment. `shared/reference-workspace.css` and `.js` add presentation adapters, loaded only in the football workspace. They relocate the same native controls rather than replacing their event delegates or calculations. Best Plays remains Today’s eligible-candidate list with its original order/settings; the existing GOING Score destination is retained because it has a separate documented meaning.

Measured extension tokens: background `#010d14`, surface `#01121c`, border `#194458`, muted `#9abccb`, teal `#00e4d0`; restrained inset teal active glow, 6–9px radii, 8/12/16px principal gaps. Locally licensed Archivo Black remains the closest available broad italic display font; Inter remains the body font. Shared header at desktop is 54px; tablet Today uses 50px. Desktop tool row is 52px; phone tools remain a three-column grid with 47px controls. NFL/NCAA active segments respond to actual league state.

Artwork: `shared/reference-helmet.webp`, 30,400 bytes, is an artwork-only crop `(796,64,1437,207)` from the user-approved `10_35_45 AM.png`. It contains the generic helmet/light composition and no UI, names, statistics or controls. This uses the supplied approved artwork; no outside player photography, generation API or paid service was used. Full reference PNGs are documentation, excluded from the deployed runtime tree.

### Measured comparison and corrections
Baseline production screenshots were captured before edits. Each unique reference then underwent multiple built-page render/screenshot comparisons; all six final screenshots have aligned side-by-side, 50% overlay and raw difference artifacts. Raw RGB differences include real-data text and unsupported mockup metrics, so they are diagnostic, not a claimed 99.9% accuracy score. Browser DOM bounds were checked independently of the images.

- Removed the inherited 1160px content cap and 55px relative header offset. Games now uses x96/1344px width, hero y63/146px height, tools y217/52px, workspace y443 versus reference y439. Its real period markets and original Compare books dialog remain available.
- DFS now uses x38/1460px width, hero y63/146px, workspace y332.5 versus reference y329; columns retain actual CSV import, objective and nine-slot roster. Compact import instructions/paste entry are expandable; file controls are not clipped.
- Parlays uses the reference’s centered x242/1052px hero at y55/138px; x131/1274px three-column workspace starts y336 versus reference y344. Original checked games, settings, build/remove/swap and actual draft evidence remain authoritative.
- Jackpot uses x38/1460px hero at y63/204px, tools y279/52px and two-column workspace y453 versus reference y455. Its scorer search filters displayed rows only. Separate first/last/longest/anytime tools remain accessible; no joint jackpot probability is created.
- Today’s 1024px hero uses x32/960px width, y115/181px, matching the reference’s vertical position. Secondary controls previously displaced the slate by about390px; native disclosures now retain them below the cards. Final matchup area was measured around y667 versus reference y655 before the final heading/font refinement.
- Best Plays uses x18/988px hero, 694px candidate column and x730/276px sidebar. First cards start around y377 versus reference y360; the longer real evidence and explicit risk disclosure increase individual card height. Fixed native details-content grid behavior so the sidebar sits beside candidates; actual projection/probability/odds/estimated-return strings and original action buttons are reused.

### Honest differences from the new references
Games has actual quotes/model means/book coverage, not example records, weather, universal team GOING Scores, public-betting percentages or a fabricated scoring histogram. Its original period tables remain under a native disclosure. Today keeps actual research counts and lead-candidate caveats; unsupported live weather/movement, calibrated confidence and team scores are not invented. Best Plays does not copy “highest-value/no research required,” historical hit rate/ROI or a fictitious performance curve; evidence confidence is not a probability. Real text, available filters and native disclosure controls can require taller cards.

DFS displays the real empty-import state when no official salary file is supplied; no example salaries, kicker or fake projections are copied. The Classic roster and $50,000 cap remain unchanged. Parlays displays the actual current leg count and qualified existing probability/price explanation, not mock hit-rate/ROI or guessed correlation. Jackpot presents the already-published first-TD field without multiplying first/last/longest estimates; model break-even odds are explicitly distinct from sportsbook quotes. Specialized original tools remain expandable. Unsupported example metrics have honest unavailable/evidence text, while preserving their surface hierarchy.

Phone verification covers all six screens at430/393/390/375/360/320px: zero horizontal page overflow after correcting long matchup team names and Jackpot title/subtitle clipping. Hero height adapts where real phone text needs room. Desktop1536px and tablet1024px checks include real data, empty DFS, empty search, league state, native comparison/Confidence controls and retained Score/Cheatsheets navigation. Reduced motion, native keyboard disclosures and existing bottom modes remain intact. Existing model, DFS, ABBEYS, 2+TD and ranking source/protocol files are untouched.
