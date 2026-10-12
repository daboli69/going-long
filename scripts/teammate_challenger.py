"""Offline opportunity challenger; never imported by the production pipeline.

Frozen prototype: three verified games per condition, four games of shrinkage
toward the same-player overall target rate. Constants are research choices,
not fitted/calibrated probabilities. See MODEL_RESEARCH.md for promotion gate.
"""
import math

VERSION = 'teammate-target-research-v1'
MINIMUM_PER_CONDITION = 3
PRIOR_GAMES = 4


def forecast(*, champion_mean, all_targets, with_targets, without_targets,
             teammate_state, pregame_verified=False):
    """Scale a receiving projection by a shrunk conditional opportunity rate.

    Caller must supply prior completed same-team/current-season appearances,
    explicit OUT or positive-snap cohorts and verified pregame availability.
    Missing participation must be excluded, not classified as WITHOUT.
    """
    result = {'version': VERSION, 'status': 'blocked', 'champion': champion_mean,
              'challenger': None, 'reason': None}
    if pregame_verified is not True or teammate_state not in ('playing', 'out'):
        result['reason'] = 'Exact-game pregame participation evidence missing.'
        return result
    samples = (all_targets, with_targets, without_targets)
    if (not isinstance(champion_mean, (int, float)) or isinstance(champion_mean, bool)
            or not math.isfinite(champion_mean) or champion_mean < 0
            or any(not isinstance(xs, (list, tuple)) for xs in samples)
            or any(not isinstance(x, (int, float)) or isinstance(x, bool)
                   or not math.isfinite(x) or x < 0 for xs in samples for x in xs)):
        result['reason'] = 'Invalid model or opportunity inputs.'
        return result
    if (min(len(with_targets), len(without_targets)) < MINIMUM_PER_CONDITION
            or len(all_targets) < len(with_targets) + len(without_targets)):
        result['reason'] = 'At least three games in each verified condition required.'
        return result
    overall = sum(all_targets) / len(all_targets)
    if overall <= 0:
        result['reason'] = 'No observed targets to scale.'
        return result
    group = with_targets if teammate_state == 'playing' else without_targets
    conditional = (sum(group) + PRIOR_GAMES * overall) / (len(group) + PRIOR_GAMES)
    result.update(status='research_only', reason='Unvalidated conditional opportunity scenario.',
                  overall_targets=overall, conditional_targets=conditional,
                  challenger=champion_mean * conditional / overall)
    return result
