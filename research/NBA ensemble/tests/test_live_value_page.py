"""The Live Value page renders inside the real app with mocked ESPN/Kalshi data and never labels a missing or stale quote as live."""
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / 'research_nba_xgb' / 'live_models_frozen.pkl').exists(), reason='frozen live models not present')


def _patch(monkeypatch, bids=(0.40, 0.42), pregame=True):
    from nba_xgb import live_collector as LC, kalshi, live_value_page as P
    today = pd.Timestamp.now(tz='America/New_York')
    date = today.strftime('%Y-%m-%d')
    ev = {'event_id': '999000001', 'start': '2026-10-30T00:00Z', 'state': 'in', 'detail': 'Q3 6:00', 'period': 3, 'clock': '6:00', 'clock_s': 360.0,
          'home': 'ATL', 'away': 'CLE', 'home_score': 70, 'away_score': 60}
    monkeypatch.setattr(LC, 'espn_state', lambda d: ([ev], pd.Timestamp.now(tz='UTC').isoformat()))
    pri = pd.DataFrame({'home': ['ATL'], 'away': ['CLE'], 'mu_base': [2.0], 'mu_avail': [2.5], 'T_pre': [224.0], 'status': ['PREGAME'],
                        'generated_utc': ['2026-10-29T22:15:00+00:00']}, index=['999000001'])
    monkeypatch.setattr(P, '_priors', lambda d: pri)
    monkeypatch.setattr(P, '_pregame_close', lambda d, h, a: (0.62, '2026-10-29T23:00:00+00:00') if pregame else None)
    suffix = today.strftime('%y%b%d').upper() + 'CLEATL'
    monkeypatch.setattr(kalshi, 'list_markets', lambda log=print: pd.DataFrame({'event_ticker': ['KXNBAGAME-' + suffix]}))
    mkts = [{'ticker': f'KXNBAGAME-{suffix}-ATL', 'yes_bid_dollars': str(bids[0]), 'yes_ask_dollars': str(bids[1]), 'floor_strike': None, 'yes_sub_title': 'Atlanta'},
            {'ticker': f'KXNBASPREAD-{suffix}-ATL8', 'yes_bid_dollars': '0.30', 'yes_ask_dollars': '0.32', 'floor_strike': 7.5, 'yes_sub_title': 'Atlanta wins by over 7.5'},
            {'ticker': f'KXNBATOTAL-{suffix}-232', 'yes_bid_dollars': '0.49', 'yes_ask_dollars': '0.51', 'floor_strike': 231.5, 'yes_sub_title': 'Over 231.5 points'}]
    monkeypatch.setattr(LC, 'kalshi_event_markets', lambda series, et: [m for m in mkts if m['ticker'].startswith(series)])
    return date


def run_page(monkeypatch, **kw):
    from streamlit.testing.v1 import AppTest
    _patch(monkeypatch, **kw)
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value('Live Value').run()
    return at


def test_page_renders_and_shows_fair_prices_with_sources(monkeypatch):
    at = run_page(monkeypatch)
    assert not at.exception, at.exception
    text = ' '.join(x.value for x in at.markdown) + ' '.join(x.value for x in at.caption)
    assert 'Live Value' in ' '.join(h.value for h in at.header)
    assert 'Kalshi quotes retrieved' in text                      # retrieval time is always displayed
    assert any('Model A' in m.label for m in at.metric)
    assert len(at.dataframe) >= 1


def test_without_pregame_close_nothing_is_called_actionable(monkeypatch):
    at = run_page(monkeypatch, pregame=False)
    assert not at.exception, at.exception
    frames = [d.value for d in at.dataframe]
    assert frames and all('ACTIONABLE' not in ' '.join(f.verdict.astype(str)) for f in frames)
    assert all(f.verdict.str.startswith('THEORETICAL').all() for f in frames)


def test_page_survives_missing_priors(monkeypatch):
    from nba_xgb import live_value_page as P
    from streamlit.testing.v1 import AppTest
    _patch(monkeypatch)
    monkeypatch.setattr(P, '_priors', lambda d: None)
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value('Live Value').run()
    assert not at.exception, at.exception
    assert any('No saved pregame priors' in w.value for w in at.warning)
