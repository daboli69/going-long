# ABBEYS NFL score-method diagnostic

**Recommendation:** use the transparent current-season scoring average B as the provisional manual straight-up and exact-score method. Do not replace it with opponent-adjusted OLS C or a four-game recency window on the available evidence. Keep the production game/prop models unchanged. The proposed manual output is a score **point estimate** and a winner direction; no calibrated win probability, betting edge or exact-score likelihood has been established. The [registered protocol](PROTOCOL.md) was written before running [the diagnostic](diagnostic-20261003.json).

The checked-in `data/nfl_betting.json` is a 2026-10-03 ET nflreadpy-derived schedule snapshot (generation UTC 2026-10-04 00:38:53) with regular-season scores. It includes 49 completed 2026 games through Thursday of Week 4. It also contains historical and odds columns, but [diagnose.py](diagnose.py) selects only season, week, team IDs, kickoff and scores; forecasts always use the **same season**, earlier weeks and a 12-hour result-availability buffer. The registered portable SHA-256 normalizes only CRLF to LF before hashing; the original Windows-byte hash is retained separately in the protocol and diagnostic. Both hashes happen to match for this LF-ending snapshot. The snapshot lacks per-result publication timestamps and its exact upstream nflverse release ID, so this is a retrospective check, not a verified archived pregame feed. No network or credentialed source was called.

| Season, Weeks 4–18 | Paired games | B margin RMSE | C margin RMSE | B team-score RMSE | C team-score RMSE | B winner correct | C winner correct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 sanity | 224 | 13.25 | 14.14 | 9.35 | 10.05 | 156/224 | 150/224 |
| 2025 retrospective validation | 224 | 13.14 | 13.60 | 9.39 | 9.85 | 136/223 | 134/223 |

C's total RMSE also rose from 13.19 to 14.28 in 2024 and 13.42 to 14.24 in 2025. With the registered bootstrap seed `20261003`, the paired weekly interval for B-minus-C team-score RMSE was `[-1.22, -0.20]` in 2024 and `[-0.89, -0.06]` in 2025; negative favors B. The 2024 and 2025 margin intervals include zero, so no precise margin superiority claim follows. The 2024/25 samples are only two related seasons from a revised public source. OLS had full design rank and paired coverage for all 224 eligible games in each; poor results were not an early-week coverage artifact.

The exploratory four-game B variant had margin RMSE 13.65 in 2024 versus B's 13.25, and 13.03 in 2025 versus 13.14. It had higher team-score and total RMSE in both years. That mixed margin result does not support a recency adjustment for v1. The rounded exact-score pick matched 0/224 games for B in each year, which illustrates why it must not be presented as a likely exact outcome. The result is a descriptive count, not a reason to invent an exact-score probability.

The 2026 Week 4 schedule has 16/16 B-eligible and C-full-rank games based on completed Weeks 1–3 only. Its Thursday result was excluded from all Week 4 inputs and **no 2026 result was scored**. The future 2026 Weeks 5–18 holdout remains locked until at least January 16, 2027 at noon ET and after all Week 18 games finish. It needs genuinely saved pregame forecasts, not after-the-fact reconstructions. The current manual board implements B only; a B-versus-C prospective comparison remains **unimplemented** until C is independently frozen before each registered origin. A B-only capture is partial evidence and cannot satisfy the paired holdout gate. Thus this report recommends a manual B implementation, not model promotion or a claim of prospective validation.

For a user-facing cue, report `Limited evidence`, `Stable lean`, or `Sensitive lean` from the registered leave-one-prior-week-out check, alongside each team's input count. These are sensitivity labels only. Manual B can return a limited-evidence pick before each team has three games, using only the current-season league mean for a team without games; such picks are outside the paired validation sample. If the entire league has no completed current-season game, a lexical winner tie break must be labeled `No score evidence` and no numerical score should be shown. An exact-zero unrounded margin also uses a disclosed lexical tie break. If rounded scores tie despite a nonzero margin, the protocol chooses the nearest adjacent integer pair consistent with the winner, without claiming that one point is meaningful. Neutral-site status, weather, injuries and starting-quarterback changes are not captured by this score-only method.

Reproduce offline from the repository root with the existing Windows environment:

```powershell
& C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/.venv/Scripts/python.exe research/abbeys/diagnose.py
& C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/.venv/Scripts/python.exe -m unittest discover -s research/abbeys -p 'test_*.py'
```

The three tests verify that same-week score changes and 2024–25 score changes cannot alter 2026 forecasts. This research folder can be reverted independently; it does not alter an application route, production data file, scheduler or model parameter.
