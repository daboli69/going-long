# Daily review pipeline (prepared; publication disabled)

Target: `daboli69/going-long`, branch `codex/going-long-daily-review`.
Existing 10 AM Eastern heartbeat, $0 spending and all AGENTS.md gates remain unchanged.
No remote branch or push authorization exists from this preparation request.

## Deployment and CI prerequisites
- Include the exact branch exclusion in `vercel.json` in the FIRST published tree and every later tree. `git.deploymentEnabled` disables Git-triggered deployments for this branch. Never add an overlapping true rule. This does not authorize CLI, dashboard, deploy-hook or other manual deployments.
- Current root configuration is the expected Vercel configuration; confirm connected project/root/production-branch settings and absence of separate deployment hooks before first publication. Local checks cannot verify dashboard configuration or all external integrations. Stop if uncertain; no project-setting changes without approval.
- Validation workflow triggers on code/config/test pushes to any branch (path-filtered) and PRs. Standard `ubuntu-latest`, read-only token, no deploy step; public-repo runner minutes are free. Docs-only pushes need local checks because they may skip CI.
- Data refresh may receive a matching push event, but its sole job requires `refs/heads/main`; it cannot refresh or commit from the review branch.
- Existing npm/pip caches remain; no uploads, new runners or paid storage enabled. Account cache/billing settings were not audited. Recheck visibility and free capacity before enabling publication; stop if $0 cannot be established.

## Isolation and publication (requires separate authorization)
1. Approve a baseline and explicit initial commit list. Do not publish the current development branch wholesale; it contains setup, fixes and reviewer/user documentation. Prepare a separate automation-owned checkout from the approved base, with no credentials copied.
2. One writer only. Fetch the exact remote review branch before each cycle. Require a clean checkout and the expected remote tip; if another writer advanced it, stop. No automatic merge, rebase, reset, conflict resolution or force push.
3. Stage explicit cycle-owned paths. Review the full outgoing commit range for unrelated files, secrets and unapproved work. Confirm deployment exclusion, workflow safety and $0 prerequisites in the final outgoing tree.
4. Complete relevant tests on the exact code/config tree; record checks and limitations. Commit only completed work and its concise tracker updates. Incomplete or failed cycles remain local. Never push a bare HEAD merely because the working tree is clean.
5. Only after authorization: publish an explicitly verified commit SHA to the exact remote review ref using a normal fast-forward push. Never push main, tags, all branches or PRs automatically. Refuse non-fast-forward changes. Failed push means local result only; do not claim Claude can see it.

## Claude handoff
- Record cycle ID, previous completed/base SHA, changed files, test results and remaining work in PROGRESS.md; MODEL_RESEARCH.md changes only with meaningful research evidence.
- Final commit subject: `cycle complete: <UTC timestamp ID>`. Avoid a self-referential SHA inside that commit. The actual final SHA is obtained from Git and supplied in the publication report.
- Claude fetches the explicit review branch, finds its newest completed-cycle marker, records that exact SHA and reviews the range from the recorded base. Branch default/main or latest timestamp alone is not a completion signal.
- Cloud review remains read-only; no automatic messages, review service activation or extra usage purchases. Repository access and existing included Claude capacity must be confirmed by Travis. Later merging/deployment/model promotion retain separate approval gates.

References: [Vercel branch deployment controls](https://vercel.com/docs/project-configuration/git-configuration), [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
