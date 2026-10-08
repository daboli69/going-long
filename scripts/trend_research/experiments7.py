"""Phase 3 distribution research: are Poisson (counts) and lognormal-plus-zero-mass (yardage) the right shapes around the mean?

The mean is held fixed (the production Champion mean, and the P3-1 blend mean) so the comparison isolates the distribution. Parameters are learned on 2021-2023 only,
validated on 2024 and confirmed on 2025. GOING prices probabilities such as P(player > 64.5 yards), so the evaluation uses threshold Brier scores, the log score (counts)
and pinball loss and interval coverage (yardage), not only a mean error.
"""
import numpy as np
from scipy.stats import nbinom, norm, poisson

from .experiments2 import COMMON, MARKET_RULES, _blend, _eligible, champion_rows
from .experiments5 import _cluster_ci

FLOOR = 0.01
COUNTS = ('receptions', 'rec_tds', 'rush_tds', 'atd', 'pass_tds')
YARDS = ('rec_yds', 'rush_yds', 'pass_yds')
LINES = {'receptions': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5], 'rec_tds': [0.5], 'rush_tds': [0.5], 'atd': [0.5], 'pass_tds': [0.5, 1.5, 2.5]}
PHI_GRID = [0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8]
PI_GRID = [0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3]
CV_GRID = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]
QUANTILES = [0.1, 0.25, 0.5, 0.75, 0.9]
RULE = {'min_nats': 0.005, 'min_brier_relative': 0.002, 'years_required': [2024, 2025]}

SPECS = {
    'P3-5': {**COMMON, 'id': 'P3-5', 'title': 'Count distributions: Poisson vs negative binomial vs zero-inflated Poisson around a fixed mean',
             'hypothesis': 'Counts are overdispersed (receptions variance/mean about 1.2); a negative binomial (or zero-inflated Poisson) with a market-level parameter learned on 2021-2023 prices count thresholds better than Poisson.',
             'football_rationale': 'Game scripts, injuries and role changes make a player\'s counts vary more than a Poisson with a stable mean allows.',
             'population': 'reconstructed Champion rows 2021-2025, count markets receptions, rec_tds, rush_tds, atd, pass_tds', 'markets': list(COUNTS),
             'models': {'POIS': 'Poisson(mean)', 'NB': 'negative binomial, variance = mean + phi*mean^2, phi grid on 2021-2023 maximum likelihood', 'ZIP': 'zero-inflated Poisson, constant pi, rate = mean/(1-pi)'},
             'means': ['champion 80/20 mean', 'P3-1 blend mean (c per market from P3-1)'],
             'splits': {'development': [2021, 2022, 2023], 'validation': [2024], 'holdout': [2025], 'note': '2025 was already examined for the mean in P3-1/E7; the distribution parameters are new'},
             'metric': 'mean log score (floor 0.01) and threshold Brier over standard lines (' + str(LINES) + '), all weeks', 'multiple_testing': 'Bonferroni over 5 markets x 2 alternatives (99.5% intervals)',
             'decision_rule': {'PROMISING': 'log score improves >= 0.005 nats per row in BOTH 2024 and 2025, the 2025 clustered interval excludes 0, and threshold Brier is not worse than Poisson by more than 0.2% in either year',
                               'REJECTED': 'the 2025 interval lies below the minimum improvement', 'INCONCLUSIVE': 'otherwise'}, 'rule_numbers': RULE,
             'sources': ['nflverse weekly stats'], 'leakage': 'parameters from 2021-2023 only', 'limitations': 'does not include injury adjustments or the live line selection; no historical prop prices'},
    'P3-6': {**COMMON, 'id': 'P3-6', 'title': 'Yardage distributions: production lognormal + zero mass vs pooled-spread alternatives around a fixed mean',
             'hypothesis': 'Replacing the player-window spread (noisy with 5-12 games) by a pooled coefficient of variation per market and position, with the zero mass shrunk toward the market rate, prices yardage thresholds and quantiles better.',
             'football_rationale': 'A 12-game window gives a poor estimate of a player\'s own spread; most of the spread is structural and shared across similar players.',
             'population': 'reconstructed Champion rows 2021-2025 with a positive-game window, markets rec_yds, rush_yds, pass_yds', 'markets': list(YARDS),
             'models': {'PROD': 'production: lognormal on the window\'s positive games (weighted mean and sd) + empirical nonpositive mass',
                        'PROD-B': 'PROD shape with the positive mean rescaled so the overall mean equals the P3-1 blend mean',
                        'POOL': 'lognormal with coefficient of variation learned on 2021-2023 per market and position, zero mass shrunk toward the position rate, mean = blend mean'},
             'splits': {'development': [2021, 2022, 2023], 'validation': [2024], 'holdout': [2025]}, 'metric': 'mean pinball loss over quantiles 0.1/0.25/0.5/0.75/0.9, Brier at lines (champion mean x 0.8/1.0/1.2), 80% interval coverage',
             'multiple_testing': 'Bonferroni over 3 markets x 2 alternatives (99.2% intervals)',
             'decision_rule': {'PROMISING': 'pinball loss improves >= 1% in BOTH 2024 and 2025 with the 2025 interval excluding 0 and Brier at lines not worse by more than 0.2%', 'REJECTED': 'the 2025 interval lies below 1%',
                               'INCONCLUSIVE': 'otherwise'}, 'rule_numbers': {'min_relative_pinball': 0.01, 'years_required': [2024, 2025]}, 'sources': ['nflverse weekly stats'],
             'leakage': 'parameters from 2021-2023 only', 'limitations': 'as P3-5'},
}


# ------------------------------------------------------------------ count distributions
def _pmf(family, y, mu, param):
    mu = np.maximum(mu, FLOOR)
    if family == 'POIS':
        return poisson.logpmf(y, mu)
    if family == 'NB':
        if param <= 0:
            return poisson.logpmf(y, mu)
        n = 1.0 / param
        return nbinom.logpmf(y, n, n / (n + mu))
    if family == 'ZIP':
        lam = mu / (1 - param)
        p = (1 - param) * poisson.pmf(y, lam) + (param if np.ndim(y) == 0 and y == 0 else param * (np.asarray(y) == 0))
        return np.log(np.maximum(p, 1e-300))
    raise ValueError(family)


def _tail(family, line, mu, param):
    """P(X > line) for a half-integer line."""
    mu = np.maximum(mu, FLOOR)
    k = np.floor(line)
    if family == 'POIS' or (family == 'NB' and param <= 0):
        return poisson.sf(k, mu)
    if family == 'NB':
        n = 1.0 / param
        return nbinom.sf(k, n, n / (n + mu))
    lam = mu / (1 - param)
    return (1 - param) * poisson.sf(k, lam)


def _fit_param(family, y, mu):
    grid = {'POIS': [None], 'NB': PHI_GRID, 'ZIP': PI_GRID}[family]
    scores = {p: float(_pmf(family, y, mu, p).mean()) if p is not None else float(poisson.logpmf(y, np.maximum(mu, FLOOR)).mean()) for p in grid}
    return max(scores, key=scores.get), scores


def run_p3_5(root, manifest):
    spec = SPECS['P3-5']
    frame = champion_rows(root)
    chosen = _c_from_ledger()
    out, verdicts = {}, []
    conf = 1 - 0.05 / 10
    for market in COUNTS:
        rows = _eligible(frame, market)
        c = chosen.get(market, 2)
        rows = rows.assign(blend=_blend(rows, market, c))
        res = {'blend_c': c, 'means': {}}
        for mean_name, col in (('champion', 'champ_' + market), ('blend', 'blend')):
            dev = rows[rows.season <= 2023]
            ydev, mdev = dev['y_' + market].to_numpy(float), dev[col].to_numpy(float)
            params = {fam: _fit_param(fam, ydev, mdev)[0] for fam in ('NB', 'ZIP')}
            params['POIS'] = None
            cells = {}
            for fam in ('POIS', 'NB', 'ZIP'):
                cells[fam] = {}
            for label, season in (('validation', 2024), ('holdout', 2025)):
                test = rows[rows.season == season]
                y, mu = test['y_' + market].to_numpy(float), test[col].to_numpy(float)
                logs, briers = {}, {}
                for fam in ('POIS', 'NB', 'ZIP'):
                    p = params[fam]
                    logs[fam] = _pmf(fam, y, mu, p) if fam != 'POIS' else poisson.logpmf(y, np.maximum(mu, FLOOR))
                    b = np.zeros(len(y))
                    for line in LINES[market]:
                        b += (_tail(fam, line, mu, p) - (y > line)) ** 2
                    briers[fam] = b / len(LINES[market])
                for fam in ('POIS', 'NB', 'ZIP'):
                    cells[fam][label] = {'log_score': float(logs[fam].mean()), 'brier': float(briers[fam].mean()),
                                         'mean_p_over_first_line': float(_tail(fam, LINES[market][0], mu, params[fam]).mean()), 'actual_over_first_line': float((y > LINES[market][0]).mean())}
                    if fam != 'POIS':
                        d = logs[fam] - logs['POIS']
                        m, lo, hi = _cluster_ci(d, test.player_id.to_numpy(), conf)
                        cells[fam][label].update(delta_log_score=m, delta_ci=[lo, hi], brier_relative_vs_pois=float((briers['POIS'].mean() - briers[fam].mean()) / briers['POIS'].mean()))
            res['means'][mean_name] = {'params': {k: v for k, v in params.items()}, 'cells': cells}
            for fam in ('NB', 'ZIP'):
                v, h = cells[fam]['validation'], cells[fam]['holdout']
                ok = (v['delta_log_score'] >= RULE['min_nats'] and h['delta_log_score'] >= RULE['min_nats'] and h['delta_ci'][0] > 0
                      and v['brier_relative_vs_pois'] >= -RULE['min_brier_relative'] and h['brier_relative_vs_pois'] >= -RULE['min_brier_relative'])
                label = 'PROMISING' if ok else ('REJECTED' if h['delta_ci'][1] < RULE['min_nats'] else 'INCONCLUSIVE')
                cells[fam]['verdict'] = label
                if mean_name == 'blend':
                    verdicts.append(label)
        out[market] = res
    status = 'PROMISING' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return {'markets': out}, status


def _c_from_ledger():
    """Prior strengths chosen by P3-1 on 2021-2023 (read from the committed ledger so this experiment cannot re-tune them)."""
    import json
    from pathlib import Path
    ledger = json.loads((Path(__file__).resolve().parents[2] / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))
    entry = ledger.get('experiments', ledger)['P3-1']
    return (entry.get('result') or entry)['chosen_c']


# ------------------------------------------------------------------ yardage distributions
def _ln_params(pm, ps):
    pm = np.asarray(pm, float)
    ratio = np.where(pm > 0, (np.asarray(ps, float) / np.where(pm > 0, pm, 1)) ** 2, 0.0)
    sigma2 = np.log1p(ratio)
    return np.log(np.where(pm > 0, pm, 1)) - sigma2 / 2, np.sqrt(sigma2)


def _ln_cdf(x, mu_log, sigma, p0):
    x = np.asarray(x, float)
    with np.errstate(divide='ignore', invalid='ignore'):
        z = np.where(sigma > 0, (np.log(np.maximum(x, 1e-9)) - mu_log) / np.where(sigma > 0, sigma, 1), np.where(np.log(np.maximum(x, 1e-9)) >= mu_log, 50, -50))
    return np.where(x <= 0, p0, p0 + (1 - p0) * norm.cdf(z))


def _ln_quantile(q, mu_log, sigma, p0):
    inner = np.clip((q - p0) / np.maximum(1 - p0, 1e-9), 1e-9, 1 - 1e-9)
    value = np.exp(mu_log + sigma * norm.ppf(inner))
    return np.where(q <= p0, 0.0, value)


def _pinball(y, qs):
    loss = 0.0
    for q, pred in zip(QUANTILES, qs):
        diff = y - pred
        loss = loss + np.maximum(q * diff, (q - 1) * diff)
    return loss / len(QUANTILES)


def run_p3_6(root, manifest):
    spec = SPECS['P3-6']
    frame = champion_rows(root)
    chosen = _c_from_ledger()
    out, verdicts = {}, []
    conf = 1 - 0.05 / 6
    for market in YARDS:
        rows = _eligible(frame, market)
        rows = rows[(rows['pw_' + market] > 0) & rows['pm_' + market].notna() & rows['ps_' + market].notna() & (rows['pm_' + market] > 0)]
        c = chosen.get(market, 2)
        rows = rows.assign(blend=_blend(rows, market, c))
        rows = rows[rows.blend > 0]
        dev = rows[rows.season <= 2023]
        pos = dev['position'].to_numpy()
        # POOL parameters on development seasons: per-position coefficient of variation of positive games and zero rate
        pool = {}
        for p in np.unique(pos):
            sub = dev[dev.position == p]
            y = sub['y_' + market].to_numpy(float)
            zero_rate = float((y <= 0).mean())
            positive = y[y > 0]
            pm = sub['blend'].to_numpy(float)
            best_cv, best = None, -np.inf
            for cv in CV_GRID:
                p0 = np.clip(zero_rate, 0.001, 0.99)
                mu_l, sg = _ln_params(pm / (1 - p0), pm / (1 - p0) * cv)
                score = float(np.mean(_pinball_neg(sub['y_' + market].to_numpy(float), mu_l, sg, p0)))
                if score > best:
                    best_cv, best = cv, score
            pool[p] = {'cv': best_cv, 'zero_rate': zero_rate, 'n': int(len(sub))}
        res = {'blend_c': c, 'pool': pool, 'cells': {}}
        for label, season in (('validation', 2024), ('holdout', 2025)):
            test = rows[rows.season == season]
            y = test['y_' + market].to_numpy(float)
            champ_mean = test['champ_' + market].to_numpy(float)
            pw, pm, ps = test['pw_' + market].to_numpy(float), test['pm_' + market].to_numpy(float), test['ps_' + market].to_numpy(float)
            blend = test['blend'].to_numpy(float)
            models = {}
            mu_l, sg = _ln_params(pm, ps)
            models['PROD'] = (mu_l, sg, 1 - pw)
            pm_b = np.where(pw > 0, blend / pw, pm)
            mu_b, sg_b = _ln_params(pm_b, ps * pm_b / pm)
            models['PROD-B'] = (mu_b, sg_b, 1 - pw)
            cv = np.array([pool[p]['cv'] for p in test['position']])
            zr = np.array([pool[p]['zero_rate'] for p in test['position']])
            n_games = test['n'].to_numpy(float)
            p0 = np.clip((n_games * (1 - pw) + 10 * zr) / (n_games + 10), 0.001, 0.99)
            pm_p = blend / (1 - p0)
            mu_p, sg_p = _ln_params(pm_p, pm_p * cv)
            models['POOL'] = (mu_p, sg_p, p0)
            stats = {}
            for name, (m_l, s_l, z0) in models.items():
                qs = [_ln_quantile(q, m_l, s_l, z0) for q in QUANTILES]
                pin = _pinball(y, qs)
                brier = np.zeros(len(y))
                for factor in (0.8, 1.0, 1.2):
                    line = np.maximum(champ_mean * factor, 1.0)
                    brier += ((1 - _ln_cdf(line, m_l, s_l, z0)) - (y > line)) ** 2
                brier /= 3
                lo, hi = _ln_quantile(0.1, m_l, s_l, z0), _ln_quantile(0.9, m_l, s_l, z0)
                stats[name] = {'pinball': pin, 'brier': brier, 'coverage80': float(((y >= lo) & (y <= hi)).mean())}
            groups = test.player_id.to_numpy()
            cell = {}
            for name in models:
                cell[name] = {'pinball': float(stats[name]['pinball'].mean()), 'brier': float(stats[name]['brier'].mean()), 'coverage80': stats[name]['coverage80']}
                if name != 'PROD':
                    d = stats['PROD']['pinball'] - stats[name]['pinball']
                    m, lo_ci, hi_ci = _cluster_ci(d / stats['PROD']['pinball'].mean(), groups, conf)
                    cell[name].update(relative_pinball_gain=m, ci=[lo_ci, hi_ci], brier_relative=float((stats['PROD']['brier'].mean() - stats[name]['brier'].mean()) / stats['PROD']['brier'].mean()))
            cell['n'] = int(len(y))
            res['cells'][label] = cell
        for name in ('PROD-B', 'POOL'):
            v, h = res['cells']['validation'][name], res['cells']['holdout'][name]
            ok = (v['relative_pinball_gain'] >= 0.01 and h['relative_pinball_gain'] >= 0.01 and h['ci'][0] > 0 and v['brier_relative'] >= -0.002 and h['brier_relative'] >= -0.002)
            label = 'PROMISING' if ok else ('REJECTED' if h['ci'][1] < 0.01 else 'INCONCLUSIVE')
            res['cells'].setdefault('verdicts', {})[name] = label
            verdicts.append(label)
        out[market] = res
    status = 'PROMISING' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return {'markets': out}, status


def _pinball_neg(y, mu_l, sg, p0):
    qs = [_ln_quantile(q, mu_l, sg, p0) for q in QUANTILES]
    return -_pinball(y, qs)


RUNNERS = {'P3-5': run_p3_5, 'P3-6': run_p3_6}
