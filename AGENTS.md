# Going Long visual system

The approved images in `docs/design-reference/` are the visual source of truth for Going Long. UI work must preserve near-pixel visual fidelity and reuse the shared design system documented in `docs/GOING_VISUAL_SYSTEM.md`. Do not introduce competing visual styles without explicit Travis approval. Real data, accessibility, routing and existing model/research gates remain authoritative; never replace controls or data with a flattened mockup.

ABBEYS is a separate NFL current-season-only straight-up board; follow `docs/ABBEYS.md` and its frozen research protocol. Keep prior seasons, sportsbook data and historical context outside its prediction boundary. Never rewrite official journal observations or v1 model/protocol definitions after freeze; append outcomes/integrity evidence separately. Preserve all existing models and prospective ranking policies. New versions require preregistration and existing model-promotion approval gates; scheduled cycles retain their existing limits and publication rules.

## Process safety (all agents)

- Never use broad process-kill commands: `taskkill /IM node.exe`, `pkill`, `killall`, `Stop-Process -Name ...`, or anything that matches processes by image name or pattern across the machine. Node, Python and other processes on this host belong to other tools and sessions.
- Terminate only a process you started yourself and can identify by its specific PID: record the PID when you launch it, verify it in the process list, then stop that PID alone. If you cannot identify your process by PID, leave it running and report it.
- Prefer finite commands with timeouts over long-running servers. If you must start a server, start it from your own directory, note the PID, and stop that exact PID when done.
