# Saved-output secondary diagnostics

Bias/pseudo-line intervals are unadjusted secondary diagnostics, never nomination criteria. Count/zero ties mean above-median need not equal50%; above-mean need not equal50%. No real historical prop prices.

## Current champion / closing benchmarks

Negative delta means lower model loss than the benchmark. These secondary comparisons never change nominations. The saved champion used longer training history and was selected on previously examined years. Closing prices can reflect later information. Champion total predictions are unavailable.

|Variant|Target|Benchmark|n / games|Benchmark loss|Model loss|Delta [corrected95% CI]|
|---|---|---|---:|---:|---:|---|
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
|opportunity__pass_yds__control__hierarchy|-13.70239 [-18.07596,-9.14860]|59.8% / 0.0%|51.6% / 0.0%|+0.006469 [-0.001112,+0.014595]|
|opportunity__pass_yds__fpds__hierarchy|-15.31901 [-19.69881,-10.70154]|60.5% / 0.0%|50.7% / 0.0%|+0.010061 [+0.002076,+0.018778]|
|opportunity__pass_tds__control__hierarchy|-0.13764 [-0.19822,-0.07773]|48.6% / 0.3%|38.2% / 34.8%|+0.008764 [+0.003634,+0.014039]|
|opportunity__pass_tds__fpds__hierarchy|-0.16075 [-0.22240,-0.10196]|50.5% / 1.1%|39.1% / 34.6%|+0.009373 [+0.003542,+0.015402]|
|opportunity__rec__control__hierarchy|-0.11245 [-0.17380,-0.05026]|47.8% / 0.0%|41.8% / 18.7%|+0.011727 [+0.007871,+0.015507]|
|opportunity__rec__fpds__hierarchy|-0.11981 [-0.18335,-0.05601]|48.2% / 0.1%|43.0% / 17.9%|+0.021165 [+0.016539,+0.025730]|
|opportunity__rec_yds__control__hierarchy|-2.31502 [-3.12252,-1.44960]|46.0% / 0.0%|51.0% / 0.0%|+0.007250 [+0.004308,+0.010204]|
|opportunity__rec_yds__fpds__hierarchy|-2.79716 [-3.64790,-1.89945]|47.8% / 0.1%|50.6% / 0.4%|+0.012709 [+0.009310,+0.016323]|
|opportunity__rush_yds__control__hierarchy|-2.29359 [-3.50263,-1.13696]|46.2% / 0.3%|48.8% / 0.4%|+0.010158 [+0.004493,+0.015688]|
|opportunity__rush_yds__fpds__hierarchy|-2.16518 [-3.35384,-0.95580]|47.3% / 0.6%|48.5% / 0.7%|+0.011767 [+0.005494,+0.018090]|
|opportunity__anytime_td__control__hierarchy|-0.01802 [-0.02767,-0.00841]|27.9% / 0.7%|24.9% / 72.3%|unavailable|
|opportunity__anytime_td__fpds__hierarchy|-0.03125 [-0.04081,-0.02122]|27.9% / 5.2%|24.1% / 71.6%|unavailable|

## Registered individual members

|Variant / member|n / games|Reference loss|New loss|Delta [corrected95% CI]|
|---|---:|---:|---:|---|
