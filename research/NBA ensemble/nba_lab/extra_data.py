"""Free player-box archives and official injury-index links; no retrospective joins."""
import re
from html.parser import HTMLParser
from pathlib import Path
import pandas as pd
from .config import CACHE,DATA,ROOT,now,read
from .sources import BASE,fetch,ending_season
from .research_io import update


class Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            if href.startswith('https://ak-static.cms.nba.com/referee/injury/') and href.lower().endswith('.pdf'):self.urls.append(href)


def injury_index(html,retrieved=None):
    retrieved=pd.Timestamp(retrieved or pd.Timestamp.now(tz='UTC'));parser=Links();parser.feed(html)
    records=[]
    for url in set(parser.urls):
        match=re.search(r'Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf',url,re.I)
        if not match:continue
        date,hour,minute,ampm=match.groups()
        time=pd.Timestamp(pd.to_datetime(date+' '+hour+':'+minute+ampm.upper(),format='%Y-%m-%d %I:%M%p')).tz_localize('America/New_York').tz_convert('UTC')
        if time<=retrieved:records.append({'report_time':time.isoformat(),'url':url})
    if not records:raise ValueError('No timestamped official injury links found; schema/source may have changed')
    latest=max(records,key=lambda r:r['report_time'])
    return {'retrieved_at':retrieved.isoformat(),'latest_report':latest,'links':len(records),
            'age_hours':(retrieved-pd.Timestamp(latest['report_time'])).total_seconds()/3600,
            'model_input':False,'warning':'Index/link archived only. PDF statuses have not been parsed or joined to projections.'}


def player_boxes(frame,games):
    required={'game_id','season','athlete_id','team_id','minutes','points','rebounds','assists'}
    if required-set(frame):raise ValueError('Player box schema incomplete: '+','.join(sorted(required-set(frame))))
    d=frame.copy()
    # Some exports encode integer IDs as floats because other rows are missing IDs.
    # Strip only a verified zero fractional part; never round a noninteger identity.
    for key in ('game_id','athlete_id','team_id'):
        labels=d[key].astype('string').str.strip()
        valid=labels.str.fullmatch(r'\d+(?:\.0+)?').fillna(False)
        d[key]=labels.where(valid).str.replace(r'\.0+$','',regex=True)
    if 'season_type' in d:d=d[d.season_type.eq(2)]
    d=d[d.game_id.isin(games.game_id)]
    invalid_id=d.athlete_id.isna()|~d.athlete_id.str.fullmatch(r'\d+')
    unmatched_ids=int(invalid_id.sum());d=d[~invalid_id]
    d=d.drop_duplicates()
    if d.duplicated(['game_id','athlete_id']).any():raise ValueError('Conflicting player/game duplicates; no silent identity resolution')
    identity=games[['game_id','home_id','away_id','tipoff']]
    d=d.merge(identity,on='game_id',validate='many_to_one')
    bad_team=~(d.team_id.eq(d.home_id)|d.team_id.eq(d.away_id)).fillna(False)
    unmatched_teams=int(bad_team.sum());d=d[~bad_team]
    for col in ('minutes','points','rebounds','assists'):d[col]=pd.to_numeric(d[col],errors='coerce')
    d['available_at']=d.tipoff+pd.Timedelta(hours=24)
    coverage={'rows':len(d),'players':int(d.athlete_id.nunique()),'games':int(d.game_id.nunique()),
              'missing_minutes':int(d.minutes.isna().sum()),'zero_minute_rows':int(d.minutes.eq(0).sum()),
              'unmatched_id_rows':unmatched_ids,'wrong_team_rows':unmatched_teams,
              'negative_stat_rows':int(d[['minutes','points','rebounds','assists']].lt(0).any(axis=1).sum()),
              'columns':list(frame.columns),'id_namespace':'ESPN athlete_id; no inferred NBA Stats crosswalk'}
    return d,coverage


def collect(start=2021,end=None,log=print):
    end=end or ending_season()
    games=pd.read_parquet(CACHE/'games.parquet');frames=[];coverage={};issues=[]
    for season in range(start,end+1):
        try:
            path=fetch(BASE+f'espn_nba_player_boxscores/player_box_{season}.parquet',f'player_box_{season}','parquet',ttl_hours=6 if season==end else 24*365)
            d,meta=player_boxes(pd.read_parquet(path),games)
            coverage[str(season)]=meta;frames.append(d);log(f'Player boxes {season}: {meta["rows"]} rows, {meta["games"]} games')
        except Exception as error:
            issues.append({'source':'player_boxes','season':season,'error':type(error).__name__,'message':str(error)[:200]});log(str(issues[-1]))
    if frames:
        players=pd.concat(frames,ignore_index=True)
        if players.duplicated(['game_id','athlete_id']).any():raise ValueError('Cross-export player/game duplicates')
        players.to_parquet(CACHE/'player_boxes.parquet',index=False)
    try:
        season_label=f'{end-1}-{str(end)[-2:]}'
        url=f'https://official.nba.com/nba-injury-report-{season_label}-season'
        key='official_injury_index_'+str(end)
        path=fetch(url,key,'html',ttl_hours=.25)
        actual_retrieval=read(DATA/'SOURCES.json')[key]['checked_at']
        injury=injury_index(Path(path).read_text(encoding='utf-8'),actual_retrieval);injury['source_url']=url
        injury['processed_at']=now()
        update(DATA/'INJURY_CONTEXT.json',injury)
    except Exception as error:
        issues.append({'source':'official_injury_index','error':type(error).__name__,'message':str(error)[:200]});injury=None
    report={'created_at':now(),'coverage':coverage,'issues':issues,'injury_context':injury,
            'status':'Player props prerequisite only; no player projection trained or injury adjustment claimed.'}
    update(DATA/'EXTRA_DATA.json',report);return report
