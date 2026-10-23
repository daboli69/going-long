# NBA pregame context — 2026-10-23

Frozen before fitting. User authorized agent brainstorming and bounded implementation before tonight's games. Earliest tipoff16:00Eastern verified independently by ESPN and official NBA report. Stop new research by15:30, finish verification/archive before15:45; all save operations must independently reject started games. Local/$0/no keys/odds APIs/deployment/NFL changes. Original winner,score,individual and frozen forecast files remain untouched; new shadow revisions only. Owner: root model/UI/QA; agents own context_features.py and availability.py with separate fixtures.

## Evidence and fixed hypotheses

Existing features.py carries last5/10/20games across offseason unchanged; only Elo regresses,rest clips at10days. Thus prior-season form can enter October without age/continuity context. Existing efficiency estimates use different possession denominators for each side of a single game. These are concrete hypotheses,not proof that new forecasts improve. Current injury collector retains official links only; free ESPN summary.injuries and current team rosters offer exact athlete IDs and current statuses. They do not establish historical pregame availability or causal player impact.

H1 season continuity: original logistic C1,max_iter1000 plus one fixed feature group: home/away current-season released games capped20;days since latest released game capped180;prior-season share of last20released games;home-away differences of those three;home_margin20*prior_share minus away equivalent;home net-efficiency20*prior_share minus away equivalent. No hard reset or arbitrary shrinking of form. Net efficiency=ORtg20-DRtg20. Track timestamps/counts and unknown history.

H2 shared possessions: original logistic with its existing features plus two fixed differences—last20shared-denominator ORtg and DRtg. For each prior completed game,compute both sides' original possession estimates and take their mean only when both are positive/finite and boxes agree with final scores. That same denominator serves both teams. No invented missing possessions or unverified overtime normalization. Last20means count games,retaining unknowns rather than substituting unrelated games.

Every result/box is available strictly after tipoff+24h;opponent/season context is frozen at the target decision. No current-game outcomes or current roster backfill into historical rows. Native source statistics are revised historical data,not authentic pregame snapshots.

## Splits, budget and gate

Exactly2fixed logistic configurations,2target folds2024/2025:4base fits and4sigmoid calibrators,seed20261023. Train ending-seasons2016through target-2,calibrate target-1,evaluate target only. Reuse original saved logistic OOF predictions for identical2460game controls. No refitting original models,extra settings,ensemble selection or2026confirmation/current2026-27outcome selection. Reused development,not fresh independent validation.

Primary log loss;Brier/accuracy,reliability,per-season results secondary. Paired whole-game bootstrap2000draws;Bonferroni across2candidates,familywise95%intervals. Exploratory gate:>=1%relative LL reduction,corrected upper CI<0,both seasons improve,Brier no worse. Fixed early-season diagnostic subset=either team has fewer than10released current-season games;report it descriptively,never use it to select another setting or change thresholds. Stop after2candidates even if neither passes.

Freeze final config/result before operational refit. Archive both prespecified configurations for prospective comparison regardless of development result,each labelled with its gate result and no promotion. Operational refit uses available earlier completed games,last300calibration games including whole boundary tipoff block,and a strict24h embargo;same frozen logistic/feature groups. Record config/code/input hashes,training/calibration availability cutoffs,creation time. Do not silently replace the existing ensemble or claim a rejected configuration is recommended. No automatic selection on prospective results.

## Availability diagnostics,not numerical adjustment

Archive only filtered ESPN injury/team-roster fields with raw-response filtered-content SHA256,actual retrieval time,provider injury timestamp,team/game/athlete IDs and explicit missing/conflict states. Never retain/read summary odds or pickcenter as lines/features. Empty injury arrays do not mean healthy;unavailable/not-submitted/future-dated/inconsistent statuses stay unknown. Prefer exact IDs;no guessed name mapping. Read-only public sources,no login/PDF dependency or paid tracking.

For today's verified current roster,report share of last20released team-game positive finite player minutes belonging to currently rostered exact athlete IDs. Also show released current-season game count and known-out prior-minutes share. These are coverage/continuity diagnostics,not probabilities,causal absence effects or past-valid features. Missing current rosters mean unknown,not zero roster retention. New source snapshots append without overwriting;published-after-tipoff information cannot become a pregame snapshot.

## Verification and output

Leakage canaries: change own/future outcomes without changing own features;strict24h release;season boundary;missing/mismatched boxes. Availability fixtures: exact IDs,unknown empty responses,conflicting/future statuses,started games,valid minute denominators. Same sample IDs/outcomes versus original controls. Cache completed unchanged trials;log/skip failures,never weaken tests. Local app exposes risk/context panel and separate shadow probabilities with freshness/gate labels. Root trackers and report hold aggregate metadata only. Existing-launcher daily/manual refresh collects availability and appends frozen context shadows;never reruns research. No original model promotion or market superiority claim.

Primary references: https://www.nba.com/stats/help/glossary ; https://jr.nba.com/basictraditional-stats-vs-advanced-stats/ ; https://official.nba.com/nba-injury-report-2026-27-season ; https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/4/roster . A joint latent-strength graph is deferred to a separate protocol rather than added after results.
