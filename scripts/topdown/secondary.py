"""Dated venue scoring sanity check. Never replaces the reference-book probability."""
import statistics
from .model import secondary_baseline,stamp


def context(quote,games,names,now):
    home,away=names.get(quote['home']),names.get(quote['away'])
    if not home or not away:return None
    prior=[g for g in games if g.get('completed') and stamp(g.get('kickoff')) is not None and stamp(g['kickoff'])<min(now,stamp(quote['kickoff'])) and isinstance(g.get('home_score'),(int,float)) and isinstance(g.get('away_score'),(int,float))]
    if not prior:return None
    latest_season=max(g['season'] for g in prior)
    # Derive the scheduled week from the exact dated matchup, not calendar arithmetic.
    fixture=next((g for g in games if g.get('home')==home and g.get('away')==away and stamp(g.get('kickoff'))==stamp(quote['kickoff'])),None)
    if not fixture:return None
    year,week=fixture['season'],fixture['week']
    league_rows=[g for g in prior if g['season']==year-1] or prior
    league=statistics.mean([g[k] for g in league_rows for k in ('home_score','away_score')])
    estimates=[]
    for team,venue in ((home,'home'),(away,'away')):
        current=sorted([g for g in prior if g['season']==year and g[venue]==team],key=lambda g:stamp(g['kickoff']))
        # No current games means league prior, not a fabricated observed team rating.
        rates=[g[venue+'_score'] for g in current]
        estimate=secondary_baseline(statistics.mean(rates) if rates else league,statistics.mean(rates[-4:]) if rates else league,len(rates),league,week)
        estimates.append(dict(estimate,team=team,venue=venue,games=len(rates),season=year))
    return {'estimated_total':sum(e['rating'] for e in estimates),'teams':estimates,'league_reference':league,'week':week,'method':'40% season / 60% last four venue games; overlapping evidence counted once; prior weight 8 games in weeks 1–4, then 4. Scoring-only secondary check, not a market price.'}
