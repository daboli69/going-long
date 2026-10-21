"""Deterministic header/table-driven trial manifest; no outcome selection."""
from .common import STATS, SOURCE
import re


def title(path):
    stem = re.sub(r'\s*\(\d+\)$', '', path.stem)
    marker = re.search(r'(?:weeks?)[\s_-]*(?:1[\s_-]*[-–to]+[\s_-]*)?(\d+)\s*$', stem, re.I)
    week = int(marker.group(1)) if marker else None
    if marker:
        stem = stem[:marker.start()]
    return re.sub(r'[^a-z0-9]+', '_', stem.lower()).strip('_'), week


def family(table):
    if 'injury' in table or 'lineup' in table: return 'H7'
    if any(s in table for s in ('separation', 'coverage', 'cornerback', 'shadow', 'allowed')): return 'H5'
    if 'receiving' in table: return 'H1'
    if any(s in table for s in ('rushing', 'bell_cow', 'efficiency')): return 'H2'
    if 'passing' in table: return 'H4'
    return 'H6'


def table_targets(table):
    f = family(table)
    if f == 'H1': return ('rec', 'rec_yds')
    if f == 'H2': return ('rush_yds', 'anytime_td')
    if f == 'H4': return ('pass_yds', 'pass_tds')
    if f == 'H5': return ('rec_yds', 'anytime_td')
    if f == 'H7': return ('rec_yds', 'rush_yds')
    return ('rec_yds', 'rush_yds')


def manifest(tables):
    trials = []
    def add(stat, arm, group='all', model='linear', fam=None):
        trials.append(dict(id=f'{stat}__{arm}__{group}__{model}', stat=stat, arm=arm, group=group,
                           model=model, family=fam or ('H6' if stat in ('margin', 'total', 'win') else 'H9')))
    for stat in STATS:
        add(stat, 'control')
        add(stat, 'all')
    for table in sorted(tables):
        for stat in table_targets(table):
            add(stat, 'add', table, fam=family(table))
            add(stat, 'leave', table, fam=family(table))
    for stat in STATS:
        for f in ('H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7'):
            add(stat, 'family', f, fam=f)
        for model in ('hist', 'xgboost', 'mlp', 'structural_proxy', 'equal', 'weighted', 'stacked'):
            add(stat, 'all', model=model)
        for model in ('shrink', 'distribution'):
            add(stat, 'all', model=model, fam='H8')
    for stat in ('margin', 'total', 'win'):
        for arm in ('control', 'all'):
            add(stat, arm, fam='H6')
        add(stat, 'all', model='hist', fam='H6')
        if stat != 'win': add(stat, 'all', model='blend', fam='H6')
    for arm in ('control', 'all'):
        add('first_td', arm, fam='H3')
    return {'schema': 1, 'trial_budget': len(trials), 'refit_weeks': [1,5,9,13,17],
            'discovery': [2022,2023,2024], 'validation': 2025, 'descriptive': 2026,
            'tables': sorted(tables), 'trials': trials}
