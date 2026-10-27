"""The only candidate model repair: paired empirical conditional FGA pools."""
import math
from datetime import timedelta
import numpy as np

from scripts.king_court.common import utc
from scripts.king_court.history import effective_n, recency_weights


def possessions(game):
    home,away=game['teams'][game['home']],game['teams'][game['away']]
    return .5*(home['fga']-home['oreb']+home['tov']+.44*home['fta']+
               away['fga']-away['oreb']+away['tov']+.44*away['fta'])


class PairedFGA:
    """Zero-centered residual ratios preserve v1 conditional means in expectation.

    Both teams use one earlier game block per draw. Sparse support is reported;
    this finite empirical distribution cannot establish unobserved extreme tails.
    """
    def __init__(self,games,origin,season,parameters,teams,seed=271026):
        selected=[g for g in games if season-3<=g['season']<=season and utc(g['tipoff'])+timedelta(hours=36)<origin]
        w=recency_weights(selected,origin,season,parameters)
        if len(selected)<30 or not w.sum():
            raise ValueError('Insufficient paired FGA history')
        self.probability=w/w.sum()
        ratios=np.array([[g['teams'][g['home']]['fga']/possessions(g),g['teams'][g['away']]['fga']/possessions(g)] for g in selected])
        self.residuals=ratios-np.average(ratios,weights=w,axis=0)
        self.rng=np.random.default_rng(seed)
        self.teams=teams
        self.evidence=dict(games=len(selected),effective_sample_size=effective_n(w),
                           history_max_tipoff=max(g['tipoff'] for g in selected),
                           centered_weighted_residual_mean=np.average(self.residuals,weights=w,axis=0).tolist(),
                           weighted_residual_covariance=((self.residuals*self.probability[:,None]).T@self.residuals).tolist(),
                           clipping_draws=0,total_draws=0,season_weight_shares={str(s):float(sum(v for g,v in zip(selected,self.probability) if g['season']==s)) for s in sorted({g['season'] for g in selected})})

    def __call__(self,game,pace):
        indexes=self.rng.choice(len(self.residuals),size=len(pace),p=self.probability)
        result={}
        for side,(code,opponent) in enumerate(((game['home'],game['away']),(game['away'],game['home']))):
            mu=math.sqrt(self.teams[code]['fga_poss']*self.teams[opponent]['allowed_fga_poss'])
            rate=mu+self.residuals[indexes,side]
            self.evidence['clipping_draws']+=int(np.sum(rate<0))
            self.evidence['total_draws']+=len(rate)
            continuous=np.maximum(0,rate*pace)
            lower=np.floor(continuous)
            result[code]=(lower+self.rng.binomial(1,continuous-lower)).astype(np.int64)
        return result
