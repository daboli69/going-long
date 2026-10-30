"""DIAGNOSTIC for the Step 2 failure (props false-positive rate above 5%). Not part of the protocol chain; its result does not change the Step 2 verdict.
Question: is the week-clustered percentile bootstrap too liberal with 20 clusters, and does a t-interval on cluster means behave better?"""
from common import *
from scipy.stats import t as tdist

T = pd.read_parquet(PK / "scored_thresholds.parquet")
T["lad"] = T.gid + "|" + T.pid.astype(str) + "|" + T.stat
T = T[T.p_market90.notna()]
lads, sds, wks = [], [], []
for lid, d in T.groupby("lad"):
    d = d.sort_values("k")
    pm = d.p_market90.to_numpy(float)
    if len(d) >= 3 and np.ptp(pm) > 0.02:
        mu_, sd_, ok = fit_normal(d.k.to_numpy(float) - 0.5, pm)
        lads.append((d.k.to_numpy(float), pm))
        sds.append(sd_)
        wks.append(f"{int(d.season.iloc[0])}_{int(d.week.iloc[0]):02d}")
cod, kk = cluster_index(np.array(wks))
sds = np.array(sds)
rr = np.random.default_rng(SEED + 7)
B = 500
idx = rr.integers(0, kk, (B, kk))
n_per = np.bincount(cod, minlength=kk).astype(float)
theta = 0.3
N = 400
hit_boot = hit_t = 0
heavy = []
for _ in range(N):
    d = np.empty(len(lads))
    for i, (ks, S) in enumerate(lads):
        z, eA, eB, u = rr.standard_normal(), rr.standard_normal(), rr.standard_normal(), rr.random()
        yes = (u <= np.interp(ks - theta * sds[i] * z, ks, S)).astype(float)
        Sa = np.interp(ks - theta * sds[i] * (z + eA), ks, S)
        Sb = np.interp(ks - theta * sds[i] * (z + eB), ks, S)
        d[i] = ((Sa - yes) ** 2).sum() - ((Sb - yes) ** 2).sum()
    s = np.bincount(cod, weights=d, minlength=kk)
    bs = s[idx].sum(1) / n_per[idx].sum(1)
    hit_boot += np.percentile(bs, 2.5) > 0
    # t-interval on the ratio estimator: linearize residuals by cluster
    mbar = d.mean()
    resid = np.bincount(cod, weights=d - mbar, minlength=kk)
    se = np.sqrt((kk / (kk - 1)) * (resid ** 2).sum()) / len(d)
    hit_t += (mbar - tdist.ppf(0.975, kk - 1) * se) > 0
    heavy.append(float(np.abs(d).max() / (np.abs(d).std() + 1e-12)))
out = {"clusters": kk, "ladders": len(lads), "sims": N, "false_positive_percentile_bootstrap": hit_boot / N,
       "false_positive_t_interval_on_cluster_means": hit_t / N, "median_max_over_sd_of_ladder_differences": float(np.median(heavy)),
       "nominal_one_sided": 0.025, "mc_standard_error_at_nominal": float(np.sqrt(0.025 * 0.975 / N))}
write("step2_diag_props.json", out)
print(json.dumps(out, indent=1))
