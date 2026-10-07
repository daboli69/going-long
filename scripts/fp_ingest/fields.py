"""Column use classes (what each Fantasy Points metric may be used for) and the model boundary.

CURRENT   safe descriptive count/fact that can be shown as current evidence
DERIVED   role / deployment / opportunity share that can become a trend or matchup feature
RESEARCH  efficiency or skill measure: a hypothesis, not evidence. Needs historical test -> chronological OOS ->
          calibration -> Champion comparison -> human approval before it influences any model or GOING rating
REDUNDANT GOING already has an equal or better source (nflverse / expected-usage); keep only as a cross-check
UNREVIEWED a column no rule knows (new from Fantasy Points). Never used until someone classifies it
DO_NOT_USE export artifact or unusable for modelling

Everything here is a classification only. Nothing in this module feeds a model.
"""
import re

IDENTITY_GROUPS = {'Player Details', 'Team Details'}
IDENTITY_BASES = {'Rank', 'Name', 'Team', 'POS', 'G', 'Season', 'OPP', 'Location', 'Team Name'}

DO_NOT_USE = {'Rank': 'position in the export sort at download time; depends on filters and sample, not a stable measure'}

REDUNDANT = {
    'ATT', 'CMP', 'CMP %', 'YDS', 'TD', 'INT', 'REC', 'TGT', 'FUM', '1D', 'SACK', 'SACK %', 'SK YDS', 'SCRM', 'TOUCH', 'YFS', 'YPA', 'YPC', 'YPR',
    'YPT', 'YDS/G', 'RuYDS/G', 'RecYDS/G', 'YFS/G', 'RATE', 'ANY/A', 'TGT/G', 'Snaps', 'TM Snaps', 'Snap %', 'SNAPS', 'FP', 'FP/G', 'XFP',
    'XFP/G', 'XTD', 'XTD/G', 'TM XFP', 'XFP %', 'TM ATT', 'TM TGT', 'YAC', 'YAC/REC', 'AY', 'aDOT', 'AY Share', 'TM YDS %', 'TM TD %', 'TGT %',
    'CATCH %', 'RecXFP', 'YFS/TOUCH', 'PPR', 'NON-PPR', 'SK YDS', 'OPP', 'WO', 'WO/G',
}
REDUNDANT_WHY = 'GOING already derives this from nflverse play-by-play / expected-usage; compare, do not duplicate as a second source of truth'

CURRENT = {
    'i5', 'i10', 'i20', 'MTF', 'YACO', 'EXP', 'EXP YDS', 'YBCO', 'DRP', 'DROP YDS', 'TA', 'BAT', 'SPK', 'QB SK', 'QBP', 'TWT', 'HERO', 'CT', 'CC', 'DESIGN', 'CTGT',
    '1READ', 'EZTGT', 'EZTD', 'i20 TGT', 'DP TGT', 'EZATT', 'DB', 'RTE', 'PASS', 'RUSH', 'Deep Throw',
}
CURRENT_WHY = 'descriptive count of what happened; safe to show as current evidence with its week'

DERIVED = {
    'RTE %', 'RTE/G', 'TM RTE %', 'WIDE RTE %', 'SLOT RTE %', 'INLINE RTE %', 'BACK RTE %', 'DB/G', 'TPRR', '1READ %', '1Read %', 'DESIGN %',
    'CTGT %', 'i5 %', 'i10 %', 'i20 %', '1+ %', '3+ %', '5+ %', '10+ %', '15+ %', '20+ %', '30+ %', 'PASS %', 'RUSH %', 'Deep Throw %', 'RPO %', 'CHK %', 'CC %', 'ATT %', 'EXP PLAY %', 'EXP REC %', 'EXP RUN %',
}
DERIVED_WHY = 'role / deployment / opportunity share: can be tracked week to week and compared to expectation'

RESEARCH = {
    'YPRR', 'FP/RR', 'XFP/RR', 'FP/DB', 'FP/OPP', 'SEP SCORE', 'WIN RATE', '+1 Rate', '+2 Rate', '+3 Rate', 'Neg Rate', 'ADOR', 'YPTOE', 'THREAT',
    'CPOE', 'PrROE', 'PRESS %', 'PRESS SK %', 'TTT', 'TTP', 'TTSK', 'TTSC', 'HERO %', 'TWT %', 'ACC %', 'OFF %', 'ADJ CMP %', 'DROP %', 'DRP %',
    'YAC %', 'YACO/ATT', 'YACO %', 'YACO/REC', 'YACO/TOUCH', 'MTF/ATT', 'MTF/REC', 'MTF/TOUCH', 'EXP YDS %', 'Success %', 'STUFF %', 'TD RATE',
    'YBCO/ATT', 'ADJ YBC/ATT', '1D/RR', 'COV GRADE', 'EXP FP/DB', 'EXP FP/RTE', 'DEF COVER 2 %', 'DEF COVER 3 %', 'DEF COVER 4 %', 'DEF COVER 6 %',
    'DEF MAN %', 'QB COVER 2 %', 'QB Cover 3 %', 'QB Cover 4 %', 'QB COVER 6 %', 'QB MAN %', 'DEF FP/DB', 'QB FP/DB', 'FP/RTE', 'RUSH GRADE',
    'PASS GRADE', 'CR %', 'HERO', 'MTF/ATT', 'MAN %', 'ZONE %', '1-HI/MOF C %', '2-HI/MOF O %', 'COVER 0 %', 'COVER 1 %', 'COVER 2 %',
    'COVER 2 MAN %', 'COVER 3 %', 'COVER 4 %', 'COVER 6 %',
}
RESEARCH_WHY = 'efficiency / skill / matchup measure: a hypothesis. Unstable on small samples; needs historical + chronological OOS testing before any model use'

LEAKAGE_NOTE = ('All values are cumulative through the games played in the export. They are point-in-time only if the export was captured '
                'live during that season; a later download of a past season contains future information for any intra-season prediction.')


def base_name(key):
    return key.split('.', 1)[-1].split('#')[0]


def classify_column(key):
    group = key.split('.', 1)[0] if '.' in key else ''
    base = base_name(key)
    if group in IDENTITY_GROUPS or (not group and base in IDENTITY_BASES and base != 'Rank') or (group in ('Offense Stats', 'Defense Stats') and base in ('Team', 'Name')):
        return {'class': 'IDENTITY', 'why': 'row identity / context, not a metric'}
    if base in DO_NOT_USE:
        return {'class': 'DO_NOT_USE', 'why': DO_NOT_USE[base]}
    if base in ('Snaps', 'TM Snaps', 'Snap %') and group in ('Inside 5', 'Inside 10', 'Inside 20'):
        return {'class': 'DERIVED', 'why': 'goal-line / red-zone snap share: GOING has no equivalent source for these splits'}
    if base in REDUNDANT:
        return {'class': 'REDUNDANT', 'why': REDUNDANT_WHY}
    if base in CURRENT:
        return {'class': 'CURRENT', 'why': CURRENT_WHY}
    if base in DERIVED:
        return {'class': 'DERIVED', 'why': DERIVED_WHY}
    if base in RESEARCH:
        return {'class': 'RESEARCH', 'why': RESEARCH_WHY}
    return {'class': 'UNREVIEWED', 'why': 'not classified yet; review before use'}


def unit_hint(key):
    base = base_name(key)
    return 'percent_points' if '%' in base or (base != 'RATE' and base.upper().endswith('RATE')) else 'value'
