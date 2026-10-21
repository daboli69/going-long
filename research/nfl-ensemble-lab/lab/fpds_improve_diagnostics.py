"""Predeclared secondary diagnostics from saved discovery rows; no fitting."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from .fpds_improve import storage as S,core as C
from .fpds_improve.run import specs,get_reference
from .fpds_manual import engine as E,jobs
from .fpds_research import models as M
from .fpds_research.common import read,write_once,now


def probability_diagnostics(frame):
    valid=frame.pseudo_line.notna()&frame.p_over.notna()
    d=frame[valid]
    if d.empty:return {}
    y=(d.actual>d.pseudo_line).to_numpy(float);p=np.clip(d.p_over.to_numpy(float),1e-6,1-1e-6)
    bins=np.minimum((p*10).astype(int),9)
    return {'n':len(d),'games':int(d.game_id.nunique()),'brier':float(np.square(y-p).mean()),
            'log_loss':float(-(y*np.log(p)+(1-y)*np.log1p(-p)).mean()),
            'mean_probability':float(p.mean()),'observed_over':float(y.mean()),
            'reliability':[{'low':i/10,'n':int((bins==i).sum()),'predicted':float(p[bins==i].mean()),'observed':float(y[bins==i].mean())} for i in range(10) if (bins==i).any()]}


def baseline_probabilities(source,stat,arm,players):
    pieces=[]
    col='pseudo_'+stat
    if col not in players:return pd.DataFrame()
    for f in sorted((source/'blocks'/stat/arm).glob('*.parquet')):
        d=pd.read_parquet(f).merge(players[['game_id','pid',col]],on=['game_id','pid'],validate='one_to_one')
        d['pseudo_line']=d[col]
        if stat in ('rec','pass_tds'):d['p_over']=C.count_over(d.pseudo_line,d.pred)
        else:
            bank=np.load(f.with_suffix('.npy'),allow_pickle=False)
            d['p_over']=[float(np.mean(v+bank>line)) if np.isfinite(line) else np.nan for v,line in zip(d.pred,d.pseudo_line)]
        pieces.append(d)
    return pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()


def benchmark_metrics(frame,stat,column,correction):
    valid=frame.dropna(subset=[column,'actual','pred'])
    if valid.empty:return None
    a=M.loss(stat,valid.actual,valid[column]);b=M.loss(stat,valid.actual,valid.pred)
    return {'benchmark_loss':float(a.mean()),'model_loss':float(b.mean()),**E.paired(b-a,valid.game_id,correction)}


def saved_game_benchmarks(source,frames):
    from .config import MODELS_DIR,ARTIFACTS_DIR
    meta=read(source/'INPUT.json')
    games=pd.read_parquet(Path(meta['path'])/'games.parquet',columns=['game_id','season','game_type','market_p_home_novig','spread_line','total_line'])
    games=games[games.season.between(2022,2024)&games.game_type.eq('REG')]
    pointer=MODELS_DIR/'CURRENT.json';champ=None;version=None;pointer_hash=S.sha(pointer) if pointer.exists() else None
    if pointer.exists():
        version=read(pointer)['version'];folder=ARTIFACTS_DIR/'runs'/version
        metadata=read(folder/'summary.json');method=metadata['champion'];file=folder/'oof_predictions.parquet'
        import pyarrow.parquet as pq
        names=pq.read_schema(file).names
        cols=['game_id','season','game_type']+[c for c in ('p_'+method,'margin_ensemble') if c in names]
        champ=pd.read_parquet(file,columns=cols,filters=[('season','in',[2022,2023,2024]),('game_type','==','REG')])
        champ=champ.rename(columns={'p_'+method:'champ_win','margin_ensemble':'champ_margin'})
    result=[]
    for label,stat,frame in frames:
        price={'win':'market_p_home_novig','margin':'spread_line','total':'total_line'}[stat]
        d=frame[['game_id','actual','pred']].merge(games[['game_id',price]],on='game_id',validate='one_to_one')
        values=benchmark_metrics(d,stat,price,30)
        if values:result.append(dict(variant=label,stat=stat,benchmark='historical closing line; potentially later information',**values))
        if champ is not None and 'champ_'+stat in champ:
            d=frame[['game_id','actual','pred']].merge(champ[['game_id','champ_'+stat]],on='game_id',validate='one_to_one')
            values=benchmark_metrics(d,stat,'champ_'+stat,21)
            if values:result.append(dict(variant=label,stat=stat,benchmark='saved production champion; already-examined descriptive comparison',champion_version=version,**values))
    if pointer_hash and S.sha(pointer)!=pointer_hash:raise ValueError('Champion pointer changed during read-only diagnostics')
    return result


def run(path):
    summary=read(path/'SUMMARY.json');protocol=read(path/'RUN.json')['protocol'];source=jobs.directory(protocol['source_job'])
    players=pd.read_parquet(path/'players.parquet')
    originals={(s,a):S.source_blocks(source,s,a) for s in E.GAME_STATS+E.PROP_STATS for a in ('control','fpds')}
    probabilities={};rows=[];members=[];game_frames=[]
    for spec in specs():
        files=sorted((path/'blocks'/spec['id']).glob('*.parquet'))
        if not files:continue
        d=pd.concat([pd.read_parquet(f) for f in files],ignore_index=True);stat=spec['stat']
        if stat in E.GAME_STATS:game_frames.append((spec['id'],stat,d))
        row={'variant':spec['id'],'n':len(d),'games':int(d.game_id.nunique()),
             'mean_bias':E.paired(d.pred-d.actual,d.game_id,1),
             'fraction_above_point':float((d.actual>d.pred).mean()),'fraction_equal_point':float((d.actual==d.pred).mean())}
        if 'q50' in d:
            row['fraction_above_q50']=float((d.actual>d.q50).mean());row['fraction_equal_q50']=float((d.actual==d.q50).mean())
        if 'pseudo_line' in d and 'p_over' in d:
            row['pseudo_line']=probability_diagnostics(d)
            reference=get_reference(path,spec['reference'],originals)
            if spec['reference'].startswith('A7/'):
                key=(stat,spec['arm'])
                if key not in probabilities:probabilities[key]=baseline_probabilities(source,stat,spec['arm'],players)
                reference=probabilities[key]
            if not reference.empty and 'p_over' in reference:
                keys=['game_id','pid']
                z=d.merge(reference[keys+['p_over']],on=keys,suffixes=('','_reference'),validate='one_to_one').dropna(subset=['pseudo_line','p_over','p_over_reference'])
                if len(z):
                    y=z.actual.gt(z.pseudo_line).to_numpy(float)
                    effect=np.square(z.p_over-y)-np.square(z.p_over_reference-y)
                    row['pseudo_brier_delta_secondary_unadjusted95']=E.paired(effect,z.game_id,1)
        rows.append(row)
        if spec['family'] not in ('strong_games','target_features'):continue
        reference=get_reference(path,spec['reference'],originals);keys=['game_id']+(['pid'] if 'pid' in d else [])
        for member in E.members(stat):
            col='member_'+member
            z=d.merge(reference[keys+[col]],on=keys,suffixes=('','_reference'),validate='one_to_one')
            base=M.loss(stat,z.actual,z[col+'_reference']);new=M.loss(stat,z.actual,z[col])
            effect=E.paired(new-base,z.game_id,42 if stat in E.GAME_STATS else 30)
            members.append({'variant':spec['id'],'member':member,'control_loss':float(base.mean()),'new_loss':float(new.mean()),**effect,
                            'status':'registered member diagnostic only; does not change primary nominations'})
    for (stat,arm),d in originals.items():
        if stat in E.GAME_STATS:game_frames.append((f'A7/{stat}/{arm}',stat,d))
    benchmarks=saved_game_benchmarks(source,game_frames)
    result={'created_at':now(),'source_run':path.name,'secondary':rows,'member_diagnostics':members,'game_benchmarks':benchmarks,
            'note':'Bias/pseudo-line intervals are unadjusted secondary diagnostics, never nomination criteria. Count/zero ties mean above-median need not equal50%; above-mean need not equal50%. No real historical prop prices.'}
    destination=path/'SECONDARY.json'
    if destination.exists():raise ValueError('Secondary diagnostic archive already exists; never overwrite')
    write_once(destination,result)
    return result


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--run');args=parser.parse_args()
    if args.run and not args.run.isalnum():raise SystemExit('Invalid run ID')
    if args.run:path=S.ROOT/args.run
    else:
        files=sorted(S.ROOT.glob('*/RUN.json'),reverse=True)
        if not files:raise SystemExit('No improvement study exists')
        path=files[0].parent
    if not (path/'SUMMARY.json').exists():print('Study incomplete; secondary diagnostics remain pending.');return
    if (path/'SECONDARY.json').exists():print('Saved secondary diagnostics already exist; no re-scoring.');return
    result=run(path)
    print('Saved aggregate secondary diagnostics:',len(result['secondary']),'variants;',len(result['member_diagnostics']),'member comparisons. No fits.')


if __name__=='__main__':main()
