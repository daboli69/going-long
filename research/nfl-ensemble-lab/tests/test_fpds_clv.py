"""Synthetic quote contracts only; no real CSVs, prices, API or outcome fit."""
import pandas as pd
from lab.fpds_clv import track


def fixtures():
    row={'game_id':'synthetic','pid':'00-synthetic','stat':'pass_yds','arm':'frozen','created_at':'2026-10-20T12:00Z',
         'kickoff_utc':'2026-10-22T12:00Z','home_team':'BUF','away_team':'NE','consensus_line':150.5}
    base={'gsis_id':'00-synthetic','stat':'pass_yds','home':'BUF','away':'NE','period':'FULL','pregame_verified':True,
          'kickoff':row['kickoff_utc'],'book':'fixture','dfs':False,'over_odds':-110,'under_odds':-110}
    quotes=pd.DataFrame([base|{'quote_time':'2026-10-20T11:00Z','available_at':'2026-10-20T11:01Z','line':150.5},
                        base|{'quote_time':'2026-10-22T11:00Z','available_at':'2026-10-22T11:01Z','line':160.5},
                        base|{'quote_time':'2026-10-22T13:00Z','available_at':'2026-10-22T13:01Z','line':999.5}])
    return row,quotes


def test_pending_before_kickoff_and_no_future_quote():
    r,q=fixtures();assert track(r,q,'2026-10-21T00:00Z')['status'].startswith('pending')
    out=track(r,q,'2026-10-23T00:00Z')
    assert out['closing_proxy_line']==160.5 and out['line_change']==10
    assert not out['same_numeric_contract'] and 'over_closing_proxy_american' not in out


def test_stale_and_wrong_kickoff_unavailable():
    r,q=fixtures();out=track(r,q.iloc[:1],'2026-10-23T00:00Z')
    assert out['status'].startswith('no quote within24h')
    q['kickoff']='2026-10-21T12:00Z'
    assert track(r,q,'2026-10-23T00:00Z')['status'].startswith('entry quote not recoverable')


def test_ambiguous_alternates_do_not_invent_a_close():
    r,q=fixtures();alternate=q.iloc[[1]].copy();alternate['line']=170.5
    out=track(r,pd.concat([q,alternate],ignore_index=True),'2026-10-23T00:00Z')
    assert out['status'].startswith('ambiguous/missing')


def test_identical_contract_can_track_real_two_sided_quote_movement():
    r,q=fixtures();q.loc[1,['line','over_odds','under_odds']]=[150.5,-120,100]
    out=track(r,q,'2026-10-23T00:00Z')
    assert out['same_numeric_contract'] and out['entry_over_probability_novig']==.5
    assert out['over_probability_movement']>0
