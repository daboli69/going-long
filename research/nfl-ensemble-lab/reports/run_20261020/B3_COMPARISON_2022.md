# Original v1 / baseline B versus ensembles — 2022

Requested ensemble rows 8576 / 271 games; exact matched rows 4795 / 271 games. All methods within each stat use identical rows. Original v1/B cover four stats and use closing anchors/retrospective eligibility. TD targets unsupported, not invented. Negative deltas favor the row method; paired game-cluster 95% CIs, 2,000 draws seed 20261020.

| stat | method | n | games | metric | loss | delta_vs_sim_mean | ci95_low_vs_sim_mean | ci95_high_vs_sim_mean | delta_vs_base_mean | ci95_low_vs_base_mean | ci95_high_vs_base_mean | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pass_yds | equal | 478.0000 | 264.0000 | MAE | 56.1799 | -1.6248 | -3.7687 | 0.5506 | -3.2205 | -6.0797 | -0.3313 | unavailable |
| pass_yds | weighted | 478.0000 | 264.0000 | MAE | 56.1869 | -1.6178 | -3.7796 | 0.5607 | -3.2135 | -6.0796 | -0.3325 | unavailable |
| pass_yds | stacked | 478.0000 | 264.0000 | MAE | 56.6087 | -1.1960 | -3.8605 | 1.3548 | -2.7917 | -5.8471 | 0.2098 | unavailable |
| pass_yds | sim_mean | 478.0000 | 264.0000 | MAE | 57.8047 | 0.0000 | 0.0000 | 0.0000 | -1.5957 | -4.6433 | 1.4931 | unavailable |
| pass_yds | base_mean | 478.0000 | 264.0000 | MAE | 59.4004 | 1.5957 | -1.4931 | 4.6433 | 0.0000 | 0.0000 | 0.0000 | unavailable |
| pass_tds | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | original v1/baseline B unsupported; no values invented |
| anytime_td | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | original v1/baseline B unsupported; no values invented |
| rec | equal | 1749.0000 | 271.0000 | Poisson deviance | 1.5385 | -0.0890 | -0.1296 | -0.0480 | -0.1493 | -0.2906 | -0.0504 | unavailable |
| rec | weighted | 1749.0000 | 271.0000 | Poisson deviance | 1.5383 | -0.0892 | -0.1301 | -0.0481 | -0.1495 | -0.2906 | -0.0505 | unavailable |
| rec | stacked | 1749.0000 | 271.0000 | Poisson deviance | 1.5407 | -0.0868 | -0.1280 | -0.0456 | -0.1471 | -0.2884 | -0.0474 | unavailable |
| rec | sim_mean | 1749.0000 | 271.0000 | Poisson deviance | 1.6275 | 0.0000 | 0.0000 | 0.0000 | -0.0604 | -0.2072 | 0.0517 | unavailable |
| rec | base_mean | 1749.0000 | 271.0000 | Poisson deviance | 1.6878 | 0.0604 | -0.0517 | 0.2072 | 0.0000 | 0.0000 | 0.0000 | unavailable |
| rec_yds | equal | 1749.0000 | 271.0000 | MAE | 25.4496 | -0.3984 | -0.8348 | 0.0417 | -0.4650 | -0.9657 | 0.0389 | unavailable |
| rec_yds | weighted | 1749.0000 | 271.0000 | MAE | 25.4484 | -0.3996 | -0.8362 | 0.0421 | -0.4662 | -0.9674 | 0.0379 | unavailable |
| rec_yds | stacked | 1749.0000 | 271.0000 | MAE | 25.2969 | -0.5512 | -0.9689 | -0.1221 | -0.6177 | -1.1334 | -0.1094 | unavailable |
| rec_yds | sim_mean | 1749.0000 | 271.0000 | MAE | 25.8481 | 0.0000 | 0.0000 | 0.0000 | -0.0666 | -0.6843 | 0.5256 | unavailable |
| rec_yds | base_mean | 1749.0000 | 271.0000 | MAE | 25.9146 | 0.0666 | -0.5256 | 0.6843 | 0.0000 | 0.0000 | 0.0000 | unavailable |
| rush_yds | equal | 819.0000 | 271.0000 | MAE | 27.8554 | -0.2972 | -0.9562 | 0.3221 | -0.6804 | -1.3408 | -0.0565 | unavailable |
| rush_yds | weighted | 819.0000 | 271.0000 | MAE | 27.8540 | -0.2986 | -0.9578 | 0.3222 | -0.6818 | -1.3416 | -0.0582 | unavailable |
| rush_yds | stacked | 819.0000 | 271.0000 | MAE | 28.1892 | 0.0366 | -0.5607 | 0.6417 | -0.3466 | -1.0272 | 0.2699 | unavailable |
| rush_yds | sim_mean | 819.0000 | 271.0000 | MAE | 28.1526 | 0.0000 | 0.0000 | 0.0000 | -0.3832 | -1.1769 | 0.3243 | unavailable |
| rush_yds | base_mean | 819.0000 | 271.0000 | MAE | 28.5358 | 0.3832 | -0.3243 | 1.1769 | 0.0000 | 0.0000 | 0.0000 | unavailable |
