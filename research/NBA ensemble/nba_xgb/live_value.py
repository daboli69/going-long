"""Calculation layer for live valuation: game state + pregame priors + (optional) Kalshi quotes -> fair prices, EV after fees, target prices, status.

Used identically by the Live Value page, the historical replay and the final evaluation. Pure functions around the frozen models; no network access here.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats
from . import fair_value as FV, live_model as M, pbp
from .avail_study import OUT

REG = 2880.0
TAU_EDGES = [0, 360, 720, 1440, 2160, 2880]


def load_frozen():
    return pd.read_pickle(OUT / 'live_models_frozen.pkl')


def clock_to_seconds(display: str) -> float:
    s = str(display)
    if ':' in s:
        mm, ss = s.split(':')
        return float(mm) * 60 + float(ss)
    return float(s)


def state_row(period: int, clock_display: str, home: int, away: int, mu: dict, T_pre: float, L: float = 0.0) -> pd.Series | None:
    """Regulation state as a row for the model. Returns None in overtime or before the game starts."""
    if period < 1 or period > 4:
        return None
    el = float(pbp.elapsed(np.array([float(period)]), np.array([clock_to_seconds(clock_display)]))[0])
    return pd.Series({'t': el, 'tau': REG - el, 'm': float(home - away), 'S': float(home + away), 'L': L, 'T_pre': T_pre, **mu})


def mu_from_close_prob(p_home_close: float, sigma_g: float) -> float:
    return float(sigma_g * stats.norm.ppf(np.clip(p_home_close, 0.02, 0.98)))


def se_total(frozen: dict, model: str, tau: float) -> float:
    b = int(np.clip(np.searchsorted(TAU_EDGES, tau, side='left') - 1, 0, len(TAU_EDGES) - 2))
    par = frozen['se'].get(model, {})
    sd = par.get(b, np.mean(list(par.values())) if par else 0.02)
    slack = frozen['slack'].get(model, 0.015)
    return float(np.sqrt(sd ** 2 + slack ** 2))


def draws(params: M.Params, row: pd.Series, n=200_000, seed=0):
    return M.simulate(params, row, n=n, seed=seed)


def mc_error(p: float, n: int) -> float:
    """Monte Carlo standard error of a simulated probability (separate from model uncertainty)."""
    return float(np.sqrt(max(p * (1 - p), 1e-12) / n))


def contract_event(kind: str, team_side: str, strike: float | None, margin: np.ndarray, total: np.ndarray) -> np.ndarray:
    """Boolean outcome of the YES side of a Kalshi game contract."""
    if kind == 'moneyline':
        return margin > 0 if team_side == 'home' else margin < 0
    if kind == 'spread':           # "<team> wins by more than <strike>"
        return margin > strike if team_side == 'home' else -margin > strike
    if kind == 'total':            # "Over <strike> points"
        return total > strike
    raise ValueError(kind)


def value_contracts(contracts: list, margin, total, model: str, frozen: dict, tau: float, age_s: float | None, max_age_s=120.0, n_contracts=100):
    """contracts: list of dicts with ticker, kind, team_side, strike, bid, ask (dollars). Returns one row per contract."""
    se = se_total(frozen, model, tau)
    rows = []
    for c in contracts:
        ev = contract_event(c['kind'], c.get('team_side'), c.get('strike'), margin, total)
        p = float(ev.mean())
        v = FV.value_kalshi_yes(p, se, c.get('bid'), c.get('ask'), age_s, max_age_s, contracts=n_contracts)
        rows.append({'ticker': c['ticker'], 'kind': c['kind'], 'strike': c.get('strike'), 'team_side': c.get('team_side'),
                     'fair_yes': p, 'mc_error': mc_error(p, len(margin)), 'model_se': se, 'bid': c.get('bid'), 'ask': c.get('ask'),
                     'action': v.side, 'quote_price': v.quote, 'ev_at_quote': v.ev_at_quote, 'ev_conservative': v.ev_at_quote_conservative,
                     'max_price': v.max_price, 'status': v.status, 'why': '; '.join(v.reasons)})
    return pd.DataFrame(rows)
