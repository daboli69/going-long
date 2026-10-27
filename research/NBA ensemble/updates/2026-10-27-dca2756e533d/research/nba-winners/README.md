# NBA winner development diagnostic

Retained earlier replay, not a new holdout evaluation. No betting-return or promotion claim.

| Model | Brier | Log loss | Accuracy |
| --- | ---: | ---: | ---: |
| elo | 0.219406 | 0.628177 | 64.2560% |
| logistic | 0.215709 | 0.620219 | 65.6320% |
| gradient_boosting | 0.228911 | 0.651993 | 62.7520% |
| random_forest | 0.218028 | 0.625351 | 64.4160% |
| naive_bayes | 0.262637 | 0.869145 | 64.0640% |
| ridge_margin | 0.214671 | 0.617392 | 65.3440% |
| ensemble | 0.216804 | 0.622215 | 64.8320% |
| equal_weight | 0.217060 | 0.622828 | 64.7360% |
| home_frequency | 0.248270 | 0.689720 | 54.9440% |

Forecast games: 3125. Original source/protocol hashes and full predictions remain in `.cache/nba-winners/development-final.json`.
