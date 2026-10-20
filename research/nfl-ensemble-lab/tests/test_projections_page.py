"""Offline AppTests exercise actual Phase 10 render/filter behavior."""
from pathlib import Path
import os
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from app.phase10_pages import latest_sheet, load


@pytest.fixture
def sheets(tmp_path, monkeypatch):
    import requests
    def no_network(*a, **kw):
        raise AssertionError("Page render attempted network access")
    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    base = dict(row_type="player",game_id="2026_07_NE_CHI",team="NE",stat="pass_yds",projection=180.,q10=100.,q50=180.,q90=280.,market_line=195.,consensus_line=195.,p_over=.4,p_under=.6,p_push=0.,line_type="consensus",line_status="current",is_consensus_representative=True,quote_time=now,training_cutoff_date="2026-10-19",no_vig_market_probability=.5,coherence_flag="gap",stability_flag="stable",scenario_sensitivity="unknown",confidence_tier="B")
    rows=[]
    for name, extras in (("Skew",dict(projection=200.,q50=190.)),("Plain",dict(team="CHI")),("Duplicate",dict(is_consensus_representative=False)),("Alternate",dict(line_type="alternate")),("DFS",dict(line_type="DFS-pickem")),("Exchange",dict(line_type="exchange")),("Stale",dict(quote_time="2020-01-01T00:00:00Z"))):
        rows.append(base|dict(name=name,pid=name)|extras)
    rows += [base|dict(row_type="game",pid="",name="game",stat=s,projection=v,q50=v,market_line=v,consensus_line=v,market_anchored_projection=v+1) for s,v in (("margin",3.),("total",45.))]
    rows.append(base|dict(row_type="first_td",pid="first",name="First",stat="first_td",projection=.1))
    frame=pd.DataFrame(rows)
    for kind in ("projections","leans"):
        frame.to_csv(tmp_path/f"{kind}_2026_w07_r02_20261020T185328300076Z.csv",index=False)
    pd.DataFrame([dict(game_id="2026_07_NE_CHI",team="NE",player_pass_yds=180.,team_pass_yds=250.)]).to_csv(tmp_path/"projections_2026_w07_r02_20261020T185328300076Z_coherence.csv",index=False)
    return tmp_path


def app(directory,kind="projections"):
    return AppTest.from_string(f"from app.phase10_pages import render\nrender({kind!r}, {str(directory)!r})").run(timeout=30)


def players(at):
    return next(x.value for x in at.dataframe if "name" in x.value.columns)


def checkbox(at,label):
    return next(x for x in at.checkbox if x.label==label)


def test_pages_render_and_filter(sheets):
    at=app(sheets)
    assert not at.exception
    assert set(players(at).name)=={"Skew","Plain"}
    assert len(at.tabs)==5
    assert at.warning
    checkbox(at,"Include alternate").check().run()
    assert not at.exception
    assert "Alternate" in set(players(at).name)
    next(x for x in at.multiselect if x.label=="Team").select("CHI").run()
    assert list(players(at).name)==["Plain"]
    assert len(at.get("download_button"))>=3


def test_leans_skew_and_stale_toggles(sheets):
    at=app(sheets,"leans")
    assert not at.exception
    assert list(players(at).name)==["Plain"]
    checkbox(at,"Include skew-flagged rows").check().run()
    assert set(players(at).name)=={"Plain","Skew"}
    checkbox(at,"Include stale / unavailable rows").check().run()
    assert "Stale" in set(players(at).name)


@pytest.mark.parametrize("empty",[False,True])
def test_missing_or_empty_sheet(tmp_path,empty):
    if empty:
        pd.DataFrame(columns=["row_type","game_id","stat"]).to_csv(tmp_path/"projections_2026_w07_r03_20261020T190000Z.csv",index=False)
    at=app(tmp_path)
    assert not at.exception
    assert at.info


def test_revision_selection_ignores_mtime(tmp_path):
    old=tmp_path/"projections_2026_w07_r02_20261020T200000Z.csv"
    new=tmp_path/"projections_2026_w07_r03_20261020T190000123456Z.csv"
    for p in (old,new):p.write_text("a\n1\n")
    os.utime(old,(9999999999,9999999999))
    assert latest_sheet(tmp_path,"projections")==new
    companion=tmp_path/(new.stem+"_coherence.csv");companion.write_text("a\n1\n")
    assert latest_sheet(tmp_path,"projections")==new


def test_cache_invalidates_changed_file(tmp_path):
    p=tmp_path/"table.csv";p.write_text("a\n1\n")
    assert len(load(p))==1
    p.write_text("a\n1\n2\n");os.utime(p,ns=(p.stat().st_atime_ns,p.stat().st_mtime_ns+1000000))
    assert len(load(p))==2
