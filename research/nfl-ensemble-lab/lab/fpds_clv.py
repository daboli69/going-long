"""Descriptive forward quote tracking only. No API, outcome fit or selection.

All contract-level rows remain private. Last-archived pregame quotes are a
closing proxy, never asserted to be the actual bookmaker close.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from .fpds_research.common import ROOT,now,stamp,read,write_once,private_error


def eligible_quotes(quotes,row,decision):
    """Exact player/game/period and observation time, never a later quote."""
    if quotes.empty:return quotes.copy()
    q=quotes.copy();ko=pd.Timestamp(row['kickoff_utc']);decision=pd.Timestamp(decision)
    for col in ('quote_time','available_at','kickoff'):
        q[col]=pd.to_datetime(q[col],utc=True,errors='coerce',format='mixed')
    mask=(q.gsis_id.eq(row['pid'])&q.stat.eq(row['stat'])&q.home.eq(row['home_team'])&q.away.eq(row['away_team'])&
          q.period.eq('FULL')&q.pregame_verified&(q.kickoff-ko).abs().le(pd.Timedelta(minutes=15))&
          q.available_at.le(decision)&q.quote_time.le(decision)&q.available_at.lt(ko)&q.quote_time.lt(ko))
    q=q[mask].copy()
    from .props.amendment2.sheets import classify
    traditional=pd.Series([classify(b,bool(f))=='alternate' for b,f in zip(q.book,q.dfs)],index=q.index,dtype=bool)
    q=q.loc[traditional]
    return q.sort_values(['quote_time','available_at']).drop_duplicates(['book','line'],keep='last')


def track(row,quotes,asof):
    ko=pd.Timestamp(row['kickoff_utc']);asof=pd.Timestamp(asof)
    result={k:row.get(k) for k in ('game_id','pid','stat','arm','created_at','kickoff_utc','consensus_line')}
    if ko>asof:return result|{'status':'pending kickoff; no closing comparison'}
    if row['stat'] in ('first_td','anytime_td'):
        return result|{'status':'binary/offensive-only contract not verified; no price-edge comparison'}
    entry=eligible_quotes(quotes,row,row['created_at'])
    line=pd.to_numeric(pd.Series([row.get('consensus_line')]),errors='coerce').iloc[0]
    if not np.isfinite(line):return result|{'status':'no recorded consensus entry line'}
    entry=entry[pd.to_numeric(entry.line,errors='coerce').eq(line)]
    if entry.empty:return result|{'status':'entry quote not recoverable from authorized archives'}
    # Same alphabetically first representative as the saved consensus comparison.
    e=entry.sort_values(['book','quote_time'],ascending=[True,False]).iloc[0]
    entry_age=(pd.Timestamp(row['created_at'])-e.quote_time).total_seconds()/3600
    if entry_age>24:return result|{'status':'stale entry; comparison unavailable'}
    close=eligible_quotes(quotes,row,min(asof,ko-pd.Timedelta(microseconds=1)))
    close=close[close.book.eq(e.book)]
    if close.empty:return result|{'status':'no same-book pregame quote'}
    latest=close[close.quote_time.eq(close.quote_time.max())]
    values=pd.to_numeric(latest.line,errors='coerce').dropna().unique()
    if len(values)!=1:return result|{'status':'ambiguous/missing latest alternate lines; closing proxy unavailable','book':e.book}
    c=close.sort_values(['quote_time','available_at']).iloc[-1]
    age=(ko-c.quote_time).total_seconds()/3600
    if age>24:return result|{'status':'no quote within24h of kickoff; closing proxy unavailable','book':e.book,'last_quote_age_at_kickoff_hours':age}
    closing=float(c.line)
    out=result|{'status':'descriptive last-archived pregame proxy; actual close unverified','book':e.book,
                'entry_line':float(line),'closing_proxy_line':closing,'line_change':closing-float(line),
                'entry_quote_time':e.quote_time.isoformat(),'closing_proxy_quote_time':c.quote_time.isoformat(),
                'last_quote_age_at_kickoff_hours':age,'same_numeric_contract':bool(closing==line),
                'interpretation':'line movement only; no return, staking or tradable-edge claim'}
    # Quote prices only on the identical numerical contract. Never manufacture a price.
    if closing==line:
        for side in ('over','under'):
            a=pd.to_numeric(pd.Series([e.get(side+'_odds')]),errors='coerce').iloc[0]
            b=pd.to_numeric(pd.Series([c.get(side+'_odds')]),errors='coerce').iloc[0]
            if np.isfinite(a) and np.isfinite(b) and abs(a)>=100 and abs(b)>=100:
                out[side+'_entry_american']=float(a);out[side+'_closing_proxy_american']=float(b)
        keys=('over_entry_american','under_entry_american','over_closing_proxy_american','under_closing_proxy_american')
        if all(k in out for k in keys):
            from .market81 import american_to_prob
            a,b,c,d=(float(american_to_prob(out[k])) for k in keys)
            out['entry_over_probability_novig']=a/(a+b)
            out['closing_proxy_over_probability_novig']=c/(c+d)
            out['over_probability_movement']=out['closing_proxy_over_probability_novig']-out['entry_over_probability_novig']
    return out


def run(asof=None):
    from .props.lines import archived_lines
    asof=pd.Timestamp.now(tz='UTC') if asof is None else pd.Timestamp(asof)
    quotes=archived_lines(asof=asof);rows=[]
    for directory in (ROOT/'weekly').glob('2026_w*_r*'):
        if not (directory/'FORECAST.json').exists():continue
        frame=pd.read_csv(directory/'projections.csv')
        for r in frame[frame.arm.eq('frozen')].to_dict('records'):
            rows.append({'forecast_revision':directory.name,**track(r,quotes,asof)})
    directory=ROOT/'clv'/stamp();directory.mkdir(parents=True,exist_ok=False)
    frame=pd.DataFrame(rows);frame.to_parquet(directory/'CONTRACT_TRACKING_PRIVATE.parquet',index=False)
    result={'created_at':now(),'path':str(directory),'rows':len(frame),'status_counts':frame.status.value_counts().to_dict() if len(frame) else {},
            'scope':'descriptive archived quote tracking only; no fit, tuning, actual-close assumption or betting-return claim'}
    write_once(directory/'SUMMARY.json',result)
    return result


if __name__=='__main__':
    try:
        result=run();print('Private forward quote tracking saved: '+result['path'])
    except Exception:
        private_error('quote_tracking');raise SystemExit('Forward quote tracking failed; see ignored private error log')
