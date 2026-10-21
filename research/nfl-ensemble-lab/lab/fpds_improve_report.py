"""Format saved aggregate Amendment8 metrics only; never fits or scores rows."""
import argparse
from pathlib import Path
from .fpds_improve import storage as S
from .fpds_research.common import read,write_once
from .config import REPORTS_DIR


def render(summary,run_id):
    rows=summary.get('rows',[]);trials=summary.get('trials',{})
    lines=['# FPDS improvement study — Amendment 8','',
           f"Run `{run_id}`. {summary.get('split','Unknown split')}. All outputs shadow only; nothing promoted.",'',
           f"Completed {len(rows)} primary comparisons; {len(summary.get('failures',[]))} failed blocks. "
           f"Recorded {len(trials.get('output_configurations',[]))} member/head outputs, "
           f"{len(trials.get('fit_configurations',[]))} internal fit configurations and {trials.get('fit_calls',0)} fit dispatches. "
           'The fixed ceiling is147 outputs /300 internal configurations /4500 dispatches. No grid search.','',
           'Lower loss is better. Negative delta means improvement against the named reference. Intervals are registered family-corrected paired whole-game95% intervals. A discovery nominee requires >=1% reduction, corrected interval below zero, >=200 games, two improving seasons, identical complete samples, no failed blocks and Holm p<.05. It still requires future confirmation.','',
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
    print('Saved aggregate report:',report)


if __name__=='__main__':main()
