"""Metadata-only dictionary and coverage audit, with private row-level evidence."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import ROOT, LAB_ROOT, REPORT, now, read, write_once, atomic,sha
from . import ingest as I


def latest():
    return read(read(ROOT/'LATEST_IMPORT.json')['path']+'/MANIFEST.json')


def run(manifest=None):
    m=manifest or latest()
    out=ROOT/'audits'/(m['fingerprint'][:20]+'_'+sha(__file__)[:10])
    if (out/'AUDIT.json').exists():return read(out/'AUDIT.json')
    out.mkdir(parents=True,exist_ok=True)
    summary={'created_at':now(),'import_fingerprint':m['fingerprint'],'tables':[],
             'publication_warning':'Historical reconstruction; vendor original publication and pre-download revisions unverified.',
             'canary_status':'Future-mutation and shifted/shuffled-week tests required before model fits.'}
    lines=['# FPDS data dictionary — Amendment 6', '',
           'Metadata only. No subscription rows, player labels or values are published here.', '',
           'All numeric game statistics are outcome-contaminated in their source week. They are usable only after a strict availability lag. Unknown/DFS/fantasy/projection fields are excluded. Header definitions below are guesses, not verified vendor definitions.', '',
           'Historical exports downloaded in2026 are reconstructed event-time data. They cannot establish what a bettor could actually have observed in an earlier season. First imports cannot estimate earlier vendor revisions.', '',
           '|Table|Rows|Usable entity-weeks|Identity/join excluded|Ambiguous rows|Export-cap flag|2026 weeks|',
           '|---|---:|---:|---:|---:|---|---|']
    column_coverage={'created_at':now(),'definition':'nonmissing cell counts by source season:week; metadata only','tables':{}}
    for t in m['working_tables']:
        column_coverage['tables'][t['table']]={c['column']:c.get('nonmissing_by_season_week',{}) for c in t['columns']}
        lines.append(f"|{t['table']}|{t['valid_rows']}|{t['usable_entity_week_rows']}|{t['unmatched_rows']}|{t['ambiguous_entity_week_rows']}|{t['possible_export_cap']}|{','.join(map(str,t['coverage'].get('2026',[])))}|")
        summary['tables'].append({k:t[k] for k in ('table','valid_rows','usable_entity_week_rows','unmatched_rows','unmatched_distinct_labels','ambiguous_entity_week_rows','possible_export_cap','coverage','selector_conflicts','defense_label_rows')})
        summary['tables'][-1].update({k:t.get(k,0) for k in ('native_id_resolved_rows','recognized_native_gsis_rows','historical_team_corrections','historical_defender_team_corrections','rows_without_schedule_game','opponent_conflict_rows','shadow_matchup_conflict_rows','defender_unmatched_rows','defender_unmatched_distinct_labels','valid_rows_games_gt_one')})
        identities=pd.read_parquet(t['private_path'],columns=['pid','team','entity'])
        known=identities.pid.notna() if t['entity_kind']=='player' else identities.team.notna()
        summary['tables'][-1]['identity_unmatched_rows']=int((~known).sum())
        summary['tables'][-1]['known_identity_quarantined_rows']=int((known&identities.entity.isna()).sum())
    lines+=['', 'Per-column nonmissing counts for every season/week are in [FPDS_COLUMN_COVERAGE.json](FPDS_COLUMN_COVERAGE.json). They distinguish absent fields from observed zeros.', '', '## File inventory and coverage grid', '',
            'Coverage entries are observed week:row-count, not a completeness claim.2021–25 expected regular-season weeks1–18;2026 expected through the export marker (currently6). Missing entire weeks are listed. Entity coverage is checked separately against NFL eligible rows.', '']
    for t in m['files']:
        lines += [f"### {t['name']}", '',
                  f"Table `{t['table']}`; {t['bytes']} bytes; modified {t['modified_at']}; SHA256 `{t['sha256']}`; imported {t['imported_at']}; header rows {t['header_rows']}; raw rows {t['rows']}; valid weekly rows {t['valid_rows']}; malformed {t['malformed_rows']}; calendar/summary exclusions {t['invalid_calendar_rows']}; selector conflicts {t['selector_conflicts']}.", '',
                  'Selected keys: '+', '.join(f'{k}=`{v}`' for k,v in t['selected_keys'].items())+'.', '',
                  '|Season|Weeks and row counts|Missing weeks|', '|---|---|---|']
        for s in range(2021,2027):
            weeks=t['coverage'].get(str(s),[]);expected=range(1,(t['export_through_week'] or 6)+1) if s==2026 else range(1,19)
            grid=', '.join(f"{w}:{t['coverage_counts'].get(f'{s}:{w}',0)}" for w in weeks)
            missing=','.join(map(str,sorted(set(expected)-set(weeks)))) or 'none'
            lines.append(f'|{s}|{grid or "none"}|{missing}|')
        lines+=['', '|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|', '|---|---|---|---:|---|---|']
        for c in t['columns']:
            safe=lambda s:str(s).replace('|','/').replace('\n',' ')
            lines.append(f"|`{safe(c['column'])}`|{safe(c['definition_guess'])}|{c['type']}|{100*c['missing_fraction']:.2f}|{c['validity']}|{c['rule']}|")
        lines.append('')
    lines+=['## Revisions', '', '|Table|Status|Overlapping entity-weeks|Changed values|', '|---|---|---:|---:|']
    for r in m['revisions']:lines.append(f"|{r['table']}|{r['status']}|{r['overlap_rows']}|{r.get('changed_values',0)}|")
    lines+=['', 'The private REVISION_LOG.json includes changed-value count and mean/max absolute revision by column. No comparable prior snapshot means revision frequency is unknown, not zero.', '',
            '## Entity and timing limitations', '',
            'Exact known GSIS identifiers or unambiguous full-name aliases must resolve to a unique completed source-week roster team. Verified historical team/position evidence overrides conflicting vendor display labels, with corrections counted; ambiguous teams remain unmatched. Native identifiers are recognized only by exact existing membership, never guessed from their format. Scheduled-game/opponent/shadow contradictions are quarantined. Identity-unmatched and known-identity/quarantined counts are separate in FPDS_A6_AUDIT.json. Synthetic Defense labels are never assigned a player ID. All unmatched labels/raw evidence remain private. Overlapping split/unit rows may form explicitly labelled arithmetic means; they are never invented team totals. Missing history remains missing on identical control/challenger rows. Untimestamped current shadow assignments/injuries cannot enter target-week predictors.']
    (LAB_ROOT/'docs'/'FPDS_DATA_DICTIONARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    atomic(LAB_ROOT/'docs'/'FPDS_COLUMN_COVERAGE.json',column_coverage)
    write_once(out/'AUDIT.json',summary)
    public=REPORT/'FPDS_A6_AUDIT.json'
    atomic(public,summary)
    return summary


def association(frame, target, columns):
    """Diagnostic only; forbidden raw values never become model inputs."""
    flags=[]
    for c in columns:
        pairs=frame[[c,target]].apply(pd.to_numeric,errors='coerce').dropna()
        if len(pairs)>=100 and pairs[c].nunique()>1 and pairs[target].nunique()>1:
            rho=float(pairs.corr(method='spearman').iloc[0,1])
            if abs(rho)>.9:flags.append({'column':c,'target':target,'n':len(pairs),'abs_rho':abs(rho)})
    return flags
