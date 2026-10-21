"""Aggregated metrics only; no raw observations, identities or features published."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import poisson
from .common import ROOT, REPORT, LAB_ROOT, SEED, now, read, atomic, write_once, digest
from . import models as M


def paired(frame,family_size=1):
    d=frame.dropna(subset=['delta'])
    group=d.groupby('game_id').delta.agg(['sum','size'])
    if group.empty:return {'n':0,'games':0,'delta':None,'ci95':None,'corrected_ci95':None,'p':1.}
    rng=np.random.default_rng(SEED);sample=rng.integers(0,len(group),(2000,len(group)))
    draws=group['sum'].to_numpy()[sample].sum(1)/group['size'].to_numpy()[sample].sum(1)
    effect=float(d.delta.mean());alpha=.025/max(1,family_size)
    return {'n':len(d),'games':len(group),'delta':effect,'ci95':np.quantile(draws,[.025,.975]).tolist(),
            'corrected_ci95':np.quantile(draws,[alpha,1-alpha]).tolist(),
            'p':float((np.sum(draws-effect<=effect)+1)/2001),'family_tests':family_size,
            'tail_resolution_warning':alpha<1/2000}


def diagnostics(d,stat):
    if d.empty:return {}
    y=d.actual.to_numpy(float);p=d.pred.to_numpy(float)
    out={'n':len(d),'games':int(d.game_id.nunique()),'primary_loss':float(M.loss(stat,y,p).mean())}
    if M.binary(stat):
        q=np.clip(p,1e-9,1-1e-9)
        out['log_loss']=float(np.mean(-y*np.log(q)-(1-y)*np.log1p(-q)))
        bins=[]
        for low in np.arange(0,1,.1):
            mask=(p>=low)&(p<low+.1)
            if mask.any():bins.append({'low':float(low),'n':int(mask.sum()),'predicted':float(p[mask].mean()),'observed':float(y[mask].mean())})
        out['reliability']=bins
    else:
        out['mae']=float(np.mean(abs(y-p)));out['rmse']=float(np.sqrt(np.mean((y-p)**2)))
        if 'crps' in d:out['crps_empirical_residual']=float(d.crps.mean())
        if stat in ('rec','pass_tds'):out['poisson_log_loss']=float(-poisson.logpmf(y,np.maximum(p,1e-9)).mean())
        if 'q10' in d:
            out['interval80_coverage']=float(np.mean((y>=d.q10)&(y<=d.q90)))
            out['pinball']={str(q):float(np.maximum(q*(y-d[c]),(q-1)*(y-d[c])).mean()) for q,c in ((.1,'q10'),(.5,'q50'),(.9,'q90'))}
            # Three-quantile approximation only; not exact continuous CRPS.
            out['crps_three_quantile_approx']=2*float(np.mean(list(out['pinball'].values())))
        if 'pseudo_line' in d:
            mask=d.pseudo_line.notna().to_numpy();line=d.pseudo_line.to_numpy(float)
            if 'p_over_pseudo' in d:over=d.p_over_pseudo.to_numpy(float)
            elif stat in ('rec','pass_tds'):over=poisson.sf(np.floor(line),np.maximum(p,1e-6))
            else:
                from scipy.stats import norm
                scale=np.maximum((d.q90-d.q10).to_numpy()/2.563,1)
                over=norm.sf((line-p)/scale)
            actual=(y>line).astype(float)
            out['pseudo_line_brier']=float(np.mean((over[mask]-actual[mask])**2)) if mask.any() else None
            out['pseudo_line_probability_method']='earlier empirical residual distribution for yards; Poisson approximation for count means (including hurdle mean)'
            if mask.any():
                bins=np.minimum((np.clip(over[mask],0,1)*10).astype(int),9)
                out['pseudo_line_reliability']=[{'bin':i,'n':int((bins==i).sum()),'predicted':float(over[mask][bins==i].mean()),'observed':float(actual[mask][bins==i].mean())} for i in range(10) if (bins==i).any()]
                bias=pd.DataFrame({'game_id':d.game_id.to_numpy()[mask],'delta':over[mask]-actual[mask]})
                out['pseudo_probability_bias']=paired(bias)
            out['above_mean_fraction']=float((y>p).mean());out['above_median_fraction']=float((y>d.q50.to_numpy()).mean())
    return out


def results(directory,phase='discovery'):
    from .walkforward import completed_blocks
    protocol=read(LAB_ROOT/'docs/FPDS_AMENDMENT6_TRIALS.json')
    specs=protocol['trials'];seasons={'discovery':[2022,2023,2024],'validation':[2025],'descriptive':[2026]}[phase]
    family_size={f:sum(x['family']==f and x['arm']!='control' for x in specs) for f in {x['family'] for x in specs}}
    rows=[];ledger=read(Path(directory)/'LEDGER.json')
    for s in specs:
        if s['arm']=='control':continue
        d=completed_blocks(directory,s);control=s|{'id':f"{s['stat']}__control__all__linear"}
        b=completed_blocks(directory,control)
        if d.empty or b.empty:continue
        d=d[d.season.isin(seasons)];b=b[b.season.isin(seasons)]
        if d.empty:continue
        keys=['game_id']+(['pid'] if 'pid' in d else [])
        j=d.merge(b[keys+['pred','loss']],on=keys,suffixes=('','_control'),validate='one_to_one')
        if j.empty:continue
        j['delta']=j.loss-j.loss_control
        r=dict(configuration=s,**paired(j,family_size[s['family']]),
               control_loss=float(j.loss_control.mean()),new_loss=float(j.loss.mean()),
               seasons_agreeing=int(sum(z.delta.mean()<0 for _,z in j.groupby('season'))),
               by_season={str(year):{'n':len(z),'delta':float(z.delta.mean())} for year,z in j.groupby('season')},
               identical_sample=len(j)==len(b),diagnostics=diagnostics(j,s['stat']) if s['stat']!='first_td' else {'brier':float(j.brier.mean())})
        r['relative_reduction']=-r['delta']/max(r['control_loss'],1e-12)
        record=ledger.get(s['id'],{})
        r['run_status']=record.get(phase+'_status',record.get('status','unknown'))
        # Table removal and model-family comparisons also retain the full-feature linear reference.
        reference=s|{'id':f"{s['stat']}__all__all__linear"}
        full=completed_blocks(directory,reference)
        if len(full) and s['id']!=reference['id']:
            full=full[full.season.isin(seasons)]
            extra=j.merge(full[keys+['loss']],on=keys,suffixes=('','_full'),validate='one_to_one')
            if len(extra):
                extra['delta']=extra.loss-extra.loss_full
                r['vs_full_feature_linear']=paired(extra,family_size[s['family']])
        rows.append(r)
    for family in family_size:
        group=sorted([r for r in rows if r['configuration']['family']==family],key=lambda x:x['p'])
        running=0.
        for i,r in enumerate(group):
            # Failed/unavailable registered slots still consume multiplicity budget.
            running=max(running,min(1.,r['p']*(family_size[family]-i)));r['holm_p']=running
    for r in rows:
        stat=r['configuration']['stat']
        r['discovery_gate']=bool(phase=='discovery' and r['games']>=200 and (r['n']>=300 or stat in ('margin','total','win','first_td')) and
            r['run_status']=='complete' and r['identical_sample'] and r['relative_reduction']>=.01 and r['corrected_ci95'][1]<0 and r['holm_p']<.05 and r['seasons_agreeing']>=2 and
            (r['configuration']['model']!='distribution' or stat in ('rec','pass_tds')))
    return rows


def freeze(directory,rows):
    protocol=read(LAB_ROOT/'docs/FPDS_AMENDMENT6_TRIALS.json');selection=[]
    for stat in ('rec','rec_yds','rush_yds','anytime_td','pass_yds','pass_tds','margin','total','win','first_td'):
        candidates=[r for r in rows if r['configuration']['stat']==stat and r['discovery_gate'] and r['configuration']['model']!='blend']
        if candidates:chosen=min(candidates,key=lambda x:x['new_loss'])['configuration']
        else:chosen=next(x for x in protocol['trials'] if x['stat']==stat and x['arm']=='control')
        selection.append(chosen)
    value={'created_at':now(),'configurations':selection,'selection':'discovery only; control where no full gate passed',
           'market_informed_configurations':[r['configuration'] for r in rows if r['configuration']['model']=='blend' and r['discovery_gate']],
           'validation_warning':'2025 previously examined for old simulator; one pass, no changes',
           'trial_count':len(read(directory/'LEDGER.json')),'research_path':str(directory)}
    dest=LAB_ROOT/'docs/FPDS_AMENDMENT6_FROZEN.json'
    if dest.exists():
        previous=read(dest)
        if previous['configurations']!=selection:raise ValueError('Frozen config already exists; cannot reselect')
        return previous
    write_once(dest,value)
    return value


def frozen(directory):
    import subprocess
    dest=LAB_ROOT/'docs/FPDS_AMENDMENT6_FROZEN.json'
    if not dest.exists():raise ValueError('Discovery selection not frozen')
    rel=subprocess.check_output(['git','ls-files','--full-name',str(dest)],cwd=LAB_ROOT,text=True).strip()
    if not rel:raise ValueError('Commit frozen selection BEFORE validation')
    blob=subprocess.check_output(['git','show','HEAD:'+rel],cwd=LAB_ROOT).decode('utf-8').replace('\r\n','\n')
    if blob!=dest.read_text(encoding='utf-8'):raise ValueError('Frozen selection differs from commit')
    result=read(dest)
    if result['research_path']!=str(directory):raise ValueError('Frozen selection belongs to a different data/code fingerprint')
    return result


def run():
    directory=Path(read(ROOT/'LATEST_RESEARCH.json')['path'])
    rows=results(directory)
    atomic(REPORT/'FPDS_A6_DISCOVERY.json',{'created_at':now(),'research_path':str(directory),'rows':rows})
    if (directory/'DISCOVERY_COMPLETE.json').exists():freeze(directory,rows)
    full_report()
    return rows


def market_results(directory,phase='discovery'):
    """Real closing lines/probabilities are read only after forecasts exist."""
    from .features import latest_features
    from .walkforward import completed_blocks
    meta=read(Path(directory)/'JOB.json')['feature_metadata'];games=pd.read_parquet(Path(meta['path'])/'games.parquet')
    protocol=read(LAB_ROOT/'docs/FPDS_AMENDMENT6_TRIALS.json')
    seasons={'discovery':[2022,2023,2024],'validation':[2025],'descriptive':[2026]}[phase]
    rows=[]
    for spec in protocol['trials']:
        stat=spec['stat']
        if stat not in ('margin','total','win'):continue
        p=completed_blocks(directory,spec)
        if p.empty:continue
        p=p[p.season.isin(seasons)]
        benchmark='market_p_home_novig' if stat=='win' else 'spread_line' if stat=='margin' else 'total_line'
        d=p.merge(games[['game_id',benchmark]],on='game_id',validate='one_to_one').dropna(subset=[benchmark])
        if d.empty:continue
        d['delta']=M.loss(stat,d.actual,d.pred)-M.loss(stat,d.actual,d[benchmark])
        row={'configuration':spec,'benchmark':benchmark,**paired(d,11),
             'our_loss':float(M.loss(stat,d.actual,d.pred).mean()),'benchmark_loss':float(M.loss(stat,d.actual,d[benchmark]).mean()),
             'claim':'forecast loss comparison only; no betting return/price-edge inference'}
        if stat!='win':
            row['our_rmse']=float(np.sqrt(np.mean((d.actual-d.pred)**2)))
            row['benchmark_rmse']=float(np.sqrt(np.mean((d.actual-d[benchmark])**2)))
            if 'crps' in d:
                d['delta']=d.crps-abs(d.actual-d[benchmark])
                row['crps_vs_closing_point_mass']=paired(d,11)
        rows.append(row)
    return rows


def permutation_results(directory):
    rows=[]
    for stat in ('rec','rec_yds','rush_yds','anytime_td','pass_yds','pass_tds'):
        files=list((Path(directory)/'blocks'/f'{stat}__all__all__linear').glob('*__permutation.parquet'))
        if not files:continue
        d=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
        for table,z in d.groupby('table'):
            rows.append({'stat':stat,'table':table,**paired(z),'interpretation':'exploratory permutation loss increase; positive means fitted model relied on table'})
    return rows


def full_report():
    from .features import latest_features
    from .audit import latest
    directory=Path(read(ROOT/'LATEST_RESEARCH.json')['path']);metadata=read(directory/'JOB.json')['feature_metadata'];imports=latest()
    discovery=results(directory);validation=results(directory,'validation') if (directory/'VALIDATION_COMPLETE.json').exists() else []
    descriptive=results(directory,'descriptive') if (directory/'DESCRIPTIVE_COMPLETE.json').exists() else []
    market=market_results(directory);permutation=permutation_results(directory)
    ledger=read(directory/'LEDGER.json')
    frozen_file=LAB_ROOT/'docs/FPDS_AMENDMENT6_FROZEN.json'
    frozen_ids={s['id'] for s in read(frozen_file)['configurations']} if frozen_file.exists() else set()
    accepted=[r for r in discovery if r['configuration']['id'] in frozen_ids and r['discovery_gate'] and r['configuration']['model']!='blend' and any(v['configuration']['id']==r['configuration']['id'] and v['delta']<0 and v['identical_sample'] and v['run_status']=='complete' for v in validation)]
    table=[]
    for family in ('H1','H2','H3','H4','H5','H6','H7','H8','H9'):
        rows=[r for r in discovery if r['configuration']['family']==family and r['configuration']['model']!='blend']
        if not rows:
            table.append(f'|{family}|not completed|—|—|pending / blocked|');continue
        best=min(rows,key=lambda r:r['delta']/max(r['control_loss'],1e-12))
        confirm=next((r for r in validation if r['configuration']['id']==best['configuration']['id']),None)
        passed=best['discovery_gate'] and confirm is not None and confirm['delta']<0 and confirm['identical_sample'] and confirm['run_status']=='complete'
        decision='Challenger; frozen validation same direction' if passed else 'Rejected / exploratory; no full gate'
        ci=best['corrected_ci95']
        table.append(f"|{family}: {best['configuration']['stat']} / {best['configuration']['arm']} / {best['configuration']['model']}|{best['n']} / {best['games']}|{best['control_loss']:.4g} → {best['new_loss']:.4g}|{best['delta']:+.4g} [{ci[0]:+.4g}, {ci[1]:+.4g}]|{best['seasons_agreeing']}/3; {decision}|")
    coverage={'files':len(imports['files']),'tables':len(imports['working_tables']),
              'valid_rows':sum(t['valid_rows'] for t in imports['working_tables']),
              'unmatched_rows':sum(t['unmatched_rows'] for t in imports['working_tables']),
              'possible_caps':sum(t['possible_export_cap'] for t in imports['working_tables']),
              'native_resolved':sum(t.get('native_id_resolved_rows',0) for t in imports['working_tables'])}
    result={'created_at':now(),'trial_count':len(ledger),'trial_ceiling':269,'failed_configurations':sum(x['status']=='failed' for x in ledger.values()),
            'coverage':coverage,'discovery':discovery,'validation':validation,'descriptive_2026':descriptive,'market':market,'permutation':permutation,
            'accepted_shadow_count':len(accepted),'warning':'No promotion; historical publication/revisions and earlier holdout exposure limit inference.'}
    atomic(REPORT/'FPDS_A6_RESULTS.json',result)
    changed=sum(r.get('changed_values',0) for r in imports['revisions'])
    report=['# FPDS full report — Amendment 6','',
      f"**Completed:** append-only importer, column dictionary/coverage, exact GSIS/team/week joins, games-played rolling feature store and resumable fixed-budget program. {len(ledger)}/269 configurations attempted; {result['failed_configurations']} failed/skipped. Single frozen2025 pass: {'complete' if validation else 'pending'}.2026 is descriptive only. All models remain shadow; no promotion.", '',
      f"**Data:** {coverage['files']} files / {coverage['tables']} tables / {coverage['valid_rows']:,} weekly rows; {coverage['unmatched_rows']:,} unmatched rows (not unique players); {coverage['native_resolved']:,} exact native-ID resolutions. {coverage['possible_caps']} possible export caps; five separation tables start2022. Overlap revisions observed in this import: {changed}; pre-download revision frequency remains unknown. Historical publication times are unverified. Strict later-week/final-kickoff+24h joins and future-mutation/shifted/shuffled canaries enforced. See dictionary and aggregate JSON for full coverage.", '',
      '**What data improved what:** lowest relative discovery loss per family below is a selected, exploratory display; corrected intervals and all trials remain in FPDS_A6_RESULTS.json. Acceptance also requires the frozen validation direction. H3 first-TD/scoring is offensive regulation only; H7 undated target-week injury/shadow effects are unavailable.', '',
      '|Family / displayed configuration|n / games|Control → new loss|Delta [family-corrected95% CI]|Seasons agreeing / decision|',
      '|---|---:|---|---|---|',*table,'',
      '**Recommended changes:** '+('Review the statistically qualified shadow configurations in the frozen file; do not promote. Revised/truncated source data still limits credibility.' if accepted else 'No new model change has passed the complete preregistered gate; keep the control. Positive table permutation is tentative reliance, not proof of independent value.'),'',
      '**Edge assessment:** real historical game closing lines are benchmark-only; their paired forecast-loss comparisons are in the aggregate JSON. Historical prop prices do not exist here: pseudo-lines test calibration only.2026 archived quotes support small-sample descriptive comparisons and forward tracking. No tradable price edge is established.', '',
      '**Concerns:**269-slot search/multiple testing; finite2000-draw bootstrap tail resolution; possible export truncation/selection; unverified historical publication/revisions; unmatched identities; overlapping unit means; earlier2023 development and old simulator2023–25 exposure.2025 is not a pristine holdout. Structural proxies are analytical, not v1 simulations. Training-residual interval warm-up is labelled. Causal on/off effects and current replacement assumptions are not identified by the exports.', '',
      '**Next angles:** preregister uncapped coverage and real pregame publication snapshots; compare exposure-normalized role changes, timestamped injury/replacement features and true prospective calibration on matched quote contracts. No further trials on2025.', '',
      '**Needs Travis / weekly:** download the same full-history tables with trailing `week N`, retain them in Inbox, run `run_weekly_fpds.bat`. Outputs stay in ignored private revision folders; do not share subscription derivatives. Review missing/capped coverage before relying on apparent improvements.']
    (REPORT/'FPDS_FULL_REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    return result
