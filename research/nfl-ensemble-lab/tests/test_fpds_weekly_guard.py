"""Calendar admission fixtures only; no network, subscription files or fits."""
import pandas as pd
import pytest
from lab.fpds_weekly_guard import next_week


def schedule():
    return pd.DataFrame({
        'season':[2026,2026,2026], 'week':[7,8,9],
        'completed':[False,False,False],
        'kickoff_utc':pd.to_datetime(['2026-10-26T00:20Z','2026-10-30T00:15Z','2026-11-06T01:15Z'],utc=True),
    })


def test_stale_completed_flags_do_not_select_last_week():
    assert next_week(schedule(),pd.Timestamp('2026-10-28T12:00Z'))==8


def test_fresh_and_stale_completion_flags_select_same_future_week():
    games=schedule(); fresh=games.copy(); fresh.loc[fresh.week.eq(7),'completed']=True
    now=pd.Timestamp('2026-10-28T12:00Z')
    assert next_week(games,now)==next_week(fresh,now)==8


def test_no_future_regular_season_game_stops_clearly():
    with pytest.raises(ValueError,match='No future regular-season games'):
        next_week(schedule(),pd.Timestamp('2026-12-01T00:00Z'))


def test_other_seasons_and_postseason_do_not_choose_target_week():
    games=schedule(); games.loc[1,'season']=2027; games.loc[2,'week']=19
    with pytest.raises(ValueError,match='No future regular-season games'):
        next_week(games,pd.Timestamp('2026-10-28T12:00Z'))
