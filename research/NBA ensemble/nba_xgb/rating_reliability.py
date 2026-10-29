"""Split-half reliability of the stint-based player ratings.

Within one season, games are split into two halves by game-id parity. The same ridge model (penalty 3000, no time decay) is fitted on each half;
the correlation of player net ratings across halves, for players with enough possessions in both halves, is stepped up with Spearman-Brown.
Reliability near 1 means ratings are mostly signal; near 0 means mostly noise.
"""
import json
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.linalg import cho_factor, cho_solve
from . import data, rapm
from .avail_study import OUT, DOCS


def fit_masked(design, mask, lam):
    X = design.X[mask]
    w = design.poss[mask]
    Xw = X.T @ sparse.diags(w)
    A = (Xw @ X).toarray()
    pen = np.full(A.shape[0], lam)
    pen[:2] = 1e-6
    A[np.diag_indices_from(A)] += pen
    beta = cho_solve(cho_factor(A), Xw @ design.y[mask])
    expo = np.asarray(X[:, 2:2 + design.P].T @ w).ravel()
    P = design.P
    return beta[2:2 + P] - beta[2 + P:], expo


def run(min_poss=300.0, lam=3000.0):
    games, _ = data.load()
    stints = pd.read_parquet(OUT / 'stints.parquet')
    stints = stints[stints.season >= 2021]
    design = rapm.Design(stints, games)
    season_of = games.set_index('game_id').season
    gs = pd.Series(design.game).map(season_of).values
    half = pd.Series(design.game).map(lambda g: int(g) % 2).values
    out = {}
    for s in range(2022, 2027):
        in_s = gs == s
        n1, e1 = fit_masked(design, in_s & (half == 0), lam)
        n2, e2 = fit_masked(design, in_s & (half == 1), lam)
        ok = (e1 >= min_poss) & (e2 >= min_poss)
        assert ok.sum() > 50, f'only {ok.sum()} players with enough possessions in season {s}: the reliability would be meaningless'
        r = float(np.corrcoef(n1[ok], n2[ok])[0, 1])
        rho = float(pd.Series(n1[ok]).corr(pd.Series(n2[ok]), method='spearman'))
        out[s] = {'players': int(ok.sum()), 'pearson_half_corr': r, 'spearman_half_corr': rho,
                  'spearman_brown_reliability': 2 * r / (1 + r), 'sd_half1': float(n1[ok].std()), 'sd_half2': float(n2[ok].std())}
        print(s, out[s], flush=True)
    # same without shrinkage as a reference for how much signal the penalty keeps
    (OUT / 'RATING_RELIABILITY.json').write_text(json.dumps({'penalty': lam, 'min_possessions_each_half': min_poss, 'seasons': out}, indent=2),
                                                 encoding='utf-8')
    return out


if __name__ == '__main__':
    run()
