import json
import numpy as np
import pandas as pd
import pytest
from lab.props.amendment2.sheets import consensus, compare, coherence, leans, classify


def test_consensus_excludes_pickem_exchange_and_breaks_ties_deterministically():
    rows=[{"game_id":"g","pid":"p","stat":"rec","book":b,"market_line":v,"gap":3}
          for b,v in [("b",4.5),("a",4.5),("c",5.5),("d",5.5),("novig",9.5),("underdog",9.5)]]
    d=consensus(pd.DataFrame(rows))
    assert d.consensus_line.eq(4.5).all()
    assert d.loc[d.is_consensus_representative,"book"].tolist()==["a"]
    assert d.loc[d.book.eq("novig"),"line_type"].iloc[0]=="exchange"
    assert d.loc[d.book.eq("underdog"),"line_type"].iloc[0]=="DFS-pickem"
    assert d.loc[~d.line_type.eq("consensus"),"gap"].isna().all()


def test_reprice_fixed_distributions_keeps_pushes_and_only_consensus_gaps():
    base={"game_id":"g","pid":"p","stat":"rec","projection":2.,"book":"a","over_odds":-110,"under_odds":-110,"line_status":"current"}
    d=consensus(pd.DataFrame([base|{"market_line":2},base|{"book":"novig","market_line":3}]))
    d=compare(d,{("g","p","rec"):np.array([0,1,2,3])})
    assert d.loc[0,"p_over"]==.25 and d.loc[0,"p_under"]==.5 and d.loc[0,"p_push"]==.25
    assert d.loc[0,"p_over_no_push"]==pytest.approx(1/3)
    assert d.loc[0,"no_vig_market_probability"]==pytest.approx(.5)
    assert pd.isna(d.loc[1,"gap"])


def test_atd_one_sided_price_is_not_claimed_no_vig_and_first_td_incompatible():
    base={"game_id":"g","pid":"p","projection":.3,"book":"a","market_line":.5,"over_odds":150,"under_odds":None}
    d=compare(consensus(pd.DataFrame([base|{"stat":"anytime_td"},base|{"stat":"first_td"}])),{})
    assert d.loc[0,"market_probability"]==.4
    assert pd.isna(d.loc[0,"no_vig_market_probability"])
    assert "raw" in d.loc[0,"market_probability_basis"]
    assert pd.isna(d.loc[1,"gap"]) and pd.isna(d.loc[1,"market_probability"])
    assert "unverified" in d.loc[1,"benchmark_scope_status"]


def test_multi_td_threshold_is_never_a_binary_atd_comparison():
    d=pd.DataFrame([{"game_id":"g","pid":"p","stat":"anytime_td","projection":.4,"book":"a","market_line":1.5}])
    d=compare(consensus(d),{})
    assert pd.isna(d.loc[0,"gap"]) and pd.isna(d.loc[0,"p_over"])


def test_coherence_exposes_missing_eligible_volume_and_scorer_count_semantics():
    totals={"pass_yds":200.,"rec_yds":200.,"rush_yds":100.,"rec":20.,"pass_tds":2.,"rec_tds":2.,"rush_tds":1.,"anytime_td":2.5}
    frame=pd.DataFrame([{"row_type":"player","game_id":"g","team":"SF","pid":"p","stat":s,"projection":v}
                         for s,v in [("pass_yds",200),("rec_yds",100),("rush_yds",100),("rec",20),("pass_tds",2),("anytime_td",2.5)]])
    _,d=coherence(frame,{"g":{"SF":totals}})
    assert "rec_yds" in d.coherence_flag.iloc[0]
    assert d.atd_vs_td_count_gap.iloc[0]==-.5
    assert "not TD count" in d.atd_semantics.iloc[0]
    assert totals["rec_yds"]==200


def test_unknown_scenarios_cannot_satisfy_tier_a():
    d=pd.DataFrame([{"game_id":"g","pid":"p","stat":"rec","projection":6.,"q10":2.,"q50":5.,"q90":9.,"market_line":3.5,
        "line_type":"consensus","line_status":"current","gap":2.5,"member_min":4.,"member_max":7.,"coherence_flag":"coherent"}])
    a=leans(d,{("g","p","rec"):"stable"},{})
    assert a.confidence_tier.iloc[0]=="B"
    a=leans(d,{("g","p","rec"):"stable"},{("g","p","rec"):"robust"})
    assert a.confidence_tier.iloc[0]=="A"


def test_quantile_floor_is_output_only_and_keeps_signed_game_margin(tmp_path,monkeypatch):
    from lab.props import projections10 as p
    monkeypatch.setattr(p,"REPORTS_DIR",tmp_path)
    monkeypatch.setattr(p,"OUT",tmp_path)
    monkeypatch.delenv("NFL_LAB_ARTIFACT_NODE",raising=False)
    frame=pd.DataFrame([{"game_id":"g","name":"fixture","row_type":"player","stat":"rush_yds","projection":1.,"q10":-5.,"q50":1.,"q90":8.,"training_cutoff_date":"2026-10-19"},
        {"game_id":"g","name":"game","row_type":"game","stat":"margin","projection":-2.,"q10":-8.,"q50":-2.,"q90":4.,"training_cutoff_date":"2026-10-19"}])
    p.write_sheet(frame,7)
    rows=json.loads((tmp_path/"projections_2026_w7.json").read_text())["rows"]
    assert rows[0]["q10"]==0 and rows[1]["q10"]==-8
    assert frame.q10.iloc[0]==-5


def test_relocation_restores_state_after_failure(tmp_path):
    from lab.props.amendment2.revision import relocated,P,S
    old=P.OUT,S.OUT,P.REPORTS_DIR
    with pytest.raises(RuntimeError):
        with relocated(tmp_path):
            assert P.OUT==S.OUT==tmp_path
            raise RuntimeError("fixture")
    assert (P.OUT,S.OUT,P.REPORTS_DIR)==old


def test_stability_tolerances_are_fixed():
    from lab.props.amendment2.simulation import tolerance
    assert tolerance("margin")==1 and tolerance("total")==1
    assert tolerance("pass_yds")==5 and tolerance("rec")==1
    assert tolerance("first_td")==.03 and tolerance("anytime_td")==.03


def test_eight_hour_window_includes_wrap_and_rejects_hard_stop_overrun():
    from lab.props.amendment2.run import planned_window
    start=pd.Timestamp("2026-10-20T08:00:00-04:00")
    end,wrap=planned_window(start)
    assert end-start==pd.Timedelta(hours=8)
    assert end-wrap==pd.Timedelta(minutes=45)
    with pytest.raises(ValueError,match="hard stop"):
        planned_window(pd.Timestamp("2026-10-20T10:00:00-04:00"))


def test_saved_seed_and_scenario_diagnostics_keep_instability_visible(tmp_path):
    from lab.props.amendment2.simulation import analyze,SCENARIOS,SEEDS
    base={"game_id":"2026_07_FIX_TEST","pid":"p","stat":"pass_yds","mode":"sim_independent","q10":50.,"q90":200.}
    rows=[base|{"seed":seed,"scenario":"expected","mean":100.,"q50":median} for seed,median in zip(SEEDS,[100.,102.,110.])]
    rows += [base|{"seed":SEEDS[0],"scenario":scenario,"mean":200. if i==0 else 100.,"q50":100.} for i,scenario in enumerate(SCENARIOS)]
    pd.DataFrame(rows).to_parquet(tmp_path/"2026_07_FIX_TEST.parquet")
    result=analyze(tmp_path)
    assert result["games"]==1
    stability=pd.read_csv(tmp_path/"stability_summary.csv")
    sensitivity=pd.read_csv(tmp_path/"scenario_summary.csv")
    assert stability.stability_flag.iloc[0]=="unstable" and stability.range.iloc[0]==10
    assert sensitivity.scenario_sensitivity.iloc[0]=="sensitive"


def test_saved_benchmark_line_diagnostics_use_supplied_line_and_isolated_output(tmp_path):
    from lab.props.ensemble.probability_research import run
    from scipy.stats import poisson
    frame=pd.DataFrame([{"season":2022,"game_id":"g","pid":"p","week":1,"stat":"rec","actual":2.,
                         "equal":2.,"recent_mean":3.,"fixed_line":1.5}])
    destination=tmp_path/"secondary"
    result=run(frame,destination,seed=20261020,line_column="fixed_line")
    data=pd.read_parquet(destination/"synthetic_ou2022.parquet")
    assert data.line.eq(1.5).all()
    assert data.loc[data.method.eq("equal"),"p_over"].iloc[0]==pytest.approx(poisson.sf(1,2))
    assert "not actual market" in result["line_definition"]


def test_controller_logs_failed_owned_command_without_aborting_following_work(tmp_path,monkeypatch):
    import sys
    from lab.props.amendment2 import run
    messages=[]
    monkeypatch.setattr(run,"note",messages.append)
    code=run.command([sys.executable,"-c","print(123); raise SystemExit(3)"],tmp_path/"failure.log",10)
    assert code==3 and any("FAILED" in m for m in messages)
    assert "123" in (tmp_path/"failure.log").read_text()
    assert run.command([sys.executable,"-c","pass"],tmp_path/"next.log",10)==0


def test_expected_zero_role_for_backup_remains_available_for_scenario_deltas():
    from lab.props.amendment2.simulation import summarize,STATS
    result={"points":np.array([[7,0],[0,0]]),"first_td_col":np.array([0,-1]),
            "stats":{s:np.zeros((2,1)) for s in STATS}}
    rows=summarize(result,{"starter":0},{"starter":"SF","backup":"SF"},"g","sim_independent",20261020,"expected",{"starter","backup"})
    d=pd.DataFrame(rows)
    assert d.loc[d.pid.eq("backup")&d.stat.eq("pass_yds"),"mean"].iloc[0]==0
    assert d.loc[d.stat.eq("first_td"),"mean"].sum()==pytest.approx(1)


def test_projection_markdown_contains_forecast_point_interval_and_signed_spread(tmp_path):
    from lab.props.amendment2.sheets import export
    d=pd.DataFrame([{"game_id":"g","name":"away at home","stat":"margin","projection":2.5,
        "q10":-9.,"q50":2.,"q90":13.,"spread_display":"SF -2.5","consensus_line":3.,"consensus_spread_display":"SF -3.0"}])
    export(d,tmp_path/"projection",heading="fixture")
    text=(tmp_path/"projection.md").read_text()
    assert "projection" in text and "q10" in text and "q90" in text
    assert "2.500" in text and "-9.000" in text and "SF -2.5" in text and "SF -3.0" in text


def test_exact_game_roster_alias_can_disambiguate_but_never_guess_or_map_defense():
    from lab.props.amendment2.revision import contextual_identity
    quotes=pd.DataFrame([{"game_id":"g","player":name,"pid":None} for name in ("Same Name","Unknown Name","Team Defense")])
    candidates=pd.DataFrame([{"game_id":"g","pid":"right"},{"game_id":"other","pid":"wrong"}])
    def mapping_fn(eligible_ids):
        assert eligible_ids=={"right"}
        return {"samename":"right","teamdefense":"right"}
    result=contextual_identity(quotes,candidates,mapping_fn)
    assert result.pid.iloc[0]=="right"
    assert pd.isna(result.pid.iloc[1]) and pd.isna(result.pid.iloc[2])
    assert quotes.pid.isna().all()


def test_detached_search_startup_lock_absence_is_not_completion():
    from lab.props.amendment2.run import search_lifecycle
    seen=False;ready=[]
    for active in (None,None,"owned","owned",None):
        seen,done=search_lifecycle("owned",seen,active)
        ready.append(done)
    assert ready==[False,False,False,False,True]
    assert search_lifecycle("owned",True,"another")== (True,False)
