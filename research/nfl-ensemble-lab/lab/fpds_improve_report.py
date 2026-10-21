"""Format saved aggregate Amendment8 metrics only; never fits or scores rows."""
import argparse
from pathlib import Path
from .fpds_improve import storage as S
from .fpds_research.common import read,write_once
from .config import REPORTS_DIR


def render(summary,run_id):
    rows=summary.get('rows',[]);trials=summary.get('trials',{})
    budget=(12,84,1500) if summary.get('repair_parent') else (147,300,4500)
    lines=['# FPDS improvement study — Amendment 8','',
           f"Run `{run_id}`. {summary.get('split','Unknown split')}. All outputs shadow only; nothing promoted.",'',
           f"Completed {len(rows)} primary comparisons; {len(summary.get('failures',[]))} failed blocks. "
           f"Recorded {len(trials.get('output_configurations',[]))} member/head outputs, "
           f"{len(trials.get('fit_configurations',[]))} internal fit configurations and {trials.get('fit_calls',0)} fit dispatches. "
           f'The fixed ceiling is{budget[0]} outputs /{budget[1]} internal configurations /{budget[2]} dispatches. No grid search.','',
           'Lower loss is better. Negative delta means improvement against the named reference. Intervals are registered family-corrected paired whole-game95% intervals. A discovery nominee requires >=1% reduction, corrected interval below zero, >=200 games, two improving seasons, identical complete samples, no failed blocks and Holm p<.05. It still requires future confirmation.','',
           'Primary loss is MAE for yards/margin/total, Poisson deviance for receptions/passing TDs, and Brier for winners/anytime TD. Median quantile heads are point forecasts; they are not means.','',
           '## Best observed change per family','',
           'These are exploratory rankings within the fixed study; the complete table below includes regressions. Different rows have different references and are not automatically comparable.','',
           '|Family|Target / variant / inputs|n / games|Reference → new loss|Change|Corrected95% CI|Nominee|',
           '|---|---|---:|---:|---:|---|---|']
    for family in ['strong_games','target_features','combination','opportunity','distribution']:
        group=[r for r in rows if r['family']==family]
        if not group:
            lines.append(f'|{family}|Unavailable|||||No|');continue
        best=max(group,key=lambda r:r['relative_reduction']);lo,hi=best['corrected_ci95']
        lines.append(f"|{family}|{best['stat']} / {best['kind']} / {best['arm']}|{best['n']} / {best['games']}|{best['control_loss']:.5f} → {best['new_loss']:.5f}|{-100*best['relative_reduction']:+.2f}%|[{lo:+.5f},{hi:+.5f}]|{'Yes, exploratory' if best['discovery_nomination'] else 'No'}|")
    nominees=[r for r in rows if r['discovery_nomination']]
    if summary.get('repair_parent'):
        lines+=['',f"Separate opportunity-only repair of `{summary['repair_parent']}`. The original failed blocks and original zero nominations remain unchanged; successful other families were not refitted."]
    lines+=['',f"Discovery nominees: {len(nominees)} of {len(rows)} primary comparisons. These do not establish provider value versus the production champion or a market-price edge.",'',
            '## Coherence','']
    coherence=summary.get('coherence',[])
    if coherence:
        maximum=max(r['max_abs_coherence_error'] for r in coherence)
        lines.append(f'Opportunity outputs: maximum absolute team-minus-players-minus-other error={maximum:.3g}. This is an arithmetic check, not evidence of better player accuracy.')
        lines+=['','|Variant|Team-games|Mean other-player fraction|','|---|---:|---:|']
        lines.extend(f"|{r['variant']}|{r['team_games']}|{r['mean_other_fraction']:.1%}|" for r in coherence)
    lines+=['','## All primary comparisons','',
            '|Family / target / inputs / variant|Reference|n / games|Reference loss|New loss|Delta [corrected95% CI]|Improving seasons|Nominee|',
            '|---|---|---:|---:|---:|---|---:|---|']
    for r in rows:
        lo,hi=r['corrected_ci95']
        lines.append(f"|{r['family']} / {r['stat']} / {r['arm']} / {r['kind']}|{r['reference']}|{r['n']} / {r['games']}|{r['control_loss']:.6f}|{r['new_loss']:.6f}|{r['delta']:+.6f} [{lo:+.6f},{hi:+.6f}]|{r['seasons_agreeing']}/3|{'Yes' if r['discovery_nomination'] else 'No'}|")
    lines+=['','## Distribution diagnostics','',
            '|Target / variant|80% coverage|Pinball10 /50 /90|Pseudo-line Brier|','|---|---:|---|---:|']
    for r in rows:
        if r['family']!='distribution':continue
        d=r['diagnostics'];q=d.get('pinball',{});pseudo=d.get('pseudo_line',{})
        coverage=f"{d['coverage80']:.1%}" if 'coverage80' in d else 'n/a'
        pin=' / '.join(f'{q[str(v)]:.4f}' for v in (.1,.5,.9)) if q else 'n/a'
        brier=f"{pseudo['brier']:.5f}" if 'brier' in pseudo else 'n/a'
        lines.append(f"|{r['stat']} / {r['arm']} / {r['kind']}|{coverage}|{pin}|{brier}|")
    lines+=['','## Limits / next','',
            '2022–2024 were already examined. No fresh2025 pass or2026 selection occurred. True prospective archives must confirm any nominee. Strong game features reconstruct verified champion-style information, not the champion fitted artifact or all advanced inputs. Last-known starters and injury flags retain uncertainty. Revised historical exports and unverified publication times remain limitations.',
            'NB-only keeps the mean fixed; any benefit is a probability/distribution diagnostic, not a primary mean improvement. Quantile medians are evaluated as point forecasts and are not interchangeable with means. Pseudo-lines are not real prop prices. Empirical residual CRPS is unavailable for direct quantile-only heads; pinball and coverage are reported instead.',
            'Coherent outputs retain an explicit other-player remainder. Other-player distinct-scorer counts are labelled approximations, not invented identities. Failed blocks remain retained; no incomplete family can qualify. All existing forecast archives stay unchanged.',
            f"Frozen input hashes unchanged: {summary.get('source_integrity_unchanged','unknown')}. Preparation failures before this completed attempt are recorded separately in STATUS.md and retained privately. No raw or player-level subscription rows appear in this report."]
    return '\n'.join(lines)+'\n'


def render_secondary(data):
    lines=['# Saved-output secondary diagnostics','',data['note'],'',
           '## Current champion / closing benchmarks','',
           'Negative delta means lower model loss than the benchmark. These secondary comparisons never change nominations. The saved champion used longer training history and was selected on previously examined years. Closing prices can reflect later information. Champion total predictions are unavailable.','',
           '|Variant|Target|Benchmark|n / games|Benchmark loss|Model loss|Delta [corrected95% CI]|',
           '|---|---|---|---:|---:|---:|---|']
    for r in data.get('game_benchmarks',[]):
        lo,hi=r['corrected_ci95']
        lines.append(f"|{r['variant']}|{r['stat']}|{r['benchmark']}|{r['n']} / {r['games']}|{r['benchmark_loss']:.6f}|{r['model_loss']:.6f}|{r['delta']:+.6f} [{lo:+.6f},{hi:+.6f}]|")
    lines+=['','## Pseudo-line reliability and bias','',
            'Pseudo-lines are diagnostic thresholds, not real historical prop prices. Bias=prediction minus actual. These95% intervals are secondary and unadjusted; no selection is allowed.','',
            '|Variant|Mean bias [95% CI]|Above point / equal point|Above median / equal median|Pseudo-line Brier delta [95% CI]|','|---|---|---|---|---|']
    for r in data.get('secondary',[]):
        bias=r['mean_bias'];lo,hi=bias['ci95']
        point=f"{r['fraction_above_point']:.1%} / {r['fraction_equal_point']:.1%}"
        median=f"{r['fraction_above_q50']:.1%} / {r['fraction_equal_q50']:.1%}" if 'fraction_above_q50' in r else 'n/a'
        effect=r.get('pseudo_brier_delta_secondary_unadjusted95')
        delta=f"{effect['delta']:+.6f} [{effect['ci95'][0]:+.6f},{effect['ci95'][1]:+.6f}]" if effect else 'unavailable'
        lines.append(f"|{r['variant']}|{bias['delta']:+.5f} [{lo:+.5f},{hi:+.5f}]|{point}|{median}|{delta}|")
    lines+=['','## Registered individual members','',
            '|Variant / member|n / games|Reference loss|New loss|Delta [corrected95% CI]|','|---|---:|---:|---:|---|']
    for r in data.get('member_diagnostics',[]):
        lo,hi=r['corrected_ci95']
        lines.append(f"|{r['variant']} / {r['member']}|{r['n']} / {r['games']}|{r['control_loss']:.6f}|{r['new_loss']:.6f}|{r['delta']:+.6f} [{lo:+.6f},{hi:+.6f}]|")
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--run');args=parser.parse_args()
    if args.run and not args.run.isalnum():raise SystemExit('Invalid run identifier')
    if args.run:path=S.ROOT/args.run
    else:
        files=sorted(S.ROOT.glob('*/RUN.json'),reverse=True)
        if not files:raise SystemExit('No improvement study exists')
        path=files[0].parent
    if not (path/'SUMMARY.json').exists():
        print('Study is not complete; no saved-output report generated.');return
    data=read(path/'SUMMARY.json')
    folder=REPORTS_DIR/('run_'+path.name[:8])/('A8_'+path.name);folder.mkdir(parents=True,exist_ok=True)
    report=folder/'REPORT.md';text=render(data,path.name)
    if report.exists() and report.read_text(encoding='utf-8')!=text:raise SystemExit('Existing report is immutable')
    if not report.exists():report.write_text(text,encoding='utf-8')
    aggregate=folder/'AGGREGATE_RESULTS.json'
    if aggregate.exists():
        if read(aggregate)!=data:raise SystemExit('Existing aggregate report is immutable')
    else:write_once(aggregate,data)
    if (path/'SECONDARY.json').exists():
        secondary=read(path/'SECONDARY.json');text=render_secondary(secondary)
        target=folder/'SECONDARY.md'
        if target.exists() and target.read_text(encoding='utf-8')!=text:raise SystemExit('Existing secondary report is immutable')
        if not target.exists():target.write_text(text,encoding='utf-8')
        target=folder/'AGGREGATE_SECONDARY.json'
        if target.exists() and read(target)!=secondary:raise SystemExit('Existing secondary aggregate is immutable')
        if not target.exists():write_once(target,secondary)
    print('Saved aggregate report:',report)


if __name__=='__main__':main()
