# Research ledger and backlog

Generated from `research_ledger.json`. Score = gap x share x P(detect within 2 seasons) / cost hours x 10^4.

Q14-QB is pinned first by construction of Phase 14 (pre-registered); all other items are ranked by score. By raw score, P11-BLEND is higher because it is cheap and already running.

| Rank | ID | Hypothesis | Status | Score | Gap targeted | Games to detect | Cost (h) | Kill rule |
|---|---|---|---|---|---|---|---|---|
| 1 | Q14-QB | QB value adjustment for starter changes (Phase 14) | prospective monitor (M6); Q1 passed r=0.22, Q2 failed p=0.074 | 5.13 | 0.032 | 1222 | 6 | kill if M6 e-value < 1/20 after 100 QB-change games or r < 0.2 on prospective games |
| 2 | P11-BLEND | Champion + opening-line blend (Phase 11) | prospective shadow, 0/128 | 20.26 | 0.011 | 1964 | 2 | fixed rule at 128 games; kill if paired CI excludes improvement |
| 3 | LATE-NEWS | Information-arrival timing: practice reports and inactives (Phase 14 events) | descriptive, ongoing | 4.05 | 0.011 | 1964 | 10 | kill if after 200 events mean absolute 24h move is not above the random-time move |
| 4 | S2P | Line movement toward the underdog flag (Phase 8.4) | prospective, 26/128 | 3.91 | 0.011 | 8538 | 1 | fixed rule at 128 games |
| 5 | P5-P7 | Registered challengers p5_player_continuity, p7_qb_snap | prospective, 26/128 | 1.59 | 0.002 | 59403 | 1 | Phase 3 rule at 128 games |
| 6 | PRACTICE | Wed/Thu/Fri practice participation of top starters as early injury signal | backlog (not registered) | 1.03 | 0.007 | 7028 | 8 | pre-register before testing; kill if line-move corr < 0.1 on 618 games |
| 7 | PROPS-V2 | Props simulator v2 vs v1 (CRPS) | prospective, archive needs weekly runs | 0 | None |  | 2 | v2 pre-registration rule |
| 8 | K-13 | Kalman market-anchored ratings (Phase 13) | killed: equals the opener | 0 | 0.0 |  | 0 | - |
| 9 | CIRC-12 | Circadian night-game advantage (Phase 12) | killed: not replicated | 0 | 0.0 |  | 0 | - |
| 10 | NGS-87 | NGS separation edge (Phase 8.7) | killed | 0 | 0.0 |  | 0 | - |
| 11 | BDB-86 | BDB tracking separation (Phase 8.6) | killed (one season, p 0.23) | 0 | 0.0 |  | 0 | - |
| 12 | ANGLES-85 | Combined upset angles (Phase 8.5) | killed | 0 | 0.0 |  | 0 | - |
| 13 | UPSET-83 | Nine upset metrics (Phase 8.3) | killed | 0 | 0.0 |  | 0 | - |
| 14 | WIND | Wind forecast tag (Phase 13 audit) | killed: 22 games, no gap | 0 | 0.0 |  | 0 | - |
| 15 | TUNING | Long hyperparameter/feature searches | killed: undetectable gains (power) | 0 | 0.0 |  | 0 | - |
