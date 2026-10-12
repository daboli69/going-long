# Opportunity TD forward comparison

This is a separate research recorder, not a production model or betting recommendation.
The currently displayed probabilities and spread/total explanations remain unchanged.

`scripts/opportunity_shadow.py` consumes only existing public snapshots. It freezes the
opportunity formula, coefficients, production calibration and code hashes for 2026 weeks
6â€“10. The whole first week must still be future when the experiment begins; a missed
start cannot be backfilled. Each subsequent complete weekly slate is recorded before
its first kickoff. Files are sealed with SHA256 and published atomically without overwrite.

Each supported RB/WR/TE gets three predictions: actual production ATD probability,
fixed carry/target opportunity probability, and Beta(1,1) current-team TD frequency.
Features are current-season only and exact schedule/team identity is required. Prior
games must be completed with at least 12 hours since kickoff and confirmed offensive
participation. Fresh shared availability is required for the target week. OUT/unknown
players and unsupported/new starters are retained as exclusions, never filled with guesses.

The recorder retains complete appearance features, production model parameters,
availability source times, source-content hashes and observed statistics week. It does
not claim that a fresh build time proves upstream stat publication freshness: the
current producer does not supply that upstream clock. Goal-line/end-zone opportunities,
dated coverage/alignment, and matched two-sided sportsbook prices are absent and
explicitly reported; no arbitrary adjustments or market-edge claims are made.

The proposed gate requires at least 1,000 settled player-games and 60 games, paired
Brier gain >=.001 versus both production and simple frequency, clustered uncertainty
and nonworsening log loss. No intermediate-outcome retuning or automatic promotion.
Official scorer TD settlement must include special teams/defense/recovery categories;
passing TD alone does not credit the passer. Nonparticipants void, unknown outcomes
pending. Settlement/evaluation automation is a subsequent task and is not running.

Approved release workflow `.github/workflows/opportunity-shadow.yml` runs on Thursdays before
the opener, with optional manual retry before kickoff. It uses no paid calls or secrets
from providers and only publishes the research directory. Concurrency cannot replay
older snapshots onto advancing main. It activates on the approved main release; it does not fetch paid data or change predictions.

Current October12 offline snapshot validation correctly refuses capture: roster still
describes week5, while the target is week6. Existing history also lacks the newly added
per-game provenance until the next successful history build. No real cohort was invented
or frozen locally. First eligible capture depends on a fresh week6 roster/injury snapshot
and rebuilt history before the October15 weekly opener.

Rollback: revert the recorder/workflow commit; existing sealed research receipts should
remain unchanged. This version does not change any UI, Champion or numeric betting model.
