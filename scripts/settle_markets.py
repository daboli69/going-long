"""Settle published full-game observations without backfilling missing player stats."""
import json
from datetime import datetime,timezone
from topdown.model import stamp,uid
from build_pipeline import match_player

MAP={'player_passing_yards':'pass_yds','player_rushing_yards':'rush_yds','player_receiving_yards':'rec_yds','player_receptions':'receptions','player_passing_tds':'pass_tds'}


def settle(journal,root,now):
    results=json.loads((root/'data/results.json').read_text());h=json.loads((root/'data/history.json').read_text())['betting']
    names=h.get('team_names',{});profiles=h.get('profiles',{});existing={s['prediction_id'] for s in journal.rows('settlement')}
    for p in journal.rows('prediction'):
        if not p.get('actionable') and not p.get('tracking_group'):continue
        if stamp(p.get('observed_at')) is None or stamp(p['observed_at']) >= (stamp(p['kickoff']) or 0):continue
        if p['id'] in existing or stamp(p['kickoff']) is None or now<=stamp(p['kickoff']):continue
        sport=p.get('sport','nfl')
        if sport=='ncaa':
            from topdown.college import team_id
            home,away=team_id(p['home']),team_id(p['away'])
            games=[g for g in results['games'].values() if g['sport']=='ncaa' and home and away and team_id(g['home'])==home and team_id(g['away'])==away and abs(stamp(g['kickoff'])-stamp(p['kickoff']))<60]
        else:
            home,away=names.get(p['home'],p['home']),names.get(p['away'],p['away'])
            games=[g for g in results['games'].values() if g['sport']=='nfl' and g['home']==home and g['away']==away and abs(stamp(g['kickoff'])-stamp(p['kickoff']))<60]
        if len(games)!=1:continue
        g=games[0];market=p['market'];value=None
        if market=='totals':value=g['homeScore']+g['awayScore'];target=p['line'];over=p['side_index']==0
        elif market=='spreads':value=g['homeScore']-g['awayScore']+p['line'];target=0;over=p['side_index']==0
        elif market=='h2h':value=g['homeScore']-g['awayScore'];target=0;over=p['side_index']==0
        elif market in MAP:
            matches=[(pid,profile) for pid,profile in profiles.items() if (pid==p.get('profile_id') or profile.get('name')==p.get('player')) and profile.get('team') in (home,away)]
            if len(matches)!=1:continue
            date=datetime.fromtimestamp(stamp(g['kickoff']),timezone.utc).date().isoformat()
            # NFL game dates are Eastern calendar dates, including late-night kickoffs.
            from zoneinfo import ZoneInfo
            date=datetime.fromtimestamp(stamp(g['kickoff']),ZoneInfo('America/New_York')).date().isoformat()
            stat=results['players'].get(matches[0][0]+'|'+date,{})
            value=stat.get(MAP[market]);target=p['line'];over=p['side_index']==0
        else:continue
        if value is None:continue
        status='refund' if value==target else ('win' if (value>target)==over else 'loss')
        at=datetime.fromtimestamp(now,timezone.utc).isoformat()
        row={'sport':sport,'prediction_id':p['id'],'event':p['event'],'status':status,'actual':value,'observed_at':at,'source_url':g.get('source_url','https://github.com/daboli69/going-long/blob/main/data/results.json'),'source_generated_at':results['generated_at'],'source_sha256':uid(g,results['generated_at']),'method':'published_full_game_result','rules_note':'Research settlement; book-specific injury/void exceptions require reconciliation'}
        journal.append('settlement',uid(p['id'],'settlement'),row)
