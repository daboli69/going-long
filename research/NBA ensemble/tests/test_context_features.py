import numpy as np
import pandas as pd
import pytest
from nba_lab import features as F
from nba_lab import context_features as C


def fixture(n=25):
    games = pd.DataFrame([dict(game_id=str(i), season=2024,
        tipoff=pd.Timestamp('2024-01-01T00:00Z') + pd.Timedelta(days=2*i),
        home_id='1', away_id='2', home='ONE', away='TWO', home_score=110+i%3,
        away_score=100+i%2, completed=True, neutral=False) for i in range(n)])
    boxes = pd.DataFrame([dict(game_id=g.game_id, team_id=team, points=score,
        fgm=40, fg3m=10, fga=85, fta=20, oreb=10, dreb=30, tov=12)
        for g in games.itertuples() for team, score in ((g.home_id,g.home_score),(g.away_id,g.away_score))])
    return games, boxes


def build(games, boxes, asof='2025-01-01T00:00Z'):
    base, _ = F.build(games, boxes, asof=asof)
    return base, C.build(base, games, boxes)


def test_preserves_base_and_explicit_whitelists():
    games, boxes = fixture()
    base, context = build(games, boxes)
    pd.testing.assert_frame_equal(base, context[base.columns])
    assert len(C.AGE_COLUMNS) == 11 and len(C.SHARED_COLUMNS) == 6
    assert not set((*C.AGE_COLUMNS,*C.SHARED_COLUMNS)) & {'home_win','home_score','away_score','tipoff'}
    assert context.iloc[-1].home_season_history_20 == 20


def test_target_and_future_outcome_box_canary():
    games, boxes = fixture()
    _, before = build(games, boxes)
    games.loc[20:, ['home_score','away_score']] = [70,150]
    boxes.loc[boxes.game_id.astype(int).ge(20),'points'] = 999
    boxes.loc[boxes.game_id.astype(int).ge(20),'fga'] = 900
    _, after = build(games, boxes)
    pd.testing.assert_frame_equal(before.loc[:20,list(C.AGE_COLUMNS+C.SHARED_COLUMNS)],
                                  after.loc[:20,list(C.AGE_COLUMNS+C.SHARED_COLUMNS)])


def test_strict_release_and_asof_future_cap():
    games, boxes = fixture(4)
    games.loc[1,'tipoff'] = games.loc[0,'tipoff'] + pd.Timedelta(hours=24)
    _, context = build(games, boxes)
    assert context.loc[1,'home_season_history_20'] == 0
    assert np.isnan(context.loc[1,'home_shared_ortg_20'])
    _, capped = build(games, boxes, asof='2024-01-02T00:00:00Z')
    assert capped.home_season_history_20.eq(0).all()
    assert capped.context_latest_available_at.isna().all()


def test_season_boundary_tracks_carryover_and_calendar_age():
    games, boxes = fixture(4)
    games.loc[2:,'season'] = 2025
    games.loc[2,'tipoff'] = pd.Timestamp('2024-10-01T00:00Z')
    games.loc[3,'tipoff'] = pd.Timestamp('2024-10-04T00:00Z')
    _, context = build(games, boxes)
    assert context.loc[2,'home_form_age_days'] == 180
    assert context.loc[2,'home_prior_season_fraction_20'] == 1
    assert context.loc[2,'home_season_history_20'] == 0
    assert context.loc[3,'home_form_age_days'] == 3
    assert context.loc[3,'home_season_history_20'] == 1
    assert context.loc[3,'home_prior_season_fraction_20'] == pytest.approx(2/3)


def test_shared_denominator_and_missing_or_inconsistent_box():
    games, boxes = fixture(3)
    boxes.loc[boxes.team_id.eq('2'),'fga'] = 95
    _, context = build(games, boxes)
    denominator = ((85+.44*20-10+12)+(95+.44*20-10+12))/2
    assert context.loc[1,'home_shared_ortg_20'] == pytest.approx(11000/denominator)
    assert context.loc[1,'home_shared_drtg_20'] == pytest.approx(10000/denominator)
    assert context.loc[1,'home_shared_ortg_20'] == context.loc[1,'away_shared_drtg_20']
    for bad in (boxes[~(boxes.game_id.eq('0') & boxes.team_id.eq('2'))].copy(), boxes.copy()):
        if len(bad)==len(boxes): bad.loc[bad.game_id.eq('0'),'points'] = 999
        _, broken = build(games, bad)
        assert np.isnan(broken.loc[1,'home_shared_ortg_20'])
        assert broken.loc[1,'home_season_history_20'] == 1


def test_duplicates_and_replacing_existing_context_refused():
    games, boxes = fixture(3)
    base, context = build(games, boxes)
    with pytest.raises(ValueError, match='already present'): C.build(context,games,boxes)
    with pytest.raises(ValueError, match='Duplicate'): C.build(base,games,pd.concat([boxes,boxes.iloc[:1]]))
