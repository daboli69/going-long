# Current availability fallback

The October14 refresh had current Week6 roster bytes, but only15 nflverse injury
rows across2teams, no aware report clocks, and only9 qualifying NFLMeta club
game-status reports. A freshly downloaded file was not sufficient availability
evidence. Final weekly designations can be incomplete during the week.

The existing full-report path now requires complete NFLMeta coverage for every
playing club present in the current weekly roster. Partial club reports cannot
clear an entire league. If dated injury verification fails, the builder can read
ESPN's free public current injury endpoint. It is a capped list, so absence is
never clearance. Only explicit records matched by ESPN ID, normalized full name,
current roster team and current regular-season week enter a restricted scope.
Each player's actual report date must be within36hours; the endpoint's request
timestamp is ignored. Conflicting identities/designations, future clocks, stale
records and unmatched players cannot qualify. Unknown players stay excluded.

Both snapshots carry the identical `availability_verification` scope. JavaScript
and Python reject absent/inconsistent scopes and independently expire each
player. The roster and injury source clocks must still pass the existing36hour
checks. Known OUT/IR/suspended/doubtful reports remain exclusions; a less severe
fallback report cannot erase a more severe current-week nflverse designation.
More recent explicit reports can replace older records within the fallback feed.
The browser displays limited coverage instead of claiming every player is active.

Restricted snapshots use schema2 and leave the legacy injury source-clock field
null, with the real clock in `restricted_source_content_at` (injury snapshot) or
`restricted_source_injury_at` (roster). New engines validate both matching scopes
before using those clocks. Already-open older engines therefore fail freshness
and remain paused; they cannot silently ignore the restriction and clear everyone.
Reloading the site loads the new engine. No timestamp is synthesized or re-aged.

Responses are cached privately for30minutes so roster/injury builders share one
free request. No new paid API, threshold relaxation, synthetic timestamp, player
probability change or manual production freeze is introduced. The existing
workflow publishes validated components; failed components retain their prior
snapshots. Health diagnostics include the restricted scope's status/count.

Actual isolated October14 replay initially verified162player reports and cleared
72 of865 public historical profiles before market/sample/game filters. These
counts vary with dated updates and are not a promise of72 bet recommendations.
All other profiles remained excluded. Browser and Python decisions matched.
This replay used throwaway snapshots, not production writes; release readback
must separately verify the naturally generated artifacts and visible banner.

Primary source: https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries
Provider coverage guidance: https://nflmeta.org/api-docs/core-endpoints

Rollback: revert the availability repair commit as a unit, including both engine
mirrors and scope-producing builders. Do not leave new restricted snapshots in
use with an older engine that ignores their scope; restore paired prior snapshots
or keep availability paused during rollback.

## Released verification

PR22/code50135bd95d64b22b2d3f477b06c887368da26786 is deployed. Exact-code
CI38643644775 passed888Node and619Pythonrun(614pass,5existing skips), both
builds; dependency audit0. Natural refresh38643644513 published data commit
1209d064d6b301f4b6106bf59e5cc4f8f6e69ae5:167verified player reports,
74of865profile availability gates pass and69severe reports remain excluded.
Live JavaScript/Python profile decisions and repeat-refresh guards match; the
live banner displays limited coverage at1280/390px without overflow. Old engine
checks against the restricted contract clear0profiles. Independent review found
two release blockers that were repaired; follow-up independent approval was
unavailable due to reviewer usage limits. Root reproduced both fixes.

The overall refresh remains red solely because NFL props coverage is degraded
and incomplete. Injury/roster steps and publication integrity succeeded; this
release does not claim all odds providers are healthy or all players verified.
