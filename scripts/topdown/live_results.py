"""Public ESPN final scores; an in-progress score can never settle a pick."""
import json
from datetime import datetime, timezone, timedelta
import requests
from .model import stamp


def parse_finals(body,sport,now,names):
    rows={}
    for event in body.get('events',[]):
        status=event.get('status',{}).get('type',{})
        if not status.get('completed') or status.get('name') not in ('STATUS_FINAL','STATUS_FINAL_OVERTIME'):continue
        kickoff=stamp(event.get('date'))
        if kickoff is None or kickoff>=now:continue
        competitors=event.get('competitions',[{}])[0].get('competitors',[])
        sides={c.get('homeAway'):c for c in competitors}
        if set(sides)!= {'home','away'}:continue
        try:
            home,away=sides['home'],sides['away']
            hn,an=home['team']['displayName'],away['team']['displayName']
            if sport=='nfl':hn,an=names.get(hn),names.get(an)
            if not hn or not an:continue
            hs,aws=int(home['score']),int(away['score'])
            if min(hs,aws)<0:continue
        except (KeyError,ValueError,TypeError):continue
        rows[f"{sport}|espn|{event['id']}"]=dict(sport=sport,id=event['id'],home=hn,away=an,kickoff=event['date'],homeScore=hs,awayScore=aws,confirmed_final=True,source_url=f"https://www.espn.com/{'college-football' if sport=='ncaa' else 'nfl'}/game/_/gameId/{event['id']}")
    return rows


def refresh_finals(root,now):
    path=root/'data/results.json';data=json.loads(path.read_text(encoding='utf-8'))
    names=json.loads((root/'data/history.json').read_text(encoding='utf-8'))['betting'].get('team_names',{})
    status={};today=datetime.fromtimestamp(now,timezone.utc)
    for sport,slug in [('nfl','nfl'),('ncaa','college-football')]:
        total=0
        try:
            for delta in (1,0):
                params={'dates':(today-timedelta(days=delta)).strftime('%Y%m%d'),'limit':1000}
                if sport=='ncaa':params['groups']=80
                r=requests.get(f'https://site.api.espn.com/apis/site/v2/sports/football/{slug}/scoreboard',params=params,timeout=15);r.raise_for_status()
                finals=parse_finals(r.json(),sport,now,names)
                # Replace an older source's duplicate game, preserving exact event matching.
                for key,g in finals.items():
                    from .college import team_id
                    identity=lambda x: (team_id(x['home']),team_id(x['away'])) if sport=='ncaa' else (x['home'],x['away'])
                    for old,prev in list(data['games'].items()):
                        if prev['sport']==sport and identity(prev)==identity(g) and abs((stamp(prev['kickoff']) or 0)-stamp(g['kickoff']))<60:data['games'].pop(old)
                    data['games'][key]=g
                total+=len(finals)
            status[sport]={'status':'loaded','finals':total}
        except (requests.RequestException,ValueError,KeyError,TypeError) as exc:status[sport]={'status':'unavailable','reason':type(exc).__name__}
    data['generated_at']=datetime.fromtimestamp(now,timezone.utc).isoformat();data['live_sources']=status
    temp=path.with_suffix('.live.tmp');temp.write_text(json.dumps(data,allow_nan=False),encoding='utf-8');temp.replace(path)
    return status
