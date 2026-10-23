from pathlib import Path
import pandas as pd
import pytest
from nba_lab import injury_reports as I

FIXTURE=Path(__file__).parent/'fixtures'/'Injury-Report_2022-01-15_05PM.pdf'
# Column starts mirror the 2025-26 layout (no header row on later pages).
X=dict(date=24,time=120,matchup=201,team=265,player=426,status=587,reason=667)


def words(top,**cells):
    out=[]
    for col,text in cells.items():
        x=X[col]
        for token in text.split():out.append({'x0':x,'top':top,'text':token});x+=len(token)*5+3
    return out


def title(top=45):return words(top,matchup='Injury Report: 01/15/26 05:00 PM')
def header(top=107):
    return words(top,date='Game Date',time='Game Time',matchup='Matchup',team='Team',player='Player Name',status='Current Status',reason='Reason')


def test_real_2022_pdf_parses_header_time_rows_and_not_yet_submitted():
    stamp,rows,issues=I.parse_pdf(FIXTURE.read_bytes())
    assert stamp==pd.Timestamp('2022-01-15 17:30',tz=I.ET) and not issues
    d=pd.DataFrame(rows)
    assert len(d)==123 and d.not_yet_submitted.sum()==5
    first=d.iloc[0]
    assert (first.matchup,first.team,first.player_name_raw,first.status,first.reason)==('TOR@MIL','Milwaukee Bucks','Dowtin, Jeff','Out','G League - On Assignment')
    holiday=d[d.player_name_raw.eq('Holiday, Jrue')].iloc[0]
    assert holiday.team=='Milwaukee Bucks' and holiday.reason=='Injury/Illness - Left Ankle; Soreness'
    assert d[d.not_yet_submitted].player_name_raw.isna().all()
    assert set(d.status)<=set(I.STATUSES)|{I.NYS}


def test_wrapped_reason_and_cross_page_continuation_attach_to_their_row():
    page1=title()+header()+words(129,date='01/15/2026',time='07:00 (ET)',matchup='PHX@DET',team='Phoenix Suns',player='Booker, Devin',status='Out',reason='Injury/Illness - Left Ankle; Sprain')
    page1+=words(144,reason='Injury/Illness - Right Hamstring;')+words(151,player='Green, Jalen',status='Out')+words(158,reason='Strain')
    page1+=words(173,team='Detroit Pistons',player='Ivey, Jaden',status='Questionable',reason='Injury/Illness - Left')
    page2=title()+words(80,reason='Knee; Soreness')+words(102,player='Jones, Isaac',status='Out',reason='G League - Two-Way')
    page2+=words(124,time='10:00 (ET)',matchup='MIN@HOU',team='Minnesota Timberwolves',player='NOT YET SUBMITTED')
    stamp,rows,issues=I.parse_pages([page1,page2])
    assert not issues and stamp.hour==17
    d=pd.DataFrame(rows).set_index('player_name_raw',drop=False)
    assert d.loc['Green, Jalen','reason']=='Injury/Illness - Right Hamstring; Strain'
    assert d.loc['Booker, Devin','reason']=='Injury/Illness - Left Ankle; Sprain'
    assert d.loc['Ivey, Jaden','reason']=='Injury/Illness - Left Knee; Soreness'
    assert d.loc['Jones, Isaac',['team','matchup','game_time']].tolist()==['Detroit Pistons','PHX@DET','07:00 (ET)']
    nys=pd.DataFrame(rows).iloc[-1]
    assert nys.not_yet_submitted and nys.team=='Minnesota Timberwolves' and nys.status==I.NYS and nys.player_name_raw is None


def test_unattached_fragment_is_reported_not_merged():
    page=title()+header()+words(129,date='01/15/2026',time='07:00 (ET)',matchup='PHX@DET',team='Phoenix Suns',player='Booker, Devin',status='Out',reason='Rest')
    page+=words(151,player='Green, Jalen',status='Out',reason='Rest')+words(300,reason='stray text')
    _,rows,issues=I.parse_pages([page])
    assert len(rows)==2 and rows[-1]['reason']=='Rest' and issues[0]['issue']=='unattached fragment'


def test_slot_urls_switch_format_and_never_pass_the_cutoff():
    assert I.slot_url(pd.Timestamp('2022-01-15 17:00',tz=I.ET)).endswith('Injury-Report_2022-01-15_05PM.pdf')
    assert I.slot_url(pd.Timestamp('2026-01-15 17:15',tz=I.ET)).endswith('Injury-Report_2026-01-15_05_15PM.pdf')
    slots=I.candidate_slots(pd.Timestamp('2026-01-15 18:20',tz=I.ET))
    assert slots[0]==pd.Timestamp('2026-01-15 18:15',tz=I.ET) and all(s<=pd.Timestamp('2026-01-15 18:20',tz=I.ET) for s in slots)
    early=I.candidate_slots(pd.Timestamp('2022-01-15 02:30',tz=I.ET))
    assert early==[pd.Timestamp(f'2022-01-15 0{h}:00',tz=I.ET) for h in (2,1,0)]


def test_pregame_report_rejects_a_slot_whose_header_time_is_after_cutoff(monkeypatch):
    body=FIXTURE.read_bytes()
    def fetch(url,manifest,session):
        if url.endswith('_05PM.pdf') or url.endswith('_06PM.pdf'):
            return body,{'sha256':'x','retrieved_at':'now','last_modified':'2022-01-15T22:30:02+00:00'}
        return None,{'status':403}
    monkeypatch.setattr(I,'fetch',fetch)
    # Cutoff 17:15 ET: 06PM is after cutoff; 05PM slot's header says 17:30 -> also rejected.
    # Cutoff 17:30 would still reject it: Last-Modified is 17:30:02.
    out=I.pregame_report('2022-01-15',pd.Timestamp('2022-01-15 18:15',tz=I.ET).tz_convert('UTC'),{},None)
    assert out['url'] is None
    out=I.pregame_report('2022-01-15',pd.Timestamp('2022-01-15 18:31',tz=I.ET).tz_convert('UTC'),{},None)
    assert out['url'].endswith('_05PM.pdf') and out['available_at']==pd.Timestamp('2022-01-15T22:30:02Z')
    assert out['available_at']<=out['cutoff']


def test_names_map_only_by_exact_team_season_identity():
    assert I.display_name('Moore Jr., Wendell')=='Wendell Moore Jr.' and I.display_name('Nene')=='Nene'
    assert I.normalize_name('Luka Dončić')=='luka doncic' and I.normalize_name('Gary Trent Jr.',True)=='gary trent'
    games=pd.DataFrame([{'game_id':'g1','season':2022,'tipoff':pd.Timestamp('2022-01-16T00:00Z'),'home_id':'15','away_id':'28'}])
    players=pd.DataFrame([
        {'season':2022,'team_id':'15','team_display_name':'Milwaukee Bucks','athlete_id':'1','athlete_display_name':'Jrue Holiday'},
        {'season':2022,'team_id':'28','team_display_name':'Toronto Raptors','athlete_id':'2','athlete_display_name':'Gary Trent'},
        {'season':2022,'team_id':'28','team_display_name':'Toronto Raptors','athlete_id':'3','athlete_display_name':'Chris Boucher'},
        {'season':2022,'team_id':'15','team_display_name':'Milwaukee Bucks','athlete_id':'4','athlete_display_name':'Chris Boucher'},
        {'season':2022,'team_id':'99','team_display_name':'Other Team','athlete_id':'5','athlete_display_name':'Traded Guy'}])
    rows=pd.DataFrame([{'season':2022,'game_date':'01/15/2022','team':'Milwaukee Bucks','player_name':'Jrue Holiday','not_yet_submitted':False},
        {'season':2022,'game_date':'01/15/2022','team':'Toronto Raptors','player_name':'Gary Trent Jr.','not_yet_submitted':False},
        {'season':2022,'game_date':'01/15/2022','team':'Toronto Raptors','player_name':'Jrue Holliday','not_yet_submitted':False},
        {'season':2022,'game_date':'01/15/2022','team':'Toronto Raptors','player_name':'Traded Guy','not_yet_submitted':False},
        {'season':2022,'game_date':'01/15/2022','team':'Milwaukee Bucks','player_name':None,'not_yet_submitted':True}])
    out=I.map_rows(rows,games,players)
    assert out.game_id.tolist()==['g1']*5 and out.team_id.tolist()==['15','28','28','28','15']
    assert out.athlete_id.tolist()==['1','2',None,'5',None]
    assert out.match_method.tolist()==['team_exact','team_suffix','unmatched','season_exact',None]
    # A name shared by two players in the season is ambiguous outside the team.
    amb=I.map_rows(rows.iloc[[0]].assign(team='Toronto Raptors',player_name='Chris Boucher'),games,players)
    assert amb.athlete_id.tolist()==['3']
    others=pd.concat([players.query("athlete_id!='3'"),players.iloc[[4]].assign(athlete_id='6',athlete_display_name='Chris Boucher')])
    amb=I.map_rows(rows.iloc[[0]].assign(team='Toronto Raptors',player_name='Chris Boucher'),games,others)
    assert amb.match_method.tolist()==['ambiguous_season_exact'] and amb.athlete_id.isna().all()


def test_historical_misses_are_not_requested_again():
    manifest={'u':{'status':403,'retrieved_at':'t'}}
    class Boom:
        def get(self,*a,**k):raise AssertionError('network used')
    assert I.fetch('u',manifest,Boom())==(None,manifest['u'])


def test_three_line_reason_attaches_to_its_row():
    page=title()+header()+words(304,date='12/01/2023',time='08:00 (ET)',matchup='IND@MIA',team='Indiana Pacers',player='Haliburton, Tyrese',status='Questionable',reason='Knee')
    page+=words(326,reason='Injury/Illness - Left Knee, Heel; Left')+words(340,player='Smith, Jalen',status='Out',reason='Knee Bone Bruise, Left Heel')
    page+=words(354,reason='Contusion')+words(376,player='Tshiebwe, Oscar',status='Questionable',reason='G League - Two-Way')
    _,rows,issues=I.parse_pages([page])
    assert not issues and rows[1]['reason']=='Injury/Illness - Left Knee, Heel; Left Knee Bone Bruise, Left Heel Contusion'
    assert rows[0]['reason']=='Knee' and rows[2]['reason']=='G League - Two-Way'


def test_fallback_levels_for_players_without_a_box_that_season():
    assert I.normalize_name('O.G. Anunoby')==I.normalize_name('OG Anunoby')=='og anunoby'
    games=pd.DataFrame([{'game_id':'g1','season':2022,'tipoff':pd.Timestamp('2022-01-16T00:00Z'),'home_id':'3','away_id':'7'}])
    players=pd.DataFrame([
        {'season':2021,'team_id':'3','team_display_name':'New Orleans Pelicans','athlete_id':'10','athlete_display_name':'Zion Williamson'},
        {'season':2021,'team_id':'7','team_display_name':'Denver Nuggets','athlete_id':'11','athlete_display_name':'Some Veteran'},
        {'season':2022,'team_id':'3','team_display_name':'New Orleans Pelicans','athlete_id':'12','athlete_display_name':'Other Player'}])
    rows=pd.DataFrame([{'season':2022,'game_date':'01/15/2022','team':'New Orleans Pelicans','player_name':'Zion Williamson','not_yet_submitted':False},
        {'season':2022,'game_date':'01/15/2022','team':'New Orleans Pelicans','player_name':'Some Veteran','not_yet_submitted':False},
        {'season':2022,'game_date':'01/15/2022','team':'Denver Nuggets','player_name':'Bub Carrington','not_yet_submitted':False}])
    out=I.map_rows(rows,games,players)
    assert out.athlete_id.tolist()==['10','11',None]
    assert out.match_method.tolist()==['team_other_season','any_exact','unmatched']
