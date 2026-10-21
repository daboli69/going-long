"""Append-only presentation of fixed FPDS shadow forecasts; never fits a model."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from scipy.stats import poisson
from .fpds_research.common import ROOT,LAB_ROOT,now,stamp,read,write_once,sha,private_error


def correct_comparisons(frame,banks):
    """Price-free distribution transform fixed to the research probability method."""
    d=frame.copy();d['p_push']=np.nan;d['probability_method']='unavailable'
    d['benchmark_scope_status']=None
    for ix,r in d.iterrows():
        if r.stat in ('anytime_td','first_td'):
            d.loc[ix,'gap']=np.nan
            d.loc[ix,'benchmark_scope_status']='offensive rushing/receiving only; book settlement not verified'
            d.loc[ix,'probability_method']='model offensive-scorer probability; no numerical-line gap'
            if r.stat=='anytime_td':d.loc[ix,['p_over','p_under','p_push']]=[r['mean'],1-r['mean'],0.]
            continue
        line=pd.to_numeric(pd.Series([r.get('consensus_line')]),errors='coerce').iloc[0]
        if not np.isfinite(line) or r.get('line_type')!='consensus':
            d.loc[ix,'gap']=np.nan
            continue
        d.loc[ix,'gap']=r['mean']-line
        if r.stat in ('rec','pass_tds'):
            over=float(poisson.sf(np.floor(line),max(r['mean'],1e-6)))
            under=float(poisson.cdf(np.ceil(line)-1,max(r['mean'],1e-6)))
            d.loc[ix,'probability_method']='Poisson approximation from frozen mean; not a full hurdle distribution'
        else:
            bank=np.asarray(banks.get((r.arm,r.stat),[]),float)
            bank=bank[np.isfinite(bank)]
            if not len(bank):
                d.loc[ix,['p_over','p_under']]=np.nan
                continue
            samples=r['mean']+bank
            if r.stat!='margin':samples=np.maximum(samples,0)
            over=float(np.mean(samples>line));under=float(np.mean(samples<line))
            d.loc[ix,'probability_method']='earlier-block empirical residual CDF; historical reconstruction'
        d.loc[ix,['p_over','p_under','p_push']]=[over,under,max(0.,1-over-under)]
    d['skew_artifact_flag']=(d['mean']-pd.to_numeric(d.consensus_line,errors='coerce'))*(d['median']-pd.to_numeric(d.consensus_line,errors='coerce'))<0
    d['confidence_tier']='C';d['stability_flag']='not tested';d['coherence_flag']='not reconciled';d['scenario_sensitivity']='not tested'
    return d


def latest_forecast():
    paths=[p for p in (ROOT/'weekly').glob('2026_w*_r*') if (p/'FORECAST.json').exists()]
    if not paths:raise FileNotFoundError('No completed FPDS forecast revision')
    return max(paths,key=lambda p:read(p/'FORECAST.json')['created_at'])


def run(directory=None,refresh=True):
    from .fpds_research.weekly import quote_comparison,game_comparison
    from .fpds_research.walkforward import completed_blocks
    source=Path(directory) if directory else latest_forecast();manifest=read(source/'FORECAST.json')
    for filename,expected in manifest['files'].items():
        if sha(source/filename)!=expected:raise ValueError('An archived source forecast changed; stop')
    players=pd.read_csv(source/'projections.csv',float_precision='round_trip')
    games=pd.read_csv(source/'game_projections.csv',float_precision='round_trip')
    created=pd.Timestamp(manifest['created_at']);asof=pd.Timestamp.now(tz='UTC')
    for d in (players,games):
        d['decision_started_at']=d.created_at;d['forecast_created_at']=created.isoformat();d['comparison_created_at']=asof.isoformat()
        d['created_at']=created.isoformat();d['kickoff_utc']=pd.to_datetime(d.kickoff_utc,utc=True)
    bad=set(players.loc[players.kickoff_utc.le(created),'game_id'])|set(games.loc[games.kickoff_utc.le(created),'game_id'])
    players=players[~players.game_id.isin(bad)];games=games[~games.game_id.isin(bad)]
    frozen=read(LAB_ROOT/'docs/FPDS_AMENDMENT6_FROZEN.json');research=Path(frozen['research_path'])
    specs={s['stat']:s for s in frozen['configurations']};banks={}
    for arm in ('control','frozen'):
        for stat in ('rec_yds','rush_yds','pass_yds','margin','total'):
            spec=specs[stat] if arm=='frozen' else {'id':f'{stat}__control__all__linear'}
            d=completed_blocks(research,spec)
            if len(d):
                cutoff=manifest['training_last_completed_week']
                d=d[(d.season<2026)|(d.season.eq(2026)&d.week.le(cutoff))]
                banks[(arm,stat)]=(d.actual-d.pred).to_numpy(float)
    if refresh:
        players=quote_comparison(players,asof)
        targets=games.drop_duplicates('game_id')[['game_id','home_team','away_team','kickoff_utc']]
        games=game_comparison(games,targets,asof)
    games['line_type']=np.where(games.consensus_line.notna(),'consensus','unavailable')
    combined=correct_comparisons(pd.concat([players,games],ignore_index=True),banks)
    combined['name']=combined['name'].fillna(combined.away_team+'@'+combined.home_team)
    leans=combined[combined.arm.eq('frozen')&combined.kickoff_utc.gt(asof)].copy()
    leans['investigation_score']=leans.gap.abs()/(leans.q90-leans.q10).clip(lower=1)
    leans.loc[leans.skew_artifact_flag | ~leans.line_status.eq('current'),'investigation_score']=np.nan
    leans['rank_in_game']=leans.groupby('game_id').investigation_score.rank(method='first',ascending=False,na_option='bottom')
    leans['investigation_note']='Tier C research comparison; investigate source coverage, role assumptions and distribution fit. Stale quotes, skew, injury changes, unstable or incoherent projections can invalidate it.'
    directory=source/'presentations'/stamp();directory.mkdir(parents=True,exist_ok=False)
    combined.to_csv(directory/'projections.csv',index=False)
    leans.sort_values(['game_id','rank_in_game']).to_csv(directory/'leans.csv',index=False)
    (directory/'leans.md').write_text('# FPDS shadow comparisons\n\nAll rows are tier C: stability, coherence and scenarios are unvalidated. Numeric gaps compare fixed point projections to consensus lines; they are not price-edge signals. Binary scorer contracts have no numerical-line gap because settlement scope is unverified. Yards use earlier empirical residual probabilities; counts use labelled Poisson approximations. Skew/stale rows have no investigation score. No betting recommendation or stake.\n',encoding='utf-8')
    result={'created_at':now(),'path':str(directory),'forecast_created_at':created.isoformat(),'source_forecast':str(source),
            'source_files_unchanged':all(sha(source/k)==v for k,v in manifest['files'].items()),
            'excluded_started_before_archive_games':sorted(bad),'rows':len(combined),'confidence_tier':'C',
            'rule':'abs(point mean - line) / max(q90-q10,1); no score for skew/stale/binary/unavailable rows'}
    write_once(directory/'PRESENTATION.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory');a=p.parse_args()
    try:
        result=run(a.directory);print('Reviewed private projections/leans: '+result['path'])
    except Exception:
        private_error('presentation');raise SystemExit('Presentation stopped; see ignored private error log')
