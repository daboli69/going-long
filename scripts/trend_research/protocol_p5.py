"""Frozen protocols P5-1 (weekly end-zone/inside-20 target TD role) and P5-2 (pace and totals vs matched pregame totals), P5-3 (real-archive audit).

This module holds ONLY the specifications. It is committed and registered in the ledger BEFORE any runner for these experiments exists, so the
hash proves the protocol was fixed before an outcome was computed for them. Runners live in experiments14.py and must not edit these dicts.

Evidence status of the data (stated in every spec): 2021-2025 outcomes were already inspected by earlier work (E1-E14, P3-x, JP-x, P4-1) and are
DEVELOPMENT evidence, not an untouched holdout. Only 2026 Week 6+ games that have not been played when the shadow pipeline captures them are untouched.
"""
from .experiments11 import BLOCK_DEFS, C_V2, DEV, HOLD, MIN_EFFECT, PEN_ANY, VAL

FP_EZ = ['fp_eztgt12', 'fp_eztd12', 'fp_i20tgt12', 'fp_eztgt6']
FP_EZ_DEFS = {'fp_eztgt12': "Fantasy Points weekly receiving end-zone targets, mean of the player's last 12 FP weekly rows before the target week (cross-season window)",
              'fp_eztd12': 'same, end-zone receiving touchdowns', 'fp_i20tgt12': 'same, targets inside the 20', 'fp_eztgt6': 'same as fp_eztgt12 over the last 6 rows'}
FREE_BLOCKS = ['OPP', 'ROLE', 'TREND', 'TEAM', 'INJ', 'REG', 'POS']

DATA_STATUS = ('2021-2025 outcomes are previously inspected development evidence (JP-2 already scored 2024 and 2025 on the free blocks; E1-E14, P3-x and P4-1 used the same seasons). '
               'Results below are therefore not an untouched holdout. A positive result can only qualify a feature for prospective shadow collection.')

P51_RULE = {'ACCEPT_FOR_SHADOW': 'validation gain > 0 AND holdout gain >= 0.001 nats per player-game AND the Bonferroni-adjusted (2 comparisons) player-clustered 95% interval of the holdout gain has a lower bound > 0',
            'REJECT': 'holdout gain <= 0 OR the adjusted interval upper bound < 0.001 nats',
            'INCONCLUSIVE': 'anything else', 'no_retrospective_change': 'these thresholds are fixed here and are not altered after outcomes are seen; a different rule would be a new experiment id'}

P52_RULE = {'ACCEPT_FOR_SHADOW': 'pooled Brier gain of the model over the equal-weight de-vigged pregame market (paired, game-clustered 2000-draw bootstrap, 95%) has an interval lower bound > 0 AND relative gain >= 0.5% AND the model is better in both evaluation periods',
            'REJECT': 'pooled gain <= 0 OR the interval upper bound < 0.5% of the market Brier',
            'INCONCLUSIVE': 'anything else', 'no_retrospective_change': 'fixed before any model-vs-market score for these experiments was computed'}

SPECS = {
    'P5-1': {
        'id': 'P5-1', 'status_note': DATA_STATUS,
        'title': 'Anytime TD: do weekly Fantasy Points end-zone and inside-20 target histories add to the Champion v2 rate and to the free-data scoring-role blocks?',
        'hypothesis': 'Prior-week end-zone targets, end-zone receiving TDs and inside-20 targets improve the log loss of the anytime-TD probability beyond (a) the recalibrated Champion v2 rate and (b) the full JP-2 free-data block model.',
        'football_rationale': 'Touchdowns follow scoring-zone looks. The free pbp blocks already count inside-20 targets and yard-line expected TDs, so the likely outcome is no additional information; this tests whether the licensed labels differ enough to matter.',
        'data_that_exists': 'receiving_advanced_weekly 2021-2025: EZTGT, EZTD, i20 TGT per player-game (WR/TE/RB with receiving rows). No historical goal-line CARRIES exist: rushing i5 is only a season-style percentage and 2026 offense_snaps inside-5/10/20 starts in 2026; neither is used. Goal-line carries are a prospective-only feature.',
        'population': 'JP-2 population (Champion-ready QB/RB/WR/TE player-games 2021-2025, >= 5 earlier appearances) restricted to RB/WR/TE with >= 1 FP receiving row among the 6 rows before the target week; the SAME rows score every model. Coverage loss is reported per season and position.',
        'features': {k: FP_EZ_DEFS[k] for k in FP_EZ}, 'free_blocks': FREE_BLOCKS, 'free_block_features': {b: list(BLOCK_DEFS[b]) for b in FREE_BLOCKS},
        'models': {'B0': 'Champion v2 anytime rate, uncalibrated', 'B0c': 'logit recalibration of log Champion rate (dev fit)', 'B1c': 'last-12 TDs per game, recalibrated (frequency baseline)',
                   'B2c': 'B0c + rz_tgt12 + inside5_touch12 (free simple opportunity baseline)', 'BF': 'B0c + all seven free JP-2 blocks (strongest free model)',
                   'M1': 'B0c + FP end-zone features', 'M2': 'BF + FP end-zone features'},
        'fit': {'seasons': list(DEV), 'method': f'ridge logistic, penalty {PEN_ANY} on standardized features, log Champion rate and intercept unpenalised; median fill and 1st/99th winsorising from development rows; no refit', 'seed': 20261015},
        'splits': {'development': list(DEV), 'validation': [VAL], 'holdout': [HOLD], 'chronological': True},
        'primary_comparisons': ['M1 vs B0c', 'M2 vs BF'], 'secondary': ['M1 vs B2c', 'single features vs B0c (descriptive)', 'by position', 'calibration slope and intercept of each model on holdout'],
        'metric': 'mean log loss per player-game (primary); Brier; calibration slope; ECE with 10 bins', 'uncertainty': 'player-clustered bootstrap of the paired per-row loss difference, 2000 draws, Bonferroni-adjusted for 2 primary comparisons',
        'decision_rule': P51_RULE, 'min_effect_nats': 0.001, 'leakage': 'FP rows used are strictly earlier weeks (merge_asof, exact matches disallowed); outcomes from the target game only; FP archive stamp known_at is retrospective, so availability is assumed at the end of each prior game',
        'limitations': 'No prop prices exist for historical TD markets in the archive sample used here, so this scores probabilities, not returns. FP weekly values are licensed and local.',
        'markets': ['anytime TD']},
    'P5-2': {
        'id': 'P5-2', 'status_note': DATA_STATUS,
        'title': 'Pace and pass tendency vs the matched pregame total: does lagged same-season pace add information beyond the posted total?',
        'hypothesis': 'Combined lagged team snaps per game and pass tendency (Fantasy Points weekly run/pass report) predict actual total minus posted total beyond the posted line, recent scoring and public (nflverse) pace.',
        'football_rationale': 'Total points = possessions x efficiency. The market already prices pace, and the production Champion game model carries no information beyond the line (research/calibration/GAME_LINES.md); a pace feature would have to see something the line does not.',
        'population': 'Regular-season games. Development: nflverse games 2021-2023 with the posted total_line (outcome = total - line). Evaluation: archive games with a matched pregame total (one board per game, actual-schedule gate) in 2025 (period A) and 2026 Weeks 1-5 (period B); 2024 is evaluated ONLY for models not needing FP pace, and its FP-model games are counted as excluded.',
        'missing_data_handling': 'The 2024 run_pass_report_weekly export does not exist: no 2024 FP pace feature is computed, imputed or taken from season totals; 2024 games are excluded from every FP-feature model and reported as a coverage loss. Features use SAME-SEASON prior games only (>= 3 prior team games, mean of the last 6), so 2025 does not borrow 2023 and 2026 does not borrow 2025. Early-season games without 3 prior games are excluded for all models on identical rows.',
        'features': {'pts6': 'sum of both teams mean points scored+allowed per game over last 6 same-season games, minus the posted line (simple recent-scoring baseline)',
                     'nfl_plays6': 'both teams nflverse pass attempts + carries per game, last 6 same-season games, summed', 'nfl_pass6': 'both teams mean nflverse pass rate, last 6',
                     'fp_snaps6': 'both teams FP Overall.SNAPS per game, last 6, summed', 'fp_pass6': 'both teams FP Overall.PASS %, last 6, mean', 'fp_neutral6': 'both teams FP Neutral.PASS %, last 6, mean'},
        'models': {'MKT': 'equal-weight de-vigged pregame market over books, same line and snapshot (Champion market-anchored game model equals this)', 'CH_RAW': 'raw Champion trailing average, weight 1 on (pts6 - line) with no fitting',
                   'B_PTS': 'line + ridge on pts6', 'B_NFL': 'B_PTS + nfl_plays6, nfl_pass6', 'C_FP': 'B_NFL + fp_snaps6, fp_pass6, fp_neutral6'},
        'fit': {'seasons': [2021, 2022, 2023], 'method': 'stats.Ridge alpha 10 on standardized features, target = total - posted line; sigma = residual SD on development; p_over = Phi(r_hat / sigma); no tuning on 2025/2026', 'seed': 20261015},
        'matching': 'model p is compared with the equal-weight de-vigged pregame P(over) of the SAME game, line, book set and snapshot from scripts/missions_history_export.py; pushes removed; forecast asOf = kickoff of the latest prior game used + 4h and must precede the snapshot or the forecast is refused',
        'primary_comparison': 'C_FP vs MKT Brier on periods A+B pooled; B_NFL vs MKT and C_FP vs B_NFL secondary (beyond public pace)',
        'metric': 'Brier (primary), log loss, calibration bins, over rate', 'uncertainty': 'paired game-clustered bootstrap, 2000 draws, 95%',
        'decision_rule': P52_RULE, 'leakage': 'only strictly earlier same-season games; closing nflverse total_line is used only for development training and for the pts6 baseline offset, never to score evaluation',
        'limitations': 'one pre-kickoff board per game about 30 min before kickoff, not a verified close: no closing-line-value claim is possible. About 280 games per season: small samples, wide intervals expected.',
        'markets': ['game total']},
    'P5-3': {
        'id': 'P5-3', 'status_note': DATA_STATUS,
        'title': 'Real-archive audit of the game-line comparison (actual-game mapping, market/period, lines, books, paired sides, de-vig, timestamps)',
        'checks': ['each exported game maps to exactly one completed NFL schedule game within 36h and the exported home/away match nflverse games.csv for that date',
                   'exported final scores equal nflverse games.csv scores', 'markets are full-game h2h/spreads/totals only (no period or alternate markets in the quotes used)',
                   'spread pairs have line_home == -line_away, total pairs share one line, moneyline has exactly one quote per side per book',
                   'quote_at <= snapshot_at < actual kickoff for every quote used; report the distribution of snapshot-to-kickoff and quote-to-snapshot lags',
                   'one decision snapshot per game; no later-than-kickoff observation used', 'de-vig overround within (0.985, 1.2) for pairs used; count crossed or odd pairs',
                   'sides: home/over = side A, y computed from the actual score, pushes dropped'],
        'timestamps_distinguished': {'snapshot_at': 'time the provider board was captured', 'quote_at': 'bookmaker last update of the quote', 'forecast_asOf': 'time a model forecast was created', 'feature_available_at': 'time the latest input feature became known'},
        'comparison': 'scripts/missions_backtest.cjs on the real exported records (equal-weight, research-weighted and learned consensus, walk-forward) and with the P5-2 totals forecasts',
        'decision_rule': {'PASS': 'every check holds with 0 violations or documented exclusions below 1% of games', 'FAIL': 'any check with an unexplained violation'},
        'limitations': 'closing prices are absent so CLV is not supported; a correct pregame-price comparison is supported',
        'markets': ['moneyline', 'spread', 'total']},
}
