"""EXPLORATORY post-hoc checks for the Jackpot TD experiments (JP-1..JP-5). Run AFTER the registered verdicts; they cannot change a verdict.

    python -c "import sys; sys.path.insert(0,'scripts'); from trend_research import jackpot_posthoc as p; p.write('<GOING root>')"

(1) baseline log transform, (2) refit through 2024, (3) anytime score transferred to first/last, (4) coefficient differences first vs last,
(5) PRIMARY-role tier first vs last, (6) favourite share by season.
"""
import json

import numpy as np
import pandas as pd

from . import experiments11 as e


def _gain_table(result):
    return {n: {'verdict': c['verdict'], 'val': c['validation']['gain_logloss'][0], 'hold': c['holdout']['gain_logloss'][0], 'hold_adj_ci': c['holdout']['gain_logloss_adj'][1:]}
            for n, c in result['blocks'].items() if not n.startswith('f:')}


def posthoc(root, boots=200):
    pop = e._population(root)
    out = {'note': 'EXPLORATORY post-hoc checks run after the registered verdicts; they cannot change a verdict.'}
    original = pop['log_rate'].copy()
    pop['log_rate'] = np.log(pop.rate + 0.05)  # (1) alternative baseline transform
    out['alt_baseline_log_rate_plus_0.05'] = {sid: _gain_table(e.evaluate_market(sid, root)) for sid in ('JP-2', 'JP-3', 'JP-4', 'JP-5')}
    pop['log_rate'] = original
    # (2) refit on 2021-2024, score 2025 (anytime)
    train, test = pop[pop.season.isin(list(e.DEV) + [e.VAL])], e._rows(pop, e.HOLD)
    lls = {}
    for name, cols in (('B0c', []), ('ALL', e.cols_for(e.ANY_BLOCKS)), ('OPP', e.cols_for(['OPP'])), ('ROLE', e.cols_for(['ROLE']))):
        w = e.fit_logit(np.column_stack([train.log_rate] + ([train[cols].to_numpy(float)] if cols else [])), train.y_any.to_numpy(float), e.PEN_ANY)
        p = e.predict_logit(w, np.column_stack([test.log_rate] + ([test[cols].to_numpy(float)] if cols else [])))
        lls[name] = e.row_metrics_any(p, test.y_any.to_numpy(float), test)['ll']
    out['refit_2021_2024_anytime_holdout'] = {n: {'logloss': float(v.mean()), 'gain_vs_B0c': e._summ(lls['B0c'] - v, test.player_id.to_numpy(), 0.95)} for n, v in lls.items() if n != 'B0c'}
    # (3) anytime-ALL linear predictor (dev fit) used as the only feature of the first / last model
    dev = pop[pop.season.isin(e.DEV)]
    anycols = e.cols_for(e.ANY_BLOCKS)
    w_any = e.fit_logit(np.column_stack([dev.log_rate, dev[anycols].to_numpy(float)]), dev.y_any.to_numpy(float), e.PEN_ANY)
    pop['any_score'] = np.column_stack([np.ones(len(pop)), pop.log_rate, pop[anycols].to_numpy(float)]) @ w_any
    transfer = {}
    for market, sid in (('first', 'JP-3'), ('last', 'JP-4')):
        specs = {'B0c': dict(base='log_rate', cols=[]), 'ANY_TRANSFER': dict(base='any_score', cols=[]), 'OWN_ALL': dict(base='log_rate', cols=e.cols_for(e.ALL_BY_MARKET[sid]))}
        P = e.fit_models(market, pop, specs)
        res = {}
        for label, season in (('validation', e.VAL), ('holdout', e.HOLD)):
            frame, y, gid, uniq = e._game_frame(pop, season, market)
            G = len(uniq)
            per = {}
            for n, s in specs.items():
                X = np.column_stack([frame[s['base']].to_numpy(float)] + ([frame[s['cols']].to_numpy(float)] if s['cols'] else []))
                p, po = e.predict_clogit(P[n], X, gid)
                per[n] = e.game_metrics(p, po, y, gid, G)
            res[label] = {'logloss': {n: float(v['ll'].mean()) for n, v in per.items()}, 'hit5': {n: float(v['hit'][5].mean()) for n, v in per.items()},
                          'transfer_vs_B0c_gain': e._summ(per['B0c']['ll'] - per['ANY_TRANSFER']['ll'], np.arange(G), 0.95),
                          'own_all_vs_transfer_gain': e._summ(per['ANY_TRANSFER']['ll'] - per['OWN_ALL']['ll'], np.arange(G), 0.95)}
        transfer[market] = res
    out['anytime_score_transferred'] = transfer
    # (4) coefficient differences first vs last, all seasons, in-sample, game bootstrap
    feats = ['is_rb', 'is_te', 'is_qb', 'team_win_p', 'open_share6', 'late_share6', 'tm_first_td_rate', 'snap6', 'xtd12', 'xshare6']
    fc = [f + '_z' for f in feats]
    frames, ys = {}, {}
    for m in ('first', 'last', 'king'):
        parts = [e._game_frame(pop, s, m) for s in range(2021, 2026)]
        frames[m] = pd.concat([p[0] for p in parts], ignore_index=True)
        ys[m] = np.concatenate([p[1] for p in parts])

    def fit(m, rows=None, gid=None):
        f = frames[m] if rows is None else frames[m].iloc[rows]
        y = ys[m] if rows is None else ys[m][rows]
        g = pd.factorize(f.game_id)[0] if gid is None else gid
        return e.fit_clogit(np.column_stack([f.log_rate.to_numpy(float), f[fc].to_numpy(float)]), g, y, e.PEN_GAME)

    point = {m: fit(m) for m in ('first', 'last', 'king')}
    rng = np.random.default_rng(e.SEED)
    games = sorted(set(frames['first'].game_id) & set(frames['last'].game_id))
    pos = {m: {g: np.flatnonzero(frames[m].game_id.to_numpy() == g) for g in games} for m in ('first', 'last')}
    diffs = []
    for _ in range(boots):
        pick = rng.choice(len(games), len(games), replace=True)
        th = {}
        for m in ('first', 'last'):
            rows = np.concatenate([pos[m][games[i]] for i in pick])
            th[m] = fit(m, rows, np.repeat(np.arange(len(pick)), [len(pos[m][games[i]]) for i in pick]))
        diffs.append(th['first'] - th['last'])
    diffs = np.array(diffs)
    names = ['other_utility', 'log_rate'] + feats
    out['coef_first_vs_last_all_seasons_insample'] = {n: {'first': float(point['first'][i]), 'last': float(point['last'][i]), 'king': float(point['king'][i]),
                                                          'first_minus_last_ci95': [float(np.quantile(diffs[:, i], 0.025)), float(np.quantile(diffs[:, i], 0.975))]} for i, n in enumerate(names)}
    out['coef_note'] = 'conditional-logit coefficients per 1 sd (log_rate per log unit), all 2021-2025 games in-sample (descriptive), 200 game-bootstrap draws of first minus last'
    # (5) PRIMARY-role tier first vs last
    tier = {}
    for label, mask in (('all 2021-2025', pop.season >= 2021), ('2024-2025', pop.season.isin([e.VAL, e.HOLD]))):
        sub = pop[mask & (pop['xtd_share__L6'].fillna(0) >= 0.30) & (pop.n_td >= 2)]
        tier[label] = {'n': int(len(sub)), 'first_rate': float(sub.y_first.mean()), 'last_rate': float(sub.y_last.mean()), 'anytime_rate': float(sub.y_any.mean()),
                       'first_minus_last': e._summ((sub.y_first - sub.y_last).to_numpy(), sub.player_id.to_numpy(), 0.95)}
    out['primary_tier_first_vs_last'] = tier
    # (6) favourite share by season
    ev = e._event_frame(root)
    out['favourite_share_by_season'] = {str(s): {'games': int(ev[ev.season == s].game_id.nunique()), 'first': float(ev[(ev.season == s) & ev.is_first].fav.astype(float).mean()),
                                                 'last': float(ev[(ev.season == s) & ev.is_last].fav.astype(float).mean()), 'all': float(ev[ev.season == s].fav.astype(float).mean())} for s in range(2021, 2026)}
    return out


def write(root, boots=200):
    result = posthoc(root, boots)
    existing = json.loads(e.OUT.read_text(encoding='utf-8')) if e.OUT.exists() else {}
    existing['posthoc'] = result
    e.OUT.write_text(json.dumps(existing, indent=1, sort_keys=True), encoding='utf-8')
    return result


LEAN = ['xtd12', 'xshare6', 'snap3', 'inside5_touch12']


def production_candidate(root):
    """POST-HOC lean model and market constants for the pipeline. Evaluation rows use development-only fits; production rows are refit on 2021-2025 (no holdout left to check them)."""
    pop = e._population(root)
    stats = e._STATE['stats']
    lc = [f + '_z' for f in LEAN]
    out = {'note': 'POST-HOC: lean feature set chosen from the registered PROMOTE verdicts; evaluation uses development-only fits; production constants are refit on 2021-2025.',
           'features': LEAN, 'standardisation': {f: {'median_fill': stats[f][0], 'winsor_lo': stats[f][1], 'winsor_hi': stats[f][2], 'mean': stats[f][3], 'sd': stats[f][4]} for f in LEAN}}
    dev = pop[pop.season.isin(e.DEV)]

    def design(frame):
        return np.column_stack([frame.log_rate.to_numpy(float), frame[lc].to_numpy(float)])

    w_dev = e.fit_logit(design(dev), dev.y_any.to_numpy(float), e.PEN_ANY)
    ev = {}
    for label, season in (('validation', e.VAL), ('holdout', e.HOLD)):
        fr = e._rows(pop, season)
        y = fr.y_any.to_numpy(float)
        base = e.fit_logit(dev[['log_rate']].to_numpy(float), dev.y_any.to_numpy(float), e.PEN_ANY)
        p_base = e.predict_logit(base, fr[['log_rate']].to_numpy(float))
        p_lean = e.predict_logit(w_dev, design(fr))
        m0, m1 = e.row_metrics_any(p_base, y, fr), e.row_metrics_any(p_lean, y, fr)
        ev[label] = {'logloss_B0c': float(m0['ll'].mean()), 'logloss_lean': float(m1['ll'].mean()), 'gain': e._summ(m0['ll'] - m1['ll'], fr.player_id.to_numpy(), 0.95),
                     'brier_gain': e._summ(m0['brier'] - m1['brier'], fr.player_id.to_numpy(), 0.95),
                     'top10_precision': [float(m0['prec'][10].mean()), float(m1['prec'][10].mean())], 'calibration_slope_lean': _slope(p_lean, y)}
    out['anytime_lean_evaluation'] = ev
    allr = pop[pop.season >= 2021]
    w_all = e.fit_logit(design(allr), allr.y_any.to_numpy(float), e.PEN_ANY)
    names = ['intercept', 'log_champion_rate'] + LEAN
    sd = np.array([1.0, 1.0] + [stats[f][4] for f in LEAN])
    raw = w_all.copy()
    raw[2:] = w_all[2:] / sd[2:]
    raw[0] = w_all[0] - sum(w_all[2 + i] * stats[f][3] / stats[f][4] for i, f in enumerate(LEAN))
    out['anytime_production_coefficients_standardised'] = dict(zip(names, [float(x) for x in w_all]))
    out['anytime_production_coefficients_raw_features'] = dict(zip(names, [float(x) for x in raw]))
    out['anytime_formula'] = 'logit P(anytime TD) = intercept + b_rate*ln(max(champion_rate,0.01)) + sum b_f*clip(feature_f, winsor_lo, winsor_hi) [median-fill missing first]; raw-scale coefficients apply to the winsorised feature'
    # first / last / king: one shared score, market-specific slope and "other" utility
    dev_score = np.column_stack([np.ones(len(pop)), design(pop)]) @ w_dev
    pop['lean_score'] = dev_score
    allscore = np.column_stack([np.ones(len(pop)), design(pop)]) @ w_all
    market = {}
    for m in ('first', 'last', 'king'):
        extra = e.cols_for(['KING']) if m == 'king' else []
        specs = {'B0c': dict(base='log_rate', cols=[]), 'LEAN': dict(base='lean_score', cols=extra)}
        P = e.fit_models(m, pop, specs)
        res = {}
        for label, season in (('validation', e.VAL), ('holdout', e.HOLD)):
            frame, y, gid, uniq = e._game_frame(pop, season, m)
            G = len(uniq)
            per = {}
            for n, s in specs.items():
                X = np.column_stack([frame[s['base']].to_numpy(float)] + ([frame[s['cols']].to_numpy(float)] if s['cols'] else []))
                p, po = e.predict_clogit(P[n], X, gid)
                per[n] = e.game_metrics(p, po, y, gid, G)
            res[label] = {'logloss_B0c': float(per['B0c']['ll'].mean()), 'logloss_lean': float(per['LEAN']['ll'].mean()), 'gain': e._summ(per['B0c']['ll'] - per['LEAN']['ll'], np.arange(G), 0.95),
                          'hit3': [float(per['B0c']['hit'][3].mean()), float(per['LEAN']['hit'][3].mean())], 'hit10': [float(per['B0c']['hit'][10].mean()), float(per['LEAN']['hit'][10].mean())]}
        pop2 = pop.assign(lean_score=allscore)
        frames = [e._game_frame(pop2, s, m) for s in range(2021, 2026)]
        frame = pd.concat([f[0] for f in frames], ignore_index=True)
        y = np.concatenate([f[1] for f in frames])
        X = np.column_stack([frame.lean_score.to_numpy(float)] + ([frame[extra].to_numpy(float)] if extra else []))
        theta = e.fit_clogit(X, pd.factorize(frame.game_id)[0], y, e.PEN_GAME)
        market[m] = {'evaluation_dev_fit': res, 'production_other_utility': float(theta[0]), 'production_slope_on_anytime_logit': float(theta[1]),
                     'production_extra_standardised': dict(zip([c[:-2] for c in extra], [float(x) for x in theta[2:]]))}
    out['game_markets'] = market
    out['game_market_formula'] = ('P(player i is the first/last/longest-TD scorer in the game) = exp(k*s_i) / (exp(u) + sum_j exp(k*s_j)), s = anytime logit above (+ king extras), '
                                  'sum over all candidates of BOTH teams; "other" = exp(u)/(...) covers returns, defence and non-candidates')
    return out


def _slope(p, y):
    from numpy.linalg import lstsq
    z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    w = e.fit_logit(z.reshape(-1, 1), y, 0.0, n_unpenalised=1)
    return float(w[1])


def write_production(root):
    result = production_candidate(root)
    existing = json.loads(e.OUT.read_text(encoding='utf-8')) if e.OUT.exists() else {}
    existing['posthoc_production_candidate'] = result
    e.OUT.write_text(json.dumps(existing, indent=1, sort_keys=True), encoding='utf-8')
    return result
