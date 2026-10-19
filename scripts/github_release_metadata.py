"""Read public NFLverse release metadata with the runner's scoped GitHub token."""
import os
import requests


def release_metadata(tag):
    if tag not in ('stats_team', 'stats_player'):
        raise ValueError('Unsupported public release metadata')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'going-long-refresh'}
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    if token:
        headers['Authorization'] = 'Bearer ' + token
    response = requests.get('https://api.github.com/repos/nflverse/nflverse-data/releases/tags/' + tag,
                            headers=headers, timeout=60, allow_redirects=False)
    if 300 <= response.status_code < 400:
        raise RuntimeError('Unexpected public release metadata redirect')
    response.raise_for_status()
    return response.json()
