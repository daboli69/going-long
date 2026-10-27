"""Local CLI. All receipts use exclusive creation; no sportsbook interaction."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import numpy as np

from .common import code_receipts, digest, load_sealed, protocol, seal, utc, write_new
from .data import fetch_archives, normalize, validate_slate
from .demo import fixtures
from .events import reconcile
from .research import evaluate_result, forecast_comparison, paired_slate_intervals, parameter_grid, select_parameters


def _json(path):
    return json.loads(Path(path).read_text())


def _save_run(path,output,simulations,slate,kind):
    artifact=Path(path).with_suffix('.npz')
    arrays={'player_ids':np.array(simulations['recency']['player_ids'])}
    arrays.update({f'pra__{name}':sim['pra'] for name,sim in simulations.items()})
    if Path(path).exists() or artifact.exists():
        raise ValueError('Run receipt or sample artifact already exists')
    with artifact.open('xb') as out:
        np.savez_compressed(out,**arrays)
    body=dict(output,kind=kind,slate=slate,recorded_at=datetime.now(timezone.utc).isoformat(),
              simulation_artifact=dict(path=str(artifact),sha256=sha256(artifact.read_bytes()).hexdigest()))
    write_new(path,seal(body))


def main():
    parser=argparse.ArgumentParser(description='Research-only Tuesday King of the Court PRA simulation')
    sub=parser.add_subparsers(dest='command',required=True)
    fetch=sub.add_parser('fetch',help='Preserve free raw archive bytes and retrieval receipts')
    fetch.add_argument('--seasons',nargs='+',type=int,required=True)
    fetch.add_argument('--cache',required=True)
    fetch.add_argument('--include-pbp',action='store_true')
    fetch.add_argument('--output',required=True)
    ingest=sub.add_parser('ingest',help='Reconcile schedules, player boxes and team boxes')
    ingest.add_argument('--manifest',required=True)
    ingest.add_argument('--debut-metadata',help='JSON: debut_seasons, known_at, source; optional for data audit')
    ingest.add_argument('--output',required=True)
    audit=sub.add_parser('audit',help='Report missingness/reconciliation without making picks')
    audit.add_argument('--history',required=True)
    audit.add_argument('--output',required=True)
    events=sub.add_parser('reconcile-pbp',help='Exact-ID NBA live JSON events and optional stint reconciliation')
    events.add_argument('--history',required=True)
    events.add_argument('--pbp',required=True)
    events.add_argument('--crosswalk',required=True)
    events.add_argument('--output',required=True)
    selection=sub.add_parser('select',help='Select decay only on registered earlier pregame folds')
    selection.add_argument('--history',required=True)
    selection.add_argument('--experiment',required=True)
    selection.add_argument('--slates',required=True,help='JSON array of archived pregame manifests')
    selection.add_argument('--outcomes',required=True)
    selection.add_argument('--draws',type=int,default=2000)
    selection.add_argument('--output',required=True)
    register=sub.add_parser('register',help='Preserve actual-time future development/holdout experiment registration')
    register.add_argument('--plan',required=True,help='JSON: development_dates and holdout_dates')
    register.add_argument('--output',required=True)
    for name in ('simulate','freeze'):
        cmd=sub.add_parser(name,help='Local research run' if name=='simulate' else 'Immutable actual-time pregame research capture')
        cmd.add_argument('--history',required=True)
        cmd.add_argument('--slate',required=True)
        group=cmd.add_mutually_exclusive_group(required=True)
        group.add_argument('--selection',help='Sealed earlier-fold parameter selection')
        group.add_argument('--research-parameters',help='Explicit JSON grid member; flagged unselected')
        cmd.add_argument('--ownership',help='JSON array of explicit crowd scenarios')
        cmd.add_argument('--draws',type=int,default=20000)
        cmd.add_argument('--mode',choices=('prospective','retrospective'),default='prospective')
        cmd.add_argument('--output',required=True)
    demo=sub.add_parser('demo',help='Entirely synthetic illustrative run, no real players or ownership')
    demo.add_argument('--draws',type=int,default=2000)
    demo.add_argument('--output',required=True)
    settle=sub.add_parser('settle',help='Append official statistical outcomes; unresolved games stay pending')
    settle.add_argument('--freeze',required=True)
    settle.add_argument('--outcomes',required=True)
    settle.add_argument('--output',required=True)
    evaluate=sub.add_parser('evaluate',help='Whole-slate paired diagnostics from immutable settlements')
    evaluate.add_argument('--settlements',nargs='+',required=True)
    evaluate.add_argument('--selection',help='Required to label cohort registered holdout')
    evaluate.add_argument('--output',required=True)
    args=parser.parse_args()
    if Path(args.output).exists():
        parser.error('Output exists: choose a new receipt path')
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    if args.command=='fetch':
        kinds=('schedule','player','team','pbp') if args.include_pbp else ('schedule','player','team')
        write_new(args.output,fetch_archives(args.seasons,args.cache,kinds))
    elif args.command=='ingest':
        import polars as pl
        manifest=load_sealed(args.manifest)
        rows={'schedule':[],'player':[],'team':[]}
        for source in manifest['sources']:
            if sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:
                raise ValueError('Raw source hash mismatch')
            if source['kind'] in rows:
                rows[source['kind']].extend(pl.read_parquet(source['path']).to_dicts())
        metadata=_json(args.debut_metadata) if args.debut_metadata else {}
        if metadata and (not metadata.get('source') or not metadata.get('known_at')):
            raise ValueError('Debut metadata provenance required')
        observed=max(utc(s['retrieved_at']) for s in manifest['sources']).isoformat()
        body=normalize(rows['schedule'],rows['player'],rows['team'],observed,metadata.get('debut_seasons'))
        body.pop('sha256')
        body.update(sources=manifest['sources'],source_manifest_sha256=manifest['sha256'],debut_metadata=metadata)
        write_new(args.output,seal(body))
    elif args.command=='audit':
        history=load_sealed(args.history)
        seasons=sorted({g['season'] for g in history['games']})
        write_new(args.output,seal(dict(kind='data_audit_not_prediction',history_sha256=history['sha256'],
                    games_by_season={str(s):sum(g['season']==s for g in history['games']) for s in seasons},
                    exclusions=history.get('exclusions',{}),reconciliation_failures=history.get('reconciliation_failures',[]),
                    availability=history.get('historical_availability','unknown'),
                    missing=['historical_pregame_rosters','injury_receipts','potential_assists','actual_rebound_tracking_chances',
                             'promotion_selection_counts','complete_date_specific_terms'],
                    event_reconciled_games=sum(g.get('event_reconciliation')=='reconciled' for g in history['games']))))
    elif args.command=='reconcile-pbp':
        history=load_sealed(args.history)
        crosswalk=_json(args.crosswalk)
        game=next(g for g in history['games'] if g['game_id']==crosswalk['game_id'])
        report=reconcile(_json(args.pbp),game,crosswalk)
        history.pop('sha256')
        # Raw source receipt is retained, not just a Boolean supplied by a caller.
        report['raw_file_sha256']=sha256(Path(args.pbp).read_bytes()).hexdigest()
        report['crosswalk_sha256']=digest(crosswalk)
        report['reconciled_at']=datetime.now(timezone.utc).isoformat()
        game['event_evidence']=report
        game['event_reconciliation']='reconciled' if report['event_agreement'] else 'failed'
        game['lineup_reconciliation']='reconciled' if report['lineup_agreement'] else 'unavailable_or_failed'
        write_new(args.output,seal(history))
    elif args.command=='register':
        from .common import EASTERN
        now=datetime.now(timezone.utc)
        plan=_json(args.plan)
        dev,hold=plan['development_dates'],plan['holdout_dates']
        if (not dev or not hold or len(set(dev+hold))!=len(dev+hold) or max(dev)>=min(hold)
            or len(dev)<protocol()['minimum_selection_slates']):
            raise ValueError('Enough disjoint development dates and later holdout required')
        if any(datetime.fromisoformat(d).date().weekday()!=1 or datetime.fromisoformat(d).date()<=now.astimezone(EASTERN).date() for d in dev+hold):
            raise ValueError('Registration requires future Tuesday dates; no retrospective registration')
        write_new(args.output,seal(dict(plan,kind='experiment_registration',registered_at=now.isoformat(),
                                       model_code_sha256=code_receipts(),protocol_sha256=digest(protocol()))))
    elif args.command=='select':
        write_new(args.output,select_parameters(load_sealed(args.history),load_sealed(args.experiment),_json(args.slates),_json(args.outcomes),args.draws))
    elif args.command in ('simulate','freeze','demo'):
        if args.command=='demo':
            history,slate=fixtures()
            parameters=parameter_grid()[0]
            ids=[p['player_id'] for p in slate['players']]
            scenarios=[dict(name='SYNTHETIC uniform ownership, 100000 other entries',kind='hypothetical',
                            other_entrants=100000,ownership={pid:1/len(ids) for pid in ids})]
            selection=None
            mode='retrospective'
        else:
            history,slate=load_sealed(args.history),_json(args.slate)
            selection=load_sealed(args.selection) if args.selection else None
            parameters=selection['parameters'] if selection else _json(args.research_parameters)
            scenarios=_json(args.ownership) if args.ownership else []
            mode=args.mode
            if args.command=='freeze':
                if slate['evidence_kind']!='prospective' or mode!='prospective':
                    raise ValueError('Official research capture requires prospective evidence')
                slate['origin']=datetime.now(timezone.utc).isoformat()
        output,simulations=forecast_comparison(history,slate,parameters,args.draws,scenarios,mode,selection)
        _save_run(args.output,output,simulations,slate,'prospective_freeze' if args.command=='freeze' else 'synthetic_demo' if args.command=='demo' else 'research_simulation')
    elif args.command=='settle':
        frozen=load_sealed(args.freeze)
        outcome=_json(args.outcomes)
        if not outcome.get('source') or utc(outcome['known_at'])<=max(utc(g['tipoff']) for g in frozen['slate']['games']):
            raise ValueError('Official after-game outcome evidence required')
        target=set(frozen['slate']['eligible_game_ids'])
        if outcome.get('unresolved_game_ids') or outcome.get('voided_game_ids') or set(outcome['completed_game_ids'])!=target:
            write_new(args.output,seal(dict(kind='pending_settlement',freeze_sha256=frozen['sha256'],outcome=outcome,
                                           reason='Incomplete/postponed/voided field; no leader grade invented')))
        else:
            artifact=frozen['simulation_artifact']
            if sha256(Path(artifact['path']).read_bytes()).hexdigest()!=artifact['sha256']:
                raise ValueError('Frozen simulation artifact changed')
            with np.load(artifact['path'],allow_pickle=False) as arrays:
                ids=arrays['player_ids'].tolist()
                evaluation=evaluate_result(frozen,dict(player_ids=ids,pra=arrays['pra__recency']),outcome['values'])
                evaluation['history_comparators']={}
                for variant,value in frozen['history_comparators'].items():
                    if f'pra__{variant}' in arrays:
                        evaluation['history_comparators'][variant]=evaluate_result(value,dict(player_ids=ids,pra=arrays[f'pra__{variant}']),outcome['values'])
            write_new(args.output,seal(dict(kind='statistical_settlement_promo_award_unverified',
                                           freeze_kind=frozen['kind'],freeze_sha256=frozen['sha256'],
                                           model_code_sha256=frozen['receipts']['model_code_sha256'],
                                           selection_sha256=frozen['receipts']['selection_sha256'],outcome=outcome,evaluation=evaluation)))
    else:
        records=[load_sealed(path) for path in args.settlements]
        selected=[r for r in records if 'evaluation' in r]
        dates=[r['evaluation']['slate_date'] for r in selected]
        if len(set(dates))!=len(dates):
            raise ValueError('Duplicate slate observations cannot count as independent trials')
        label='diagnostic_only'
        if args.selection:
            selection=load_sealed(args.selection)
            for r in selected:
                if (r['evaluation']['slate_date'] not in selection['holdout_dates'] or r['freeze_kind']!='prospective_freeze'
                    or r['selection_sha256']!=selection['sha256'] or r['model_code_sha256']!=selection['model_code_sha256']):
                    raise ValueError('Holdout receipt/selection/code mismatch')
            label='registered_holdout_no_automatic_promotion'
        write_new(args.output,seal(dict(kind=label,excluded_pending_records=len(records)-len(selected),
                                       result=paired_slate_intervals([r['evaluation'] for r in selected]))))
    print(json.dumps({'output':args.output,'command':args.command}))


if __name__=='__main__':
    main()
