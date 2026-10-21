# Saved-output secondary diagnostics

Bias/pseudo-line intervals are unadjusted secondary diagnostics, never nomination criteria. Count/zero ties mean above-median need not equal50%; above-mean need not equal50%. No real historical prop prices.

## Current champion / closing benchmarks

Negative delta means lower model loss than the benchmark. These secondary comparisons never change nominations. The saved champion used longer training history and was selected on previously examined years. Closing prices can reflect later information. Champion total predictions are unavailable.

|Variant|Target|Benchmark|n / games|Benchmark loss|Model loss|Delta [corrected95% CI]|
|---|---|---|---:|---:|---:|---|
|strong_games__win__control__equal|win|historical closing line; potentially later information|813 / 813|0.209894|0.227242|+0.017348 [+0.005619,+0.028600]|
|strong_games__win__control__equal|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.227242|+0.007383 [-0.001632,+0.015660]|
|strong_games__win__fpds__equal|win|historical closing line; potentially later information|813 / 813|0.209894|0.226656|+0.016762 [+0.005352,+0.028542]|
|strong_games__win__fpds__equal|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.226656|+0.006797 [-0.001874,+0.015106]|
|strong_games__margin__control__equal|margin|historical closing line; potentially later information|815 / 815|9.418405|9.882063|+0.463658 [+0.103866,+0.828715]|
|strong_games__margin__control__equal|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|9.882063|+0.185027 [-0.089694,+0.445240]|
|strong_games__margin__fpds__equal|margin|historical closing line; potentially later information|815 / 815|9.418405|9.951932|+0.533527 [+0.179785,+0.893761]|
|strong_games__margin__fpds__equal|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|9.951932|+0.254897 [-0.046260,+0.539352]|
|strong_games__total__control__equal|total|historical closing line; potentially later information|815 / 815|10.120859|10.507282|+0.386424 [-0.059638,+0.737122]|
|strong_games__total__fpds__equal|total|historical closing line; potentially later information|815 / 815|10.120859|10.512706|+0.391847 [+0.011454,+0.779826]|
|combination__win__control__weighted|win|historical closing line; potentially later information|813 / 813|0.209894|0.234443|+0.024549 [+0.010911,+0.037205]|
|combination__win__control__weighted|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.234443|+0.014584 [+0.002600,+0.025120]|
|combination__win__control__stacked|win|historical closing line; potentially later information|813 / 813|0.209894|0.235188|+0.025294 [+0.010864,+0.038105]|
|combination__win__control__stacked|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.235188|+0.015329 [+0.003353,+0.025804]|
|combination__win__fpds__weighted|win|historical closing line; potentially later information|813 / 813|0.209894|0.234797|+0.024903 [+0.010845,+0.037760]|
|combination__win__fpds__weighted|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.234797|+0.014938 [+0.002601,+0.026756]|
|combination__win__fpds__stacked|win|historical closing line; potentially later information|813 / 813|0.209894|0.236695|+0.026801 [+0.012707,+0.040197]|
|combination__win__fpds__stacked|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.236695|+0.016836 [+0.004636,+0.028622]|
|combination__margin__control__weighted|margin|historical closing line; potentially later information|815 / 815|9.418405|10.033676|+0.615271 [+0.167818,+1.053717]|
|combination__margin__control__weighted|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|10.033676|+0.336641 [-0.042864,+0.683932]|
|combination__margin__control__stacked|margin|historical closing line; potentially later information|815 / 815|9.418405|10.055537|+0.637132 [+0.192007,+1.079097]|
|combination__margin__control__stacked|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|10.055537|+0.358501 [-0.021689,+0.722903]|
|combination__margin__fpds__weighted|margin|historical closing line; potentially later information|815 / 815|9.418405|10.264182|+0.845777 [+0.418342,+1.298314]|
|combination__margin__fpds__weighted|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|10.264182|+0.567147 [+0.200990,+0.966776]|
|combination__margin__fpds__stacked|margin|historical closing line; potentially later information|815 / 815|9.418405|10.195704|+0.777299 [+0.340491,+1.192482]|
|combination__margin__fpds__stacked|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|10.195704|+0.498668 [+0.128480,+0.893061]|
|combination__total__control__weighted|total|historical closing line; potentially later information|815 / 815|10.120859|10.391385|+0.270526 [-0.088739,+0.629786]|
|combination__total__control__stacked|total|historical closing line; potentially later information|815 / 815|10.120859|10.415220|+0.294362 [-0.054121,+0.638909]|
|combination__total__fpds__weighted|total|historical closing line; potentially later information|815 / 815|10.120859|10.623064|+0.502205 [+0.088500,+0.870685]|
|combination__total__fpds__stacked|total|historical closing line; potentially later information|815 / 815|10.120859|10.573451|+0.452592 [+0.064013,+0.813195]|
|distribution__margin__fpds__quantile|margin|historical closing line; potentially later information|815 / 815|9.418405|9.990755|+0.572350 [+0.150080,+0.971477]|
|distribution__margin__fpds__quantile|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|9.990755|+0.293719 [-0.061440,+0.640643]|
|distribution__total__fpds__quantile|total|historical closing line; potentially later information|815 / 815|10.120859|10.597702|+0.476843 [+0.046866,+0.874114]|
|distribution__win__control__sigmoid|win|historical closing line; potentially later information|813 / 813|0.209894|0.233893|+0.023999 [+0.010797,+0.036815]|
|distribution__win__control__sigmoid|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.233893|+0.014034 [+0.002070,+0.024582]|
|distribution__win__control__isotonic|win|historical closing line; potentially later information|813 / 813|0.209894|0.235869|+0.025975 [+0.011348,+0.039805]|
|distribution__win__control__isotonic|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.235869|+0.016010 [+0.002270,+0.027251]|
|distribution__win__fpds__sigmoid|win|historical closing line; potentially later information|813 / 813|0.209894|0.233034|+0.023140 [+0.008581,+0.036125]|
|distribution__win__fpds__sigmoid|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.233034|+0.013175 [+0.001037,+0.024047]|
|distribution__win__fpds__isotonic|win|historical closing line; potentially later information|813 / 813|0.209894|0.234272|+0.024378 [+0.009697,+0.038241]|
|distribution__win__fpds__isotonic|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.234272|+0.014414 [+0.001961,+0.027202]|
|A7/win/control|win|historical closing line; potentially later information|813 / 813|0.209894|0.234501|+0.024607 [+0.010985,+0.037285]|
|A7/win/control|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.234501|+0.014643 [+0.002641,+0.025207]|
|A7/win/fpds|win|historical closing line; potentially later information|813 / 813|0.209894|0.234834|+0.024940 [+0.010835,+0.037760]|
|A7/win/fpds|win|saved production champion; already-examined descriptive comparison|813 / 813|0.219859|0.234834|+0.014975 [+0.002572,+0.026793]|
|A7/margin/control|margin|historical closing line; potentially later information|815 / 815|9.418405|10.034585|+0.616180 [+0.168175,+1.055067]|
|A7/margin/control|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|10.034585|+0.337550 [-0.041928,+0.685249]|
|A7/margin/fpds|margin|historical closing line; potentially later information|815 / 815|9.418405|10.275824|+0.857419 [+0.429111,+1.314578]|
|A7/margin/fpds|margin|saved production champion; already-examined descriptive comparison|815 / 815|9.697035|10.275824|+0.578789 [+0.209615,+0.987296]|
|A7/total/control|total|historical closing line; potentially later information|815 / 815|10.120859|10.391796|+0.270938 [-0.088253,+0.630240]|
|A7/total/fpds|total|historical closing line; potentially later information|815 / 815|10.120859|10.639280|+0.518421 [+0.102027,+0.891947]|

## Pseudo-line reliability and bias

Pseudo-lines are diagnostic thresholds, not real historical prop prices. Bias=prediction minus actual. These95% intervals are secondary and unadjusted; no selection is allowed.

|Variant|Mean bias [95% CI]|Above point / equal point|Above median / equal median|Pseudo-line Brier delta [95% CI]|
|---|---|---|---|---|
|strong_games__win__control__equal|+0.00343 [-0.02826,+0.03747]|55.0% / 0.0%|14.9% / 64.1%|unavailable|
|strong_games__win__fpds__equal|+0.00369 [-0.02836,+0.03775]|55.0% / 0.0%|14.5% / 64.1%|unavailable|
|strong_games__margin__control__equal|-0.37751 [-1.22269,+0.50273]|50.1% / 0.0%|50.7% / 0.0%|unavailable|
|strong_games__margin__fpds__equal|-0.27017 [-1.10721,+0.64182]|49.9% / 0.0%|50.1% / 0.0%|unavailable|
|strong_games__total__control__equal|-0.43693 [-1.32421,+0.52372]|48.2% / 0.0%|53.6% / 0.0%|unavailable|
|strong_games__total__fpds__equal|-0.31874 [-1.20192,+0.63145]|47.2% / 0.0%|54.1% / 0.0%|unavailable|
|target_features__pass_yds__fpds__equal|-1.97649 [-6.06190,+2.41197]|52.9% / 0.0%|50.3% / 0.0%|-0.002011 [-0.005904,+0.001931]|
|target_features__pass_tds__fpds__equal|-0.03546 [-0.09425,+0.02233]|46.2% / 0.0%|35.9% / 34.2%|-0.001407 [-0.003226,+0.000466]|
|target_features__rec__fpds__equal|+0.01790 [-0.03843,+0.07519]|44.7% / 0.0%|38.9% / 18.4%|-0.000227 [-0.001192,+0.000804]|
|target_features__rec_yds__fpds__equal|+0.60898 [-0.19312,+1.43372]|41.8% / 0.0%|50.2% / 0.1%|-0.000844 [-0.002135,+0.000556]|
|target_features__rush_yds__fpds__equal|+0.75272 [-0.35812,+1.90682]|41.1% / 0.0%|49.7% / 0.0%|-0.000423 [-0.002719,+0.001968]|
|target_features__anytime_td__fpds__equal|-0.00749 [-0.01704,+0.00165]|27.9% / 0.0%|26.5% / 72.0%|unavailable|
|combination__win__control__weighted|+0.00003 [-0.03219,+0.03419]|55.0% / 0.0%|12.5% / 61.7%|unavailable|
|combination__win__control__stacked|+0.00196 [-0.03047,+0.03616]|55.0% / 0.0%|11.9% / 60.1%|unavailable|
|combination__win__fpds__weighted|+0.00185 [-0.02970,+0.03594]|55.0% / 0.0%|11.3% / 61.9%|unavailable|
|combination__win__fpds__stacked|+0.00254 [-0.02962,+0.03669]|55.0% / 0.0%|10.5% / 61.5%|unavailable|
|combination__margin__control__weighted|+0.05116 [-0.81006,+0.93838]|46.5% / 0.0%|49.6% / 0.0%|unavailable|
|combination__margin__control__stacked|-0.00080 [-0.86425,+0.89315]|47.0% / 0.0%|49.6% / 0.0%|unavailable|
|combination__margin__fpds__weighted|+0.40029 [-0.48229,+1.32511]|46.3% / 0.0%|49.4% / 0.0%|unavailable|
|combination__margin__fpds__stacked|+0.10230 [-0.77884,+1.01577]|47.1% / 0.0%|49.6% / 0.0%|unavailable|
|combination__total__control__weighted|-0.05315 [-0.93023,+0.89036]|47.4% / 0.0%|53.3% / 0.0%|unavailable|
|combination__total__control__stacked|-0.22923 [-1.12675,+0.71488]|47.4% / 0.0%|52.9% / 0.0%|unavailable|
|combination__total__fpds__weighted|+0.26684 [-0.64864,+1.25041]|46.5% / 0.0%|53.3% / 0.0%|unavailable|
|combination__total__fpds__stacked|-0.12685 [-1.03278,+0.84805]|47.7% / 0.0%|54.0% / 0.0%|unavailable|
|combination__pass_yds__control__weighted|-1.79779 [-6.08311,+2.57900]|53.3% / 0.0%|49.8% / 0.0%|-0.000403 [-0.000999,+0.000102]|
|combination__pass_yds__control__stacked|-0.42056 [-4.68134,+3.96392]|52.3% / 0.0%|50.4% / 0.0%|-0.000411 [-0.001222,+0.000418]|
|combination__pass_yds__fpds__weighted|-1.01960 [-5.21513,+3.42101]|51.6% / 0.0%|50.9% / 0.0%|-0.000631 [-0.001591,+0.000224]|
|combination__pass_yds__fpds__stacked|-0.59727 [-4.79780,+3.82300]|51.4% / 0.0%|50.8% / 0.0%|-0.001042 [-0.002675,+0.000583]|
|combination__pass_tds__control__weighted|-0.02873 [-0.08694,+0.02957]|45.7% / 0.0%|36.8% / 34.2%|+0.000005 [-0.000000,+0.000011]|
|combination__pass_tds__control__stacked|-0.02911 [-0.08729,+0.02878]|44.2% / 0.0%|37.3% / 34.0%|+0.000402 [-0.000585,+0.001350]|
|combination__pass_tds__fpds__weighted|-0.03314 [-0.09143,+0.02451]|46.5% / 0.0%|36.3% / 33.2%|-0.000036 [-0.000060,-0.000012]|
|combination__pass_tds__fpds__stacked|-0.03102 [-0.09000,+0.02736]|45.2% / 0.0%|36.8% / 33.2%|-0.000007 [-0.001331,+0.001276]|
|combination__rec__control__weighted|+0.00604 [-0.05190,+0.06389]|44.7% / 0.0%|39.0% / 18.8%|-0.000007 [-0.000011,-0.000002]|
|combination__rec__control__stacked|-0.00267 [-0.06036,+0.05532]|44.9% / 0.0%|39.3% / 18.8%|-0.000268 [-0.000525,-0.000018]|
|combination__rec__fpds__weighted|+0.00076 [-0.05649,+0.05795]|45.1% / 0.0%|38.9% / 19.3%|-0.000029 [-0.000071,+0.000011]|
|combination__rec__fpds__stacked|+0.00313 [-0.05432,+0.06078]|44.9% / 0.0%|38.9% / 19.5%|-0.000284 [-0.000668,+0.000056]|
|combination__rec_yds__control__weighted|+0.14070 [-0.65141,+0.95706]|41.8% / 0.0%|50.9% / 0.0%|-0.000157 [-0.000461,+0.000116]|
|combination__rec_yds__control__stacked|-0.04118 [-0.82819,+0.77551]|42.4% / 0.0%|51.1% / 0.0%|-0.000090 [-0.000497,+0.000301]|
|combination__rec_yds__fpds__weighted|+0.48144 [-0.31060,+1.28697]|42.1% / 0.0%|50.3% / 0.0%|-0.000453 [-0.000873,-0.000071]|
|combination__rec_yds__fpds__stacked|+0.25708 [-0.52593,+1.07531]|42.5% / 0.0%|50.4% / 0.0%|-0.001469 [-0.002197,-0.000797]|
|combination__rush_yds__control__weighted|-0.08649 [-1.17641,+1.08306]|42.3% / 0.0%|50.0% / 0.0%|-0.000705 [-0.001316,-0.000185]|
|combination__rush_yds__control__stacked|+0.14473 [-0.94533,+1.31378]|42.1% / 0.0%|50.4% / 0.0%|-0.000459 [-0.001193,+0.000230]|
|combination__rush_yds__fpds__weighted|+1.31489 [+0.18427,+2.49630]|40.9% / 0.0%|50.0% / 0.1%|-0.001599 [-0.002773,-0.000577]|
|combination__rush_yds__fpds__stacked|+0.83552 [-0.28414,+2.00097]|41.7% / 0.0%|50.4% / 0.1%|-0.002339 [-0.003676,-0.001059]|
|combination__anytime_td__control__weighted|-0.00497 [-0.01453,+0.00434]|27.9% / 0.0%|25.9% / 72.4%|unavailable|
|combination__anytime_td__control__stacked|-0.00843 [-0.01784,+0.00103]|27.9% / 0.0%|25.7% / 72.4%|unavailable|
|combination__anytime_td__fpds__weighted|-0.00995 [-0.01993,-0.00025]|27.9% / 0.0%|26.9% / 72.0%|unavailable|
|combination__anytime_td__fpds__stacked|-0.01126 [-0.02104,-0.00157]|27.9% / 0.0%|26.6% / 72.1%|unavailable|
|opportunity__rush_yds__control__hierarchy|-7.54348 [-11.50253,-3.48790]|51.0% / 0.0%|58.5% / 0.0%|-0.003891 [-0.021649,+0.013089]|
|opportunity__rush_yds__fpds__hierarchy|-7.63906 [-11.65717,-3.50988]|51.0% / 0.4%|56.8% / 0.8%|-0.006538 [-0.035742,+0.021781]|
|distribution__margin__fpds__quantile|-0.28927 [-1.15832,+0.61080]|50.6% / 0.0%|50.6% / 0.0%|unavailable|
|distribution__total__fpds__quantile|-0.96340 [-1.88579,+0.01471]|50.3% / 0.0%|50.3% / 0.0%|unavailable|
|distribution__pass_yds__fpds__quantile|+4.69967 [+0.43649,+9.04347]|50.3% / 0.0%|50.3% / 0.0%|+0.002887 [-0.001379,+0.007045]|
|distribution__rec_yds__fpds__quantile|-5.29463 [-6.08440,-4.46673]|49.9% / 0.0%|49.9% / 0.0%|+0.000142 [-0.001914,+0.002088]|
|distribution__rush_yds__fpds__quantile|-4.71340 [-5.81758,-3.55174]|48.6% / 0.1%|48.6% / 0.1%|-0.001727 [-0.004741,+0.001214]|
|distribution__rec__fpds__hurdle|-0.04832 [-0.10781,+0.01375]|46.3% / 0.0%|39.8% / 19.3%|+0.010493 [+0.007909,+0.013123]|
|distribution__rec__fpds__nb|+0.01790 [-0.03843,+0.07519]|44.7% / 0.0%|40.8% / 19.1%|-0.000837 [-0.001392,-0.000284]|
|distribution__pass_tds__fpds__hurdle|-0.05798 [-0.12002,+0.00357]|47.4% / 0.0%|38.5% / 33.4%|+0.018850 [+0.011799,+0.025773]|
|distribution__pass_tds__fpds__nb|-0.03546 [-0.09425,+0.02233]|46.2% / 0.0%|35.9% / 34.3%|-0.000014 [-0.000067,+0.000039]|
|distribution__win__control__sigmoid|-0.00039 [-0.03237,+0.03379]|55.0% / 0.0%|13.8% / 61.9%|unavailable|
|distribution__win__control__isotonic|+0.00176 [-0.03000,+0.03561]|55.0% / 0.0%|15.9% / 60.4%|unavailable|
|distribution__win__fpds__sigmoid|+0.00235 [-0.02943,+0.03619]|55.0% / 0.0%|12.2% / 61.9%|unavailable|
|distribution__win__fpds__isotonic|+0.00053 [-0.03074,+0.03495]|55.0% / 0.0%|14.3% / 62.5%|unavailable|
|distribution__anytime_td__control__sigmoid|-0.00416 [-0.01374,+0.00513]|27.9% / 0.0%|25.9% / 72.4%|unavailable|
|distribution__anytime_td__control__isotonic|-0.00400 [-0.01351,+0.00540]|27.9% / 0.0%|26.7% / 72.2%|unavailable|
|distribution__anytime_td__fpds__sigmoid|-0.00976 [-0.01974,-0.00007]|27.9% / 0.0%|27.0% / 72.0%|unavailable|
|distribution__anytime_td__fpds__isotonic|-0.01027 [-0.02025,-0.00051]|27.9% / 0.0%|27.1% / 71.9%|unavailable|

## Registered individual members

|Variant / member|n / games|Reference loss|New loss|Delta [corrected95% CI]|
|---|---:|---:|---:|---|
|strong_games__win__control__equal / logreg|813 / 813|0.235341|0.226287|-0.009053 [-0.018447,+0.001827]|
|strong_games__win__control__equal / xgboost|813 / 813|0.236043|0.228502|-0.007541 [-0.019597,+0.003870]|
|strong_games__win__control__equal / decision_tree|813 / 813|0.261878|0.250695|-0.011183 [-0.039688,+0.018723]|
|strong_games__win__control__equal / random_forest|813 / 813|0.233499|0.225012|-0.008487 [-0.019771,+0.003346]|
|strong_games__win__control__equal / mlp|813 / 813|0.234123|0.232726|-0.001397 [-0.014169,+0.011060]|
|strong_games__win__control__equal / single_layer|813 / 813|0.236129|0.237873|+0.001744 [-0.010358,+0.015087]|
|strong_games__win__fpds__equal / logreg|813 / 813|0.226287|0.226778|+0.000490 [-0.001618,+0.002986]|
|strong_games__win__fpds__equal / xgboost|813 / 813|0.228502|0.229231|+0.000729 [-0.003610,+0.005659]|
|strong_games__win__fpds__equal / decision_tree|813 / 813|0.250695|0.248592|-0.002103 [-0.017351,+0.013943]|
|strong_games__win__fpds__equal / random_forest|813 / 813|0.225012|0.224730|-0.000282 [-0.003042,+0.002270]|
|strong_games__win__fpds__equal / mlp|813 / 813|0.232726|0.230707|-0.002019 [-0.009785,+0.004897]|
|strong_games__win__fpds__equal / single_layer|813 / 813|0.237873|0.238735|+0.000862 [-0.005716,+0.007732]|
|strong_games__margin__control__equal / logreg|815 / 815|10.416305|11.035246|+0.618941 [-0.016946,+1.215487]|
|strong_games__margin__control__equal / xgboost|815 / 815|10.137736|9.889560|-0.248176 [-0.612089,+0.184582]|
|strong_games__margin__control__equal / decision_tree|815 / 815|10.865591|10.589957|-0.275634 [-0.916183,+0.400436]|
|strong_games__margin__control__equal / random_forest|815 / 815|10.065088|9.787210|-0.277878 [-0.609018,+0.074306]|
|strong_games__margin__control__equal / mlp|815 / 815|10.081617|9.964799|-0.116819 [-0.521091,+0.311953]|
|strong_games__margin__control__equal / single_layer|815 / 815|10.242968|10.595515|+0.352548 [-0.180944,+0.941744]|
|strong_games__margin__fpds__equal / logreg|815 / 815|11.035246|11.447388|+0.412142 [+0.051047,+0.796184]|
|strong_games__margin__fpds__equal / xgboost|815 / 815|9.889560|9.901938|+0.012378 [-0.144061,+0.149732]|
|strong_games__margin__fpds__equal / decision_tree|815 / 815|10.589957|10.644677|+0.054720 [-0.169481,+0.241167]|
|strong_games__margin__fpds__equal / random_forest|815 / 815|9.787210|9.781898|-0.005312 [-0.077960,+0.068692]|
|strong_games__margin__fpds__equal / mlp|815 / 815|9.964799|9.924188|-0.040610 [-0.289729,+0.213877]|
|strong_games__margin__fpds__equal / single_layer|815 / 815|10.595515|10.827529|+0.232014 [-0.142929,+0.566710]|
|strong_games__total__control__equal / logreg|815 / 815|10.591815|11.663179|+1.071363 [+0.546136,+1.628910]|
|strong_games__total__control__equal / xgboost|815 / 815|10.488283|10.494815|+0.006532 [-0.245695,+0.272668]|
|strong_games__total__control__equal / decision_tree|815 / 815|10.702121|11.083660|+0.381538 [-0.166123,+0.939313]|
|strong_games__total__control__equal / random_forest|815 / 815|10.458010|10.425142|-0.032868 [-0.225760,+0.145592]|
|strong_games__total__control__equal / mlp|815 / 815|10.476489|10.515242|+0.038754 [-0.245213,+0.351231]|
|strong_games__total__control__equal / single_layer|815 / 815|10.828962|11.245552|+0.416590 [-0.086081,+0.877198]|
|strong_games__total__fpds__equal / logreg|815 / 815|11.663179|12.023832|+0.360653 [-0.017891,+0.763730]|
|strong_games__total__fpds__equal / xgboost|815 / 815|10.494815|10.473886|-0.020929 [-0.194842,+0.140541]|
|strong_games__total__fpds__equal / decision_tree|815 / 815|11.083660|10.946626|-0.137033 [-0.551970,+0.249305]|
|strong_games__total__fpds__equal / random_forest|815 / 815|10.425142|10.409640|-0.015502 [-0.107471,+0.063841]|
|strong_games__total__fpds__equal / mlp|815 / 815|10.515242|10.543261|+0.028019 [-0.202202,+0.265698]|
|strong_games__total__fpds__equal / single_layer|815 / 815|11.245552|11.448660|+0.203108 [-0.110078,+0.539179]|
|target_features__pass_yds__fpds__equal / linear|1528 / 807|73.432630|69.306839|-4.125791 [-6.771799,-1.330997]|
|target_features__pass_yds__fpds__equal / hist|1528 / 807|66.296648|66.158532|-0.138116 [-1.580679,+1.388498]|
|target_features__pass_yds__fpds__equal / xgboost|1528 / 807|65.681803|65.453982|-0.227820 [-1.353559,+0.783339]|
|target_features__pass_yds__fpds__equal / mlp|1528 / 807|64.522036|64.773838|+0.251802 [-0.606866,+1.189604]|
|target_features__pass_tds__fpds__equal / linear|1528 / 807|1.148048|1.107245|-0.040804 [-0.073799,-0.011537]|
|target_features__pass_tds__fpds__equal / hist|1528 / 807|1.102839|1.081629|-0.021211 [-0.053052,+0.011431]|
|target_features__pass_tds__fpds__equal / xgboost|1528 / 807|1.074618|1.059814|-0.014804 [-0.032620,+0.002983]|
|target_features__pass_tds__fpds__equal / mlp|1528 / 807|1.080768|1.075462|-0.005306 [-0.026038,+0.013823]|
|target_features__rec__fpds__equal / linear|6196 / 815|1.615424|1.568849|-0.046575 [-0.078544,-0.016455]|
|target_features__rec__fpds__equal / hist|6196 / 815|1.499972|1.488296|-0.011676 [-0.025263,+0.003363]|
|target_features__rec__fpds__equal / xgboost|6196 / 815|1.493774|1.494407|+0.000633 [-0.004401,+0.006071]|
|target_features__rec__fpds__equal / mlp|6196 / 815|1.544556|1.542804|-0.001752 [-0.018986,+0.019458]|
|target_features__rec_yds__fpds__equal / linear|6196 / 815|26.332523|25.320055|-1.012467 [-1.428425,-0.610990]|
|target_features__rec_yds__fpds__equal / hist|6196 / 815|24.126295|24.125680|-0.000615 [-0.180494,+0.195871]|
|target_features__rec_yds__fpds__equal / xgboost|6196 / 815|24.049528|24.055243|+0.005715 [-0.120403,+0.136182]|
|target_features__rec_yds__fpds__equal / mlp|6196 / 815|24.614920|24.689876|+0.074956 [-0.080703,+0.246617]|
|target_features__rush_yds__fpds__equal / linear|2740 / 814|28.007875|25.950773|-2.057103 [-2.860712,-1.287189]|
|target_features__rush_yds__fpds__equal / hist|2740 / 814|25.020999|25.031622|+0.010623 [-0.307945,+0.387444]|
|target_features__rush_yds__fpds__equal / xgboost|2740 / 814|24.860956|24.866472|+0.005515 [-0.248567,+0.252935]|
|target_features__rush_yds__fpds__equal / mlp|2740 / 814|25.611137|25.795349|+0.184213 [-0.040363,+0.428562]|
|target_features__anytime_td__fpds__equal / linear|8042 / 815|0.230650|0.208210|-0.022440 [-0.028471,-0.016744]|
|target_features__anytime_td__fpds__equal / hist|8042 / 815|0.189963|0.189575|-0.000388 [-0.001847,+0.001107]|
|target_features__anytime_td__fpds__equal / xgboost|8042 / 815|0.189018|0.188926|-0.000093 [-0.001213,+0.001081]|
|target_features__anytime_td__fpds__equal / mlp|8042 / 815|0.212933|0.211454|-0.001478 [-0.002588,-0.000336]|
