"""Streamlit page: Live Value. Imported by app.py; all data access is read-only and every quote carries its retrieval time.

Rules enforced here:
  * a quote is shown as LIVE only when it was fetched in this render and is younger than MAX_AGE_S; otherwise it is labelled stale or not shown;
  * a contract is ACTIONABLE only with a fresh two-sided quote, a state the model supports (regulation), a pregame closing price, and positive expected value
    after the Kalshi fee and the uncertainty margin; otherwise it is THEORETICAL (a target price without a live signal) or INSUFFICIENT DATA;
  * the historical replay is always labelled as replay and says whether the frozen models saw that game when they were fitted.
No order is placed, previewed or simulated.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_nba_xgb'
MAX_AGE_S = 120.0
ET = 'America/New_York'


def _frozen():
    from . import live_value as LV
    p = OUT / 'live_models_frozen.pkl'
    return LV.load_frozen() if p.exists() else None


def _priors(date: str) -> pd.DataFrame | None:
    f = OUT / 'live' / f'forecast_{date}.csv'
    if not f.exists():
        return None
    d = pd.read_csv(f, dtype={'game_id': str})
    if 'mu_avail' not in d:
        return None
    return d.drop_duplicates('game_id').set_index('game_id')[['home', 'away', 'mu_base', 'mu_avail', 'T_pre', 'status', 'generated_utc']]


def _pregame_close(date: str, home: str, away: str):
    """Earliest captured pregame Kalshi moneyline mid for this game from today's capture file (None if not captured)."""
    f = OUT / 'live_capture' / f'capture_{date.replace("-", "")}.jsonl'
    if not f.exists():
        return None
    from . import kalshi
    key = f'{away}@{home}'
    best = None
    for line in f.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        k = r.get('kalshi', {}).get(key)
        espn = {e['home'] + e['away']: e for e in (r.get('espn') or [])}.get(home + away)
        if not k or not espn or espn['state'] != 'pre':
            continue
        mids = {}
        for m in k['moneyline']:
            try:
                mids[m['ticker'].rsplit('-', 1)[1]] = (float(m['bid']) + float(m['ask'])) / 2
            except (TypeError, ValueError):
                pass
        h, a = kalshi.CODE.get(home), kalshi.CODE.get(away)
        if h in mids and a in mids:
            best = (mids[h] / (mids[h] + mids[a]), r['captured_utc'])      # keep the latest pregame snapshot
    return best


def render():
    import streamlit as st
    st.header('Live Value')
    st.info('Compares the NBA Ensemble\'s own in-game fair prices with Kalshi quotes. The model does not read any quote when it makes Model A prices; '
            'Model B uses only the pregame closing price. Research status: see the Method & evidence tab. A theoretical target is not a signal; '
            'quotes are bid/ask, not guaranteed fills.')
    fz = _frozen()
    tabs = st.tabs(['Live games', 'Historical replay', 'Method & evidence'])
    with tabs[0]:
        _live(st, fz)
    with tabs[1]:
        _replay(st, fz)
    with tabs[2]:
        _evidence(st)


# --------------------------------------------------------------------------------------------- live
def _live(st, fz):
    from . import live_collector as LC, kalshi, live_value as LV, live_model as M, fair_value as FV
    today = pd.Timestamp.now(tz=ET).strftime('%Y-%m-%d')
    date = st.text_input('Game date (ET)', today)
    if st.button('Refresh now'):
        st.cache_data.clear()
    if fz is None:
        st.warning('Insufficient data: the frozen live models are not available (research_nba_xgb/live_models_frozen.pkl).')
        return
    try:
        espn, espn_t = LC.espn_state(date)
    except Exception as e:
        st.error(f'ESPN scoreboard unavailable ({type(e).__name__}). No live state, so no live valuation.')
        return
    st.caption(f'ESPN scoreboard retrieved {espn_t} UTC.')
    pri = _priors(date)
    if pri is None:
        st.warning('No saved pregame priors for this date (research_nba_xgb/live/forecast_<date>.csv with mu and total). Games below are shown without fair prices.')
    for e in espn:
        label = f"{e['away']} @ {e['home']}  |  {e['detail']}  |  {e['away_score']}-{e['home_score']}"
        with st.expander(label, expanded=(e['state'] == 'in')):
            if e['state'] == 'post':
                st.write('Final. Nothing to price.')
                continue
            if e['state'] == 'pre':
                st.write('Not started: only a pregame valuation is possible.')
            gid = e['event_id']
            if pri is None or gid not in pri.index:
                st.write('**INSUFFICIENT DATA** — no pregame prior saved for this game.')
                continue
            pr = pri.loc[gid]
            pc = _pregame_close(date, e['home'], e['away'])
            st.write(f"Pregame prior (saved {pr.generated_utc[:19]} UTC, status {pr.status}): expected margin {pr.mu_avail:+.1f} (home), expected total {pr.T_pre:.1f}."
                     + (f" Kalshi pregame close (home win) {pc[0]:.1%}, captured {pc[1][:19]} UTC." if pc else ' No pregame Kalshi close captured for this game.'))
            if e['state'] != 'in' or not e['period'] or e['period'] > 4:
                st.write('Live pricing needs a game in regulation (periods 1-4). ' + ('Overtime is not supported.' if e['period'] and e['period'] > 4 else ''))
                continue
            row = LV.state_row(int(e['period']), e['clock'], e['home_score'], e['away_score'], {'mu_avail': pr.mu_avail, 'mu_base': pr.mu_base, 'mu_close': np.nan}, pr.T_pre, L=0.0)
            if row is None:
                st.write('State not supported.')
                continue
            models = fz['models']
            pA = float(M.p_home_win(models['A_full'], pd.DataFrame([row]))[0])
            c1, c2 = st.columns(2)
            c1.metric('Model A (independent) home win', f'{pA:.1%}')
            if pc:
                mu_k = LV.mu_from_close_prob(pc[0], fz['sigma_g'])
                rowB = row.copy()
                rowB['mu_close'] = mu_k
                pB = float(M.p_home_win(models['B_close'], pd.DataFrame([rowB]))[0])
                c2.metric('Model B (closing-informed) home win', f'{pB:.1%}')
            else:
                rowB = None
                c2.metric('Model B (closing-informed)', 'needs pregame close')
            st.caption(f"State: {int(row.tau // 60)}:{int(row.tau % 60):02d} of regulation left, margin {row.m:+.0f} (home). Lineup effect not available live (set to neutral). "
                       f"Lead-dependent drift {models['A_full'].am:+.3f} per unit lead per share of game remaining.")
            # Kalshi quotes
            try:
                mk = kalshi.list_markets(lambda *a: None) if 'kmk' not in st.session_state or time.time() - st.session_state.get('kmk_t', 0) > 600 else st.session_state['kmk']
                st.session_state['kmk'], st.session_state['kmk_t'] = mk, time.time()
                evs = {kalshi.parse_event(x)[1:]: x for x in mk.event_ticker.unique() if kalshi.parse_event(x) and kalshi.parse_event(x)[0] == date}
                et = evs.get(tuple(sorted([kalshi.CODE[e['home']], kalshi.CODE[e['away']]]))) or next((v for k, v in evs.items() if set(k) == {kalshi.CODE[e['home']], kalshi.CODE[e['away']]}), None)
            except Exception as ex:
                et = None
                st.warning(f'Kalshi market list unavailable ({type(ex).__name__}).')
            if not et:
                st.write('No Kalshi event found for this game: theoretical fair prices only.')
                continue
            t0 = time.time()
            suffix = et.split('-', 1)[1]
            contracts = []
            for series, kind in (('KXNBAGAME', 'moneyline'), ('KXNBASPREAD', 'spread'), ('KXNBATOTAL', 'total')):
                for m in LC.kalshi_event_markets(series, f'{series}-{suffix}'):
                    try:
                        bid, ask = float(m['yes_bid_dollars']), float(m['yes_ask_dollars'])
                    except (KeyError, TypeError, ValueError):
                        bid = ask = None
                    code = m['ticker'].rsplit('-', 1)[1]
                    team = ''.join(ch for ch in code if ch.isalpha())
                    side = 'home' if team == kalshi.CODE[e['home']] else 'away' if team == kalshi.CODE[e['away']] else None
                    contracts.append({'ticker': m['ticker'], 'kind': kind, 'team_side': side, 'strike': m.get('floor_strike'), 'bid': bid, 'ask': ask, 'label': m.get('yes_sub_title')})
            age = time.time() - t0
            st.caption(f'Kalshi quotes retrieved {pd.Timestamp.now(tz="UTC").isoformat()[:19]} UTC ({len(contracts)} contracts). Freshness is our retrieval time; thin markets can hold older resting quotes.')
            primary = rowB if rowB is not None else row
            pm = models['B_close'] if rowB is not None else models['A_full']
            name = 'B_close' if rowB is not None else 'A_full'
            margin, total = M.simulate(pm, primary, n=200_000, seed=1)
            tbl = LV.value_contracts(contracts, margin, total, name, fz, float(row.tau), min(age, 5.0), MAX_AGE_S)
            tbl['label'] = [c['label'] for c in contracts]
            tbl['verdict'] = tbl.status.str.upper()
            if rowB is None:
                tbl['verdict'] = 'THEORETICAL (no pregame close)'
            show = tbl[(tbl.fair_yes > 0.03) & (tbl.fair_yes < 0.97)].sort_values('ev_conservative', ascending=False)
            st.write(f"Valuation model: **{'B (closing-informed)' if rowB is not None else 'A (independent)'}**, {len(margin):,} joint draws "
                     f"(simulation error ≤ {tbl.mc_error.max():.3f}). Model uncertainty (1 SE) shown separately.")
            st.dataframe(show[['label', 'kind', 'fair_yes', 'model_se', 'bid', 'ask', 'action', 'ev_at_quote', 'ev_conservative', 'max_price', 'verdict', 'why']]
                         .rename(columns={'fair_yes': 'fair P(yes)', 'model_se': 'model SE', 'ev_at_quote': 'EV/contract', 'ev_conservative': 'EV conservative',
                                          'max_price': 'highest price still +EV'}).head(25), use_container_width=True)
            if rowB is not None:
                other = LV.value_contracts(contracts, *M.simulate(models['A_full'], row, n=100_000, seed=2), 'A_full', fz, float(row.tau), min(age, 5.0), MAX_AGE_S)
                agree = (other.set_index('ticker').action.reindex(show.ticker).values == show.action.values).mean() if len(show) else float('nan')
                st.caption(f'Independent Model A chooses the same side on {agree:.0%} of the rows shown (disagreement is a reason for caution).')
            _manual_sportsbook(st, margin, total, e)


def _manual_sportsbook(st, margin, total, e):
    from . import fair_value as FV
    if st.checkbox('Enter a sportsbook quote you can see (manual; nothing is fetched)', key='sb_toggle' + e['event_id']):
        c = st.columns(4)
        kind = c[0].selectbox('Market', ['Moneyline', 'Spread', 'Total'], key='sb_kind' + e['event_id'])
        side = c[1].selectbox('Side', [e['home'], e['away']] if kind != 'Total' else ['Over', 'Under'], key='sb_side' + e['event_id'])
        line = c[2].number_input('Line (home perspective for spreads)', value=0.0, step=0.5, key='sb_line' + e['event_id'])
        odds = c[3].number_input('American odds', value=-110, step=5, key='sb_odds' + e['event_id'])
        if kind == 'Moneyline':
            s = 'home_ml' if side == e['home'] else 'away_ml'
        elif kind == 'Spread':
            s = ('home_spread', line) if side == e['home'] else ('away_spread', -line)
        else:
            s = ('over' if side == 'Over' else 'under', line)
        pr = FV.side_probabilities(margin, total, s)
        ev = FV.ev_american(pr['win'], pr['push'], odds)
        st.write(f"P(win) {pr['win']:.1%}, P(push) {pr['push']:.1%}. EV per unit staked at {odds:+.0f}: **{ev:+.3f}**. "
                 f"Fair odds {FV.fair_american(pr['win'], pr['push']):+.0f}; worst odds still at EV ≥ 0: {FV.min_american(pr['win'], pr['push'], 0.0):+.0f}. "
                 "Manual quote: freshness and availability are your responsibility.")


# --------------------------------------------------------------------------------------------- replay
def _replay(st, fz):
    from . import live_value as LV, live_model as M
    st.warning('HISTORICAL REPLAY — recorded 2025-26 data, not live. Quotes are the recorded 1-minute bid/ask of Kalshi winner contracts, not fills.')
    p = OUT / 'inplay_states.parquet'
    if fz is None or not p.exists():
        st.write('Insufficient data: replay table or frozen models missing.')
        return
    S = pd.read_parquet(p)
    S = S.dropna(subset=['k_pre', 'h_bid', 'h_ask'])
    date = st.selectbox('Date', sorted(S.game_date.unique())[::-1])
    games = S[S.game_date == date].game_id.unique()
    gid = st.selectbox('Game', games)
    g = S[S.game_id == gid].sort_values('ts').reset_index(drop=True)
    seen = date < '2026-02-01'
    st.caption(('In-sample: the frozen models were fitted on this date. ' if seen else 'Out-of-sample: the frozen models were fitted only on earlier dates. ') + 'Replay uses regulation states only.')
    i = st.slider('Minute of the game (2-minute steps)', 0, len(g) - 1, min(len(g) - 1, len(g) // 2))
    r = g.iloc[i]
    mu_k = LV.mu_from_close_prob(r.k_pre, fz['sigma_g'])
    base = pd.Series({'t': r.t, 'tau': r.tau, 'm': r.m, 'S': r.S, 'L': 0.0, 'T_pre': r.T_pre, 'mu_avail': r.mu_avail, 'mu_base': r.mu_base, 'mu_close': mu_k})
    pA = float(M.p_home_win(fz['models']['A_full'], pd.DataFrame([base]))[0])
    pB = float(M.p_home_win(fz['models']['B_close'], pd.DataFrame([base]))[0])
    margin, total = M.simulate(fz['models']['B_close'], base, n=150_000, seed=3)
    contract = [{'ticker': 'home_ml', 'kind': 'moneyline', 'team_side': 'home', 'strike': None, 'bid': r.h_bid, 'ask': r.h_ask}]
    v = LV.value_contracts(contract, margin, total, 'B_close', fz, float(r.tau), 60.0).iloc[0]
    c = st.columns(4)
    c[0].metric('Score (home margin)', f'{r.m:+.0f}')
    c[1].metric('Time left', f'{int(r.tau // 60)}:{int(r.tau % 60):02d}')
    c[2].metric('Kalshi home bid/ask', f'{r.h_bid:.2f} / {r.h_ask:.2f}')
    c[3].metric('Pregame close (home)', f'{r.k_pre:.1%}')
    st.write(f"Model A fair {pA:.1%} · Model B fair {pB:.1%} (± {v.model_se:.1%}) · Kalshi mid {r.k_mid:.1%}. "
             f"Side {v.action}, EV/contract {v.ev_at_quote:+.3f}, conservative {v.ev_conservative:+.3f}, highest price still +EV {v.max_price}. "
             f"**{str(v.status).upper()}** ({v.why or 'conservative EV positive'}). Outcome: home {'won' if r.final_margin > 0 else 'lost'} by {r.final_margin:+.0f}.")
    g['A fair'] = M.p_home_win(fz['models']['A_full'], g.assign(L=0.0))
    g['B fair'] = M.p_home_win(fz['models']['B_close'], g.assign(mu_close=[LV.mu_from_close_prob(x, fz['sigma_g']) for x in g.k_pre]))
    st.line_chart(g.set_index('t')[['k_mid', 'A fair', 'B fair']].rename(columns={'k_mid': 'Kalshi mid'}))


# --------------------------------------------------------------------------------------------- evidence
def _evidence(st):
    f = OUT / 'LIVE_FINAL_RESULTS.json'
    st.write('**Research status**')
    if f.exists():
        r = json.loads(f.read_text(encoding='utf-8'))
        st.write(f"Final window {r['dates'][0]} to {r['dates'][1]}: {r['games']} games, {r['rows']:,} states. Mean log loss — Kalshi {r['mean_ll']['C']:.4f}, "
                 f"Model A {r['mean_ll']['A']:.4f}, Model B {r['mean_ll']['B_K']:.4f}.")
        st.json({k: r[k] for k in ('paired_ll', 'H1_encompassing_B_K', 'H2b_correction', 'H2c')})
    else:
        st.write('The pre-registered final-window evaluation has not been run. Until it has, nothing on this page is evidence of an edge.')
    for name in ('NBA_LIVE_PREREGISTRATION.md', 'NBA_LIVE_RESULTS.md'):
        p = ROOT / 'docs' / name
        if p.exists():
            with st.expander(name):
                st.markdown(p.read_text(encoding='utf-8'))
