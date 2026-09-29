"""Read-only walk-forward diagnostics; never learn weights from individual wins."""
import math
from collections import defaultdict
from build_pipeline import finite, fit_stat, season_fit


def evaluate(profiles, season):
    output = {}
    positions = {'pass_yds':{'QB'}, 'pass_tds':{'QB'}, 'rush_yds':{'QB','RB'},
                 'rec_yds':{'WR','TE','RB'}, 'receptions':{'WR','TE','RB'}, 'atd':{'QB','RB','WR','TE'}}
    for market, eligible in positions.items():
        errors = []
        for profile in profiles.values():
            if profile.get('position') not in eligible:
                continue
            games = sorted(profile.get('games', []), key=lambda r:(r['season'],r['week']))
            for i, game in enumerate(games):
                prior = [r for r in games[max(0,i-12):i] if finite(r.get(market))]
                if game['season'] != season or len(prior)<5 or not finite(game.get(market)):
                    continue
                baseline = fit_stat([r[market] for r in prior], 'poisson')['mean']
                candidate = season_fit(prior, market, 'poisson', season, candidate=True)['mean']
                errors.append(((baseline-game[market])**2, (candidate-game[market])**2))
        output[market] = {'n':len(errors), 'baseline_rmse':math.sqrt(sum(x for x,y in errors)/len(errors)) if errors else None,
            'candidate_rmse':math.sqrt(sum(y for x,y in errors)/len(errors)) if errors else None}
    return {'season':season, 'markets':output, 'promotion':'not promoted',
        'method':'strict prior-appearance replay of archived trailing windows; two historical game equivalents for volume, six for TD counts',
        'limitations':'Small current-season development sample; no odds/ROI claim; QB replay includes relief appearances in the legacy archive; require prospective role-matched validation.'}


def results_review(tracker):
    """First observed exact contracts, automatic binary settlements only."""
    settlements = {r['payload']['prediction_id']:r['payload'] for r in tracker.get('records', [])
                   if r.get('kind')=='settlement' and r.get('payload',{}).get('method')=='published_full_game_result'}
    groups, seen = defaultdict(list), set()
    predictions = sorted((r['payload'] for r in tracker.get('records',[]) if r.get('kind')=='prediction'),key=lambda p:p.get('observed_at',''))
    for p in predictions:
        key = p.get('canonical_contract') or p.get('selection')
        if not key or key in seen or p.get('sport')!='nfl': continue
        seen.add(key)
        outcome = settlements.get(p.get('id'),{})
        if outcome.get('status') not in ('win','loss') or not finite(p.get('probability')):continue
        push = p.get('model_evidence',{}).get('push') or 0
        if not 0 <= push < 1: continue
        prob = p['probability']/(1-push)
        if not 0 <= prob <= 1:continue
        groups[p['market']].append((prob,int(outcome['status']=='win'),p.get('event')))
    return {market:{'contracts':len(rows),'distinct_games':len({r[2] for r in rows}),
            'brier':sum((p-y)**2 for p,y,_ in rows)/len(rows),
            'mean_probability':sum(p for p,y,_ in rows)/len(rows), 'win_rate':sum(y for p,y,_ in rows)/len(rows)}
            for market,rows in groups.items()}
