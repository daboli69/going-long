"""Free public downloads, immutable content archives and explicit source status."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import time
import pandas as pd
import requests
from .config import RAW,CACHE,DATA,now,stamp,read,atomic

BASE='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/'
URLS={'schedule':BASE+'espn_nba_schedules/nba_schedule_{season}.parquet',
      'team_box':BASE+'espn_nba_team_boxscores/team_box_{season}.parquet'}
ALLOWED=('https://github.com/sportsdataverse/','https://site.api.espn.com/',
         'https://stats.nba.com/','https://api.pbpstats.com/')


def fetch(url,key,extension='json',ttl_hours=12,session=None):
    if not any(url.startswith(prefix) for prefix in ALLOWED):raise ValueError('Unapproved source URL')
    manifest=read(DATA/'SOURCES.json') if (DATA/'SOURCES.json').exists() else {}
    prior=manifest.get(key)
    if prior and Path(prior['path']).exists() and (pd.Timestamp.now(tz='UTC')-pd.Timestamp(prior['checked_at'])).total_seconds()<ttl_hours*3600:
        return Path(prior['path'])
    response=(session or requests).get(url,timeout=(10,35),headers={'User-Agent':'NBA-Ensemble-Local-Research/1.0'})
    response.raise_for_status();body=response.content
    if len(body)>40_000_000:raise ValueError('Source exceeds the bounded download size')
    if extension=='parquet':pd.read_parquet(io.BytesIO(body))
    elif extension=='json':json.loads(body)
    checksum=hashlib.sha256(body).hexdigest();directory=RAW/'archive'/key;directory.mkdir(parents=True,exist_ok=True)
    existing=list(directory.glob('*_'+checksum[:16]+'.'+extension))
    path=existing[0] if existing else directory/(stamp()+'_'+checksum[:16]+'.'+extension)
    if not existing:
        with path.open('xb') as f:f.write(body)
    manifest[key]={'url':url,'sha256':checksum,'path':str(path),'checked_at':now(),'bytes':len(body)}
    atomic(DATA/'SOURCES.json',manifest)
    return path


def schedules(frame):
    required=['game_id','season','season_type','date','home_id','away_id','home_abbreviation','away_abbreviation','status_type_completed','home_score','away_score']
    if set(required)-set(frame):raise ValueError('SportsDataverse schedule schema is incomplete')
    d=frame[frame.season_type.eq(2)].copy()
    if 'status_type_name' in d:
        d=d[~d.status_type_name.fillna('').str.contains('POSTPONED|CANCELED|CANCELLED',case=False)]
    if 'notes_headline' in d:
        d=d[~d.notes_headline.fillna('').str.contains(r'(?:Cup|Tournament).*Championship',case=False,regex=True)]
    out=pd.DataFrame({'game_id':d.game_id.astype(str),'season':d.season.astype(int),
        'tipoff':pd.to_datetime(d.date,utc=True,errors='coerce'),'home_id':d.home_id.astype(str),'away_id':d.away_id.astype(str),
        'home':d.home_abbreviation,'away':d.away_abbreviation,'completed':d.status_type_completed.eq(True),
        'home_score':pd.to_numeric(d.home_score,errors='coerce'),'away_score':pd.to_numeric(d.away_score,errors='coerce'),
        'neutral':d.get('neutral_site',pd.Series(False,index=d.index)).fillna(False).astype(bool)})
    out=out.dropna(subset=['tipoff','home','away'])
    out=out[out.home_id.ne(out.away_id)]
    out.loc[~out.completed,['home_score','away_score']]=float('nan')
    bad=out.completed&(out.home_score.isna()|out.away_score.isna()|out.home_score.eq(out.away_score))
    if bad.any():raise ValueError('Completed games have missing/tied scores')
    if out.game_id.duplicated().any():raise ValueError('Duplicate canonical game IDs')
    return out


def boxes(frame):
    if {'game_id','team_id','team_score'}-set(frame):raise ValueError('Team box schema is incomplete')
    mapping={'team_score':'points','field_goals_made':'fgm','field_goals_attempted':'fga',
             'three_point_field_goals_made':'fg3m','free_throws_attempted':'fta',
             'offensive_rebounds':'oreb','defensive_rebounds':'dreb','total_turnovers':'tov'}
    out=pd.DataFrame({'game_id':frame.game_id.astype(str),'team_id':frame.team_id.astype(str)})
    for source,target in mapping.items():out[target]=pd.to_numeric(frame[source],errors='coerce') if source in frame else float('nan')
    out=out.drop_duplicates()
    if out.duplicated(['game_id','team_id']).any():raise ValueError('Conflicting duplicate team boxes')
    return out


def scoreboard(payload):
    result=[]
    for event in payload.get('events',[]):
        competition=event['competitions'][0]
        if int(event.get('season',{}).get('type',0))!=2:continue
        if any(word in event['status']['type'].get('name','') for word in ('POSTPONED','CANCELED','CANCELLED')):continue
        notes=' '.join(n.get('headline','') for n in competition.get('notes',[])).lower()
        if ('cup' in notes or 'tournament' in notes) and 'championship' in notes:continue
        teams={r['homeAway']:r for r in competition['competitors']}
        if not {'home','away'}<=set(teams):continue
        home,away=teams['home'],teams['away'];complete=event['status']['type']['completed']
        result.append({'game_id':str(event['id']),'season':int(event['season']['year']),
            'tipoff':pd.Timestamp(event['date']),'home_id':str(home['team']['id']),'away_id':str(away['team']['id']),
            'home':home['team']['abbreviation'],'away':away['team']['abbreviation'],'completed':bool(complete),
            'home_score':float(home.get('score',0)) if complete else float('nan'),
            'away_score':float(away.get('score',0)) if complete else float('nan'),
            'neutral':bool(competition.get('neutralSite',False))})
    return pd.DataFrame(result)


def refresh(start=2015,end=None,log=print):
    end=end or pd.Timestamp.now(tz='America/New_York').year+1
    frames=[];team_frames=[];issues=[]
    directory=read(fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams','nba_team_directory',ttl_hours=24*30))
    teams=[r['team'] for r in directory['sports'][0]['leagues'][0]['teams']]
    team_ids={str(t['id']) for t in teams}
    if len(team_ids)<30:raise ValueError('Official NBA team directory incomplete')
    for season in range(start,end+1):
        for kind,target,normalizer in [('schedule',frames,schedules),('team_box',team_frames,boxes)]:
            try:
                path=fetch(URLS[kind].format(season=season),f'{kind}_{season}','parquet',ttl_hours=6 if season==end else 24*365)
                d=normalizer(pd.read_parquet(path));target.append(d)
                log(f'{season} {kind}: {len(d)} rows')
            except Exception as error:
                issues.append({'season':season,'source':kind,'error':type(error).__name__})
                log(f'{season} {kind}: unavailable ({type(error).__name__}); retained source error')
    if not frames:raise RuntimeError('No valid NBA schedule; refresh stopped')
    games=pd.concat(frames,ignore_index=True).drop_duplicates('game_id',keep='last')
    # Current daily scoreboard: no credentials, odds fields never retained as inputs.
    for date in pd.date_range(pd.Timestamp.now(tz='UTC').normalize()-pd.Timedelta(days=2),periods=10):
        try:
            path=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+date.strftime('%Y%m%d'),
                       'scoreboard_'+date.strftime('%Y%m%d'),ttl_hours=1)
            extra=scoreboard(read(path))
            if len(extra):games=pd.concat([games,extra],ignore_index=True).drop_duplicates('game_id',keep='last')
        except Exception as error:issues.append({'source':'daily_scoreboard','date':str(date.date()),'error':type(error).__name__})
    team=pd.concat(team_frames,ignore_index=True).drop_duplicates(['game_id','team_id'],keep='last') if team_frames else pd.DataFrame(columns=['game_id','team_id','points'])
    non_nba=~games.home_id.isin(team_ids)|~games.away_id.isin(team_ids)
    excluded=int(non_nba.sum());games=games[~non_nba].copy()
    team=team[team.game_id.isin(games.game_id)&team.team_id.isin(team_ids)]
    CACHE.mkdir(parents=True,exist_ok=True)
    games.sort_values(['tipoff','game_id']).to_parquet(CACHE/'games.parquet',index=False)
    team.to_parquet(CACHE/'team_boxes.parquet',index=False)
    summary={'created_at':now(),'games':len(games),'team_boxes':len(team),'issues':issues,
             'season_counts':games.groupby('season').size().to_dict(),'non_nba_rows_excluded':excluded,
             'active_feature_sources':['SportsDataverse ESPN schedule + team boxes'],
             'warning':'Historical files are revised retrospective data. Current injury/lineup effects are NOT modeled in v1.'}
    atomic(DATA/'HEALTH.json',summary);return summary


def optional_context(source,season=2026):
    """Explicit audit downloads; never silently enter historical model features."""
    if source=='pbpstats':
        label=f'{season-1}-{str(season)[-2:]}'
        url=f'https://api.pbpstats.com/get-totals/nba?Season={label}&SeasonType=Regular+Season&Type=Team'
    elif source=='nba_api':
        # Exact public endpoint wrapped by nba_api; NBA's server may block requests.
        from urllib.parse import urlencode
        params=dict(PlayerOrTeam='T',LeagueID='00',Season=f'{season-1}-{str(season)[-2:]}',SeasonType='Regular Season')
        url='https://stats.nba.com/stats/leaguegamefinder?'+urlencode(params)
    else:raise ValueError('Unknown optional source')
    path=fetch(url,source+'_'+str(season),ttl_hours=24)
    result={'source':source,'season':season,'retrieved_at':now(),'path':str(path),'model_input':False,
            'warning':'Different ID namespace / revised season totals; context-only pending a preregistered feature audit.'}
    atomic(DATA/(source+'_CONTEXT.json'),result);return result
