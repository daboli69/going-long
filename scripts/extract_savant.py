"""Fetch the live Savant season API; CSV absence is explicit, never a fake 2026 file."""
import csv
import io
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from build_pipeline import atomic_json

ROOT = Path(__file__).resolve().parents[1]


def public_get(url, **kwargs):
    """One bounded retry for transient failures of these free public sources."""
    for attempt in range(2):
        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            transient = isinstance(exc, (requests.Timeout, requests.ConnectionError)) or status in (429, 500, 502, 503, 504)
            if not transient or attempt:
                raise
            from parlay_feed import retry_after_seconds
            headers = getattr(getattr(exc, 'response', None), 'headers', {})
            delay = max(2, retry_after_seconds(headers.get('Retry-After')))
            print(f'[savant] transient {status or type(exc).__name__}; retry 2/2 in {delay:g}s', flush=True)
            time.sleep(delay)


def failure_reason(exc):
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    return f'{type(exc).__name__} HTTP {status}' if status else type(exc).__name__


def build(season=None):
    season = season or int(os.getenv('SEASON', datetime.now().year))
    now = datetime.now(timezone.utc).isoformat()
    output = {'season':season,'observed_at':now,'sources':{},'team_context':[], 'usage':'Secondary descriptive context only. Acquisition time is not historical availability.'}
    base = 'https://nflsavant.com'
    try:
        r = public_get(base+'/api/league',params={'season':season},timeout=30);body=r.json()
        if body.get('season') != season or not isinstance(body.get('teams'),list):raise ValueError('Unexpected Savant season schema')
        output['team_context']=[{'team':t['abbr'],'completed_wins_losses':t.get('wins',0)+t.get('losses',0),'metrics':{k:t.get('m',{}).get(k) for k in ('net_epa','proe','sec_play','plays_g','pass_epa','def_pass_epa','def_rush_epa')}} for t in body['teams']]
        output['sources']['savant_api']={'status':'loaded','url':r.url,'teams':len(output['team_context']),'week':body.get('week')}
    except (requests.RequestException,ValueError,KeyError) as exc:
        output['sources']['savant_api']={'status':'unavailable','reason':failure_reason(exc)}
    url=f'https://pub-e9a6e73e336047fba26374ae44334139.r2.dev/pbp-{season}.csv'
    rows=None
    try:
        r=public_get(url,timeout=60)
        reader=csv.DictReader(io.StringIO(r.text))
        if not {'game_id','season','play_id'}.issubset(reader.fieldnames or []):raise ValueError('Not a play-by-play CSV')
        rows=list(reader)
        if not rows or any(int(x['season']) != season for x in rows):raise ValueError('Wrong season or empty file')
        output['sources']['savant_csv']={'status':'loaded','url':url,'rows':len(rows)}
    except (requests.RequestException,ValueError,KeyError) as exc:
        output['sources']['savant_csv']={'status':'unavailable','url':url,'reason':failure_reason(exc)}
    if rows is None:
        try:
            import nflreadpy as nfl
            frame=nfl.load_pbp([season]);rows=frame.select([k for k in ['game_id','season','game_date','play_id','posteam','defteam','wp','xpass','qb_dropback','epa','play_type','season_type'] if k in frame.columns]).to_dicts()
            output['sources']['nflreadpy_fallback']={'status':'loaded','rows':len(rows),'reason':'Savant bulk CSV unavailable'}
        except Exception as exc:output['sources']['nflreadpy_fallback']={'status':'unavailable','reason':type(exc).__name__}
    # Do not count missing WP as a neutral snap or substitute a zero efficiency.
    neutral={}
    for r in rows or []:
        try:
            if r.get('season_type')!='REG' or r.get('play_type') not in ('run','pass') or not .2<=float(r['wp'])<=.8 or str(r.get('game_date',''))[:10]>=now[:10]:continue
            team=r['posteam'];b=neutral.setdefault(team,{'snaps':0,'dropbacks':0,'expected_pass_sum':0.,'pass_model_snaps':0})
            b['snaps']+=1;b['dropbacks']+=int(float(r.get('qb_dropback') or 0))
            if r.get('xpass') is not None:b['expected_pass_sum']+=float(r['xpass']);b['pass_model_snaps']+=1
        except (ValueError,TypeError,KeyError):continue
    output['neutral_script']=neutral
    atomic_json(ROOT/'data/savant_context.json',output)
    print('Savant extraction:',output['sources'])
    return output

if __name__=='__main__':build()
