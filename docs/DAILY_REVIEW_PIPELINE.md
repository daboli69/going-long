# Daily Codex-to-Claude review pipeline

Repository: `https://github.com/daboli69/going-long.git`.
Automation-owned branch: `codex/going-long-daily-review`; isolated checkout.
Bootstrap base: `7d33e75b7eea05a52845a9fa02c203d850512da9`. One initial bootstrap push authorized; automatic/further pushes remain disabled pending separate approval.

## Gates before every authorized publication
1. Require clean isolated checkout, sole writer, correct origin and expected remote review tip. Fetch before later cycles; stop if another writer advanced it. No automatic merges/rebases/resets, force pushes or conflict resolution.
2. Verify the FIRST and every later outgoing tree retains `git.deploymentEnabled["codex/going-long-daily-review"] = false`, without overlapping true rules or alternate Vercel configuration. No manual CLI/dashboard/hook deployment. Current preflight: connected project/root verified, no hooks/integrations or repository webhooks; external changes invalidate that snapshot.
3. Stage explicit cycle-owned paths and inspect EVERY outgoing commit/file. No unrelated user work, credentials/private files, incomplete experiments or unapproved application fixes. Do not publish accumulated development history wholesale.
4. Test the exact code/config tree; record meaningful checks, limitations and rollback in concise trackers. Keep incomplete/failed cycles local. Stop if $0 included capacity cannot be established; public standard Ubuntu Actions minutes free, no new paid runner/storage configuration.
5. Push only the verified completion SHA to the exact review ref after authorization. No main, tags, all-branch pushes, merge, PR creation, deploy or reviewer messages. Require ordinary fast-forward updates; fail closed on remote divergence. Verify remote SHA before claiming publication. First creation must refuse an already-existing review ref.

## Cycle and reviewer contract
- Keep existing 10 AM Eastern heartbeat, at most one issue and 15 minutes active work; default one relevant role, maximum three agents total. Reuse findings, focused reads/tests, no duplicate work without valuable validation; stop when no meaningful work exists. All AGENTS.md cost/safety/approval/model gates apply.
- Update PROGRESS.md only for meaningful changes; MODEL_RESEARCH.md only for meaningful hypotheses/evidence/tests/results/status. Record cycle ID and previous completed/base SHA; no fabricated validation or promotion.
- Final subject: `cycle complete: <ID>`. Get its final SHA from Git/publication report; don't embed a commit's own SHA inside itself. Claude explicitly fetches the review branch, records the newest marker's SHA and reviews against the recorded base.
- Claude reviews read-only with existing included capacity. Initial bootstrap includes no application fixes; future transfer and publication require separate approval. The existing heartbeat is not retargeted or changed by this bootstrap.

References: [Vercel Git deployment controls](https://vercel.com/docs/project-configuration/git-configuration), [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
