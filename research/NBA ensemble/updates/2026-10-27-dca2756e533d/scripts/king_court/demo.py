"""Entirely synthetic, anonymized accounting fixtures. Never real NBA picks."""
from datetime import datetime, timedelta, timezone

from .common import seal


def fixtures():
    games=[]
    debut={}
    teams=('BOS','NYK')
    minutes=(36,34,32,30,28,28,26,26)
    for season in (2024,2025,2026,2027):
        for day in range(6):
            tip=datetime(season-1,10,10+day*2,23,tzinfo=timezone.utc)
            players=[]
            boxes={}
            for code in teams:
                roster=[]
                for j,m in enumerate(minutes):
                    # Last roster slot is a different new rookie each season.
                    pid=f'fixture:{code}:{j}' if j<7 else f'fixture:{code}:rookie:{season}'
                    debut[pid]=2020 if j<6 else 2026 if j==6 else season
                    if j==6 and season<2026:
                        debut[pid]=2020
                    fgm=4+(day+j)%4
                    tpm=1+j%2
                    ftm=2
                    p=dict(player_id=pid,name=f'Synthetic {code} {j}',team=code,position='G',minutes=float(m),
                           fga=11+j%3,tpa=4,fgm=fgm,tpm=tpm,fta=3,ftm=ftm,
                           pts=2*fgm+tpm+ftm,oreb=j%2,dreb=3+j%3,reb=j%2+3+j%3,ast=1+(day+j)%5)
                    roster.append(p)
                # An established same ID cannot precede its stated debut; use historical alternate.
                if season<2026:
                    roster[6]['player_id']=f'fixture:{code}:prior6'
                    debut[roster[6]['player_id']]=2020
                players.extend(roster)
                boxes[code]={k:sum(p[k] for p in roster) for k in ('pts','reb','ast','fga','fgm','tpa','tpm','fta','ftm','oreb','dreb')}
                boxes[code]['tov']=12
            games.append(dict(game_id=f'fixture:{season}:{day}',season=season,tipoff=tip.isoformat(),
                              home='BOS',away='NYK',game_minutes=48,teams=boxes,players=players,
                              known_at=(tip+timedelta(hours=4)).isoformat(),regular_season=True,
                              event_reconciliation='synthetic_only',lineup_reconciliation='synthetic_only'))
    origin=datetime(2026,10,27,12,tzinfo=timezone.utc)
    gid='fixture:target'
    field=[]
    for p in games[-1]['players']:
        field.append(dict(player_id=p['player_id'],name=p['name'],position=p['position'],team=p['team'],game_id=gid,
                          debut_season=debut[p['player_id']],availability='available',selectable=True,
                          known_at=origin.isoformat(),source='SYNTHETIC FIXTURE',
                          expected_minutes=dict(mean=p['minutes'],sd=3.,known_at=origin.isoformat(),source='SYNTHETIC ROTATION')))
    slate=dict(date='2026-10-27',season=2027,origin=origin.isoformat(),regular_season=True,
               known_at=origin.isoformat(),source='SYNTHETIC FIXTURE',evidence_kind='synthetic',field_complete=True,rosters_complete=True,
               full_terms_verified=False,eligible_game_ids=[gid],eligible_player_ids=[p['player_id'] for p in field],
               offer=dict(date='2026-10-27',pool_bonus_bet_face_value=1000000,source='SYNTHETIC EXAMPLE',requires_prop_win=None),
               games=[dict(game_id=gid,home='BOS',away='NYK',tipoff='2026-10-27T23:00:00+00:00',status='scheduled')],players=field)
    snapshot=seal(dict(games=games,debut_seasons=debut,kind='synthetic_not_real_NBA'))
    return snapshot,slate
