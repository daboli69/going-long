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
