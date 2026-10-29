"""Bayesian hierarchical logistic robustness check: is the availability effect stable across seasons?

Season-varying coefficients beta[s,k] ~ N(mu[k], tau[k]) on standardized features. Descriptive inference on the
2023-2026 retrospective sample (in-sample), NOT a forecasting model.
"""
import json
import numpy as np
import jax
import jax.numpy as jnp
import numpyro
import numpyro.distributions as dist
from numpyro.infer import MCMC, NUTS
from . import avail_study as S

numpyro.set_host_device_count(4)
FEATS = S.BASE + S.AVAIL


def model(X, season_idx, y, n_season):
    k = X.shape[1]
    b0 = numpyro.sample('b0', dist.Normal(0, 1))
    mu = numpyro.sample('mu', dist.Normal(0, 0.5).expand([k]))
    tau = numpyro.sample('tau', dist.HalfNormal(0.25).expand([k]))
    z = numpyro.sample('z', dist.Normal(0, 1).expand([n_season, k]))
    beta = mu + tau * z
    logits = b0 + jnp.sum(X * beta[season_idx], axis=1)
    numpyro.sample('y', dist.Bernoulli(logits=logits), obs=y)


def main():
    T = S.load_table()
    d = T[T.eligible & T.season.between(2023, 2026)].copy()
    X = d[FEATS].values.astype(float)
    X = (X - X.mean(0)) / X.std(0)
    sidx = (d.season.values - 2023).astype(int)
    mcmc = MCMC(NUTS(model), num_warmup=800, num_samples=1000, num_chains=4, progress_bar=False)
    mcmc.run(jax.random.PRNGKey(20261028), jnp.array(X), jnp.array(sidx), jnp.array(d.home_win.values), 4)
    s = mcmc.get_samples(group_by_chain=False)
    beta = np.array(s['mu'][:, None, :] + s['tau'][:, None, :] * s['z'])           # draws x season x k
    out = {'n_games': int(len(d)), 'features': FEATS, 'standardized': True, 'effects': {}}
    for j, f in enumerate(FEATS):
        mu = np.array(s['mu'][:, j])
        out['effects'][f] = {'pooled_mean': float(mu.mean()), 'pooled_ci94': [float(x) for x in np.percentile(mu, [3, 97])],
                             'prob_positive': float((mu > 0).mean()), 'between_season_sd_mean': float(np.array(s['tau'][:, j]).mean()),
                             'by_season_mean': {int(2023 + i): float(beta[:, i, j].mean()) for i in range(4)}}
    summ = numpyro.diagnostics.summary(mcmc.get_samples(group_by_chain=True), group_by_chain=True)
    out['max_r_hat'] = float(max(np.max(np.array(v['r_hat'])) for v in summ.values()))
    out['min_n_eff'] = float(min(np.min(np.array(v['n_eff'])) for v in summ.values()))
    (S.OUT / 'BAYES_CHECK.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'effects'}))
    for f, e in out['effects'].items():
        print(f"{f:20s} mu={e['pooled_mean']:+.3f} ci94=[{e['pooled_ci94'][0]:+.3f},{e['pooled_ci94'][1]:+.3f}] P>0={e['prob_positive']:.3f} tau={e['between_season_sd_mean']:.3f} seasons={[round(v,3) for v in e['by_season_mean'].values()]}")


if __name__ == '__main__':
    main()
