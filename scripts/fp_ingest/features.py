"""Exact-identity adapter for private GOING model/research consumers.

Returns separate source covariates, never overwrites Champion forecasts or
availability. Multiple filter variants remain separate; no first-file wins.
"""
from .identity import canonical_team, norm_name, TeamError
from .weekly import model_inputs


def player_context(root, profile, season, week, known_by):
    team = canonical_team(profile['team'])
    name = norm_name(profile['name'])
    result = {'player': {}, 'team': {}, 'opponent': {}, 'problems': [],
              'model_status': 'research_features_not_promoted'}
    opponent = canonical_team(profile['opponent']) if profile.get('opponent') else None
    for dataset in model_inputs(root, season, week, known_by):
        columns = dataset['columns']
        def key(base):
            return next((k for k in columns if k.split('.')[-1].lower() == base.lower()), None)
        team_key, name_key, pos_key = key('Team'), key('Name'), key('POS')
        player_table = any('player details' in str(g).lower() for g in dataset.get('groups') or [])
        if player_table and (not pos_key or not name_key or not team_key):
            result['problems'].append({'table':dataset['table'],'problem':'Missing player identity fields; no player values selected'})
            continue
        matched = {'player': [], 'team': [], 'opponent': []}
        for row in dataset['records']:
            raw_team = row.get(team_key) if team_key else row.get(name_key)
            try:row_team = canonical_team(str(raw_team or ''))
            except TeamError:continue
            if pos_key and name_key and not str(row.get(pos_key,'')).startswith('vs.'):
                if row_team == team and norm_name(str(row.get(name_key) or '')) == name and row.get(pos_key) == profile.get('position'):
                    matched['player'].append(row)
            elif row_team in (team, opponent):
                matched['team' if row_team == team else 'opponent'].append(row)
        for scope, rows in matched.items():
            if not rows:continue
            if scope == 'player' and len(rows) != 1:
                result['problems'].append({'table':dataset['table'],'problem':'Ambiguous same-player rows; no values selected'})
                continue
            result[scope].setdefault(dataset['table'], []).append({'scope':dataset['scope'],
                'observed_week':dataset['observed_week'],'known_at':dataset['known_at'],
                'source_sha256':dataset['sha256'],'source_path':dataset['path'],'records':rows})
    return result
