"""Fair values, expected value and minimum acceptable prices from a final-score distribution. Pure functions; no market access, no orders.

Conventions
-----------
margin = home points - away points over the whole game including overtime; total = both teams' points including overtime.
A contract or bet is defined by a *side* of a line:
    'home_ml' / 'away_ml'            moneyline
    ('home_spread', k)               home team covers if margin + k > 0   (k is the home line, e.g. -4.5 means home gives 4.5)
    ('away_spread', k)               away team covers if -margin + k > 0
    ('over', x) / ('under', x)       total > x / total < x
Pushes occur only on whole-number lines. Kalshi spreads and totals use half-point strikes, so pushes are zero there.

Kalshi fee: ceil(0.07 * contracts * P * (1-P) to the cent) for takers (per secondary sources; the official fee schedule page could not be fetched and must be
confirmed). Series with 'quadratic_with_maker_fees' charge makers 0.0175 instead of 0.07. A YES contract at price a pays 1 if the event occurs; a NO
contract at price b = 1 - yes_bid pays 1 if it does not. Quoted bid/ask are not fills: depth and queue position are unknown from candle data.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np

TAKER_RATE = 0.07
MAKER_RATE = 0.0175


def kalshi_fee(price: float, contracts: int = 1, rate: float = TAKER_RATE) -> float:
    """Total fee in dollars for an order, rounded up to the next cent."""
    if not 0.0 < price < 1.0:
        return 0.0
    return math.ceil(rate * contracts * price * (1.0 - price) * 100.0 - 1e-9) / 100.0


def side_probabilities(margin: np.ndarray, total: np.ndarray, side) -> dict:
    """Win / push / loss probabilities of one side of one line from joint draws."""
    if side == 'home_ml':
        w, p = margin > 0, np.zeros_like(margin, bool)
    elif side == 'away_ml':
        w, p = margin < 0, np.zeros_like(margin, bool)
    else:
        kind, k = side
        if kind == 'home_spread':
            v = margin + k
        elif kind == 'away_spread':
            v = -margin + k
        elif kind == 'over':
            v = total - k
        elif kind == 'under':
            v = k - total
        else:
            raise ValueError(kind)
        w, p = v > 0, v == 0
    pw, pp = float(w.mean()), float(p.mean())
    return {'win': pw, 'push': pp, 'loss': 1.0 - pw - pp}


# ------------------------------------------------------------------ sportsbook-style odds
def american_profit(odds: float) -> float:
    """Profit on a 1-unit stake at American odds."""
    return odds / 100.0 if odds > 0 else 100.0 / abs(odds)


def ev_american(win: float, push: float, odds: float) -> float:
    return win * american_profit(odds) - (1.0 - win - push)


def fair_american(win: float, push: float = 0.0) -> float:
    """American odds at which EV is exactly zero."""
    loss = 1.0 - win - push
    b = loss / win
    return 100.0 * b if b >= 1.0 else -100.0 / b


def min_american(win: float, push: float, required_ev: float = 0.0) -> float:
    """Worst American odds that still give EV >= required_ev per unit staked (uses the supplied win probability)."""
    loss = 1.0 - win - push
    b = (required_ev + loss) / win
    return 100.0 * b if b >= 1.0 else -100.0 / b


# ------------------------------------------------------------------ Kalshi contracts
def ev_buy_yes(p_yes: float, ask: float, contracts: int = 1, rate: float = TAKER_RATE) -> float:
    fee = kalshi_fee(ask, contracts, rate) / contracts
    return p_yes - ask - fee


def ev_buy_no(p_yes: float, yes_bid: float, contracts: int = 1, rate: float = TAKER_RATE) -> float:
    no_price = 1.0 - yes_bid
    fee = kalshi_fee(no_price, contracts, rate) / contracts
    return (1.0 - p_yes) - no_price - fee


def max_yes_price(p_yes: float, required_ev: float = 0.0, contracts: int = 1, rate: float = TAKER_RATE):
    """Highest YES price (cent grid) at which EV >= required_ev given p_yes; None if none exists."""
    best = None
    for c in range(1, 100):
        a = c / 100.0
        if ev_buy_yes(p_yes, a, contracts, rate) >= required_ev - 1e-12:
            best = a
    return best


def max_no_price(p_yes: float, required_ev: float = 0.0, contracts: int = 1, rate: float = TAKER_RATE):
    """Highest NO price at which EV >= required_ev, expressed as the NO price (YES bid = 1 - price)."""
    return max_yes_price(1.0 - p_yes, required_ev, contracts, rate)


@dataclass
class Valuation:
    side: str
    p_model: float
    p_low: float             # conservative probability after the uncertainty margin
    se: float
    fair_price: float
    quote: float | None
    ev_at_quote: float | None
    ev_at_quote_conservative: float | None
    max_price: float | None  # highest price still positive EV on the conservative probability
    status: str
    reasons: list


def value_kalshi_yes(p_yes: float, se: float, bid: float | None, ask: float | None, quote_age_s: float | None,
                     max_age_s: float = 120.0, z: float = 1.0, contracts: int = 1, rate: float = TAKER_RATE) -> Valuation:
    """Value both ways on a YES/NO Kalshi contract. The bet is actionable only with a fresh, two-sided, executable quote and positive conservative EV."""
    p_lo = max(0.0, p_yes - z * se)
    p_hi = min(1.0, p_yes + z * se)
    reasons = []
    if ask is None or bid is None:
        return Valuation('none', p_yes, p_lo, se, p_yes, None, None, None, max_yes_price(p_lo, 0.0, contracts, rate), 'theoretical',
                         ['no executable two-sided quote'])
    stale = quote_age_s is None or quote_age_s > max_age_s
    ev_yes = ev_buy_yes(p_yes, ask, contracts, rate)
    ev_no = ev_buy_no(p_yes, bid, contracts, rate)
    ev_yes_c = ev_buy_yes(p_lo, ask, contracts, rate)
    ev_no_c = ev_buy_no(p_hi, bid, contracts, rate)
    if ev_yes >= ev_no:
        side, q, ev, evc, maxp = 'buy_yes', ask, ev_yes, ev_yes_c, max_yes_price(p_lo, 0.0, contracts, rate)
        fair = p_yes
    else:
        side, q, ev, evc, maxp = 'buy_no', 1.0 - bid, ev_no, ev_no_c, max_no_price(p_hi, 0.0, contracts, rate)
        fair = 1.0 - p_yes
    if stale:
        reasons.append('quote older than the freshness limit or age unknown')
    if evc <= 0:
        reasons.append('conservative expected value is not positive after fee and uncertainty margin')
    status = 'actionable' if (not stale and evc > 0) else ('theoretical' if stale else 'no edge')
    return Valuation(side, p_yes, p_lo, se, fair, q, ev, evc, maxp, status, reasons)
